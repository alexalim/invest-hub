"""조건식 기반 백테스트. 매수 전용, 전액 진입·전액 청산.
신호는 봉 종가에 확정되고 다음 봉 시가에 체결한다 (미래 정보 사용 방지)."""
import math

import numpy as np

from . import indicators as ind


def run(d: dict, spec: dict) -> dict:
    n = len(d["c"])
    ts, o, h, l, c = d["ts"], d["o"], d["h"], d["l"], d["c"]
    entry = ind.evaluate_all(d, spec.get("entry") or [], spec.get("entry_mode", "and"))
    exit_conds = spec.get("exit") or []
    exit_sig = ind.evaluate_all(d, exit_conds, spec.get("exit_mode", "or")) if exit_conds else np.zeros(n, dtype=bool)
    sl = float(spec["stop_loss"]) / 100 if spec.get("stop_loss") else None
    tp = float(spec["take_profit"]) / 100 if spec.get("take_profit") else None
    max_hold = int(spec["max_hold"]) if spec.get("max_hold") else None
    fee = float(spec.get("fee_pct", 0.015)) / 100
    tax = float(spec.get("tax_pct", 0.18)) / 100
    start_ts = int(spec.get("start") or 0)
    end_ts = int(spec.get("end") or 2 ** 62)
    first = int(np.searchsorted(ts, start_ts))

    cash, shares = 1.0, 0.0
    entry_price, entry_i = 0.0, -1
    trades, equity = [], []
    pending_buy = pending_sell = False
    reason = ""
    in_market = 0

    def close(i: int, price: float, why: str):
        nonlocal cash, shares
        proceeds = shares * price * (1 - fee - tax)
        ret = proceeds / (shares * entry_price * (1 + fee)) - 1
        trades.append(dict(entry_ts=int(ts[entry_i]), entry_price=round(entry_price, 4), exit_ts=int(ts[i]),
                           exit_price=round(price, 4), ret_pct=round(ret * 100, 2), bars=i - entry_i, reason=why))
        cash, shares = proceeds, 0.0

    for i in range(first, n):
        if ts[i] > end_ts:
            break
        if pending_sell and shares > 0:
            close(i, o[i], reason)
        pending_sell = False
        if pending_buy and shares == 0:
            entry_price, entry_i = o[i], i
            shares = cash / (entry_price * (1 + fee))
            cash = 0.0
        pending_buy = False
        if shares > 0:
            in_market += 1
            stop_p = entry_price * (1 - sl) if sl else None
            take_p = entry_price * (1 + tp) if tp else None
            if stop_p and l[i] <= stop_p and i > entry_i:
                close(i, min(o[i], stop_p), "손절")
            elif take_p and h[i] >= take_p and i > entry_i:
                close(i, max(o[i], take_p), "익절")
            elif exit_sig[i]:
                pending_sell, reason = True, "매도 조건"
            elif max_hold and i - entry_i >= max_hold:
                pending_sell, reason = True, "보유 기간 만료"
        elif entry[i]:
            pending_buy = True
        equity.append((int(ts[i]), cash + shares * c[i]))
    if shares > 0 and equity:
        i = min(n - 1, int(np.searchsorted(ts, equity[-1][0])))
        close(i, c[i], "기간 종료")
        equity[-1] = (equity[-1][0], cash)
    return dict(trades=trades, equity=[[t, round(e, 5)] for t, e in equity], stats=_stats(trades, equity, c, ts, first, in_market))


def _stats(trades, equity, c, ts, first, in_market) -> dict:
    if not equity:
        return dict(n_trades=0)
    eq = np.array([e for _, e in equity])
    total = eq[-1] - 1
    days = max(1, (equity[-1][0] - equity[0][0]) / 86400)
    cagr = (eq[-1] ** (365 / days) - 1) if eq[-1] > 0 and days > 30 else total
    peak = np.maximum.accumulate(eq)
    mdd = float(((eq - peak) / peak).min())
    rets = [t["ret_pct"] for t in trades]
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    daily = np.diff(eq) / eq[:-1] if len(eq) > 1 else np.array([0.0])
    sharpe = float(daily.mean() / daily.std() * math.sqrt(252)) if daily.std() > 0 else 0.0
    last_i = min(len(c) - 1, first + len(equity) - 1)
    bh = c[last_i] / c[first] - 1 if c[first] else 0.0
    return dict(
        n_trades=len(trades), total_return=round(total * 100, 2), cagr=round(cagr * 100, 2), mdd=round(mdd * 100, 2),
        win_rate=round(len(wins) / len(rets) * 100, 1) if rets else 0.0,
        avg_return=round(float(np.mean(rets)), 2) if rets else 0.0,
        avg_win=round(float(np.mean(wins)), 2) if wins else 0.0,
        avg_loss=round(float(np.mean(losses)), 2) if losses else 0.0,
        profit_factor=round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else None,
        avg_bars=round(float(np.mean([t["bars"] for t in trades])), 1) if trades else 0.0,
        buy_hold=round(float(bh) * 100, 2), exposure=round(in_market / len(equity) * 100, 1), sharpe=round(sharpe, 2))


def forward_stats(d: dict, mask: np.ndarray, horizons=(5, 10, 20), side: str = "buy") -> dict:
    """신호 발생 시점 이후 n일 수익률 통계. 매매신호의 과거 성과 계산에 쓴다."""
    c = d["c"]
    n = len(c)
    out = {}
    idx = np.flatnonzero(mask)
    for hz in horizons:
        ii = idx[idx + hz < n]
        if len(ii) == 0:
            out[str(hz)] = dict(n=0, avg=None, win=None)
            continue
        r = c[ii + hz] / c[ii] - 1
        good = (r > 0) if side == "buy" else (r < 0)
        out[str(hz)] = dict(n=int(len(ii)), avg=round(float(r.mean()) * 100, 2), win=round(float(good.mean()) * 100, 1),
                            median=round(float(np.median(r)) * 100, 2))
    return out
