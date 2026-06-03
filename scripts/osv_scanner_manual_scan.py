from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def find_osv_scanner(root: Path) -> str | None:
    configured = os.environ.get("RIFTREADER_OSV_SCANNER")
    if configured:
        return configured

    local = root.parent / "tools" / "osv-scanner" / "osv-scanner.cmd"
    if local.exists():
        return str(local)

    return shutil.which("osv-scanner")


def main() -> int:
    root = repo_root()
    scanner = find_osv_scanner(root)
    if not scanner:
        print(
            "OSV-Scanner was not found. Install it under "
            r"C:\RIFT MODDING\tools\osv-scanner or set RIFTREADER_OSV_SCANNER.",
            file=sys.stderr,
        )
        return 2

    cmd = [
        scanner,
        "scan",
        "source",
        "--recursive",
        "--allow-no-lockfiles",
        "--experimental-exclude",
        ".riftreader-local",
        "--experimental-exclude",
        "scripts/captures",
        ".",
    ]
    return subprocess.run(cmd, cwd=root).returncode


if __name__ == "__main__":
    raise SystemExit(main())
