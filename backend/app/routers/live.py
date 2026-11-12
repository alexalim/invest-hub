"""실계좌 주문 (한국투자증권). 관리자만, 서버에서 강제한다.

주문 흐름: 잠금 해제(비밀번호 재입력, 10분) → 미리보기(한도 검사, 확인 코드 발급 45초) → 확정(확인 코드 1회용)
모의 투자 앱(trading.py)의 계좌·체결 로직과 섞지 않는다. 잔고·체결의 기준은 증권사다."""
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from .. import auth, db
from ..broker import kis
from ..providers import market

log = logging.getLogger("live")
router = APIRouter(prefix="/api/live")
UNLOCK_SECONDS = 600
CONFIRM_SECONDS = 45
_unlocked: dict[str, float] = {}     # 세션 토큰 → 만료 시각
_confirms: dict[str, dict] = {}      # 확인 코드 → 주문 내용


def admin(request: Request, user: dict = Depends(auth.admin_user)) -> dict:
    # 다른 사이트에서 보낸 요청 차단: Origin이 있으면 접속 주소와 같아야 한다
    origin = request.headers.get("origin")
    if request.method != "GET" and origin and origin.split("://", 1)[-1] != request.headers.get("host"):
        raise HTTPException(403, "허용되지 않은 출처의 요청입니다")
    return user


def _session(request: Request) -> str:
    return request.cookies.get(auth.COOKIE) or ""


def _require_unlock(request: Request):
    if _unlocked.get(_session(request), 0) < time.time():
        raise HTTPException(423, "실계좌 잠금 상태입니다. 비밀번호로 잠금을 풀어 주세요")


def _today_start() -> int:
    kst = datetime.now(timezone.utc) + timedelta(hours=9)
    return int(datetime(kst.year, kst.month, kst.day, tzinfo=timezone.utc).timestamp()) - 9 * 3600


def _usage(env: str) -> dict:
    r = db.one("SELECT COUNT(*) n, COALESCE(SUM(est_amount),0) amt FROM live_orders WHERE env=? AND created_at>=? "
               "AND status IN ('sending','accepted','filled','partial','unknown')", (env, _today_start()))
    return dict(count=r["n"], amount=r["amt"])


@router.get("/status")
def status(request: Request, user=Depends(admin)):
    cfg = kis.load()
    exp = _unlocked.get(_session(request), 0)
    return dict(**kis.public_status(cfg), unlocked_until=int(exp) if exp > time.time() else None,
                usage={e: _usage(e) for e in kis.HOSTS})


@router.post("/unlock")
def unlock(request: Request, p: dict = Body(...), user=Depends(admin)):
    u = db.one("SELECT pw_hash FROM users WHERE id=?", (user["id"],))
    if not auth.check_pw(p.get("password", ""), u["pw_hash"]):
        raise HTTPException(401, "비밀번호가 올바르지 않습니다")
    _unlocked[_session(request)] = time.time() + UNLOCK_SECONDS
    return dict(unlocked_until=int(time.time() + UNLOCK_SECONDS))


@router.post("/lock")
def lock(request: Request, user=Depends(admin)):
    _unlocked.pop(_session(request), None)
    return dict(ok=True)


@router.post("/config")
def config(request: Request, p: dict = Body(...), user=Depends(admin)):
    """키·계좌 저장(값은 다시 보여 주지 않음), 한도, 실행 스위치, 모의/실전 전환."""
    cfg = kis.load()
    env = p.get("env")
    if env in kis.HOSTS and p.get("keys"):
        k = p["keys"]
        cano, prdt = str(k.get("cano", "")).replace("-", "").strip(), str(k.get("prdt", "01")).strip()
        if not (len(cano) == 8 and cano.isdigit() and len(prdt) == 2 and prdt.isdigit()):
            raise HTTPException(400, "계좌번호는 앞 8자리와 뒤 2자리 숫자로 입력해 주세요")
        if not k.get("app_key") or not k.get("app_secret"):
            raise HTTPException(400, "앱키와 앱시크릿을 모두 입력해 주세요")
        if env == "real":
            _require_unlock(request)
        cfg[env] = dict(app_key=k["app_key"].strip(), app_secret=k["app_secret"].strip(), cano=cano, prdt=prdt)
    if p.get("clear_env") in kis.HOSTS:
        cfg[p["clear_env"]] = {}
    if "limits" in p:
        lim = p["limits"]
        for key in ("per_order_krw", "daily_krw", "daily_count"):
            if key in lim:
                v = float(lim[key])
                if v <= 0:
                    raise HTTPException(400, "한도는 0보다 커야 합니다")
                cfg["limits"][key] = int(v)
    if "enabled" in p:
        cfg["enabled"] = bool(p["enabled"])
    if "mode" in p:
        if p["mode"] not in kis.HOSTS:
            raise HTTPException(400, "모드는 demo 또는 real입니다")
        if p["mode"] == "real":
            _require_unlock(request)
            if not kis.configured(cfg, "real"):
                raise HTTPException(400, "실전투자 키와 계좌번호를 먼저 저장해 주세요")
        cfg["mode"] = p["mode"]
    kis.save(cfg)
    return kis.public_status(cfg)


def _kis_error(e: kis.KisError):
    raise HTTPException(502, f"증권사: {e}" + (f" [{e.code}]" if e.code else ""))


@router.get("/balance")
async def balance(request: Request, user=Depends(admin)):
    env = kis.load()["mode"]
    try:
        b = await kis.balance(env)
    except kis.KisError as e:
        _kis_error(e)
    return dict(env=env, **b)


@router.post("/preview")
async def preview(request: Request, p: dict = Body(...), user=Depends(admin)):
    _require_unlock(request)
    cfg = kis.load()
    env = cfg["mode"]
    if not cfg["enabled"]:
        raise HTTPException(403, "실계좌 주문이 꺼져 있습니다 (설정의 실행 스위치)")
    symbol, side, otype = p.get("symbol", ""), p.get("side"), p.get("type", "limit")
    inst = market.instrument(symbol)
    if not inst or not symbol.startswith("KR:") or inst.get("kind") not in ("stock", "etf", "etn"):
        raise HTTPException(400, "실계좌 주문은 국내 주식·ETF·ETN만 지원합니다")
    if side not in ("buy", "sell") or otype not in ("market", "limit"):
        raise HTTPException(400, "주문 유형이 올바르지 않습니다")
    try:
        qty = int(p.get("qty") or 0)
    except (TypeError, ValueError):
        qty = 0
    if qty <= 0:
        raise HTTPException(400, "수량은 1주 이상이어야 합니다")
    qd = await market.quote(symbol) or {}
    last = qd.get("price")
    price = None
    if otype == "limit":
        raw = float(p.get("price") or 0)
        if raw <= 0:
            raise HTTPException(400, "지정가를 입력해 주세요")
        price = kis.round_tick(raw, side, inst.get("kind") or "stock")
    ref = price or last
    if not ref:
        raise HTTPException(503, "현재가를 가져오지 못해 금액 한도를 확인할 수 없습니다")
    # 시장가 매수는 체결가가 현재가보다 높을 수 있어 여유를 둬서 한도를 본다
    est = ref * qty * (1.03 if otype == "market" and side == "buy" else 1.0)
    lim, used = cfg["limits"], _usage(env)
    if est > lim["per_order_krw"]:
        raise HTTPException(400, f"1회 주문 한도({lim['per_order_krw']:,}원)를 넘습니다 (예상 {est:,.0f}원)")
    if used["amount"] + est > lim["daily_krw"]:
        raise HTTPException(400, f"하루 주문 금액 한도({lim['daily_krw']:,}원)를 넘습니다 (오늘 {used['amount']:,.0f}원 사용)")
    if used["count"] + 1 > lim["daily_count"]:
        raise HTTPException(400, f"하루 주문 횟수 한도({lim['daily_count']}회)를 넘습니다")
    now = time.time()
    for k in [k for k, v in _confirms.items() if v["exp"] < now]:
        _confirms.pop(k, None)
    cid = secrets.token_urlsafe(16)
    item = dict(env=env, symbol=symbol, code=inst["code"], name=inst["name"], side=side, type=otype, qty=qty, price=price,
                last=last, est=est, exp=now + CONFIRM_SECONDS, user_id=user["id"], session=_session(request))
    _confirms[cid] = item
    out = {k: v for k, v in item.items() if k not in ("session", "user_id")}
    if price is not None and p.get("price") and float(p["price"]) != price:
        out["tick_adjusted"] = True
    return dict(confirm_id=cid, expires_in=CONFIRM_SECONDS, **out)


@router.post("/order")
async def place(request: Request, p: dict = Body(...), user=Depends(admin)):
    _require_unlock(request)
    item = _confirms.pop(p.get("confirm_id") or "", None)  # 1회용: 두 번 누르면 두 번째는 실패
    if not item or item["exp"] < time.time() or item["session"] != _session(request):
        raise HTTPException(409, "확인 시간이 지났거나 이미 처리된 주문입니다. 다시 미리보기 해 주세요")
    cfg = kis.load()
    if not cfg["enabled"] or cfg["mode"] != item["env"]:
        raise HTTPException(409, "그사이 설정(실행 스위치·모의/실전)이 바뀌었습니다. 다시 미리보기 해 주세요")
    used, lim = _usage(item["env"]), cfg["limits"]
    if used["amount"] + item["est"] > lim["daily_krw"] or used["count"] + 1 > lim["daily_count"]:
        raise HTTPException(400, "하루 한도를 넘습니다")
    oid = db.ex("INSERT INTO live_orders(env,user_id,symbol,side,ord_type,qty,price,est_amount,status,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?, 'sending', ?, ?)", (item["env"], user["id"], item["symbol"], item["side"], item["type"],
                                                            item["qty"], item["price"], item["est"], db.now(), db.now()))
    try:
        r = await kis.order(item["env"], item["side"], item["code"], item["qty"], item["price"])
        db.ex("UPDATE live_orders SET status='accepted', odno=?, orgno=?, ord_tmd=?, msg=?, updated_at=? WHERE id=?",
              (r["odno"], r["orgno"], r["ord_tmd"], r["msg"], db.now(), oid))
    except kis.KisError as e:
        st = "unknown" if e.unknown else "rejected"
        db.ex("UPDATE live_orders SET status=?, msg=?, msg_cd=?, updated_at=? WHERE id=?", (st, str(e), e.code, db.now(), oid))
        log.warning("live order %s %s: %s", oid, st, e)
    return db.one("SELECT * FROM live_orders WHERE id=?", (oid,))


@router.post("/orders/{oid}/cancel")
async def cancel(oid: int, request: Request, user=Depends(admin)):
    _require_unlock(request)
    o = db.one("SELECT * FROM live_orders WHERE id=?", (oid,))
    if not o or not o["odno"] or o["status"] not in ("accepted", "partial"):
        raise HTTPException(400, "취소할 수 있는 주문이 아닙니다")
    try:
        r = await kis.cancel(o["env"], o["odno"], o["orgno"])
    except kis.KisError as e:
        _kis_error(e)
    db.ex("UPDATE live_orders SET status='cancel_requested', msg=?, updated_at=? WHERE id=?", (r["msg"], db.now(), oid))
    return dict(ok=True, msg=r["msg"])


@router.get("/orders")
async def orders(request: Request, sync: int = 1, user=Depends(admin)):
    """주문 기록. sync=1이면 증권사 당일 체결내역으로 상태를 맞춘다 (결과 미확인 주문 포함)."""
    env = kis.load()["mode"]
    note = None
    if sync and db.val("SELECT 1 FROM live_orders WHERE env=? AND created_at>=? AND status IN "
                       "('accepted','partial','unknown','cancel_requested','sending')", (env, _today_start())):
        try:
            fl = {f["odno"]: f for f in await kis.fills(env)}
            for o in db.q("SELECT * FROM live_orders WHERE env=? AND created_at>=? AND status IN "
                          "('accepted','partial','cancel_requested')", (env, _today_start())):
                f = fl.get(o["odno"])
                if not f:
                    continue
                st = ("cancelled" if f["cancelled"] and f["filled"] == 0 else "filled" if f["filled"] >= o["qty"]
                      else "partial" if f["filled"] > 0 else "rejected" if f["rejected"] >= o["qty"] else o["status"])
                db.ex("UPDATE live_orders SET status=?, filled_qty=?, avg_price=?, updated_at=? WHERE id=?",
                      (st, f["filled"], f["avg_price"], db.now(), o["id"]))
            # 결과 미확인 주문: 같은 종목·방향·수량의 증권사 주문이 기록에 없는 주문번호로 있으면 연결한다
            known = {r["odno"] for r in db.q("SELECT odno FROM live_orders WHERE odno IS NOT NULL")}
            for o in db.q("SELECT * FROM live_orders WHERE env=? AND created_at>=? AND status IN ('unknown','sending')",
                          (env, _today_start())):
                code = o["symbol"].split(":")[1]
                m = next((f for f in fl.values() if f["odno"] not in known and f["code"] == code and f["side"] == o["side"]
                          and f["qty"] == o["qty"]), None)
                if m:
                    known.add(m["odno"])
                    db.ex("UPDATE live_orders SET status=?, odno=?, filled_qty=?, avg_price=?, msg=?, updated_at=? WHERE id=?",
                          ("filled" if m["filled"] >= o["qty"] else "partial" if m["filled"] else "accepted", m["odno"],
                           m["filled"], m["avg_price"], "증권사 체결내역으로 확인됨", db.now(), o["id"]))
        except kis.KisError as e:
            note = f"체결내역 동기화 실패: {e}"
    rows = db.q("SELECT * FROM live_orders ORDER BY id DESC LIMIT 200")
    nm = market.names(list({r["symbol"] for r in rows}))
    for r in rows:
        r["name"] = nm.get(r["symbol"], r["symbol"])
    return dict(env=env, rows=rows, note=note)
