"""공용 HTTP 클라이언트. 호스트별 동시 요청 수를 제한하고 짧은 TTL 캐시를 둔다."""
import asyncio
import time
from urllib.parse import urlparse

import httpx

# 야후는 브라우저처럼 보이는 긴 UA를 429로 막고 짧은 UA는 통과시킨다 (2026-11 실측)
UA = "Mozilla/5.0"
_client: httpx.AsyncClient | None = None
_sems: dict[str, asyncio.Semaphore] = {}
_cache: dict[str, tuple[float, object]] = {}
LIMITS = {"api.upbit.com": 3, "query1.finance.yahoo.com": 2, "query2.finance.yahoo.com": 2}


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"},
            timeout=httpx.Timeout(15.0, connect=8.0), follow_redirects=True,
            limits=httpx.Limits(max_connections=40, max_keepalive_connections=20))
    return _client


def _sem(url: str) -> asyncio.Semaphore:
    host = urlparse(url).netloc
    if host not in _sems:
        _sems[host] = asyncio.Semaphore(LIMITS.get(host, 6))
    return _sems[host]


async def get(url: str, params: dict | None = None, headers: dict | None = None, retries: int = 2) -> httpx.Response:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with _sem(url):
                r = await client().get(url, params=params, headers=headers)
            if r.status_code == 429 or r.status_code >= 500:
                raise httpx.HTTPStatusError(f"{r.status_code}", request=r.request, response=r)
            return r
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            last = e
            if "finance.yahoo.com" in url:  # 야후는 호스트별로 제한이 따로 걸린다
                url = url.replace("query1.", "query2.") if "query1." in url else url.replace("query2.", "query1.")
            await asyncio.sleep(0.8 * (attempt + 1))
    raise last  # type: ignore[misc]


async def get_json(url: str, params: dict | None = None, ttl: float = 0, headers: dict | None = None):
    key = url + "?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
    if ttl:
        hit = _cache.get(key)
        if hit and hit[0] > time.time():
            return hit[1]
    r = await get(url, params=params, headers=headers)
    r.raise_for_status()
    data = r.json()
    if ttl:
        if len(_cache) > 5000:
            cutoff = time.time()
            for k in [k for k, v in _cache.items() if v[0] < cutoff]:
                _cache.pop(k, None)
        _cache[key] = (time.time() + ttl, data)
    return data


async def get_text(url: str, params: dict | None = None, ttl: float = 0, headers: dict | None = None) -> str:
    key = "T:" + url + "?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
    if ttl:
        hit = _cache.get(key)
        if hit and hit[0] > time.time():
            return hit[1]  # type: ignore[return-value]
    r = await get(url, params=params, headers=headers)
    r.raise_for_status()
    text = r.text
    if ttl:
        _cache[key] = (time.time() + ttl, text)
    return text


async def close():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
