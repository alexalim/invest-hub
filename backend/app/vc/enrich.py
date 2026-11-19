"""기업 프로필 보강. 키가 설정된 출처만 호출한다.
- DART(전자공시): 기업 개황, 사업보고서 재무, 공시 목록  → 설정 키 dart_key
- 공공데이터포털: 금융위 기업기본정보·요약재무, 국민연금 가입 사업장(고용) → 설정 키 data_go_kr_key
주의: 공공데이터포털 연동은 키 없이 작성해 실제 응답으로 검증하지 못했다. 실패하면 오류를 기록만 하고 넘어간다."""
import io
import json
import logging
import re
import zipfile
from datetime import datetime

from .. import db
from ..providers import http
from .extract import norm_name

log = logging.getLogger("vc.enrich")


def _safe_error(e: Exception) -> str:
    """외부 호출 오류를 키 없이 짧게 적는다: 응답 코드가 있으면 코드만, 아니면 예외 종류만."""
    code = getattr(getattr(e, "response", None), "status_code", None)
    return f"HTTP {code}" if code is not None else type(e).__name__
DART = "https://opendart.fss.or.kr/api"
GO = "https://apis.data.go.kr"
ACCOUNTS = {
    "revenue": r"^(매출액|수익\(매출액\)|영업수익|매출)$", "op_income": r"^영업이익(\(손실\))?$",
    "net_income": r"^(당기순이익(\(손실\))?|당기순손익)$", "assets": r"^자산총계$", "liabilities": r"^부채총계$",
    "equity": r"^자본총계$", "current_assets": r"^유동자산$", "current_liab": r"^유동부채$", "cash": r"^현금및현금성자산$",
}


def keys() -> dict:
    return dict(dart=db.get_setting("dart_key"), go=db.get_setting("data_go_kr_key"))


def _items(text: str) -> list[dict]:
    """공공데이터포털 응답은 JSON일 수도 XML일 수도 있다."""
    try:
        body = json.loads(text)["response"]["body"]
        items = body.get("items") or {}
        if isinstance(items, dict):
            items = items.get("item") or []
        return items if isinstance(items, list) else [items]
    except Exception:
        out = []
        for m in re.finditer(r"<item>(.*?)</item>", text, re.S):
            out.append({t.group(1): t.group(2).strip() for t in re.finditer(r"<(\w+)>(.*?)</\1>", m.group(1), re.S)})
        return out


def _f(v) -> float | None:
    try:
        return float(str(v).replace(",", "")) if v not in (None, "", "-") else None
    except ValueError:
        return None


async def sync_dart_corps() -> int:
    key = keys()["dart"]
    if not key:
        return 0
    r = await http.get(f"{DART}/corpCode.xml", {"crtfc_key": key})
    z = zipfile.ZipFile(io.BytesIO(r.content))
    xml = z.read(z.namelist()[0]).decode("utf-8")
    rows = []
    for m in re.finditer(r"<list>(.*?)</list>", xml, re.S):
        d = {t.group(1): t.group(2).strip() for t in re.finditer(r"<(\w+)>(.*?)</\1>", m.group(1), re.S)}
        if d.get("corp_code") and d.get("corp_name"):
            rows.append((d["corp_code"], d["corp_name"], norm_name(d["corp_name"]), d.get("stock_code") or None))
    if rows:
        db.many("INSERT OR REPLACE INTO dart_corps(corp_code,name,name_norm,stock_code) VALUES(?,?,?,?)", rows)
        db.set_setting("dart_corps_synced", db.now())
    return len(rows)


async def _dart(company: dict, log_: list):
    key = keys()["dart"]
    if not key:
        return
    if not db.val("SELECT 1 FROM dart_corps LIMIT 1"):
        await sync_dart_corps()
    code = company.get("corp_code") or db.val(
        "SELECT corp_code FROM dart_corps WHERE name_norm=? ORDER BY stock_code IS NULL LIMIT 1", (company["name_norm"],))
    if not code:
        log_.append("DART: 일치하는 법인 없음")
        return
    d = await http.get_json(f"{DART}/company.json", {"crtfc_key": key, "corp_code": code})
    if d.get("status") != "000":
        log_.append(f"DART 개황: {d.get('message')}")
        return
    est = d.get("est_dt") or ""
    db.ex("UPDATE companies SET corp_code=?, stock_code=COALESCE(NULLIF(?,''),stock_code), ceo=COALESCE(?,ceo), "
          "founded=COALESCE(?,founded), address=COALESCE(?,address), homepage=COALESCE(NULLIF(?,''),homepage), "
          "bizno=COALESCE(?,bizno), extra=? WHERE id=?",
          (code, d.get("stock_code"), d.get("ceo_nm"), f"{est[:4]}-{est[4:6]}-{est[6:8]}" if len(est) == 8 else None,
           d.get("adres"), d.get("hm_url"), d.get("bizr_no"),
           json.dumps(dict(jurir_no=d.get("jurir_no"), induty_code=d.get("induty_code"), corp_cls=d.get("corp_cls"),
                           corp_name=d.get("corp_name")), ensure_ascii=False), company["id"]))
    log_.append("DART 개황 반영")
    year = datetime.now().year
    got = 0
    for y in range(year - 1, year - 5, -1):
        for fs in ("OFS", "CFS"):
            f = await http.get_json(f"{DART}/fnlttSinglAcntAll.json", {"crtfc_key": key, "corp_code": code, "bsns_year": y,
                                                                      "reprt_code": "11011", "fs_div": fs})
            if f.get("status") != "000":
                continue
            vals: dict[str, float] = {}
            for row in f.get("list") or []:
                nm = (row.get("account_nm") or "").replace(" ", "")
                for k, pat in ACCOUNTS.items():
                    if k not in vals and re.match(pat, nm):
                        v = _f(row.get("thstrm_amount"))
                        if v is not None:
                            vals[k] = v
            if vals:
                db.ex("INSERT OR REPLACE INTO company_financials(company_id,year,revenue,op_income,net_income,assets,liabilities,"
                      "equity,current_assets,current_liab,cash,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (company["id"], y, vals.get("revenue"), vals.get("op_income"), vals.get("net_income"), vals.get("assets"),
                       vals.get("liabilities"), vals.get("equity"), vals.get("current_assets"), vals.get("current_liab"),
                       vals.get("cash"), "DART"))
                got += 1
                break
    log_.append(f"DART 재무 {got}개 연도")
    lst = await http.get_json(f"{DART}/list.json", {"crtfc_key": key, "corp_code": code, "bgn_de": f"{year - 2}0101", "page_count": 30})
    for it in lst.get("list") or []:
        dt = it.get("rcept_dt") or ""
        db.ex("INSERT OR IGNORE INTO company_records(company_id,kind,ext_id,title,date,detail) VALUES(?,?,?,?,?,?)",
              (company["id"], "filing", it.get("rcept_no"), it.get("report_nm"), f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}",
               f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={it.get('rcept_no')}"))


async def _fsc(company: dict, log_: list):
    key = keys()["go"]
    if not key:
        return
    crno = json.loads(company.get("extra") or "{}").get("jurir_no")
    if not crno:
        text = await http.get_text(f"{GO}/1160100/service/GetCorpBasicInfoService_V2/getCorpOutline_V2",
                                   {"serviceKey": key, "resultType": "json", "numOfRows": 20, "pageNo": 1, "corpNm": company["name"]})
        cands = [i for i in _items(text) if norm_name(i.get("corpNm") or "") == company["name_norm"]]
        if not cands:
            log_.append("금융위 기업정보: 일치하는 법인 없음")
            return
        c = cands[0]
        crno = c.get("crno")
        est = c.get("enpEstbDt") or ""
        db.ex("UPDATE companies SET ceo=COALESCE(ceo,?), founded=COALESCE(founded,?), address=COALESCE(address,?), "
              "homepage=COALESCE(homepage,NULLIF(?,'')), employees=COALESCE(employees,?), bizno=COALESCE(bizno,?), extra=? WHERE id=?",
              (c.get("enpRprFnm"), f"{est[:4]}-{est[4:6]}-{est[6:8]}" if len(est) == 8 else None, c.get("enpBsadr"),
               c.get("enpHmpgUrl"), _f(c.get("enpEmpeCnt")), c.get("bzno"), json.dumps(dict(jurir_no=crno), ensure_ascii=False),
               company["id"]))
        log_.append("금융위 기업정보 반영")
    year = datetime.now().year
    got = 0
    for y in range(year - 1, year - 5, -1):
        if db.val("SELECT 1 FROM company_financials WHERE company_id=? AND year=?", (company["id"], y)):
            continue
        text = await http.get_text(f"{GO}/1160100/service/GetFinaStatInfoService_V2/getSummFinaStat_V2",
                                   {"serviceKey": key, "resultType": "json", "numOfRows": 5, "pageNo": 1, "crno": crno, "bizYear": y})
        its = _items(text)
        if not its:
            continue
        it = its[0]
        db.ex("INSERT OR REPLACE INTO company_financials(company_id,year,revenue,op_income,net_income,assets,liabilities,equity,source) "
              "VALUES(?,?,?,?,?,?,?,?,?)", (company["id"], y, _f(it.get("enpSaleAmt")), _f(it.get("enpBzopPft")),
                                             _f(it.get("enpCrtmNpf")), _f(it.get("enpTastAmt")), _f(it.get("enpTdbtAmt")),
                                             _f(it.get("enpTcptAmt")), "금융위"))
        got += 1
    log_.append(f"금융위 재무 {got}개 연도")


async def _nps(company: dict, log_: list):
    key = keys()["go"]
    if not key:
        return
    base = f"{GO}/B552015/NpsBplcInfoInqireService"
    text = await http.get_text(f"{base}/getBassInfoSearch", {"serviceKey": key, "wkpl_nm": company["name"], "numOfRows": 30, "pageNo": 1})
    its = [i for i in _items(text) if norm_name(i.get("wkplNm") or "") == company["name_norm"]]
    if not its:
        log_.append("국민연금: 일치하는 사업장 없음")
        return
    its.sort(key=lambda i: i.get("dataCrtYm") or "", reverse=True)
    n = 0
    for it in its[:12]:
        seq, ym = it.get("seq"), it.get("dataCrtYm") or ""
        det = _items(await http.get_text(f"{base}/getDetailInfoSearch", {"serviceKey": key, "seq": seq}))
        stt = _items(await http.get_text(f"{base}/getPdAcctoSttusInfoSearch", {"serviceKey": key, "seq": seq, "data_crt_ym": ym}))
        total = _f(det[0].get("jnngpCnt")) if det else None
        db.ex("INSERT OR REPLACE INTO company_employment(company_id,ym,total,joined,left) VALUES(?,?,?,?,?)",
              (company["id"], f"{ym[:4]}-{ym[4:6]}", total, _f(stt[0].get("nwAcqzrCnt")) if stt else None,
               _f(stt[0].get("lssJnngpCnt")) if stt else None))
        if total is not None and n == 0:
            db.ex("UPDATE companies SET employees=? WHERE id=?", (int(total), company["id"]))
        n += 1
    log_.append(f"국민연금 고용 {n}개월")


async def enrich(company_id: int) -> dict:
    company = db.one("SELECT * FROM companies WHERE id=?", (company_id,))
    if not company:
        return dict(ok=False, log=["기업 없음"])
    k = keys()
    if not k["dart"] and not k["go"]:
        return dict(ok=False, log=["설정 화면에서 DART 또는 공공데이터포털 키를 넣으면 기업 개황·재무·고용 정보를 채웁니다"])
    out: list[str] = []
    for fn in (_dart, _fsc, _nps):
        try:
            await fn(db.one("SELECT * FROM companies WHERE id=?", (company_id,)), out)
        except Exception as e:
            # 키가 주소(crtfc_key·serviceKey)에 실려 가므로, 주소가 담긴 예외 원문은 화면에도 로그에도 남기지 않는다
            out.append(f"{fn.__name__.strip('_').upper()} 오류: {_safe_error(e)}")
            log.warning("enrich %s %s: %s", company_id, fn.__name__, _safe_error(e))
    db.ex("UPDATE companies SET enriched_at=? WHERE id=?", (db.now(), company_id))
    return dict(ok=True, log=out)


def financial_analysis(company_id: int) -> dict | None:
    """재무 지표와 규칙 기반 해설 (런웨이, 번레이트, 유동비율, 성장률)."""
    rows = db.q("SELECT * FROM company_financials WHERE company_id=? ORDER BY year", (company_id,))
    if not rows:
        return None
    last = rows[-1]
    prev = rows[-2] if len(rows) > 1 else None
    notes = []
    burn = runway = None
    op = last.get("op_income")
    if op is not None and op < 0:
        burn = -op / 12
        if last.get("cash"):
            runway = last["cash"] / burn
            notes.append(f"{last['year']}년 영업손실 기준 월평균 약 {burn / 1e8:,.1f}억 원을 쓰고 있고, 보유 현금으로는 약 {runway:,.0f}개월을 버틸 수 있습니다.")
        else:
            notes.append(f"{last['year']}년 영업손실 기준 월평균 약 {burn / 1e8:,.1f}억 원을 쓰고 있습니다. 현금 잔액 자료가 없어 런웨이는 계산하지 못했습니다.")
    elif op is not None:
        notes.append(f"{last['year']}년 영업이익을 내고 있어 외부 자금 없이도 운영이 가능한 구조입니다.")
    growth = None
    if prev and prev.get("revenue") and last.get("revenue") is not None:
        growth = (last["revenue"] / prev["revenue"] - 1) * 100
        notes.append(f"매출은 전년 대비 {growth:+.1f}% 변했습니다.")
    cur = last["current_assets"] / last["current_liab"] * 100 if last.get("current_assets") and last.get("current_liab") else None
    if cur is not None:
        notes.append(f"유동비율은 {cur:.0f}%로 " + ("단기 지급 여력이 충분합니다." if cur >= 150 else "단기 유동성에 주의가 필요합니다." if cur < 100 else "보통 수준입니다."))
    debt = last["liabilities"] / last["equity"] * 100 if last.get("liabilities") is not None and last.get("equity") and last["equity"] > 0 else None
    if last.get("equity") is not None and last["equity"] <= 0:
        notes.append("자본총계가 0 이하인 자본잠식 상태입니다.")
    elif debt is not None:
        notes.append(f"부채비율은 {debt:.0f}%입니다.")
    margin = last["op_income"] / last["revenue"] * 100 if last.get("revenue") and last.get("op_income") is not None else None
    return dict(year=last["year"], burn_monthly=burn, runway_months=runway, revenue_growth=growth, current_ratio=cur,
                debt_ratio=debt, op_margin=margin, notes=notes, source=last.get("source"))
