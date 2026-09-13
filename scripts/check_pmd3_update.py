"""Compare the pymobiledevice3 pin in backend/requirements.txt with PyPI.

Used by .github/workflows/pmd3-watch.yml. When PyPI has a newer release the
pin is rewritten to ``pymobiledevice3>=<latest>`` and ``updated=true`` is
written to $GITHUB_OUTPUT. Safe to run locally:

    python scripts/check_pmd3_update.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQ = ROOT / "backend" / "requirements.txt"
PYPI = "https://pypi.org/pypi/pymobiledevice3/json"
PIN_RE = re.compile(r"^(pymobiledevice3)\s*(>=|==)\s*([0-9][0-9A-Za-z.]*)\s*$", re.M)


def _ver(s: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", s))


def _output(**kv: str) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    for k, v in kv.items():
        print(f"{k}={v}")
        if out:
            with open(out, "a", encoding="utf-8") as fh:
                fh.write(f"{k}={v}\n")


def main() -> int:
    text = REQ.read_text(encoding="utf-8")
    m = PIN_RE.search(text)
    if not m:
        print("no pymobiledevice3 pin found in", REQ, file=sys.stderr)
        return 1
    current = m.group(3)

    with urllib.request.urlopen(PYPI, timeout=30) as resp:
        latest = json.load(resp)["info"]["version"]

    force = os.environ.get("FORCE", "").lower() in ("1", "true", "yes")
    newer = _ver(latest) > _ver(current)
    print(f"pinned: {current}   pypi latest: {latest}   newer: {newer}   force: {force}")

    if not newer and not force:
        _output(updated="false", current=current, latest=latest)
        return 0

    new_text = PIN_RE.sub(rf"\g<1>>={latest}", text, count=1)
    REQ.write_text(new_text, encoding="utf-8")
    _output(updated="true", current=current, latest=latest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
