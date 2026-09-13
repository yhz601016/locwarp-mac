"""
LocWarp Mac 一鍵啟動器（開發模式）

macOS：雙擊 LocWarp.command，或在終端機執行  python3 start.py
Windows / Linux：python start.py

參數：
  --kernel-tunnel   強制 kernel TUN 模式（macOS 需 sudo；可同時連 3 支 iPhone）
  --no-browser      啟動後不自動開瀏覽器
"""

import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")
FRONTEND = os.path.join(ROOT, "frontend")

BACKEND_PORT = 8777
FRONTEND_PORT = 5173

IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"

procs = []


def print_banner():
    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║   LocWarp Mac — iOS 虛擬定位模擬器        ║")
    print("  ╚══════════════════════════════════════════╝")
    print()


def check_tool(name, hint):
    if shutil.which(name):
        print(f"  [✓] 已找到 {name}")
        return True
    print(f"  [✗] 找不到 {name}，請先安裝：{hint}")
    return False


def is_port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except (ConnectionRefusedError, OSError, TimeoutError):
        return False


def _pids_on_port(port):
    """PIDs listening on *port* (cross-platform)."""
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
            for line in out.strip().splitlines():
                if line.strip():
                    pids.add(line.strip())
    except Exception:
        pass
    return pids


def kill_port(port):
    for pid in _pids_on_port(port):
        try:
            if IS_WIN:
                subprocess.run(f"taskkill /pid {pid} /f", shell=True, capture_output=True)
            else:
                subprocess.run(["kill", "-9", pid], capture_output=True)
        except Exception:
            pass


def wait_for_port(port, label, timeout=90):
    print(f"      等待{label}啟動中", end="", flush=True)
    start = time.time()
    while time.time() - start < timeout:
        if is_port_open(port):
            print(" OK ✓")
            return True
        print(".", end="", flush=True)
        time.sleep(2)
    print(" 超時！")
    return False


def install_backend():
    print("  [1/4] 檢查後端依賴...", end=" ", flush=True)
    req = os.path.join(BACKEND, "requirements.txt")
    dry = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", req, "--dry-run", "-q"],
        capture_output=True, text=True,
    )
    if "would install" not in dry.stdout.lower():
        print("已就緒 ✓")
        return
    print("安裝中（首次約 1-3 分鐘）...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", req, "-q"], cwd=BACKEND)
    print("        完成 ✓")


def install_frontend():
    print("  [2/4] 檢查前端依賴...", end=" ", flush=True)
    if os.path.isdir(os.path.join(FRONTEND, "node_modules")):
        print("已就緒 ✓")
        return
    print("安裝中...")
    subprocess.run(["npm", "install"], cwd=FRONTEND, shell=IS_WIN)
    print("        完成 ✓")


def _popen(cmd, cwd, env=None, shell=False):
    kwargs = {"cwd": cwd, "env": env, "shell": shell}
    if IS_WIN:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def start_backend(env):
    print(f"  [3/4] 啟動後端服務 (port {BACKEND_PORT})...")
    if is_port_open(BACKEND_PORT):
        print(f"      Port {BACKEND_PORT} 被佔用，清理中...")
        kill_port(BACKEND_PORT)
        time.sleep(1)
    procs.append(_popen([sys.executable, "main.py"], BACKEND, env=env))
    return wait_for_port(BACKEND_PORT, "後端")


def start_frontend():
    print(f"  [4/4] 啟動前端服務 (port {FRONTEND_PORT})...")
    if is_port_open(FRONTEND_PORT):
        print(f"      Port {FRONTEND_PORT} 被佔用，清理中...")
        kill_port(FRONTEND_PORT)
        time.sleep(1)
    cmd = ["npx", "vite", "--host", "--port", str(FRONTEND_PORT), "--strictPort"]
    procs.append(_popen(cmd, FRONTEND, shell=IS_WIN))
    return wait_for_port(FRONTEND_PORT, "前端")


def cleanup():
    print("\n  正在關閉所有服務...")
    for p in procs:
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    kill_port(BACKEND_PORT)
    kill_port(FRONTEND_PORT)
    print("  已停止。再見！")


def is_privileged():
    if IS_WIN:
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return os.geteuid() == 0


def main():
    args = set(sys.argv[1:])
    print_banner()

    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    want_kernel = "--kernel-tunnel" in args
    if want_kernel:
        env["LOCWARP_TUNNEL_MODE"] = "kernel"
        if not is_privileged():
            print("  [!] --kernel-tunnel 需要 root / 管理員權限")
            if IS_MAC:
                print("      請改用：sudo python3 start.py --kernel-tunnel")
            return
    else:
        mode = "kernel（多裝置）" if is_privileged() else "userspace（免權限，一次一支 iPhone）"
        print(f"  Tunnel 模式：{mode}")
        if IS_MAC and not is_privileged():
            print("      想同時連多支 iPhone？改用：sudo python3 start.py")
        print()

    ok = True
    ok = check_tool("node", "https://nodejs.org/") and ok
    ok = check_tool("npm", "隨 Node.js 一起安裝") and ok
    print()
    if not ok:
        input("  缺少必要工具，請安裝後重試。按 Enter 離開...")
        return

    if sys.version_info < (3, 13):
        print(f"  [!] 目前 Python {sys.version.split()[0]}；WiFi Tunnel 需要 Python 3.13+（USB 模式仍可用）")
        print()

    install_backend()
    print()
    install_frontend()
    print()

    if not start_backend(env):
        print("  [錯誤] 後端啟動失敗，請查看上方錯誤訊息（log 在 ~/.locwarp/logs/backend.log）")
        cleanup()
        input("  按 Enter 離開...")
        return
    print()

    if not start_frontend():
        print("  [錯誤] 前端啟動失敗")
        cleanup()
        input("  按 Enter 離開...")
        return
    print()

    time.sleep(2)
    url = f"http://localhost:{FRONTEND_PORT}"
    if "--no-browser" not in args:
        webbrowser.open(url)

    print("  ╔══════════════════════════════════════════╗")
    print("  ║          LocWarp 已就緒！                ║")
    print("  ╠══════════════════════════════════════════╣")
    print(f"  ║  前端畫面:  http://localhost:{FRONTEND_PORT}        ║")
    print(f"  ║  後端 API:  http://localhost:{BACKEND_PORT}        ║")
    print(f"  ║  API 文件:  http://localhost:{BACKEND_PORT}/docs   ║")
    print("  ╠══════════════════════════════════════════╣")
    print("  ║  按 Enter 或 Ctrl+C 停止所有服務         ║")
    print("  ╚══════════════════════════════════════════╝")
    print()

    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass
    cleanup()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        cleanup()
