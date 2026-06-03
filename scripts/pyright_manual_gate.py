from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def find_pyright(root: Path) -> str | None:
    configured = os.environ.get("RIFTREADER_PYRIGHT")
    if configured:
        return configured

    local_tools = root.parent / "tools" / "pyright"
    candidates = [
        local_tools / "pyright.cmd",
        local_tools / "node_modules" / ".bin" / "pyright.cmd",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return shutil.which("pyright")


def main() -> int:
    root = repo_root()
    pyright = find_pyright(root)
    if not pyright:
        print(
            "Pyright was not found. Install it under "
            r"C:\RIFT MODDING\tools\pyright or set RIFTREADER_PYRIGHT.",
            file=sys.stderr,
        )
        return 2

    cmd = [
        pyright,
        "--project",
        str(root / "pyrightconfig.json"),
    ]
    completed = subprocess.run(cmd, cwd=root)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
