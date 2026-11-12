"""전략·예측 검증 (워크포워드). 각 시점에는 그때까지 결과가 확정된 정보만 쓴다.

- 매수 시점: 신호 다음 날 시가, 매도: 20거래일 뒤 종가, 거래비용 0.25%
- '시장 대비'는 같은 날 대상 종목 전체의 같은 방식 평균 수익률을 뺀 값
- 대상: 국내 주식 중 현재 시가총액 3천억 원 이상 (현재 기준이라 생존 편향이 있다)
결과는 settings 'validation'에 저장하고 화면이 읽어 간다."""
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

from .. import db
from . import indicators as ind, signals, similar, store

log = logging.getLogger("validate")
H, COST = 20, 0.0025


def _universe() -> dict:
    syms = [r["symbol"] for r in db.q("SELECT symbol FROM instruments WHERE market IN ('KOSPI','KOSDAQ') AND kind='stock' AND mcap>=3e11")]
    out = {}
    for s in syms:
        d = store.get(s, live=False)
        if d is not None and len(d["c"]) >= 300:
            out[s] = d
    return out


def _fwd(d: dict) -> np.ndarray:
    n = len(d["c"])
    f = np.full(n, np.nan)
    f[:n - H - 1] = d["c"][H + 1:] / d["o"][1:n - H] - 1
    return f


def strategies(data: dict) -> dict:
    """전략별 모든 매수 신호의 시장 대비 성과(최근 2년, 앞 1년/뒤 1년)와 '종목별 과거 적중률' 선별 규칙의 효과."""
    buy = {k: v for k, v in signals.STRATEGIES.items() if v["side"] == "buy"}
    mk = defaultdict(list)
    recs = []  # (ts, fwd, strategy, selected)
    for d in data.values():
        f = _fwd(d)
        n = len(f)
        for i in range(n - H - 1):
            mk[int(d["ts"][i])].append(f[i])
        for k, st in buy.items():
            idx = np.flatnonzero(ind.evaluate_all(d, st["conds"]))
            idx = idx[idx < n - H - 1]
            for t, i in enumerate(idx):
                prior = idx[:t]
                pr = f[prior[prior + H + 1 <= i]]
                sel = len(pr) >= 5 and pr.mean() > 0 and (pr > 0).mean() >= 0.55
                recs.append((int(d["ts"][i]), f[i], k, sel))
    mkt = {t: float(np.nanmean(v)) for t, v in mk.items()}
    end = max(mkt)
    cut, mid = end - 2 * 365 * 86400, end - 365 * 86400
    per = {}
    for k in buy:
        a = [r - mkt[t] for t, r, kk, _ in recs if kk == k and cut <= t < mid]
        b = [r - mkt[t] for t, r, kk, _ in recs if kk == k and t >= mid]
        if len(a) >= 50 and len(b) >= 50:
            ea, eb = float(np.mean(a)) * 100, float(np.mean(b)) * 100
            per[k] = dict(name=buy[k]["name"], first=round(ea, 2), second=round(eb, 2), n=len(a) + len(b),
                          verdict="양쪽 모두 시장보다 나음" if ea > 0.3 and eb > 0.3 else
                          "양쪽 모두 시장보다 못함" if ea < 0 and eb < 0 else "일관되지 않음")
    recent = [(t, r, s) for t, r, _, s in recs if t >= cut]
    sel = [r - mkt[t] for t, r, s in recent if s]
    rej = [r - mkt[t] for t, r, s in recent if not s]
    return dict(per_strategy=per, period=[cut, end],
                selection=dict(selected=round(float(np.mean(sel)) * 100, 2), selected_n=len(sel),
                               rejected=round(float(np.mean(rej)) * 100, 2), rejected_n=len(rej)))


def ai(data: dict, window: int = 60, k: int = 30, n_dates: int = 26, limit: int = 200) -> dict:
    """AI예측: 과거 시험일마다 그 이전에 결과가 끝난 구간만으로 예측하고 실제 20일 수익률과 비교."""
    ix = similar.index(window)
    end_ts = np.array([int(store.get(ix.symbols[s], live=False)["ts"][st + window - 1 + H]) for s, st in zip(ix.sym, ix.start)])
    top = [r["symbol"] for r in db.q("SELECT symbol FROM instruments WHERE market IN ('KOSPI','KOSDAQ') AND kind='stock' "
                                     "ORDER BY mcap DESC LIMIT ?", (limit,))]
    D = {s: data.get(s) or store.get(s, live=False) for s in top}
    D = {s: d for s, d in D.items() if d is not None and len(d["c"]) > 400}
    ref = max(D.values(), key=lambda d: d["ts"][-1])["ts"]
    dates = [int(t) for t in ref[-(n_dates * 10) - H - 1:-H - 1:10]]
    by = defaultdict(list)
    for T in dates:
        ok = end_ts < T
        Xa, Fa = ix.X[ok], ix.F[ok][:, -1]
        for d in D.values():
            i = int(np.searchsorted(d["ts"], T))
            if i >= len(d["c"]) or d["ts"][i] != T or i < window or i + H + 1 >= len(d["c"]):
                continue
            q = similar._znorm(d["c"][i - window + 1:i + 1][None, :])
            if q is None or not np.isfinite(q).all():
                continue
            fin = Fa[np.argsort(-(Xa @ q[0] / window))[:k]]
            up, med = float((fin > 0).mean()), float(np.median(fin))
            score = (up - 0.5) * 2 + float(np.clip(med * 5, -0.6, 0.6))
            by[T].append((score, d["c"][i + H + 1] / d["o"][i + 1] - 1))
    ics, op = [], defaultdict(list)
    rank = lambda x: np.argsort(np.argsort(x))
    for rs in by.values():
        sc, re = np.array([r[0] for r in rs]), np.array([r[1] for r in rs])
        if len(rs) > 10:
            ics.append(float(np.corrcoef(rank(sc), rank(re))[0, 1]))
        for s, r in rs:
            o = "강력 매수" if s > .55 else "매수" if s > .2 else "강력 매도" if s < -.55 else "매도" if s < -.2 else "중립"
            op[o].append(r - re.mean())
    return dict(ic=round(float(np.mean(ics)), 3), ic_pos=round(float(np.mean(np.array(ics) > 0)) * 100), dates=len(ics),
                n=sum(len(v) for v in by.values()),
                by_opinion={o: dict(excess=round(float(np.mean(v)) * 100, 2), n=len(v)) for o, v in op.items()})


def run() -> dict:
    t0 = time.time()
    data = _universe()
    res = dict(at=db.now(), universe=len(data), horizon=H, cost=COST * 100, strategies=strategies(data), ai=ai(data))
    res["seconds"] = round(time.time() - t0)
    db.set_setting("validation", res)
    log.info("validation done in %ss", res["seconds"])
    return dict(universe=res["universe"], ai_ic=res["ai"]["ic"], seconds=res["seconds"])
