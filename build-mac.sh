#!/bin/bash
# LocWarp Mac — one-shot build: PyInstaller backend + Vite frontend + electron-builder DMG.
#
# Prereqs (install once):
#   brew install python@3.13 node
#   python3.13 -m pip install -r backend/requirements.txt pyinstaller
#   (cd frontend && npm install)
#
# Usage:
#   ./build-mac.sh            # build for the CPU you're on (arm64 on Apple Silicon)
#   ./build-mac.sh --skip-py  # reuse an existing dist-py/ backend build
#
# Output: frontend/release/LocWarp-<version>-mac-<arch>.dmg (+ .zip)
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for cand in python3.13 python3.14 python3; do
    if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
  done
fi
[ -n "$PY" ] || { echo "python3 not found"; exit 1; }

ARCH="$(uname -m)"           # arm64 | x86_64
EB_ARCH="arm64"; [ "$ARCH" = "x86_64" ] && EB_ARCH="x64"

echo
echo "============================================================"
echo " [1/3] Build backend with PyInstaller ($PY, $ARCH)"
echo "============================================================"
if [ "${1:-}" != "--skip-py" ]; then
  rm -rf "$ROOT/dist-py" "$ROOT/build-py"
  (cd "$ROOT/backend" && "$PY" -m PyInstaller locwarp-backend.spec --noconfirm \
      --distpath "$ROOT/dist-py" --workpath "$ROOT/build-py/backend")
fi
[ -x "$ROOT/dist-py/locwarp-backend/locwarp-backend" ] || { echo "backend build missing"; exit 1; }

echo
echo "============================================================"
echo " [2/3] Build frontend (Vite)"
echo "============================================================"
(cd "$ROOT/frontend" && npm run build)

echo
echo "============================================================"
echo " [3/3] Package DMG (electron-builder --mac --$EB_ARCH)"
echo "============================================================"
(cd "$ROOT/frontend" && npx electron-builder --mac --"$EB_ARCH" --publish never)

echo
echo "============================================================"
echo " DONE — artifacts in frontend/release/"
echo "============================================================"
ls -1 "$ROOT/frontend/release/" | grep -E '\.(dmg|zip)$' || true
