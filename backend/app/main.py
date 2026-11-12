"""서버 진입점. API와 빌드된 프런트엔드 정적 파일을 한 프로세스에서 제공한다."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db, jobs
from .providers import http
from .routers import community, core, discover, live, market, pulse, stock, trade, user, vc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    if db.val("SELECT COUNT(*) FROM users") == 0:
        from .auth import setup_code
        logging.getLogger("app").warning("처음 실행: 관리자 가입용 설치 코드 = %s (data/setup_code.txt)", setup_code())
    jobs.start()
    yield
    await jobs.stop()
    await http.close()


app = FastAPI(title="Invest Hub", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
for r in (core, market, stock, discover, trade, community, user, vc, live, pulse):
    app.include_router(r.router)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    # 내부 오류 내용은 로그에만 남기고 화면에는 일반 문구만 보낸다
    logging.getLogger("app").exception("unhandled error on %s", request.url.path)
    return JSONResponse({"detail": "서버에서 처리하지 못했습니다. 잠시 뒤 다시 시도해 주세요"}, status_code=500)


if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        f = DIST / path
        if path and f.is_file() and DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
