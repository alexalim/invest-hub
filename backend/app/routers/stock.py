"""종목 상세: 시세, 차트, 보조지표, 재무, 뉴스·공시, 호가, 지표분석, 매매신호, AI예측, 유사차트."""
import asyncio
import json
from datetime import datetime, timezone

import numpy as np

from fastapi import APIRouter, Body, Depends, HTTPException

from .. import auth, db
from ..analysis import indicators as ind, signals, similar, store
from ..providers import market, naver, upbit

router = APIRouter(prefix="/api/stock")
U = Depends(auth.current_user)


def _inst(symbol: str) -> dict:
    row = market.instrument(symbol)
    if not row:
        raise HTTPException(404, "종목을 찾을 수 없습니다")
    return row


@router.get("/{symbol}")
async def detail(symbol: str, user=U):
    row = _inst(symbol)
    p, code = market.parse(symbol)
    qd = await market.quote(symbol) or {}
    info: dict = {}
    try:
        if p == "KR":
            info = await naver.integration_kr(code)
        elif p == "US" and market.reuters(symbol):
            info = await naver.integration_us(market.reuters(symbol))
    except Exception:
        info = {}
    for k in ("per", "pbr", "eps", "bps", "div_yield", "high52", "low52"):
        if info.get(k) is not None:
            row[k] = info[k]
    if p == "KR" and info.get("per") is not None:
        db.ex("UPDATE instruments SET per=?,pbr=?,eps=?,bps=?,div_yield=?,fund_updated_at=? WHERE symbol=?",
              (info.get("per"), info.get("pbr"), info.get("eps"), info.get("bps"), info.get("div_yield"), db.now(), symbol))
    row.pop("extra", None)
    memo = db.val("SELECT body FROM memos WHERE user_id=? AND symbol=?", (user["id"], symbol))
    watched = db.val("SELECT 1 FROM watch_items w JOIN watch_groups g ON g.id=w.group_id WHERE g.user_id=? AND w.symbol=?",
                     (user["id"], symbol))
    return dict(instrument=row, quote=qd, info=info, memo=memo, watched=bool(watched),
                tradable=p in ("KR", "US", "CR"), has_orderbook=p in ("KR", "CR"))


@router.get("/{symbol}/candles")
async def candles(symbol: str, tf: str = "day", count: int = 500, user=U):
    _inst(symbol)
    rows = await market.candles(symbol, tf, min(count, 2000))
    return dict(symbol=symbol, tf=tf, candles=[list(r) for r in rows])


@router.post("/{symbol}/indicators")
async def chart_indicators(symbol: str, p: dict = Body(...), user=U):
    """차트 보조지표. 화면에 보이는 봉과 같은 주기로 계산한다."""
    import numpy as np
    rows = await market.candles(symbol, p.get("tf", "day"), min(int(p.get("count", 500)), 2000))
    if not rows:
        return []
    a = np.array(rows, dtype=np.float64)
    d = dict(ts=a[:, 0].astype(np.int64), o=a[:, 1], h=a[:, 2], l=a[:, 3], c=a[:, 4], v=a[:, 5])
    try:
        return ind.chart_series(d, p.get("specs") or [])
    except (ValueError, KeyError, TypeError, IndexError) as e:
        raise HTTPException(400, f"보조지표 설정 오류: {e}")


@router.get("/{symbol}/finance")
async def finance(symbol: str, period: str = "annual", user=U):
    p, code = market.parse(symbol)
    period = "quarter" if period == "quarter" else "annual"
    if p == "KR":
        return await naver.finance_kr(code, period)
    if p == "US" and market.reuters(symbol):
        return await naver.finance_us(market.reuters(symbol), period)
    return dict(columns=[], rows=[])


@router.get("/{symbol}/news")
async def news(symbol: str, page: int = 1, user=U):
    p, code = market.parse(symbol)
    out = dict(news=[], disclosures=[], research=[])
    try:
        if p == "KR":
            out["news"], out["disclosures"], out["research"] = await asyncio.gather(
                naver.news_kr(code, page), naver.disclosure_kr(code, page), naver.research_kr(code, page))
        elif p == "US" and market.reuters(symbol):
            out["news"] = await naver.news_us(market.reuters(symbol), page)
    except Exception:
        pass
    return out


@router.get("/{symbol}/orderbook")
async def orderbook(symbol: str, user=U):
    p, code = market.parse(symbol)
    if p == "KR":
        return await naver.asking_kr(code)
    if p == "CR":
        return await upbit.orderbook(code)
    return dict(asks=[], bids=[])


@router.get("/{symbol}/trend")
async def trend(symbol: str, user=U):
    p, code = market.parse(symbol)
    return await naver.trend_kr(code) if p == "KR" else []


async def _daily(symbol: str) -> dict:
    await market.daily(symbol, max_age=3 * 3600)
    d = store.get(symbol)
    if d is None or len(d["c"]) < 30:
        raise HTTPException(404, "일봉 데이터가 부족합니다")
    return d


@router.get("/{symbol}/analysis")
async def analysis(symbol: str, user=U):
    """지표분석."""
    d = await _daily(symbol)
    return signals.technical_summary(d)


@router.get("/{symbol}/signals")
async def symbol_signals(symbol: str, user=U):
    d = await _daily(symbol)
    return signals.symbol_signals(d)


@router.get("/{symbol}/predict")
async def predict(symbol: str, window: int = 60, user=U):
    await _daily(symbol)
    window = window if window in (30, 60, 120) else 60
    res = await asyncio.to_thread(similar.predict, symbol, window)
    if res is None:
        raise HTTPException(404, "예측에 쓸 데이터가 부족합니다")
    return res


@router.get("/{symbol}/similar")
async def similar_now(symbol: str, window: int = 60, user=U):
    await _daily(symbol)
    window = window if window in (30, 60, 120) else 60
    rows = await asyncio.to_thread(similar.similar_now, symbol, window)
    ph = ",".join("?" * len(rows)) or "''"
    px = {r["symbol"]: r for r in db.q(f"SELECT symbol,price,change_pct,market FROM instruments WHERE symbol IN ({ph})",
                                       [r["symbol"] for r in rows])}
    return [dict(r, **{k: v for k, v in (px.get(r["symbol"]) or {}).items() if k != "symbol"}) for r in rows]


FEES = {"KR": (0.00015, 0.0018), "US": (0.001, 0.0), "CR": (0.0005, 0.0)}  # (매수·매도 수수료율, 매도세)


def _bench(symbol: str) -> str | None:
    p = symbol.split(":")[0]
    if p == "KR":
        return "IX:KOSDAQ" if db.val("SELECT market FROM instruments WHERE symbol=?", (symbol,)) == "KOSDAQ" else "IX:KOSPI"
    return {"US": "IX:SPX", "CR": "CR:KRW-BTC"}.get(p)


def _at(d: dict, day: str, after: bool = True) -> int | None:
    """그 날짜의 봉 위치. 휴장일이면 다음(또는 이전) 거래일."""
    from datetime import datetime as _dt
    t = int(_dt.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    i = int(np.searchsorted(d["ts"], t))
    if not after and (i >= len(d["ts"]) or d["ts"][i] != t):
        i -= 1
    return i if 0 <= i < len(d["ts"]) else None


@router.get("/{symbol}/whatif")
async def whatif(symbol: str, buy: str, sell: str = "", amount: float = 10_000_000, user=U):
    """과거 어느 날 종가에 사서 어느 날 종가에 팔았다면 (배당 제외, 액면분할은 가격에 반영됨)."""
    _inst(symbol)
    await market.daily(symbol, max_age=3 * 3600)
    d = store.get(symbol)
    if d is None or len(d["c"]) < 2:
        raise HTTPException(404, "일봉 데이터가 없습니다")
    try:
        i = _at(d, buy, after=True)
        j = _at(d, sell, after=False) if sell else len(d["c"]) - 1
    except ValueError:
        raise HTTPException(400, "날짜 형식은 YYYY-MM-DD입니다")
    if i is None:
        raise HTTPException(400, f"{barDate(int(d['ts'][0]))} 이후 날짜를 골라 주세요 (자료 시작일)")
    if j is None or j <= i:
        raise HTTPException(400, "파는 날은 사는 날보다 뒤여야 합니다")
    p = symbol.split(":")[0]
    fee, tax = FEES.get(p, (0.0, 0.0))
    if p == "KR" and db.val("SELECT kind FROM instruments WHERE symbol=?", (symbol,)) != "stock":
        tax = 0.0
    c, h, l, ts = d["c"], d["h"], d["l"], d["ts"]
    bp, sp = float(c[i]), float(c[j])
    qty = amount / (bp * (1 + fee))
    if p != "CR":
        qty = float(int(qty))
    if qty <= 0:
        raise HTTPException(400, "투자 금액이 1주 가격보다 작습니다")
    cost = qty * bp * (1 + fee)
    proceeds = qty * sp * (1 - fee - tax)
    seg = c[i:j + 1]
    peak = np.maximum.accumulate(seg)
    dd = (seg / peak - 1).min()
    lo_k, hi_k = int(np.argmin(l[i:j + 1])), int(np.argmax(h[i:j + 1]))
    # 그 기간 안에서 가장 좋았을 매수·매도 조합 (종가 기준)
    run_min = np.minimum.accumulate(seg)
    gains = seg / run_min - 1
    bj = int(np.argmax(gains))
    bi = int(np.argmin(seg[:bj + 1])) if bj > 0 else 0
    days = (int(ts[j]) - int(ts[i])) / 86400
    ret = proceeds / cost - 1
    out = dict(symbol=symbol, buy_ts=int(ts[i]), sell_ts=int(ts[j]), buy_price=bp, sell_price=sp, qty=qty, cost=cost,
               proceeds=proceeds, pnl=proceeds - cost, ret_pct=ret * 100, price_ret_pct=(sp / bp - 1) * 100,
               cagr_pct=((1 + ret) ** (365 / days) - 1) * 100 if days >= 30 and ret > -1 else None, days=round(days),
               fees=cost - qty * bp + qty * sp * (fee + tax), mdd_pct=float(dd) * 100,
               low=dict(ts=int(ts[i + lo_k]), price=float(l[i + lo_k])), high=dict(ts=int(ts[i + hi_k]), price=float(h[i + hi_k])),
               best=dict(buy_ts=int(ts[i + bi]), sell_ts=int(ts[i + bj]), ret_pct=float(gains[bj]) * 100),
               currency=market.currency(symbol), sell_is_today=not sell)
    bench = _bench(symbol)
    if bench and bench != symbol:
        await market.daily(bench, max_age=6 * 3600)
        bd = store.get(bench)
        if bd is not None:
            bi2, bj2 = _at(bd, barDate(int(ts[i]))), _at(bd, barDate(int(ts[j])), after=False)
            if bi2 is not None and bj2 is not None and bj2 > bi2:
                out["bench"] = dict(symbol=bench, name=market.name_of(bench), ret_pct=(float(bd["c"][bj2]) / float(bd["c"][bi2]) - 1) * 100)
    return out


def barDate(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


@router.put("/{symbol}/memo")
def save_memo(symbol: str, p: dict = Body(...), user=U):
    body = (p.get("body") or "").strip()
    if body:
        db.ex("INSERT OR REPLACE INTO memos(user_id,symbol,body,updated_at) VALUES(?,?,?,?)", (user["id"], symbol, body, db.now()))
    else:
        db.ex("DELETE FROM memos WHERE user_id=? AND symbol=?", (user["id"], symbol))
    return dict(ok=True)


@router.get("/{symbol}/drawings")
def get_drawings(symbol: str, user=U):
    v = db.val("SELECT data FROM drawings WHERE user_id=? AND symbol=?", (user["id"], symbol))
    return json.loads(v) if v else []


@router.put("/{symbol}/drawings")
def save_drawings(symbol: str, p: list = Body(...), user=U):
    db.ex("INSERT OR REPLACE INTO drawings(user_id,symbol,data) VALUES(?,?,?)", (user["id"], symbol, json.dumps(p[:200])))
    return dict(ok=True)
