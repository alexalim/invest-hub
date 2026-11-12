"""야후 파이낸스 차트 엔드포인트: 미국 주식, 지수, 환율, 원자재, 국내 분봉."""
from . import http

URL = "https://query1.finance.yahoo.com/v8/finance/chart/"
# 분봉 주기별로 야후가 허용하는 최대 조회 기간
INTRADAY = {"1m": ("1m", "5d"), "5m": ("5m", "1mo"), "15m": ("15m", "1mo"), "30m": ("30m", "1mo"), "60m": ("60m", "6mo")}
DAILY = {"day": "1d", "week": "1wk", "month": "1mo"}


def ticker_us(code: str) -> str:
    return code.replace(".", "-")


async def chart(ticker: str, tf: str = "day", rng: str | None = None, ttl: float = 30) -> dict:
    """반환: {candles: [(ts,o,h,l,c,v)], meta}. 일봉 이상은 ts를 UTC 자정으로, 분봉은 거래소 현지 시각으로 맞춘다."""
    if tf in INTRADAY:
        interval, default_rng = INTRADAY[tf]
    else:
        interval, default_rng = DAILY.get(tf, "1d"), "5y"
    d = await http.get_json(URL + ticker, {"interval": interval, "range": rng or default_rng, "includePrePost": "false"}, ttl=ttl)
    res = (d.get("chart") or {}).get("result") or []
    if not res:
        return {"candles": [], "meta": {}}
    r = res[0]
    meta = r.get("meta") or {}
    off = int(meta.get("gmtoffset") or 0)
    ts = r.get("timestamp") or []
    qd = ((r.get("indicators") or {}).get("quote") or [{}])[0]
    o, h, l, c, v = (qd.get(k) or [] for k in ("open", "high", "low", "close", "volume"))
    out, seen = [], {}
    for i, t in enumerate(ts):
        if i >= len(c) or c[i] is None or o[i] is None:
            continue
        local = t + off
        key = local - local % 86400 if tf not in INTRADAY else local
        if key in seen:
            if tf not in INTRADAY and seen[key] % 86400 == 0 and local % 86400:
                # 선물: 확정된 일봉(자정 시각) 뒤에 같은 날짜로 오는 진행 중 봉은 다음 거래일(저녁 개장) 것이다
                key += 86400
            else:  # 장중에는 마지막 봉이 중복으로 올 수 있다
                out = [x for x in out if x[0] != key]
        seen[key] = local
        out.append((key, float(o[i]), float(h[i]), float(l[i]), float(c[i]), float(v[i] or 0)))
    out.sort(key=lambda x: x[0])
    return {"candles": out, "meta": meta}


async def quote(ticker: str) -> dict | None:
    d = await chart(ticker, "day", "5d", ttl=20)
    m = d["meta"]
    price = m.get("regularMarketPrice")
    if price is None:
        return None
    cs = d["candles"]
    prev = cs[-2][4] if len(cs) >= 2 else m.get("chartPreviousClose") or price
    last = cs[-1] if cs else None
    return dict(price=float(price), prev_close=float(prev), change=float(price - prev),
                change_pct=float((price / prev - 1) * 100) if prev else 0.0,
                open=last[1] if last else None, high=m.get("regularMarketDayHigh") or (last[2] if last else None),
                low=m.get("regularMarketDayLow") or (last[3] if last else None),
                volume=m.get("regularMarketVolume"), currency=m.get("currency"), name=m.get("shortName") or m.get("longName"))
