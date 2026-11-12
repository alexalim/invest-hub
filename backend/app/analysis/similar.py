"""유사차트 검색과 AI예측.
모든 종목의 과거 일봉에서 길이 W의 구간을 잘라 정규화해 두고, 조회 구간과의 상관계수로 가장 닮은 구간을 찾는다.
닮은 구간들이 그 뒤 H일 동안 어떻게 움직였는지를 모아 예상 경로·상승 확률·목표가·손절가를 만든다."""
import logging
import threading
import time

import numpy as np

from .. import db
from ..providers import market
from . import store

log = logging.getLogger("similar")
HORIZON = 20
STRIDE = 4
_indexes: dict[int, "Index"] = {}
_lock = threading.Lock()


def _znorm(w: np.ndarray) -> np.ndarray | None:
    x = np.log(w)
    x = x - x.mean(axis=-1, keepdims=True)
    sd = x.std(axis=-1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = (x / sd).astype(np.float32)
    if z.shape[0] == 1 and not np.isfinite(z).all():  # 단일 조회 구간이 평평하면 비교할 수 없다
        return None
    return z


class Index:
    def __init__(self, window: int):
        self.window = window
        self.built_at = 0.0
        self.X = np.zeros((0, window), dtype=np.float32)   # 과거 구간 (미래가 알려진 것)
        self.F = np.zeros((0, HORIZON), dtype=np.float32)  # 구간 종료 후 H일 누적수익률 경로
        self.sym = np.zeros(0, dtype=np.int32)
        self.start = np.zeros(0, dtype=np.int32)
        self.symbols: list[str] = []
        self.CX = np.zeros((0, window), dtype=np.float32)  # 종목별 현재 구간
        self.csym: list[str] = []

    def build(self):
        t0 = time.time()
        W, H = self.window, HORIZON
        xs, fs, syms, starts, cx, csym = [], [], [], [], [], []
        self.symbols = store.synced_symbols(W + H + 20)
        for si, s in enumerate(self.symbols):
            d = store.get(s, live=False)
            if d is None:
                continue
            c = d["c"]
            if (c <= 0).any():
                continue
            n = len(c)
            win = np.lib.stride_tricks.sliding_window_view(c, W)  # (n-W+1, W)
            ends = np.arange(W - 1, n - H, STRIDE)
            if len(ends):
                w = win[ends - W + 1]
                z = _znorm(w)
                ok = np.isfinite(z).all(axis=1)
                fut = np.stack([c[ends + k] / c[ends] - 1 for k in range(1, H + 1)], axis=1).astype(np.float32)
                xs.append(z[ok])
                fs.append(fut[ok])
                syms.append(np.full(int(ok.sum()), si, dtype=np.int32))
                starts.append((ends - W + 1)[ok].astype(np.int32))
            zc = _znorm(c[-W:][None, :])
            if zc is not None and np.isfinite(zc).all():
                cx.append(zc[0])
                csym.append(s)
        if xs:
            self.X, self.F = np.concatenate(xs), np.concatenate(fs)
            self.sym, self.start = np.concatenate(syms), np.concatenate(starts)
        if cx:
            self.CX, self.csym = np.stack(cx), csym
        self.built_at = time.time()
        log.info("similar index W=%d: %d windows, %d symbols, %.1fs", W, len(self.X), len(self.symbols), time.time() - t0)


def index(window: int = 60) -> Index:
    with _lock:
        ix = _indexes.get(window)
        if ix is None or time.time() - ix.built_at > 6 * 3600 or len(ix.X) == 0:
            ix = Index(window)
            ix.build()
            _indexes[window] = ix
        return ix


def invalidate():
    with _lock:
        _indexes.clear()


def status() -> dict:
    return {w: dict(windows=int(len(ix.X)), symbols=len(ix.symbols), built_at=int(ix.built_at)) for w, ix in _indexes.items()}


def _matches(ix: Index, q: np.ndarray, symbol: str | None, k: int, min_gap: int = 30) -> list[dict]:
    corr = ix.X @ q / ix.window
    order = np.argsort(-corr)[: k * 40]
    out, used = [], {}
    self_i = ix.symbols.index(symbol) if symbol in ix.symbols else -1
    n_self = len(store.get(symbol, live=False)["c"]) if self_i >= 0 else 0
    for j in order:
        si, st = int(ix.sym[j]), int(ix.start[j])
        if si == self_i and st + ix.window + HORIZON > n_self - ix.window:  # 자기 자신의 최근 구간은 제외
            continue
        prev = used.setdefault(si, [])
        if any(abs(st - p) < min_gap for p in prev) or len(prev) >= 2:
            continue
        prev.append(st)
        out.append(dict(j=int(j), corr=float(corr[j])))
        if len(out) >= k:
            break
    return out


def _detail(ix: Index, m: dict, with_series: bool = True) -> dict:
    j = m["j"]
    s = ix.symbols[int(ix.sym[j])]
    d = store.get(s, live=False)
    st, W = int(ix.start[j]), ix.window
    out = dict(symbol=s, name=market.name_of(s), corr=round(m["corr"], 3), start_ts=int(d["ts"][st]), end_ts=int(d["ts"][st + W - 1]),
               fwd=[round(float(x) * 100, 2) for x in ix.F[j][[4, 9, 19]]])
    if with_series:
        seg = d["c"][st: st + W + HORIZON]
        out["series"] = [round(float(x / seg[W - 1] * 100 - 100), 2) for x in seg]
    return out


def predict(symbol: str, window: int = 60, k: int = 30) -> dict | None:
    d = store.get(symbol)
    if d is None or len(d["c"]) < window + 5:
        return None
    ix = index(window)
    c = d["c"]
    q = _znorm(c[-window:][None, :])
    if q is None or len(ix.X) == 0:
        return None
    ms = _matches(ix, q[0], symbol, k)
    if not ms:
        return None
    F = ix.F[[m["j"] for m in ms]]
    w = np.array([max(m["corr"], 0) ** 4 for m in ms])
    w = w / w.sum() if w.sum() > 0 else np.full(len(ms), 1 / len(ms))
    final = F[:, -1]
    med_path = np.median(F, axis=0)
    up = float((w * (final > 0)).sum())
    exp = float((w * final).sum())
    p25, p50, p75 = (float(x) for x in np.percentile(final, [25, 50, 75]))
    score = (up - 0.5) * 2 + np.clip(p50 * 5, -0.6, 0.6)
    opinion = ("강력 매수" if score > 0.55 else "매수" if score > 0.2 else "강력 매도" if score < -0.55
               else "매도" if score < -0.2 else "중립")
    last = float(c[-1])
    target = last * (1 + max(p75, 0.02))
    stop = last * (1 + min(p25, -0.02))
    return dict(
        symbol=symbol, window=window, horizon=HORIZON, price=last, opinion=opinion, up_prob=round(up * 100, 1),
        expected=round(exp * 100, 2), median=round(p50 * 100, 2), p25=round(p25 * 100, 2), p75=round(p75 * 100, 2),
        target=round(target, 4), stop=round(stop, 4), avg_corr=round(float(np.mean([m["corr"] for m in ms])), 3),
        query=[round(float(x / last * 100 - 100), 2) for x in c[-window:]],
        query_ts=[int(t) for t in d["ts"][-window:]],
        path=dict(median=[round(float(x) * 100, 2) for x in med_path],
                  p25=[round(float(x) * 100, 2) for x in np.percentile(F, 25, axis=0)],
                  p75=[round(float(x) * 100, 2) for x in np.percentile(F, 75, axis=0)]),
        dist=[round(float(x) * 100, 2) for x in np.sort(final)],
        matches=[_detail(ix, m) for m in ms[:12]], n_matches=len(ms), index_size=int(len(ix.X)))


def similar_now(symbol: str, window: int = 60, k: int = 20) -> list[dict]:
    """지금 차트가 이 종목과 닮은 다른 종목."""
    d = store.get(symbol)
    if d is None or len(d["c"]) < window:
        return []
    ix = index(window)
    q = _znorm(d["c"][-window:][None, :])
    if q is None or len(ix.CX) == 0:
        return []
    corr = ix.CX @ q[0] / window
    out = []
    for j in np.argsort(-corr)[: k + 1]:
        s = ix.csym[int(j)]
        if s == symbol:
            continue
        dd = store.get(s)
        seg = dd["c"][-window:]
        out.append(dict(symbol=s, name=market.name_of(s), corr=round(float(corr[j]), 3),
                        series=[round(float(x / seg[-1] * 100 - 100), 2) for x in seg]))
    return out[:k]


def rank_predictions(symbols: list[str], window: int = 60, k: int = 30) -> list[dict]:
    """여러 종목의 예측을 한꺼번에 계산해 순위표를 만든다 (AI예측 목록)."""
    ix = index(window)
    if len(ix.X) == 0:
        return []
    out = []
    for s in symbols:
        d = store.get(s)
        if d is None or len(d["c"]) < window + 5:
            continue
        q = _znorm(d["c"][-window:][None, :])
        if q is None or not np.isfinite(q).all():
            continue
        ms = _matches(ix, q[0], s, k)
        if len(ms) < 10:
            continue
        final = ix.F[[m["j"] for m in ms]][:, -1]
        up = float((final > 0).mean())
        p25, p50, p75 = (float(x) for x in np.percentile(final, [25, 50, 75]))
        score = (up - 0.5) * 2 + float(np.clip(p50 * 5, -0.6, 0.6))
        last = float(d["c"][-1])
        out.append(dict(symbol=s, score=round(score, 3), up_prob=round(up * 100, 1), median=round(p50 * 100, 2),
                        target=round(last * (1 + max(p75, 0.02)), 4), stop=round(last * (1 + min(p25, -0.02)), 4),
                        price=last, avg_corr=round(float(np.mean([m["corr"] for m in ms])), 3),
                        opinion=("강력 매수" if score > 0.55 else "매수" if score > 0.2 else "강력 매도" if score < -0.55
                                 else "매도" if score < -0.2 else "중립")))
    return out


def search_custom(series: list[float], window: int = 60, k: int = 20) -> list[dict]:
    """직접 그린 모양(임의 길이의 값 목록)과 닮은 현재 차트를 찾는다."""
    if len(series) < 5:
        return []
    x = np.interp(np.linspace(0, len(series) - 1, window), np.arange(len(series)), np.array(series, dtype=np.float64))
    x = x - x.min() + 1.0
    q = _znorm(x[None, :])
    if q is None:
        return []
    ix = index(window)
    corr = ix.CX @ q[0] / window
    out = []
    for j in np.argsort(-corr)[:k]:
        s = ix.csym[int(j)]
        seg = store.get(s)["c"][-window:]
        out.append(dict(symbol=s, name=market.name_of(s), corr=round(float(corr[j]), 3),
                        series=[round(float(v / seg[-1] * 100 - 100), 2) for v in seg]))
    return out
