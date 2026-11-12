"""스타트업 투자 뉴스 수집. RSS에서 기사를 모으고, 추출기로 라운드·인수·펀드 정보를 뽑아 저장한다.
같은 라운드를 여러 매체가 보도하므로 회사·시기 기준으로 한 건으로 합친다."""
import asyncio
import html
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

from .. import db
from ..providers import http
from . import extract as E

log = logging.getLogger("vc.collect")
FEEDS = [
    ("벤처스퀘어", "https://www.venturesquare.net/feed"),
    ("스타트업투데이", "https://www.startuptoday.kr/rss/allArticle.xml"),
    ("비석세스", "https://www.besuccess.com/feed/"),
    ("스타트업엔", "https://www.startupn.kr/rss/allArticle.xml"),
]
GOOGLE_QUERIES = ["스타트업 투자 유치", "시리즈A 투자 유치", "시리즈B 투자 유치", "시리즈C 투자 유치", "프리A 투자 유치",
                  "시드 투자 유치", "프리IPO 투자 유치", "스타트업 인수", "벤처펀드 결성", "투자조합 결성", "팁스 선정 스타트업"]
BODY_SELECTORS = [r'id="article-view-content-div"[^>]*>(.*?)</article>', r'itemprop="articleBody"[^>]*>(.*?)</div>\s*</div>',
                  r'class="entry-content[^"]*"[^>]*>(.*?)</div>\s*(?:<footer|<div class="(?:post-tags|sharedaddy))']


def parse_rss(text: str) -> list[dict]:
    """정규식 기반 RSS 파서. 일부 매체 피드가 XML로는 깨져 있어 표준 파서를 쓰지 않는다."""
    out = []
    for m in re.finditer(r"<item\b[^>]*>(.*?)</item>", text, re.S):
        d: dict[str, str] = {}
        for t in re.finditer(r"<([\w:]+)\b[^>]*>(.*?)</\1>", m.group(1), re.S):
            v = re.sub(r"^<!\[CDATA\[(.*)\]\]>$", r"\1", t.group(2).strip(), flags=re.S)
            d.setdefault(t.group(1), v)
        out.append(d)
    return out


def _date(s: str | None) -> str:
    if not s:
        return datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        dt = parsedate_to_datetime(s)
        return (dt.astimezone(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return s[:16]


async def _fetch_body(url: str) -> str:
    try:
        text = await http.get_text(url)
    except Exception:
        return ""
    for pat in BODY_SELECTORS:
        m = re.search(pat, text, re.S)
        if m:
            return E.clean_text(m.group(1))[:6000]
    return ""


def _store_article(url, source, title, summary, body, published) -> int | None:
    if db.val("SELECT 1 FROM articles WHERE url=?", (url,)):
        return None
    kind = E.classify(title)
    return db.ex("INSERT INTO articles(url,source,title,summary,body,published,kind,sentiment,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                 (url, source, title, summary[:500], body, published, kind, E.sentiment(title + " " + summary), db.now()))


async def collect_feeds() -> int:
    new = 0
    for source, url in FEEDS:
        try:
            items = parse_rss(await http.get_text(url))
        except Exception as e:
            log.warning("feed %s: %r", source, e)
            continue
        for it in items:
            link = html.unescape(it.get("link") or "").strip()
            title = html.unescape(E.clean_text(it.get("title") or ""))
            if not link or not title or db.val("SELECT 1 FROM articles WHERE url=?", (link,)):
                continue
            body = E.clean_text(it.get("content:encoded") or "")
            summary = E.clean_text(it.get("description") or "")
            if not body and E.classify(title) != "general":
                body = await _fetch_body(link)
            if _store_article(link, source, title, summary, body or summary, _date(it.get("pubDate"))):
                new += 1
    return new


async def collect_google(queries: list[str] | None = None, window: str = "when:3d") -> int:
    new = 0
    for q in queries or GOOGLE_QUERIES:
        url = f"https://news.google.com/rss/search?q={quote(q + ' ' + window)}&hl=ko&gl=KR&ceid=KR:ko"
        try:
            items = parse_rss(await http.get_text(url))
        except Exception as e:
            log.warning("google %s: %r", q, e)
            continue
        for it in items:
            link = html.unescape(it.get("link") or "").strip()
            raw = html.unescape(it.get("title") or "")
            source = html.unescape(it.get("source") or "") or "구글 뉴스"
            title = re.sub(r"\s+-\s+" + re.escape(source) + r"$", "", raw).strip()
            if not link or not title:
                continue
            if E.classify(title) == "general":
                continue
            if _store_article(link, source, title, "", "", _date(it.get("pubDate"))):
                new += 1
        await asyncio.sleep(1.0)
    return new


async def backfill(months: int = 24) -> int:
    """구글 뉴스 검색을 월 단위로 끊어 과거 기사를 채운다 (최초 1회)."""
    total = 0
    now = datetime.now()
    y, m = now.year, now.month
    for _ in range(months):
        start = f"{y}-{m:02d}-01"
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        end = f"{ny}-{nm:02d}-01"
        total += await collect_google(window=f"after:{start} before:{end}")
        process()
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    db.set_setting("vc_backfill_done", db.now())
    return total


def get_company(name: str, context: str = "") -> int:
    norm = E.norm_name(name)
    cid = db.val("SELECT id FROM companies WHERE name_norm=?", (norm,))
    if cid:
        return cid
    return db.ex("INSERT INTO companies(name,name_norm,category,status,created_at) VALUES(?,?,?,?,?)",
                 (name, norm, E.guess_category(context), "운영 중", db.now()))


def get_investor(name: str) -> int:
    norm = E.norm_name(name)
    iid = db.val("SELECT id FROM investors WHERE name_norm=?", (norm,))
    if iid:
        return iid
    kind = ("액셀러레이터" if re.search(r"액셀러레이터|엔젤|랩스?$|파운더스", name) else
            "CVC·기업" if not E.INVESTOR_SUFFIX.search(name) else
            "금융기관" if re.search(r"증권|은행|자산운용|금융|보증기금", name) else
            "공공기관" if re.search(r"공사|재단|기금|기술지주", name) else "벤처캐피탈")
    return db.ex("INSERT INTO investors(name,name_norm,type,created_at) VALUES(?,?,?,?)", (name, norm, kind, db.now()))


def _merge_deal(cid: int, date: str, info: dict, article: dict) -> int:
    """같은 회사의 ±45일 안 같은 라운드(또는 라운드 미상)는 한 건으로 본다."""
    d0 = datetime.fromisoformat(date[:10])
    lo, hi = (d0 - timedelta(days=45)).strftime("%Y-%m-%d"), (d0 + timedelta(days=45)).strftime("%Y-%m-%d")
    kind = "mna" if info["kind"] == "mna" else "investment"
    if info.get("amount"):
        lo3, hi3 = (d0 - timedelta(days=3)).strftime("%Y-%m-%d"), (d0 + timedelta(days=3)).strftime("%Y-%m-%d")
        dup = db.val("SELECT id FROM deals WHERE kind=? AND amount=? AND date BETWEEN ? AND ? AND company_id<>?",
                     (kind, info["amount"], lo3, hi3, cid))
        if dup:
            return dup
    cands = db.q("SELECT * FROM deals WHERE company_id=? AND kind=? AND date BETWEEN ? AND ?", (cid, kind, lo, hi))
    hit = None
    for c in cands:
        if not info.get("round") or not c["round"] or c["round"] == info["round"]:
            hit = c
            break
    if hit:
        db.ex("UPDATE deals SET round=COALESCE(round,?), amount=COALESCE(amount,?), amount_text=COALESCE(amount_text,?), "
              "valuation=COALESCE(valuation,?), date=MIN(date,?) WHERE id=?",
              (info.get("round"), info.get("amount"), info.get("amount_text"), info.get("valuation"), date[:10], hit["id"]))
        return hit["id"]
    return db.ex("INSERT INTO deals(company_id,date,round,kind,amount,amount_text,valuation,acquirer,source_url,article_id,title,"
                 "created_at,foreign_deal) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (cid, date[:10], info.get("round"), kind, info.get("amount"), info.get("amount_text"), info.get("valuation"),
                  info.get("acquirer"), article["url"], article["id"], article["title"], db.now(), 1 if info.get("foreign") else 0))


def process(limit: int = 5000) -> dict:
    """아직 처리하지 않은 기사에서 라운드·펀드를 추출한다."""
    stats = dict(articles=0, deals=0, funds=0)
    for a in db.q("SELECT * FROM articles WHERE processed=0 ORDER BY published LIMIT ?", (limit,)):
        stats["articles"] += 1
        company_ids = []
        try:
            info = E.extract(a["title"], a["body"] or "")
        except Exception as e:
            log.warning("extract %s: %r", a["id"], e)
            info = None
        if info and info["kind"] == "fund":
            norm = E.norm_name(info["fund_name"]) + "|" + (a["published"] or "")[:7]
            if not db.val("SELECT 1 FROM funds WHERE name_norm=?", (norm,)):
                inv_id = get_investor(info["manager"]) if info.get("manager") else None
                db.ex("INSERT INTO funds(name,name_norm,investor_id,size,size_text,date,source_url,article_id,title,created_at) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?)", (info["fund_name"], norm, inv_id, info.get("amount"), info.get("amount_text"),
                                                      (a["published"] or "")[:10], a["url"], a["id"], a["title"], db.now()))
                stats["funds"] += 1
        elif info:
            cid = get_company(info["company"], a["title"] + " " + (a["body"] or "")[:300])
            company_ids.append(cid)
            before = db.val("SELECT COUNT(*) FROM deals")
            did = _merge_deal(cid, a["published"] or datetime.now().strftime("%Y-%m-%d"), info, a)
            stats["deals"] += db.val("SELECT COUNT(*) FROM deals") - before
            for name, lead in info.get("investors") or []:
                iid = get_investor(name)
                db.ex("INSERT INTO deal_investors(deal_id,investor_id,lead) VALUES(?,?,?) "
                      "ON CONFLICT(deal_id,investor_id) DO UPDATE SET lead=MAX(lead,excluded.lead)", (did, iid, 1 if lead else 0))
            if a["body"] and not db.val("SELECT description FROM companies WHERE id=?", (cid,)):
                m = re.search(r"[^.]*" + re.escape(info["company"]) + r"[^.]{10,160}(?:다|음)\.", a["body"][:900])
                if m:
                    db.ex("UPDATE companies SET description=? WHERE id=?", (m.group(0).strip()[:300], cid))
        else:
            # 일반 기사: 이미 아는 회사가 제목 주어로 나오면 연결해 둔다
            name = E.company_from_title(a["title"])
            if name:
                cid = db.val("SELECT id FROM companies WHERE name_norm=?", (E.norm_name(name),))
                if cid:
                    company_ids.append(cid)
        db.ex("UPDATE articles SET processed=1, company_ids=? WHERE id=?", (json.dumps(company_ids), a["id"]))
    refresh_rollups()
    return stats


def refresh_rollups():
    c = db.conn()
    c.execute("""UPDATE companies SET
        total_raised=(SELECT COALESCE(SUM(amount),0) FROM deals d WHERE d.company_id=companies.id AND d.kind='investment'),
        deal_count=(SELECT COUNT(*) FROM deals d WHERE d.company_id=companies.id),
        last_deal_date=(SELECT MAX(date) FROM deals d WHERE d.company_id=companies.id),
        last_round=(SELECT round FROM deals d WHERE d.company_id=companies.id AND d.round IS NOT NULL ORDER BY date DESC LIMIT 1),
        valuation=(SELECT valuation FROM deals d WHERE d.company_id=companies.id AND d.valuation IS NOT NULL ORDER BY date DESC LIMIT 1),
        foreign_co=COALESCE((SELECT MIN(foreign_deal) FROM deals d WHERE d.company_id=companies.id), 0)""")
    c.execute("""UPDATE investors SET
        deal_count=(SELECT COUNT(*) FROM deal_investors di WHERE di.investor_id=investors.id),
        total_amount=(SELECT COALESCE(SUM(d.amount),0) FROM deal_investors di JOIN deals d ON d.id=di.deal_id WHERE di.investor_id=investors.id),
        last_deal_date=(SELECT MAX(d.date) FROM deal_investors di JOIN deals d ON d.id=di.deal_id WHERE di.investor_id=investors.id)""")


async def run_once() -> dict:
    a = await collect_feeds()
    b = await collect_google()
    st = process()
    return dict(new_articles=a + b, **st)
