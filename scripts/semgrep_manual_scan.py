from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def find_semgrep(root: Path) -> str | None:
    configured = os.environ.get("RIFTREADER_SEMGREP")
    if configured:
        return configured

    local = root.parent / "tools" / "semgrep" / "semgrep.cmd"
    if local.exists():
        return str(local)

    return shutil.which("semgrep")


def main() -> int:
    root = repo_root()
    semgrep = find_semgrep(root)
    if not semgrep:
        print(
            "Semgrep was not found. Install it under "
            r"C:\RIFT MODDING\tools\semgrep or set RIFTREADER_SEMGREP.",
            file=sys.stderr,
        )
        return 2

    cmd = [
        semgrep,
        "scan",
        "--config",
        "semgrep.yml",
        "--error",
        "--no-git-ignore",
        "--exclude",
        "scripts/captures",
        "--skip-unknown-extensions",
        "--metrics=off",
        "scripts",
        "tools/riftreader_workflow",
    ]
    return subprocess.run(cmd, cwd=root).returncode


if __name__ == "__main__":
    raise SystemExit(main())
