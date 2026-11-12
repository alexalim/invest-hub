"""매매신호와 지표분석. 신호마다 해당 종목의 과거 발생 시점 이후 수익률을 함께 계산한다."""
import json
import logging

import numpy as np

from .. import db
from . import backtest, indicators as ind, store

log = logging.getLogger("signals")


def I(name, *p, out=None, shift=0, mul=None):
    d = {"ind": name, "p": list(p)}
    if out:
        d["out"] = out
    if shift:
        d["shift"] = shift
    if mul:
        d["mul"] = mul
    return d


def C(left, op, right):
    return {"left": left, "op": op, "right": right if isinstance(right, dict) else {"value": right}}


STRATEGIES = {
    "golden_cross": dict(name="골든크로스 (5·20일)", side="buy", desc="5일선이 20일선을 위로 돌파",
                         conds=[C(I("sma", 5), "cross_up", I("sma", 20))]),
    "mid_golden": dict(name="중기 골든크로스 (20·60일)", side="buy", desc="20일선이 60일선을 위로 돌파",
                       conds=[C(I("sma", 20), "cross_up", I("sma", 60))]),
    "rsi_rebound": dict(name="RSI 과매도 반등", side="buy", desc="RSI(14)가 30을 위로 회복",
                        conds=[C(I("rsi", 14), "cross_up", 30)]),
    "bb_rebound": dict(name="볼린저 하단 반등", side="buy", desc="종가가 볼린저 하단선을 위로 회복",
                       conds=[C(I("close"), "cross_up", I("bb", 20, 2, out="lower"))]),
    "macd_cross": dict(name="MACD 골든크로스", side="buy", desc="0선 아래에서 MACD가 시그널을 상향 돌파",
                       conds=[C(I("macd", 12, 26, 9, out="macd"), "cross_up", I("macd", 12, 26, 9, out="signal")),
                              C(I("macd", 12, 26, 9, out="macd"), "<", 0)]),
    "breakout20": dict(name="20일 신고가 돌파 + 거래량", side="buy", desc="전일까지의 20일 고가를 돌파하고 거래량이 평균의 1.5배 이상",
                       conds=[C(I("close"), ">", I("highest", 20, shift=1)), C(I("close", shift=1), "<=", I("highest", 20, shift=2)),
                              C(I("volume"), ">", I("vol_sma", 20, mul=1.5))]),
    "high52": dict(name="52주 신고가", side="buy", desc="종가가 직전 250일 고가를 처음 넘어섬",
                   conds=[C(I("close"), ">", I("highest", 250, shift=1)), C(I("close", shift=1), "<=", I("highest", 250, shift=2))]),
    "volume_spike": dict(name="거래량 급증 양봉", side="buy", desc="거래량이 20일 평균의 3배 이상이고 3% 넘게 상승",
                         conds=[C(I("volume"), ">", I("vol_sma", 20, mul=3)), C(I("change", 1), ">", 3)]),
    "stoch_cross": dict(name="스토캐스틱 과매도 교차", side="buy", desc="%K가 25 아래에서 %D를 상향 돌파",
                        conds=[C(I("stoch", 14, 3, 3, out="k"), "cross_up", I("stoch", 14, 3, 3, out="d")),
                               C(I("stoch", 14, 3, 3, out="k"), "<", 25)]),
    "pullback": dict(name="상승 추세 눌림목", side="buy", desc="60일선 위에서 20일선까지 내려왔다가 종가로 지지",
                     conds=[C(I("close"), ">", I("sma", 60)), C(I("low"), "<=", I("sma", 20)), C(I("close"), ">", I("sma", 20)),
                            C(I("sma", 20), ">", I("sma", 60))]),
    "dead_cross": dict(name="데드크로스 (5·20일)", side="sell", desc="5일선이 20일선을 아래로 이탈",
                       conds=[C(I("sma", 5), "cross_down", I("sma", 20))]),
    "rsi_overbought": dict(name="RSI 과매수 이탈", side="sell", desc="RSI(14)가 70 아래로 내려옴",
                           conds=[C(I("rsi", 14), "cross_down", 70)]),
    "bb_upper_fall": dict(name="볼린저 상단 이탈", side="sell", desc="종가가 볼린저 상단선 아래로 내려옴",
                          conds=[C(I("close"), "cross_down", I("bb", 20, 2, out="upper"))]),
    "macd_dead": dict(name="MACD 데드크로스", side="sell", desc="0선 위에서 MACD가 시그널을 하향 이탈",
                      conds=[C(I("macd", 12, 26, 9, out="macd"), "cross_down", I("macd", 12, 26, 9, out="signal")),
                             C(I("macd", 12, 26, 9, out="macd"), ">", 0)]),
    "breakdown20": dict(name="20일 신저가 이탈", side="sell", desc="전일까지의 20일 저가를 아래로 이탈",
                        conds=[C(I("close"), "<", I("lowest", 20, shift=1)), C(I("close", shift=1), ">=", I("lowest", 20, shift=2))]),
}


def catalog() -> list[dict]:
    return [dict(key=k, name=v["name"], side=v["side"], desc=v["desc"],
                 conds=[ind.describe_cond(c) for c in v["conds"]], spec=v["conds"]) for k, v in STRATEGIES.items()]


def symbol_signals(d: dict, lookback: int = 250) -> list[dict]:
    """한 종목의 최근 신호 목록 (차트 표시용) + 전략별 과거 성과."""
    out = []
    n = len(d["c"])
    for key, st in STRATEGIES.items():
        try:
            mask = ind.evaluate_all(d, st["conds"])
        except Exception:
            continue
        idx = np.flatnonzero(mask)
        if len(idx) == 0:
            continue
        stats = backtest.forward_stats(d, mask, side=st["side"])
        recent = [dict(ts=int(d["ts"][i]), price=float(d["c"][i])) for i in idx if i >= n - lookback]
        out.append(dict(strategy=key, name=st["name"], side=st["side"], desc=st["desc"], stats=stats, points=recent,
                        active=bool(mask[-1])))
    return out


def scan(symbols: list[str], recent_bars: int = 1) -> dict:
    """전 종목 신호 스캔. 마지막 봉에서 발생한 신호를 signals 테이블에 기록한다."""
    rows, sims = [], 0
    agg: dict[str, list] = {k: [] for k in STRATEGIES}
    for s in symbols:
        d = store.get(s)
        if d is None or len(d["c"]) < 80:
            continue
        for key, st in STRATEGIES.items():
            try:
                mask = ind.evaluate_all(d, st["conds"])
            except Exception:
                continue
            hits = int(mask.sum())
            sims += hits
            if hits == 0:
                continue
            c = d["c"]
            ii = np.flatnonzero(mask)
            ii = ii[ii + 10 < len(c)]
            if len(ii):
                agg[key].append(c[ii + 10] / c[ii] - 1)
            if mask[-recent_bars:].any():
                i = int(np.flatnonzero(mask)[-1])
                stats = backtest.forward_stats(d, mask, side=st["side"])
                rows.append((s, key, int(d["ts"][i]), float(c[i]), st["side"], json.dumps(stats), db.now()))
    if rows:
        db.many("INSERT INTO signals(symbol,strategy,date,price,side,stats,created_at) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(symbol,strategy,date) DO UPDATE SET price=excluded.price,stats=excluded.stats", rows)
    summary = {}
    for key, parts in agg.items():
        if not parts:
            continue
        r = np.concatenate(parts)
        good = (r > 0) if STRATEGIES[key]["side"] == "buy" else (r < 0)
        summary[key] = dict(n=int(len(r)), avg10=round(float(r.mean()) * 100, 2), win10=round(float(good.mean()) * 100, 1))
    db.set_setting("signal_summary", dict(strategies=summary, simulations=sims, symbols=len(symbols), at=db.now()))
    return dict(signals=len(rows), simulations=sims)


def _judge(v, buy_below=None, sell_above=None):
    if v is None or np.isnan(v):
        return "중립"
    if buy_below is not None and v < buy_below:
        return "매수"
    if sell_above is not None and v > sell_above:
        return "매도"
    return "중립"


def technical_summary(d: dict) -> dict:
    """지표분석: 오실레이터·이동평균별 판정과 종합 의견, 피봇 지지·저항."""
    c, h, l, v = d["c"], d["h"], d["l"], d["v"]
    last = float(c[-1])

    def lastv(a):
        x = a[-1]
        return None if np.isnan(x) else float(x)

    osc = []
    r = lastv(ind.rsi(c, 14))
    osc.append(dict(name="RSI(14)", value=r, signal=_judge(r, 30, 70), rule="30 미만 매수 · 70 초과 매도"))
    k, dd = ind.stoch(h, l, c)
    kv = lastv(k)
    osc.append(dict(name="스토캐스틱 %K(14,3,3)", value=kv, signal=_judge(kv, 20, 80), rule="20 미만 매수 · 80 초과 매도"))
    cv = lastv(ind.cci(h, l, c, 20))
    osc.append(dict(name="CCI(20)", value=cv, signal=_judge(cv, -100, 100), rule="-100 미만 매수 · 100 초과 매도"))
    wv = lastv(ind.williams_r(h, l, c, 14))
    osc.append(dict(name="윌리엄스 %R(14)", value=wv, signal=_judge(wv, -80, -20), rule="-80 미만 매수 · -20 초과 매도"))
    mv = lastv(ind.mfi(h, l, c, v, 14))
    osc.append(dict(name="MFI(14)", value=mv, signal=_judge(mv, 20, 80), rule="20 미만 매수 · 80 초과 매도"))
    m, sgn, hist = ind.macd(c)
    hv = lastv(hist)
    osc.append(dict(name="MACD(12,26,9)", value=lastv(m), signal="중립" if hv is None else ("매수" if hv > 0 else "매도"),
                    rule="MACD가 시그널 위면 매수"))
    a, pdi, ndi = ind.adx(h, l, c)
    av, pv, nv = lastv(a), lastv(pdi), lastv(ndi)
    adx_sig = "중립"
    if av is not None and av > 25 and pv is not None and nv is not None:
        adx_sig = "매수" if pv > nv else "매도"
    osc.append(dict(name="ADX(14)", value=av, signal=adx_sig, rule="25 초과 시 +DI·-DI 방향"))
    up, mid, lo = ind.bollinger(c)
    uv, lv = lastv(up), lastv(lo)
    bb_sig = "중립"
    if uv is not None and lv is not None:
        bb_sig = "매수" if last < lv else "매도" if last > uv else "중립"
    pos = None if uv is None or uv == lv else round((last - lv) / (uv - lv) * 100, 1)
    osc.append(dict(name="볼린저밴드 위치(%)", value=pos, signal=bb_sig, rule="하단 아래 매수 · 상단 위 매도"))

    mas = []
    for n in (5, 10, 20, 60, 120, 200):
        for kind, fn in (("SMA", ind.sma), ("EMA", ind.ema)):
            x = lastv(fn(c, n))
            mas.append(dict(name=f"{kind}({n})", value=x, signal="중립" if x is None else ("매수" if last > x else "매도")))

    def tally(items):
        b = sum(1 for i in items if i["signal"] == "매수")
        s = sum(1 for i in items if i["signal"] == "매도")
        return dict(buy=b, sell=s, neutral=len(items) - b - s)

    def opinion(t):
        tot = t["buy"] + t["sell"] + t["neutral"]
        sc = (t["buy"] - t["sell"]) / tot if tot else 0
        return "강력 매수" if sc > 0.5 else "매수" if sc > 0.15 else "강력 매도" if sc < -0.5 else "매도" if sc < -0.15 else "중립"

    to, tm = tally(osc), tally(mas)
    tall = {k: to[k] + tm[k] for k in to}
    ph, pl, pc = float(h[-2]) if len(h) > 1 else last, float(l[-2]) if len(l) > 1 else last, float(c[-2]) if len(c) > 1 else last
    pp = (ph + pl + pc) / 3
    pivots = dict(r3=ph + 2 * (pp - pl), r2=pp + (ph - pl), r1=2 * pp - pl, pp=pp, s1=2 * pp - ph, s2=pp - (ph - pl),
                  s3=pl - 2 * (ph - pp))
    atr_v = lastv(ind.atr(h, l, c, 14))
    return dict(price=last, oscillators=osc, moving_averages=mas,
                summary=dict(oscillators=dict(**to, opinion=opinion(to)), moving_averages=dict(**tm, opinion=opinion(tm)),
                             overall=dict(**tall, opinion=opinion(tall))),
                pivots={k: round(v, 4) for k, v in pivots.items()}, atr=atr_v,
                volatility=round(float(np.std(np.diff(np.log(c[-61:]))) * np.sqrt(252) * 100), 1) if len(c) > 61 else None)
