#!/bin/bash
# Invest Hub 실행. 처음이면 의존성을 설치하고 화면을 빌드한다.
#   ./run.sh            포그라운드 실행 (Ctrl+C로 종료)
#   PORT=9000 ./run.sh  다른 포트
set -e
cd "$(dirname "$0")"
PORT="${PORT:-8700}"
HOST="${HOST:-0.0.0.0}"

if [ ! -x backend/.venv/bin/uvicorn ]; then
  echo "[1/2] 파이썬 환경 설치"
  (cd backend && uv venv --python 3.12 .venv -q && uv pip install -q -p .venv/bin/python -r pyproject.toml)
fi
if [ ! -f frontend/dist/index.html ] || [ -n "$(find frontend/src -newer frontend/dist/index.html -print -quit)" ]; then
  echo "[2/2] 화면 빌드"
  (cd frontend && { [ -d node_modules ] || npm install --no-audit --no-fund --loglevel=error; } && npx vite build >/dev/null)
fi

echo "Invest Hub → http://$(hostname -I | awk '{print $1}'):$PORT  (이 PC에서는 http://127.0.0.1:$PORT)"
cd backend
exec .venv/bin/uvicorn app.main:app --host "$HOST" --port "$PORT" --log-level warning
