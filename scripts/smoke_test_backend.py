"""Smoke test: does the installed pymobiledevice3 still expose everything the
LocWarp backend relies on, and does the backend import cleanly?

Run after `pip install -r backend/requirements.txt`:

    python scripts/smoke_test_backend.py

Exit code 0 = OK. Anything else = a human needs to look at the upgrade.
No iPhone is required; nothing talks to a device.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

failures: list[str] = []


def check(label: str, fn) -> None:
    try:
        fn()
        print(f"  [OK]   {label}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"{label}: {type(exc).__name__}: {exc}")
        print(f"  [FAIL] {label}: {type(exc).__name__}: {exc}")


def _attr(module: str, *names: str):
    def _inner():
        mod = importlib.import_module(module)
        for n in names:
            if not hasattr(mod, n):
                raise AttributeError(f"{module}.{n} missing")
    return _inner


print("pymobiledevice3 API surface used by LocWarp:")
from importlib.metadata import version as _dist_version  # noqa: E402
print("  version:", _dist_version("pymobiledevice3"))

check("tunnel_service.USE_USERSPACE_TUNNEL / CoreDeviceTunnelProxy / create_core_device_tunnel_service_using_remotepairing",
      _attr("pymobiledevice3.remote.tunnel_service",
            "USE_USERSPACE_TUNNEL", "CoreDeviceTunnelProxy",
            "create_core_device_tunnel_service_using_remotepairing"))
check("userspace_tunnel.UserspaceTun", _attr("pymobiledevice3.remote.userspace_tunnel", "UserspaceTun"))
check("remote_service_discovery.RemoteServiceDiscoveryService",
      _attr("pymobiledevice3.remote.remote_service_discovery", "RemoteServiceDiscoveryService"))
check("lockdown.create_using_usbmux / create_using_tcp",
      _attr("pymobiledevice3.lockdown", "create_using_usbmux", "create_using_tcp"))
check("usbmux.list_devices", _attr("pymobiledevice3.usbmux", "list_devices"))
check("dvt_provider.DvtProvider", _attr("pymobiledevice3.services.dvt.instruments.dvt_provider", "DvtProvider"))
check("location_simulation.LocationSimulation",
      _attr("pymobiledevice3.services.dvt.instruments.location_simulation", "LocationSimulation"))
check("simulate_location.DtSimulateLocation", _attr("pymobiledevice3.services.simulate_location", "DtSimulateLocation"))
check("mobile_image_mounter.MobileImageMounterService / auto_mount_personalized",
      _attr("pymobiledevice3.services.mobile_image_mounter", "MobileImageMounterService", "auto_mount_personalized"))


def _import_backend():
    import os
    os.environ.setdefault("LOCWARP_TUNNEL_MODE", "userspace")
    import core.platform_compat as pc
    mode = pc.apply_tunnel_mode()
    assert mode == "userspace", mode
    from pymobiledevice3.remote import tunnel_service
    assert tunnel_service.USE_USERSPACE_TUNNEL is True
    importlib.import_module("core.device_manager")
    importlib.import_module("services.location_service")
    importlib.import_module("core.wifi_tunnel")
    # Import the FastAPI app itself (registers every router).
    importlib.import_module("main")


print("\nLocWarp backend import:")
check("backend imports with userspace tunnel mode applied", _import_backend)

if failures:
    print(f"\n{len(failures)} check(s) failed:")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("\nAll checks passed.")
