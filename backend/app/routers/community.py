"""커뮤니티: 타임라인, 인사이트, 토론(투자 DB), 댓글, 좋아요, 종목예측."""
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException

from .. import auth, db
from ..providers import market

router = APIRouter(prefix="/api/community")
U = Depends(auth.current_user)
KINDS = ("timeline", "insight", "discussion")


def _decorate(rows: list[dict], user: dict) -> list[dict]:
    for r in rows:
        r["symbols"] = json.loads(r.get("symbols") or "[]")
        r["symbol_names"] = market.names(r["symbols"])
        r["likes"] = db.val("SELECT COUNT(*) FROM post_likes WHERE post_id=?", (r["id"],))
        r["liked"] = bool(db.val("SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?", (r["id"], user["id"])))
        r["comments"] = db.val("SELECT COUNT(*) FROM comments WHERE post_id=?", (r["id"],))
        r["mine"] = r["user_id"] == user["id"]
    return rows


@router.get("/posts")
def posts(kind: str = "timeline", symbol: str = "", page: int = 1, user=U):
    where, params = ["p.kind=?"], [kind if kind in KINDS else "timeline"]
    if symbol:
        where.append("p.symbols LIKE ?")
        params.append(f'%"{symbol}"%')
    rows = db.q("SELECT p.*, u.nickname FROM posts p JOIN users u ON u.id=p.user_id "
                f"WHERE {' AND '.join(where)} ORDER BY p.id DESC LIMIT 30 OFFSET ?", (*params, (page - 1) * 30))
    return _decorate(rows, user)


@router.get("/posts/{pid}")
def post(pid: int, user=U):
    rows = db.q("SELECT p.*, u.nickname FROM posts p JOIN users u ON u.id=p.user_id WHERE p.id=?", (pid,))
    if not rows:
        raise HTTPException(404, "글을 찾을 수 없습니다")
    out = _decorate(rows, user)[0]
    out["comment_list"] = db.q("SELECT c.*, u.nickname FROM comments c JOIN users u ON u.id=c.user_id WHERE c.post_id=? ORDER BY c.id", (pid,))
    for c in out["comment_list"]:
        c["mine"] = c["user_id"] == user["id"]
    return out


@router.post("/posts")
def post_save(p: dict = Body(...), user=U):
    body = (p.get("body") or "").strip()
    kind = p.get("kind") if p.get("kind") in KINDS else "timeline"
    if not body:
        raise HTTPException(400, "내용을 입력해 주세요")
    if len(body) > 20000:
        raise HTTPException(400, "글이 너무 깁니다 (2만 자까지)")
    if kind != "timeline" and not (p.get("title") or "").strip():
        raise HTTPException(400, "제목을 입력해 주세요")
    syms = json.dumps([s for s in (p.get("symbols") or []) if isinstance(s, str)][:10])
    if p.get("id"):
        db.ex("UPDATE posts SET title=?, body=?, symbols=?, updated_at=? WHERE id=? AND user_id=?",
              ((p.get("title") or "")[:120], body, syms, db.now(), p["id"], user["id"]))
        return dict(id=p["id"])
    return dict(id=db.ex("INSERT INTO posts(user_id,kind,title,body,symbols,created_at) VALUES(?,?,?,?,?,?)",
                         (user["id"], kind, (p.get("title") or "")[:120], body, syms, db.now())))


@router.delete("/posts/{pid}")
def post_delete(pid: int, user=U):
    owner = db.val("SELECT user_id FROM posts WHERE id=?", (pid,))
    if owner != user["id"] and not user["is_admin"]:
        raise HTTPException(403, "삭제 권한이 없습니다")
    db.ex("DELETE FROM posts WHERE id=?", (pid,))
    db.ex("DELETE FROM comments WHERE post_id=?", (pid,))
    db.ex("DELETE FROM post_likes WHERE post_id=?", (pid,))
    return dict(ok=True)


@router.post("/posts/{pid}/like")
def like(pid: int, user=U):
    if db.val("SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?", (pid, user["id"])):
        db.ex("DELETE FROM post_likes WHERE post_id=? AND user_id=?", (pid, user["id"]))
    else:
        db.ex("INSERT INTO post_likes(post_id,user_id) VALUES(?,?)", (pid, user["id"]))
    return dict(likes=db.val("SELECT COUNT(*) FROM post_likes WHERE post_id=?", (pid,)))


@router.post("/posts/{pid}/comments")
def comment(pid: int, p: dict = Body(...), user=U):
    body = (p.get("body") or "").strip()
    if not body:
        raise HTTPException(400, "내용을 입력해 주세요")
    cid = db.ex("INSERT INTO comments(post_id,user_id,body,created_at) VALUES(?,?,?,?)", (pid, user["id"], body, db.now()))
    owner = db.val("SELECT user_id FROM posts WHERE id=?", (pid,))
    if owner and owner != user["id"]:
        db.ex("INSERT INTO notifications(user_id,title,body,link,created_at) VALUES(?,?,?,?,?)",
              (owner, "새 댓글", f"{user['nickname']}: {body[:60]}", f"/community/post/{pid}", db.now()))
    return dict(id=cid)


@router.delete("/comments/{cid}")
def comment_delete(cid: int, user=U):
    db.ex("DELETE FROM comments WHERE id=? AND (user_id=? OR ?=1)", (cid, user["id"], user["is_admin"]))
    return dict(ok=True)


# ── 종목예측 ───────────────────────────────────────────────────────────
@router.get("/predictions")
def predictions(symbol: str = "", user=U):
    where, params = "", []
    if symbol:
        where, params = "WHERE p.symbol=?", [symbol]
    rows = db.q(f"SELECT p.*, u.nickname FROM predictions p JOIN users u ON u.id=p.user_id {where} ORDER BY p.id DESC LIMIT 200", params)
    nm = market.names(list({r["symbol"] for r in rows}))
    for r in rows:
        r["name"] = nm.get(r["symbol"], r["symbol"])
        r["mine"] = r["user_id"] == user["id"]
    board = db.q("SELECT u.id user_id,u.nickname,COUNT(*) total,SUM(p.result='hit') hits,"
                 "SUM(p.result='hit')*100.0/COUNT(*) rate FROM predictions p JOIN users u ON u.id=p.user_id "
                 "WHERE p.result IS NOT NULL GROUP BY u.id ORDER BY rate DESC, total DESC")
    return dict(rows=rows, board=board)


@router.post("/predictions")
async def predict(p: dict = Body(...), user=U):
    symbol, direction = p.get("symbol"), p.get("direction")
    days = int(p.get("days") or 5)
    if direction not in ("up", "down") or days not in (1, 5, 10, 20):
        raise HTTPException(400, "방향과 기간을 확인해 주세요")
    qd = await market.quote(symbol or "")
    if not qd or qd.get("price") is None:
        raise HTTPException(400, "종목 시세를 가져오지 못했습니다")
    target = datetime.now(timezone.utc) + timedelta(hours=9)
    left = days
    while left > 0:  # 영업일 기준으로 만기를 잡는다 (코인은 달력일)
        target += timedelta(days=1)
        if symbol.startswith("CR:") or target.weekday() < 5:
            left -= 1
    return dict(id=db.ex("INSERT INTO predictions(user_id,symbol,direction,base_price,days,target_date,comment,created_at) "
                         "VALUES(?,?,?,?,?,?,?,?)", (user["id"], symbol, direction, float(qd["price"]), days,
                                                      target.strftime("%Y-%m-%d"), (p.get("comment") or "")[:200], db.now())))


@router.delete("/predictions/{pid}")
def prediction_delete(pid: int, user=U):
    db.ex("DELETE FROM predictions WHERE id=? AND user_id=? AND result IS NULL", (pid, user["id"]))
    return dict(ok=True)
