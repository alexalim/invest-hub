"""다음 금융: 시장별 투자자 순매수. 일별 값이며 당일 행은 장중 누계로 계속 바뀐다."""
from . import http

URL = "https://finance.daum.net/api/investor/{}/days"
HDR = {"Referer": "https://finance.daum.net/domestic/investors"}
# 세부 주체: 응답 키 -> (우리 키, 화면 이름)
DETAIL = {"FINANCIAL_INVESTOR": ("fin", "금융투자"), "INSURANCE_COMPANIES": ("ins", "보험"), "MUTUAL_FUND": ("trust", "투신"),
          "PRIVATE_EQUITY_FUND": ("pef", "사모펀드"), "BANK": ("bank", "은행"), "ETC_FINANCIAL_INSTITUTION": ("etcfin", "기타금융"),
          "PENSION_FUND": ("pension", "연기금"), "ETC_CORPORATION": ("corp", "기타법인"), "ETC_FOREIGN": ("etcforeign", "기타외국인")}
DETAIL_NAMES = {k: name for k, name in DETAIL.values()}


def _eok(v) -> float:
    return round(float(v or 0) / 1e8, 1)


async def investor_days(market: str, page: int = 1, per_page: int = 100, ttl: float = 0) -> list[dict]:
    """market: KOSPI | KOSDAQ. 금액 단위는 억원, 최신 날짜가 먼저 온다."""
    d = await http.get_json(URL.format(market), {"page": page, "perPage": per_page, "details": "true"}, ttl=ttl, headers=HDR)
    out = []
    for r in d.get("data") or []:
        det = r.get("details") or {}
        out.append(dict(date=(r.get("date") or "")[:10].replace("-", ""), individual=_eok(r.get("individualStraightPurchasePrice")),
                        foreigner=_eok(r.get("foreignStraightPurchasePrice")), institution=_eok(r.get("institutionStraightPurchasePrice")),
                        details={ours: _eok(det.get(theirs)) for theirs, (ours, _) in DETAIL.items()}))
    return [r for r in out if len(r["date"]) == 8]
