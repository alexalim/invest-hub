"""장중(5분봉) 단타 백테스트와 검증.

규칙
- 신호는 봉이 끝날 때 확정되고 다음 봉 시가에 진입한다.
- 하루 안에 반드시 청산한다: 매도 조건(다음 봉 시가), 손절·익절(봉 안의 고가·저가, 둘 다 닿으면 손절을 먼저 가정),
  또는 그날 마지막 봉(15:15 봉) 종가. 다음 날로 넘기지 않는다.
- 비용: 왕복 0.23% (수수료 0.03% + 매도세 0.18% + 호가 차이 약 0.02%)
"""
import math

import numpy as np

from .. import db, intraday
from . import indicators as ind

COST = 0.0023
# 장중 전용 지표 (indicators.CATALOG에 함께 노출)
INTRADAY = {
    "svwap": dict(label="당일 VWAP", params=[], outs=[]),
    "or_high": dict(label="시가 범위 고가 (처음 n봉)", params=[("봉 수", 6)], outs=[]),
    "or_low": dict(label="시가 범위 저가 (처음 n봉)", params=[("봉 수", 6)], outs=[]),
    "day_open": dict(label="당일 시가", params=[], outs=[]),
    "prev_close": dict(label="전일 종가", params=[], outs=[]),
    "gap": dict(label="시초가 갭(%)", params=[], outs=[]),
    "day_chg": dict(label="당일 등락률(%)", params=[], outs=[]),
    "from_open": dict(label="시가 대비(%)", params=[], outs=[]),
    "bar_no": dict(label="장 시작 후 봉 번호 (5분 단위)", params=[], outs=[]),
    "day_high": dict(label="당일 고가 (직전 봉까지)", params=[], outs=[]),
    "day_low": dict(label="당일 저가 (직전 봉까지)", params=[], outs=[]),
}


def compute(d: dict, name: str, p: list) -> np.ndarray:
    day, bar, first = d["day"], d["bar"], d["first"]
    c, h, l, v = d["c"], d["h"], d["l"], d["v"]
    if name == "svwap":
        tp = (h + l + c) / 3
        pv, vv = np.cumsum(tp * v), np.cumsum(v)
        base = first[day]
        pv0 = np.where(base > 0, pv[base - 1], 0.0)
        vv0 = np.where(base > 0, vv[base - 1], 0.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            out = (pv - pv0) / (vv - vv0)
        return np.where(np.isfinite(out), out, c)
    if name in ("or_high", "or_low"):
        n = int(p[0] if p else 6)
        out = np.full(len(c), np.nan)
        for k, f in enumerate(first):
            e = f + n
            if e <= len(c) and day[min(e - 1, len(c) - 1)] == k:
                val = h[f:e].max() if name == "or_high" else l[f:e].min()
                seg = (day == k) & (bar >= n)
                out[seg] = val
        return out
    if name == "day_open":
        return d["day_open"]
    if name == "prev_close":
        return d["prev_close"]
    if name == "gap":
        return (d["day_open"] / d["prev_close"] - 1) * 100
    if name == "day_chg":
        return (c / d["prev_close"] - 1) * 100
    if name == "from_open":
        return (c / d["day_open"] - 1) * 100
    if name == "bar_no":
        return bar.astype(float)
    if name in ("day_high", "day_low"):
        out = np.full(len(c), np.nan)
        for k, f in enumerate(first):
            e = d["last"][k] + 1
            seg = (h if name == "day_high" else l)[f:e]
            acc = np.maximum.accumulate(seg) if name == "day_high" else np.minimum.accumulate(seg)
            out[f + 1:e] = acc[:-1]  # 직전 봉까지 (현재 봉 미포함)
        return out
    raise ValueError(f"알 수 없는 장중 지표: {name}")


def run(d: dict, spec: dict) -> dict:
    """한 종목 장중 백테스트."""
    n = len(d["c"])
    o, h, l, c, ts = d["o"], d["h"], d["l"], d["c"], d["ts"]
    entry = ind.evaluate_all(d, spec.get("entry") or [], spec.get("entry_mode", "and"))
    exit_c = spec.get("exit") or []
    exit_sig = ind.evaluate_all(d, exit_c, spec.get("exit_mode", "or")) if exit_c else np.zeros(n, dtype=bool)
    sl = float(spec["stop_loss"]) / 100 if spec.get("stop_loss") else None
    tp = float(spec["take_profit"]) / 100 if spec.get("take_profit") else None
    first_bar = int(spec.get("first_bar") or 0)                 # 이 봉 번호부터 진입 허용
    last_entry = int(spec.get("last_entry_bar") or 66)          # 이 봉 번호까지 진입 허용 (66 = 14:30)
    max_trades = int(spec.get("max_trades") or 1)
    cost = float(spec.get("cost_pct", COST * 100)) / 100
    trades = []
    for k, f in enumerate(d["first"]):
        e = d["last"][k]
        taken, pos, pending_in, pending_out = 0, None, False, False
        for i in range(f, e + 1):
            if pos is not None and pending_out:
                trades.append(_close(pos, i, o[i], "매도 조건", ts, cost)); pos = None
            pending_out = False
            if pos is None and pending_in:
                pos = dict(i=i, px=o[i]); taken += 1
            pending_in = False
            if pos is not None:
                if sl and l[i] <= pos["px"] * (1 - sl) and (i > pos["i"] or o[i] > pos["px"] * (1 - sl)):
                    trades.append(_close(pos, i, min(o[i], pos["px"] * (1 - sl)) if i > pos["i"] else pos["px"] * (1 - sl), "손절", ts, cost)); pos = None
                elif tp and h[i] >= pos["px"] * (1 + tp):
                    trades.append(_close(pos, i, max(o[i], pos["px"] * (1 + tp)) if i > pos["i"] else pos["px"] * (1 + tp), "익절", ts, cost)); pos = None
                elif i == e:
                    trades.append(_close(pos, i, c[i], "장 마감 청산", ts, cost)); pos = None
                elif exit_sig[i]:
                    pending_out = True
            elif taken < max_trades and entry[i] and first_bar <= d["bar"][i] <= last_entry and i < e:
                pending_in = True
    return dict(trades=trades, stats=stats(trades, d))


def _close(pos, i, px, why, ts, cost):
    r = px / pos["px"] - 1 - cost
    return dict(entry_ts=int(ts[pos["i"]]), entry_price=round(pos["px"], 2), exit_ts=int(ts[i]), exit_price=round(px, 2),
                ret_pct=round(r * 100, 3), bars=i - pos["i"], reason=why)


def stats(trades: list[dict], d: dict | None = None) -> dict:
    if not trades:
        return dict(n_trades=0)
    r = np.array([t["ret_pct"] for t in trades])
    se = r.std(ddof=1) / math.sqrt(len(r)) if len(r) > 1 else float("nan")
    wins, losses = r[r > 0], r[r <= 0]
    eq = np.cumprod(1 + r / 100)
    mdd = float((eq / np.maximum.accumulate(eq) - 1).min()) * 100
    out = dict(n_trades=len(r), avg=round(float(r.mean()), 3), median=round(float(np.median(r)), 3),
               win_rate=round(float((r > 0).mean()) * 100, 1), total=round(float(eq[-1] - 1) * 100, 2), mdd=round(mdd, 2),
               avg_win=round(float(wins.mean()), 3) if len(wins) else 0, avg_loss=round(float(losses.mean()), 3) if len(losses) else 0,
               profit_factor=round(float(wins.sum() / -losses.sum()), 2) if len(losses) and losses.sum() < 0 else None,
               t_stat=round(float(r.mean() / se), 2) if se and se > 0 else None,
               ci95=[round(float(r.mean() - 1.96 * se), 3), round(float(r.mean() + 1.96 * se), 3)] if se == se else None,
               avg_bars=round(float(np.mean([t["bars"] for t in trades])), 1))
    if d is not None:
        # 같은 날 시가에 사서 장 마감에 팔았을 때(비용 포함)와 비교
        days = {t["entry_ts"] // 86400 for t in trades}
        bh = [(d["c"][e] / d["o"][f] - 1 - COST) * 100 for f, e in zip(d["first"], d["last"]) if int(d["ts"][f]) // 86400 in days]
        out["same_day_open_close"] = round(float(np.mean(bh)), 3) if bh else None
        out["days"] = len(d["days"])
    return out


def I(name, *p, out=None, shift=0, mul=None):
    x = {"ind": name, "p": list(p)}
    if out:
        x["out"] = out
    if shift:
        x["shift"] = shift
    if mul:
        x["mul"] = mul
    return x


def C(a, op, b):
    return {"left": a, "op": op, "right": b if isinstance(b, dict) else {"value": b}}


PRESETS = {
    "open_close": dict(name="(기준) 장 시작 5분 뒤 매수 → 마감 매도", desc="아무 조건 없이 매일 09:05 봉 시가에 사서 장 마감에 판다",
                       spec=dict(entry=[C(I("bar_no"), ">=", 0)], exit=[], first_bar=0, last_entry_bar=0)),
    "orb30": dict(name="시가 범위 돌파 (30분)", desc="첫 30분(6봉) 고가를 넘으면 매수, 30분 저가 이탈 시 매도, 아니면 마감 청산",
                  spec=dict(entry=[C(I("close"), "cross_up", I("or_high", 6))], exit=[C(I("close"), "<", I("or_low", 6))], first_bar=6)),
    "gap_up_vwap": dict(name="갭 상승 + VWAP 위 유지", desc="시가가 전일 종가보다 2% 이상 높고, 30분 뒤에도 당일 VWAP 위면 매수",
                        spec=dict(entry=[C(I("gap"), ">", 2), C(I("close"), ">", I("svwap"))], exit=[C(I("close"), "cross_down", I("svwap"))],
                                  first_bar=6, stop_loss=2)),
    "gap_down_rebound": dict(name="갭 하락 반등", desc="시가가 2% 이상 낮게 시작한 뒤 당일 VWAP를 위로 돌파하면 매수",
                             spec=dict(entry=[C(I("gap"), "<", -2), C(I("close"), "cross_up", I("svwap"))], exit=[], first_bar=3, stop_loss=2)),
    "vwap_cross": dict(name="VWAP 상향 돌파", desc="당일 VWAP를 위로 뚫으면 매수, 다시 아래로 내려가면 매도",
                       spec=dict(entry=[C(I("close"), "cross_up", I("svwap"))], exit=[C(I("close"), "cross_down", I("svwap"))], first_bar=3, stop_loss=1.5)),
    "rsi5m": dict(name="5분 RSI 과매도 반등", desc="5분봉 RSI(14)가 30을 위로 회복하면 매수, 60을 넘으면 매도",
                  spec=dict(entry=[C(I("rsi", 14), "cross_up", 30)], exit=[C(I("rsi", 14), ">", 60)], first_bar=3, stop_loss=1.5)),
    "vol_burst": dict(name="5분 거래량 폭발 양봉", desc="5분 거래량이 직전 20봉 평균의 3배 이상이고 그 봉에서 1% 넘게 오르면 매수",
                      spec=dict(entry=[C(I("volume"), ">", I("vol_sma", 20, shift=1, mul=3)), C(I("change", 1), ">", 1)], exit=[], first_bar=2, stop_loss=2, take_profit=4)),
    "new_high": dict(name="당일 신고가 돌파", desc="오전 10시 이후 당일 고가를 새로 쓰고 당일 +3% 이상이면 매수",
                     spec=dict(entry=[C(I("close"), ">", I("day_high")), C(I("day_chg"), ">", 3)], exit=[], first_bar=12, stop_loss=2)),
}


def validate(limit: int = 300) -> dict:
    """프리셋 전략을 저장된 모든 종목에 돌린다. 기간을 앞·뒤 절반으로 나눠 일관성도 본다."""
    syms = [r[0] for r in intraday.conn().execute("SELECT symbol FROM bars GROUP BY symbol HAVING COUNT(*)>=20 LIMIT ?", (limit,)).fetchall()]
    all_days = sorted({r[0] for r in intraday.conn().execute("SELECT DISTINCT day FROM bars").fetchall()})
    if not syms or len(all_days) < 10:
        return {}
    mid = all_days[len(all_days) // 2]
    from datetime import datetime, timezone
    mid_ts = int(datetime.strptime(mid, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    res = {k: dict(name=v["name"], desc=v["desc"], trades=[]) for k, v in PRESETS.items()}
    market_day = {}   # 날짜별 '시가 매수 → 마감 매도' 전체 평균 (비용 포함)
    for s in syms:
        d = intraday.load(s)
        if d is None:
            continue
        for f, e in zip(d["first"], d["last"]):
            market_day.setdefault(int(d["ts"][f]) // 86400, []).append((d["c"][e] / d["o"][f] - 1 - COST) * 100)
        for k, v in PRESETS.items():
            try:
                res[k]["trades"] += [(t["entry_ts"], t["ret_pct"]) for t in run(d, v["spec"])["trades"]]
            except Exception:
                continue
    mday = {k: float(np.mean(v)) for k, v in market_day.items()}
    out = {}
    for k, v in res.items():
        tr = v["trades"]
        if len(tr) < 30:
            out[k] = dict(name=v["name"], desc=v["desc"], n=len(tr))
            continue
        r = np.array([x[1] for x in tr])
        ex = np.array([x[1] - mday.get(x[0] // 86400, 0) for x in tr])
        a = np.array([x[1] for x in tr if x[0] < mid_ts]); b = np.array([x[1] for x in tr if x[0] >= mid_ts])
        se = r.std(ddof=1) / math.sqrt(len(r))
        # 같은 날 여러 종목이 함께 움직여 거래들이 서로 독립이 아니므로, 날짜별 평균으로 다시 본 t값도 같이 낸다
        by_day = {}
        for x in tr:
            by_day.setdefault(x[0] // 86400, []).append(x[1])
        dm = np.array([np.mean(v) for v in by_day.values()])
        t_day = float(dm.mean() / (dm.std(ddof=1) / math.sqrt(len(dm)))) if len(dm) > 2 and dm.std() > 0 else None
        verdict = ("양쪽 기간 모두 비용 뺀 뒤 플러스" if a.size and b.size and a.mean() > 0 and b.mean() > 0 and (t_day or 0) > 2 else
                   "양쪽 기간 모두 마이너스" if a.size and b.size and a.mean() < 0 and b.mean() < 0 else "일관되지 않음 또는 근거 부족")
        out[k] = dict(name=v["name"], desc=v["desc"], n=len(r), days_traded=len(dm), avg=round(float(r.mean()), 3),
                      win=round(float((r > 0).mean()) * 100, 1), excess=round(float(ex.mean()), 3),
                      first=round(float(a.mean()), 3) if a.size else None, second=round(float(b.mean()), 3) if b.size else None,
                      t_trade=round(float(r.mean() / se), 2), t_day=round(t_day, 2) if t_day is not None else None, verdict=verdict)
    result = dict(at=db.now(), symbols=len(syms), days=len(all_days), first_day=all_days[0], last_day=all_days[-1], split=mid,
                  cost=round(COST * 100, 2), strategies=out)
    db.set_setting("validation_intraday", result)
    return result
