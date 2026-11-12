"""스타트업 투자 DB: 투자/M&A, 스타트업, 투자자, 펀드, 뉴스, IR, 지원사업, 통계, 컬렉션."""
import csv
import io
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import Response

from .. import auth, db
from ..vc import enrich

router = APIRouter(prefix="/api/vc")
U = Depends(auth.current_user)
PAGE = 50
ROUND_ORDER = ["Pre-Seed", "Seed", "TIPS", "Pre-A", "Series A", "Series A Bridge", "Pre-B", "Series B", "Series B Bridge",
               "Pre-C", "Series C", "Series D", "Series E", "Series F", "Series G", "Bridge", "SI", "Pre-IPO", "M&A"]


def _deal_rows(where: list[str], params: list, order: str, limit: int, offset: int = 0) -> list[dict]:
    rows = db.q("SELECT d.*, c.name company, c.category FROM deals d JOIN companies c ON c.id=d.company_id "
                f"WHERE {' AND '.join(where) or '1=1'} ORDER BY {order} LIMIT ? OFFSET ?", (*params, limit, offset))
    if rows:
        ph = ",".join("?" * len(rows))
        inv: dict[int, list] = {}
        for r in db.q(f"SELECT di.deal_id, i.id, i.name, di.lead FROM deal_investors di JOIN investors i ON i.id=di.investor_id "
                      f"WHERE di.deal_id IN ({ph}) ORDER BY di.lead DESC, i.name", [r["id"] for r in rows]):
            inv.setdefault(r["deal_id"], []).append(dict(id=r["id"], name=r["name"], lead=bool(r["lead"])))
        for r in rows:
            r["investors"] = inv.get(r["id"], [])
    return rows


def _num(v, label):
    try:
        return float(v)
    except (ValueError, TypeError):
        raise HTTPException(400, f"{label}은 숫자로 넣어 주세요")


def _deal_filter(kind, round_, q, min_amount, max_amount, date_from, date_to, category, investor_id, region="kr"):
    where, params = [], []
    if region == "kr":
        where.append("d.foreign_deal=0")
    elif region == "global":
        where.append("d.foreign_deal=1")
    if kind:
        where.append("d.kind=?")
        params.append(kind)
    if round_:
        rs = round_.split(",")
        where.append(f"d.round IN ({','.join('?' * len(rs))})")
        params += rs
    if q:
        where.append("(c.name LIKE ? OR d.title LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if min_amount not in (None, ""):
        where.append("d.amount>=?")
        params.append(_num(min_amount, "최소 금액") * 1e8)
    if max_amount not in (None, ""):
        where.append("d.amount<=?")
        params.append(_num(max_amount, "최대 금액") * 1e8)
    if date_from:
        where.append("d.date>=?")
        params.append(date_from)
    if date_to:
        where.append("d.date<=?")
        params.append(date_to)
    if category:
        where.append("c.category=?")
        params.append(category)
    if investor_id:
        where.append("d.id IN (SELECT deal_id FROM deal_investors WHERE investor_id=?)")
        params.append(int(investor_id))
    return where, params


@router.get("/meta")
def meta(user=U):
    rounds = [r["round"] for r in db.q("SELECT DISTINCT round FROM deals WHERE round IS NOT NULL")]
    rounds.sort(key=lambda r: ROUND_ORDER.index(r) if r in ROUND_ORDER else 99)
    return dict(
        rounds=rounds,
        categories=[r["category"] for r in db.q("SELECT category, COUNT(*) n FROM companies WHERE category IS NOT NULL GROUP BY 1 ORDER BY n DESC")],
        investor_types=[r["type"] for r in db.q("SELECT type, COUNT(*) n FROM investors GROUP BY 1 ORDER BY n DESC")],
        grant_categories=[r["category"] for r in db.q("SELECT category, COUNT(*) n FROM grants WHERE category IS NOT NULL GROUP BY 1 ORDER BY n DESC")],
        keys={k: bool(v) for k, v in enrich.keys().items()},
        range=db.one("SELECT MIN(date) first, MAX(date) last, COUNT(*) n FROM deals"))


@router.get("/deals")
def deals(kind: str = "", round_: str = "", q: str = "", min_amount: str = "", max_amount: str = "", date_from: str = "",
          date_to: str = "", category: str = "", investor_id: str = "", region: str = "kr", sort: str = "date", page: int = 1, user=U):
    where, params = _deal_filter(kind, round_, q, min_amount, max_amount, date_from, date_to, category, investor_id, region)
    order = {"date": "d.date DESC, d.id DESC", "amount": "d.amount IS NULL, d.amount DESC"}.get(sort, "d.date DESC, d.id DESC")
    w = " AND ".join(where) or "1=1"
    agg = db.one(f"SELECT COUNT(*) n, COALESCE(SUM(d.amount),0) amount FROM deals d JOIN companies c ON c.id=d.company_id WHERE {w}", params)
    return dict(total=agg["n"], amount=agg["amount"], rows=_deal_rows(where, params, order, PAGE, (page - 1) * PAGE))


@router.get("/deals.csv")
def deals_csv(kind: str = "", round_: str = "", q: str = "", min_amount: str = "", max_amount: str = "", date_from: str = "",
              date_to: str = "", category: str = "", investor_id: str = "", region: str = "kr", user=U):
    where, params = _deal_filter(kind, round_, q, min_amount, max_amount, date_from, date_to, category, investor_id, region)
    rows = _deal_rows(where, params, "d.date DESC", 5000)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["날짜", "기업", "분야", "구분", "단계", "금액(원)", "금액 표기", "투자자", "출처"])
    for r in rows:
        w.writerow([r["date"], r["company"], r["category"] or "", "M&A" if r["kind"] == "mna" else "투자", r["round"] or "",
                    int(r["amount"]) if r["amount"] else "", r["amount_text"] or "",
                    ", ".join(i["name"] for i in r["investors"]), r["source_url"]])
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=deals.csv"})


@router.get("/companies")
def companies(q: str = "", category: str = "", round_: str = "", min_raised: str = "", has_deal: int = 1, sort: str = "recent",
              page: int = 1, region: str = "kr", user=U):
    where, params = [], []
    if region == "kr":
        where.append("COALESCE(foreign_co,0)=0")
    if q:
        where.append("(name LIKE ? OR description LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if category:
        where.append("category=?")
        params.append(category)
    if round_:
        where.append("last_round=?")
        params.append(round_)
    if min_raised not in (None, ""):
        where.append("total_raised>=?")
        params.append(float(min_raised) * 1e8)
    if has_deal:
        where.append("deal_count>0")
    w = " AND ".join(where) or "1=1"
    order = {"recent": "last_deal_date DESC", "raised": "total_raised DESC", "name": "name", "deals": "deal_count DESC"}.get(sort, "last_deal_date DESC")
    return dict(total=db.val(f"SELECT COUNT(*) FROM companies WHERE {w}", params),
                rows=db.q(f"SELECT id,name,description,category,founded,ceo,employees,total_raised,deal_count,last_round,last_deal_date,"
                          f"status,homepage,valuation,foreign_co FROM companies WHERE {w} ORDER BY {order} LIMIT ? OFFSET ?", (*params, PAGE, (page - 1) * PAGE)))


@router.get("/companies/{cid}")
def company(cid: int, user=U):
    c = db.one("SELECT * FROM companies WHERE id=?", (cid,))
    if not c:
        raise HTTPException(404, "기업을 찾을 수 없습니다")
    c["extra"] = json.loads(c["extra"] or "{}")
    deal_rows = _deal_rows(["d.company_id=?"], [cid], "d.date DESC", 100)
    news = db.q("SELECT id,url,source,title,published,kind,sentiment FROM articles WHERE company_ids LIKE ? OR company_ids LIKE ? "
                "OR company_ids LIKE ? OR company_ids=? ORDER BY published DESC LIMIT 40",
                (f"[{cid},%", f"%, {cid},%", f"%, {cid}]", f"[{cid}]"))
    investors = db.q("SELECT i.id,i.name,i.type,COUNT(*) n FROM deal_investors di JOIN investors i ON i.id=di.investor_id "
                     "JOIN deals d ON d.id=di.deal_id WHERE d.company_id=? GROUP BY i.id ORDER BY n DESC, i.name", (cid,))
    similar_rows = db.q("SELECT id,name,category,total_raised,last_round,last_deal_date FROM companies WHERE category=? AND id<>? "
                        "AND deal_count>0 ORDER BY ABS(total_raised-?) LIMIT 8", (c["category"], cid, c["total_raised"] or 0)) if c["category"] else []
    return dict(company=c, deals=deal_rows, news=news, investors=investors, similar=similar_rows,
                financials=db.q("SELECT * FROM company_financials WHERE company_id=? ORDER BY year", (cid,)),
                analysis=enrich.financial_analysis(cid),
                employment=db.q("SELECT * FROM company_employment WHERE company_id=? ORDER BY ym", (cid,)),
                filings=db.q("SELECT title,date,detail url FROM company_records WHERE company_id=? AND kind='filing' ORDER BY date DESC LIMIT 30", (cid,)),
                collections=[r["collection_id"] for r in db.q(
                    "SELECT ci.collection_id FROM collection_items ci JOIN collections c ON c.id=ci.collection_id "
                    "WHERE c.user_id=? AND ci.entity_type='company' AND ci.entity_id=?", (user["id"], cid))])


@router.post("/companies/{cid}/enrich")
async def company_enrich(cid: int, user=U):
    return await enrich.enrich(cid)


@router.get("/compare")
def compare(ids: str, user=U):
    out = []
    for cid in [int(x) for x in ids.split(",") if x.isdigit()][:4]:
        c = db.one("SELECT id,name,category,founded,ceo,employees,total_raised,deal_count,last_round,last_deal_date FROM companies WHERE id=?", (cid,))
        if c:
            c["financials"] = db.q("SELECT year,revenue,op_income,net_income FROM company_financials WHERE company_id=? ORDER BY year", (cid,))
            c["deals"] = db.q("SELECT date,round,amount,amount_text FROM deals WHERE company_id=? ORDER BY date", (cid,))
            out.append(c)
    return out


@router.get("/investors")
def investors(q: str = "", type_: str = "", sort: str = "deals", page: int = 1, user=U):
    where, params = ["deal_count>0"], []
    if q:
        where.append("name LIKE ?")
        params.append(f"%{q}%")
    if type_:
        where.append("type=?")
        params.append(type_)
    w = " AND ".join(where)
    order = {"deals": "deal_count DESC", "amount": "total_amount DESC", "recent": "last_deal_date DESC", "name": "name"}.get(sort, "deal_count DESC")
    rows = db.q(f"SELECT * FROM investors WHERE {w} ORDER BY {order} LIMIT ? OFFSET ?", (*params, PAGE, (page - 1) * PAGE))
    for r in rows:
        r["portfolio"] = [x["name"] for x in db.q(
            "SELECT DISTINCT c.name FROM deal_investors di JOIN deals d ON d.id=di.deal_id JOIN companies c ON c.id=d.company_id "
            "WHERE di.investor_id=? ORDER BY d.date DESC LIMIT 4", (r["id"],))]
    return dict(total=db.val(f"SELECT COUNT(*) FROM investors WHERE {w}", params), rows=rows)


@router.get("/investors/{iid}")
def investor(iid: int, user=U):
    i = db.one("SELECT * FROM investors WHERE id=?", (iid,))
    if not i:
        raise HTTPException(404, "투자자를 찾을 수 없습니다")
    sub = "d.id IN (SELECT deal_id FROM deal_investors WHERE investor_id=?)"
    return dict(
        investor=i, deals=_deal_rows([sub], [iid], "d.date DESC", 200),
        by_round=db.q(f"SELECT COALESCE(d.round,'미상') round, COUNT(*) n, COALESCE(SUM(d.amount),0) amount FROM deals d WHERE {sub} GROUP BY 1 ORDER BY n DESC", (iid,)),
        by_category=db.q(f"SELECT COALESCE(c.category,'기타') category, COUNT(*) n FROM deals d JOIN companies c ON c.id=d.company_id WHERE {sub} GROUP BY 1 ORDER BY n DESC", (iid,)),
        co_investors=db.q("SELECT i.id,i.name,COUNT(*) n FROM deal_investors a JOIN deal_investors b ON a.deal_id=b.deal_id AND b.investor_id<>a.investor_id "
                          "JOIN investors i ON i.id=b.investor_id WHERE a.investor_id=? GROUP BY i.id ORDER BY n DESC LIMIT 15", (iid,)),
        funds=db.q("SELECT * FROM funds WHERE investor_id=? ORDER BY date DESC", (iid,)),
        by_year=db.q(f"SELECT substr(d.date,1,4) year, COUNT(*) n, COALESCE(SUM(d.amount),0) amount FROM deals d WHERE {sub} GROUP BY 1 ORDER BY 1", (iid,)))


@router.get("/funds")
def funds(q: str = "", page: int = 1, user=U):
    where, params = "1=1", []
    if q:
        where, params = "(f.name LIKE ? OR i.name LIKE ? OR f.title LIKE ?)", [f"%{q}%"] * 3
    return dict(total=db.val(f"SELECT COUNT(*) FROM funds f LEFT JOIN investors i ON i.id=f.investor_id WHERE {where}", params),
                rows=db.q(f"SELECT f.*, i.name manager FROM funds f LEFT JOIN investors i ON i.id=f.investor_id WHERE {where} "
                          "ORDER BY f.date DESC LIMIT ? OFFSET ?", (*params, PAGE, (page - 1) * PAGE)))


@router.get("/news")
def news(kind: str = "", sentiment: str = "", q: str = "", page: int = 1, user=U):
    where, params = [], []
    if kind:
        where.append("kind=?")
        params.append(kind)
    if sentiment:
        where.append("sentiment=?")
        params.append(sentiment)
    if q:
        where.append("title LIKE ?")
        params.append(f"%{q}%")
    w = " AND ".join(where) or "1=1"
    rows = db.q(f"SELECT id,url,source,title,summary,published,kind,sentiment,company_ids FROM articles WHERE {w} "
                "ORDER BY published DESC LIMIT ? OFFSET ?", (*params, PAGE, (page - 1) * PAGE))
    for r in rows:
        ids = json.loads(r.pop("company_ids") or "[]")
        r["companies"] = db.q(f"SELECT id,name FROM companies WHERE id IN ({','.join('?' * len(ids))})", ids) if ids else []
    return dict(total=db.val(f"SELECT COUNT(*) FROM articles WHERE {w}", params), rows=rows)


@router.get("/grants")
def grants(q: str = "", category: str = "", open_only: int = 1, page: int = 1, user=U):
    where, params = [], []
    today = datetime.now().strftime("%Y-%m-%d")
    if q:
        where.append("(title LIKE ? OR org LIKE ? OR target LIKE ?)")
        params += [f"%{q}%"] * 3
    if category:
        where.append("category=?")
        params.append(category)
    if open_only:
        where.append("(end_date IS NULL OR end_date>=?)")
        params.append(today)
    w = " AND ".join(where) or "1=1"
    by_month = db.q("SELECT substr(end_date,1,7) month, COUNT(*) n FROM grants WHERE end_date>=? GROUP BY 1 ORDER BY 1 LIMIT 8", (today,))
    return dict(total=db.val(f"SELECT COUNT(*) FROM grants WHERE {w}", params), by_month=by_month, today=today,
                by_category=db.q("SELECT category, COUNT(*) n FROM grants WHERE category IS NOT NULL AND (end_date IS NULL OR end_date>=?) GROUP BY 1 ORDER BY n DESC", (today,)),
                rows=db.q(f"SELECT * FROM grants WHERE {w} ORDER BY end_date IS NULL, end_date LIMIT ? OFFSET ?", (*params, PAGE, (page - 1) * PAGE)))


@router.patch("/deals/{did}")
def deal_fix(did: int, p: dict = Body(...), user=Depends(auth.admin_user)):
    """자동 추출이 틀린 딜 바로잡기: 해외 표시, 단계·금액 수정, 삭제."""
    if p.get("delete"):
        db.ex("DELETE FROM deal_investors WHERE deal_id=?", (did,))
        db.ex("DELETE FROM deals WHERE id=?", (did,))
    else:
        for k in ("foreign_deal", "round", "amount", "amount_text", "valuation", "date"):
            if k in p:
                db.ex(f"UPDATE deals SET {k}=? WHERE id=?", (p[k], did))
    from ..vc import collect
    collect.refresh_rollups()
    return dict(ok=True)


@router.get("/stats")
def stats(months: int = 12, user=U):
    start = (datetime.now() - timedelta(days=31 * months)).strftime("%Y-%m-01")
    inv = "kind='investment' AND foreign_deal=0 AND date>=?"
    return dict(
        start=start,
        total=db.one(f"SELECT COUNT(*) n, COALESCE(SUM(amount),0) amount, SUM(amount IS NULL) undisclosed FROM deals WHERE {inv}", (start,)),
        monthly=db.q(f"SELECT substr(date,1,7) month, COUNT(*) n, COALESCE(SUM(amount),0) amount FROM deals WHERE {inv} GROUP BY 1 ORDER BY 1", (start,)),
        by_round=db.q(f"SELECT COALESCE(round,'미상') round, COUNT(*) n, COALESCE(SUM(amount),0) amount FROM deals WHERE {inv} GROUP BY 1 ORDER BY n DESC", (start,)),
        by_category=db.q("SELECT COALESCE(c.category,'기타') category, COUNT(*) n, COALESCE(SUM(d.amount),0) amount FROM deals d "
                         "JOIN companies c ON c.id=d.company_id WHERE d.kind='investment' AND d.foreign_deal=0 AND d.date>=? GROUP BY 1 ORDER BY amount DESC", (start,)),
        top_deals=_deal_rows(["d.kind='investment'", "d.foreign_deal=0", "d.date>=?", "d.amount IS NOT NULL"], [start], "d.amount DESC", 15),
        top_investors=db.q("SELECT i.id,i.name,i.type,COUNT(*) n,COALESCE(SUM(d.amount),0) amount FROM deal_investors di "
                           "JOIN deals d ON d.id=di.deal_id JOIN investors i ON i.id=di.investor_id WHERE d.foreign_deal=0 AND d.date>=? GROUP BY i.id "
                           "ORDER BY n DESC LIMIT 15", (start,)),
        mna=db.one("SELECT COUNT(*) n, COALESCE(SUM(amount),0) amount FROM deals WHERE kind='mna' AND foreign_deal=0 AND date>=?", (start,)),
        foreign=db.one("SELECT COUNT(*) n, COALESCE(SUM(amount),0) amount FROM deals WHERE foreign_deal=1 AND date>=?", (start,)),
        funds=db.one("SELECT COUNT(*) n, COALESCE(SUM(size),0) amount FROM funds WHERE date>=?", (start,)),
        size_buckets=db.q(f"SELECT CASE WHEN amount<1e9 THEN '10억 미만' WHEN amount<5e9 THEN '10억~50억' WHEN amount<1e10 THEN '50억~100억' "
                          f"WHEN amount<3e10 THEN '100억~300억' WHEN amount<1e11 THEN '300억~1,000억' ELSE '1,000억 이상' END bucket, "
                          f"COUNT(*) n, MIN(amount) lo FROM deals WHERE {inv} AND amount IS NOT NULL GROUP BY 1 ORDER BY lo", (start,)))


# ── IR ─────────────────────────────────────────────────────────────────
@router.get("/ir")
def ir_list(user=U):
    rows = db.q("SELECT r.*, u.nickname FROM ir_rounds r JOIN users u ON u.id=r.user_id ORDER BY r.status='open' DESC, r.id DESC")
    for r in rows:
        r["mine"] = r["user_id"] == user["id"]
    return rows


@router.post("/ir")
def ir_save(p: dict = Body(...), user=U):
    name = (p.get("company_name") or "").strip()
    if not name:
        raise HTTPException(400, "기업명을 입력해 주세요")
    vals = (name[:60], p.get("round") or "", p.get("target_amount"), p.get("valuation"), p.get("description") or "",
            p.get("deck_url") or "", p.get("contact") or "", p.get("status") or "open")
    if p.get("id"):
        db.ex("UPDATE ir_rounds SET company_name=?,round=?,target_amount=?,valuation=?,description=?,deck_url=?,contact=?,status=? "
              "WHERE id=? AND user_id=?", (*vals, p["id"], user["id"]))
        return dict(id=p["id"])
    return dict(id=db.ex("INSERT INTO ir_rounds(user_id,company_name,round,target_amount,valuation,description,deck_url,contact,status,created_at) "
                         "VALUES(?,?,?,?,?,?,?,?,?,?)", (user["id"], *vals, db.now())))


@router.delete("/ir/{rid}")
def ir_delete(rid: int, user=U):
    db.ex("DELETE FROM ir_rounds WHERE id=? AND user_id=?", (rid, user["id"]))
    return dict(ok=True)


# ── 컬렉션 ─────────────────────────────────────────────────────────────
def _smart_rows(spec: dict) -> list[dict]:
    res = companies(q=spec.get("q", ""), category=spec.get("category", ""), round_=spec.get("round", ""),
                    min_raised=spec.get("min_raised", ""), has_deal=1, sort=spec.get("sort", "recent"), page=1, user=None)
    return res["rows"]


@router.get("/collections")
def collections(user=U):
    rows = db.q("SELECT * FROM collections WHERE user_id=? ORDER BY id DESC", (user["id"],))
    for r in rows:
        r["smart_spec"] = json.loads(r["smart_spec"]) if r["smart_spec"] else None
        r["count"] = len(_smart_rows(r["smart_spec"])) if r["smart_spec"] else db.val(
            "SELECT COUNT(*) FROM collection_items WHERE collection_id=?", (r["id"],))
    return rows


@router.post("/collections")
def collection_save(p: dict = Body(...), user=U):
    name = (p.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "컬렉션 이름을 입력해 주세요")
    spec = json.dumps(p["smart_spec"]) if p.get("smart_spec") else None
    if p.get("id"):
        db.ex("UPDATE collections SET name=?, description=?, smart_spec=? WHERE id=? AND user_id=?",
              (name[:40], p.get("description") or "", spec, p["id"], user["id"]))
        return dict(id=p["id"])
    return dict(id=db.ex("INSERT INTO collections(user_id,name,description,smart_spec,created_at) VALUES(?,?,?,?,?)",
                         (user["id"], name[:40], p.get("description") or "", spec, db.now())))


@router.get("/collections/{cid}")
def collection(cid: int, user=U):
    c = db.one("SELECT * FROM collections WHERE id=? AND user_id=?", (cid, user["id"]))
    if not c:
        raise HTTPException(404, "컬렉션을 찾을 수 없습니다")
    c["smart_spec"] = json.loads(c["smart_spec"]) if c["smart_spec"] else None
    if c["smart_spec"]:
        return dict(collection=c, companies=_smart_rows(c["smart_spec"]), investors=[])
    comp = db.q("SELECT c.id,c.name,c.category,c.total_raised,c.deal_count,c.last_round,c.last_deal_date FROM collection_items ci "
                "JOIN companies c ON c.id=ci.entity_id WHERE ci.collection_id=? AND ci.entity_type='company' ORDER BY ci.added_at DESC", (cid,))
    inv = db.q("SELECT i.id,i.name,i.type,i.deal_count,i.last_deal_date FROM collection_items ci JOIN investors i ON i.id=ci.entity_id "
               "WHERE ci.collection_id=? AND ci.entity_type='investor' ORDER BY ci.added_at DESC", (cid,))
    return dict(collection=c, companies=comp, investors=inv)


@router.post("/collections/{cid}/toggle")
def collection_toggle(cid: int, p: dict = Body(...), user=U):
    if not db.val("SELECT 1 FROM collections WHERE id=? AND user_id=? AND smart_spec IS NULL", (cid, user["id"])):
        raise HTTPException(404, "담을 수 있는 컬렉션이 아닙니다")
    et, eid = p.get("entity_type"), int(p.get("entity_id") or 0)
    if et not in ("company", "investor"):
        raise HTTPException(400, "대상을 확인해 주세요")
    if db.val("SELECT 1 FROM collection_items WHERE collection_id=? AND entity_type=? AND entity_id=?", (cid, et, eid)):
        db.ex("DELETE FROM collection_items WHERE collection_id=? AND entity_type=? AND entity_id=?", (cid, et, eid))
        return dict(added=False)
    db.ex("INSERT INTO collection_items(collection_id,entity_type,entity_id,added_at) VALUES(?,?,?,?)", (cid, et, eid, db.now()))
    return dict(added=True)


@router.delete("/collections/{cid}")
def collection_delete(cid: int, user=U):
    if db.val("SELECT 1 FROM collections WHERE id=? AND user_id=?", (cid, user["id"])):
        db.ex("DELETE FROM collection_items WHERE collection_id=?", (cid,))
        db.ex("DELETE FROM collections WHERE id=?", (cid,))
    return dict(ok=True)
