#!/usr/bin/env bash
# FreeAgent IDE — Linux one-command installer
# Usage: curl -fsSL https://raw.githubusercontent.com/<user>/FreeAgent-IDE/main/install.sh | bash
# Or from a cloned repo: bash install.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
echo ""
echo "FreeAgent IDE installer"
echo "========================"
echo "Root: $ROOT"
echo "OS: $(uname -s) / $(uname -m)"

have() { command -v "$1" >/dev/null 2>&1; }

# --- Python ---
PYTHON=""
for cand in python3.12 python3.11 python3; do
  if have "$cand"; then
    ver="$("$cand" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    major="${ver%%.*}"; minor="${ver#*.}"
    if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; }; then
      PYTHON="$cand"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo "Python 3.11+ required. Install via your package manager, e.g.:"
  echo "  Ubuntu: sudo apt install python3.12 python3.12-venv python3-pip"
  echo "  Fedora: sudo dnf install python3.12"
  exit 1
fi
echo "Using: $($PYTHON --version)"

# --- Node ---
if ! have node; then
  echo "Node.js not found. Install Node 18+ then re-run to build the UI."
  echo "  Ubuntu: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs"
fi

# --- Ollama ---
if ! have ollama; then
  read -r -p "Install Ollama for local models? [Y/n] " ans || true
  ans="${ans:-Y}"
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    curl -fsSL https://ollama.com/install.sh | sh
  fi
fi

# --- venv ---
VENV="$ROOT/backend/.venv"
if [ ! -d "$VENV" ]; then
  echo "Creating virtual environment..."
  "$PYTHON" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install --upgrade pip
pip install -e "$ROOT/backend"

# --- Frontend ---
if have npm; then
  echo "Installing & building frontend..."
  (cd "$ROOT/frontend" && npm install && npm run build)
else
  echo "Skipping UI build (npm missing)."
fi

# --- Model ---
if have ollama; then
  read -r -p "Download recommended model llama3.2:3b now? [Y/n] " pull || true
  pull="${pull:-Y}"
  if [[ "$pull" =~ ^[Yy]$ ]]; then
    ollama pull llama3.2:3b || true
  fi
fi

# --- Launcher ---
cat > "$ROOT/start.sh" <<'EOF'
#!/usr/bin/env bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$ROOT/backend/.venv/bin/activate"
cd "$ROOT/backend"
echo "Starting FreeAgent IDE at http://127.0.0.1:8765"
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
EOF
chmod +x "$ROOT/start.sh" "$ROOT/install.sh"

# Optional desktop entry
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APP_DIR"
cat > "$APP_DIR/freeagent-ide.desktop" <<EOF
[Desktop Entry]
Name=FreeAgent IDE
Comment=Local-first multi-agent AI coding IDE
Exec=$ROOT/start.sh
Terminal=true
Type=Application
Categories=Development;IDE;
EOF

echo ""
echo "Install complete."
echo "Next steps:"
echo "  1. Start Ollama if using local models (ollama serve)"
echo "  2. Run:  $ROOT/start.sh"
echo "  3. Open: http://127.0.0.1:8765"
echo ""

read -r -p "Launch FreeAgent IDE now? [Y/n] " launch || true
launch="${launch:-Y}"
if [[ "$launch" =~ ^[Yy]$ ]]; then
  exec "$ROOT/start.sh"
fi
