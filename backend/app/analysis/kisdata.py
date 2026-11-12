"""한국투자증권 시세 조회로 받는 시장 자료: 프로그램 매매, 업종별 수급, 공매도, 장중 가집계.

관리자가 등록한 실전투자 키로 '조회'만 한다. 주문·계좌 API는 부르지 않고 계좌번호도 보내지 않는다.
금액은 모두 억원으로 바꿔서 돌려준다.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from .. import db
from ..broker import kis
from . import pulse

log = logging.getLogger("kisdata")
MK = {"KOSPI": dict(cls="K", inv="KSP", total="0001", short="0001", prelim="0001"),
      "KOSDAQ": dict(cls="Q", inv="KSQ", total="1001", short="1001", prelim="1001")}
# 한투 업종 코드 (idxcode.mst 2026-11 기준). 대형·중형·소형, '제조' 같은 묶음 지수는 뺐다
SECTORS = {
    "KOSPI": {"0005": "음식료·담배", "0006": "섬유·의류", "0007": "종이·목재", "0008": "화학", "0009": "제약", "0010": "비금속",
              "0011": "금속", "0012": "기계·장비", "0013": "전기·전자", "0014": "의료·정밀기기", "0015": "운송장비·부품", "0016": "유통",
              "0017": "전기·가스", "0018": "건설", "0019": "운송·창고", "0020": "통신", "0021": "금융", "0024": "증권", "0025": "보험",
              "0026": "일반서비스", "0028": "부동산", "0029": "IT 서비스"},
    "KOSDAQ": {"1006": "일반서비스", "1010": "건설", "1011": "유통", "1013": "운송·창고", "1014": "금융", "1015": "오락·문화",
               "1019": "음식료·담배", "1020": "섬유·의류", "1021": "종이·목재", "1022": "출판·매체복제", "1023": "화학", "1024": "제약",
               "1025": "비금속", "1026": "금속", "1027": "기계·장비", "1028": "전기·전자", "1029": "의료·정밀기기", "1030": "운송장비·부품",
               "1031": "기타제조", "1032": "통신", "1033": "IT 서비스"},
}
_cache: dict[str, tuple[float, object]] = {}


def available() -> bool:
    return kis.configured(kis.load(), "real")


def _f(v) -> float:
    try:
        return float(str(v).replace(",", "") or 0)
    except ValueError:
        return 0.0


def _eok(v) -> float:
    """백만원 → 억원."""
    return round(_f(v) / 100, 1)


def _today() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y%m%d")


def _mk(market: str) -> str:
    return market if market in MK else "KOSPI"


# ── 프로그램 매매 ──────────────────────────────────────────────────────
async def program_tick() -> int:
    """당일 프로그램 매매 누계(차익·비차익)를 한 점 기록한다. 한투는 최근 30분만 주므로 직접 쌓는다."""
    n = 0
    day = _today()
    for mk, c in MK.items():
        d = await kis.market_data("prog_today", {"FID_COND_MRKT_DIV_CODE": "J", "FID_MRKT_CLS_CODE": c["cls"], "FID_SCTN_CLS_CODE": "",
                                                 "FID_INPUT_ISCD": "", "FID_COND_MRKT_DIV_CODE1": "", "FID_INPUT_HOUR_1": ""})
        rows = []
        for r in d.get("output") or []:
            hh = str(r.get("bsop_hour") or "")
            if len(hh) != 6:
                continue
            rows.append((mk, day, hh[:4], _eok(r.get("arbt_smtn_ntby_tr_pbmn")), _eok(r.get("nabt_smtn_ntby_tr_pbmn")),
                         _eok(r.get("whol_smtn_ntby_tr_pbmn"))))
        if rows:
            db.many("INSERT OR REPLACE INTO program_ticks(market,date,hhmm,arb,nonarb,total) VALUES(?,?,?,?,?,?)", rows)
            n += len(rows)
    db.ex("DELETE FROM program_ticks WHERE date < ?", ((datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y%m%d"),))
    return n


async def program_view(market: str) -> dict:
    market = _mk(market)
    if not available():
        return dict(available=False)
    key = f"progd:{market}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 600:
        days = hit[1]
    else:
        d = await kis.market_data("prog_daily", {"FID_COND_MRKT_DIV_CODE": "J", "FID_MRKT_CLS_CODE": MK[market]["cls"],
                                                 "FID_INPUT_DATE_1": "", "FID_INPUT_DATE_2": ""})
        days = [dict(date=r["stck_bsop_date"], arb=_eok(r.get("arbt_smtn_ntby_tr_pbmn")), nonarb=_eok(r.get("nabt_smtn_ntby_tr_pbmn")),
                     total=_eok(r.get("whol_smtn_ntby_tr_pbmn"))) for r in d.get("output") or [] if r.get("stck_bsop_date")]
        days.reverse()
        _cache[key] = (time.time(), days)
    tick_date = db.val("SELECT MAX(date) FROM program_ticks WHERE market=?", (market,))
    ticks = db.q("SELECT hhmm,arb,nonarb,total FROM program_ticks WHERE market=? AND date=? ORDER BY hhmm", (market, tick_date)) if tick_date else []
    return dict(available=True, market=market, tick_date=tick_date, ticks=ticks, days=days)


# ── 업종별 수급 ────────────────────────────────────────────────────────
async def sector_sync(market: str) -> int:
    """업종마다 투자자별 순매수(오늘·5일·20일·1년 누적)를 받아 저장한다. 업종 수만큼 호출하므로 20초쯤 걸린다."""
    market = _mk(market)
    day = _today()
    out = []
    for code, name in SECTORS[market].items():
        try:
            d = await kis.market_data("inv_daily", {"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": code, "FID_INPUT_DATE_1": day,
                                                    "FID_INPUT_ISCD_1": MK[market]["inv"], "FID_INPUT_DATE_2": day, "FID_INPUT_ISCD_2": code})
        except kis.KisError as e:
            log.warning("sector %s %s: %s", market, code, e)
            continue
        rows = d.get("output") or []
        if not rows:
            continue

        def total(field: str, n: int) -> float:
            return round(sum(_f(r.get(field)) for r in rows[:n]) / 100, 1)

        row = dict(code=code, name=name, date=rows[0].get("stck_bsop_date"), change_pct=_f(rows[0].get("bstp_nmix_prdy_ctrt")), days=len(rows))
        for who, field in (("foreigner", "frgn_ntby_tr_pbmn"), ("institution", "orgn_ntby_tr_pbmn"), ("individual", "prsn_ntby_tr_pbmn")):
            row[who] = {"1": total(field, 1), "5": total(field, 5), "20": total(field, 20), "250": total(field, 250)}
        out.append(row)
    if out:
        db.set_setting(f"sector_flow:{market}", dict(at=db.now(), rows=out))
    return len(out)


def sector_view(market: str) -> dict:
    market = _mk(market)
    if not available():
        return dict(available=False)
    d = db.get_setting(f"sector_flow:{market}") or dict(at=None, rows=[])
    return dict(available=True, market=market, **d)


# ── 공매도 상위 · 장중 가집계 (요청할 때 조회, 잠깐 기억) ───────────────
async def short_view(market: str, period: str = "0") -> dict:
    market = _mk(market)
    period = period if period in ("0", "4", "9") else "0"   # 1일 · 1주일 · 2주일
    if not available():
        return dict(available=False)
    key = f"short:{market}:{period}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    d = await kis.market_data("short_rank", {"FID_APLY_RANG_VOL": "", "FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20482",
                                             "FID_INPUT_ISCD": MK[market]["short"], "FID_PERIOD_DIV_CODE": "D", "FID_INPUT_CNT_1": period,
                                             "FID_TRGT_EXLS_CLS_CODE": "", "FID_TRGT_CLS_CODE": "", "FID_APLY_RANG_PRC_1": "", "FID_APLY_RANG_PRC_2": ""})
    rows = [dict(symbol="KR:" + r["mksc_shrn_iscd"], name=r.get("hts_kor_isnm"), price=_f(r.get("stck_prpr")), change_pct=_f(r.get("prdy_ctrt")),
                 short_amount=round(_f(r.get("ssts_tr_pbmn")) / 1e8, 1), short_ratio=_f(r.get("ssts_tr_pbmn_rlim")),
                 value=round(_f(r.get("acml_tr_pbmn")) / 1e8, 1), avg_price=_f(r.get("avrg_prc")))
            for r in d.get("output") or [] if r.get("mksc_shrn_iscd")]
    out = dict(available=True, market=market, period=period, at=db.now(), rows=rows)
    _cache[key] = (time.time(), out)
    return out


async def prelim_view(market: str, who: str = "foreign", side: str = "buy") -> dict:
    """외국인·기관 장중 가집계. 증권사 직원이 하루 네 번쯤 입력하는 어림 자료다."""
    market = _mk(market)
    etc = {"foreign": "1", "organ": "2"}.get(who, "1")
    sort = "1" if side == "sell" else "0"
    if not available():
        return dict(available=False)
    key = f"prelim:{market}:{etc}:{sort}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 300:
        return hit[1]
    d = await kis.market_data("frgn_inst", {"FID_COND_MRKT_DIV_CODE": "V", "FID_COND_SCR_DIV_CODE": "16449", "FID_INPUT_ISCD": MK[market]["prelim"],
                                            "FID_DIV_CLS_CODE": "1", "FID_RANK_SORT_CLS_CODE": sort, "FID_ETC_CLS_CODE": etc})
    rows = [dict(symbol="KR:" + r["mksc_shrn_iscd"], name=r.get("hts_kor_isnm"), price=_f(r.get("stck_prpr")), change_pct=_f(r.get("prdy_ctrt")),
                 foreigner=_eok(r.get("frgn_ntby_tr_pbmn")), institution=_eok(r.get("orgn_ntby_tr_pbmn")))
            for r in d.get("output") or [] if r.get("mksc_shrn_iscd")]
    out = dict(available=True, market=market, at=db.now(), rows=rows)
    _cache[key] = (time.time(), out)
    return out


async def job() -> str:
    """정규장 중: 프로그램 누계를 매번 기록하고 업종 수급은 10분마다. 장 마감 뒤에는 그날 확정치를 한 번 더 받는다."""
    if not available():
        return "실전 키 없음 — 건너뜀"
    msg = []
    live = pulse.regular_session()
    if live:
        msg.append(f"프로그램 {await program_tick()}점")
    for mk in MK:
        at = (db.get_setting(f"sector_flow:{mk}") or {}).get("at") or 0
        if db.now() - at > (600 if live else 6 * 3600):
            msg.append(f"{mk} 업종 {await sector_sync(mk)}개")
    return ", ".join(msg) or "변동 없음"
