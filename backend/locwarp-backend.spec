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


def _openssl_wanted_by_cryptography(names):
    """Return {libname: absolute path} for the OpenSSL dylibs that
    cryptography's _rust.abi3.so resolves through its LC_RPATH entries.
    Empty when the wheel is statically linked (the normal PyPI wheel)."""
    import os
    import subprocess

    found = {}
    try:
        import cryptography.hazmat.bindings._rust as rust_mod
        so_path = rust_mod.__file__
    except Exception as exc:
        print(f"[spec] cryptography _rust not importable ({exc}); skipping rpath probe")
        return found
    try:
        out = subprocess.run(["otool", "-l", so_path], capture_output=True, text=True, timeout=30).stdout
    except Exception as exc:
        print(f"[spec] otool failed ({exc}); skipping rpath probe")
        return found
    rpaths = []
    lines = out.splitlines()
    for i, line in enumerate(lines):
        if "cmd LC_RPATH" in line:
            for j in range(i, min(i + 4, len(lines))):
                if "path " in lines[j]:
                    rpaths.append(lines[j].split("path ", 1)[1].split(" (offset")[0].strip())
                    break
    so_dir = os.path.dirname(so_path)
    for rp in rpaths:
        rp_abs = rp.replace("@loader_path", so_dir).replace("@executable_path", os.path.dirname(sys.executable))
        for base in names:
            cand = os.path.normpath(os.path.join(rp_abs, base))
            if base not in found and os.path.isfile(cand):
                found[base] = cand
    if rpaths:
        print(f"[spec] cryptography rpaths: {rpaths}")
    return found


def _dedupe_openssl_dylibs(analysis):
    """macOS: keep exactly one libssl / libcrypto, the newest one.

    Python's own framework ships OpenSSL 3.0.x, while the `cryptography`
    wheel (and anything built against Homebrew) links OpenSSL 3.2+. Both
    are named libssl.3.dylib; PyInstaller flattens them into _internal/
    and whichever wins is a coin toss. If the 3.0 copy wins, cryptography
    dies at import with "Symbol not found: _SSL_get0_group_name" and the
    backend never starts. OpenSSL 3.x is ABI-compatible within the major
    version, so the newest copy satisfies every consumer.
    """
    import re

    if sys.platform != "darwin":
        return
    names = ("libssl.3.dylib", "libcrypto.3.dylib")
    ver_re = re.compile(rb"OpenSSL (3\.\d+\.\d+)")

    def version_of(path):
        try:
            with open(path, "rb") as fh:
                m = ver_re.search(fh.read())
            return tuple(int(x) for x in m.group(1).split(".")) if m else (0,)
        except Exception:
            return (0,)

    entries = list(analysis.binaries)
    groups = {}
    for dest, src, kind in entries:
        base = dest.replace("\\", "/").split("/")[-1]
        if base in names:
            groups.setdefault(base, []).append((dest, src, kind))
    if not groups:
        return

    # What does cryptography's Rust extension actually want? Resolve its
    # LC_RPATH entries and prefer the libssl/libcrypto found there — that is
    # the exact file dyld would load in a normal venv, so it is guaranteed
    # to export every symbol the extension needs.
    wanted = _openssl_wanted_by_cryptography(names)
    for base, src in wanted.items():
        print(f"[spec] {base}: cryptography's rpath resolves to {src}")

    best_src = {}
    for base, items in groups.items():
        srcs = {src for _d, src, _k in items}
        if base in wanted:
            srcs.add(wanted[base])
        best = wanted.get(base) or max(srcs, key=version_of)
        best_src[base] = best
        print(f"[spec] {base}: {len(srcs)} candidate(s); keeping {best} "
              f"(OpenSSL {'.'.join(map(str, version_of(best)))})")
    # cryptography needs a lib that PyInstaller never collected at all
    # (e.g. only Python's copy was found): add it as a fresh top-level entry.
    for base, src in wanted.items():
        if base not in groups:
            best_src[base] = src
            entries.append((base, src, "BINARY"))
            print(f"[spec] {base}: not collected by analysis; adding {src}")

    seen = set()
    new_entries = []
    for dest, src, kind in entries:
        base = dest.replace("\\", "/").split("/")[-1]
        if base in best_src:
            # Collapse every copy onto ONE top-level entry pointing at the newest file.
            if base in seen:
                continue
            seen.add(base)
            new_entries.append((base, best_src[base], kind))
        else:
            new_entries.append((dest, src, kind))
    analysis.binaries = new_entries


_dedupe_openssl_dylibs(a)

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
