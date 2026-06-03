from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def find_markdownlint(root: Path) -> str | None:
    configured = os.environ.get("RIFTREADER_MARKDOWNLINT")
    if configured:
        return configured

    local = root.parent / "tools" / "markdownlint-cli2" / "markdownlint-cli2.cmd"
    if local.exists():
        return str(local)

    return shutil.which("markdownlint-cli2")


def normalize_markdown_args(args: list[str]) -> list[str]:
    markdown_files = []
    for arg in args:
        path = Path(arg)
        if path.suffix.lower() not in {".md", ".markdown"}:
            continue
        markdown_files.append(":" + path.as_posix())
    return markdown_files


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    markdownlint = find_markdownlint(root)
    if not markdownlint:
        print(
            "markdownlint-cli2 was not found. Install it under "
            r"C:\RIFT MODDING\tools\markdownlint-cli2 or set RIFTREADER_MARKDOWNLINT.",
            file=sys.stderr,
        )
        return 2

    args = normalize_markdown_args(list(argv or sys.argv[1:]))
    if not args:
        args = [
            ":docs/workflow/pre-commit-local-gates.md",
        ]

    cmd = [
        markdownlint,
        "--config",
        ".markdownlint-cli2.yaml",
        "--no-globs",
        *args,
    ]
    return subprocess.run(cmd, cwd=root).returncode


if __name__ == "__main__":
    raise SystemExit(main())
