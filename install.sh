#!/usr/bin/env bash
# Install Quill for the current user (macOS / Linux). Run from the repo folder:  ./install.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/quill"
BIN_DIR="$HOME/.local/bin"

say() { printf '\033[1m%s\033[0m\n' "$*"; }

# 1. Find Python 3.10+
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  say "Quill needs Python 3.10 or newer."
  echo "Install it from https://www.python.org/downloads/ (or 'brew install python' on a Mac), then run ./install.sh again."
  exit 1
fi

# 2. Private environment so Quill never conflicts with other Python software
say "Installing Quill…"
"$PY" -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/python" -m pip install --quiet --upgrade pip
"$APP_DIR/venv/bin/python" -m pip install --quiet --upgrade "$HERE"

mkdir -p "$BIN_DIR"
ln -sf "$APP_DIR/venv/bin/quill" "$BIN_DIR/quill"

# 3. Something to double-click
case "$(uname -s)" in
  Darwin)
    SHORTCUT="$HOME/Desktop/Quill.command"
    printf '#!/bin/bash\nexec "%s"\n' "$APP_DIR/venv/bin/quill" > "$SHORTCUT"
    chmod +x "$SHORTCUT"
    say "Added Quill to your Desktop — double-click it to start writing."
    ;;
  Linux)
    mkdir -p "$HOME/.local/share/applications"
    cat > "$HOME/.local/share/applications/quill.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Quill
Comment=Your personal writing partner
Exec=$APP_DIR/venv/bin/quill
Terminal=true
Categories=Office;TextEditor;
DESKTOP
    say "Added Quill to your applications menu."
    ;;
esac

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Tip: add this line to your ~/.zshrc or ~/.bashrc so the 'quill' command works everywhere:"
     echo "  export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac

say "Done! Starting Quill in your browser…"
exec "$APP_DIR/venv/bin/quill"
