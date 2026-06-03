from __future__ import annotations

import configparser
import sys
from pathlib import Path


REQUIRED_ROOT_KEYS = {
    "root": "true",
}

REQUIRED_STAR_KEYS = {
    "charset": "utf-8",
    "insert_final_newline": "true",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    path = repo_root() / ".editorconfig"
    if not path.exists():
        print(".editorconfig is missing", file=sys.stderr)
        return 1

    parser = configparser.ConfigParser()
    content = path.read_text(encoding="utf-8")
    parser.read_string("[__root__]\n" + content)

    root_section = parser["__root__"]
    for key, expected in REQUIRED_ROOT_KEYS.items():
        actual = root_section.get(key)
        if actual != expected:
            print(f".editorconfig {key} must be {expected!r}, got {actual!r}", file=sys.stderr)
            return 1

    if "*" not in parser:
        print(".editorconfig is missing [*] section", file=sys.stderr)
        return 1

    star_section = parser["*"]
    for key, expected in REQUIRED_STAR_KEYS.items():
        actual = star_section.get(key)
        if actual != expected:
            print(f".editorconfig [*] {key} must be {expected!r}, got {actual!r}", file=sys.stderr)
            return 1

    print(".editorconfig verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
