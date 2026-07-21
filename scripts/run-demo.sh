#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/meaningsync-demo.XXXXXX")
API_PID=""
WEB_PID=""
cleanup() {
  trap - EXIT INT TERM
  [[ -n "$WEB_PID" ]] && kill "$WEB_PID" 2>/dev/null || true
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
  wait "$WEB_PID" "$API_PID" 2>/dev/null || true
  if [[ -d "$TMP_DIR" ]]; then
    find "$TMP_DIR" -mindepth 1 -delete
    rmdir "$TMP_DIR"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

PYTHON="$ROOT/api/.venv/bin/python"
ALEMBIC="$ROOT/api/.venv/bin/alembic"
[[ -x "$PYTHON" && -x "$ALEMBIC" ]] || { echo "Run 'cd api && uv sync --locked --extra dev' first." >&2; exit 1; }
[[ -d "$ROOT/web/node_modules" ]] || { echo "Run 'cd web && npm ci' first." >&2; exit 1; }

export PYTHONPATH="$ROOT/api"
export MEANINGSYNC_DATABASE_URL="sqlite:///$TMP_DIR/demo.sqlite3"
export MEANINGSYNC_CORS_ORIGINS="http://localhost:3000"
export NEXT_PUBLIC_API_URL="http://localhost:8000"

sed "s|^script_location = .*|script_location = $ROOT/api/alembic|" "$ROOT/api/alembic.ini" > "$TMP_DIR/alembic.ini"
(cd "$TMP_DIR" && "$ALEMBIC" -c "$TMP_DIR/alembic.ini" upgrade head)
(cd "$TMP_DIR" && "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
API_PID=$!
(cd "$ROOT/web" && npm run dev) &
WEB_PID=$!

echo "MeaningSync Demo is starting at http://localhost:3000/demo/setup"
echo "Press Ctrl+C to stop only these two processes."
wait "$API_PID" "$WEB_PID"
