"""발굴분석: 종목필터, 매매신호, AI예측 순위, 유사차트 검색, 백테스팅, 저장한 조건."""
import asyncio
import json

from fastapi import APIRouter, Body, Depends, HTTPException

from .. import auth, db
from ..analysis import backtest, indicators as ind, screener, signals, similar, store
from ..providers import market

router = APIRouter(prefix="/api/discover")
U = Depends(auth.current_user)


@router.get("/intraday/meta")
def intraday_meta(user=U):
    from .. import intraday
    from ..analysis import intraday_bt
    return dict(indicators=[dict(key=k, **v) for k, v in {**ind.CATALOG, **intraday_bt.INTRADAY}.items()],
                presets=[dict(key=k, name=v["name"], desc=v["desc"], spec=v["spec"]) for k, v in intraday_bt.PRESETS.items()],
                status=intraday.status(), cost=round(intraday_bt.COST * 100, 2))


@router.get("/intraday/validation")
def intraday_validation(user=U):
    return db.get_setting("validation_intraday") or {}


@router.post("/intraday/backtest")
async def intraday_backtest(p: dict = Body(...), user=U):
    from .. import intraday
    from ..analysis import intraday_bt
    symbol = p.get("symbol") or ""
    if not symbol.startswith("KR:") or not market.instrument(symbol):
        raise HTTPException(400, "장중 백테스트는 국내 종목만 됩니다")
    spec = p.get("spec") or {}
    if not spec.get("entry"):
        raise HTTPException(400, "매수 조건을 하나 이상 넣어 주세요")
    try:
        await intraday.ensure(symbol)
    except Exception:
        pass
    d = await asyncio.to_thread(intraday.load, symbol)
    if d is None or len(d["days"]) < 5:
        raise HTTPException(404, "이 종목의 5분봉 자료가 부족합니다")
    try:
        res = await asyncio.to_thread(intraday_bt.run, d, spec)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, f"조건식 오류: {e}")
    res["candles"] = [[int(t), float(o), float(h), float(l), float(c), float(v)] for t, o, h, l, c, v in zip(d["ts"], d["o"], d["h"], d["l"], d["c"], d["v"])]
    res["days"] = [d["days"][0], d["days"][-1], len(d["days"])]
    res["name"] = market.name_of(symbol)
    return res


@router.post("/intraday/backtest/multi")
async def intraday_backtest_multi(p: dict = Body(...), user=U):
    """같은 장중 전략을 저장된 모든 종목(또는 지정 종목)에 돌려 합산한다."""
    from .. import intraday
    from ..analysis import intraday_bt
    spec = p.get("spec") or {}
    if not spec.get("entry"):
        raise HTTPException(400, "매수 조건을 하나 이상 넣어 주세요")
    syms = p.get("symbols") or [r[0] for r in intraday.conn().execute("SELECT symbol FROM bars GROUP BY symbol HAVING COUNT(*)>=20").fetchall()]
    nm = market.names(syms)

    def work():
        rows, allt = [], []
        for s in syms[:400]:
            d = intraday.load(s)
            if d is None:
                continue
            try:
                r = intraday_bt.run(d, spec)
            except Exception:
                continue
            if r["trades"]:
                allt += r["trades"]
                rows.append(dict(symbol=s, name=nm.get(s, s), **r["stats"]))
        return rows, intraday_bt.stats(allt)

    rows, total = await asyncio.to_thread(work)
    rows.sort(key=lambda r: -(r.get("avg") or -99))
    return dict(rows=rows, total=total)


@router.get("/validation")
def validation(user=U):
    return db.get_setting("validation") or {}


@router.get("/meta")
def meta(user=U):
    return dict(indicators=[dict(key=k, **v) for k, v in ind.CATALOG.items()], ops=ind.OP_LABEL,
                fields=screener.fields(), presets=screener.PRESETS, strategies=signals.catalog())


@router.post("/screener")
async def run_screener(spec: dict = Body(...), user=U):
    res = await asyncio.to_thread(screener.run, spec)
    return res


@router.get("/signals")
def list_signals(side: str = "", strategy: str = "", market_: str = "", days: int = 3, limit: int = 300, user=U):
    last = db.val("SELECT MAX(date) FROM signals")
    if not last:
        return dict(rows=[], summary=db.get_setting("signal_summary"), strategies=signals.catalog())
    where, params = ["s.date>=?"], [last - days * 86400]
    if side:
        where.append("s.side=?")
        params.append(side)
    if strategy:
        where.append("s.strategy=?")
        params.append(strategy)
    if market_:
        mk = {"KR": ("KOSPI", "KOSDAQ"), "US": ("NASDAQ", "NYSE", "AMEX"), "CR": ("CRYPTO",)}.get(market_, (market_,))
        where.append(f"i.market IN ({','.join('?' * len(mk))})")
        params += list(mk)
    rows = db.q("SELECT s.symbol,s.strategy,s.date,s.price sig_price,s.side,s.stats,i.name,i.market,i.price,i.change_pct,i.mcap,"
                f"i.value FROM signals s JOIN instruments i ON i.symbol=s.symbol WHERE {' AND '.join(where)} "
                "ORDER BY s.date DESC, COALESCE(i.mcap,i.value,0) DESC LIMIT ?", (*params, limit))
    names = {k: v["name"] for k, v in signals.STRATEGIES.items()}
    for r in rows:
        r["stats"] = json.loads(r["stats"] or "{}")
        r["strategy_name"] = names.get(r["strategy"], r["strategy"])
    return dict(rows=rows, summary=db.get_setting("signal_summary"), strategies=signals.catalog())


@router.get("/ai")
async def ai_ranking(market_: str = "KR", limit: int = 150, window: int = 60, user=U):
    """AI예측 순위: 시가총액 상위 종목의 예측 점수."""
    markets = {"KR": ("KOSPI", "KOSDAQ"), "KOSPI": ("KOSPI",), "KOSDAQ": ("KOSDAQ",), "US": ("NASDAQ", "NYSE"),
               "CR": ("CRYPTO",)}.get(market_, ("KOSPI", "KOSDAQ"))
    key = f"ai_rank:{market_}:{window}"
    cached = db.get_setting(key)
    if cached and db.now() - cached["at"] < 3 * 3600:
        rows = cached["rows"]
    else:
        syms = market.universe(markets, limit=limit, kinds=("crypto",) if market_ == "CR" else ("stock",))
        rows = await asyncio.to_thread(similar.rank_predictions, syms, window)
        if rows:
            db.set_setting(key, dict(at=db.now(), rows=rows))
    nm = market.names([r["symbol"] for r in rows])
    ph = ",".join("?" * len(rows)) or "''"
    px = {r["symbol"]: r for r in db.q(f"SELECT symbol,price,change_pct,market,mcap FROM instruments WHERE symbol IN ({ph})",
                                       [r["symbol"] for r in rows])}
    out = [dict(r, name=nm.get(r["symbol"]), change_pct=(px.get(r["symbol"]) or {}).get("change_pct"),
                market=(px.get(r["symbol"]) or {}).get("market"), mcap=(px.get(r["symbol"]) or {}).get("mcap")) for r in rows]
    out.sort(key=lambda r: -r["score"])
    return dict(rows=out, index=similar.status())


@router.post("/similar")
async def similar_search(p: dict = Body(...), user=U):
    """직접 그린 모양과 닮은 차트 찾기."""
    try:
        series = [float(x) for x in (p.get("series") or [])][:2000]
        window = max(10, min(int(p.get("window") or 60), 250))
    except (ValueError, TypeError):
        raise HTTPException(400, "그린 모양을 읽지 못했습니다. 다시 그려 주세요")
    rows = await asyncio.to_thread(similar.search_custom, series, window)
    return rows


@router.post("/backtest")
async def run_backtest(p: dict = Body(...), user=U):
    symbol = p.get("symbol")
    if not symbol or not market.instrument(symbol):
        raise HTTPException(400, "종목을 선택해 주세요")
    await market.daily(symbol, max_age=6 * 3600)
    d = store.get(symbol, live=False)
    if d is None or len(d["c"]) < 60:
        raise HTTPException(404, "일봉 데이터가 부족합니다")
    spec = p.get("spec") or {}
    if not spec.get("entry"):
        raise HTTPException(400, "매수 조건을 하나 이상 넣어 주세요")
    try:
        res = await asyncio.to_thread(backtest.run, d, spec)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, f"조건식 오류: {e}")
    res["candles"] = [[int(t), float(o), float(h), float(l), float(c), float(v)]
                      for t, o, h, l, c, v in zip(d["ts"], d["o"], d["h"], d["l"], d["c"], d["v"])]
    res["name"] = market.name_of(symbol)
    return res


@router.post("/backtest/multi")
async def backtest_multi(p: dict = Body(...), user=U):
    """같은 전략을 여러 종목에 돌려 비교한다."""
    spec = p.get("spec") or {}
    symbols = (p.get("symbols") or [])[:60]
    if not spec.get("entry") or not symbols:
        raise HTTPException(400, "종목과 매수 조건이 필요합니다")
    nm = market.names(symbols)

    def work():
        out = []
        for s in symbols:
            d = store.get(s, live=False)
            if d is None or len(d["c"]) < 60:
                continue
            try:
                st = backtest.run(d, spec)["stats"]
            except Exception:
                continue
            out.append(dict(symbol=s, name=nm.get(s, s), **st))
        return out

    rows = await asyncio.to_thread(work)
    rows.sort(key=lambda r: -(r.get("total_return") or -999))
    return rows


@router.get("/saved/{kind}")
def saved_list(kind: str, user=U):
    rows = db.q("SELECT id,name,spec,updated_at FROM saved_specs WHERE user_id=? AND kind=? ORDER BY updated_at DESC", (user["id"], kind))
    for r in rows:
        r["spec"] = json.loads(r["spec"])
    return rows


@router.post("/saved/{kind}")
def saved_put(kind: str, p: dict = Body(...), user=U):
    name = (p.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "이름을 입력해 주세요")
    if p.get("id"):
        db.ex("UPDATE saved_specs SET name=?, spec=?, updated_at=? WHERE id=? AND user_id=?",
              (name, json.dumps(p.get("spec") or {}), db.now(), p["id"], user["id"]))
        return dict(id=p["id"])
    return dict(id=db.ex("INSERT INTO saved_specs(user_id,kind,name,spec,updated_at) VALUES(?,?,?,?,?)",
                         (user["id"], kind, name, json.dumps(p.get("spec") or {}), db.now())))


@router.delete("/saved/{kind}/{sid}")
def saved_delete(kind: str, sid: int, user=U):
    db.ex("DELETE FROM saved_specs WHERE id=? AND user_id=? AND kind=?", (sid, user["id"], kind))
    return dict(ok=True)
