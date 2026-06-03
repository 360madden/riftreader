from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def find_renovate_validator(root: Path) -> str | None:
    configured = os.environ.get("RIFTREADER_RENOVATE_CONFIG_VALIDATOR")
    if configured:
        return configured

    local = root.parent / "tools" / "renovate" / "renovate-config-validator.cmd"
    if local.exists():
        return str(local)

    return shutil.which("renovate-config-validator")


def main() -> int:
    root = repo_root()
    validator = find_renovate_validator(root)
    if not validator:
        print(
            "renovate-config-validator was not found. Install Renovate under "
            r"C:\RIFT MODDING\tools\renovate or set RIFTREADER_RENOVATE_CONFIG_VALIDATOR.",
            file=sys.stderr,
        )
        return 2

    return subprocess.run([validator, "--strict", "--no-global", "renovate.json"], cwd=root).returncode


if __name__ == "__main__":
    raise SystemExit(main())
