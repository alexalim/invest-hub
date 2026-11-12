"""모의투자 엔진. 계좌 현금은 원화로 관리하고, 미국 종목은 체결 시점 환율로 환산한다.
시장가는 현재가로 즉시 체결, 지정가는 현재가가 지정가에 닿으면 체결한다."""
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from . import db
from .providers import market

log = logging.getLogger("trading")
FEES = {"KR": 0.00015, "US": 0.001, "CR": 0.0005}   # 매수·매도 수수료율
SELL_TAX = {"KR": 0.0018}                            # 국내 주식 매도 거래세 (ETF·ETN은 면제)
MAX_ACCOUNTS = 5
MIN_COIN_ORDER = 5000   # 코인 최소 주문 금액(원). 업비트 원화 마켓 기준


def is_open(symbol: str) -> bool:
    p = symbol.split(":")[0]
    if p == "CR":
        return True
    if p == "KR":
        now = datetime.now(timezone.utc) + timedelta(hours=9)
        return now.weekday() < 5 and (8, 0) <= (now.hour, now.minute) < (20, 0)
    if p == "US":
        now = datetime.now(ZoneInfo("America/New_York"))
        return now.weekday() < 5 and (9, 30) <= (now.hour, now.minute) < (16, 0)
    return False


def _tax_rate(symbol: str) -> float:
    p = symbol.split(":")[0]
    if p == "KR" and db.val("SELECT kind FROM instruments WHERE symbol=?", (symbol,)) != "stock":
        return 0.0
    return SELL_TAX.get(p, 0.0)


def account_of(user: dict, account_id: int) -> dict:
    a = db.one("SELECT * FROM accounts WHERE id=? AND user_id=?", (account_id, user["id"]))
    if not a:
        raise HTTPException(404, "계좌를 찾을 수 없습니다")
    return a


def _reserved_cash(account_id: int, fx: float) -> float:
    total = 0.0
    for o in db.q("SELECT symbol,price,qty FROM orders WHERE account_id=? AND status='open' AND side='buy'", (account_id,)):
        rate = fx if o["symbol"].startswith("US:") else 1.0
        total += o["price"] * o["qty"] * rate * (1 + FEES[o["symbol"].split(":")[0]])
    return total


def _reserved_qty(account_id: int, symbol: str) -> float:
    return db.val("SELECT COALESCE(SUM(qty),0) FROM orders WHERE account_id=? AND symbol=? AND status='open' AND side='sell'",
                  (account_id, symbol)) or 0.0


def _fill(order: dict, price: float, fx: float):
    """체결 처리. 잔고·포지션·체결 기록을 한 트랜잭션으로 바꾼다."""
    sym, side, qty = order["symbol"], order["side"], order["qty"]
    p = sym.split(":")[0]
    rate = fx if p == "US" else 1.0
    gross = price * qty * rate
    fee = gross * FEES[p]
    with db.tx() as c:
        acc = c.execute("SELECT cash FROM accounts WHERE id=?", (order["account_id"],)).fetchone()
        pos = c.execute("SELECT qty,avg_price,cost_krw FROM positions WHERE account_id=? AND symbol=?",
                        (order["account_id"], sym)).fetchone()
        pnl = None
        if side == "buy":
            if acc["cash"] < gross + fee - 1e-6:
                c.execute("UPDATE orders SET status='rejected', note='잔고 부족' WHERE id=?", (order["id"],))
                return False
            c.execute("UPDATE accounts SET cash=cash-? WHERE id=?", (gross + fee, order["account_id"]))
            if pos:
                nq = pos["qty"] + qty
                c.execute("UPDATE positions SET qty=?, avg_price=?, cost_krw=? WHERE account_id=? AND symbol=?",
                          (nq, (pos["avg_price"] * pos["qty"] + price * qty) / nq, pos["cost_krw"] + gross + fee,
                           order["account_id"], sym))
            else:
                c.execute("INSERT INTO positions(account_id,symbol,qty,avg_price,cost_krw) VALUES(?,?,?,?,?)",
                          (order["account_id"], sym, qty, price, gross + fee))
        else:
            if not pos or pos["qty"] < qty - 1e-9:
                c.execute("UPDATE orders SET status='rejected', note='보유 수량 부족' WHERE id=?", (order["id"],))
                return False
            tax = gross * _tax_rate(sym)
            fee += tax
            cost = pos["cost_krw"] * (qty / pos["qty"])
            pnl = gross - fee - cost
            c.execute("UPDATE accounts SET cash=cash+? WHERE id=?", (gross - fee, order["account_id"]))
            left = pos["qty"] - qty
            if left <= 1e-9:
                c.execute("DELETE FROM positions WHERE account_id=? AND symbol=?", (order["account_id"], sym))
            else:
                c.execute("UPDATE positions SET qty=?, cost_krw=? WHERE account_id=? AND symbol=?",
                          (left, pos["cost_krw"] - cost, order["account_id"], sym))
        t = db.now()
        c.execute("UPDATE orders SET status='filled', fill_price=?, fee=?, filled_at=? WHERE id=?", (price, fee, t, order["id"]))
        c.execute("INSERT INTO trades(account_id,order_id,symbol,side,price,qty,amount_krw,fee,pnl,ts) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (order["account_id"], order["id"], sym, side, price, qty, gross, fee, pnl, t))
    return True


async def place(user: dict, account_id: int, symbol: str, side: str, otype: str, qty: float, price: float | None) -> dict:
    acc = account_of(user, account_id)
    p = symbol.split(":")[0]
    if p not in FEES or not market.instrument(symbol):
        raise HTTPException(400, "주문할 수 없는 종목입니다")
    if side not in ("buy", "sell") or otype not in ("market", "limit"):
        raise HTTPException(400, "주문 유형이 올바르지 않습니다")
    qty = float(qty)
    if p != "CR":
        qty = float(int(qty))
    if qty <= 0:
        raise HTTPException(400, "수량을 확인해 주세요")
    qd = await market.quote(symbol)
    if not qd or not qd.get("price"):
        raise HTTPException(503, "현재가를 가져오지 못했습니다")
    last = float(qd["price"])
    fx = await market.usdkrw() if p == "US" else 1.0
    rate = fx if p == "US" else 1.0
    open_now = is_open(symbol)
    if otype == "market":
        if not open_now:
            raise HTTPException(400, "지금은 장 운영 시간이 아닙니다. 지정가 주문은 접수할 수 있습니다")
        price = last
    else:
        if not price or price <= 0:
            raise HTTPException(400, "지정가를 입력해 주세요")
        price = float(price)
    if side == "buy":
        if p == "CR" and price * qty < MIN_COIN_ORDER:
            raise HTTPException(400, f"코인은 {MIN_COIN_ORDER:,}원 이상부터 주문할 수 있습니다")
        need = price * qty * rate * (1 + FEES[p])
        avail = acc["cash"] - _reserved_cash(account_id, fx)
        if need > avail + 1e-6:
            raise HTTPException(400, f"주문 가능 금액이 부족합니다 (가능 {avail:,.0f}원, 필요 {need:,.0f}원)")
    else:
        held = db.val("SELECT qty FROM positions WHERE account_id=? AND symbol=?", (account_id, symbol)) or 0.0
        if qty > held - _reserved_qty(account_id, symbol) + 1e-9:
            raise HTTPException(400, "매도 가능 수량이 부족합니다")
    oid = db.ex("INSERT INTO orders(account_id,symbol,side,type,price,qty,status,created_at) VALUES(?,?,?,?,?,?,'open',?)",
                (account_id, symbol, side, otype, price, qty, db.now()))
    order = db.one("SELECT * FROM orders WHERE id=?", (oid,))
    marketable = otype == "market" or (open_now and ((side == "buy" and price >= last) or (side == "sell" and price <= last)))
    if marketable:
        _fill(order, last if otype == "limit" else price, fx)
    return db.one("SELECT * FROM orders WHERE id=?", (oid,))


def cancel(user: dict, order_id: int):
    o = db.one("SELECT o.* FROM orders o JOIN accounts a ON a.id=o.account_id WHERE o.id=? AND a.user_id=?",
               (order_id, user["id"]))
    if not o or o["status"] != "open":
        raise HTTPException(400, "취소할 수 없는 주문입니다")
    db.ex("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))


async def match_open_orders() -> int:
    """미체결 지정가 주문을 현재가와 비교해 체결한다 (스케줄러가 몇 초마다 호출)."""
    orders = db.q("SELECT * FROM orders WHERE status='open'")
    orders = [o for o in orders if is_open(o["symbol"])]
    if not orders:
        return 0
    qs = await market.quotes(list({o["symbol"] for o in orders}))
    fx = await market.usdkrw() if any(o["symbol"].startswith("US:") for o in orders) else 1.0
    n = 0
    for o in orders:
        qd = qs.get(o["symbol"])
        if not qd or qd.get("stale") or not qd.get("price"):
            continue
        last = float(qd["price"])
        if (o["side"] == "buy" and last <= o["price"]) or (o["side"] == "sell" and last >= o["price"]):
            if _fill(o, o["price"], fx):
                n += 1
                uid = db.val("SELECT user_id FROM accounts WHERE id=?", (o["account_id"],))
                db.ex("INSERT INTO notifications(user_id,title,body,link,created_at) VALUES(?,?,?,?,?)",
                      (uid, "지정가 주문 체결", f"{market.name_of(o['symbol'])} {'매수' if o['side'] == 'buy' else '매도'} "
                       f"{o['qty']:g}주 @ {o['price']:,.2f}", "/trade/status", db.now()))
    return n


async def summary(account: dict) -> dict:
    pos = db.q("SELECT * FROM positions WHERE account_id=?", (account["id"],))
    syms = [p["symbol"] for p in pos]
    qs = await market.quotes(syms) if syms else {}
    fx = await market.usdkrw()
    nm = market.names(syms)
    items, stock_value = [], 0.0
    for p in pos:
        qd = qs.get(p["symbol"]) or {}
        last = float(qd.get("price") or p["avg_price"])
        rate = fx if p["symbol"].startswith("US:") else 1.0
        value = last * p["qty"] * rate
        stock_value += value
        items.append(dict(symbol=p["symbol"], name=nm.get(p["symbol"], p["symbol"]), qty=p["qty"], avg_price=p["avg_price"],
                          price=last, change_pct=qd.get("change_pct"), value_krw=value, cost_krw=p["cost_krw"],
                          pnl_krw=value - p["cost_krw"], pnl_pct=(value / p["cost_krw"] - 1) * 100 if p["cost_krw"] else 0.0,
                          currency=market.currency(p["symbol"]),
                          sellable=p["qty"] - _reserved_qty(account["id"], p["symbol"])))
    equity = account["cash"] + stock_value
    realized = db.val("SELECT COALESCE(SUM(pnl),0) FROM trades WHERE account_id=? AND pnl IS NOT NULL", (account["id"],)) or 0.0
    return dict(id=account["id"], name=account["name"], cash=account["cash"], available=account["cash"] - _reserved_cash(account["id"], fx),
                stock_value=stock_value, equity=equity, initial=account["initial_cash"], pnl=equity - account["initial_cash"],
                return_pct=(equity / account["initial_cash"] - 1) * 100, realized=realized, positions=items, usdkrw=fx)


async def snapshot_all():
    today = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d")
    for a in db.q("SELECT * FROM accounts"):
        try:
            s = await summary(a)
            db.ex("INSERT OR REPLACE INTO equity_snapshots(account_id,date,equity) VALUES(?,?,?)", (a["id"], today, s["equity"]))
        except Exception as e:
            log.warning("snapshot %s: %r", a["id"], e)


def season() -> tuple[str, str]:
    now = datetime.now(timezone.utc) + timedelta(hours=9)
    qn = (now.month - 1) // 3
    return f"{now.year}-{qn * 3 + 1:02d}-01", f"{now.year} {qn + 1}분기"


async def league() -> dict:
    start, label = season()
    rows = []
    for a in db.q("SELECT a.*, u.nickname FROM accounts a JOIN users u ON u.id=a.user_id"):
        s = await summary(a)
        base = db.val("SELECT equity FROM equity_snapshots WHERE account_id=? AND date<? ORDER BY date DESC LIMIT 1",
                      (a["id"], start)) or a["initial_cash"]
        n_trades = db.val("SELECT COUNT(*) FROM trades WHERE account_id=? AND ts>=?",
                          (a["id"], int(datetime.fromisoformat(start).timestamp()) - 9 * 3600))
        wins = db.val("SELECT COUNT(*) FROM trades WHERE account_id=? AND pnl>0", (a["id"],)) or 0
        sells = db.val("SELECT COUNT(*) FROM trades WHERE account_id=? AND pnl IS NOT NULL", (a["id"],)) or 0
        rows.append(dict(account_id=a["id"], account=a["name"], nickname=a["nickname"], user_id=a["user_id"], equity=s["equity"],
                         season_return=(s["equity"] / base - 1) * 100, total_return=s["return_pct"], trades=n_trades,
                         win_rate=round(wins / sells * 100, 1) if sells else None))
    rows.sort(key=lambda r: -r["season_return"])
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return dict(season=label, start=start, rows=rows)
