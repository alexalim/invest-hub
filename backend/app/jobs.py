"""백그라운드 작업. 서버 프로세스 안에서 asyncio 태스크로 돌린다 (사용자 수가 적어 별도 워커가 필요 없다)."""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

import numpy as np

from . import db, trading
from .analysis import events, indicators as ind, kisdata, pulse, signals, similar, store
from .providers import market, naver, upbit
from .vc import collect as vc_collect, grants as vc_grants

log = logging.getLogger("jobs")
_tasks: list[asyncio.Task] = []
_running: set[str] = set()


def kst() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=9)


def kr_hours() -> bool:
    n = kst()
    return n.weekday() < 5 and 8 <= n.hour < 20


def us_hours() -> bool:
    n = kst()
    return (n.hour >= 22 or n.hour < 7) and (n - timedelta(hours=7)).weekday() < 5


async def run(name: str, fn):
    """작업 1회 실행 + 기록. 같은 작업이 겹쳐 돌지 않게 한다."""
    if name in _running:
        return
    _running.add(name)
    db.job_start(name)
    try:
        res = await fn()
        db.job_end(name, "ok", "" if res is None else str(res))
    except Exception as e:
        log.exception("job %s failed", name)
        db.job_end(name, "error", repr(e))
    finally:
        _running.discard(name)


def notify(user_id: int, title: str, body: str, link: str = ""):
    db.ex("INSERT INTO notifications(user_id,title,body,link,created_at) VALUES(?,?,?,?,?)", (user_id, title, body, link, db.now()))


# ── 시세 목록 ──────────────────────────────────────────────────────────
async def j_instruments_kr():
    return await naver.refresh_kr()


async def j_instruments_us():
    return await naver.refresh_us()


async def j_crypto():
    return await upbit.refresh()


async def j_macro():
    return await market.refresh_macro()


async def j_flow():
    """투자자별 수급: 과거분이 비어 있으면 먼저 채우고 당일 누계를 기록한다."""
    filled = await pulse.flow_backfill()
    return (f"과거 {filled}일 채움, " if filled else "") + await pulse.flow_tick()


async def j_stock_flows():
    """종목별 외국인·기관 순매수. 확정치는 저녁에 올라오므로 6시간에 한 번만 다시 받는다."""
    last = db.get_setting("stock_flows_at", 0)
    if db.now() - last < 6 * 3600:
        return "최근에 받음"
    return await pulse.stock_flow_sync()


async def j_disclosures():
    """공시 속보. 근무 시간에는 2분마다 RSS를 읽고, DART 키가 있으면 하루 한 번 지난 공시도 채운다."""
    msg = await events.dart_poll()
    back = await events.dart_backfill()
    return msg if "건너뜀" in back or "이미" in back else f"{msg}, {back}"


async def j_groups():
    return dict(theme=await naver.refresh_groups("theme"), industry=await naver.refresh_groups("industry"))


def update_52w():
    """일봉에서 52주 고저를 계산해 종목 테이블에 반영한다."""
    cutoff = db.now() - 366 * 86400
    # 시스템 SQLite가 3.31이라 UPDATE ... FROM을 쓸 수 없다
    rows = db.q("SELECT symbol, MAX(h) hi, MIN(l) lo FROM candles WHERE tf='day' AND ts>=? GROUP BY symbol", (cutoff,))
    db.many("UPDATE instruments SET high52=?, low52=? WHERE symbol=?", [(r["hi"], r["lo"], r["symbol"]) for r in rows])


async def j_candles(scope: str = "all"):
    out = {}
    if scope in ("all", "kr"):
        out["kr"] = await market.bulk_sync(market.universe(("KOSPI", "KOSDAQ")), concurrency=5)
        out["etf"] = await market.bulk_sync(market.universe(("KOSPI",), limit=150, kinds=("etf",)), concurrency=5)
    if scope in ("all", "us"):
        out["us"] = await market.bulk_sync(market.universe(("NASDAQ", "NYSE", "AMEX"), limit=500), concurrency=4)
    if scope in ("all", "cr"):
        cr = [r["symbol"] for r in db.q("SELECT symbol FROM instruments WHERE market='CRYPTO' ORDER BY value DESC LIMIT 120")]
        out["cr"] = await market.bulk_sync(cr, concurrency=2)
    if scope == "all":
        out["macro"] = await market.bulk_sync(list(market.MACRO), concurrency=3)
    update_52w()
    store.clear()
    similar.invalidate()
    await run("signals", j_signals)
    return out


async def j_signals():
    syms = market.universe(("KOSPI", "KOSDAQ")) + market.universe(("NASDAQ", "NYSE", "AMEX"), limit=500)
    syms += [r["symbol"] for r in db.q("SELECT symbol FROM instruments WHERE market='CRYPTO' ORDER BY value DESC LIMIT 120")]
    return await asyncio.to_thread(signals.scan, syms)


async def j_fundamentals():
    """PER·PBR·EPS·BPS·배당수익률. 종목별 조회라 하루 한 번만 돈다."""
    stale = db.now() - 20 * 3600
    kr = db.q("SELECT symbol,code FROM instruments WHERE market IN ('KOSPI','KOSDAQ') AND kind='stock' "
              "AND COALESCE(fund_updated_at,0)<? ORDER BY mcap DESC", (stale,))
    us = db.q("SELECT symbol,extra FROM instruments WHERE market IN ('NASDAQ','NYSE','AMEX') AND COALESCE(fund_updated_at,0)<? "
              "ORDER BY mcap DESC LIMIT 600", (stale,))
    sem = asyncio.Semaphore(5)
    n = 0

    async def one(sym, fetch):
        nonlocal n
        async with sem:
            try:
                d = await fetch()
                db.ex("UPDATE instruments SET per=?,pbr=?,eps=?,bps=?,div_yield=?,fund_updated_at=? WHERE symbol=?",
                      (d.get("per"), d.get("pbr"), d.get("eps"), d.get("bps"), d.get("div_yield"), db.now(), sym))
                n += 1
            except Exception as e:
                log.debug("fundamental %s: %r", sym, e)
            await asyncio.sleep(0.05)

    tasks = [one(r["symbol"], lambda c=r["code"]: naver.integration_kr(c)) for r in kr]
    for r in us:
        reut = json.loads(r["extra"] or "{}").get("reuters")
        if reut:
            tasks.append(one(r["symbol"], lambda x=reut: naver.integration_us(x)))
    await asyncio.gather(*tasks)
    return n


# ── 거래·알림 ──────────────────────────────────────────────────────────
async def j_match():
    return await trading.match_open_orders()


async def j_alerts():
    rows = db.q("SELECT * FROM alerts WHERE active=1")
    if not rows:
        return 0
    qs = await market.quotes(list({r["symbol"] for r in rows}))
    fired = 0
    for a in rows:
        qd = qs.get(a["symbol"])
        if not qd or qd.get("price") is None:
            continue
        p = json.loads(a["params"] or "{}")
        price = float(qd["price"])
        name = market.name_of(a["symbol"])
        msg = None
        if a["kind"] == "price_above" and price >= float(p["price"]):
            msg = f"{name} 현재가 {price:,.2f} — 목표가 {float(p['price']):,.2f} 이상 도달"
        elif a["kind"] == "price_below" and price <= float(p["price"]):
            msg = f"{name} 현재가 {price:,.2f} — 기준가 {float(p['price']):,.2f} 이하 도달"
        elif a["kind"] == "change_above" and (qd.get("change_pct") or 0) >= float(p["pct"]):
            msg = f"{name} 등락률 {qd['change_pct']:+.2f}% — {float(p['pct']):+.1f}% 이상"
        elif a["kind"] == "change_below" and (qd.get("change_pct") or 0) <= float(p["pct"]):
            msg = f"{name} 등락률 {qd['change_pct']:+.2f}% — {float(p['pct']):+.1f}% 이하"
        elif a["kind"] == "condition":
            if a["triggered_at"] and db.now() - a["triggered_at"] < 20 * 3600:
                continue  # 조건 알림은 하루 한 번
            d = store.get(a["symbol"])
            if d is None:  # 일괄 수집 대상(미국 시총 상위 500 등) 밖의 종목은 필요할 때 받아 둔다
                await market.daily(a["symbol"], max_age=6 * 3600)
                d = store.get(a["symbol"])
            if d is None:
                continue
            try:
                conds = p.get("conds") or []
                if conds and bool(ind.evaluate_all(store.tail(d, 400), conds, p.get("mode", "and"))[-1]):
                    msg = f"{name} 조건 충족: " + " · ".join(ind.describe_cond(c) for c in conds)
            except Exception as e:
                log.debug("alert cond %s: %r", a["id"], e)
        if msg:
            fired += 1
            notify(a["user_id"], "알림: " + name, msg + (f" ({a['note']})" if a["note"] else ""), f"/stock/{a['symbol']}")
            if a["kind"] == "condition" or a["repeat"]:
                db.ex("UPDATE alerts SET triggered_at=? WHERE id=?", (db.now(), a["id"]))
            else:
                db.ex("UPDATE alerts SET active=0, triggered_at=? WHERE id=?", (db.now(), a["id"]))
    return fired


async def j_predictions():
    """종목예측 만기 정산."""
    today = kst().strftime("%Y-%m-%d")
    rows = db.q("SELECT * FROM predictions WHERE result IS NULL AND target_date<=?", (today,))
    if not rows:
        return 0
    qs = await market.quotes(list({r["symbol"] for r in rows}))
    for r in rows:
        qd = qs.get(r["symbol"])
        if not qd or qd.get("price") is None:
            continue
        price = float(qd["price"])
        up = price > r["base_price"]
        res = "hit" if (r["direction"] == "up") == up and price != r["base_price"] else "miss"
        db.ex("UPDATE predictions SET close_price=?, result=? WHERE id=?", (price, res, r["id"]))
        notify(r["user_id"], "종목예측 결과", f"{market.name_of(r['symbol'])}: {'적중' if res == 'hit' else '빗나감'} "
               f"({r['base_price']:,.2f} → {price:,.2f})", "/community/predict")
    return len(rows)


async def j_snapshot():
    await trading.snapshot_all()


# ── 스타트업 투자 DB ───────────────────────────────────────────────────
async def j_validate():
    """매주 한 번 전략·AI예측 검증을 다시 계산한다 (몇 분 걸리는 계산이라 별도 스레드)."""
    from .analysis import validate
    return await asyncio.to_thread(validate.run)


_stop_kis = {"flag": False}


async def j_kis_minutes():
    """한국투자증권에서 과거 1분봉을 받아 5분봉으로 저장 (시간이 오래 걸리고, 중단 후 이어받기가 된다)."""
    from . import intraday
    _stop_kis["flag"] = False
    r = await intraday.kis_download(100, 252, stop=lambda: _stop_kis["flag"])
    return r


async def j_intraday():
    """장 마감 뒤 5분봉을 덧붙이고, 그다음 장중 검증을 다시 계산한다."""
    from . import intraday
    from .analysis import intraday_bt
    r = await intraday.sync(300)
    v = await asyncio.to_thread(intraday_bt.validate)
    return dict(r, validated=bool(v))


async def j_validate_if_old():
    v = db.get_setting("validation")
    if v and db.now() - v.get("at", 0) < 7 * 86400:
        return "최근 결과 있음"
    if db.val("SELECT COUNT(*) FROM candle_sync") < 500:
        return "일봉 수집 대기"
    return await j_validate()


async def j_vc():
    return await vc_collect.run_once()


async def j_grants():
    return await vc_grants.collect()


async def j_vc_backfill():
    if db.get_setting("vc_backfill_done"):
        return "이미 완료"
    return await vc_collect.backfill(int(db.get_setting("vc_backfill_months", 24)))


JOBS = {
    "instruments_kr": (j_instruments_kr, "국내 종목 시세 목록"), "instruments_us": (j_instruments_us, "미국 종목 시세 목록"),
    "crypto": (j_crypto, "코인 시세 목록"), "macro": (j_macro, "지수·환율·원자재"), "groups": (j_groups, "테마·업종"),
    "disclosures": (j_disclosures, "공시 속보 (DART)"),
    "flow": (j_flow, "투자자별 수급 (시장 전체)"), "kis_market": (kisdata.job, "프로그램 매매·업종별 수급 (한투 시세 조회)"), "stock_flows": (lambda: pulse.stock_flow_sync(), "종목별 외국인·기관 순매수 (시총 상위 200)"),
    "candles": (j_candles, "일봉 전체 수집 + 매매신호"), "signals": (j_signals, "매매신호 스캔"),
    "fundamentals": (j_fundamentals, "PER·PBR 등 재무 지표"), "vc": (j_vc, "투자 뉴스 수집"), "grants": (j_grants, "지원사업 공고"),
    "vc_backfill": (j_vc_backfill, "과거 투자 뉴스 채우기"), "validate": (j_validate, "전략·AI예측 검증 (주 1회)"),
    "intraday": (j_intraday, "5분봉 수집 + 장중 단타 검증 (매일 장 마감 뒤)"),
    "kis_minutes": (j_kis_minutes, "한투 과거 1분봉 1년치 받기 (오래 걸림, 이어받기)"), "snapshot": (j_snapshot, "계좌 평가액 기록"),
}


async def _loop(name: str, fn, interval, first_delay: float = 0):
    await asyncio.sleep(first_delay)
    while True:
        await run(name, fn)
        await asyncio.sleep(interval() if callable(interval) else interval)


async def _daily_candles():
    """기동 직후 한 번, 이후 장 마감 뒤 정해진 시각에 일봉을 다시 받는다."""
    await asyncio.sleep(20)
    last = db.one("SELECT finished_at,status FROM job_log WHERE name='candles'")
    if not last or last["status"] != "ok" or not last["finished_at"] or db.now() - last["finished_at"] > 10 * 3600:
        await run("candles", j_candles)
    slots = {(15, 50): "kr", (20, 10): "kr", (6, 40): "us", (9, 10): "cr"}
    done: set[str] = set()
    while True:
        n = kst()
        key = (n.hour, n.minute - n.minute % 10)
        tag = f"{n.date()}-{key}"
        if key in slots and tag not in done:
            done.add(tag)
            await run("candles", lambda s=slots[key]: j_candles(s))
            if key == (20, 10):
                await run("fundamentals", j_fundamentals)
            if key == (15, 50):
                await run("intraday", j_intraday)
        await asyncio.sleep(60)


def start():
    spec = [
        ("instruments_kr", j_instruments_kr, lambda: 45 if kr_hours() else 1800, 0),
        ("instruments_us", j_instruments_us, lambda: 120 if us_hours() else 3600, 3),
        ("crypto", j_crypto, 20, 1), ("macro", j_macro, 60, 2),
        ("groups", j_groups, lambda: 300 if kr_hours() else 3600, 6),
        ("flow", j_flow, lambda: 60 if pulse.regular_session() else 1800, 8), ("stock_flows", j_stock_flows, 3600, 120),
        ("disclosures", j_disclosures, lambda: 120 if kr_hours() else 1800, 20),
        ("kis_market", kisdata.job, lambda: 60 if pulse.regular_session() else 1800, 45),
        ("match", j_match, 3, 10), ("alerts", j_alerts, 20, 15), ("predictions", j_predictions, 1800, 30),
        ("snapshot", j_snapshot, 1800, 40), ("vc", j_vc, 1800, 25), ("grants", j_grants, 6 * 3600, 35),
        ("vc_backfill", j_vc_backfill, 24 * 3600, 90), ("validate", j_validate_if_old, 6 * 3600, 900), ("fundamentals", j_fundamentals, 24 * 3600, 600),
    ]
    for name, fn, interval, delay in spec:
        _tasks.append(asyncio.create_task(_loop(name, fn, interval, delay)))
    _tasks.append(asyncio.create_task(_daily_candles()))


async def stop():
    for t in _tasks:
        t.cancel()
    await asyncio.gather(*_tasks, return_exceptions=True)
    _tasks.clear()
