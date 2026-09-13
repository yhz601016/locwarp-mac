# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the LocWarp backend — cross-platform (macOS / Windows / Linux).
# Build (from the backend/ directory):
#   python3.13 -m PyInstaller locwarp-backend.spec --noconfirm
#
# pymobiledevice3 resolves a lot of modules dynamically, so we collect entire
# packages instead of relying on import analysis. Packages that only exist on
# some platforms (pytun_pmd3's wintun.dll, psutil's Windows extension) are
# collected best-effort: a missing package just contributes nothing.

import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata


def _collect(name):
    try:
        return collect_all(name)
    except Exception as exc:  # package not installed on this platform
        print(f"[spec] collect_all({name!r}) skipped: {exc}")
        return [], [], []


def _metadata(name):
    try:
        return copy_metadata(name)
    except Exception as exc:
        print(f"[spec] copy_metadata({name!r}) skipped: {exc}")
        return []


def _submodules(name):
    try:
        return collect_submodules(name)
    except Exception as exc:
        print(f"[spec] collect_submodules({name!r}) skipped: {exc}")
        return []


datas, binaries, hidden = [], [], []

# Core iOS protocol stack + everything it lazily imports.
for pkg in (
    "pymobiledevice3",
    "pytun_pmd3",            # kernel TUN (utun on macOS / wintun on Windows) — root mode only
    "pmd_pytcp",             # userspace TCP/IP stack — no-root tunnel mode (default on macOS)
    "pmd_net_addr",
    "pmd_net_proto",
    "developer_disk_image",  # Personalized DDI download (auto-mount on macOS)
    "pyimg4",
    "qh3",                   # imported by tunnel_service even though we only use TCP tunnels
    "psutil",
    "ifaddr",
    "construct",
    "construct_typing",
):
    d, b, h = _collect(pkg)
    datas += d
    binaries += b
    hidden += h

# importlib.metadata lookups performed at import time.
for pkg in ("pyimg4", "pymobiledevice3", "developer_disk_image", "pmd_pytcp"):
    datas += _metadata(pkg)

# Web stack.
for pkg in ("uvicorn", "fastapi", "websockets", "anyio", "starlette"):
    hidden += _submodules(pkg)

hidden += [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "gpxpy",
    "httpx",
    "multipart",
    "plistlib",
]

datas += [("static/phone.html", "static")]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hidden)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "scipy", "pandas", "IPython", "xonsh"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="locwarp-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,          # native arch of the build machine (arm64 / x86_64)
    codesign_identity=None,    # PyInstaller ad-hoc signs on macOS by default
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="locwarp-backend",
)
