"""업비트 공개 시세 API (키 불필요): 원화 마켓 코인 목록, 현재가, 캔들, 호가."""
import asyncio
from datetime import datetime, timezone

from .. import db
from . import http, naver

API = "https://api.upbit.com/v1"
KST = 9 * 3600
MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "60m": 60}


async def refresh() -> int:
    markets = await http.get_json(f"{API}/market/all", ttl=3600)
    krw = {m["market"]: m for m in markets if m["market"].startswith("KRW-")}
    rows = []
    keys = list(krw)
    for i in range(0, len(keys), 100):
        ticks = await http.get_json(f"{API}/ticker", {"markets": ",".join(keys[i:i + 100])})
        for t in ticks:
            m = krw[t["market"]]
            rows.append(dict(
                symbol=f"CR:{t['market']}", market="CRYPTO", kind="crypto", code=t["market"], name=m["korean_name"],
                name_en=m["english_name"], price=t["trade_price"], prev_close=t["prev_closing_price"],
                change=t["signed_change_price"], change_pct=t["signed_change_rate"] * 100,
                open=t["opening_price"], high=t["high_price"], low=t["low_price"],
                volume=t["acc_trade_volume_24h"], value=t["acc_trade_price_24h"], mcap=None, currency="KRW"))
    naver.upsert_instruments(rows)
    return len(rows)


async def quotes(markets: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(markets), 100):
        ticks = await http.get_json(f"{API}/ticker", {"markets": ",".join(markets[i:i + 100])}, ttl=2)
        for t in ticks:
            out[f"CR:{t['market']}"] = dict(
                price=t["trade_price"], prev_close=t["prev_closing_price"], change=t["signed_change_price"],
                change_pct=t["signed_change_rate"] * 100, open=t["opening_price"], high=t["high_price"],
                low=t["low_price"], volume=t["acc_trade_volume_24h"], value=t["acc_trade_price_24h"],
                high52=t.get("highest_52_week_price"), low52=t.get("lowest_52_week_price"), market_status="OPEN")
    return out


async def candles(market: str, tf: str = "day", count: int = 400) -> list[tuple]:
    if tf in MINUTES:
        path = f"candles/minutes/{MINUTES[tf]}"
    else:
        path = {"day": "candles/days", "week": "candles/weeks", "month": "candles/months"}[tf]
    out: dict[int, tuple] = {}
    to = None
    while len(out) < count:
        params = {"market": market, "count": min(200, count - len(out))}
        if to:
            params["to"] = to
        rows = await http.get_json(f"{API}/{path}", params, ttl=5 if not to else 600)
        if not rows:
            break
        for r in rows:
            utc = datetime.fromisoformat(r["candle_date_time_utc"]).replace(tzinfo=timezone.utc)
            if tf in MINUTES:
                ts = int(utc.timestamp()) + KST
            else:
                kst = datetime.fromisoformat(r["candle_date_time_kst"])
                ts = int(datetime(kst.year, kst.month, kst.day, tzinfo=timezone.utc).timestamp())
            out[ts] = (ts, r["opening_price"], r["high_price"], r["low_price"], r["trade_price"], r["candle_acc_trade_volume"])
        if len(rows) < 200:
            break
        to = rows[-1]["candle_date_time_utc"] + "Z"
        await asyncio.sleep(0.12)
    return sorted(out.values())


async def orderbook(market: str) -> dict:
    d = await http.get_json(f"{API}/orderbook", {"markets": market}, ttl=1)
    units = (d[0] if d else {}).get("orderbook_units") or []
    return dict(asks=[dict(price=u["ask_price"], qty=u["ask_size"]) for u in reversed(units[:10])],
                bids=[dict(price=u["bid_price"], qty=u["bid_size"]) for u in units[:10]],
                total_ask=(d[0] if d else {}).get("total_ask_size"), total_bid=(d[0] if d else {}).get("total_bid_size"))
