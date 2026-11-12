"""국내 주식 5분봉 저장소.

- 저장: data/intraday.db, (종목, 날짜)마다 정규장(09:00~15:30) 5분봉을 float32 묶음 하나로 저장한다.
- 수집: 처음에는 야후(최근 60거래일), 이후 매일 장 마감 뒤 네이버(최근 7거래일)로 덧붙인다.
  네이버 분봉에는 넥스트레이드 시간외(15:30 이후)가 섞여 있어 정규장 시간만 남긴다.
- 대상: 최근 20일 평균 거래대금 상위 종목(기본 300) + 관심종목·백테스트 요청 종목.
"""
import asyncio
import logging
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import numpy as np

from . import db
from .providers import http, naver

log = logging.getLogger("intraday")
PATH = db.DATA_DIR / "intraday.db"
TF = "5m"
KST = timedelta(hours=9)
_local = threading.local()


def conn() -> sqlite3.Connection:
    c = getattr(_local, "c", None)
    if c is None:
        c = sqlite3.connect(PATH, timeout=30, isolation_level=None, check_same_thread=False)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("CREATE TABLE IF NOT EXISTS bars(symbol TEXT, day TEXT, n INTEGER, data BLOB, src TEXT, PRIMARY KEY(symbol, day)) WITHOUT ROWID")
        c.execute("CREATE TABLE IF NOT EXISTS empties(symbol TEXT, day TEXT, PRIMARY KEY(symbol, day)) WITHOUT ROWID")
        _local.c = c
    return c


def _pack(rows: list[tuple]) -> bytes:
    """rows: [(분(0~389), o, h, l, c, v)] → float32 묶음."""
    return np.array(rows, dtype=np.float32).tobytes()


def _session_rows(items: list[tuple]) -> dict[str, list[tuple]]:
    """(KST datetime, o,h,l,c,v) 목록 → 날짜별 정규장 봉. 시각은 09:00부터 지난 분으로 저장한다."""
    out: dict[str, list[tuple]] = {}
    for k, o, h, l, c, v in items:
        mins = (k.hour - 9) * 60 + k.minute
        if mins < 0 or mins > 390 or None in (o, h, l, c) or c <= 0:
            continue
        out.setdefault(k.strftime("%Y-%m-%d"), []).append((mins, o, h, l, c, v or 0))
    for d in out:
        out[d].sort()
    return out


def save(symbol: str, days: dict[str, list[tuple]], src: str, today: str | None = None):
    rows = []
    kis_days = {r[0] for r in conn().execute("SELECT day FROM bars WHERE symbol=? AND src='kis'", (symbol,)).fetchall()} if src != "kis" else set()
    for day, bars in days.items():
        if len(bars) < 10 or day == today or day in kis_days:   # 장중인 오늘 자료와, 이미 한투 자료가 있는 날은 건드리지 않는다
            continue
        rows.append((symbol, day, len(bars), _pack(bars), src))
    if rows:
        c = conn()
        c.execute("BEGIN")
        c.executemany("INSERT OR REPLACE INTO bars(symbol,day,n,data,src) VALUES(?,?,?,?,?)", rows)
        c.execute("COMMIT")
    return len(rows)


def _today_kst() -> str:
    k = datetime.now(timezone.utc) + KST
    # 정규장이 끝나기 전(15:35 전)이면 오늘 자료는 미완성이다
    return k.strftime("%Y-%m-%d") if (k.hour, k.minute) < (15, 35) else ""


async def fetch_yahoo(symbol: str, market: str) -> int:
    code = symbol.split(":")[1]
    tk = f"{code}.KQ" if market == "KOSDAQ" else f"{code}.KS"
    d = await http.get_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}", {"interval": "5m", "range": "60d"})
    r = ((d.get("chart") or {}).get("result") or [None])[0]
    if not r or not r.get("timestamp"):
        return 0
    q = r["indicators"]["quote"][0]
    items = [(datetime.fromtimestamp(t, timezone.utc) + KST, q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i])
             for i, t in enumerate(r["timestamp"])]
    return save(symbol, _session_rows(items), "yahoo", _today_kst())


async def fetch_naver(symbol: str) -> int:
    code = symbol.split(":")[1]
    now = datetime.now(timezone.utc) + KST
    d = await http.get_json(f"{naver.W}/chart/domestic/item/{code}/minute5",
                            {"startDateTime": (now - timedelta(days=12)).strftime("%Y%m%d0000"), "endDateTime": now.strftime("%Y%m%d2359")})
    items = []
    for x in d or []:
        s = x.get("localDateTime") or ""
        if len(s) < 12:
            continue
        k = datetime(int(s[:4]), int(s[4:6]), int(s[6:8]), int(s[8:10]), int(s[10:12]))
        items.append((k, x.get("openPrice"), x.get("highPrice"), x.get("lowPrice"), x.get("currentPrice"), x.get("accumulatedTradingVolume")))
    return save(symbol, _session_rows(items), "naver", _today_kst())


def universe(limit: int = 300) -> list[tuple[str, str]]:
    """거래대금 상위 국내 주식 (단타에는 유동성이 중요하다) + 관심종목."""
    cut = db.now() - 40 * 86400
    rows = db.q("""SELECT i.symbol, i.market FROM instruments i JOIN (SELECT symbol, AVG(c*v) val FROM candles
                   WHERE tf='day' AND ts>=? AND symbol LIKE 'KR:%' GROUP BY symbol) x ON x.symbol=i.symbol
                   WHERE i.market IN ('KOSPI','KOSDAQ') AND i.kind='stock' ORDER BY x.val DESC LIMIT ?""", (cut, limit))
    watch = db.q("""SELECT DISTINCT i.symbol, i.market FROM watch_items w JOIN instruments i ON i.symbol=w.symbol
                    WHERE i.market IN ('KOSPI','KOSDAQ')""")
    seen, out = set(), []
    for r in rows + watch:
        if r["symbol"] not in seen:
            seen.add(r["symbol"])
            out.append((r["symbol"], r["market"]))
    return out


def have_days(symbol: str) -> int:
    return conn().execute("SELECT COUNT(*) FROM bars WHERE symbol=?", (symbol,)).fetchone()[0]


async def ensure(symbol: str) -> int:
    """백테스트 요청 종목에 자료가 없으면 야후에서 60일치를 받는다."""
    if have_days(symbol) >= 20:
        return 0
    mk = db.val("SELECT market FROM instruments WHERE symbol=?", (symbol,)) or "KOSPI"
    n = await fetch_yahoo(symbol, mk)
    n += await fetch_naver(symbol)
    return n


async def sync(limit: int = 300, progress=None) -> dict:
    """처음이면 야후 60일, 아니면 네이버 최근분을 덧붙인다."""
    uni = universe(limit)
    stats = dict(symbols=len(uni), yahoo=0, naver=0, failed=0)
    for i, (s, mk) in enumerate(uni):
        try:
            if have_days(s) < 20:
                stats["yahoo"] += await fetch_yahoo(s, mk)
                await asyncio.sleep(0.25)
            stats["naver"] += await fetch_naver(s)
        except Exception as e:
            stats["failed"] += 1
            log.warning("intraday %s: %r", s, e)
        await asyncio.sleep(0.05)
    stats["days"] = conn().execute("SELECT COUNT(DISTINCT day) FROM bars").fetchone()[0]
    stats["rows"] = conn().execute("SELECT COUNT(*) FROM bars").fetchone()[0]
    db.set_setting("intraday_sync", dict(stats, at=db.now()))
    return stats


def load(symbol: str, days: int | None = None) -> dict | None:
    """연속된 5분봉 배열 + 날짜 정보. ts는 한국 시각을 UTC처럼 표기(차트 축용)."""
    rows = conn().execute("SELECT day, data FROM bars WHERE symbol=? ORDER BY day", (symbol,)).fetchall()
    if days:
        rows = rows[-days:]
    if not rows:
        return None
    parts, day_idx, day_names = [], [], []
    for k, (day, blob) in enumerate(rows):
        a = np.frombuffer(blob, dtype=np.float32).reshape(-1, 6).astype(np.float64)
        base = int(datetime.strptime(day, "%Y-%m-%d").replace(hour=9, tzinfo=timezone.utc).timestamp())
        ts = base + a[:, 0] * 60
        parts.append(np.column_stack([ts, a[:, 1:], a[:, 0]]))
        day_idx.append(np.full(len(a), k))
        day_names.append(day)
    m = np.vstack(parts)
    day = np.concatenate(day_idx)
    out = dict(ts=m[:, 0].astype(np.int64), o=m[:, 1], h=m[:, 2], l=m[:, 3], c=m[:, 4], v=m[:, 5], minute=m[:, 6].astype(int),
               day=day, days=day_names)
    # 날짜별 값: 그날 시가, 전날 마지막 봉 종가, 그날 몇 번째 봉인지
    first = np.r_[0, np.flatnonzero(np.diff(day)) + 1]
    last = np.r_[first[1:] - 1, len(day) - 1]
    out["day_open"] = out["o"][first][day]
    # 전일 종가는 정규장 공식 종가(일봉)를 쓴다. 5분봉 마지막(15:15)은 종가 단일가 전 가격이라 다르다
    daily = {datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d"): c for t, c in
             db.conn().execute("SELECT ts, c FROM candles WHERE symbol=? AND tf='day'", (symbol,)).fetchall()}
    dkeys = sorted(daily)
    import bisect
    prev = []
    for k, name in enumerate(day_names):
        j = bisect.bisect_left(dkeys, name) - 1
        prev.append(daily[dkeys[j]] if j >= 0 else (out["c"][last[k - 1]] if k else np.nan))
    out["prev_close"] = np.array(prev, dtype=np.float64)[day]
    out["bar"] = np.arange(len(day)) - first[day]
    out["first"], out["last"] = first, last
    return out


def status() -> dict:
    c = conn()
    r = c.execute("SELECT COUNT(DISTINCT symbol), COUNT(DISTINCT day), MIN(day), MAX(day), COUNT(*) FROM bars").fetchone()
    size = PATH.stat().st_size if PATH.exists() else 0
    return dict(symbols=r[0], days=r[1], first=r[2], last=r[3], rows=r[4], mb=round(size / 1e6, 1),
                sync=db.get_setting("intraday_sync"))


# ── 한국투자증권 1분봉(정규장) → 5분봉 ───────────────────────────────────
HOURS = ("153000", "132100", "112200", "092300")


def _five_minute(bars: list[dict]) -> list[tuple]:
    """1분봉(라벨=봉 시작 시각) → 5분봉. 15:30 종가 단일가 봉은 따로 남긴다 (공식 종가)."""
    buckets: dict[int, list[tuple]] = {}
    for b in bars:
        hh, mm = int(b["hour"][:2]), int(b["hour"][2:4])
        mins = (hh - 9) * 60 + mm
        if mins < 0 or mins > 390 or b["c"] <= 0:
            continue
        buckets.setdefault(390 if mins == 390 else mins // 5 * 5, []).append((mins, b))
    out = []
    for m in sorted(buckets):
        it = sorted(buckets[m], key=lambda t: t[0])
        out.append((m, it[0][1]["o"], max(x[1]["h"] for x in it), min(x[1]["l"] for x in it), it[-1][1]["c"], sum(x[1]["v"] for x in it)))
    return out


async def kis_day(code: str, day: str) -> list[dict]:
    """하루치 정규장 1분봉 (최대 4번 호출)."""
    from .broker import kis
    ymd = day.replace("-", "")
    got: dict[str, dict] = {}
    for hour in HOURS:
        rows = await kis.minute_bars("real", code, ymd, hour)
        if not rows:
            break
        for r in rows:
            if r["day"] == ymd and "090000" <= r["hour"] <= "153000":
                got[r["hour"]] = r
        if min(r["day"] + r["hour"] for r in rows) < ymd + "090100":
            break
    return sorted(got.values(), key=lambda r: r["hour"])


def trading_days(symbol: str, n: int = 252) -> list[str]:
    rows = db.conn().execute("SELECT ts FROM candles WHERE symbol=? AND tf='day' ORDER BY ts DESC LIMIT ?", (symbol, n)).fetchall()
    return [datetime.fromtimestamp(r[0], timezone.utc).strftime("%Y-%m-%d") for r in rows][::-1]


async def kis_download(limit: int = 100, days: int = 252, stop=None) -> dict:
    """거래대금 상위 limit종목의 최근 days거래일 5분봉을 한투에서 받는다.
    종목 단위로 끝까지 받고 다음 종목으로 넘어가므로 중간에 멈춰도 쓸 수 있고, 다시 돌리면 받은 날은 건너뛴다."""
    from .broker import kis
    if not kis.configured(kis.load(), "real"):
        raise kis.KisError("실전투자 키를 설정해 주세요 (과거 분봉 조회는 실전 키로만 됩니다)")
    today = _today_kst()
    uni = [s for s, _ in universe(limit)]
    prog = dict(symbols=len(uni), done_symbols=0, calls=0, days_saved=0, started=db.now())
    for si, s in enumerate(uni):
        code = s.split(":")[1]
        have = {r[0] for r in conn().execute("SELECT day FROM bars WHERE symbol=? AND src='kis'", (s,)).fetchall()}
        empty = {r[0] for r in conn().execute("SELECT day FROM empties WHERE symbol=?", (s,)).fetchall()}
        todo = [d for d in trading_days(s, days) if d not in have and d not in empty and d != today][::-1]  # 최근 날부터
        sem = asyncio.Semaphore(4)   # 동시에 4일치를 받는다 (호출 시작 간격은 kis.call이 지킨다)

        async def one(d):
            async with sem:
                if stop and stop():
                    return
                try:
                    bars = await kis_day(code, d)
                except kis.KisError as e:
                    if e.code in ("EGW00123", "EGW00121"):
                        raise
                    log.warning("kis minute %s %s: %s", s, d, e)
                    return
                prog["calls"] += 4 if len(bars) > 270 else max(1, len(bars) // 120 + 1)
                five = _five_minute(bars)
                if len(five) >= 20:
                    prog["days_saved"] += save(s, {d: five}, "kis", today)
                else:
                    conn().execute("INSERT OR IGNORE INTO empties(symbol, day) VALUES(?,?)", (s, d))

        await asyncio.gather(*(one(d) for d in todo))
        if stop and stop():
            db.set_setting("kis_minutes_progress", dict(prog, stopped=True, at=db.now()))
            return prog
        prog["done_symbols"] = si + 1
        db.set_setting("kis_minutes_progress", dict(prog, current=s, at=db.now()))
    db.set_setting("kis_minutes_progress", dict(prog, finished=True, at=db.now()))
    return prog
