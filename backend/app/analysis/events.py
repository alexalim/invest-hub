"""공시 속보(DART), 미국 실적 발표 일정(나스닥), 코스피200 선물 베이시스."""
import asyncio
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape

from .. import db
from ..providers import http, market

log = logging.getLogger("events")
RSS = "https://dart.fss.or.kr/api/todayRSS.xml"
DART_LIST = "https://opendart.fss.or.kr/api/list.json"
NASDAQ = "https://api.nasdaq.com/api/calendar/earnings"
# 분류: (키, 화면 이름, 제목에 들어 있으면 해당하는 낱말들). 위에서부터 먼저 맞는 것으로 정한다
CATS = [
    ("holder5", "5% 대량보유", ("대량보유상황보고서",)),
    ("insider", "임원·주요주주", ("임원ㆍ주요주주", "임원·주요주주", "최대주주등소유주식변동")),
    ("buyback", "자사주", ("자기주식", "신탁계약에의한취득", "신탁계약해지", "주식소각")),
    ("earnings", "실적", ("영업(잠정)실적", "잠정실적", "손익구조", "영업실적등에대한전망", "매출액또는손익")),
    ("contract", "수주·계약", ("단일판매", "공급계약")),
    ("capital", "증자·사채", ("유상증자", "무상증자", "전환사채", "신주인수권부사채", "교환사채", "감자결정")),
    ("dividend", "배당", ("배당",)),
    ("deal", "합병·분할·인수", ("합병", "분할", "영업양수", "영업양도", "타법인주식", "공개매수")),
    ("warning", "거래정지·관리", ("매매거래정지", "관리종목", "상장폐지", "불성실공시", "투자주의", "투자경고", "투자위험", "횡령", "배임")),
    ("major", "주요 경영사항", ("투자판단관련주요경영사항", "주요사항보고서", "최대주주변경", "소송", "회생절차", "영업정지")),
    ("guarantee", "담보·보증", ("담보제공", "채무보증", "금전대여")),
    ("option", "스톡옵션", ("주식매수선택권",)),
    ("meeting", "주주총회", ("주주총회", "의결권대리행사", "주주명부폐쇄")),
    ("ir", "기업설명회", ("기업설명회",)),
    ("related", "계열사 거래", ("동일인등출자계열회사", "대규모기업집단", "특수관계인", "대규모내부거래")),
    ("issue", "증권 발행 서류", ("증권발행실적보고서", "증권발행결과", "일괄신고", "투자설명서", "증권신고서", "자산유동화")),
    ("report", "정기보고서", ("분기보고서", "반기보고서", "사업보고서")),
]
CAT_NAMES = {k: n for k, n, _ in CATS} | {"etc": "기타"}
_cache: dict[str, tuple[float, object]] = {}


def classify(title: str) -> str:
    for key, _, words in CATS:
        if any(w in title for w in words):
            return key
    return "etc"


def _symbols() -> dict[str, str]:
    hit = _cache.get("names")
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    m = {r["name"]: r["symbol"] for r in db.q("SELECT name,symbol FROM instruments WHERE market IN ('KOSPI','KOSDAQ') AND kind='stock' ORDER BY mcap")}
    _cache["names"] = (time.time(), m)
    return m


def _save(rows: list[tuple]) -> int:
    before = db.val("SELECT COUNT(*) FROM disclosures")
    db.many("INSERT OR IGNORE INTO disclosures(rcept_no,corp,market,symbol,title,cat,at) VALUES(?,?,?,?,?,?,?)", rows)
    return db.val("SELECT COUNT(*) FROM disclosures") - before


async def dart_poll() -> str:
    """DART '최근 공시' RSS(최근 50건, 키 불필요)를 읽어 쌓는다."""
    xml = await http.get_text(RSS)
    names = _symbols()
    rows = []
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
        def tag(t):
            m = re.search(rf"<{t}>(.*?)</{t}>", item, re.S)
            return unescape(m.group(1).strip()) if m else ""
        no = re.search(r"rcpNo=(\d{14})", tag("link"))
        full = tag("title")
        if not no or " - " not in full:
            continue
        head, title = full.split(" - ", 1)
        mk = re.match(r"\((.*?)\)", head)
        corp = tag("dc:creator") or re.sub(r"^\(.*?\)", "", head).strip()
        try:
            at = int(parsedate_to_datetime(tag("pubDate")).timestamp())
        except Exception:
            at = db.now()
        rows.append((no.group(1), corp, mk.group(1) if mk else "", names.get(corp), title.strip(), classify(title), at))
    new = _save(rows)
    db.ex("DELETE FROM disclosures WHERE at < ?", (db.now() - 120 * 86400,))
    return f"새 공시 {new}건"


async def dart_backfill(days: int = 30) -> str:
    """DART 인증키가 설정돼 있으면 지난 공시를 채운다 (키가 없으면 RSS로 쌓인 것만 보인다)."""
    key = db.get_setting("dart_key")
    if not key:
        return "DART 키 없음 — 건너뜀"
    if db.now() - (db.get_setting("dart_backfill_at") or 0) < 86400:
        return "오늘 이미 받음"
    names = _symbols()
    kst = datetime.now(timezone.utc) + timedelta(hours=9)
    total = 0
    for back in range(days):
        day = (kst - timedelta(days=back)).strftime("%Y%m%d")
        for page in range(1, 30):
            d = await http.get_json(DART_LIST, {"crtfc_key": key, "bgn_de": day, "end_de": day, "page_no": page, "page_count": 100})
            if d.get("status") != "000":
                break
            rows = []
            for r in d.get("list") or []:
                if r.get("corp_cls") not in ("Y", "K"):
                    continue
                at = int(datetime.strptime(r["rcept_dt"], "%Y%m%d").replace(tzinfo=timezone.utc).timestamp()) - 9 * 3600 + 18 * 3600
                sym = f"KR:{r['stock_code']}" if r.get("stock_code") else names.get(r.get("corp_name"))
                rows.append((r["rcept_no"], r.get("corp_name"), "유가" if r["corp_cls"] == "Y" else "코스닥", sym,
                             (r.get("report_nm") or "").strip(), classify(r.get("report_nm") or ""), at))
            total += _save(rows)
            if page >= int(d.get("total_page") or 1):
                break
    db.set_setting("dart_backfill_at", db.now())
    return f"과거 공시 {total}건"


def disclosure_view(cat: str = "", q: str = "", page: int = 1, size: int = 50, mine: list[str] | None = None) -> dict:
    page, size = max(1, int(page)), max(1, min(int(size), 100))
    where, params = ["1=1"], []
    if cat and cat in CAT_NAMES:
        where.append("d.cat=?"); params.append(cat)
    elif not cat:
        where.append("d.cat NOT IN ('report','issue')")   # 기본 화면에서는 건수만 많은 정기보고서·증권 발행 서류를 뺀다
    if q.strip():
        where.append("(d.corp LIKE ? OR d.title LIKE ?)"); params += [f"%{q.strip()}%"] * 2
    if mine is not None:
        if not mine:
            return dict(total=0, rows=[], cats=[], names=CAT_NAMES, since=None)
        where.append(f"d.symbol IN ({','.join('?' * len(mine))})"); params += mine
    w = " AND ".join(where)
    total = db.val(f"SELECT COUNT(*) FROM disclosures d WHERE {w}", params)
    rows = db.q(f"SELECT d.rcept_no,d.corp,d.market,d.symbol,d.title,d.cat,d.at,i.price,i.change_pct FROM disclosures d "
                f"LEFT JOIN instruments i ON i.symbol=d.symbol WHERE {w} ORDER BY d.at DESC, d.rcept_no DESC LIMIT ? OFFSET ?",
                (*params, size, (page - 1) * size))
    cats = db.q("SELECT cat, COUNT(*) n FROM disclosures WHERE at>=? GROUP BY cat ORDER BY n DESC", (db.now() - 7 * 86400,))
    return dict(total=total, rows=rows, cats=cats, names=CAT_NAMES, since=db.val("SELECT MIN(at) FROM disclosures"),
                has_key=bool(db.get_setting("dart_key")))


# ── 미국 실적 발표 일정 ────────────────────────────────────────────────
def _usd(s) -> float | None:
    s = str(s or "").replace("$", "").replace(",", "").strip()
    neg = s.startswith("(") and s.endswith(")")
    try:
        v = float(s.strip("()"))
    except ValueError:
        return None
    return -v if neg else v


async def earnings_view(days: int = 6) -> dict:
    """앞으로 며칠 동안 실적을 발표하는 미국 종목 (우리 종목 목록에 있는 것만, 시가총액 순)."""
    hit = _cache.get("earnings")
    if hit and time.time() - hit[0] < 6 * 3600:
        return hit[1]
    known = {r["code"]: r for r in db.q("SELECT symbol,code,name,price,change_pct,mcap FROM instruments WHERE market IN ('NASDAQ','NYSE','AMEX')")}
    et = datetime.now(timezone.utc) - timedelta(hours=5)
    dates = []
    d = et
    while len(dates) < days:
        if d.weekday() < 5:
            dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)

    async def one(day: str):
        try:
            j = await http.get_json(NASDAQ, {"date": day}, headers={"Accept": "application/json, text/plain, */*"})
        except Exception as e:
            log.warning("earnings %s: %s", day, e)
            return day, None
        out = []
        for r in ((j.get("data") or {}).get("rows")) or []:
            k = known.get(str(r.get("symbol") or "").replace(".", "-")) or known.get(r.get("symbol"))
            if not k:
                continue
            when = {"time-pre-market": "개장 전", "time-after-hours": "마감 후"}.get(r.get("time"), "시간 미정")
            out.append(dict(symbol=k["symbol"], name=k["name"], price=k["price"], change_pct=k["change_pct"], mcap=k["mcap"], when=when,
                            eps_forecast=_usd(r.get("epsForecast")), eps_last=_usd(r.get("lastYearEPS")), quarter=r.get("fiscalQuarterEnding"),
                            estimates=r.get("noOfEsts")))
        out.sort(key=lambda x: -(x["mcap"] or 0))
        return day, out

    res = await asyncio.gather(*(one(x) for x in dates))
    out = dict(at=db.now(), days=[dict(date=day, rows=rows[:40], total=len(rows)) for day, rows in res if rows is not None])
    if out["days"]:
        _cache["earnings"] = (time.time(), out)
    return out


# ── 코스피200 선물 베이시스 ────────────────────────────────────────────
async def basis_view() -> dict:
    qs = await market.quotes(["IX:K200F", "IX:KOSPI200"])
    fut, spot = qs.get("IX:K200F"), qs.get("IX:KOSPI200")
    if not fut or not spot:
        return dict(basis=None)
    return dict(future=fut["price"], future_pct=fut.get("change_pct"), spot=spot["price"], spot_pct=spot.get("change_pct"),
                basis=round(fut["price"] - spot["price"], 2))
