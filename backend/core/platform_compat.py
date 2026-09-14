"""Cross-platform helpers for LocWarp Mac (macOS first, Windows / Linux still work).

The original LocWarp was Windows-only: the iOS 17+ tunnel was built on a
kernel TUN adapter (wintun.dll), which is why it insisted on Administrator.
pymobiledevice3 11.x ships a pure-userspace TCP/IP stack (``pmd-pytcp``)
that needs **no root at all**, so on macOS the default is:

* ``userspace`` tunnel mode  -> no sudo prompt, one iPhone at a time
* ``kernel`` tunnel mode     -> only when the backend runs as root
  (``sudo python3 start.py``), up to three iPhones at once

Override with the ``LOCWARP_TUNNEL_MODE`` environment variable
(``auto`` | ``kernel`` | ``userspace``).
"""

from __future__ import annotations

import logging
import os
import platform as _platform
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

TUNNEL_MODE_ENV = "LOCWARP_TUNNEL_MODE"
AUTO_MOUNT_DDI_ENV = "LOCWARP_AUTO_MOUNT_DDI"

_VALID_MODES = ("auto", "kernel", "userspace")
_applied_mode: str | None = None


def is_privileged() -> bool:
    """True when the backend runs as Administrator (Windows) or root (Unix)."""
    if IS_WIN:
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
        except Exception:
            return False
    try:
        return os.geteuid() == 0  # type: ignore[attr-defined]
    except AttributeError:
        return False


def resolve_tunnel_mode() -> str:
    """Decide which tunnel backend to use without touching pymobiledevice3."""
    mode = os.environ.get(TUNNEL_MODE_ENV, "auto").strip().lower()
    if mode not in _VALID_MODES:
        logger.warning("Unknown %s=%r, falling back to auto", TUNNEL_MODE_ENV, mode)
        mode = "auto"
    if mode == "auto":
        mode = "kernel" if is_privileged() else "userspace"
    return mode


def apply_tunnel_mode() -> str:
    """Flip pymobiledevice3's module-level switch. Call once at startup,
    before any tunnel is created."""
    global _applied_mode
    mode = resolve_tunnel_mode()
    try:
        from pymobiledevice3.remote import tunnel_service
        if not hasattr(tunnel_service, "USE_USERSPACE_TUNNEL"):
            raise AttributeError("USE_USERSPACE_TUNNEL missing (pymobiledevice3 too old?)")
        tunnel_service.USE_USERSPACE_TUNNEL = (mode == "userspace")
    except Exception:
        logger.exception(
            "Could not apply tunnel mode %s; pymobiledevice3 will use its default (kernel TUN)",
            mode,
        )
        mode = "kernel"
    _applied_mode = mode
    logger.info(
        "Tunnel mode: %s (platform=%s, privileged=%s)",
        mode, sys.platform, is_privileged(),
    )
    return mode


def tunnel_mode() -> str:
    return _applied_mode or resolve_tunnel_mode()


def max_devices() -> int:
    """Kernel mode: the upstream three-device cap.

    No-root mode on macOS rides Apple's own `remoted` tunnel (one per
    device), so several iPhones work there too. On Windows / Linux the
    no-root path is the in-process PyTCP stack, a process-global singleton,
    so only one iOS 17+ iPhone fits per process."""
    if tunnel_mode() == "kernel" or IS_MAC:
        return 3
    return 1


def privilege_hint() -> str:
    if IS_MAC:
        return (
            "macOS：請確認 iPhone 已解鎖、已按「信任」、開發者模式已開啟，然後重新插拔 USB。"
            "詳細原因請看 ~/.locwarp/logs/backend.log。"
        )
    if IS_WIN:
        return "Windows：請以系統管理員身份執行 LocWarp（或設定 LOCWARP_TUNNEL_MODE=userspace）。"
    return "Linux：請以 root 執行後端，或設定 LOCWARP_TUNNEL_MODE=userspace。"


def auto_mount_ddi_enabled() -> bool:
    """Whether LocWarp should try to download + mount the Personalized DDI
    itself. Default ON for macOS / Linux (no Xcode / 3uTools needed);
    OFF on Windows to keep the upstream behaviour."""
    raw = os.environ.get(AUTO_MOUNT_DDI_ENV)
    if raw is not None:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return not IS_WIN


def lockdown_pair_record_dirs() -> list[Path]:
    """Directories that may hold ``<udid>.plist`` lockdown pair records,
    most authoritative first."""
    dirs: list[Path] = []
    if IS_WIN:
        dirs.append(Path(os.environ.get("ALLUSERSPROFILE", "C:/ProgramData")) / "Apple" / "Lockdown")
    elif IS_MAC:
        dirs.append(Path("/var/db/lockdown"))  # root-only on modern macOS
    else:
        dirs.append(Path("/var/lib/lockdown"))
    # pymobiledevice3 keeps its own copy when it cannot write the system store.
    try:
        from pymobiledevice3.common import get_home_folder
        dirs.append(Path(get_home_folder()))
    except Exception:
        dirs.append(Path.home() / ".pymobiledevice3")
    return dirs


def describe_platform() -> dict:
    """Small JSON-able summary exposed at /api/system/platform."""
    return {
        "os": sys.platform,
        "os_release": _platform.release(),
        "machine": _platform.machine(),
        "python": _platform.python_version(),
        "privileged": is_privileged(),
        "tunnel_mode": tunnel_mode(),
        "max_devices": max_devices(),
        "auto_mount_ddi": auto_mount_ddi_enabled(),
    }
