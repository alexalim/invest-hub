"""사용자 데이터 정리. 시장·투자 DB 데이터는 건드리지 않는다."""
from . import db

USER_TABLES = ["sessions", "watch_groups", "memos", "drawings", "alerts", "notifications", "saved_specs", "journal", "games",
               "posts", "post_likes", "comments", "predictions", "collections", "ir_rounds"]


def delete_user_data(uid: int):
    with db.tx() as c:
        accs = [r[0] for r in c.execute("SELECT id FROM accounts WHERE user_id=?", (uid,)).fetchall()]
        for a in accs:
            for t in ("orders", "trades", "positions", "equity_snapshots"):
                c.execute(f"DELETE FROM {t} WHERE account_id=?", (a,))
        c.execute("DELETE FROM accounts WHERE user_id=?", (uid,))
        c.execute("DELETE FROM watch_items WHERE group_id IN (SELECT id FROM watch_groups WHERE user_id=?)", (uid,))
        c.execute("DELETE FROM collection_items WHERE collection_id IN (SELECT id FROM collections WHERE user_id=?)", (uid,))
        c.execute("DELETE FROM comments WHERE post_id IN (SELECT id FROM posts WHERE user_id=?)", (uid,))
        for t in USER_TABLES:
            c.execute(f"DELETE FROM {t} WHERE user_id=?", (uid,))
        c.execute("DELETE FROM competitions WHERE creator_id=?", (uid,))
        c.execute("DELETE FROM users WHERE id=?", (uid,))


def reset_all_users():
    """모든 사용자와 사용자 데이터를 지운다 (시세·일봉·투자 DB는 남긴다). 다음 가입자가 관리자가 된다."""
    for (uid,) in db.conn().execute("SELECT id FROM users").fetchall():
        delete_user_data(uid)
    for t in ("orders", "trades", "positions", "equity_snapshots", "accounts", "watch_items", "collection_items", "competitions"):
        db.ex(f"DELETE FROM {t}")
    for k in ("invite_code",):
        db.ex("DELETE FROM settings WHERE key=?", (k,))
    db.ex("DELETE FROM settings WHERE key LIKE 'ai_rank:%'")


if __name__ == "__main__":
    import sys
    db.init()
    if "--reset-users" in sys.argv:
        reset_all_users()
        print("사용자 데이터를 모두 지웠습니다. 서버를 다시 시작하면 새 설치 코드가 나옵니다.")
