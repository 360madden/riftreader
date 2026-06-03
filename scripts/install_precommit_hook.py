from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PRE_COMMIT_HOME = r"C:\RIFT MODDING\tools\pre-commit\cache"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def pre_commit_launcher(root: Path) -> Path:
    configured = os.environ.get("RIFTREADER_PRE_COMMIT")
    if configured:
        return Path(configured)
    return root.parent / "tools" / "pre-commit" / "pre-commit.cmd"


def install_hook(root: Path, launcher: Path) -> None:
    if not launcher.exists():
        raise FileNotFoundError(f"pre-commit launcher not found: {launcher}")
    subprocess.run([str(launcher), "install"], cwd=root, check=True)


def patch_hook(root: Path) -> Path:
    hook = root / ".git" / "hooks" / "pre-commit"
    if not hook.exists():
        raise FileNotFoundError(f"pre-commit hook not found after install: {hook}")

    text = hook.read_text(encoding="utf-8")
    export_line = f"export PRE_COMMIT_HOME='{PRE_COMMIT_HOME}'"
    if "PRE_COMMIT_HOME" in text:
        lines = [
            export_line if line.startswith("export PRE_COMMIT_HOME=") else line
            for line in text.splitlines()
        ]
        text = "\n".join(lines) + "\n"
    elif "# end templated" in text:
        text = text.replace("# end templated\n", f"# end templated\n\n{export_line}\n", 1)
    else:
        text = f"{export_line}\n{text}"

    hook.write_text(text, encoding="utf-8")
    return hook


def main() -> int:
    root = repo_root()
    launcher = pre_commit_launcher(root)
    install_hook(root, launcher)
    hook = patch_hook(root)
    print(f"installed hook: {hook}")
    print(f"PRE_COMMIT_HOME={PRE_COMMIT_HOME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
