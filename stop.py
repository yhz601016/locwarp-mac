"""
LocWarp 一鍵停止（跨平台）
"""

import os
import subprocess
import sys

PORTS = (8777, 5173)
IS_WIN = os.name == "nt"


def _pids_on_port(port):
    pids = set()
    try:
        if IS_WIN:
            out = subprocess.run(
                f'netstat -ano | findstr ":{port}" | findstr "LISTENING"',
                capture_output=True, text=True, shell=True,
            ).stdout
            for line in out.strip().splitlines():
                parts = line.split()
                if parts:
                    pids.add(parts[-1])
        else:
            out = subprocess.run(
                ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
                capture_output=True, text=True,
            ).stdout
            pids.update(l.strip() for l in out.splitlines() if l.strip())
    except Exception:
        pass
    return pids


def main():
    print("  正在停止 LocWarp...")
    for port in PORTS:
        for pid in _pids_on_port(port):
            if IS_WIN:
                subprocess.run(f"taskkill /pid {pid} /f", shell=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["kill", "-9", pid], capture_output=True)
    print("  LocWarp 已停止。")


if __name__ == "__main__":
    main()
    if sys.stdin.isatty():
        input("  按 Enter 離開...")
