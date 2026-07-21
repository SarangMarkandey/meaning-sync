#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/meaningsync-verify.XXXXXX")
cleanup() { find "$TMP_DIR" -mindepth 1 -delete; rmdir "$TMP_DIR"; }
trap cleanup EXIT

for executable in bash python3 node npm; do
  command -v "$executable" >/dev/null || { echo "Missing required executable: $executable" >&2; exit 1; }
done

PYTHON="$ROOT/api/.venv/bin/python"
PYTEST="$ROOT/api/.venv/bin/pytest"
ALEMBIC="$ROOT/api/.venv/bin/alembic"
for executable in "$PYTHON" "$PYTEST" "$ALEMBIC"; do
  [[ -x "$executable" ]] || { echo "Run 'cd api && uv sync --locked --extra dev' first." >&2; exit 1; }
done
[[ -d "$ROOT/web/node_modules" ]] || { echo "Run 'cd web && npm ci' first." >&2; exit 1; }

export PYTHONPATH="$ROOT/api"
export MEANINGSYNC_DATABASE_URL="sqlite:///$TMP_DIR/verification.sqlite3"
export MEANINGSYNC_CORS_ORIGINS="http://localhost:3000"
(
  cd "$TMP_DIR"
  "$PYTHON" -c "from app.main import app; assert app.title == 'MeaningSync API'"
  sed "s|^script_location = .*|script_location = $ROOT/api/alembic|" "$ROOT/api/alembic.ini" > "$TMP_DIR/alembic.ini"
  "$ALEMBIC" -c "$TMP_DIR/alembic.ini" upgrade head
)

(
  cd "$TMP_DIR"
  "$PYTEST" -c "$ROOT/api/pyproject.toml" \
    "$ROOT/api/tests/test_bilingual.py" \
    "$ROOT/api/tests/test_sessions.py"
)
(
  cd "$ROOT/web"
  npm run type-check
  npm test -- --run src/components/bilingual-ui.test.tsx src/components/demo-setup.test.tsx src/app/page.test.tsx
)

echo "MeaningSync deterministic submission verification passed."
