"""기술적 지표와 조건식 평가. 종목필터·매매신호·백테스트·알림이 같은 조건식을 쓴다.

조건식 예: {"left": {"ind": "sma", "p": [5]}, "op": "cross_up", "right": {"ind": "sma", "p": [20]}}
피연산자: {"ind": 이름, "p": [파라미터], "out": 출력명, "shift": n봉 전, "mul": 배수} 또는 {"value": 숫자}
"""
import numpy as np

NAN = np.nan


def sma(x: np.ndarray, n: int) -> np.ndarray:
    n = int(n)
    out = np.full(len(x), NAN)
    if len(x) < n or n < 1:
        return out
    cs = np.cumsum(np.insert(np.nan_to_num(x), 0, 0.0))
    out[n - 1:] = (cs[n:] - cs[:-n]) / n
    bad = np.isnan(x)
    if bad.any():  # 앞부분 NaN 구간은 그대로 NaN으로 둔다
        first = int(np.argmax(~bad)) if (~bad).any() else len(x)
        out[:first + n - 1] = NAN
    return out


def ema(x: np.ndarray, n: int) -> np.ndarray:
    n = int(n)
    out = np.full(len(x), NAN)
    valid = np.flatnonzero(~np.isnan(x))
    if len(valid) < n:
        return out
    s = valid[0]
    k = 2.0 / (n + 1)
    prev = float(np.mean(x[s:s + n]))
    out[s + n - 1] = prev
    for i in range(s + n, len(x)):
        prev = x[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def wilder(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), NAN)
    valid = np.flatnonzero(~np.isnan(x))
    if len(valid) < n:
        return out
    s = valid[0]
    prev = float(np.mean(x[s:s + n]))
    out[s + n - 1] = prev
    for i in range(s + n, len(x)):
        prev = (prev * (n - 1) + x[i]) / n
        out[i] = prev
    return out


def rsi(c: np.ndarray, n: int = 14) -> np.ndarray:
    d = np.diff(c, prepend=NAN)
    up, dn = np.where(d > 0, d, 0.0), np.where(d < 0, -d, 0.0)
    up[0] = dn[0] = NAN
    au, ad = wilder(up, n), wilder(dn, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = au / ad
        out = 100 - 100 / (1 + rs)
    out[(ad == 0) & ~np.isnan(au)] = 100.0
    return out


def macd(c: np.ndarray, fast=12, slow=26, sig=9):
    line = ema(c, fast) - ema(c, slow)
    signal = ema(line, sig)
    return line, signal, line - signal


def rolling_std(x: np.ndarray, n: int) -> np.ndarray:
    n = int(n)
    out = np.full(len(x), NAN)
    if len(x) < n:
        return out
    w = np.lib.stride_tricks.sliding_window_view(x, n)
    out[n - 1:] = w.std(axis=1)
    return out


def bollinger(c: np.ndarray, n=20, k=2.0):
    mid = sma(c, n)
    sd = rolling_std(c, n)
    return mid + k * sd, mid, mid - k * sd


def highest(x: np.ndarray, n: int) -> np.ndarray:
    n = int(n)
    out = np.full(len(x), NAN)
    if len(x) >= n:
        out[n - 1:] = np.lib.stride_tricks.sliding_window_view(x, n).max(axis=1)
    return out


def lowest(x: np.ndarray, n: int) -> np.ndarray:
    n = int(n)
    out = np.full(len(x), NAN)
    if len(x) >= n:
        out[n - 1:] = np.lib.stride_tricks.sliding_window_view(x, n).min(axis=1)
    return out


def stoch(h, l, c, n=14, k=3, d=3):
    hh, ll = highest(h, n), lowest(l, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = (c - ll) / (hh - ll) * 100
    raw[(hh - ll) == 0] = 50.0
    slow_k = sma(raw, k)
    return slow_k, sma(slow_k, d)


def true_range(h, l, c):
    pc = np.roll(c, 1)
    pc[0] = c[0]
    return np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))


def atr(h, l, c, n=14):
    return wilder(true_range(h, l, c), n)


def cci(h, l, c, n=20):
    tp = (h + l + c) / 3
    ma = sma(tp, n)
    out = np.full(len(c), NAN)
    if len(c) >= n:
        w = np.lib.stride_tricks.sliding_window_view(tp, n)
        md = np.abs(w - w.mean(axis=1, keepdims=True)).mean(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            out[n - 1:] = (tp[n - 1:] - ma[n - 1:]) / (0.015 * md)
    return out


def williams_r(h, l, c, n=14):
    hh, ll = highest(h, n), lowest(l, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        return (hh - c) / (hh - ll) * -100


def obv(c, v):
    d = np.sign(np.diff(c, prepend=c[0]))
    return np.cumsum(d * v)


def mfi(h, l, c, v, n=14):
    tp = (h + l + c) / 3
    flow = tp * v
    d = np.diff(tp, prepend=tp[0])
    pos, neg = np.where(d > 0, flow, 0.0), np.where(d < 0, flow, 0.0)
    ps, ns = sma(pos, n) * n, sma(neg, n) * n
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 100 - 100 / (1 + ps / ns)
    out[(ns == 0) & ~np.isnan(ps)] = 100.0
    return out


def adx(h, l, c, n=14):
    up, dn = np.diff(h, prepend=h[0]), -np.diff(l, prepend=l[0])
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = wilder(true_range(h, l, c), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi, ndi = 100 * wilder(pdm, n) / tr, 100 * wilder(ndm, n) / tr
        dx = 100 * np.abs(pdi - ndi) / (pdi + ndi)
    return wilder(dx, n), pdi, ndi


def vwap(h, l, c, v, n=20):
    """기간 거래량가중평균가 (일봉 기준 이동 VWAP)."""
    tp = (h + l + c) / 3
    with np.errstate(divide="ignore", invalid="ignore"):
        return sma(tp * v, n) / sma(v, n)


def change_pct(c, n=1):
    n = int(n)
    out = np.full(len(c), NAN)
    if len(c) > n:
        out[n:] = (c[n:] / c[:-n] - 1) * 100
    return out


# 화면에 노출하는 지표 목록. params: [(이름, 기본값)], outs: 출력 선택지
CATALOG = {
    "close": dict(label="종가", params=[], outs=[]),
    "open": dict(label="시가", params=[], outs=[]),
    "high": dict(label="고가", params=[], outs=[]),
    "low": dict(label="저가", params=[], outs=[]),
    "volume": dict(label="거래량", params=[], outs=[]),
    "sma": dict(label="이동평균(SMA)", params=[("기간", 20)], outs=[]),
    "ema": dict(label="지수이동평균(EMA)", params=[("기간", 20)], outs=[]),
    "vol_sma": dict(label="거래량 이동평균", params=[("기간", 20)], outs=[]),
    "rsi": dict(label="RSI", params=[("기간", 14)], outs=[]),
    "macd": dict(label="MACD", params=[("단기", 12), ("장기", 26), ("시그널", 9)], outs=["macd", "signal", "hist"]),
    "bb": dict(label="볼린저밴드", params=[("기간", 20), ("배수", 2)], outs=["upper", "mid", "lower"]),
    "stoch": dict(label="스토캐스틱", params=[("기간", 14), ("%K", 3), ("%D", 3)], outs=["k", "d"]),
    "atr": dict(label="ATR", params=[("기간", 14)], outs=[]),
    "cci": dict(label="CCI", params=[("기간", 20)], outs=[]),
    "willr": dict(label="윌리엄스 %R", params=[("기간", 14)], outs=[]),
    "mfi": dict(label="MFI", params=[("기간", 14)], outs=[]),
    "adx": dict(label="ADX", params=[("기간", 14)], outs=["adx", "pdi", "ndi"]),
    "obv": dict(label="OBV", params=[], outs=[]),
    "vwap": dict(label="VWAP(이동)", params=[("기간", 20)], outs=[]),
    "highest": dict(label="기간 최고가", params=[("기간", 20)], outs=[]),
    "lowest": dict(label="기간 최저가", params=[("기간", 20)], outs=[]),
    "change": dict(label="등락률(%)", params=[("기간", 1)], outs=[]),
}


def compute(d: dict, ind: str, p: list | None = None, out: str | None = None) -> np.ndarray:
    p = list(p or [])
    if "day" in d:  # 장중 자료면 장중 전용 지표를 먼저 본다
        from . import intraday_bt
        if ind in intraday_bt.INTRADAY:
            return intraday_bt.compute(d, ind, p)
    defaults = [x[1] for x in CATALOG.get(ind, {}).get("params", [])]
    p = p + defaults[len(p):]
    c, h, l, o, v = d["c"], d["h"], d["l"], d["o"], d["v"]
    if ind == "close":
        return c
    if ind == "open":
        return o
    if ind == "high":
        return h
    if ind == "low":
        return l
    if ind == "volume":
        return v
    if ind == "sma":
        return sma(c, p[0])
    if ind == "ema":
        return ema(c, p[0])
    if ind == "vol_sma":
        return sma(v, p[0])
    if ind == "rsi":
        return rsi(c, int(p[0]))
    if ind == "macd":
        m = macd(c, int(p[0]), int(p[1]), int(p[2]))
        return m[{"macd": 0, "signal": 1, "hist": 2}.get(out or "macd", 0)]
    if ind == "bb":
        b = bollinger(c, int(p[0]), float(p[1]))
        return b[{"upper": 0, "mid": 1, "lower": 2}.get(out or "mid", 1)]
    if ind == "stoch":
        s = stoch(h, l, c, int(p[0]), int(p[1]), int(p[2]))
        return s[{"k": 0, "d": 1}.get(out or "k", 0)]
    if ind == "atr":
        return atr(h, l, c, int(p[0]))
    if ind == "cci":
        return cci(h, l, c, int(p[0]))
    if ind == "willr":
        return williams_r(h, l, c, int(p[0]))
    if ind == "mfi":
        return mfi(h, l, c, v, int(p[0]))
    if ind == "adx":
        a = adx(h, l, c, int(p[0]))
        return a[{"adx": 0, "pdi": 1, "ndi": 2}.get(out or "adx", 0)]
    if ind == "obv":
        return obv(c, v)
    if ind == "vwap":
        return vwap(h, l, c, v, int(p[0]))
    if ind == "highest":
        return highest(h, p[0])
    if ind == "lowest":
        return lowest(l, p[0])
    if ind == "change":
        return change_pct(c, p[0])
    raise ValueError(f"알 수 없는 지표: {ind}")


def operand(d: dict, op: dict) -> np.ndarray:
    n = len(d["c"])
    if "value" in op and "ind" not in op:
        return np.full(n, float(op["value"]))
    x = compute(d, op["ind"], op.get("p"), op.get("out")).astype(np.float64)
    sh = int(op.get("shift") or 0)
    if sh > 0:
        x = np.concatenate([np.full(sh, NAN), x[:-sh]]) if sh < n else np.full(n, NAN)
    mul = op.get("mul")
    if mul not in (None, "", 1):
        x = x * float(mul)
    return x


def evaluate(d: dict, cond: dict) -> np.ndarray:
    a, b = operand(d, cond["left"]), operand(d, cond["right"])
    op = cond["op"]
    with np.errstate(invalid="ignore"):
        if op == ">":
            r = a > b
        elif op == "<":
            r = a < b
        elif op == ">=":
            r = a >= b
        elif op == "<=":
            r = a <= b
        elif op in ("cross_up", "cross_down"):
            pa, pb = np.roll(a, 1), np.roll(b, 1)
            r = (a > b) & (pa <= pb) if op == "cross_up" else (a < b) & (pa >= pb)
            r[0] = False
        else:
            raise ValueError(f"알 수 없는 연산자: {op}")
    r = r & ~np.isnan(a) & ~np.isnan(b)
    return r


def evaluate_all(d: dict, conds: list[dict], mode: str = "and") -> np.ndarray:
    n = len(d["c"])
    if not conds:
        return np.zeros(n, dtype=bool)
    res = [evaluate(d, c) for c in conds]
    out = res[0]
    for r in res[1:]:
        out = (out & r) if mode == "and" else (out | r)
    return out


def describe(op: dict) -> str:
    if "ind" not in op:
        return f"{op.get('value')}"
    meta = CATALOG.get(op["ind"], {})
    s = meta.get("label", op["ind"])
    if op.get("p"):
        s += "(" + ",".join(str(x) for x in op["p"]) + ")"
    if op.get("out"):
        s += f".{op['out']}"
    if op.get("shift"):
        s += f" {op['shift']}봉 전"
    if op.get("mul") not in (None, "", 1):
        s += f" ×{op['mul']}"
    return s


OP_LABEL = {">": "＞", "<": "＜", ">=": "≥", "<=": "≤", "cross_up": "상향 돌파", "cross_down": "하향 돌파"}


def describe_cond(c: dict) -> str:
    return f"{describe(c['left'])} {OP_LABEL.get(c['op'], c['op'])} {describe(c['right'])}"


def chart_series(d: dict, specs: list[dict]) -> list[dict]:
    """차트 보조지표용. specs: [{ind, p}] → 출력별 시계열."""
    out = []
    ts = d["ts"]
    for sp in specs:
        ind = sp["ind"]
        outs = CATALOG.get(ind, {}).get("outs") or [None]
        for o in outs:
            arr = compute(d, ind, sp.get("p"), o)
            out.append(dict(ind=ind, out=o, p=sp.get("p") or [],
                            data=[[int(t), round(float(x), 4)] for t, x in zip(ts, arr) if not np.isnan(x)]))
    return out
