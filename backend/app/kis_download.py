"""한국투자증권 과거 1분봉(최근 1년)을 받아 5분봉으로 저장한다. 시세 조회만 하며 주문 API는 호출하지 않는다.

    cd backend && .venv/bin/python -m app.kis_download 40        # 거래대금 상위 40종목
    setsid nohup .venv/bin/python -m app.kis_download 40 > ../data/kis_download.log 2>&1 &

중간에 멈춰도 다시 실행하면 받은 날은 건너뛰고 이어서 받는다. 서버와 별개 프로세스로 돌려도 된다.
"""
import asyncio
import json
import sys

from . import db, intraday


async def main(limit: int):
    db.init()
    db.job_start("kis_minutes")
    try:
        r = await intraday.kis_download(limit, 252)
        db.job_end("kis_minutes", "ok", json.dumps(r, ensure_ascii=False))
        print(json.dumps(r, ensure_ascii=False))
    except Exception as e:
        db.job_end("kis_minutes", "error", repr(e))
        raise


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 40))
