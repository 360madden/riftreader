from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def find_gitleaks(root: Path) -> str | None:
    configured = os.environ.get("RIFTREADER_GITLEAKS")
    if configured:
        return configured

    local_tools = root.parent / "tools" / "gitleaks"
    candidates = [
        local_tools / "gitleaks.cmd",
        local_tools / "gitleaks.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return shutil.which("gitleaks")


def main() -> int:
    root = repo_root()
    gitleaks = find_gitleaks(root)
    if not gitleaks:
        print(
            "Gitleaks was not found. Install it under "
            r"C:\RIFT MODDING\tools\gitleaks or set RIFTREADER_GITLEAKS.",
            file=sys.stderr,
        )
        return 2

    cmd = [
        gitleaks,
        "git",
        "--no-banner",
        "--redact",
        "--verbose",
        ".",
    ]
    completed = subprocess.run(cmd, cwd=root)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
