from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
KIND = "riftreader-sensitive-artifact-scan"
DEFAULT_OUTPUT_ROOT = Path(".riftreader-local") / "sensitive-artifact-scan"


PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai-api-key", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9_-]{20,})\b")),
    ("authapi-arg", re.compile(r"--authapi=(?!<redacted>|\$|%)[^\s`\"']+", re.IGNORECASE)),
    (
        "long-sensitive-option",
        re.compile(
            r"(?:--token|--auth-token|--session|--session-id|--ticket|--password)(?:=|\s+)"
            r"(?!<redacted>|\$|%)[^\s`\"']{8,}",
            re.IGNORECASE,
        ),
    ),
    ("short-sensitive-flag", re.compile(r"(?<![A-Za-z0-9])-(?:k|s|p)\s+(?!<redacted>|\$|%)[^\s`\"']{8,}", re.IGNORECASE)),
)


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def repo_relative_or_absolute(repo_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("/", "\\")
    except ValueError:
        return str(path)


def command_output(args: list[str], cwd: Path) -> tuple[int, str, str]:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        timeout=30,
    )
    return completed.returncode, completed.stdout, completed.stderr


def staged_paths(repo_root: Path) -> list[str]:
    code, stdout, stderr = command_output(["git", "--no-pager", "diff", "--cached", "--name-only"], repo_root)
    if code != 0:
        raise RuntimeError(f"git diff --cached --name-only failed: {stderr.strip()}")
    return [line.strip() for line in stdout.splitlines() if line.strip()]


def working_paths(repo_root: Path) -> list[str]:
    code, stdout, stderr = command_output(["git", "--no-pager", "diff", "--name-only"], repo_root)
    if code != 0:
        raise RuntimeError(f"git diff --name-only failed: {stderr.strip()}")
    code_untracked, stdout_untracked, stderr_untracked = command_output(
        ["git", "ls-files", "--others", "--exclude-standard"],
        repo_root,
    )
    if code_untracked != 0:
        raise RuntimeError(f"git ls-files --others failed: {stderr_untracked.strip()}")
    return list(dict.fromkeys([line.strip() for line in (stdout + "\n" + stdout_untracked).splitlines() if line.strip()]))


def staged_text(repo_root: Path, rel_path: str) -> str | None:
    completed = subprocess.run(
        ["git", "show", f":{rel_path}"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        timeout=30,
        errors="replace",
    )
    if completed.returncode != 0:
        return None
    return completed.stdout


def working_text(repo_root: Path, rel_path: str) -> str | None:
    path = repo_root / rel_path
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def should_scan_path(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/")
    if normalized.startswith(".riftreader-local/") or normalized.startswith("artifacts/"):
        return False
    blocked_parts = {".git", "__pycache__", "bin", "obj", ".vs", ".pytest_cache"}
    parts = set(normalized.split("/"))
    return not bool(parts & blocked_parts)


def scan_text(rel_path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if "re.compile(" in line:
            continue
        for name, pattern in PATTERNS:
            if pattern.search(line):
                findings.append(
                    {
                        "path": rel_path,
                        "line": line_number,
                        "pattern": name,
                        "linePreviewStored": False,
                        "message": "Potential sensitive value matched; line content intentionally omitted.",
                    }
                )
    return findings


def collect_paths(repo_root: Path, args: argparse.Namespace) -> tuple[str, list[str]]:
    if args.path:
        return "explicit-paths", list(dict.fromkeys(str(item).replace("\\", "/") for item in args.path))
    if args.staged:
        return "staged", staged_paths(repo_root)
    return "working", working_paths(repo_root)


def build_scan_summary(repo_root: Path, args: argparse.Namespace, *, output_root: Path | None = None) -> dict[str, Any]:
    mode, raw_paths = collect_paths(repo_root, args)
    paths = [path for path in raw_paths if should_scan_path(path)]
    findings: list[dict[str, Any]] = []
    unreadable: list[str] = []
    for rel_path in paths:
        text = staged_text(repo_root, rel_path) if mode == "staged" else working_text(repo_root, rel_path)
        if text is None:
            unreadable.append(rel_path)
            continue
        findings.extend(scan_text(rel_path, text))

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "generatedAtUtc": utc_iso(),
        "status": "failed" if findings else "passed",
        "repoRoot": str(repo_root),
        "mode": mode,
        "pathsRequested": len(raw_paths),
        "filesScanned": len(paths) - len(unreadable),
        "pathsSkippedByPolicy": len(raw_paths) - len(paths),
        "unreadablePaths": unreadable,
        "findingCount": len(findings),
        "containsSensitiveData": bool(findings),
        "findings": findings,
        "patterns": [name for name, _pattern in PATTERNS],
        "safety": {
            "linePreviewStored": False,
            "movementSent": False,
            "inputSent": False,
            "launcherButtonPressed": False,
            "launchAttempted": False,
            "providerWrites": False,
            "gitMutation": False,
        },
        "artifacts": {},
    }
    if args.write:
        base = output_root or repo_root / DEFAULT_OUTPUT_ROOT
        if not base.is_absolute():
            base = repo_root / base
        output_dir = base / f"run-{utc_stamp()}"
        output_dir.mkdir(parents=True, exist_ok=False)
        summary_json = output_dir / "sensitive-artifact-scan-summary.json"
        latest = base / "latest-run.txt"
        summary["artifacts"] = {
            "outputDir": repo_relative_or_absolute(repo_root, output_dir),
            "summaryJson": repo_relative_or_absolute(repo_root, summary_json),
            "latestRun": repo_relative_or_absolute(repo_root, latest),
        }
        write_json(summary_json, summary)
        write_text_atomic(latest, str(output_dir.resolve()) + "\n")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan staged or working RiftReader artifacts for sensitive values.")
    parser.add_argument("--repo-root", default=None, help="RiftReader repo root. Defaults to this checkout.")
    parser.add_argument("--staged", action="store_true", help="Scan staged Git contents.")
    parser.add_argument("--working", action="store_true", help="Scan modified/untracked working-tree files. Default.")
    parser.add_argument("--path", action="append", help="Scan an explicit repo-relative path. Can be supplied more than once.")
    parser.add_argument("--write", action="store_true", help="Write ignored JSON output under .riftreader-local.")
    parser.add_argument("--output-dir", default=None, help="Override output root for --write.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_from_module()
    output_root = Path(args.output_dir) if args.output_dir else None
    summary = build_scan_summary(repo_root, args, output_root=output_root)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"{summary['status']}: scanned {summary['filesScanned']} file(s), findings {summary['findingCount']}")
    return 1 if summary.get("containsSensitiveData") else 0


if __name__ == "__main__":
    raise SystemExit(main())
