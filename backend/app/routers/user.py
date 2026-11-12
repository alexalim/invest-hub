"""관심종목과 알림 설정."""
import json

from fastapi import APIRouter, Body, Depends, HTTPException

from .. import auth, db
from ..analysis import indicators as ind
from ..providers import market

router = APIRouter(prefix="/api/user")
U = Depends(auth.current_user)


@router.get("/watchlist")
async def watchlist(user=U):
    groups = db.q("SELECT id,name FROM watch_groups WHERE user_id=? ORDER BY sort,id", (user["id"],))
    items = db.q("SELECT w.group_id,w.symbol FROM watch_items w JOIN watch_groups g ON g.id=w.group_id WHERE g.user_id=? "
                 "ORDER BY w.sort,w.rowid", (user["id"],))
    syms = list({i["symbol"] for i in items})
    qs = await market.quotes(syms) if syms else {}
    nm = market.names(syms)
    memos = {m["symbol"]: m["body"] for m in db.q("SELECT symbol,body FROM memos WHERE user_id=?", (user["id"],))}
    for g in groups:
        g["items"] = [dict(symbol=i["symbol"], name=nm.get(i["symbol"], i["symbol"]), memo=memos.get(i["symbol"]),
                           currency=market.currency(i["symbol"]), **{k: (qs.get(i["symbol"]) or {}).get(k)
                                                                    for k in ("price", "change", "change_pct", "volume")})
                      for i in items if i["group_id"] == g["id"]]
    return groups


@router.post("/watchlist/groups")
def group_create(p: dict = Body(...), user=U):
    name = (p.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "그룹 이름을 입력해 주세요")
    return dict(id=db.ex("INSERT INTO watch_groups(user_id,name,sort) VALUES(?,?,?)", (user["id"], name[:20], db.now())))


@router.put("/watchlist/groups/{gid}")
def group_rename(gid: int, p: dict = Body(...), user=U):
    db.ex("UPDATE watch_groups SET name=? WHERE id=? AND user_id=?", ((p.get("name") or "")[:20], gid, user["id"]))
    return dict(ok=True)


@router.delete("/watchlist/groups/{gid}")
def group_delete(gid: int, user=U):
    if db.val("SELECT COUNT(*) FROM watch_groups WHERE user_id=?", (user["id"],)) <= 1:
        raise HTTPException(400, "마지막 그룹은 삭제할 수 없습니다")
    if db.val("SELECT 1 FROM watch_groups WHERE id=? AND user_id=?", (gid, user["id"])):
        db.ex("DELETE FROM watch_items WHERE group_id=?", (gid,))
        db.ex("DELETE FROM watch_groups WHERE id=?", (gid,))
    return dict(ok=True)


@router.post("/watchlist/toggle")
def toggle(p: dict = Body(...), user=U):
    symbol = p.get("symbol")
    if not symbol or not market.instrument(symbol):
        raise HTTPException(400, "종목을 찾을 수 없습니다")
    gid = p.get("group_id") or db.val("SELECT id FROM watch_groups WHERE user_id=? ORDER BY sort,id LIMIT 1", (user["id"],))
    if not db.val("SELECT 1 FROM watch_groups WHERE id=? AND user_id=?", (gid, user["id"])):
        raise HTTPException(404, "그룹을 찾을 수 없습니다")
    if db.val("SELECT 1 FROM watch_items WHERE group_id=? AND symbol=?", (gid, symbol)):
        db.ex("DELETE FROM watch_items WHERE group_id=? AND symbol=?", (gid, symbol))
        return dict(watched=False)
    db.ex("INSERT INTO watch_items(group_id,symbol,sort) VALUES(?,?,?)", (gid, symbol, db.now()))
    return dict(watched=True)


@router.get("/alerts")
def alerts(user=U):
    rows = db.q("SELECT * FROM alerts WHERE user_id=? ORDER BY active DESC, id DESC", (user["id"],))
    nm = market.names(list({r["symbol"] for r in rows}))
    for r in rows:
        r["params"] = json.loads(r["params"] or "{}")
        r["name"] = nm.get(r["symbol"], r["symbol"])
        if r["kind"] == "condition":
            r["desc"] = " · ".join(ind.describe_cond(c) for c in r["params"].get("conds") or [])
    return rows


def _check_conds(conds):
    """저장하기 전에 조건식을 가짜 시세에 한 번 돌려 본다. 잘못된 지표·연산자는 여기서 걸러진다."""
    import numpy as np
    x = np.linspace(100.0, 130.0, 300)
    d = dict(ts=np.arange(300, dtype=np.int64) * 86400, o=x, h=x + 1, l=x - 1, c=x, v=np.full(300, 1000.0))
    try:
        if not isinstance(conds, list) or len(conds) > 10:
            raise ValueError("조건은 10개까지 넣을 수 있습니다")
        ind.evaluate_all(d, conds)
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as e:
        raise HTTPException(400, f"조건식 오류: {e}")


@router.post("/alerts")
def alert_create(p: dict = Body(...), user=U):
    kind, symbol, params = p.get("kind"), p.get("symbol"), p.get("params") or {}
    if kind not in ("price_above", "price_below", "change_above", "change_below", "condition") or not market.instrument(symbol or ""):
        raise HTTPException(400, "알림 조건을 확인해 주세요")
    try:
        if kind.startswith("price"):
            params = dict(price=float(params["price"]))
        elif kind.startswith("change"):
            params = dict(pct=float(params["pct"]))
        elif not params.get("conds"):
            raise KeyError("conds")
        else:
            _check_conds(params["conds"])
    except HTTPException:
        raise
    except (KeyError, ValueError, TypeError):
        raise HTTPException(400, "알림 값이 비어 있거나 숫자가 아닙니다")
    return dict(id=db.ex("INSERT INTO alerts(user_id,symbol,kind,params,note,active,repeat,created_at) VALUES(?,?,?,?,?,1,?,?)",
                         (user["id"], symbol, kind, json.dumps(params), (p.get("note") or "")[:100],
                          1 if p.get("repeat") else 0, db.now())))


@router.put("/alerts/{aid}")
def alert_toggle(aid: int, p: dict = Body(...), user=U):
    db.ex("UPDATE alerts SET active=?, triggered_at=NULL WHERE id=? AND user_id=?", (1 if p.get("active") else 0, aid, user["id"]))
    return dict(ok=True)


@router.delete("/alerts/{aid}")
def alert_delete(aid: int, user=U):
    db.ex("DELETE FROM alerts WHERE id=? AND user_id=?", (aid, user["id"]))
    return dict(ok=True)


@router.get("/menu")
def get_menu(user=U):
    v = db.val("SELECT spec FROM saved_specs WHERE user_id=? AND kind='menu'", (user["id"],))
    return json.loads(v) if v else []


@router.put("/menu")
def put_menu(p: list = Body(...), user=U):
    items = [x for x in p if isinstance(x, str) and x.startswith("/")][:30]
    if db.val("SELECT 1 FROM saved_specs WHERE user_id=? AND kind='menu'", (user["id"],)):
        db.ex("UPDATE saved_specs SET spec=?, updated_at=? WHERE user_id=? AND kind='menu'", (json.dumps(items), db.now(), user["id"]))
    else:
        db.ex("INSERT INTO saved_specs(user_id,kind,name,spec,updated_at) VALUES(?, 'menu', '내 메뉴', ?, ?)", (user["id"], json.dumps(items), db.now()))
    return items
