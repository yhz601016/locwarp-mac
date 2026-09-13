#!/bin/bash
# LocWarp Mac — 雙擊即可啟動（開發 / 原始碼模式）
# 免 sudo：一次一支 iPhone。要同時連多支 iPhone 請在終端機執行：
#   sudo python3 start.py --kernel-tunnel
cd "$(dirname "$0")" || exit 1

PY=""
for cand in python3.13 python3.14 python3; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
  echo "找不到 python3。請先安裝：brew install python@3.13  或  https://www.python.org/downloads/macos/"
  read -r -p "按 Enter 離開..."
  exit 1
fi

exec "$PY" start.py "$@"
