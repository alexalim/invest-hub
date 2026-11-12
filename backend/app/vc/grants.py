"""지원사업 공고 수집. K-Startup 공개 목록 페이지에서 모집 중인 공고를 읽는다.
공공데이터포털 키가 있으면 같은 공고를 API로도 받을 수 있지만, 키 없이도 동작하도록 페이지 수집을 기본으로 한다."""
import logging
import re

from .. import db
from ..providers import http
from .extract import clean_text

log = logging.getLogger("vc.grants")
LIST = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do"
VIEW = LIST + "?schM=view&pbancSn={}"


def parse_list(text: str) -> list[dict]:
    out = {}
    for m in re.finditer(r"go_view\((\d+)\);?['\"]>(.*?)</a>", text, re.S):
        gid, block = m.group(1), m.group(2)
        title = re.search(r'<p class="tit">(.*?)</p>', block, re.S)
        if not title:
            continue
        t = clean_text(re.sub(r'<span class="new">.*?</span>', "", title.group(1), flags=re.S))
        flags = [clean_text(x) for x in re.findall(r'<span class="flag[^"]*">(.*?)</span>', block, re.S)]
        end = re.search(r"마감일자\s*(\d{4}-\d{2}-\d{2})", block)
        lis = [clean_text(x) for x in re.findall(r"<li>(.*?)</li>", block, re.S)]
        out[gid] = dict(ext_id=f"kstartup:{gid}", title=t, category=flags[0] if flags else None,
                        end_date=end.group(1) if end else None, target=lis[0] if lis else None,
                        org=lis[1] if len(lis) > 1 else None, url=VIEW.format(gid))
    return list(out.values())


async def collect(pages: int = 15) -> int:
    n = 0
    for page in range(1, pages + 1):
        try:
            text = await http.get_text(LIST, {"page": page})
        except Exception as e:
            log.warning("grants page %s: %r", page, e)
            break
        rows = parse_list(text)
        fresh = 0
        for r in rows:
            if not db.val("SELECT 1 FROM grants WHERE ext_id=?", (r["ext_id"],)):
                fresh += 1
            db.ex("INSERT INTO grants(ext_id,title,org,category,target,end_date,url,source,updated_at) VALUES(?,?,?,?,?,?,?,?,?) "
                  "ON CONFLICT(ext_id) DO UPDATE SET title=excluded.title,org=excluded.org,category=excluded.category,"
                  "end_date=excluded.end_date,updated_at=excluded.updated_at",
                  (r["ext_id"], r["title"], r["org"], r["category"], r["target"], r["end_date"], r["url"], "K-Startup", db.now()))
        n += fresh
        if not rows or (page > 1 and fresh == 0):
            break
    return n
