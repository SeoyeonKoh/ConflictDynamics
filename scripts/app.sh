#!/usr/bin/env bash
# Open the Conflict Dynamics app: the backend (conflict-server) and the viewer together.
#
#   scripts/app.sh            development: conflict-server :8780 + vite dev :5173 (live reload)
#   scripts/app.sh --build    one server: build the viewer, conflict-server serves it on :8780
#
# Ctrl-C stops everything this script started. Ports: CD_API_PORT (8780), CD_WEB_PORT (5173).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
API_PORT="${CD_API_PORT:-8780}"
WEB_PORT="${CD_WEB_PORT:-5173}"
MODE="dev"
[[ "${1:-}" == "--build" ]] && MODE="build"

if [[ -x .venv/bin/conflict-server ]]; then
  SERVER=(.venv/bin/conflict-server)
else
  SERVER=(uv run conflict-server)
fi
command -v npm >/dev/null || { echo "npm이 필요해요 (Node.js 설치)."; exit 1; }
[[ -d viz/node_modules ]] || (cd viz && npm install)

port_busy() { lsof -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }
for port in "$API_PORT" $([[ $MODE == dev ]] && echo "$WEB_PORT"); do
  if port_busy "$port"; then
    echo "포트 $port 이(가) 이미 쓰이고 있어요. 앞서 띄운 앱을 닫거나 CD_API_PORT/CD_WEB_PORT를 바꿔 주세요."
    exit 1
  fi
done

PIDS=()
cleanup() {
  trap - INT TERM EXIT
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
  echo
  echo "앱을 닫았어요. (진행 중이던 라이브 run은 계속 돌아요. 다시 열면 메인 화면에서 이어서 볼 수 있어요.)"
}
trap cleanup INT TERM EXIT

LOGS="$ROOT/.conflict-sim/logs"
mkdir -p "$LOGS"

if [[ $MODE == build ]]; then
  echo "뷰어를 빌드하는 중…"
  (cd viz && npm run build >"$LOGS/build.log" 2>&1) || { tail -20 "$LOGS/build.log"; exit 1; }
  "${SERVER[@]}" --port "$API_PORT" >"$LOGS/server.log" 2>&1 &
  PIDS+=($!)
  URL="http://127.0.0.1:$API_PORT/"
else
  "${SERVER[@]}" --port "$API_PORT" --static /nonexistent >"$LOGS/server.log" 2>&1 &
  PIDS+=($!)
  (cd viz && exec ./node_modules/.bin/vite --port "$WEB_PORT" --strictPort >"$LOGS/vite.log" 2>&1) &
  PIDS+=($!)
  URL="http://localhost:$WEB_PORT/"
fi

# Wait until the app answers (up to 30 s).
for _ in $(seq 60); do
  if curl -fs -o /dev/null "${URL}api/settings"; then break; fi
  for pid in "${PIDS[@]}"; do
    kill -0 "$pid" 2>/dev/null || { echo "앱을 띄우지 못했어요. 로그: $LOGS"; tail -20 "$LOGS"/*.log; exit 1; }
  done
  sleep 0.5
done

cat <<EOF

  ┌───────────────────────────────────────────────────────────┐
     Conflict Dynamics 앱이 열렸어요
     브라우저에서 →  $URL
  └───────────────────────────────────────────────────────────┘
   메인 화면: 라이브 실행 · 리플레이 · 환경 설정
   백엔드 API: http://127.0.0.1:$API_PORT/api   ($( [[ $MODE == dev ]] && echo "개발 모드: 화면 수정이 바로 반영돼요" || echo "빌드한 화면을 서버 하나로 제공") )
   로그: $LOGS
   끄려면 Ctrl-C

EOF

wait
