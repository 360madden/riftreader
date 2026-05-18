# Version: riftreader-policy-lint-v0.1.2
# Total-Character-Count: 19527
# Purpose: Python-owned scoped repository policy gate for RiftReader workflow helper quality, safety, and review-readiness.

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Optional, Sequence

TOOL_VERSION = "riftreader-policy-lint-v0.1.2"
SUMMARY_JSON = "handoffs/current/RIFTREADER_POLICY_LINT_SUMMARY.json"
SUMMARY_MD = "handoffs/current/RIFTREADER_POLICY_LINT_SUMMARY.md"
DEFAULT_SCAN_ROOTS = ("tools/riftreader_workflow", "scripts", "docs/workflow", ".github/workflows")
BLOCKED_DIR_PREFIXES = (".git/", ".riftreader-local/", "artifacts/", "scripts/captures/", "scripts/sessions/", "Interface/", "AddOns/")
TEXT_SUFFIXES = {".py", ".cmd", ".ps1", ".bat", ".md", ".json", ".yml", ".yaml", ".txt"}
PY_HELPER_ROOT = "tools/riftreader_workflow/"
SCRIPT_TEST_ROOT = "scripts/"

class PolicyLintError(RuntimeError):
    """Raised for controlled policy-lint failures."""

@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"severity": self.severity, "rule": self.rule, "path": self.path, "message": self.message}

def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def normalize_repo_path(value: str) -> str:
    raw = value.replace("\\", "/").strip().strip('"')
    if not raw:
        raise PolicyLintError("empty path")
    if raw.startswith("/") or (len(raw) >= 2 and raw[1] == ":"):
        raise PolicyLintError(f"absolute path rejected: {value}")
    parts = [part for part in raw.split("/") if part]
    if any(part in (".", "..") for part in parts):
        raise PolicyLintError(f"path traversal rejected: {value}")
    return "/".join(parts)

def repo_join(repo_root: Path, rel: str) -> Path:
    safe = normalize_repo_path(rel)
    cur = repo_root
    for part in safe.split("/"):
        cur = cur / part
    return cur

def is_blocked_path(rel: str) -> bool:
    path = rel.rstrip("/")
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in BLOCKED_DIR_PREFIXES)

def run(repo_root: Path, args: Sequence[str], timeout_seconds: int = 120) -> dict[str, Any]:
    completed = subprocess.run(
        list(args),
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        shell=False,
    )
    return {
        "command": list(args),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "pass": completed.returncode == 0,
    }

def repo_root_from(start: Optional[str]) -> Path:
    start_path = Path(start).expanduser().resolve() if start else Path.cwd().resolve()
    result = run(start_path, ["git", "rev-parse", "--show-toplevel"], 30)
    if result["returncode"] != 0:
        raise PolicyLintError(f"not inside a Git repo: {start_path}")
    return Path(str(result["stdout"]).strip()).resolve()

def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""

def discover_text_files(repo_root: Path, roots: Sequence[str]) -> list[str]:
    found: list[str] = []
    for root in roots:
        root_path = repo_join(repo_root, root)
        if not root_path.exists():
            continue
        candidates = [root_path] if root_path.is_file() else [p for p in root_path.rglob("*") if p.is_file()]
        for candidate in candidates:
            rel = candidate.relative_to(repo_root).as_posix()
            if is_blocked_path(rel):
                continue
            if candidate.suffix.lower() in TEXT_SUFFIXES:
                found.append(rel)
    return sorted(set(found))

def git_changed_files(repo_root: Path) -> list[str]:
    report = run(repo_root, ["git", "status", "--porcelain=v1"], 60)
    if report["returncode"] != 0:
        raise PolicyLintError("git status failed")
    files: list[str] = []
    for line in str(report["stdout"]).splitlines():
        if not line.strip() or len(line) < 4:
            continue
        path_text = line[3:]
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        try:
            rel = normalize_repo_path(path_text)
        except PolicyLintError:
            continue
        if is_blocked_path(rel):
            continue
        path = repo_join(repo_root, rel)
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            files.append(rel)
    return sorted(set(files))

def has_trailing_whitespace(text: str) -> bool:
    return any(line.rstrip("\r\n").endswith((" ", "\t")) for line in text.splitlines(True))

def lint_no_git_add_dot(rel: str, text: str) -> list[Finding]:
    if Path(rel).suffix.lower() not in {".py", ".ps1", ".cmd", ".bat", ".md"}:
        return []
    if re.search(r"(?im)^\s*(?:&\s*)?git\s+add\s+\.(?:\s|$)", text):
        return [Finding("blocker", "no_git_add_dot", rel, "File appears to run or document 'git add .'. Use explicit paths only.")]
    return []

def lint_thin_cmd(rel: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    if not rel.startswith("scripts/") or not rel.endswith(".cmd"):
        return findings
    if not re.search(r"(?i)python\s+\"?tools[\\/]riftreader_workflow[\\/]", text):
        return findings
    banned = re.compile(r"(?im)^\s*(for|powershell|pwsh|git|where|findstr|curl|Invoke-|ConvertFrom-Json|ConvertTo-Json)\b")
    for match in banned.finditer(text):
        findings.append(Finding("blocker", "thin_cmd_wrapper", rel, f"CMD wrapper contains orchestration token: {match.group(1)}"))
    return findings

def is_cli_like_python_helper(rel: str, text: str, repo_root: Path) -> bool:
    if "argparse" in text or "ArgumentParser" in text:
        return True
    if "def main(" in text or "if __name__" in text:
        return True
    if "TOOL_VERSION" in text and ("--json" in text or "subprocess.run" in text):
        return True
    wrapper = repo_root / "scripts" / f"riftreader-{Path(rel).stem.replace('_', '-')}.cmd"
    return wrapper.is_file()

def lint_python_helper(rel: str, text: str, repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    if not (rel.startswith(PY_HELPER_ROOT) and rel.endswith(".py")):
        return findings
    char_count = len(text)
    stem = Path(rel).stem
    cli_like = is_cli_like_python_helper(rel, text, repo_root)
    if char_count > 1000:
        if cli_like:
            if "def main(" not in text:
                findings.append(Finding("blocker", "python_main_entrypoint", rel, "Python CLI helper over 1000 chars must define main()."))
            if "argparse" not in text and "ArgumentParser" not in text:
                findings.append(Finding("blocker", "python_argparse_cli", rel, "Python CLI helper over 1000 chars should use argparse."))
            if "except" not in text:
                findings.append(Finding("blocker", "python_error_handling", rel, "Python CLI helper over 1000 chars must include controlled error handling."))
            if "--json" not in text and "json.dumps" not in text:
                findings.append(Finding("warning", "python_json_output", rel, "Python CLI helper should support --json or emit structured JSON."))
        else:
            if "except" not in text and "raise " not in text:
                findings.append(Finding("warning", "python_library_errors", rel, "Large Python library module should expose clear errors or raise controlled exceptions."))
    if char_count > 3000:
        expected_test = repo_root / SCRIPT_TEST_ROOT / f"test_{stem}.py"
        if cli_like and not expected_test.is_file():
            findings.append(Finding("blocker", "python_large_helper_tests", rel, f"Python CLI helper over 3000 chars needs scripts/test_{stem}.py."))
        elif not cli_like and not expected_test.is_file():
            findings.append(Finding("warning", "python_large_library_tests", rel, f"Large Python library module should have tests when practical: scripts/test_{stem}.py."))
        if cli_like and "self-test" not in text and "self_test" not in text:
            findings.append(Finding("warning", "python_large_helper_self_test", rel, "Large workflow helper should expose self-test or equivalent."))
    if "subprocess.run" in text:
        if "timeout=" not in text:
            findings.append(Finding("warning", "subprocess_timeout", rel, "subprocess.run usage should include finite timeout."))
        if not any(token in text for token in ("capture_output=True", "stdout=subprocess.PIPE", "stderr=subprocess.PIPE")):
            findings.append(Finding("warning", "subprocess_capture", rel, "subprocess.run usage should capture stdout/stderr for diagnostics."))
        if re.search(r"subprocess\.run\([^)]*shell\s*=\s*True", text, re.S):
            findings.append(Finding("blocker", "subprocess_shell_true", rel, "Workflow helpers must not use shell=True for subprocess control."))
    return findings

def lint_file(repo_root: Path, rel: str) -> list[Finding]:
    path = repo_join(repo_root, rel)
    text = read_text(path)
    findings: list[Finding] = []
    if has_trailing_whitespace(text):
        findings.append(Finding("blocker", "trailing_whitespace", rel, "File contains trailing spaces or tabs."))
    if is_blocked_path(rel):
        findings.append(Finding("blocker", "forbidden_path", rel, "Policy lint was asked to scan a forbidden generated/local path."))
    findings.extend(lint_no_git_add_dot(rel, text))
    findings.extend(lint_thin_cmd(rel, text))
    findings.extend(lint_python_helper(rel, text, repo_root))
    return findings

def build_summary(repo_root: Path, command: str, files: list[str], findings: list[Finding], write_summary: bool, scope: str) -> dict[str, Any]:
    blockers = [f.as_dict() for f in findings if f.severity == "blocker"]
    warnings = [f.as_dict() for f in findings if f.severity == "warning"]
    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "tool": TOOL_VERSION,
        "command": command,
        "scope": scope,
        "status": "failed" if blockers else "passed",
        "ok": not blockers,
        "createdUtc": utc_iso(),
        "checkedFiles": len(files),
        "blockerCount": len(blockers),
        "warningCount": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "rules": {
            "noGitAddDot": "enforced",
            "thinCmdWrappers": "enforced",
            "pythonHelperEntrypoint": "enforced-for-cli-helpers",
            "pythonHelperErrorHandling": "enforced-for-cli-helpers",
            "largeHelperTests": "enforced-for-cli-helpers",
            "trailingWhitespace": "enforced",
            "forbiddenPaths": "enforced",
        },
        "artifacts": {},
    }
    if write_summary:
        json_path = repo_join(repo_root, SUMMARY_JSON)
        md_path = repo_join(repo_root, SUMMARY_MD)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        lines = [
            "# RiftReader Policy Lint Summary",
            "",
            f"Created UTC: {summary['createdUtc']}",
            f"Status: {summary['status']}",
            f"Scope: {scope}",
            f"Checked files: {summary['checkedFiles']}",
            f"Blockers: {summary['blockerCount']}",
            f"Warnings: {summary['warningCount']}",
            "",
            "## Blockers",
        ]
        if blockers:
            for item in blockers:
                lines.append(f"- `{item['path']}` [{item['rule']}]: {item['message']}")
        else:
            lines.append("None.")
        lines.append("")
        lines.append("## Warnings")
        if warnings:
            for item in warnings:
                lines.append(f"- `{item['path']}` [{item['rule']}]: {item['message']}")
        else:
            lines.append("None.")
        lines.append("")
        lines.append("# END_OF_POLICY_LINT_SUMMARY")
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        summary["artifacts"] = {"summaryJson": SUMMARY_JSON, "summaryMarkdown": SUMMARY_MD}
    return summary

def select_files(repo_root: Path, scope: str, roots: Sequence[str], paths: Optional[Sequence[str]] = None) -> list[str]:
    if scope == "changed":
        return git_changed_files(repo_root)
    if scope == "all":
        return discover_text_files(repo_root, roots)
    if scope == "paths":
        if not paths:
            raise PolicyLintError("--scope paths requires --paths")
        return sorted(set(normalize_repo_path(path) for path in paths))
    raise PolicyLintError(f"unsupported scope: {scope}")

def run_lint(repo_root: Path, command: str, scope: str, roots: Sequence[str], write_summary: bool, paths: Optional[Sequence[str]] = None) -> dict[str, Any]:
    files = select_files(repo_root, scope, roots, paths)
    findings: list[Finding] = []
    for rel in files:
        path = repo_join(repo_root, rel)
        if not path.is_file():
            findings.append(Finding("blocker", "missing_file", rel, "Requested policy-lint path does not exist."))
            continue
        findings.extend(lint_file(repo_root, rel))
    return build_summary(repo_root, command, files, findings, write_summary, scope)

def command_validate_repo(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = repo_root_from(args.repo_root)
    return run_lint(repo_root, "validate-repo", args.scope, args.roots, not args.no_write_summary)

def command_validate_paths(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = repo_root_from(args.repo_root)
    return run_lint(repo_root, "validate-paths", "paths", args.roots, not args.no_write_summary, args.paths)

def command_self_test(_args: argparse.Namespace) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="riftreader-policy-lint-selftest-") as temp_name:
        root = Path(temp_name)
        subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        (root / "tools/riftreader_workflow").mkdir(parents=True)
        (root / "scripts").mkdir()
        bad = root / "tools/riftreader_workflow/bad.py"
        bad.write_text("TOOL_VERSION = 'x'\n# --json\nprint('x')\n" + ("# filler\n" * 180), encoding="utf-8")
        good = root / "tools/riftreader_workflow/good_cli.py"
        good.write_text(
            "import argparse, json\nclass GoodError(RuntimeError): pass\n"
            "def main(argv=None):\n    try:\n        argparse.ArgumentParser().parse_args(argv)\n        print(json.dumps({'ok': True}))\n        return 0\n    except GoodError:\n        return 1\n"
            "if __name__ == '__main__': raise SystemExit(main())\n"
            "# END_OF_SCRIPT_MARKER\n",
            encoding="utf-8",
        )
        bad_git = root / "scripts/bad.ps1"
        bad_git.write_text("git add .\n", encoding="utf-8")
        trailing = root / "docs_trailing.md"
        trailing.write_text("x  \n", encoding="utf-8")
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Tests"], cwd=root, check=True)
        subprocess.run(["git", "add", "tools/riftreader_workflow/good_cli.py"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        bad_findings = lint_file(root, "tools/riftreader_workflow/bad.py")
        checks.append({"name": "detects_large_bad_python", "pass": any(f.rule == "python_main_entrypoint" for f in bad_findings)})
        checks.append({"name": "detects_git_add_dot", "pass": bool(lint_file(root, "scripts/bad.ps1"))})
        checks.append({"name": "detects_trailing_whitespace", "pass": bool(lint_file(root, "docs_trailing.md"))})
        checks.append({"name": "normalizes_paths", "pass": normalize_repo_path("a\\b") == "a/b"})
        changed = run_lint(root, "validate-repo", "changed", DEFAULT_SCAN_ROOTS, False)
        checks.append({"name": "changed_scope_runs", "pass": changed["checkedFiles"] >= 2 and not changed["ok"]})
        paths = run_lint(root, "validate-paths", "paths", DEFAULT_SCAN_ROOTS, False, ["tools/riftreader_workflow/good_cli.py"])
        checks.append({"name": "good_cli_passes", "pass": paths["ok"]})
    ok = all(check["pass"] for check in checks)
    return {"schemaVersion": 1, "tool": TOOL_VERSION, "selfTest": True, "ok": ok, "checkCount": len(checks), "checks": checks}

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RiftReader Python-owned policy lint gate.")
    parser.add_argument("--json", action="store_true", help="Emit clean JSON only.")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-repo", help="Validate repo policy. Default scope is changed files to avoid legacy debt blocking new work.")
    validate.add_argument("--repo-root", default=None)
    validate.add_argument("--scope", choices=("changed", "all"), default="changed")
    validate.add_argument("--roots", nargs="*", default=list(DEFAULT_SCAN_ROOTS))
    validate.add_argument("--no-write-summary", action="store_true")

    paths = sub.add_parser("validate-paths", help="Validate explicit repo-relative paths.")
    paths.add_argument("--repo-root", default=None)
    paths.add_argument("--paths", nargs="+", required=True)
    paths.add_argument("--roots", nargs="*", default=list(DEFAULT_SCAN_ROOTS))
    paths.add_argument("--no-write-summary", action="store_true")

    sub.add_parser("self-test", help="Run internal synthetic checks.")
    return parser

def print_report(report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print(f"tool: {report.get('tool', TOOL_VERSION)}")
    print(f"command: {report.get('command', 'self-test')}")
    print(f"ok: {report.get('ok')}")
    print(f"status: {report.get('status', 'n/a')}")
    print(f"blockers: {report.get('blockerCount', 0)}")
    print(f"warnings: {report.get('warningCount', 0)}")

def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-repo":
            report = command_validate_repo(args)
        elif args.command == "validate-paths":
            report = command_validate_paths(args)
        elif args.command == "self-test":
            report = command_self_test(args)
        else:
            parser.error("unknown command")
            return 2
        print_report(report, args.json)
        return 0 if report.get("ok") else 1
    except (PolicyLintError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        report = {"schemaVersion": 1, "tool": TOOL_VERSION, "ok": False, "status": "failed", "errorType": type(exc).__name__, "error": str(exc)}
        print_report(report, getattr(args, "json", False))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
