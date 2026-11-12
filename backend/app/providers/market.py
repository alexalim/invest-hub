"""시세 통합 계층. 심볼은 '접두사:코드' 형식이다.
KR:005930 (국내), US:AAPL (미국), CR:KRW-BTC (코인), IX/FX/CM/RT:* (지수·환율·원자재·금리)."""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone

import numpy as np

from .. import db
from . import naver, upbit, yahoo

log = logging.getLogger("market")

# 심볼: (출처, 코드, 이름, 분류). 출처 kidx=국내지수, widx=해외지수, 그 외는 네이버 marketindex 카테고리
MACRO = {
    "IX:KOSPI": ("kidx", "KOSPI", "코스피", "index"), "IX:KOSDAQ": ("kidx", "KOSDAQ", "코스닥", "index"),
    "IX:KOSPI200": ("kidx", "KPI200", "코스피 200", "index"), "IX:K200F": ("kidx", "FUT", "코스피 200 선물", "future"),
    "IX:SPX": ("widx", ".INX", "S&P 500", "index"), "IX:NASDAQ": ("widx", ".IXIC", "나스닥 종합", "index"),
    "IX:DOW": ("widx", ".DJI", "다우존스", "index"), "IX:SOX": ("widx", ".SOX", "필라델피아 반도체", "index"),
    "IX:VIX": ("widx", ".VIX", "VIX 변동성", "index"), "IX:NIKKEI": ("widx", ".N225", "닛케이 225", "index"),
    "IX:SHANGHAI": ("widx", ".SSEC", "상하이 종합", "index"), "IX:HSI": ("widx", ".HSI", "항셍", "index"),
    "IX:DAX": ("widx", ".GDAXI", "독일 DAX", "index"),
    # yh = 야후 (네이버에 없는 지수·선물). 선물은 거의 24시간 움직여 한국 장중에도 미국 분위기를 볼 수 있다
    "IX:RUT": ("yh", "^RUT", "러셀 2000", "index"), "IX:TWII": ("yh", "^TWII", "대만 가권", "index"),
    "IX:EWY": ("yh", "EWY", "MSCI 한국 ETF (EWY)", "index"),
    "IX:ESF": ("yh", "ES=F", "S&P 500 선물", "future"), "IX:NQF": ("yh", "NQ=F", "나스닥 100 선물", "future"),
    "IX:YMF": ("yh", "YM=F", "다우 선물", "future"),
    "FX:USDKRW": ("exchange", "FX_USDKRW", "달러/원", "fx"), "FX:JPYKRW": ("exchange", "FX_JPYKRW", "엔/원(100엔)", "fx"),
    "FX:EURKRW": ("exchange", "FX_EURKRW", "유로/원", "fx"), "FX:CNYKRW": ("exchange", "FX_CNYKRW", "위안/원", "fx"),
    "FX:DXY": ("exchange", ".DXY", "달러 인덱스", "fx"),
    "CM:GOLD": ("metals", "GCcv1", "국제 금", "commodity"), "CM:SILVER": ("metals", "SIcv1", "은", "commodity"),
    "CM:COPPER": ("metals", "HGcv1", "구리", "commodity"), "CM:WTI": ("energy", "CLcv1", "WTI 원유", "commodity"),
    "CM:BRENT": ("energy", "LCOcv1", "브렌트유", "commodity"), "CM:NATGAS": ("energy", "NGcv1", "천연가스", "commodity"),
    "RT:US10Y": ("bond", "US10YT=RR", "미국 국채 10년", "rate"), "RT:KR10Y": ("bond", "KR10YT=RR", "한국 국채 10년", "rate"),
    "RT:JP10Y": ("bond", "JP10YT=RR", "일본 국채 10년", "rate"), "RT:DE10Y": ("bond", "DE10YT=RR", "독일 국채 10년", "rate"),
}
DAILY_TFS = ("day", "week", "month")
_qcache: dict[str, tuple[float, dict]] = {}


def parse(symbol: str) -> tuple[str, str]:
    p, _, code = symbol.partition(":")
    return p, code


def instrument(symbol: str) -> dict | None:
    row = db.one("SELECT * FROM instruments WHERE symbol=?", (symbol,))
    if row is None and symbol in MACRO:
        _, code, name, kind = MACRO[symbol]
        return dict(symbol=symbol, market="MACRO", kind=kind, code=code, name=name, currency=None)
    return row


def name_of(symbol: str) -> str:
    if symbol in MACRO:
        return MACRO[symbol][2]
    return db.val("SELECT name FROM instruments WHERE symbol=?", (symbol,)) or parse(symbol)[1]


def names(symbols: list[str]) -> dict[str, str]:
    out = {s: MACRO[s][2] for s in symbols if s in MACRO}
    rest = [s for s in symbols if s not in out]
    if rest:
        ph = ",".join("?" * len(rest))
        out.update({r["symbol"]: r["name"] for r in db.q(f"SELECT symbol,name FROM instruments WHERE symbol IN ({ph})", rest)})
    return out


def yahoo_ticker(symbol: str) -> str:
    p, code = parse(symbol)
    if p == "KR":
        mk = db.val("SELECT market FROM instruments WHERE symbol=?", (symbol,))
        return f"{code}.KQ" if mk == "KOSDAQ" else f"{code}.KS"
    return yahoo.ticker_us(code)


def reuters(symbol: str) -> str | None:
    extra = db.val("SELECT extra FROM instruments WHERE symbol=?", (symbol,))
    return json.loads(extra or "{}").get("reuters")


def currency(symbol: str) -> str:
    return "USD" if symbol.startswith("US:") else "KRW"


def resample(rows: list[tuple], tf: str) -> list[tuple]:
    """일봉을 주봉·월봉으로 묶는다. 봉 시각은 묶음의 첫 거래일."""
    out: list[list] = []
    key_prev = None
    for ts, o, h, l, c, v in rows:
        dt = datetime.fromtimestamp(ts, timezone.utc)
        key = (dt.isocalendar()[0], dt.isocalendar()[1]) if tf == "week" else (dt.year, dt.month)
        if key != key_prev:
            out.append([ts, o, h, l, c, v])
            key_prev = key
        else:
            b = out[-1]
            b[2], b[3], b[4], b[5] = max(b[2], h), min(b[3], l), c, b[5] + v
    return [tuple(b) for b in out]


async def _daily_rows(symbol: str, days_back: int) -> list[tuple]:
    """출처별 일봉 조회 (DB를 거치지 않는 원본)."""
    p, code = parse(symbol)
    start = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
    if symbol in MACRO:
        src, mcode = MACRO[symbol][0], MACRO[symbol][1]
        if src in ("kidx", "widx"):
            return await naver.candles_index_day(mcode, src == "widx", start)
        if src == "yh":
            rng = "1mo" if days_back <= 30 else "6mo" if days_back <= 180 else "2y" if days_back <= 730 else "5y"
            return (await yahoo.chart(mcode, "day", rng, ttl=0))["candles"]
        return await naver.marketindex_candles(src, mcode, min(1500, int(days_back * 0.72) + 5))
    if p == "KR":
        return await naver.candles_kr(code, "day", start)
    if p == "CR":
        return await upbit.candles(code, "day", min(2000, days_back))
    reut = reuters(symbol)
    rows = await naver.candles_us_day(reut, start) if reut else []
    if not rows:
        rng = "1mo" if days_back <= 30 else "6mo" if days_back <= 180 else "2y" if days_back <= 730 else "5y" if days_back <= 1830 else "max"
        rows = (await yahoo.chart(yahoo_ticker(symbol), "day", rng, ttl=0))["candles"]
    return rows


async def candles(symbol: str, tf: str = "day", count: int = 600) -> list[tuple]:
    p, code = parse(symbol)
    if p == "CR":
        return await upbit.candles(code, tf, count)
    if tf in DAILY_TFS:
        if p == "KR":
            span = {"day": 1.6, "week": 7.5, "month": 32}[tf] * count + 10
            start = (datetime.now() - timedelta(days=span)).strftime("%Y%m%d")
            return (await naver.candles_kr(code, tf, start))[-count:]
        mult = {"day": 1.6, "week": 7.5, "month": 32}[tf]
        rows = await _daily_rows(symbol, int(min(count * mult + 10, 365 * 12)))
        return (rows if tf == "day" else resample(rows, tf))[-count:]
    if p == "KR" and tf in naver.MINUTE:
        return (await naver.candles_kr_minute(code, tf))[-count:]
    if symbol in MACRO:
        if MACRO[symbol][0] == "kidx" and tf in naver.MINUTE:
            return (await naver.candles_kr_minute(MACRO[symbol][1], tf, index=True))[-count:]
        return []
    return (await yahoo.chart(yahoo_ticker(symbol), tf))["candles"][-count:]


async def sync_daily(symbol: str, max_age: int = 6 * 3600, years: int = 4) -> int:
    """일봉을 DB에 적재한다. 이미 있으면 최근 구간만 다시 받는다."""
    synced = db.val("SELECT synced_at FROM candle_sync WHERE symbol=? AND tf='day'", (symbol,))
    if synced and db.now() - synced < max_age:
        return 0
    last = db.val("SELECT MAX(ts) FROM candles WHERE symbol=? AND tf='day'", (symbol,))
    back = int((time.time() - last) / 86400) + 12 if last else 365 * years
    rows = await _daily_rows(symbol, back)
    if rows:
        db.many("INSERT OR REPLACE INTO candles(symbol,tf,ts,o,h,l,c,v) VALUES(?,?,?,?,?,?,?,?)",
                [(symbol, "day", *r) for r in rows])
    db.ex("INSERT OR REPLACE INTO candle_sync(symbol,tf,synced_at) VALUES(?, 'day', ?)", (symbol, db.now()))
    return len(rows)


def load_daily(symbol: str, n: int | None = None) -> dict[str, np.ndarray] | None:
    rows = db.conn().execute("SELECT ts,o,h,l,c,v FROM candles WHERE symbol=? AND tf='day' ORDER BY ts", (symbol,)).fetchall()
    if not rows:
        return None
    if n:
        rows = rows[-n:]
    a = np.array([tuple(r) for r in rows], dtype=np.float64)
    return dict(ts=a[:, 0].astype(np.int64), o=a[:, 1], h=a[:, 2], l=a[:, 3], c=a[:, 4], v=a[:, 5])


async def daily(symbol: str, n: int | None = None, max_age: int = 6 * 3600) -> dict[str, np.ndarray] | None:
    try:
        await sync_daily(symbol, max_age=max_age)
    except Exception as e:  # 수집 실패 시 저장분으로 계속한다
        log.warning("sync_daily %s failed: %s", symbol, e)
    return load_daily(symbol, n)


async def _macro_quotes(symbols: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for world in (False, True):
        src = "widx" if world else "kidx"
        group = {MACRO[s][1]: s for s in symbols if MACRO[s][0] == src}
        if group:
            try:
                for code, qd in (await naver.quotes_index(list(group), world)).items():
                    if code in group:
                        out[group[code]] = qd
            except Exception as e:
                log.warning("index quotes: %s", e)

    async def one(s):
        try:
            if MACRO[s][0] == "yh":
                qd = await yahoo.quote(MACRO[s][1])
            else:
                qd = await naver.marketindex_quote(MACRO[s][0], MACRO[s][1])
            if qd:
                out[s] = qd
        except Exception as e:
            log.warning("macro %s: %s", s, e)

    await asyncio.gather(*(one(s) for s in symbols if MACRO[s][0] not in ("kidx", "widx")))
    return out


async def quotes(symbols: list[str]) -> dict[str, dict]:
    """최신 시세. 3초 캐시. 조회 실패 종목은 instruments 테이블 값으로 대체한다."""
    now = time.time()
    out: dict[str, dict] = {}
    need = []
    for s in dict.fromkeys(symbols):
        hit = _qcache.get(s)
        if hit and hit[0] > now:
            out[s] = hit[1]
        else:
            need.append(s)
    if not need:
        return out
    kr = [parse(s)[1] for s in need if s.startswith("KR:")]
    cr = [parse(s)[1] for s in need if s.startswith("CR:")]
    us = [s for s in need if s.startswith("US:")]
    macro = [s for s in need if s in MACRO]
    tasks = []
    if kr:
        tasks.append(naver.quotes_kr(kr))
    if cr:
        tasks.append(upbit.quotes(cr))
    if us:
        rmap = {}
        ph = ",".join("?" * len(us))
        for r in db.q(f"SELECT symbol, extra FROM instruments WHERE symbol IN ({ph})", us):
            reut = json.loads(r["extra"] or "{}").get("reuters")
            if reut:
                rmap[reut] = r["symbol"]
        if rmap:
            tasks.append(naver.quotes_us(rmap))
    if macro:
        tasks.append(_macro_quotes(macro))
    for res in await asyncio.gather(*tasks, return_exceptions=True):
        if isinstance(res, Exception):
            log.warning("quote fetch failed: %r", res)
            continue
        for s, qd in res.items():
            if qd.get("price") is not None:
                _qcache[s] = (now + (20 if s in MACRO else 3), qd)
                out[s] = qd
    for s in [m for m in need if m not in out and m.startswith("US:")]:  # 목록에 없는 미국 종목은 야후로
        try:
            qd = await yahoo.quote(yahoo_ticker(s))
            if qd:
                _qcache[s] = (now + 15, qd)
                out[s] = qd
        except Exception:
            pass
    missing = [s for s in need if s not in out]
    if missing:
        ph = ",".join("?" * len(missing))
        for r in db.q(f"SELECT symbol,price,prev_close,change,change_pct,open,high,low,volume FROM instruments WHERE symbol IN ({ph})", missing):
            if r["price"] is not None:
                out[r.pop("symbol")] = dict(r, stale=True)
    return out


async def quote(symbol: str) -> dict | None:
    return (await quotes([symbol])).get(symbol)


async def usdkrw() -> float:
    qd = await quote("FX:USDKRW")
    return qd["price"] if qd else float(db.get_setting("last_usdkrw", 1400.0))


async def refresh_macro() -> int:
    qs = await quotes(list(MACRO))
    rows = []
    for s, (_, code, name, kind) in MACRO.items():
        qd = qs.get(s)
        if not qd:
            continue
        rows.append(dict(symbol=s, market="MACRO", kind=kind, code=code, name=name, name_en=None, price=qd["price"],
                         prev_close=qd["prev_close"], change=qd["change"], change_pct=qd["change_pct"],
                         open=qd.get("open"), high=qd.get("high"), low=qd.get("low"), volume=qd.get("volume"),
                         currency=None, extra=json.dumps({"traded": (qd.get("traded_at") or "")[:10]})))
    naver.upsert_instruments(rows)
    if "FX:USDKRW" in qs:
        db.set_setting("last_usdkrw", qs["FX:USDKRW"]["price"])
    return len(rows)


def search(text: str, limit: int = 20) -> list[dict]:
    t = text.strip()
    if not t:
        return []
    like = f"%{t}%"
    return db.q(
        "SELECT symbol,market,kind,code,name,name_en,price,change_pct,currency FROM instruments "
        "WHERE name LIKE ? OR code LIKE ? OR name_en LIKE ? "
        "ORDER BY (code=? COLLATE NOCASE) DESC, (name=?) DESC, (name LIKE ?) DESC, mcap DESC NULLS LAST LIMIT ?",
        (like, like.upper(), like, t, t, f"{t}%", limit))


def universe(markets: tuple[str, ...] = ("KOSPI", "KOSDAQ"), limit: int | None = None, kinds=("stock",)) -> list[str]:
    ph = ",".join("?" * len(markets))
    kp = ",".join("?" * len(kinds))
    sql = f"SELECT symbol FROM instruments WHERE market IN ({ph}) AND kind IN ({kp}) ORDER BY COALESCE(mcap, value, 0) DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [r["symbol"] for r in db.q(sql, (*markets, *kinds))]


async def bulk_sync(symbols: list[str], concurrency: int = 4, max_age: int = 12 * 3600, progress=None) -> int:
    sem = asyncio.Semaphore(concurrency)
    done = 0

    async def one(s):
        nonlocal done
        async with sem:
            try:
                await sync_daily(s, max_age=max_age)
            except Exception as e:
                log.warning("bulk sync %s: %r", s, e)
            done += 1
            if progress and done % 50 == 0:
                progress(done, len(symbols))
            await asyncio.sleep(0.03)

    await asyncio.gather(*(one(s) for s in symbols))
    return done


def kr_market_open() -> bool:
    now = datetime.now(timezone.utc) + timedelta(hours=9)
    return now.weekday() < 5 and (8, 0) <= (now.hour, now.minute) <= (20, 0)
