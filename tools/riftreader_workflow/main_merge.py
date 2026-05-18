# Version: riftreader-main-merge-v0.1.2
# Total-Character-Count: 21174
# Purpose: Python-owned final inspection, squash merge, main push, and remote-SHA verification for validated RiftReader review branches.

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Sequence

TOOL_VERSION = "riftreader-main-merge-v0.1.2"
DEFAULT_REMOTE = "origin"
DEFAULT_BASE_BRANCH = "main"
DEFAULT_TIMEOUT_SECONDS = 240
DEFAULT_COMMIT_MESSAGE = "Add ChatGPT workflow transport helpers"

ALLOWED_PATHS = frozenset({
    "docs/workflow/chatgpt-development-standards.md",
    "docs/workflow/github-review-publish.md",
    "docs/workflow/local-artifact-bridge.md",
    "docs/workflow/main-merge.md",
    "tools/riftreader_workflow/policy_lint.py",
    "scripts/test_policy_lint.py",
    "scripts/riftreader-policy-lint.cmd",
    "docs/workflow/policy-lint.md",
    ".github/workflows/riftreader-policy.yml",
    "docs/workflow/package-flow.md",
    "docs/workflow/transport-probe.md",
    "handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.json",
    "handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.md",
    "handoffs/current/RIFTREADER_POLICY_LINT_SUMMARY.json",
    "handoffs/current/RIFTREADER_POLICY_LINT_SUMMARY.md",
    "scripts/riftreader-github-review-publish.cmd",
    "scripts/riftreader-local-artifact-bridge.cmd",
    "scripts/riftreader-main-merge.cmd",
    "scripts/riftreader-package-flow.cmd",
    "scripts/riftreader-transport-probe.cmd",
    "scripts/test_github_review_publish.py",
    "scripts/test_local_artifact_bridge.py",
    "scripts/test_main_merge.py",
    "scripts/test_package_flow.py",
    "scripts/test_transport_probe.py",
    "tools/riftreader_workflow/github_review_publish.py",
    "tools/riftreader_workflow/local_artifact_bridge.py",
    "tools/riftreader_workflow/main_merge.py",
    "tools/riftreader_workflow/package_flow.py",
    "tools/riftreader_workflow/transport_probe.py",
})

IGNORED_DIRTY_PREFIXES = (
    ".riftreader-local/",
    "artifacts/",
    "scripts/captures/",
    "scripts/sessions/",
    "Interface/",
    "AddOns/",
)

SAFE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,180}$")


class MainMergeError(RuntimeError):
    """Raised for controlled main-merge failures."""


@dataclass(frozen=True)
class StatusEntry:
    raw: str
    index_status: str
    worktree_status: str
    path: str


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_repo_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MainMergeError("empty repo-relative path")
    raw = value.replace("\\", "/").strip().strip('"')
    if raw.startswith("/") or raw.startswith("//"):
        raise MainMergeError(f"absolute path rejected: {value}")
    if len(raw) >= 2 and raw[1] == ":":
        raise MainMergeError(f"drive-rooted path rejected: {value}")
    parts = [part for part in raw.split("/") if part]
    if any(part in (".", "..") for part in parts):
        raise MainMergeError(f"path traversal rejected: {value}")
    return "/".join(parts)


def validate_ref(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MainMergeError(f"empty {label}")
    ref = value.strip()
    if not SAFE_REF_RE.match(ref) or ".." in ref or ref.endswith("/") or ref.endswith(".lock"):
        raise MainMergeError(f"unsafe {label} rejected: {value}")
    return ref


def repo_join(repo_root: Path, rel: str) -> Path:
    safe = normalize_repo_path(rel)
    current = repo_root
    for part in safe.split("/"):
        current = current / part
    return current


def command_for_platform(command: Sequence[str]) -> List[str]:
    if command and command[0].lower().endswith((".cmd", ".bat")):
        if os.name == "nt":
            return ["cmd", "/d", "/c", *command]
        return ["cmd", "/c", *command]
    return list(command)


def run_command(repo_root: Path, command: Sequence[str], timeout_seconds: int) -> Dict[str, Any]:
    if not command:
        raise MainMergeError("empty command")
    completed = subprocess.run(
        command_for_platform(command),
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        shell=False,
    )
    report = {
        "command": list(command),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "pass": completed.returncode == 0,
    }
    if completed.returncode != 0:
        stdout_tail = completed.stdout[-1600:].replace("\n", "\\n")
        stderr_tail = completed.stderr[-1600:].replace("\n", "\\n")
        raise MainMergeError(
            "command failed rc={0}: {1}; stdout_tail={2!r}; stderr_tail={3!r}".format(
                completed.returncode, " ".join(command), stdout_tail, stderr_tail
            )
        )
    return report


def git(repo_root: Path, args: Sequence[str], timeout_seconds: int) -> Dict[str, Any]:
    return run_command(repo_root, ["git", *args], timeout_seconds)


def repo_root_from(start: Optional[str], timeout_seconds: int) -> Path:
    requested = Path(start).expanduser().resolve() if start else Path.cwd().resolve()
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(requested),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        shell=False,
    )
    if completed.returncode != 0:
        raise MainMergeError(f"not inside a Git repo: {requested}")
    return Path(completed.stdout.strip()).resolve()


def parse_status_porcelain(text: str) -> List[StatusEntry]:
    entries: List[StatusEntry] = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        if len(raw_line) < 4:
            raise MainMergeError(f"unexpected git status line: {raw_line!r}")
        path_text = raw_line[3:]
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        entries.append(StatusEntry(raw_line, raw_line[0], raw_line[1], normalize_repo_path(path_text)))
    return entries


def git_status_entries(repo_root: Path, timeout_seconds: int) -> List[StatusEntry]:
    report = git(repo_root, ["status", "--porcelain=v1"], timeout_seconds)
    return parse_status_porcelain(str(report["stdout"]))


def is_ignored_dirty(path: str) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in IGNORED_DIRTY_PREFIXES)


def unexpected_dirty_paths(repo_root: Path, timeout_seconds: int) -> List[str]:
    entries = git_status_entries(repo_root, timeout_seconds)
    return sorted({entry.path for entry in entries if not is_ignored_dirty(entry.path)})


def assert_no_unexpected_dirty(repo_root: Path, timeout_seconds: int, label: str) -> None:
    unexpected = unexpected_dirty_paths(repo_root, timeout_seconds)
    if unexpected:
        raise MainMergeError(f"unexpected dirty paths during {label}: {unexpected}")


def assert_allowed_paths(paths: Iterable[str], label: str) -> List[str]:
    normalized = sorted({normalize_repo_path(path) for path in paths if str(path).strip()})
    unexpected = [path for path in normalized if path not in ALLOWED_PATHS]
    if unexpected:
        raise MainMergeError(f"unexpected {label} paths: {unexpected}")
    return normalized


def current_branch(repo_root: Path, timeout_seconds: int) -> str:
    return str(git(repo_root, ["branch", "--show-current"], timeout_seconds)["stdout"]).strip()


def current_head(repo_root: Path, timeout_seconds: int) -> str:
    return str(git(repo_root, ["rev-parse", "HEAD"], timeout_seconds)["stdout"]).strip()


def remote_ref_sha(repo_root: Path, remote: str, ref: str, timeout_seconds: int) -> str:
    report = git(repo_root, ["ls-remote", remote, ref], timeout_seconds)
    lines = [line for line in str(report["stdout"]).splitlines() if line.strip()]
    if not lines:
        raise MainMergeError(f"remote ref not found: {remote} {ref}")
    return lines[0].split()[0]


def diff_paths(repo_root: Path, base_ref: str, review_ref: str, timeout_seconds: int) -> List[str]:
    report = git(repo_root, ["diff", "--name-only", f"{base_ref}..{review_ref}"], timeout_seconds)
    return assert_allowed_paths(str(report["stdout"]).splitlines(), "diff")


def diff_check(repo_root: Path, left_ref: str, right_ref: str, timeout_seconds: int) -> Dict[str, Any]:
    return git(repo_root, ["diff", "--check", f"{left_ref}..{right_ref}"], timeout_seconds)


def inspect_review(repo_root: Path, base_ref: str, review_ref: str, expected_review_sha: Optional[str], remote: str, timeout_seconds: int, fetch: bool) -> Dict[str, Any]:
    validate_ref(base_ref, "base ref")
    validate_ref(review_ref, "review ref")
    if fetch:
        git(repo_root, ["fetch", remote], timeout_seconds)
    actual_review_sha = str(git(repo_root, ["rev-parse", review_ref], timeout_seconds)["stdout"]).strip()
    if expected_review_sha and actual_review_sha != expected_review_sha:
        raise MainMergeError(f"review SHA mismatch: actual={actual_review_sha} expected={expected_review_sha}")
    paths = diff_paths(repo_root, base_ref, review_ref, timeout_seconds)
    check_report = diff_check(repo_root, base_ref, review_ref, timeout_seconds)
    return {
        "schemaVersion": 1,
        "tool": TOOL_VERSION,
        "command": "inspect-review",
        "ok": True,
        "baseRef": base_ref,
        "reviewRef": review_ref,
        "reviewSha": actual_review_sha,
        "diffPathCount": len(paths),
        "diffPaths": paths,
        "diffCheck": {"pass": True, "stderr": check_report["stderr"], "stdout": check_report["stdout"]},
        "unexpectedDirtyPaths": unexpected_dirty_paths(repo_root, timeout_seconds),
    }


def squash_review(repo_root: Path, base_branch: str, review_ref: str, expected_review_sha: Optional[str], remote: str, message: str, timeout_seconds: int, fetch: bool, yes_push: bool) -> Dict[str, Any]:
    base_branch = validate_ref(base_branch, "base branch")
    remote = validate_ref(remote, "remote")
    review_ref = validate_ref(review_ref, "review ref")
    base_ref = f"{remote}/{base_branch}"
    inspection = inspect_review(repo_root, base_ref, review_ref, expected_review_sha, remote, timeout_seconds, fetch)
    if not yes_push:
        return {
            "schemaVersion": 1,
            "tool": TOOL_VERSION,
            "command": "squash-review",
            "ok": True,
            "dryRun": True,
            "plan": {
                "baseBranch": base_branch,
                "reviewRef": review_ref,
                "message": message,
                "pathsToMerge": inspection["diffPaths"],
            },
            "inspection": inspection,
            "note": "Pass --yes-push to switch main, squash-merge, commit, push, and verify remote SHA.",
        }
    assert_no_unexpected_dirty(repo_root, timeout_seconds, "pre-squash")
    git(repo_root, ["switch", base_branch], timeout_seconds)
    git(repo_root, ["pull", "--ff-only", remote, base_branch], timeout_seconds)
    assert_no_unexpected_dirty(repo_root, timeout_seconds, "base-before-squash")
    git(repo_root, ["merge", "--squash", review_ref], timeout_seconds)
    staged_report = git(repo_root, ["diff", "--cached", "--name-only"], timeout_seconds)
    staged_paths = assert_allowed_paths(str(staged_report["stdout"]).splitlines(), "staged")
    if set(staged_paths) != set(inspection["diffPaths"]):
        raise MainMergeError(f"staged paths do not match inspected diff paths: staged={staged_paths} diff={inspection['diffPaths']}")
    git(repo_root, ["diff", "--cached", "--check"], timeout_seconds)
    git(repo_root, ["commit", "-m", message], timeout_seconds)
    local_sha = current_head(repo_root, timeout_seconds)
    git(repo_root, ["push", remote, base_branch], timeout_seconds)
    remote_sha = remote_ref_sha(repo_root, remote, f"refs/heads/{base_branch}", timeout_seconds)
    if remote_sha != local_sha:
        raise MainMergeError(f"remote {base_branch} SHA mismatch: local={local_sha} remote={remote_sha}")
    return {
        "schemaVersion": 1,
        "tool": TOOL_VERSION,
        "command": "squash-review",
        "ok": True,
        "dryRun": False,
        "baseBranch": base_branch,
        "reviewRef": review_ref,
        "reviewSha": inspection["reviewSha"],
        "squashCommit": local_sha,
        "remoteSha": remote_sha,
        "stagedPathCount": len(staged_paths),
        "stagedPaths": staged_paths,
    }


def validate_current(repo_root: Path, timeout_seconds: int) -> Dict[str, Any]:
    expected = [
        "tools/riftreader_workflow/main_merge.py",
        "scripts/riftreader-main-merge.cmd",
        "scripts/test_main_merge.py",
        "docs/workflow/main-merge.md",
    ]
    files = []
    for rel in expected:
        path = repo_join(repo_root, rel)
        files.append({"path": rel, "exists": path.is_file()})
        if not path.is_file():
            raise MainMergeError(f"expected file missing: {rel}")
    commands = [
        [sys.executable, "-m", "py_compile", "tools/riftreader_workflow/main_merge.py", "scripts/test_main_merge.py"],
        [sys.executable, "-m", "unittest", "scripts.test_main_merge"],
        [sys.executable, "tools/riftreader_workflow/main_merge.py", "--json", "self-test"],
        ["git", "--no-pager", "diff", "--check"],
    ]
    steps = [{"name": "expected_files", "files": files, "pass": True}]
    for command in commands:
        steps.append({"name": "command", **run_command(repo_root, command, timeout_seconds)})
    return {
        "schemaVersion": 1,
        "tool": TOOL_VERSION,
        "command": "validate-current",
        "ok": True,
        "repoRoot": str(repo_root),
        "steps": steps,
    }


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def init_synthetic_repo(root: Path) -> Dict[str, Path]:
    remote = root / "remote.git"
    work = root / "work"
    run_command(root, ["git", "init", "--bare", str(remote)], 30)
    run_command(root, ["git", "init", "-b", "main", str(work)], 30)
    run_command(work, ["git", "config", "user.email", "riftreader-tests@example.invalid"], 30)
    run_command(work, ["git", "config", "user.name", "RiftReader Tests"], 30)
    run_command(work, ["git", "remote", "add", "origin", str(remote)], 30)
    write_file(work / "README.md", "base\n")
    run_command(work, ["git", "add", "README.md"], 30)
    run_command(work, ["git", "commit", "-m", "base"], 30)
    run_command(work, ["git", "push", "-u", "origin", "main"], 30)
    run_command(work, ["git", "switch", "-c", "chatgpt/review-test"], 30)
    write_file(work / "docs" / "workflow" / "main-merge.md", "# Main Merge\n")
    run_command(work, ["git", "add", "docs/workflow/main-merge.md"], 30)
    run_command(work, ["git", "commit", "-m", "review change"], 30)
    run_command(work, ["git", "push", "-u", "origin", "chatgpt/review-test"], 30)
    run_command(work, ["git", "switch", "main"], 30)
    return {"remote": remote, "work": work}


def command_self_test(_args: argparse.Namespace) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    try:
        normalize_repo_path("../bad")
        checks.append({"name": "traversal_rejected", "pass": False})
    except MainMergeError:
        checks.append({"name": "traversal_rejected", "pass": True})
    try:
        validate_ref("bad..ref", "ref")
        checks.append({"name": "unsafe_ref_rejected", "pass": False})
    except MainMergeError:
        checks.append({"name": "unsafe_ref_rejected", "pass": True})
    with tempfile.TemporaryDirectory(prefix="riftreader-main-merge-selftest-") as temp_name:
        paths = init_synthetic_repo(Path(temp_name))
        work = paths["work"]
        inspect = inspect_review(work, "origin/main", "origin/chatgpt/review-test", None, "origin", 60, True)
        checks.append({"name": "inspect_review", "pass": inspect["ok"] and inspect["diffPaths"] == ["docs/workflow/main-merge.md"]})
        merge = squash_review(work, "main", "origin/chatgpt/review-test", None, "origin", "squash review", 60, False, True)
        checks.append({"name": "squash_review", "pass": merge["ok"] and merge["remoteSha"] == merge["squashCommit"]})
    ok = all(bool(check["pass"]) for check in checks)
    return {
        "schemaVersion": 1,
        "tool": TOOL_VERSION,
        "selfTest": True,
        "ok": ok,
        "checkCount": len(checks),
        "checks": checks,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RiftReader Python-owned review branch inspection and main squash merge helper.")
    parser.add_argument("--json", action="store_true", help="Emit clean JSON only.")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_parser = sub.add_parser("inspect-review", help="Inspect review branch diff against main and enforce allowlisted paths.")
    inspect_parser.add_argument("--repo-root", default=None)
    inspect_parser.add_argument("--base-ref", default="origin/main")
    inspect_parser.add_argument("--review-branch", required=True)
    inspect_parser.add_argument("--expected-review-sha", default=None)
    inspect_parser.add_argument("--remote", default=DEFAULT_REMOTE)
    inspect_parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    inspect_parser.add_argument("--no-fetch", action="store_true")

    squash_parser = sub.add_parser("squash-review", help="Squash-merge a validated review branch into main and verify remote SHA.")
    squash_parser.add_argument("--repo-root", default=None)
    squash_parser.add_argument("--base-branch", default=DEFAULT_BASE_BRANCH)
    squash_parser.add_argument("--review-branch", required=True)
    squash_parser.add_argument("--expected-review-sha", default=None)
    squash_parser.add_argument("--remote", default=DEFAULT_REMOTE)
    squash_parser.add_argument("--message", default=DEFAULT_COMMIT_MESSAGE)
    squash_parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    squash_parser.add_argument("--no-fetch", action="store_true")
    squash_parser.add_argument("--yes-push", action="store_true", help="Actually squash-merge, commit, push main, and verify remote SHA.")

    current_parser = sub.add_parser("validate-current", help="Validate installed main-merge helper files and tests.")
    current_parser.add_argument("--repo-root", default=None)
    current_parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)

    sub.add_parser("self-test", help="Run synthetic local bare-remote inspection and squash merge test.")
    return parser


def print_report(report: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print(f"tool: {report.get('tool', TOOL_VERSION)}")
    print(f"command: {report.get('command', 'self-test')}")
    print(f"ok: {report.get('ok')}")
    if report.get("dryRun"):
        print("dryRun: true")
    if "squashCommit" in report:
        print(f"squashCommit: {report['squashCommit']}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect-review":
            repo_root = repo_root_from(args.repo_root, args.timeout_seconds)
            report = inspect_review(repo_root, args.base_ref, args.review_branch, args.expected_review_sha, args.remote, args.timeout_seconds, not args.no_fetch)
        elif args.command == "squash-review":
            repo_root = repo_root_from(args.repo_root, args.timeout_seconds)
            report = squash_review(repo_root, args.base_branch, args.review_branch, args.expected_review_sha, args.remote, args.message, args.timeout_seconds, not args.no_fetch, bool(args.yes_push))
        elif args.command == "validate-current":
            repo_root = repo_root_from(args.repo_root, args.timeout_seconds)
            report = validate_current(repo_root, args.timeout_seconds)
        elif args.command == "self-test":
            report = command_self_test(args)
            if not report.get("ok"):
                print_report(report, args.json)
                return 1
        else:
            parser.error("unknown command")
            return 2
        print_report(report, args.json)
        return 0
    except (MainMergeError, subprocess.TimeoutExpired, OSError, json.JSONDecodeError) as exc:
        print_report({
            "schemaVersion": 1,
            "tool": TOOL_VERSION,
            "ok": False,
            "errorType": type(exc).__name__,
            "error": str(exc),
        }, args.json)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
