"""시장정보: 시장요약, 특징종목, 시장지표, 시장이슈, 테마·업종."""
import asyncio

from fastapi import APIRouter, Depends

from .. import auth, db
from ..providers import market, naver

router = APIRouter(prefix="/api/market", dependencies=[Depends(auth.current_user)])
COLS = "symbol,market,kind,code,name,price,change,change_pct,volume,value,mcap,currency"


def _macro(kinds=None) -> list[dict]:
    rows = db.q(f"SELECT {COLS},high,low,open,updated_at FROM instruments WHERE market='MACRO'")
    order = {s: i for i, s in enumerate(market.MACRO)}
    rows.sort(key=lambda r: order.get(r["symbol"], 99))
    return [r for r in rows if not kinds or r["kind"] in kinds]


def _top(where: str, order: str, limit: int = 10, params=()) -> list[dict]:
    return db.q(f"SELECT {COLS} FROM instruments WHERE {where} AND price IS NOT NULL ORDER BY {order} LIMIT {int(limit)}", params)


@router.get("/summary")
async def summary():
    trends = {}
    for code in ("KOSPI", "KOSDAQ"):
        try:
            trends[code] = await naver.index_trend(code)
        except Exception:
            trends[code] = None
    kr = "market IN ('KOSPI','KOSDAQ') AND kind='stock'"
    breadth = {}
    for mk in ("KOSPI", "KOSDAQ"):
        r = db.one("SELECT SUM(change_pct>0) up, SUM(change_pct<0) down, SUM(change_pct=0) flat, SUM(value) value "
                   "FROM instruments WHERE market=? AND kind='stock'", (mk,))
        breadth[mk] = r
    sectors = db.q("SELECT no,name,change_pct,total,rise,fall FROM themes WHERE kind='industry' ORDER BY change_pct DESC")
    try:
        news = (await naver.main_news(size=12))[:12]
    except Exception:
        news = []
    return dict(
        macro=_macro(), trends=trends, breadth=breadth, sectors=sectors, news=news,
        kr_value=_top(kr, "value DESC", 10), kr_up=_top(kr + " AND value>1e9", "change_pct DESC", 10),
        kr_down=_top(kr + " AND value>1e9", "change_pct ASC", 10),
        us_top=_top("market IN ('NASDAQ','NYSE')", "mcap DESC", 12),
        crypto=_top("market='CRYPTO'", "value DESC", 12),
        themes_up=db.q("SELECT no,name,change_pct,total,rise,fall FROM themes WHERE kind='theme' ORDER BY change_pct DESC LIMIT 8"),
        heatmap=dict(kr=_top(kr, "mcap DESC", 60),
                     us=_top("market IN ('NASDAQ','NYSE') AND kind='stock' AND mcap IS NOT NULL", "mcap DESC", 60),
                     cr=_top("market='CRYPTO' AND symbol LIKE 'CR:KRW-%'", "value DESC", 60)))


@router.get("/movers")
def movers(market_: str = "KR", limit: int = 30):
    """특징종목: 급등·급락·거래량 급증·52주 신고가/신저가."""
    limit = max(1, min(int(limit), 100))
    scope = {"KR": "market IN ('KOSPI','KOSDAQ') AND kind='stock'", "KOSPI": "market='KOSPI' AND kind='stock'",
             "KOSDAQ": "market='KOSDAQ' AND kind='stock'", "US": "market IN ('NASDAQ','NYSE','AMEX')",
             "CR": "market='CRYPTO'", "ETF": "market='KOSPI' AND kind='etf'"}.get(market_, "market IN ('KOSPI','KOSDAQ')")
    liquid = scope + (" AND value>5e8" if market_ not in ("US", "CR") else "")
    out = dict(
        up=_top(liquid, "change_pct DESC", limit), down=_top(liquid, "change_pct ASC", limit),
        value=_top(scope, "value DESC", limit), volume=_top(scope, "volume DESC", limit),
        high52=_top(liquid + " AND high52 IS NOT NULL AND price>=high52*0.995", "change_pct DESC", limit),
        low52=_top(liquid + " AND low52 IS NOT NULL AND price<=low52*1.005", "change_pct ASC", limit))
    # 거래량 급증: 최근 20일 평균 거래량 대비
    cutoff = db.now() - 35 * 86400
    icols = ",".join("i." + c for c in COLS.split(","))
    out["surge"] = db.q(
        f"SELECT {icols}, i.volume/x.avgv AS vol_ratio FROM instruments i JOIN "
        "(SELECT symbol, AVG(v) avgv FROM candles WHERE tf='day' AND ts>=? GROUP BY symbol) x ON x.symbol=i.symbol "
        f"WHERE i.symbol IN (SELECT symbol FROM instruments WHERE {scope}) AND x.avgv>0 AND i.volume>x.avgv*2 "
        f"AND i.price IS NOT NULL ORDER BY vol_ratio DESC LIMIT {int(limit)}", (cutoff,))
    return out


@router.get("/indicators")
def indicators():
    """시장지표: 지수·환율·원자재·금리."""
    rows = _macro()
    return {k: [r for r in rows if r["kind"] == k] for k in ("index", "future", "fx", "commodity", "rate")}


@router.get("/news")
async def news(page: int = 1, category: str = "mainnews"):
    return await naver.main_news(page=page, size=30, category=category)


@router.get("/groups/{kind}")
def groups(kind: str):
    kind = "industry" if kind == "industry" else "theme"
    return db.q("SELECT no,name,change_pct,total,rise,fall,updated_at FROM themes WHERE kind=? ORDER BY change_pct DESC", (kind,))


@router.get("/groups/{kind}/{no}")
async def group_detail(kind: str, no: int):
    kind = "industry" if kind == "industry" else "theme"
    try:
        syms = await naver.group_stocks(kind, no)
    except Exception:
        syms = [r["symbol"] for r in db.q("SELECT symbol FROM theme_stocks WHERE kind=? AND no=?", (kind, no))]
    info = db.one("SELECT * FROM themes WHERE kind=? AND no=?", (kind, no))
    rows = []
    if syms:
        ph = ",".join("?" * len(syms))
        rows = db.q(f"SELECT {COLS},per,pbr FROM instruments WHERE symbol IN ({ph}) ORDER BY change_pct DESC", syms)
    return dict(info=info, stocks=rows)


@router.get("/list")
def listing(market_: str = "KOSPI", sort: str = "mcap", desc: bool = True, page: int = 1, size: int = 50, kind: str = "stock"):
    page, size = max(1, page), max(1, min(size, 200))
    sort = sort if sort in ("mcap", "price", "change_pct", "volume", "value", "name", "per", "pbr") else "mcap"
    markets = {"KR": ("KOSPI", "KOSDAQ"), "US": ("NASDAQ", "NYSE", "AMEX")}.get(market_, (market_,))
    ph = ",".join("?" * len(markets))
    where = f"market IN ({ph})" + (" AND kind=?" if market_ not in ("CRYPTO", "US", "NASDAQ", "NYSE", "AMEX") else "")
    params = list(markets) + ([kind] if "kind=?" in where else [])
    total = db.val(f"SELECT COUNT(*) FROM instruments WHERE {where}", params)
    rows = db.q(f"SELECT {COLS},per,pbr,div_yield,sector FROM instruments WHERE {where} "
                f"ORDER BY {sort} IS NULL, {sort} {'DESC' if desc else 'ASC'} LIMIT ? OFFSET ?", (*params, size, (page - 1) * size))
    return dict(total=total, rows=rows)
