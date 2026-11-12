"""일봉 메모리 캐시. 분석 기능이 종목 수천 개를 반복해서 읽기 때문에 DB 조회를 줄인다.
장중에는 저장된 마지막 봉 뒤에 현재가로 만든 임시 봉을 붙여 조건식이 오늘 가격을 반영하게 한다."""
import json
from datetime import datetime, timezone

import numpy as np

from .. import db

_cache: dict[str, tuple[int, dict]] = {}


def _load(symbol: str) -> dict | None:
    rows = db.conn().execute("SELECT ts,o,h,l,c,v FROM candles WHERE symbol=? AND tf='day' ORDER BY ts", (symbol,)).fetchall()
    if len(rows) < 2:
        return None
    a = np.array([tuple(r) for r in rows], dtype=np.float64)
    return dict(ts=a[:, 0].astype(np.int64), o=a[:, 1], h=a[:, 2], l=a[:, 3], c=a[:, 4], v=a[:, 5])


def get(symbol: str, live: bool = True) -> dict | None:
    synced = db.val("SELECT synced_at FROM candle_sync WHERE symbol=? AND tf='day'", (symbol,))
    if synced is None:
        return None
    hit = _cache.get(symbol)
    if hit is None or hit[0] != synced:
        d = _load(symbol)
        if d is None:
            return None
        _cache[symbol] = (synced, d)
        hit = _cache[symbol]
    d = hit[1]
    return _with_live(symbol, d) if live else d


def _with_live(symbol: str, d: dict) -> dict:
    row = db.one("SELECT price,open,high,low,volume,extra,market FROM instruments WHERE symbol=?", (symbol,))
    if not row or row["price"] is None:
        return d
    traded = json.loads(row["extra"] or "{}").get("traded")
    if not traded:
        return d
    y, m, dd = (int(x) for x in traded.split("-"))
    ts = int(datetime(y, m, dd, tzinfo=timezone.utc).timestamp())
    last = int(d["ts"][-1])
    p = float(row["price"])
    if ts < last:
        return d
    if ts == last:
        out = {k: v.copy() for k, v in d.items()}
        out["c"][-1] = p
        out["h"][-1] = max(out["h"][-1], p)
        out["l"][-1] = min(out["l"][-1], p)
        return out
    o = float(row["open"] or p)
    bar = dict(ts=ts, o=o, h=max(float(row["high"] or p), p, o), l=min(float(row["low"] or p), p, o), c=p,
               v=float(row["volume"] or 0))
    return {k: np.append(v, bar[k]).astype(v.dtype) for k, v in d.items()}


def tail(d: dict, n: int) -> dict:
    return {k: v[-n:] for k, v in d.items()}


def synced_symbols(min_bars: int = 120) -> list[str]:
    return [r["symbol"] for r in db.q(
        "SELECT symbol FROM candles WHERE tf='day' GROUP BY symbol HAVING COUNT(*)>=?", (min_bars,))]


def clear():
    _cache.clear()
