"""로그인, 검색, 시세, 알림, 관리 설정."""
import asyncio

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response

from .. import auth, db, jobs
from ..analysis import similar
from ..providers import market

router = APIRouter(prefix="/api")
SECRET_KEYS = ("dart_key", "data_go_kr_key")


def _set_session(request: Request, response: Response, user_id: int):
    # 터널·프록시를 거쳐 https 로 들어온 접속이면 쿠키가 https 로만 실리게 한다 (집 안 http 접속은 그대로)
    https = request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https"
    response.set_cookie(auth.COOKIE, auth.create_session(user_id), httponly=True, samesite="lax", secure=https, max_age=90 * 86400)


@router.get("/auth/me")
def me(request: Request):
    first = db.val("SELECT COUNT(*) FROM users") == 0
    try:
        return dict(user=auth.current_user(request), first_run=first)
    except HTTPException:
        return dict(user=None, first_run=first)


@router.post("/auth/register")
def register(request: Request, response: Response, p: dict = Body(...)):
    u = auth.register(p.get("username", ""), p.get("password", ""), p.get("nickname", ""), p.get("invite"))
    _set_session(request, response, u["id"])
    return u


@router.post("/auth/login")
def login(request: Request, response: Response, p: dict = Body(...)):
    u = auth.login(str(p.get("username", "")), str(p.get("password", "")), request.client.host if request.client else "")
    _set_session(request, response, u["id"])
    return dict(id=u["id"], username=u["username"], nickname=u["nickname"], is_admin=u["is_admin"])


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    db.ex("DELETE FROM sessions WHERE token=?", (request.cookies.get(auth.COOKIE),))
    response.delete_cookie(auth.COOKIE)
    return dict(ok=True)


@router.post("/auth/password")
def change_password(p: dict = Body(...), user=Depends(auth.current_user)):
    u = db.one("SELECT * FROM users WHERE id=?", (user["id"],))
    if not auth.check_pw(p.get("old", ""), u["pw_hash"]) or len(p.get("new", "")) < 6:
        raise HTTPException(400, "현재 비밀번호가 다르거나 새 비밀번호가 6자 미만입니다")
    db.ex("UPDATE users SET pw_hash=? WHERE id=?", (auth.hash_pw(p["new"]), user["id"]))
    return dict(ok=True)


@router.post("/auth/profile")
def profile(p: dict = Body(...), user=Depends(auth.current_user)):
    nick = (p.get("nickname") or "").strip()
    if not nick:
        raise HTTPException(400, "닉네임을 입력해 주세요")
    db.ex("UPDATE users SET nickname=? WHERE id=?", (nick[:20], user["id"]))
    return dict(ok=True)


@router.get("/search")
def search(q: str = "", limit: int = 20, user=Depends(auth.current_user)):
    return market.search(q, limit)


@router.get("/quotes")
async def quotes(symbols: str, user=Depends(auth.current_user)):
    syms = [s for s in symbols.split(",") if s][:120]
    qs = await market.quotes(syms)
    nm = market.names(syms)
    return {s: dict(q, name=nm.get(s, s)) for s, q in qs.items()}


@router.get("/notifications")
def notifications(user=Depends(auth.current_user)):
    return dict(unread=db.val("SELECT COUNT(*) FROM notifications WHERE user_id=? AND read=0", (user["id"],)),
                items=db.q("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50", (user["id"],)))


@router.post("/notifications/read")
def notifications_read(user=Depends(auth.current_user)):
    db.ex("UPDATE notifications SET read=1 WHERE user_id=?", (user["id"],))
    return dict(ok=True)


@router.get("/admin/status")
def status(user=Depends(auth.current_user)):
    counts = {k: db.val(f"SELECT COUNT(*) FROM {t}") for k, t in dict(
        instruments="instruments", candles="candles", signals="signals", articles="articles", deals="deals",
        companies="companies", investors="investors", funds="funds", grants="grants", users="users").items()}
    counts["candle_symbols"] = db.val("SELECT COUNT(*) FROM candle_sync")
    job_rows = {r["name"]: r for r in db.q("SELECT * FROM job_log")}
    out_jobs = [{**(job_rows.get(k) or {}), "name": k, "label": v[1]} for k, v in jobs.JOBS.items()]
    from .. import intraday
    return dict(counts=counts, jobs=out_jobs, similar=similar.status(), intraday=dict(intraday.status(), kis=db.get_setting("kis_minutes_progress")),
                keys={k: bool(db.get_setting(k)) for k in SECRET_KEYS},
                invite_code=db.get_setting("invite_code") if user["is_admin"] else None,
                signal_summary=db.get_setting("signal_summary"), is_admin=bool(user["is_admin"]))


@router.post("/admin/settings")
def save_settings(p: dict = Body(...), user=Depends(auth.admin_user)):
    for k in (*SECRET_KEYS, "invite_code"):
        if k in p:
            db.set_setting(k, (p[k] or "").strip() or None)
    return dict(ok=True)


@router.post("/admin/jobs/{name}")
async def run_job(name: str, user=Depends(auth.admin_user)):
    if name not in jobs.JOBS:
        raise HTTPException(404, "없는 작업입니다")
    if name == "vc_backfill":
        db.set_setting("vc_backfill_done", None)
    asyncio.create_task(jobs.run(name, jobs.JOBS[name][0]))
    return dict(started=True)


@router.get("/admin/users")
def users(user=Depends(auth.admin_user)):
    return db.q("SELECT id,username,nickname,is_admin,created_at FROM users ORDER BY id")


@router.delete("/admin/users/{uid}")
def delete_user(uid: int, user=Depends(auth.admin_user)):
    if uid == user["id"]:
        raise HTTPException(400, "자기 자신은 삭제할 수 없습니다")
    from ..maintenance import delete_user_data
    delete_user_data(uid)
    return dict(ok=True)
