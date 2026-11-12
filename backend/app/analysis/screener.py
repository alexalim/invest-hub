"""종목필터. 재무·시세 조건은 SQL로 거르고, 기술적 조건은 일봉에 조건식을 적용한다.
기술적 조건은 '그룹 안은 AND, 그룹끼리는 OR'로 묶는다."""
import numpy as np

from .. import db
from . import indicators as ind, store

# 화면에 노출하는 수치 필드: 이름 → (라벨, SQL 식, 단위)
FIELDS = {
    "price": ("현재가", "price", ""),
    "change_pct": ("등락률(%)", "change_pct", "%"),
    "volume": ("거래량", "volume", "주"),
    "value": ("거래대금(억)", "value/1e8", "억"),
    "mcap": ("시가총액(억)", "mcap/1e8", "억"),
    "per": ("PER", "per", "배"),
    "pbr": ("PBR", "pbr", "배"),
    "eps": ("EPS", "eps", ""),
    "bps": ("BPS", "bps", ""),
    "div_yield": ("배당수익률(%)", "div_yield", "%"),
    "roe": ("ROE(%) 추정", "CASE WHEN bps>0 THEN eps*100.0/bps END", "%"),
    "pos52": ("52주 위치(%)", "CASE WHEN high52>low52 THEN (price-low52)*100.0/(high52-low52) END", "%"),
    "from_high52": ("52주 고가 대비(%)", "CASE WHEN high52>0 THEN (price/high52-1)*100 END", "%"),
}
PRESETS = [
    dict(name="저PER·저PBR 가치주", filters=[dict(field="per", min=0.1, max=10), dict(field="pbr", min=0.1, max=1),
                                       dict(field="mcap", min=1000)], groups=[]),
    dict(name="고배당주", filters=[dict(field="div_yield", min=4), dict(field="mcap", min=1000)], groups=[]),
    dict(name="정배열 초입", filters=[dict(field="mcap", min=500)], groups=[[
        {"left": {"ind": "sma", "p": [5]}, "op": ">", "right": {"ind": "sma", "p": [20]}},
        {"left": {"ind": "sma", "p": [20]}, "op": "cross_up", "right": {"ind": "sma", "p": [60]}}]]),
    dict(name="RSI 과매도", filters=[dict(field="mcap", min=1000)], groups=[[
        {"left": {"ind": "rsi", "p": [14]}, "op": "<", "right": {"value": 30}}]]),
    dict(name="거래량 급증 돌파", filters=[dict(field="change_pct", min=3)], groups=[[
        {"left": {"ind": "volume"}, "op": ">", "right": {"ind": "vol_sma", "p": [20], "mul": 2}},
        {"left": {"ind": "close"}, "op": ">", "right": {"ind": "highest", "p": [20], "shift": 1}}]]),
    dict(name="52주 신고가 근접", filters=[dict(field="from_high52", min=-5), dict(field="mcap", min=1000)], groups=[]),
    dict(name="볼린저 하단 터치", filters=[dict(field="mcap", min=500)], groups=[[
        {"left": {"ind": "low"}, "op": "<=", "right": {"ind": "bb", "p": [20, 2], "out": "lower"}}]]),
    dict(name="골든크로스 발생", filters=[dict(field="mcap", min=300)], groups=[[
        {"left": {"ind": "sma", "p": [5]}, "op": "cross_up", "right": {"ind": "sma", "p": [20]}}]]),
]


def run(spec: dict) -> dict:
    markets = spec.get("markets") or ["KOSPI", "KOSDAQ"]
    kinds = spec.get("kinds") or ["stock"]
    where = [f"market IN ({','.join('?' * len(markets))})", f"kind IN ({','.join('?' * len(kinds))})", "price IS NOT NULL"]
    params: list = [*markets, *kinds]
    for f in spec.get("filters") or []:
        meta = FIELDS.get(f.get("field"))
        if not meta:
            continue
        expr = meta[1]
        if f.get("min") not in (None, ""):
            where.append(f"({expr}) >= ?")
            params.append(float(f["min"]))
        if f.get("max") not in (None, ""):
            where.append(f"({expr}) <= ?")
            params.append(float(f["max"]))
    if spec.get("query"):
        where.append("name LIKE ?")
        params.append(f"%{spec['query']}%")
    extra = ", ".join(f"({v[1]}) AS {k}" for k, v in FIELDS.items() if k in ("roe", "pos52", "from_high52"))
    rows = db.q(f"SELECT symbol,market,kind,code,name,price,change,change_pct,volume,value,mcap,per,pbr,eps,bps,div_yield,"
                f"high52,low52,sector,currency,{extra} FROM instruments WHERE {' AND '.join(where)} "
                f"ORDER BY COALESCE(mcap, value, 0) DESC", params)
    groups = [g for g in (spec.get("groups") or []) if g]
    scanned = len(rows)
    missing = 0
    if groups:
        kept = []
        for r in rows:
            d = store.get(r["symbol"])
            if d is None or len(d["c"]) < 30:
                missing += 1
                continue
            d = store.tail(d, 400)
            try:
                ok = any(all(bool(ind.evaluate(d, c)[-1]) for c in g) for g in groups)
            except Exception:
                ok = False
            if ok:
                kept.append(r)
        rows = kept
    sort = spec.get("sort") or "mcap"
    desc = spec.get("desc", True)
    rows.sort(key=lambda r: (r.get(sort) is None, -(r.get(sort) or 0) if desc else (r.get(sort) or 0)))
    limit = int(spec.get("limit") or 200)
    return dict(total=len(rows), scanned=scanned, no_data=missing, rows=rows[:limit])


def fields() -> list[dict]:
    return [dict(key=k, label=v[0], unit=v[2]) for k, v in FIELDS.items()]
