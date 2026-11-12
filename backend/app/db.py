"""SQLite 저장소. 사용자 1~3명 규모라 단일 파일 DB + WAL로 충분하다."""
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

DATA_DIR = Path(os.environ.get("INVEST_HUB_DATA", Path(__file__).resolve().parents[2] / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "hub.db"

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL,
  nickname TEXT NOT NULL, is_admin INTEGER DEFAULT 0, created_at INTEGER);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at INTEGER);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS instruments(
  symbol TEXT PRIMARY KEY, market TEXT, kind TEXT, code TEXT, name TEXT, name_en TEXT,
  price REAL, prev_close REAL, change REAL, change_pct REAL,
  open REAL, high REAL, low REAL, volume REAL, value REAL, mcap REAL,
  per REAL, pbr REAL, eps REAL, bps REAL, div_yield REAL, high52 REAL, low52 REAL,
  sector TEXT, currency TEXT, extra TEXT, updated_at INTEGER, fund_updated_at INTEGER);
CREATE INDEX IF NOT EXISTS ix_inst_market ON instruments(market, mcap DESC);
CREATE INDEX IF NOT EXISTS ix_inst_name ON instruments(name);

CREATE TABLE IF NOT EXISTS candles(
  symbol TEXT, tf TEXT, ts INTEGER, o REAL, h REAL, l REAL, c REAL, v REAL,
  PRIMARY KEY(symbol, tf, ts)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS candle_sync(symbol TEXT, tf TEXT, synced_at INTEGER, PRIMARY KEY(symbol, tf));

CREATE TABLE IF NOT EXISTS themes(
  kind TEXT, no INTEGER, name TEXT, change_pct REAL, total INTEGER, rise INTEGER, fall INTEGER,
  updated_at INTEGER, PRIMARY KEY(kind, no));
CREATE TABLE IF NOT EXISTS theme_stocks(kind TEXT, no INTEGER, symbol TEXT, PRIMARY KEY(kind, no, symbol));

CREATE TABLE IF NOT EXISTS signals(
  id INTEGER PRIMARY KEY, symbol TEXT, strategy TEXT, date INTEGER, price REAL, side TEXT,
  stats TEXT, created_at INTEGER, UNIQUE(symbol, strategy, date));
CREATE INDEX IF NOT EXISTS ix_signals_date ON signals(date DESC);

CREATE TABLE IF NOT EXISTS watch_groups(id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT, sort INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS watch_items(group_id INTEGER, symbol TEXT, sort INTEGER DEFAULT 0, PRIMARY KEY(group_id, symbol));
CREATE TABLE IF NOT EXISTS memos(user_id INTEGER, symbol TEXT, body TEXT, updated_at INTEGER, PRIMARY KEY(user_id, symbol));
CREATE TABLE IF NOT EXISTS drawings(user_id INTEGER, symbol TEXT, data TEXT, PRIMARY KEY(user_id, symbol));
CREATE TABLE IF NOT EXISTS alerts(
  id INTEGER PRIMARY KEY, user_id INTEGER, symbol TEXT, kind TEXT, params TEXT, note TEXT,
  active INTEGER DEFAULT 1, repeat INTEGER DEFAULT 0, triggered_at INTEGER, created_at INTEGER);
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT, body TEXT, link TEXT, read INTEGER DEFAULT 0, created_at INTEGER);
CREATE TABLE IF NOT EXISTS saved_specs(
  id INTEGER PRIMARY KEY, user_id INTEGER, kind TEXT, name TEXT, spec TEXT, updated_at INTEGER);

CREATE TABLE IF NOT EXISTS accounts(
  id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT, initial_cash REAL, cash REAL, created_at INTEGER);
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY, account_id INTEGER, symbol TEXT, side TEXT, type TEXT, price REAL, qty REAL,
  status TEXT, fill_price REAL, fee REAL DEFAULT 0, created_at INTEGER, filled_at INTEGER, note TEXT);
CREATE INDEX IF NOT EXISTS ix_orders_open ON orders(status, symbol);
CREATE TABLE IF NOT EXISTS positions(account_id INTEGER, symbol TEXT, qty REAL, avg_price REAL, cost_krw REAL, PRIMARY KEY(account_id, symbol));
CREATE TABLE IF NOT EXISTS trades(
  id INTEGER PRIMARY KEY, account_id INTEGER, order_id INTEGER, symbol TEXT, side TEXT, price REAL, qty REAL,
  amount_krw REAL, fee REAL, pnl REAL, ts INTEGER);
CREATE TABLE IF NOT EXISTS equity_snapshots(account_id INTEGER, date TEXT, equity REAL, PRIMARY KEY(account_id, date));
CREATE TABLE IF NOT EXISTS journal(
  id INTEGER PRIMARY KEY, user_id INTEGER, trade_id INTEGER, symbol TEXT, date TEXT, side TEXT, price REAL, qty REAL,
  pnl REAL, title TEXT, body TEXT, tags TEXT, emotion TEXT, created_at INTEGER);

CREATE TABLE IF NOT EXISTS competitions(
  id INTEGER PRIMARY KEY, code TEXT UNIQUE, creator_id INTEGER, symbol TEXT, start_idx INTEGER, bars INTEGER, created_at INTEGER);
CREATE TABLE IF NOT EXISTS games(
  id INTEGER PRIMARY KEY, user_id INTEGER, symbol TEXT, start_idx INTEGER, bars INTEGER, competition_id INTEGER,
  state TEXT, result_pct REAL, finished INTEGER DEFAULT 0, created_at INTEGER, finished_at INTEGER);

CREATE TABLE IF NOT EXISTS posts(
  id INTEGER PRIMARY KEY, user_id INTEGER, kind TEXT, title TEXT, body TEXT, symbols TEXT, created_at INTEGER, updated_at INTEGER);
CREATE INDEX IF NOT EXISTS ix_posts_kind ON posts(kind, created_at DESC);
CREATE TABLE IF NOT EXISTS post_likes(post_id INTEGER, user_id INTEGER, PRIMARY KEY(post_id, user_id));
CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY, post_id INTEGER, user_id INTEGER, body TEXT, created_at INTEGER);
CREATE TABLE IF NOT EXISTS predictions(
  id INTEGER PRIMARY KEY, user_id INTEGER, symbol TEXT, direction TEXT, base_price REAL, days INTEGER,
  target_date TEXT, comment TEXT, created_at INTEGER, close_price REAL, result TEXT);

-- 스타트업 투자 DB
CREATE TABLE IF NOT EXISTS companies(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_norm TEXT UNIQUE, description TEXT, category TEXT,
  homepage TEXT, founded TEXT, ceo TEXT, address TEXT, employees INTEGER, corp_code TEXT, stock_code TEXT,
  bizno TEXT, status TEXT, total_raised REAL DEFAULT 0, deal_count INTEGER DEFAULT 0, last_round TEXT,
  last_deal_date TEXT, extra TEXT, enriched_at INTEGER, created_at INTEGER);
CREATE TABLE IF NOT EXISTS investors(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_norm TEXT UNIQUE, type TEXT, description TEXT, homepage TEXT,
  deal_count INTEGER DEFAULT 0, total_amount REAL DEFAULT 0, last_deal_date TEXT, created_at INTEGER);
CREATE TABLE IF NOT EXISTS deals(
  id INTEGER PRIMARY KEY, company_id INTEGER, date TEXT, round TEXT, kind TEXT, amount REAL, amount_text TEXT,
  valuation REAL, acquirer TEXT, source_url TEXT, article_id INTEGER, title TEXT, created_at INTEGER, foreign_deal INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_deals_date ON deals(date DESC);
CREATE INDEX IF NOT EXISTS ix_deals_company ON deals(company_id);
CREATE TABLE IF NOT EXISTS deal_investors(deal_id INTEGER, investor_id INTEGER, lead INTEGER DEFAULT 0, PRIMARY KEY(deal_id, investor_id));
CREATE TABLE IF NOT EXISTS funds(
  id INTEGER PRIMARY KEY, name TEXT, name_norm TEXT UNIQUE, investor_id INTEGER, size REAL, size_text TEXT,
  date TEXT, source_url TEXT, article_id INTEGER, title TEXT, created_at INTEGER);
CREATE TABLE IF NOT EXISTS articles(
  id INTEGER PRIMARY KEY, url TEXT UNIQUE, source TEXT, title TEXT, summary TEXT, body TEXT, published TEXT,
  kind TEXT, sentiment TEXT, company_ids TEXT, processed INTEGER DEFAULT 0, created_at INTEGER);
CREATE INDEX IF NOT EXISTS ix_articles_pub ON articles(published DESC);
CREATE TABLE IF NOT EXISTS grants(
  id INTEGER PRIMARY KEY, ext_id TEXT UNIQUE, title TEXT, org TEXT, category TEXT, region TEXT, target TEXT,
  start_date TEXT, end_date TEXT, url TEXT, body TEXT, source TEXT, updated_at INTEGER);
CREATE TABLE IF NOT EXISTS company_financials(
  company_id INTEGER, year INTEGER, revenue REAL, op_income REAL, net_income REAL, assets REAL, liabilities REAL,
  equity REAL, current_assets REAL, current_liab REAL, cash REAL, source TEXT, PRIMARY KEY(company_id, year));
CREATE TABLE IF NOT EXISTS company_employment(
  company_id INTEGER, ym TEXT, total INTEGER, joined INTEGER, left INTEGER, PRIMARY KEY(company_id, ym));
CREATE TABLE IF NOT EXISTS company_records(
  id INTEGER PRIMARY KEY, company_id INTEGER, kind TEXT, ext_id TEXT, title TEXT, date TEXT, amount REAL,
  detail TEXT, UNIQUE(company_id, kind, ext_id));
CREATE TABLE IF NOT EXISTS collections(
  id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT, description TEXT, smart_spec TEXT, created_at INTEGER);
CREATE TABLE IF NOT EXISTS collection_items(
  collection_id INTEGER, entity_type TEXT, entity_id INTEGER, added_at INTEGER,
  PRIMARY KEY(collection_id, entity_type, entity_id));
CREATE TABLE IF NOT EXISTS ir_rounds(
  id INTEGER PRIMARY KEY, user_id INTEGER, company_name TEXT, round TEXT, target_amount REAL, valuation REAL,
  description TEXT, deck_url TEXT, contact TEXT, status TEXT DEFAULT 'open', created_at INTEGER);
CREATE TABLE IF NOT EXISTS dart_corps(corp_code TEXT PRIMARY KEY, name TEXT, name_norm TEXT, stock_code TEXT);
CREATE INDEX IF NOT EXISTS ix_dart_norm ON dart_corps(name_norm);
CREATE TABLE IF NOT EXISTS live_orders(
  id INTEGER PRIMARY KEY, env TEXT, user_id INTEGER, symbol TEXT, side TEXT, ord_type TEXT, qty INTEGER, price REAL,
  est_amount REAL, status TEXT, odno TEXT, orgno TEXT, ord_tmd TEXT, filled_qty REAL, avg_price REAL, msg TEXT, msg_cd TEXT,
  created_at INTEGER, updated_at INTEGER);
CREATE TABLE IF NOT EXISTS flow_days(
  market TEXT, date TEXT, individual REAL, foreigner REAL, institution REAL, details TEXT, PRIMARY KEY(market, date));
CREATE TABLE IF NOT EXISTS flow_ticks(
  market TEXT, date TEXT, ts INTEGER, individual REAL, foreigner REAL, institution REAL, details TEXT,
  PRIMARY KEY(market, date, ts));
CREATE TABLE IF NOT EXISTS disclosures(
  rcept_no TEXT PRIMARY KEY, corp TEXT, market TEXT, symbol TEXT, title TEXT, cat TEXT, at INTEGER);
CREATE INDEX IF NOT EXISTS ix_disc_at ON disclosures(at DESC);
CREATE INDEX IF NOT EXISTS ix_disc_sym ON disclosures(symbol);
CREATE TABLE IF NOT EXISTS program_ticks(
  market TEXT, date TEXT, hhmm TEXT, arb REAL, nonarb REAL, total REAL, PRIMARY KEY(market, date, hhmm));
CREATE TABLE IF NOT EXISTS stock_flows(
  symbol TEXT, date TEXT, foreign_qty REAL, organ_qty REAL, indiv_qty REAL, close REAL, foreign_hold REAL,
  PRIMARY KEY(symbol, date));
CREATE TABLE IF NOT EXISTS job_log(name TEXT PRIMARY KEY, started_at INTEGER, finished_at INTEGER, status TEXT, detail TEXT);
"""


def conn() -> sqlite3.Connection:
    c = getattr(_local, "c", None)
    if c is None:
        c = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA foreign_keys=OFF")
        _local.c = c
    return c


MIGRATIONS = ["ALTER TABLE deals ADD COLUMN foreign_deal INTEGER DEFAULT 0", "ALTER TABLE companies ADD COLUMN valuation REAL",
              "ALTER TABLE companies ADD COLUMN foreign_co INTEGER DEFAULT 0"]


def init():
    conn().executescript(SCHEMA)
    for m in MIGRATIONS:
        try:
            conn().execute(m)
        except sqlite3.OperationalError:
            pass  # 이미 적용됨
    # 재시작 전에 돌던 작업은 끊긴 것으로 표시한다
    conn().execute("UPDATE job_log SET status='interrupted' WHERE status='running'")


def q(sql: str, params=()) -> list[dict]:
    return [dict(r) for r in conn().execute(sql, params).fetchall()]


def one(sql: str, params=()) -> dict | None:
    r = conn().execute(sql, params).fetchone()
    return dict(r) if r else None


def val(sql: str, params=()):
    r = conn().execute(sql, params).fetchone()
    return r[0] if r else None


def ex(sql: str, params=()) -> int:
    cur = conn().execute(sql, params)
    return cur.lastrowid


def many(sql: str, rows):
    c = conn()
    c.execute("BEGIN")
    try:
        c.executemany(sql, rows)
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise


class tx:
    """여러 쓰기를 한 번에 묶는다 (주문 체결처럼 잔고·포지션이 함께 바뀌는 경우)."""

    def __enter__(self):
        conn().execute("BEGIN IMMEDIATE")
        return conn()

    def __exit__(self, et, ev, tb):
        conn().execute("ROLLBACK" if et else "COMMIT")
        return False


def now() -> int:
    return int(time.time())


def get_setting(key: str, default=None):
    v = val("SELECT value FROM settings WHERE key=?", (key,))
    return default if v is None else json.loads(v)


def set_setting(key: str, value):
    ex("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
       (key, json.dumps(value, ensure_ascii=False)))


def job_start(name: str):
    ex("INSERT INTO job_log(name,started_at,status) VALUES(?,?,'running') "
       "ON CONFLICT(name) DO UPDATE SET started_at=excluded.started_at,status='running',detail=NULL", (name, now()))


def job_end(name: str, status: str = "ok", detail: str = ""):
    ex("UPDATE job_log SET finished_at=?,status=?,detail=? WHERE name=?", (now(), status, detail[:500], name))
