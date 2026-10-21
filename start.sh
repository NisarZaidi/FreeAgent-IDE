#!/usr/bin/env bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -f "$ROOT/backend/.venv/bin/python" ]; then
  echo "Virtualenv missing. Run ./install.sh first."
  exit 1
fi
# shellcheck disable=SC1091
source "$ROOT/backend/.venv/bin/activate"
cd "$ROOT/backend"
echo "Starting FreeAgent IDE at http://127.0.0.1:8765"
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
