"""한국투자증권 Open API (국내 주식 현금 주문만).

규격 출처: github.com/koreainvestment/open-trading-api (examples_llm, 2026-11 확인)
- 실전 https://openapi.koreainvestment.com:9443 / 모의 https://openapivts.koreainvestment.com:29443
- 성공 여부는 HTTP 200 본문의 rt_cd == "0" 으로 판단한다 (업무 오류도 200으로 온다)
- 접근토큰은 1분에 1회 발급, 유효기간 1일 → 디스크에 저장해 재사용한다

안전 원칙
- 주문 요청은 절대 재시도하지 않는다. 시간 초과 등 결과를 모르면 'unknown'으로 남기고 체결조회로 확인한다.
- 키·계좌번호는 data/kis.json(권한 600)에만 두고 API 응답이나 로그로 내보내지 않는다.
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from .. import db

log = logging.getLogger("kis")
HOSTS = {"demo": "https://openapivts.koreainvestment.com:29443", "real": "https://openapi.koreainvestment.com:9443"}
GAP = {"demo": 0.55, "real": 0.55}  # 호출 간격(초). 신규 API 이용 초기에는 초당 호출 제한이 낮다 (실측: 0.08초 간격에서 초과 오류)
GAP_MIN, GAP_MAX = {"demo": 0.5, "real": 0.07}, 2.0
_ok_streak = {"demo": 0, "real": 0}
TR = {  # (실전, 모의)
    "buy": ("TTTC0012U", "VTTC0012U"), "sell": ("TTTC0011U", "VTTC0011U"), "cancel": ("TTTC0013U", "VTTC0013U"),
    "balance": ("TTTC8434R", "VTTC8434R"), "buyable": ("TTTC8908R", "VTTC8908R"), "fills": ("TTTC0081R", "VTTC0081R"),
    "minute_hist": ("FHKST03010230", "FHKST03010230"),  # 시세 조회 (주문 아님)
    # 이하 시장 자료 조회 (주문·계좌와 무관, 계좌번호를 보내지 않는다)
    "inv_daily": ("FHPTJ04040000",) * 2, "prog_today": ("FHPPG04600101",) * 2, "prog_daily": ("FHPPG04600001",) * 2,
    "short_rank": ("FHPST04820000",) * 2, "frgn_inst": ("FHPTJ04400000",) * 2,
}
MARKET_PATHS = {
    "inv_daily": "/uapi/domestic-stock/v1/quotations/inquire-investor-daily-by-market",
    "prog_today": "/uapi/domestic-stock/v1/quotations/comp-program-trade-today",
    "prog_daily": "/uapi/domestic-stock/v1/quotations/comp-program-trade-daily",
    "short_rank": "/uapi/domestic-stock/v1/ranking/short-sale",
    "frgn_inst": "/uapi/domestic-stock/v1/quotations/foreign-institution-total",
}
CONF = db.DATA_DIR / "kis.json"
TOKENS = db.DATA_DIR / "kis_tokens.json"
DEFAULT = {"mode": "demo", "enabled": True,
           "limits": {"per_order_krw": 1_000_000, "daily_krw": 5_000_000, "daily_count": 20},
           "demo": {}, "real": {}}
TRANSPORT: httpx.AsyncBaseTransport | None = None  # 시험용 가짜 전송 계층


class KisError(Exception):
    def __init__(self, msg: str, code: str = "", unknown: bool = False):
        super().__init__(msg)
        self.code = code
        self.unknown = unknown  # 주문이 접수됐는지 알 수 없음


def _write_private(path: Path, data: dict):
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def load() -> dict:
    cfg = json.loads(json.dumps(DEFAULT))
    if CONF.exists():
        saved = json.loads(CONF.read_text())
        for k, v in saved.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    if cfg.get("mode") not in HOSTS:
        cfg["mode"] = "demo"
    return cfg


def save(cfg: dict):
    _write_private(CONF, cfg)


def configured(cfg: dict, env: str) -> bool:
    c = cfg.get(env) or {}
    return all(c.get(k) for k in ("app_key", "app_secret", "cano", "prdt"))


def public_status(cfg: dict) -> dict:
    """화면에 보낼 설정 요약. 키·계좌번호 값은 보내지 않는다 (계좌번호는 뒤 2자리만)."""
    return dict(mode=cfg["mode"], enabled=bool(cfg["enabled"]), limits=cfg["limits"],
                envs={e: dict(configured=configured(cfg, e),
                              account=("****" + str(cfg[e].get("cano", ""))[-2:] + "-" + str(cfg[e].get("prdt", ""))) if configured(cfg, e) else None)
                      for e in HOSTS})


def _client() -> httpx.AsyncClient:
    # 재시도 없는 전용 클라이언트. 공용 http 모듈은 실패 시 재시도하므로 주문에 쓰면 안 된다.
    return httpx.AsyncClient(base_url="", timeout=httpx.Timeout(10.0, connect=5.0), transport=TRANSPORT,
                             headers={"content-type": "application/json; charset=utf-8"})


def _tokens() -> dict:
    try:
        return json.loads(TOKENS.read_text())
    except Exception:
        return {}


async def _token(env: str, cfg: dict) -> str:
    c = cfg[env]
    t = _tokens().get(env)
    # 키가 바뀌면 토큰도 새로 받는다 (키 앞 6자리로만 구분, 키 자체는 저장하지 않음)
    if t and t.get("key_tag") == c["app_key"][:6] and t.get("exp", 0) - 600 > time.time():
        return t["token"]
    async with _client() as cl:
        r = await cl.post(HOSTS[env] + "/oauth2/tokenP",
                          json={"grant_type": "client_credentials", "appkey": c["app_key"], "appsecret": c["app_secret"]})
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != 200 or "access_token" not in body:
        raise KisError(f"토큰 발급 실패: {body.get('error_description') or body.get('msg1') or r.status_code}", body.get("error_code", ""))
    exp = time.time() + int(body.get("expires_in") or 86400)
    toks = _tokens()
    toks[env] = dict(token=body["access_token"], exp=exp, key_tag=c["app_key"][:6])
    _write_private(TOKENS, toks)
    return body["access_token"]


async def call(env: str, method: str, path: str, tr: str, params: dict, order: bool = False, account: bool = True) -> dict:
    """KIS REST 호출. 주문(order=True)은 어떤 경우에도 재시도하지 않는다.
    조회는 '초당 거래건수 초과'(EGW00201)일 때만 호출 간격을 늘려 다시 시도하고, 성공이 이어지면 간격을 조금씩 줄인다."""
    tries = 1 if order else 8
    for n in range(tries):
        try:
            data = await _call_once(env, method, path, tr, params, order, account)
            _ok_streak[env] += 1
            if _ok_streak[env] >= 120 and GAP[env] > GAP_MIN[env]:
                GAP[env] = max(GAP_MIN[env], GAP[env] * 0.93)
                _ok_streak[env] = 0
            return data
        except KisError as e:
            if order or e.code != "EGW00201" or n == tries - 1:
                raise
            GAP[env] = min(GAP_MAX, GAP[env] * 1.4)
            _ok_streak[env] = 0
            await asyncio.sleep(0.6)
    raise KisError("호출 제한으로 조회하지 못했습니다")


_pace_lock = asyncio.Lock()
_token_lock = asyncio.Lock()
_next_start = {"demo": 0.0, "real": 0.0}


async def _pace(env: str):
    """요청 '시작' 간격만 지킨다 (응답을 기다리는 동안 다음 요청을 보낼 수 있다)."""
    async with _pace_lock:
        now = time.time()
        start = max(now, _next_start[env])
        _next_start[env] = start + GAP[env]
    if start > now:
        await asyncio.sleep(start - now)


async def _call_once(env: str, method: str, path: str, tr: str, params: dict, order: bool = False, account: bool = True) -> dict:
    if env not in HOSTS:
        raise KisError("환경 값이 잘못됐습니다")
    cfg = load()
    if not configured(cfg, env):
        raise KisError(f"{'모의' if env == 'demo' else '실전'}투자 키와 계좌번호를 먼저 설정해 주세요")
    tr_id = TR[tr][0 if env == "real" else 1]
    await _pace(env)
    async with _token_lock:
        token = await _token(env, cfg)
    c = cfg[env]
    headers = {"authorization": f"Bearer {token}", "appkey": c["app_key"], "appsecret": c["app_secret"],
               "tr_id": tr_id, "custtype": "P", "tr_cont": ""}
    body = {"CANO": str(c["cano"]), "ACNT_PRDT_CD": str(c["prdt"]), **params} if account else dict(params)
    try:
        async with _client() as cl:
            if method == "POST":
                r = await cl.post(HOSTS[env] + path, headers=headers, content=json.dumps(body))
            else:
                r = await cl.get(HOSTS[env] + path, headers=headers, params=body)
    except (httpx.TimeoutException, httpx.TransportError) as e:
        raise KisError(f"증권사 응답을 받지 못했습니다 ({type(e).__name__})", unknown=order)
    try:
        data = r.json()
    except ValueError:
        raise KisError(f"증권사 응답 형식 오류 (HTTP {r.status_code})", unknown=order and r.status_code >= 500)
    if r.status_code != 200 or str(data.get("rt_cd")) != "0":
        if data.get("msg_cd") in ("EGW00123", "EGW00121"):  # 토큰 만료·무효 → 다음 호출에서 새로 받도록 지운다
            toks = _tokens()
            toks.pop(env, None)
            _write_private(TOKENS, toks)
        raise KisError(data.get("msg1") or f"HTTP {r.status_code}", data.get("msg_cd", ""), unknown=order and r.status_code >= 500)
    return data


# ── 호가 단위 ─────────────────────────────────────────────────────────
def tick(price: float, kind: str = "stock") -> int:
    """KRX 호가 단위 (2023년 개편 기준 주식, ETF·ETN은 2천 원 미만 1원·이상 5원)."""
    if kind in ("etf", "etn"):
        return 1 if price < 2000 else 5
    for limit, t in ((2000, 1), (5000, 5), (20000, 10), (50000, 50), (200000, 100), (500000, 500)):
        if price < limit:
            return t
    return 1000


def round_tick(price: float, side: str, kind: str = "stock") -> int:
    t = tick(price, kind)
    return int(price // t * t) if side == "buy" else int(-(-price // t) * t)  # 매수는 내림, 매도는 올림


# ── 업무 함수 ─────────────────────────────────────────────────────────
async def order(env: str, side: str, code: str, qty: int, price: int | None) -> dict:
    """현금 주문. price=None이면 시장가."""
    params = {"PDNO": code, "ORD_DVSN": "01" if price is None else "00", "ORD_QTY": str(int(qty)),
              "ORD_UNPR": "0" if price is None else str(int(price)), "EXCG_ID_DVSN_CD": "KRX"}
    if side == "sell":
        params["SLL_TYPE"] = "01"
    data = await call(env, "POST", "/uapi/domestic-stock/v1/trading/order-cash", side, params, order=True)
    out = data.get("output") or {}
    return dict(odno=out.get("ODNO"), orgno=out.get("KRX_FWDG_ORD_ORGNO"), ord_tmd=out.get("ORD_TMD"), msg=data.get("msg1"))


async def cancel(env: str, odno: str, orgno: str) -> dict:
    params = {"KRX_FWDG_ORD_ORGNO": orgno or "", "ORGN_ODNO": odno, "ORD_DVSN": "00", "RVSE_CNCL_DVSN_CD": "02",
              "ORD_QTY": "0", "ORD_UNPR": "0", "QTY_ALL_ORD_YN": "Y", "EXCG_ID_DVSN_CD": "KRX"}
    data = await call(env, "POST", "/uapi/domestic-stock/v1/trading/order-rvsecncl", "cancel", params, order=True)
    return dict(msg=data.get("msg1"), odno=(data.get("output") or {}).get("ODNO"))


def _n(v) -> float:
    try:
        return float(str(v).replace(",", "") or 0)
    except ValueError:
        return 0.0


async def balance(env: str) -> dict:
    data = await call(env, "GET", "/uapi/domestic-stock/v1/trading/inquire-balance", "balance", {
        "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02", "UNPR_DVSN": "01", "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "00", "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""})
    pos = [dict(code=p.get("pdno"), name=p.get("prdt_name"), qty=_n(p.get("hldg_qty")), sellable=_n(p.get("ord_psbl_qty")),
                avg_price=_n(p.get("pchs_avg_pric")), price=_n(p.get("prpr")), value=_n(p.get("evlu_amt")),
                pnl=_n(p.get("evlu_pfls_amt")), pnl_pct=_n(p.get("evlu_pfls_rt")))
           for p in data.get("output1") or [] if _n(p.get("hldg_qty")) > 0]
    s = (data.get("output2") or [{}])[0]
    return dict(positions=pos, cash=_n(s.get("dnca_tot_amt")), d2_cash=_n(s.get("prvs_rcdl_excc_amt")),
                stock_value=_n(s.get("scts_evlu_amt")), total=_n(s.get("tot_evlu_amt")), pnl=_n(s.get("evlu_pfls_smtl_amt")))


async def buyable(env: str, code: str, price: int | None) -> dict:
    data = await call(env, "GET", "/uapi/domestic-stock/v1/trading/inquire-psbl-order", "buyable", {
        "PDNO": code, "ORD_UNPR": "" if price is None else str(int(price)), "ORD_DVSN": "01" if price is None else "00",
        "CMA_EVLU_AMT_ICLD_YN": "N", "OVRS_ICLD_YN": "N"})
    o = data.get("output") or {}
    return dict(cash=_n(o.get("ord_psbl_cash")), max_qty=_n(o.get("nrcvb_buy_qty")), max_amt=_n(o.get("nrcvb_buy_amt")))


async def fills(env: str, day: str | None = None) -> list[dict]:
    """당일 주문·체결 내역 (최근 3개월 이내 조회 TR)."""
    day = day or (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y%m%d")
    data = await call(env, "GET", "/uapi/domestic-stock/v1/trading/inquire-daily-ccld", "fills", {
        "INQR_STRT_DT": day, "INQR_END_DT": day, "SLL_BUY_DVSN_CD": "00", "PDNO": "", "CCLD_DVSN": "00", "INQR_DVSN": "00",
        "INQR_DVSN_3": "00", "ORD_GNO_BRNO": "", "ODNO": "", "INQR_DVSN_1": "", "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
        "EXCG_ID_DVSN_CD": "KRX"})
    return [dict(odno=x.get("odno"), code=x.get("pdno"), name=x.get("prdt_name"), side="sell" if x.get("sll_buy_dvsn_cd") == "01" else "buy",
                 qty=_n(x.get("ord_qty")), filled=_n(x.get("tot_ccld_qty")), avg_price=_n(x.get("avg_prvs")),
                 remain=_n(x.get("rmn_qty")), rejected=_n(x.get("rjct_qty")), cancelled=x.get("cncl_yn") == "Y",
                 ord_tmd=x.get("ord_tmd")) for x in data.get("output1") or []]


async def minute_bars(env: str, code: str, day: str, hour: str = "153000") -> list[dict]:
    """주식일별분봉조회: 지정한 날짜·시각 이전 1분봉 최대 120개 (시세 조회, 계좌번호를 보내지 않는다).
    한투 서버가 보관하는 최대 1년치까지 조회된다. 실전 서버에서만 지원한다."""
    if env != "real":
        raise KisError("과거 분봉 조회는 실전투자 키로만 됩니다")
    data = await call(env, "GET", "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice", "minute_hist", {
        "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code, "FID_INPUT_HOUR_1": hour, "FID_INPUT_DATE_1": day,
        "FID_PW_DATA_INCU_YN": "Y", "FID_FAKE_TICK_INCU_YN": ""}, account=False)
    out = []
    for x in data.get("output2") or []:
        if not x.get("stck_bsop_date") or not x.get("stck_cntg_hour"):
            continue
        out.append(dict(day=x["stck_bsop_date"], hour=x["stck_cntg_hour"], o=_n(x.get("stck_oprc")), h=_n(x.get("stck_hgpr")),
                        l=_n(x.get("stck_lwpr")), c=_n(x.get("stck_prpr")), v=_n(x.get("cntg_vol"))))
    return out


async def market_data(tr: str, params: dict) -> dict:
    """시장 자료 조회 (수급·프로그램·공매도). 정해 둔 조회 전용 주소만 부를 수 있고 실전 키로만 된다."""
    if tr not in MARKET_PATHS:
        raise KisError("허용되지 않은 조회입니다")
    return await call("real", "GET", MARKET_PATHS[tr], tr, params, account=False)
