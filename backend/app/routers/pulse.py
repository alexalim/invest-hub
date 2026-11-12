"""시장 흐름: 투자자별 수급, 위험 지표, 공포·탐욕, 상대강도, 아침 브리핑."""
from fastapi import APIRouter, Depends, HTTPException

from .. import auth, db
from ..analysis import events, kisdata, pulse
from ..broker import kis
from ..providers import market, naver

router = APIRouter(prefix="/api/pulse", dependencies=[Depends(auth.current_user)])
COLS = "symbol,market,name,price,change,change_pct,mcap,sector"


@router.get("/flow")
def flow(market_: str = "KOSPI", days: int = 60):
    return pulse.flow_view(market_, days)


@router.get("/flow/stocks")
def flow_stocks(who: str = "foreign", span: int = 1, limit: int = 20):
    return pulse.stock_flow_view(who, span, limit)


@router.get("/risk")
async def risk():
    try:
        return await pulse.risk_view()
    except Exception:
        raise HTTPException(503, "해외 시세를 받지 못했습니다. 잠시 뒤 다시 시도해 주세요")


@router.get("/feargreed")
def feargreed():
    return pulse.fear_greed() or dict(score=None, components=[], history=[])


@router.get("/rs")
def rs(market_: str = "KR", min_mcap: float = 1000, limit: int = 50):
    """min_mcap 단위: 억원(국내) / 억달러(미국)."""
    limit = max(1, min(int(limit), 200))
    unit = 1e8
    return pulse.rs_rank("US" if market_ == "US" else "KR", max(0.0, float(min_mcap)) * unit, limit)


async def _kis(coro):
    try:
        return await coro
    except kis.KisError as e:
        raise HTTPException(503, f"증권사 시세 조회 실패: {e}")


@router.get("/program")
async def program(market_: str = "KOSPI"):
    return await _kis(kisdata.program_view(market_))


@router.get("/sectors")
def sectors(market_: str = "KOSPI"):
    return kisdata.sector_view(market_)


@router.get("/short")
async def short(market_: str = "KOSPI", period: str = "0"):
    return await _kis(kisdata.short_view(market_, period))


@router.get("/prelim")
async def prelim(market_: str = "KOSPI", who: str = "foreign", side: str = "buy"):
    return await _kis(kisdata.prelim_view(market_, who, side))


@router.get("/disclosures")
def disclosures(cat: str = "", q: str = "", page: int = 1, mine: bool = False, user: dict = Depends(auth.current_user)):
    syms = None
    if mine:
        syms = [r["symbol"] for r in db.q("SELECT DISTINCT wi.symbol FROM watch_items wi JOIN watch_groups g ON g.id=wi.group_id WHERE g.user_id=?", (user["id"],))]
    return events.disclosure_view(cat, q[:40], page, 50, syms)


@router.get("/earnings")
async def earnings():
    return await events.earnings_view()


@router.get("/basis")
async def basis():
    return await events.basis_view()


def _macro(symbols: list[str]) -> list[dict]:
    ph = ",".join("?" * len(symbols))
    rows = {r["symbol"]: r for r in db.q(f"SELECT symbol,name,price,change,change_pct,kind,updated_at FROM instruments WHERE symbol IN ({ph})", symbols)}
    return [rows[s] for s in symbols if s in rows and rows[s]["price"] is not None]


def _line(rows: list[dict], digits: int = 2) -> str:
    return ", ".join(f"{r['name']} {r['change_pct']:+.{digits}f}%" for r in rows if r.get("change_pct") is not None)


@router.get("/briefing")
async def briefing():
    """저장된 시세로 만드는 아침 요약. 사람이 쓴 해설이 아니라 숫자를 규칙대로 문장으로 옮긴 것이다."""
    us_idx = _macro(["IX:DOW", "IX:NASDAQ", "IX:SPX", "IX:SOX", "IX:RUT", "IX:VIX"])
    futures = _macro(["IX:ESF", "IX:NQF", "IX:YMF", "IX:EWY", "IX:K200F"])
    rates = _macro(["RT:US10Y", "RT:KR10Y", "FX:USDKRW", "FX:DXY", "CM:WTI", "CM:GOLD"])
    asia = _macro(["IX:KOSPI", "IX:KOSDAQ", "IX:NIKKEI", "IX:SHANGHAI", "IX:HSI", "IX:TWII"])
    us = "market IN ('NASDAQ','NYSE') AND kind='stock' AND price IS NOT NULL AND change_pct IS NOT NULL"
    big = db.q(f"SELECT {COLS} FROM instruments WHERE {us} ORDER BY mcap DESC LIMIT 150")
    up = sorted(big, key=lambda r: -r["change_pct"])[:8]
    down = sorted(big, key=lambda r: r["change_pct"])[:8]
    sectors = db.q(f"SELECT sector, SUM(change_pct*mcap)/SUM(mcap) AS change_pct, COUNT(*) n, SUM(mcap) mcap FROM instruments "
                   f"WHERE {us} AND sector IS NOT NULL AND mcap IS NOT NULL GROUP BY sector HAVING n>=5 ORDER BY mcap DESC LIMIT 40")
    sectors.sort(key=lambda r: -r["change_pct"])
    flows = {}
    for mk in pulse.MARKETS:
        r = db.one("SELECT date,individual,foreigner,institution FROM flow_days WHERE market=? ORDER BY date DESC LIMIT 1", (mk,))
        if r:
            flows[mk] = r
    try:
        risk = await pulse.risk_view()
        risk = dict(score=risk["score"], level=risk["level"], week=risk["week"], asof=risk["asof"])
    except Exception:
        risk = None
    fng = pulse.fear_greed()
    fng = fng and dict(score=fng["score"], label=fng["label"], week=fng["week"], asof=fng["asof"])
    lines = []
    if us_idx:
        lines.append("미국 증시: " + _line([r for r in us_idx if r["symbol"] != "IX:VIX"]))
        vix = next((r for r in us_idx if r["symbol"] == "IX:VIX"), None)
        if vix:
            lines.append(f"변동성: VIX {vix['price']:.2f} ({vix['change_pct']:+.1f}%)")
    if sectors:
        lines.append("강한 업종: " + _line([dict(name=s["sector"], change_pct=s["change_pct"]) for s in sectors[:3]], 1)
                     + " / 약한 업종: " + _line([dict(name=s["sector"], change_pct=s["change_pct"]) for s in sectors[-3:][::-1]], 1))
    if rates:
        lines.append("금리·환율·원자재: " + ", ".join(f"{r['name']} {r['price']:,.2f} ({r['change_pct']:+.2f}%)" for r in rates))
    if futures:
        lines.append("지금 선물·한국 ETF: " + _line(futures))
    for mk, r in flows.items():
        nm = "코스피" if mk == "KOSPI" else "코스닥"
        lines.append(f"{nm} 수급 ({r['date'][4:6]}/{r['date'][6:]}): 외국인 {r['foreigner']:+,.0f}억, 기관 {r['institution']:+,.0f}억, 개인 {r['individual']:+,.0f}억")
    if risk:
        lines.append(f"미국 위험 점수 {risk['score']} ({risk['level']})" + (f", 1주 전보다 {risk['week']:+d}" if risk["week"] is not None else ""))
    if fng and fng["score"] is not None:
        lines.append(f"코스피 공포·탐욕 {fng['score']} ({fng['label']})")
    try:
        news = (await naver.main_news(size=10))[:10]
    except Exception:
        news = []
    return dict(at=db.now(), lines=lines, us_index=us_idx, futures=futures, rates=rates, asia=asia, up=up, down=down,
                sectors=sectors[:6], sectors_weak=sectors[-6:][::-1], flows=flows, risk=risk, feargreed=fng, news=news)
