"""로그인. 첫 가입자가 관리자가 되고, 이후 가입은 관리자가 정한 초대 코드가 있어야 한다."""
import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, Request

from . import db

COOKIE = "hub_session"


def hash_pw(pw: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return salt.hex() + ":" + h.hex()


def check_pw(pw: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":")
        return hmac.compare_digest(hash_pw(pw, bytes.fromhex(salt)).split(":")[1], h)
    except Exception:
        return False


def setup_code() -> str:
    """설치 코드. 처음 실행 때 data/setup_code.txt에 만들어 두고, 관리자가 생기면 지운다."""
    f = db.DATA_DIR / "setup_code.txt"
    if not f.exists():
        f.write_text(secrets.token_hex(4).upper() + "\n")
        f.chmod(0o600)
    return f.read_text().strip()


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db.ex("INSERT INTO sessions(token,user_id,created_at) VALUES(?,?,?)", (token, user_id, db.now()))
    return token


def current_user(request: Request) -> dict:
    token = request.cookies.get(COOKIE)
    user = db.one("SELECT u.id,u.username,u.nickname,u.is_admin FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?",
                  (token,)) if token else None
    if not user:
        raise HTTPException(401, "로그인이 필요합니다")
    return user


def admin_user(user: dict = Depends(current_user)) -> dict:
    if not user["is_admin"]:
        raise HTTPException(403, "관리자만 할 수 있습니다")
    return user


def register(username: str, password: str, nickname: str, invite: str | None) -> dict:
    username = username.strip()
    if len(username) < 2 or len(password) < 6:
        raise HTTPException(400, "아이디는 2자 이상, 비밀번호는 6자 이상이어야 합니다")
    first = db.val("SELECT COUNT(*) FROM users") == 0
    if first:
        # 첫 가입자는 관리자가 되므로, 같은 망의 다른 사람이 먼저 가입하지 못하게 설치 코드를 요구한다
        code = setup_code()
        if not invite or not hmac.compare_digest(code, invite.strip()):
            raise HTTPException(403, "설치 코드가 올바르지 않습니다. 서버 PC의 data/setup_code.txt를 확인하세요")
    else:
        code = db.get_setting("invite_code")
        if not code or not invite or not hmac.compare_digest(str(code), invite.strip()):
            raise HTTPException(403, "초대 코드가 올바르지 않습니다")
    if db.val("SELECT 1 FROM users WHERE username=?", (username,)):
        raise HTTPException(409, "이미 있는 아이디입니다")
    uid = db.ex("INSERT INTO users(username,pw_hash,nickname,is_admin,created_at) VALUES(?,?,?,?,?)",
                (username, hash_pw(password), nickname.strip() or username, 1 if first else 0, db.now()))
    db.ex("INSERT INTO watch_groups(user_id,name,sort) VALUES(?,?,0)", (uid, "관심종목"))
    db.ex("INSERT INTO accounts(user_id,name,initial_cash,cash,created_at) VALUES(?,?,?,?,?)",
          (uid, "모의계좌 1", 1e8, 1e8, db.now()))
    if first:
        (db.DATA_DIR / "setup_code.txt").unlink(missing_ok=True)
        if not db.get_setting("invite_code"):
            db.set_setting("invite_code", secrets.token_hex(3).upper())
    return dict(id=uid, username=username, is_admin=first)


_FAILS: dict[str, list[float]] = {}   # 아이디·접속 주소별 최근 실패 시각 (서버 메모리)
MAX_FAILS, FAIL_WINDOW = 8, 600


def login(username: str, password: str, ip: str = "") -> dict:
    """비밀번호를 10분 안에 8번 틀리면 그 아이디·접속 주소 조합을 10분 동안 막는다."""
    import time
    key, now = f"{username.strip().lower()}|{ip}", time.time()
    recent = [t for t in _FAILS.get(key, []) if now - t < FAIL_WINDOW]
    if len(recent) >= MAX_FAILS:
        raise HTTPException(429, "로그인 시도가 너무 많습니다. 10분 뒤에 다시 해 주세요")
    u = db.one("SELECT * FROM users WHERE username=?", (username.strip(),))
    if not u or not check_pw(password, u["pw_hash"]):
        _FAILS[key] = recent + [now]
        if len(_FAILS) > 5000:
            _FAILS.clear()
        raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다")
    _FAILS.pop(key, None)
    return u
