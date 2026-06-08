#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/verify_feishu_acceptance.sh <base_url> [--upload]

Runs the Feishu acceptance checks for a deployed Xingtu BI URL:
- API health, homepage, admin page, iframe headers, and overview contract
- Optional upload refresh and business contract checks
- Optional iframe DOM render check when Playwright is available

Environment overrides:
  PYTHON_BIN=/path/to/python
  NODE_BIN=/path/to/node
  NODE_PATH=/path/to/node_modules
EOF
}

BASE_URL="${1:-}"
UPLOAD_FLAG="${2:-}"

if [[ -z "$BASE_URL" || "$BASE_URL" == "-h" || "$BASE_URL" == "--help" ]]; then
  usage
  if [[ -z "$BASE_URL" ]]; then
    exit 2
  fi
  exit 0
fi

if [[ -n "$UPLOAD_FLAG" && "$UPLOAD_FLAG" != "--upload" ]]; then
  usage
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
NODE_BIN="${NODE_BIN:-node}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python executable not found or not executable: $PYTHON_BIN" >&2
  exit 1
fi

cd "$ROOT_DIR"

"$PYTHON_BIN" scripts/verify_feishu_deploy.py "$BASE_URL"

if [[ "$UPLOAD_FLAG" == "--upload" ]]; then
  "$PYTHON_BIN" scripts/verify_feishu_deploy.py "$BASE_URL" --upload
fi

if "$NODE_BIN" -e "require.resolve('playwright')" >/dev/null 2>&1; then
  "$NODE_BIN" scripts/verify_feishu_iframe_render.cjs "$BASE_URL"
else
  echo '{"iframe_dom":"skipped","reason":"Playwright is not resolvable for NODE_BIN/NODE_PATH"}'
fi
