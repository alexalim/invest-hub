"""차트게임. 과거 일봉의 임의 구간을 종목명·날짜를 가린 채 한 봉씩 공개하며 매매를 연습한다.
가격은 첫 봉 종가가 10,000이 되도록 환산해 종목을 짐작하기 어렵게 한다."""
import json
import random
import secrets

from fastapi import HTTPException

from . import db
from .analysis import store
from .providers import market

START_CASH = 10_000_000
HISTORY = 120
BASE_TS = 946857600  # 2000-01-03, 가짜 날짜의 시작점


def _pool(mk: str) -> list[str]:
    markets = {"KR": ("KOSPI", "KOSDAQ"), "US": ("NASDAQ", "NYSE"), "CR": ("CRYPTO",)}.get(mk, ("KOSPI", "KOSDAQ"))
    kinds = ("crypto",) if mk == "CR" else ("stock",)
    cand = market.universe(markets, limit=400, kinds=kinds)
    have = set(store.synced_symbols(HISTORY + 80))
    return [s for s in cand if s in have]


def _pick(mk: str, bars: int) -> tuple[str, int]:
    pool = _pool(mk)
    if not pool:
        raise HTTPException(503, "아직 일봉 데이터가 준비되지 않았습니다. 설정 화면에서 수집 상태를 확인해 주세요")
    for _ in range(30):
        s = random.choice(pool)
        d = store.get(s, live=False)
        n = len(d["c"])
        if n >= HISTORY + bars + 5:
            return s, random.randint(HISTORY, n - bars - 1)
    raise HTTPException(503, "게임에 쓸 구간을 찾지 못했습니다")


def start(user: dict, mk: str = "KR", bars: int = 50, code: str | None = None) -> dict:
    bars = max(20, min(120, int(bars)))
    comp_id = None
    if code:
        comp = db.one("SELECT * FROM competitions WHERE code=?", (code.strip().upper(),))
        if not comp:
            raise HTTPException(404, "대결 코드를 찾을 수 없습니다")
        if db.val("SELECT 1 FROM games WHERE user_id=? AND competition_id=?", (user["id"], comp["id"])):
            raise HTTPException(400, "이미 참가한 대결입니다")
        symbol, start_idx, bars, comp_id = comp["symbol"], comp["start_idx"], comp["bars"], comp["id"]
    else:
        symbol, start_idx = _pick(mk, bars)
    d = store.get(symbol, live=False)
    scale = 10000.0 / float(d["c"][start_idx - HISTORY])
    state = dict(cash=START_CASH, qty=0.0, avg=0.0, step=0, trades=[], scale=scale)
    gid = db.ex("INSERT INTO games(user_id,symbol,start_idx,bars,competition_id,state,created_at) VALUES(?,?,?,?,?,?,?)",
                (user["id"], symbol, start_idx, bars, comp_id, json.dumps(state), db.now()))
    return view(user, gid)


def create_competition(user: dict, mk: str = "KR", bars: int = 50) -> dict:
    bars = max(20, min(120, int(bars)))
    symbol, start_idx = _pick(mk, bars)
    code = secrets.token_hex(3).upper()
    db.ex("INSERT INTO competitions(code,creator_id,symbol,start_idx,bars,created_at) VALUES(?,?,?,?,?,?)",
          (code, user["id"], symbol, start_idx, bars, db.now()))
    return dict(code=code, bars=bars)


def _game(user: dict, gid: int) -> dict:
    g = db.one("SELECT * FROM games WHERE id=? AND user_id=?", (gid, user["id"]))
    if not g:
        raise HTTPException(404, "게임을 찾을 수 없습니다")
    g["state"] = json.loads(g["state"])
    return g


def view(user: dict, gid: int) -> dict:
    g = _game(user, gid)
    st = g["state"]
    d = store.get(g["symbol"], live=False)
    a, b = g["start_idx"] - HISTORY, g["start_idx"] + st["step"]
    sc = st["scale"]
    finished = bool(g["finished"])
    candles = []
    for i in range(a, b + 1):
        ts = int(d["ts"][i]) if finished else BASE_TS + (i - a) * 86400
        f = 1.0 if finished else sc
        candles.append([ts, round(float(d["o"][i]) * f, 2), round(float(d["h"][i]) * f, 2), round(float(d["l"][i]) * f, 2),
                        round(float(d["c"][i]) * f, 2), float(d["v"][i])])
    price = float(d["c"][b]) * sc
    equity = st["cash"] + st["qty"] * price
    out = dict(id=g["id"], bars=g["bars"], step=st["step"], finished=finished, cash=st["cash"], qty=st["qty"], avg=st["avg"],
               price=round(price, 2), equity=equity, return_pct=(equity / START_CASH - 1) * 100, start_cash=START_CASH,
               candles=candles, history=HISTORY, competition_id=g["competition_id"])
    trades = []
    for t in st["trades"]:
        i = g["start_idx"] + t["step"]
        f = 1.0 / sc if finished else 1.0
        trades.append(dict(side=t["side"], qty=t["qty"], price=round(t["price"] * f, 2),
                           ts=int(d["ts"][i]) if finished else BASE_TS + (i - a) * 86400))
    out["trades"] = trades
    if finished:
        out.update(symbol=g["symbol"], name=market.name_of(g["symbol"]), result_pct=g["result_pct"],
                   buy_hold_pct=(float(d["c"][b]) / float(d["c"][g["start_idx"]]) - 1) * 100)
    return out


def act(user: dict, gid: int, action: str, ratio: float = 1.0, count: int = 1) -> dict:
    g = _game(user, gid)
    if g["finished"]:
        raise HTTPException(400, "이미 끝난 게임입니다")
    st = g["state"]
    d = store.get(g["symbol"], live=False)
    price = float(d["c"][g["start_idx"] + st["step"]]) * st["scale"]
    ratio = max(0.0, min(1.0, float(ratio)))
    if action == "buy":
        qty = int(st["cash"] * ratio / price)
        if qty <= 0:
            raise HTTPException(400, "매수할 현금이 부족합니다")
        st["avg"] = (st["avg"] * st["qty"] + price * qty) / (st["qty"] + qty)
        st["qty"] += qty
        st["cash"] -= qty * price
        st["trades"].append(dict(step=st["step"], side="buy", price=price, qty=qty))
    elif action == "sell":
        qty = int(st["qty"] * ratio) if ratio < 1 else st["qty"]
        if qty <= 0:
            raise HTTPException(400, "매도할 수량이 없습니다")
        st["qty"] -= qty
        st["cash"] += qty * price
        if st["qty"] == 0:
            st["avg"] = 0.0
        st["trades"].append(dict(step=st["step"], side="sell", price=price, qty=qty))
    elif action == "next":
        st["step"] = min(g["bars"], st["step"] + max(1, int(count)))
    elif action == "finish":
        st["step"] = g["bars"]
    else:
        raise HTTPException(400, "알 수 없는 동작입니다")
    finished = st["step"] >= g["bars"]
    if finished:
        last = float(d["c"][g["start_idx"] + st["step"]]) * st["scale"]
        if st["qty"] > 0:
            st["trades"].append(dict(step=st["step"], side="sell", price=last, qty=st["qty"]))
            st["cash"] += st["qty"] * last
            st["qty"], st["avg"] = 0.0, 0.0
        res = (st["cash"] / START_CASH - 1) * 100
        db.ex("UPDATE games SET state=?, finished=1, result_pct=?, finished_at=? WHERE id=?", (json.dumps(st), res, db.now(), gid))
    else:
        db.ex("UPDATE games SET state=? WHERE id=?", (json.dumps(st), gid))
    return view(user, gid)


def history(user: dict, limit: int = 50) -> list[dict]:
    rows = db.q("SELECT g.id,g.symbol,g.bars,g.result_pct,g.finished,g.created_at,g.finished_at,g.competition_id,c.code "
                "FROM games g LEFT JOIN competitions c ON c.id=g.competition_id WHERE g.user_id=? ORDER BY g.id DESC LIMIT ?",
                (user["id"], limit))
    for r in rows:
        r["name"] = market.name_of(r["symbol"]) if r["finished"] else "?"
        if not r["finished"]:
            r["symbol"] = None
    return rows


def ranking() -> list[dict]:
    rows = db.q("SELECT u.id user_id,u.nickname,COUNT(*) games,AVG(g.result_pct) avg_pct,MAX(g.result_pct) best_pct,"
                "SUM(CASE WHEN g.result_pct>0 THEN 1 ELSE 0 END)*100.0/COUNT(*) win_rate "
                "FROM games g JOIN users u ON u.id=g.user_id WHERE g.finished=1 GROUP BY u.id ORDER BY avg_pct DESC")
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


def competition(user: dict, code: str) -> dict:
    comp = db.one("SELECT * FROM competitions WHERE code=?", (code.strip().upper(),))
    if not comp:
        raise HTTPException(404, "대결 코드를 찾을 수 없습니다")
    rows = db.q("SELECT g.id,g.user_id,u.nickname,g.result_pct,g.finished,g.state FROM games g JOIN users u ON u.id=g.user_id "
                "WHERE g.competition_id=? ORDER BY g.finished DESC, g.result_pct DESC", (comp["id"],))
    for r in rows:
        r["trades"] = len(json.loads(r.pop("state"))["trades"])
    mine = next((r for r in rows if r["user_id"] == user["id"]), None)
    done = bool(mine and mine["finished"])
    return dict(code=comp["code"], bars=comp["bars"], players=rows, joined=bool(mine), my_game_id=mine["id"] if mine else None,
                symbol=comp["symbol"] if done else None, name=market.name_of(comp["symbol"]) if done else None)
