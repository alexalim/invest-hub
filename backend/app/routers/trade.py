"""트레이딩: 모의계좌, 주문, 투자현황, 투자리그, 매매일지, 차트게임."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException

from .. import auth, db, game, trading
from ..providers import market

router = APIRouter(prefix="/api/trade")
U = Depends(auth.current_user)


@router.get("/accounts")
async def accounts(user=U):
    return [await trading.summary(a) for a in db.q("SELECT * FROM accounts WHERE user_id=? ORDER BY id", (user["id"],))]


@router.post("/accounts")
def create_account(p: dict = Body(...), user=U):
    if db.val("SELECT COUNT(*) FROM accounts WHERE user_id=?", (user["id"],)) >= trading.MAX_ACCOUNTS:
        raise HTTPException(400, f"계좌는 {trading.MAX_ACCOUNTS}개까지 만들 수 있습니다")
    cash = float(p.get("cash") or 1e8)
    if not 1e6 <= cash <= 1e11:
        raise HTTPException(400, "시작 금액은 100만 원에서 1,000억 원 사이로 정해 주세요")
    name = (p.get("name") or "").strip() or "모의계좌"
    return dict(id=db.ex("INSERT INTO accounts(user_id,name,initial_cash,cash,created_at) VALUES(?,?,?,?,?)",
                         (user["id"], name[:20], cash, cash, db.now())))


@router.post("/accounts/{aid}/reset")
def reset_account(aid: int, user=U):
    a = trading.account_of(user, aid)
    with db.tx() as c:
        for t in ("positions", "orders", "trades", "equity_snapshots"):
            c.execute(f"DELETE FROM {t} WHERE account_id=?", (aid,))
        c.execute("UPDATE accounts SET cash=initial_cash, created_at=? WHERE id=?", (db.now(), aid))
    return dict(ok=True, cash=a["initial_cash"])


@router.delete("/accounts/{aid}")
def delete_account(aid: int, user=U):
    trading.account_of(user, aid)
    if db.val("SELECT COUNT(*) FROM accounts WHERE user_id=?", (user["id"],)) <= 1:
        raise HTTPException(400, "마지막 계좌는 삭제할 수 없습니다")
    with db.tx() as c:
        for t in ("positions", "orders", "trades", "equity_snapshots"):
            c.execute(f"DELETE FROM {t} WHERE account_id=?", (aid,))
        c.execute("DELETE FROM accounts WHERE id=?", (aid,))
    return dict(ok=True)


@router.get("/accounts/{aid}")
async def account(aid: int, user=U):
    a = trading.account_of(user, aid)
    s = await trading.summary(a)
    orders = db.q("SELECT * FROM orders WHERE account_id=? ORDER BY id DESC LIMIT 100", (aid,))
    trades = db.q("SELECT * FROM trades WHERE account_id=? ORDER BY id DESC LIMIT 200", (aid,))
    nm = market.names(list({o["symbol"] for o in orders} | {t["symbol"] for t in trades}))
    for r in (*orders, *trades):
        r["name"] = nm.get(r["symbol"], r["symbol"])
    s.update(orders=orders, trades=trades,
             equity_curve=db.q("SELECT date,equity FROM equity_snapshots WHERE account_id=? ORDER BY date", (aid,)))
    return s


@router.post("/orders")
async def place_order(p: dict = Body(...), user=U):
    return await trading.place(user, int(p.get("account_id") or 0), p.get("symbol", ""), p.get("side", ""),
                               p.get("type", "market"), p.get("qty") or 0, p.get("price"))


@router.delete("/orders/{oid}")
def cancel_order(oid: int, user=U):
    trading.cancel(user, oid)
    return dict(ok=True)


@router.get("/tradable/{symbol}")
async def tradable(symbol: str, account_id: int, user=U):
    """주문 화면용: 현재가, 주문 가능 금액·수량, 장 운영 여부."""
    a = trading.account_of(user, account_id)
    qd = await market.quote(symbol) or {}
    p = symbol.split(":")[0]
    fx = await market.usdkrw() if p == "US" else 1.0
    avail = a["cash"] - trading._reserved_cash(account_id, fx)
    held = db.one("SELECT qty,avg_price FROM positions WHERE account_id=? AND symbol=?", (account_id, symbol)) or dict(qty=0, avg_price=0)
    price = qd.get("price")
    max_buy = 0
    if price and p in trading.FEES:
        max_buy = avail / (price * fx * (1 + trading.FEES[p]))
        max_buy = max_buy if p == "CR" else int(max_buy)
    return dict(price=price, open=trading.is_open(symbol), available=avail, fx=fx, max_buy=max_buy, held=held["qty"],
                avg_price=held["avg_price"], sellable=held["qty"] - trading._reserved_qty(account_id, symbol),
                currency=market.currency(symbol), fee_rate=trading.FEES.get(p), tax_rate=trading._tax_rate(symbol))


@router.get("/league")
async def league(user=U):
    return await trading.league()


# ── 매매일지 ───────────────────────────────────────────────────────────
@router.get("/journal")
def journal(user=U):
    """체결 내역에 메모를 붙인 일지 + 직접 쓴 일지. 요약 통계 포함."""
    trades = db.q("SELECT t.*, a.name account FROM trades t JOIN accounts a ON a.id=t.account_id WHERE a.user_id=? "
                  "ORDER BY t.ts DESC LIMIT 500", (user["id"],))
    notes = {j["trade_id"]: j for j in db.q("SELECT * FROM journal WHERE user_id=? AND trade_id IS NOT NULL", (user["id"],))}
    nm = market.names(list({t["symbol"] for t in trades}))
    for t in trades:
        t["name"] = nm.get(t["symbol"], t["symbol"])
        t["note"] = notes.get(t["id"])
    free = db.q("SELECT * FROM journal WHERE user_id=? AND trade_id IS NULL ORDER BY date DESC, id DESC", (user["id"],))
    sells = [t for t in trades if t["pnl"] is not None]
    wins = [t for t in sells if t["pnl"] > 0]
    by_day: dict[str, float] = {}
    for t in sells:
        day = (datetime.fromtimestamp(t["ts"], timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d")
        by_day[day] = by_day.get(day, 0) + t["pnl"]
    stats = dict(trades=len(trades), closed=len(sells), win_rate=round(len(wins) / len(sells) * 100, 1) if sells else None,
                 realized=sum(t["pnl"] for t in sells), avg_win=sum(t["pnl"] for t in wins) / len(wins) if wins else None,
                 avg_loss=(sum(t["pnl"] for t in sells if t["pnl"] <= 0) / (len(sells) - len(wins))) if len(sells) > len(wins) else None,
                 fees=sum(t["fee"] or 0 for t in trades))
    return dict(trades=trades, entries=free, stats=stats, by_day=[dict(date=k, pnl=v) for k, v in sorted(by_day.items())])


@router.post("/journal")
def journal_save(p: dict = Body(...), user=U):
    fields = (p.get("symbol"), p.get("date") or datetime.now().strftime("%Y-%m-%d"), p.get("side"), p.get("price"), p.get("qty"),
              p.get("pnl"), (p.get("title") or "")[:100], p.get("body") or "", p.get("tags") or "", p.get("emotion") or "")
    if p.get("trade_id"):
        if not db.val("SELECT 1 FROM trades t JOIN accounts a ON a.id=t.account_id WHERE t.id=? AND a.user_id=?",
                      (p["trade_id"], user["id"])):
            raise HTTPException(404, "체결 내역을 찾을 수 없습니다")
        ex = db.val("SELECT id FROM journal WHERE user_id=? AND trade_id=?", (user["id"], p["trade_id"]))
        if ex:
            db.ex("UPDATE journal SET title=?, body=?, tags=?, emotion=? WHERE id=?", (*fields[6:], ex))
            return dict(id=ex)
    elif p.get("id"):
        db.ex("UPDATE journal SET symbol=?,date=?,side=?,price=?,qty=?,pnl=?,title=?,body=?,tags=?,emotion=? WHERE id=? AND user_id=?",
              (*fields, p["id"], user["id"]))
        return dict(id=p["id"])
    return dict(id=db.ex("INSERT INTO journal(user_id,trade_id,symbol,date,side,price,qty,pnl,title,body,tags,emotion,created_at) "
                         "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (user["id"], p.get("trade_id"), *fields, db.now())))


@router.delete("/journal/{jid}")
def journal_delete(jid: int, user=U):
    db.ex("DELETE FROM journal WHERE id=? AND user_id=?", (jid, user["id"]))
    return dict(ok=True)


# ── 차트게임 ───────────────────────────────────────────────────────────
@router.post("/game")
def game_start(p: dict = Body(default={}), user=U):
    return game.start(user, p.get("market", "KR"), p.get("bars", 50), p.get("code"))


@router.get("/game")
def game_list(user=U):
    return dict(history=game.history(user), ranking=game.ranking())


@router.post("/game/competition")
def game_competition(p: dict = Body(default={}), user=U):
    return game.create_competition(user, p.get("market", "KR"), p.get("bars", 50))


@router.get("/game/competition/{code}")
def game_competition_view(code: str, user=U):
    return game.competition(user, code)


@router.get("/game/{gid}")
def game_view(gid: int, user=U):
    return game.view(user, gid)


@router.post("/game/{gid}")
def game_act(gid: int, p: dict = Body(...), user=U):
    return game.act(user, gid, p.get("action", ""), p.get("ratio", 1.0), p.get("count", 1))
