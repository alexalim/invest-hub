"""네이버 증권 공개 엔드포인트: 국내·미국 종목 목록, 시세, 재무, 뉴스, 테마, 호가."""
import json
import re
from datetime import datetime, timezone

from .. import db
from . import http

M = "https://m.stock.naver.com/api"
W = "https://api.stock.naver.com"
POLL = "https://polling.finance.naver.com/api/realtime"
DOWN = {"FALLING", "LOWER_LIMIT"}


def num(s) -> float | None:
    """'197,700' '+1,509,865' '8.87배' '45.93%' 'N/A' 같은 표기를 숫자로."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    m = re.search(r"[-+]?\d[\d,]*\.?\d*", str(s))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def won_text(s) -> float | None:
    """'1,156조 3,939억' → 원."""
    if not s:
        return None
    total, found = 0.0, False
    for n, unit in re.findall(r"([\d,\.]+)\s*(조|억|만)", str(s)):
        total += float(n.replace(",", "")) * {"조": 1e12, "억": 1e8, "만": 1e4}[unit]
        found = True
    return total if found else num(s)


def _signed(item: dict, key: str) -> float | None:
    v = num(item.get(key))
    if v is None:
        return None
    name = (item.get("compareToPreviousPrice") or {}).get("name")
    return -abs(v) if name in DOWN else abs(v)


def _kr_row(s: dict, market: str) -> dict:
    price = num(s.get("closePrice"))
    chg = _signed(s, "compareToPreviousClosePrice") or 0.0
    val = num(s.get("accumulatedTradingValue"))
    mcap = num(s.get("marketValue"))
    return dict(symbol=f"KR:{s['itemCode']}", market=market, kind=s.get("stockEndType") or "stock", code=s["itemCode"],
                name=s.get("stockName"), name_en=None, price=price, prev_close=(price - chg) if price is not None else None,
                change=chg, change_pct=_signed(s, "fluctuationsRatio") or 0.0,
                volume=num(s.get("accumulatedTradingVolume")), value=val * 1e6 if val else None,
                mcap=mcap * 1e8 if mcap else None, currency="KRW",
                extra=json.dumps({"traded": (s.get("localTradedAt") or "")[:10]}))


UPSERT = """INSERT INTO instruments(symbol,market,kind,code,name,name_en,price,prev_close,change,change_pct,
  open,high,low,volume,value,mcap,sector,currency,extra,updated_at)
VALUES(:symbol,:market,:kind,:code,:name,:name_en,:price,:prev_close,:change,:change_pct,
  :open,:high,:low,:volume,:value,:mcap,:sector,:currency,:extra,:updated_at)
ON CONFLICT(symbol) DO UPDATE SET market=excluded.market,kind=excluded.kind,name=excluded.name,
  name_en=COALESCE(excluded.name_en,name_en),price=excluded.price,prev_close=excluded.prev_close,
  change=excluded.change,change_pct=excluded.change_pct,open=COALESCE(excluded.open,open),
  high=COALESCE(excluded.high,high),low=COALESCE(excluded.low,low),volume=excluded.volume,value=excluded.value,
  mcap=COALESCE(excluded.mcap,mcap),sector=COALESCE(excluded.sector,sector),currency=excluded.currency,
  extra=COALESCE(excluded.extra,extra),updated_at=excluded.updated_at"""


def upsert_instruments(rows: list[dict]):
    t = db.now()
    for r in rows:
        for k in ("open", "high", "low", "sector", "extra", "name_en", "mcap", "value", "volume"):
            r.setdefault(k, None)
        r["updated_at"] = t
    if rows:
        db.many(UPSERT, rows)


async def refresh_kr() -> int:
    total = 0
    for market in ("KOSPI", "KOSDAQ"):
        page = 1
        while True:
            d = await http.get_json(f"{M}/stocks/marketValue/{market}", {"page": page, "pageSize": 100})
            stocks = d.get("stocks") or []
            upsert_instruments([_kr_row(s, market) for s in stocks if s.get("itemCode")])
            total += len(stocks)
            if len(stocks) < 100 or page >= 40:
                break
            page += 1
    return total


async def refresh_us(pages: dict | None = None) -> int:
    pages = pages or {"NASDAQ": 6, "NYSE": 6, "AMEX": 1}
    total = 0
    for exch, n in pages.items():
        for page in range(1, n + 1):
            d = await http.get_json(f"{W}/stock/exchange/{exch}/marketValue", {"page": page, "pageSize": 100})
            rows = []
            for s in d.get("stocks") or []:
                code = s.get("symbolCode")
                price = num(s.get("closePriceRaw") or s.get("closePrice"))
                if not code or price is None:
                    continue
                chg = _signed(s, "compareToPreviousClosePriceRaw") or 0.0
                rows.append(dict(
                    symbol=f"US:{code}", market=exch, kind=s.get("stockEndType") or "stock", code=code,
                    name=s.get("stockName"), name_en=s.get("stockNameEng"), price=price, prev_close=price - chg,
                    change=chg, change_pct=_signed(s, "fluctuationsRatioRaw") or 0.0,
                    open=num(s.get("openPriceRaw")), high=num(s.get("highPriceRaw")), low=num(s.get("lowPriceRaw")),
                    volume=num(s.get("accumulatedTradingVolumeRaw")), value=num(s.get("accumulatedTradingValueRaw")),
                    mcap=num(s.get("marketValueRaw")), sector=(s.get("industryCodeType") or {}).get("industryGroupKor"),
                    currency="USD", extra=json.dumps({"reuters": s.get("reutersCode"), "traded": (s.get("localTradedAt") or "")[:10]})))
            upsert_instruments(rows)
            total += len(rows)
            if len(d.get("stocks") or []) < 100:
                break
    return total


def _quote(d: dict) -> dict:
    price = num(d.get("closePriceRaw") or d.get("closePrice"))
    chg = _signed(d, "compareToPreviousClosePrice") or 0.0
    over = d.get("overMarketPriceInfo") or {}
    return dict(price=price, prev_close=(price - chg) if price is not None else None, change=chg,
                change_pct=_signed(d, "fluctuationsRatio") or 0.0,
                open=num(d.get("openPrice")), high=num(d.get("highPrice")), low=num(d.get("lowPrice")),
                volume=num(d.get("accumulatedTradingVolume")), market_status=d.get("marketStatus"),
                over_price=num(over.get("overPrice")) if over.get("overMarketStatus") == "OPEN" else None,
                traded_at=d.get("localTradedAt"))


async def quotes_kr(codes: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(codes), 40):
        chunk = codes[i:i + 40]
        d = await http.get_json(f"{POLL}/domestic/stock/{','.join(chunk)}", ttl=3)
        for item in d.get("datas") or []:
            out[f"KR:{item['itemCode']}"] = _quote(item)
    return out


async def quotes_us(reuters: dict[str, str]) -> dict[str, dict]:
    """reuters: {'AAPL.O': 'US:AAPL'}"""
    out = {}
    keys = list(reuters)
    for i in range(0, len(keys), 30):
        chunk = keys[i:i + 30]
        d = await http.get_json(f"{POLL}/worldstock/stock/{','.join(chunk)}", ttl=5)
        for item in d.get("datas") or []:
            sym = reuters.get(item.get("reutersCode"))
            if sym:
                out[sym] = _quote(item)
    return out


_ROW = re.compile(r'\["(\d{8,12})",\s*([\d.]+|null),\s*([\d.]+|null),\s*([\d.]+|null),\s*([\d.]+|null),\s*([\d.]+|null)')


async def candles_kr(code: str, tf: str = "day", start: str = "20190101", end: str | None = None) -> list[tuple]:
    """일·주·월봉. (ts, o, h, l, c, v) — ts는 해당 날짜 UTC 자정."""
    end = end or datetime.now().strftime("%Y%m%d")
    text = await http.get_text("https://fchart.stock.naver.com/siseJson.naver", {
        "symbol": code, "requestType": 1, "startTime": start, "endTime": end, "timeframe": tf})
    out = []
    for m in _ROW.finditer(text):
        d, o, h, l, c, v = m.groups()
        if "null" in (o, h, l, c):
            continue
        ts = int(datetime(int(d[:4]), int(d[4:6]), int(d[6:8]), tzinfo=timezone.utc).timestamp())
        o, h, l, c = float(o), float(h), float(l), float(c)
        if o == 0:  # 거래정지일은 시가가 0으로 온다
            o = h = l = c
        out.append((ts, o, h, l, c, 0.0 if v == "null" else float(v)))
    return out


MINUTE = {"1m": "minute", "3m": "minute3", "5m": "minute5", "10m": "minute10", "15m": "minute15", "30m": "minute30", "60m": "minute60"}
MINUTE_DAYS = {"1m": 4, "3m": 8, "5m": 12, "10m": 20, "15m": 30, "30m": 60, "60m": 120}


def _ts(s: str) -> int:
    s = s.ljust(14, "0")
    return int(datetime(int(s[:4]), int(s[4:6]), int(s[6:8]), int(s[8:10]), int(s[10:12]), tzinfo=timezone.utc).timestamp())


def _chart_rows(d: list) -> list[tuple]:
    out = []
    for r in d or []:
        c = r.get("closePrice", r.get("currentPrice"))
        when = r.get("localDateTime") or r.get("localDate")
        if c is None or not when:
            continue
        o = r.get("openPrice") or c
        out.append((_ts(when), float(o), float(r.get("highPrice") or max(o, c)), float(r.get("lowPrice") or min(o, c)),
                    float(c), float(r.get("accumulatedTradingVolume") or 0)))
    return out


async def candles_kr_minute(code: str, tf: str, index: bool = False) -> list[tuple]:
    """국내 분봉. ts는 한국 시각을 UTC인 것처럼 표기한다 (차트 축 표시용)."""
    from datetime import timedelta
    now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=9)
    start = now - timedelta(days=MINUTE_DAYS[tf])
    kind = "index" if index else "item"
    d = await http.get_json(f"{W}/chart/domestic/{kind}/{code}/{MINUTE[tf]}", {
        "startDateTime": start.strftime("%Y%m%d0000"), "endDateTime": now.strftime("%Y%m%d2359")}, ttl=5)
    return _chart_rows(d)


async def candles_us_day(reuters: str, start: str, end: str | None = None) -> list[tuple]:
    end = end or datetime.now().strftime("%Y%m%d")
    d = await http.get_json(f"{W}/chart/foreign/item/{reuters}/day", {"startDateTime": start, "endDateTime": end}, ttl=30)
    return _chart_rows(d)


def _infos(d: dict) -> dict:
    return {i.get("code"): i.get("value") for i in d.get("totalInfos") or []}


async def integration_kr(code: str) -> dict:
    d = await http.get_json(f"{M}/stock/{code}/integration", ttl=60)
    info = _infos(d)
    return dict(
        per=num(info.get("per")), pbr=num(info.get("pbr")), eps=num(info.get("eps")), bps=num(info.get("bps")),
        est_per=num(info.get("cnsPer")), est_eps=num(info.get("cnsEps")), div_yield=num(info.get("dividendYieldRatio")),
        dividend=num(info.get("dividend")), high52=num(info.get("highPriceOf52Weeks")), low52=num(info.get("lowPriceOf52Weeks")),
        open=num(info.get("openPrice")), high=num(info.get("highPrice")), low=num(info.get("lowPrice")),
        foreign_rate=num(info.get("foreignRate")), mcap=won_text(info.get("marketValue")),
        value=won_text(info.get("accumulatedTradingValue")), volume=num(info.get("accumulatedTradingVolume")),
        industry_code=d.get("industryCode"), description=d.get("description"),
        trend=[dict(date=t.get("bizdate"), foreign=num(t.get("foreignerPureBuyQuant")), organ=num(t.get("organPureBuyQuant")),
                    individual=num(t.get("individualPureBuyQuant")), close=num(t.get("closePrice")),
                    foreign_hold=num(t.get("foreignerHoldRatio"))) for t in d.get("dealTrendInfos") or []],
        researches=d.get("researches") or [], consensus=d.get("consensusInfo"),
        peers=[dict(symbol=f"KR:{p.get('itemCode')}", name=p.get("stockName"), price=num(p.get("closePrice")),
                    change_pct=_signed(p, "fluctuationsRatio")) for p in d.get("industryCompareInfo") or []])


async def integration_us(reuters: str) -> dict:
    d = await http.get_json(f"{W}/stock/{reuters}/integration", ttl=120)
    b = await http.get_json(f"{W}/stock/{reuters}/basic", ttl=30)
    info = {i.get("code"): i.get("value") for i in b.get("stockItemTotalInfos") or []}
    return dict(
        per=num(info.get("per")), pbr=num(info.get("pbr")), eps=num(info.get("eps")), bps=num(info.get("bps")),
        div_yield=num(info.get("dividendYieldRatio")), dividend=num(info.get("dividend")),
        high52=num(info.get("highPriceOf52Weeks")), low52=num(info.get("lowPriceOf52Weeks")),
        open=num(info.get("openPrice")), high=num(info.get("highPrice")), low=num(info.get("lowPrice")),
        mcap=num(b.get("marketValueFullRaw")), volume=num(info.get("accumulatedTradingVolume")),
        description=d.get("corporateOverview"), trend=[], researches=[], consensus=d.get("consensusInfo"),
        industry=(b.get("industryCodeType") or {}).get("industryGroupKor"),
        peers=[dict(symbol=f"US:{p.get('symbolCode')}", name=p.get("stockName"), price=num(p.get("closePrice")),
                    change_pct=_signed(p, "fluctuationsRatio")) for p in _peer_list(d.get("industryCompareInfo")) if p.get("symbolCode")])


def _peer_list(v) -> list[dict]:
    if isinstance(v, dict):  # 미국 종목은 {업종정보..., stocks: [...]} 형태로 온다
        v = next((x for x in v.values() if isinstance(x, list)), [])
    return [x for x in v or [] if isinstance(x, dict)]


async def news_us(reuters: str, page: int = 1, size: int = 20) -> list[dict]:
    d = await http.get_json(f"{W}/news/worldStock/{reuters}", {"pageSize": size, "page": page}, ttl=180)
    out = []
    for it in d or []:
        dt = str(it.get("dt") or "")
        when = f"{dt[:4]}-{dt[4:6]}-{dt[6:8]} {dt[8:10]}:{dt[10:12]}" if len(dt) >= 12 else dt
        out.append(dict(title=_unescape(it.get("tit") or ""), summary=_unescape(it.get("subcontent") or ""), office=it.get("ohnm"),
                        datetime=when, image=it.get("thumbUrl"),
                        url=f"https://m.stock.naver.com/worldstock/stock/{reuters}/news/view/{it.get('oid')}/{it.get('aid')}"))
    return out


def _finance(d: dict) -> dict:
    fi = d.get("financeInfo") or d
    cols = [dict(key=t.get("key"), title=t.get("title"), consensus=t.get("isConsensus") == "Y") for t in fi.get("trTitleList") or []]
    rows = []
    for r in fi.get("rowList") or []:
        rows.append(dict(title=r.get("title"), values={k: num((v or {}).get("value")) for k, v in (r.get("columns") or {}).items()}))
    return dict(columns=cols, rows=rows, unit=d.get("unit"))


async def finance_kr(code: str, period: str = "annual") -> dict:
    return _finance(await http.get_json(f"{M}/stock/{code}/finance/{period}", ttl=3600))


async def finance_us(reuters: str, period: str = "annual") -> dict:
    return _finance(await http.get_json(f"{W}/stock/{reuters}/finance/{period}", ttl=3600))


async def news_kr(code: str, page: int = 1, size: int = 20) -> list[dict]:
    d = await http.get_json(f"{M}/news/stock/{code}", {"pageSize": size, "page": page}, ttl=120)
    out = []
    for grp in d or []:
        for it in grp.get("items") or []:
            out.append(_news(it))
    return out


def _news(it: dict) -> dict:
    dt = it.get("datetime") or ""
    when = f"{dt[:4]}-{dt[4:6]}-{dt[6:8]} {dt[8:10]}:{dt[10:12]}" if len(dt) >= 12 else dt
    return dict(title=_unescape(it.get("title") or it.get("tit") or ""), summary=_unescape(it.get("body") or it.get("subcontent") or ""),
                office=it.get("officeName") or it.get("ohnm"), datetime=when, image=it.get("imageOriginLink") or it.get("thumbUrl"),
                url=f"https://n.news.naver.com/mnews/article/{it.get('officeId') or it.get('oid')}/{it.get('articleId') or it.get('aid')}")


def _unescape(s: str) -> str:
    import html
    return html.unescape(s or "")


async def main_news(page: int = 1, size: int = 30, category: str = "mainnews") -> list[dict]:
    d = await http.get_json(f"{M}/news/list", {"category": category, "page": page, "pageSize": size}, ttl=120)
    return [_news(it) for it in d or []]


async def disclosure_kr(code: str, page: int = 1, size: int = 20) -> list[dict]:
    d = await http.get_json(f"{M}/stock/{code}/disclosure", {"page": page, "pageSize": size}, ttl=300)
    return [dict(title=x.get("title"), datetime=(x.get("datetime") or "")[:16].replace("T", " "), author=x.get("author"),
                 url=f"https://m.stock.naver.com/domestic/stock/{code}/notice/{x.get('disclosureId')}") for x in d or []]


async def research_kr(code: str, page: int = 1, size: int = 20) -> list[dict]:
    d = await http.get_json(f"{M}/research/stock/{code}", {"page": page, "pageSize": size}, ttl=600)
    return [dict(title=x.get("title"), broker=x.get("brokerName"), date=x.get("writeDate"), preview=x.get("previewContent"),
                 url=f"https://m.stock.naver.com/investment/research/company/{x.get('researchId')}") for x in d or []]


async def asking_kr(code: str) -> dict:
    d = await http.get_json(f"{M}/stock/{code}/askingPrice", ttl=2)
    conv = lambda xs: [dict(price=num(x.get("price")), qty=num(x.get("count"))) for x in xs or []]
    return dict(prev_close=num(d.get("lastClosePrice")), asks=conv(d.get("sellInfo")), bids=conv(d.get("buyInfos")),
                total_ask=num(d.get("totalSell")), total_bid=num(d.get("totalBuy")))


async def trend_kr(code: str) -> list[dict]:
    d = await http.get_json(f"{M}/stock/{code}/trend", ttl=600)
    return [dict(date=t.get("bizdate"), foreign=num(t.get("foreignerPureBuyQuant")), organ=num(t.get("organPureBuyQuant")),
                 individual=num(t.get("individualPureBuyQuant")), close=num(t.get("closePrice")),
                 foreign_hold=num(t.get("foreignerHoldRatio")), volume=num(t.get("accumulatedTradingVolume"))) for t in d or []]


async def refresh_groups(kind: str) -> int:
    """kind: theme | industry — 그룹 목록과 등락률."""
    page, rows = 1, []
    while True:
        d = await http.get_json(f"{M}/stocks/{kind}", {"page": page, "pageSize": 100})
        gs = d.get("groups") or []
        rows += [(kind, g["no"], g.get("name"), num(g.get("changeRate")), g.get("totalCount"), g.get("riseCount"),
                  g.get("fallCount"), db.now()) for g in gs]
        if len(gs) < 100 or page >= 10:
            break
        page += 1
    if rows:
        db.many("INSERT INTO themes(kind,no,name,change_pct,total,rise,fall,updated_at) VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(kind,no) DO UPDATE SET name=excluded.name,change_pct=excluded.change_pct,total=excluded.total,"
                "rise=excluded.rise,fall=excluded.fall,updated_at=excluded.updated_at", rows)
    return len(rows)


async def group_stocks(kind: str, no: int) -> list[str]:
    d = await http.get_json(f"{M}/stocks/{kind}/{no}", {"page": 1, "pageSize": 100}, ttl=300)
    syms = [f"KR:{s['itemCode']}" for s in d.get("stocks") or [] if s.get("itemCode")]
    if syms:
        db.ex("DELETE FROM theme_stocks WHERE kind=? AND no=?", (kind, no))
        db.many("INSERT OR IGNORE INTO theme_stocks(kind,no,symbol) VALUES(?,?,?)", [(kind, no, s) for s in syms])
    return syms


async def index_basic(code: str) -> dict:
    d = await http.get_json(f"{M}/index/{code}/basic", ttl=10)
    return dict(name=d.get("stockName"), **_quote(d))


async def index_trend(code: str) -> dict:
    d = await http.get_json(f"{M}/index/{code}/trend", ttl=60)
    return dict(date=d.get("bizdate"), individual=num(d.get("personalValue")), foreign=num(d.get("foreignValue")),
                institution=num(d.get("institutionalValue")))


async def ranking(kind: str, market: str, size: int = 30) -> list[dict]:
    """kind: up | down | quantTop(거래량) | priceTop(거래대금) 등."""
    d = await http.get_json(f"{M}/stocks/{kind}/{market}", {"page": 1, "pageSize": size}, ttl=30)
    return [_kr_row(s, market) for s in d.get("stocks") or [] if s.get("itemCode")]


# ── 지수·환율·원자재·금리 ─────────────────────────────────────────────
async def quotes_index(codes: list[str], world: bool) -> dict[str, dict]:
    path = "worldstock/index" if world else "domestic/index"
    d = await http.get_json(f"{POLL}/{path}/{','.join(codes)}", ttl=5 if not world else 30)
    out = {}
    for it in d.get("datas") or []:
        qd = _quote(it)
        qd["volume"] = num(it.get("accumulatedTradingVolumeRaw"))
        out[it.get("reutersCode") or it.get("itemCode")] = qd
    return out


async def marketindex_quote(category: str, code: str) -> dict | None:
    d = await http.get_json(f"{W}/marketindex/{category}/{code}", ttl=60)
    d = d.get("exchangeInfo") or d
    price = num(d.get("closePrice"))
    if price is None:
        return None
    chg = num(d.get("fluctuations")) or 0.0
    if (d.get("fluctuationsType") or {}).get("name") in DOWN:
        chg = -abs(chg)
    pct = num(d.get("fluctuationsRatio")) or 0.0
    pct = -abs(pct) if chg < 0 else abs(pct)
    info = {i.get("code"): i.get("value") for i in d.get("marketIndexTotalInfos") or []}
    return dict(price=price, prev_close=price - chg, change=chg, change_pct=pct, open=num(info.get("openPrice")),
                high=num(info.get("highPrice")), low=num(info.get("lowPrice")), volume=None,
                high52=num(info.get("highPriceOf52weeks")), low52=num(info.get("lowPriceOf52weeks")),
                market_status=d.get("marketStatus"), unit=d.get("unit"), traded_at=d.get("localTradedAt"))


async def marketindex_candles(category: str, code: str, count: int = 300) -> list[tuple]:
    out = {}
    for page in range(1, (count + 59) // 60 + 1):
        d = await http.get_json(f"{W}/marketindex/{category}/{code}/prices", {"page": page, "pageSize": 60}, ttl=300)
        if not isinstance(d, list) or not d:
            break
        for r in d:
            c = num(r.get("closePrice"))
            when = (r.get("localTradedAt") or "")[:10].replace("-", "")
            if c is None or len(when) != 8:
                continue
            o = num(r.get("openPrice")) or c
            out[when] = (_ts(when), o, num(r.get("highPrice")) or max(o, c), num(r.get("lowPrice")) or min(o, c), c, 0.0)
        if len(d) < 60:
            break
    return [out[k] for k in sorted(out)]


async def candles_index_day(code: str, world: bool, start: str, end: str | None = None) -> list[tuple]:
    end = end or datetime.now().strftime("%Y%m%d")
    scope = "foreign" if world else "domestic"
    d = await http.get_json(f"{W}/chart/{scope}/index/{code}/day", {"startDateTime": start, "endDateTime": end}, ttl=30)
    return _chart_rows(d)
