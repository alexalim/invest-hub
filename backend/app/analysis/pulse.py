"""시장 흐름 읽기: 투자자별 수급, 위험 지표, 공포·탐욕, 상대강도(RS).

모두 무료 공개 시세로 계산한다. 수급은 다음 금융, 종목별 수급은 네이버, 해외 위험 지표는 야후 시세를 쓴다.
"""
import asyncio
import json
import logging
import time
import warnings
from datetime import datetime, timedelta, timezone

import numpy as np

from .. import db
from ..providers import daum, naver, yahoo

log = logging.getLogger("pulse")
MARKETS = ("KOSPI", "KOSDAQ")
_cache: dict[str, tuple[float, object]] = {}


def _kst() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=9)


def _cached(key: str, ttl: float):
    hit = _cache.get(key)
    return hit[1] if hit and time.time() - hit[0] < ttl else None


def _put(key: str, value):
    _cache[key] = (time.time(), value)
    return value


def _date(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), timezone.utc).strftime("%Y%m%d")


# ── 투자자별 수급 ──────────────────────────────────────────────────────
def regular_session() -> bool:
    n = _kst()
    return n.weekday() < 5 and (9, 0) <= (n.hour, n.minute) <= (15, 45)


def _save_days(market: str, rows: list[dict]):
    db.many("INSERT OR REPLACE INTO flow_days(market,date,individual,foreigner,institution,details) VALUES(?,?,?,?,?,?)",
            [(market, r["date"], r["individual"], r["foreigner"], r["institution"], json.dumps(r["details"])) for r in rows])


async def flow_tick() -> str:
    """당일 누계를 받아 일별 표를 갱신하고, 정규장 중이면 장중 기록을 한 점 남긴다."""
    today = _kst().strftime("%Y%m%d")
    ts = db.now() // 60 * 60
    n = 0
    for mk in MARKETS:
        rows = await daum.investor_days(mk, 1, 5)
        if not rows:
            continue
        _save_days(mk, rows)
        r = rows[0]
        if r["date"] == today and regular_session():
            db.ex("INSERT OR REPLACE INTO flow_ticks(market,date,ts,individual,foreigner,institution,details) VALUES(?,?,?,?,?,?,?)",
                  (mk, today, ts, r["individual"], r["foreigner"], r["institution"], json.dumps(r["details"])))
            n += 1
    db.ex("DELETE FROM flow_ticks WHERE date < ?", ((_kst() - timedelta(days=14)).strftime("%Y%m%d"),))
    return f"장중 기록 {n}건"


async def flow_backfill(pages: int = 6) -> int:
    """일별 수급 과거분(약 2년)을 채운다. 이미 있으면 건너뛴다."""
    n = 0
    for mk in MARKETS:
        if (db.val("SELECT COUNT(*) FROM flow_days WHERE market=?", (mk,)) or 0) >= pages * 90:
            continue
        for page in range(1, pages + 1):
            rows = await daum.investor_days(mk, page, 100)
            if not rows:
                break
            _save_days(mk, rows)
            n += len(rows)
    return n


def _index_closes(market: str) -> dict[str, float]:
    return {_date(r["ts"]): r["c"] for r in db.q("SELECT ts,c FROM candles WHERE symbol=? AND tf='day' ORDER BY ts", (f"IX:{market}",))}


def flow_view(market: str, days: int = 60) -> dict:
    market = market if market in MARKETS else "KOSPI"
    days = max(5, min(int(days), 520))
    tick_date = db.val("SELECT MAX(date) FROM flow_ticks WHERE market=?", (market,))
    ticks = []
    if tick_date:
        for r in db.q("SELECT ts,individual,foreigner,institution,details FROM flow_ticks WHERE market=? AND date=? ORDER BY ts", (market, tick_date)):
            ticks.append(dict(ts=r["ts"], individual=r["individual"], foreigner=r["foreigner"], institution=r["institution"],
                              **json.loads(r["details"] or "{}")))
    rows = db.q("SELECT date,individual,foreigner,institution,details FROM flow_days WHERE market=? ORDER BY date DESC LIMIT ?", (market, days))
    rows.reverse()
    closes = _index_closes(market)
    hist = [dict(date=r["date"], individual=r["individual"], foreigner=r["foreigner"], institution=r["institution"],
                 close=closes.get(r["date"]), **json.loads(r["details"] or "{}")) for r in rows]
    latest = hist[-1] if hist else None

    def total(n: int) -> dict:
        part = hist[-n:]
        return {k: round(sum(x.get(k) or 0 for x in part), 1) for k in ("individual", "foreigner", "institution", *daum.DETAIL_NAMES)}

    return dict(market=market, tick_date=tick_date, ticks=ticks, days=hist, latest=latest,
                sums={"5": total(5), "20": total(20), str(len(hist)): total(len(hist))}, names=daum.DETAIL_NAMES,
                live=regular_session())


async def stock_flow_sync(limit: int = 200) -> int:
    """시가총액 상위 종목의 외국인·기관 순매수(최근 20거래일)를 받아 둔다."""
    syms = [r["symbol"] for r in db.q("SELECT symbol FROM instruments WHERE market IN ('KOSPI','KOSDAQ') AND kind='stock' "
                                      "AND mcap IS NOT NULL ORDER BY mcap DESC LIMIT ?", (limit,))]
    sem = asyncio.Semaphore(5)
    n = 0

    async def one(sym: str):
        nonlocal n
        async with sem:
            try:
                rows = await naver.trend_kr(sym.split(":")[1])
            except Exception as e:
                log.warning("stock flow %s: %s", sym, e)
                return
        data = [(sym, r["date"], r["foreign"], r["organ"], r["individual"], r["close"], r["foreign_hold"]) for r in rows if r.get("date")]
        if data:
            db.many("INSERT OR REPLACE INTO stock_flows(symbol,date,foreign_qty,organ_qty,indiv_qty,close,foreign_hold) VALUES(?,?,?,?,?,?,?)", data)
            n += 1

    await asyncio.gather(*(one(s) for s in syms))
    db.ex("DELETE FROM stock_flows WHERE date < ?", ((_kst() - timedelta(days=90)).strftime("%Y%m%d"),))
    db.set_setting("stock_flows_at", db.now())
    return n


def stock_flow_view(who: str = "foreign", span: int = 1, limit: int = 20) -> dict:
    """외국인·기관이 많이 사고판 종목. 금액은 '순매수 수량 × 그날 종가'로 어림한 값(억원)이다."""
    col = {"foreign": "foreign_qty", "organ": "organ_qty", "individual": "indiv_qty"}.get(who, "foreign_qty")
    span = max(1, min(int(span), 20))
    limit = max(1, min(int(limit), 50))
    dates = [r["date"] for r in db.q("SELECT DISTINCT date FROM stock_flows ORDER BY date DESC LIMIT ?", (span,))]
    if not dates:
        return dict(dates=[], buy=[], sell=[], synced_at=db.get_setting("stock_flows_at"))
    ph = ",".join("?" * len(dates))
    rows = db.q(f"SELECT f.symbol, i.name, i.market, i.price, i.change_pct, i.mcap, SUM(f.{col}*f.close)/1e8 AS amount, "
                f"SUM(f.{col}) AS qty, MAX(CASE WHEN f.date=? THEN f.foreign_hold END) AS foreign_hold "
                f"FROM stock_flows f JOIN instruments i ON i.symbol=f.symbol WHERE f.date IN ({ph}) GROUP BY f.symbol", (dates[0], *dates))
    rows = [r for r in rows if r["amount"] is not None]
    for r in rows:
        r["amount"] = round(r["amount"], 1)
    buy = sorted(rows, key=lambda r: -r["amount"])[:limit]
    sell = sorted(rows, key=lambda r: r["amount"])[:limit]
    return dict(dates=dates, buy=[r for r in buy if r["amount"] > 0], sell=[r for r in sell if r["amount"] < 0],
                synced_at=db.get_setting("stock_flows_at"))


# ── 위험 지표 (미국 금융시장) ──────────────────────────────────────────
# (키, 이름, 분류, 설명, 방향) 방향 +1 = 값이 클수록 위험, -1 = 값이 작을수록 위험
RISK = [
    ("vix", "VIX (주식 변동성)", "변동성", "S&P 500 옵션에 반영된 앞으로 30일 변동성", 1),
    ("vix_term", "VIX ÷ VIX3M (기간 구조)", "변동성", "1을 넘으면 당장의 불안이 3개월 뒤보다 크다는 뜻", 1),
    ("move", "MOVE (채권 변동성)", "변동성", "미국 국채 옵션 변동성", 1),
    ("skew", "SKEW (급락 대비 수요)", "변동성", "급락에 대비한 옵션 수요. 높을수록 꼬리 위험을 의식", 1),
    ("rv", "S&P 500 실현 변동성 (20일)", "변동성", "최근 20일 실제 등락 폭을 연율로 환산", 1),
    ("hy", "하이일드 채권 상대 강도", "신용", "HYG ÷ IEF 의 60일 변화. 내리면 저신용 채권을 피한다는 뜻", -1),
    ("ig", "투자등급 채권 상대 강도", "신용", "LQD ÷ IEF 의 60일 변화", -1),
    ("bank", "지역은행 상대 강도", "신용", "KRE ÷ SPY 의 60일 변화. 내리면 은행권 불안", -1),
    ("curve", "장단기 금리차 (10년 − 3개월)", "금리·경기", "음수(역전)에 가까울수록 경기 둔화 신호", -1),
    ("y10", "10년 금리 20일 변화", "금리·경기", "금리가 빠르게 오르면 주식·채권에 부담", 1),
    ("dxy", "달러 인덱스 60일 변화", "달러·환율", "달러가 빠르게 강해지면 위험자산에 부담", 1),
    ("krw", "달러/원 60일 변화", "달러·환율", "원화 약세가 빠를수록 외국인 자금에 부담", 1),
    ("dd", "S&P 500 고점 대비 하락", "시장", "최근 1년 고점에서 얼마나 내려와 있는지", 1),
    ("sox", "반도체 지수 고점 대비 하락", "시장", "필라델피아 반도체 지수의 1년 고점 대비 하락", 1),
    ("breadth", "동일가중 상대 강도", "시장", "RSP ÷ SPY 의 60일 변화. 내리면 소수 대형주만 오르는 장", -1),
]
TICKERS = ["^VIX", "^VIX3M", "^MOVE", "^SKEW", "^GSPC", "HYG", "LQD", "IEF", "KRE", "SPY", "RSP", "^TNX", "^IRX", "DX-Y.NYB", "KRW=X", "^SOX"]
WINDOW = 756  # 약 3년


def level(score: float) -> str:
    return "안정" if score < 30 else "보통" if score < 55 else "경계" if score < 75 else "위험"


def _pct_rank(a: np.ndarray, window: int = WINDOW, tail: int = 260) -> np.ndarray:
    """끝에서 tail개 지점마다 '직전 window개 가운데 몇 %가 이 값 이하인가'를 구한다 (0~100)."""
    out = np.full(tail, np.nan)
    n = len(a)
    for k in range(tail):
        i = n - tail + k
        if i < 60:
            continue
        w = a[max(0, i - window + 1): i + 1]
        w = w[~np.isnan(w)]
        if len(w) >= 60 and not np.isnan(a[i]):
            out[k] = (w <= a[i]).mean() * 100
    return out


def _chg(a: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(a), np.nan)
    out[n:] = (a[n:] / a[:-n] - 1) * 100
    return out


async def _closes() -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """야후 5년 일봉을 S&P 500 거래일에 맞춰 정렬한다 (빈 날은 직전 값으로 채움)."""
    res = await asyncio.gather(*(yahoo.chart(t, "day", "5y", ttl=1800) for t in TICKERS), return_exceptions=True)
    series = {}
    for t, r in zip(TICKERS, res):
        if isinstance(r, Exception) or not r["candles"]:
            log.warning("risk: %s 시세 없음", t)
            continue
        series[t] = {c[0]: c[4] for c in r["candles"]}
    if "^GSPC" not in series:
        raise RuntimeError("S&P 500 시세를 받지 못했습니다")
    days = np.array(sorted(series["^GSPC"]))
    out = {}
    for t, m in series.items():
        a = np.array([m.get(d, np.nan) for d in days], dtype=float)
        for i in range(1, len(a)):  # 직전 값으로 채움
            if np.isnan(a[i]):
                a[i] = a[i - 1]
        out[t] = a
    return days, out


def _risk_series(c: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    s: dict[str, np.ndarray] = {}

    def has(*ts):
        return all(t in c for t in ts)

    if has("^VIX"):
        s["vix"] = c["^VIX"]
    if has("^VIX", "^VIX3M"):
        s["vix_term"] = c["^VIX"] / c["^VIX3M"]
    if has("^MOVE"):
        s["move"] = c["^MOVE"]
    if has("^SKEW"):
        s["skew"] = c["^SKEW"]
    g = c["^GSPC"]
    ret = np.diff(np.log(g), prepend=np.nan)
    rv = np.full(len(g), np.nan)
    for i in range(20, len(g)):
        rv[i] = np.nanstd(ret[i - 19: i + 1]) * np.sqrt(252) * 100
    s["rv"] = rv
    if has("HYG", "IEF"):
        s["hy"] = _chg(c["HYG"] / c["IEF"], 60)
    if has("LQD", "IEF"):
        s["ig"] = _chg(c["LQD"] / c["IEF"], 60)
    if has("KRE", "SPY"):
        s["bank"] = _chg(c["KRE"] / c["SPY"], 60)
    if has("^TNX", "^IRX"):
        s["curve"] = c["^TNX"] - c["^IRX"]
    if has("^TNX"):
        y = c["^TNX"]
        d = np.full(len(y), np.nan)
        d[20:] = (y[20:] - y[:-20]) * 100  # bp
        s["y10"] = d
    if has("DX-Y.NYB"):
        s["dxy"] = _chg(c["DX-Y.NYB"], 60)
    if has("KRW=X"):
        s["krw"] = _chg(c["KRW=X"], 60)
    for key, t in (("dd", "^GSPC"), ("sox", "^SOX")):
        if has(t):
            a = c[t]
            dd = np.full(len(a), np.nan)
            for i in range(len(a)):
                hi = np.nanmax(a[max(0, i - 251): i + 1])
                dd[i] = (1 - a[i] / hi) * 100
            s[key] = dd
    if has("RSP", "SPY"):
        s["breadth"] = _chg(c["RSP"] / c["SPY"], 60)
    return s


UNITS = {"vix": "", "vix_term": "배", "move": "", "skew": "", "rv": "%", "hy": "%", "ig": "%", "bank": "%", "curve": "%p",
         "y10": "bp", "dxy": "%", "krw": "%", "dd": "%", "sox": "%", "breadth": "%"}


async def risk_view() -> dict:
    hit = _cached("risk", 1800)
    if hit:
        return hit
    days, closes = await _closes()
    series = _risk_series(closes)
    tail = min(260, len(days) - 60)
    items, scores = [], {}
    for key, name, cat, desc, sign in RISK:
        a = series.get(key)
        if a is None:
            continue
        rank = _pct_rank(a, tail=tail)
        sc = rank if sign > 0 else 100 - rank
        scores[key] = sc
        cur = float(sc[-1]) if not np.isnan(sc[-1]) else None
        if cur is None:
            continue
        prev = sc[-6] if tail > 6 and not np.isnan(sc[-6]) else np.nan
        items.append(dict(key=key, name=name, category=cat, desc=desc, value=round(float(a[-1]), 3), unit=UNITS.get(key, ""),
                          score=round(cur), level=level(cur), week=None if np.isnan(prev) else round(cur - float(prev)),
                          spark=[None if np.isnan(x) else round(float(x), 3) for x in a[-120:]]))
    cats = {}
    for it in items:
        cats.setdefault(it["category"], []).append(it["key"])
    cat_hist = {cat: np.nanmean(np.vstack([scores[k] for k in keys]), axis=0) for cat, keys in cats.items()}
    comp = np.nanmean(np.vstack(list(cat_hist.values())), axis=0)
    cur = float(comp[-1])

    def diff(n):
        return round(cur - float(comp[-1 - n])) if tail > n and not np.isnan(comp[-1 - n]) else None

    out = dict(
        asof=_date(days[-1]), score=round(cur), level=level(cur), week=diff(5), month=diff(21),
        history=[dict(date=_date(d), score=None if np.isnan(v) else round(float(v), 1)) for d, v in zip(days[-tail:], comp)],
        categories=[dict(name=cat, score=round(float(h[-1])), level=level(float(h[-1])),
                         week=round(float(h[-1] - h[-6])) if tail > 6 and not np.isnan(h[-6]) else None) for cat, h in cat_hist.items()],
        items=items, count=len(items))
    return _put("risk", out)


# ── 공포·탐욕 (코스피) ─────────────────────────────────────────────────
def _universe_closes(limit: int = 400, bars: int = 780) -> tuple[np.ndarray, np.ndarray]:
    """시가총액 상위 종목의 종가 행렬 (행=거래일, 열=종목). 거래일은 코스피 지수 기준."""
    cal = [r["ts"] for r in db.q("SELECT ts FROM candles WHERE symbol='IX:KOSPI' AND tf='day' ORDER BY ts DESC LIMIT ?", (bars,))][::-1]
    syms = [r["symbol"] for r in db.q("SELECT symbol FROM instruments WHERE market IN ('KOSPI','KOSDAQ') AND kind='stock' "
                                      "AND mcap IS NOT NULL ORDER BY mcap DESC LIMIT ?", (limit,))]
    if not cal or not syms:
        return np.array(cal), np.empty((len(cal), 0))
    pos = {t: i for i, t in enumerate(cal)}
    col = {s: j for j, s in enumerate(syms)}
    m = np.full((len(cal), len(syms)), np.nan)
    ph = ",".join("?" * len(syms))
    for r in db.conn().execute(f"SELECT symbol,ts,c FROM candles WHERE tf='day' AND ts>=? AND symbol IN ({ph})", (cal[0], *syms)):
        i = pos.get(r[1])
        if i is not None:
            m[i, col[r[0]]] = r[2]
    return np.array(cal), m


def fear_greed() -> dict | None:
    hit = _cached("fng", 1800)
    if hit:
        return hit
    cal, m = _universe_closes()
    k = db.q("SELECT ts,c FROM candles WHERE symbol='IX:KOSPI' AND tf='day' ORDER BY ts")
    if len(k) < 300 or m.shape[1] < 50:
        return None
    kc = np.array([r["c"] for r in k], dtype=float)[-len(cal):]
    n = len(cal)
    tail = min(250, n - 260)
    if tail < 20:
        return None
    parts: dict[str, tuple[str, str, np.ndarray, int]] = {}
    ma125 = np.array([np.mean(kc[max(0, i - 124): i + 1]) for i in range(n)])
    parts["momentum"] = ("지수 탄력", "코스피가 125일 평균보다 얼마나 위에 있는지", (kc / ma125 - 1) * 100, 1)
    ret = np.diff(np.log(kc), prepend=np.nan)
    rv = np.array([np.nanstd(ret[i - 19: i + 1]) * np.sqrt(252) * 100 if i >= 20 else np.nan for i in range(n)])
    parts["vol"] = ("변동성", "최근 20일 등락 폭. 클수록 공포", rv, -1)
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # 상장 전이라 값이 없는 구간
        ma20 = np.full_like(m, np.nan)
        cs = np.nancumsum(np.nan_to_num(m), axis=0)
        ma20[19:] = (cs[19:] - np.vstack([np.zeros((1, m.shape[1])), cs[:-20]])) / 20
        valid = ~np.isnan(m) & ~np.isnan(ma20)
        above = np.where(valid.sum(axis=1) > 0, ((m > ma20) & valid).sum(axis=1) / np.maximum(valid.sum(axis=1), 1) * 100, np.nan)
        parts["breadth"] = ("상승 종목 폭", "시가총액 상위 종목 중 20일 평균 위에 있는 비율", above, 1)
        hl = np.full(n, np.nan)
        for i in range(250, n):
            w = m[i - 249: i + 1]
            hi, lo = np.nanmax(w, axis=0), np.nanmin(w, axis=0)
            ok = ~np.isnan(m[i])
            hl[i] = ((m[i] >= hi * 0.98) & ok).sum() / max(ok.sum(), 1) * 100 - ((m[i] <= lo * 1.02) & ok).sum() / max(ok.sum(), 1) * 100
        parts["highlow"] = ("신고가 − 신저가", "52주 고점 근처 종목 비율에서 저점 근처 비율을 뺀 값", hl, 1)
    flows = {r["date"]: r["foreigner"] for r in db.q("SELECT date,foreigner FROM flow_days WHERE market='KOSPI'")}
    f = np.array([flows.get(_date(t), np.nan) for t in cal], dtype=float)
    if (~np.isnan(f)).sum() > 200:
        f20 = np.array([np.nansum(f[i - 19: i + 1]) if i >= 20 else np.nan for i in range(n)])
        parts["foreign"] = ("외국인 수급", "외국인의 최근 20일 코스피 순매수 합계", f20, 1)
    fx = {_date(r["ts"]): r["c"] for r in db.q("SELECT ts,c FROM candles WHERE symbol='FX:USDKRW' AND tf='day'")}
    x = np.array([fx.get(_date(t), np.nan) for t in cal], dtype=float)
    if (~np.isnan(x)).sum() > 200:
        for i in range(1, n):
            if np.isnan(x[i]):
                x[i] = x[i - 1]
        parts["fx"] = ("환율", "달러/원의 20일 변화. 원화가 약해질수록 공포", _chg(x, 20), -1)
    comps, hist = [], []
    for key, (name, desc, a, sign) in parts.items():
        rank = _pct_rank(a, window=500, tail=tail)
        sc = rank if sign > 0 else 100 - rank
        if np.isnan(sc[-1]):
            continue
        hist.append(sc)
        comps.append(dict(key=key, name=name, desc=desc, value=round(float(a[-1]), 2), score=round(float(sc[-1]))))
    if not hist:
        return None
    comp = np.nanmean(np.vstack(hist), axis=0)
    cur = float(comp[-1])
    label = "극단적 공포" if cur < 20 else "공포" if cur < 40 else "중립" if cur < 60 else "탐욕" if cur < 80 else "극단적 탐욕"
    out = dict(asof=_date(cal[-1]), score=round(cur), label=label,
               week=round(cur - float(comp[-6])) if tail > 6 else None, month=round(cur - float(comp[-22])) if tail > 22 else None,
               components=comps,
               history=[dict(date=_date(t), score=None if np.isnan(v) else round(float(v), 1), close=float(c))
                        for t, v, c in zip(cal[-tail:], comp, kc[-tail:])])
    return _put("fng", out)


# ── 상대강도 (RS) ──────────────────────────────────────────────────────
def rs_rank(market: str = "KR", min_mcap: float = 1000e8, limit: int = 50) -> dict:
    """최근 1년 수익률로 줄 세운 상대강도 점수(1~99). 최근 3개월에 두 배 가중을 준다."""
    key = f"rs:{market}:{int(min_mcap)}"
    hit = _cached(key, 1800)
    if hit:
        return dict(hit, rows=hit["rows"][:limit])
    idx = "IX:SPX" if market == "US" else "IX:KOSPI"
    cal = [r["ts"] for r in db.q("SELECT ts FROM candles WHERE symbol=? AND tf='day' ORDER BY ts DESC LIMIT 275", (idx,))]
    if len(cal) < 253:
        return dict(asof=None, rows=[], total=0)
    marks = [0, 63, 126, 189, 252]
    prev = [m + 21 for m in marks if m + 21 < len(cal)]
    want = sorted({cal[m] for m in marks} | {cal[m] for m in prev})
    scope = "market IN ('NASDAQ','NYSE','AMEX')" if market == "US" else "market IN ('KOSPI','KOSDAQ') AND kind='stock'"
    info = {r["symbol"]: r for r in db.q(f"SELECT symbol,name,market,price,change_pct,mcap,high52 FROM instruments WHERE {scope} AND mcap>=?", (min_mcap,))}
    ph = ",".join("?" * len(want))
    px: dict[str, dict[int, float]] = {}
    for r in db.conn().execute(f"SELECT symbol,ts,c FROM candles WHERE tf='day' AND ts IN ({ph})", want):
        if r[0] in info:
            px.setdefault(r[0], {})[r[1]] = r[2]

    def score(off: int) -> dict[str, float]:
        out = {}
        for s, p in px.items():
            try:
                c0, c1, c2, c3, c4 = (p[cal[m + off]] for m in marks)
            except (KeyError, IndexError):
                continue
            if min(c0, c1, c2, c3, c4) <= 0:
                continue
            out[s] = 0.4 * (c0 / c1 - 1) + 0.2 * (c1 / c2 - 1) + 0.2 * (c2 / c3 - 1) + 0.2 * (c3 / c4 - 1)
        return out

    def to_rank(raw: dict[str, float]) -> dict[str, int]:
        order = sorted(raw, key=raw.get)
        n = len(order)
        return {s: max(1, min(99, round((i + 1) / n * 99))) for i, s in enumerate(order)} if n else {}

    now_raw = score(0)
    now_rank, old_rank = to_rank(now_raw), to_rank(score(21)) if len(prev) == len(marks) else {}
    rows = []
    for s, rk in now_rank.items():
        i, p = info[s], px[s]
        rows.append(dict(symbol=s, name=i["name"], market=i["market"], price=i["price"], change_pct=i["change_pct"], mcap=i["mcap"],
                         raw=now_raw[s], rs=rk, rs_prev=old_rank.get(s), r3m=round((p[cal[0]] / p[cal[63]] - 1) * 100, 1),
                         r12m=round((p[cal[0]] / p[cal[252]] - 1) * 100, 1),
                         near_high=bool(i["high52"] and i["price"] and i["price"] >= i["high52"] * 0.95)))
    rows.sort(key=lambda r: -r.pop("raw"))
    out = dict(asof=_date(cal[0]), total=len(rows), rows=rows[:200])
    _put(key, out)
    return dict(out, rows=rows[:limit])
