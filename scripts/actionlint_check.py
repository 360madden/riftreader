from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def find_actionlint(root: Path) -> str | None:
    configured = os.environ.get("RIFTREADER_ACTIONLINT")
    if configured:
        return configured

    local = root.parent / "tools" / "actionlint" / "actionlint.cmd"
    if local.exists():
        return str(local)

    return shutil.which("actionlint")


def main() -> int:
    root = repo_root()
    actionlint = find_actionlint(root)
    if not actionlint:
        print(
            "actionlint was not found. Install it under "
            r"C:\RIFT MODDING\tools\actionlint or set RIFTREADER_ACTIONLINT.",
            file=sys.stderr,
        )
        return 2

    return subprocess.run([actionlint], cwd=root).returncode


if __name__ == "__main__":
    raise SystemExit(main())
