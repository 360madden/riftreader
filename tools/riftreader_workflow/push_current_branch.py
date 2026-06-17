#!/usr/bin/env python3
"""Read-only preflight for a future MCP ``push_current_branch`` helper.

Stage 29 intentionally performs no Git remote mutation. It verifies that the
current branch can later be pushed by an approval-gated Stage 30 helper without
force, rewrite, reset, clean, stash, or arbitrary refspecs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, run_command_envelope, safety_flags, utc_iso
except ImportError:  # pragma: no cover - direct script execution fallback.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, run_command_envelope, safety_flags, utc_iso


SCHEMA_VERSION = 1
TOOL_VERSION = "riftreader-push-current-branch-v0.1.0"
KIND = "riftreader-push-current-branch-preflight"
PROTECTED_BRANCHES = {"main", "master"}
SAFE_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


class PushPreflightError(RuntimeError):
    """Internal structured failure for preflight setup failures."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _run_git(repo_root: Path, args: list[str], *, timeout_seconds: float = 30.0) -> subprocess.CompletedProcess[bytes]:
    if not args:
        raise PushPreflightError("PUSH_GIT_ARGS_INVALID")
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repo_root,
            shell=False,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise PushPreflightError("PUSH_GIT_NOT_FOUND", "git executable was not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise PushPreflightError("PUSH_GIT_TIMEOUT", f"git command timed out after {timeout_seconds}s") from exc


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _git_text(repo_root: Path, args: list[str], *, timeout_seconds: float = 30.0) -> str:
    proc = _run_git(repo_root, args, timeout_seconds=timeout_seconds)
    if proc.returncode != 0:
        raise PushPreflightError("PUSH_GIT_COMMAND_FAILED", _decode(proc.stderr).strip())
    return _decode(proc.stdout).strip()


def current_head(repo_root: Path, *, timeout_seconds: float = 30.0) -> str:
    try:
        return _git_text(repo_root, ["rev-parse", "HEAD"], timeout_seconds=timeout_seconds).splitlines()[0].strip()
    except IndexError as exc:
        raise PushPreflightError("PUSH_HEAD_UNAVAILABLE") from exc


def current_branch(repo_root: Path, *, timeout_seconds: float = 30.0) -> str | None:
    text = _git_text(repo_root, ["branch", "--show-current"], timeout_seconds=timeout_seconds)
    return text.splitlines()[0].strip() if text.strip() else None


def current_upstream(repo_root: Path, *, timeout_seconds: float = 30.0) -> str | None:
    proc = _run_git(
        repo_root,
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        timeout_seconds=timeout_seconds,
    )
    if proc.returncode != 0:
        return None
    text = _decode(proc.stdout).strip()
    return text.splitlines()[0].strip() if text else None


def remote_url(repo_root: Path, remote_name: str = "origin", *, timeout_seconds: float = 30.0) -> str | None:
    proc = _run_git(repo_root, ["remote", "get-url", "--push", remote_name], timeout_seconds=timeout_seconds)
    if proc.returncode != 0:
        return None
    text = _decode(proc.stdout).strip()
    return text.splitlines()[0].strip() if text else None


def branch_name_is_safe(branch: str | None) -> bool:
    if not branch or not SAFE_BRANCH_RE.match(branch):
        return False
    forbidden_fragments = ("..", "@{", "\\", "//")
    if any(fragment in branch for fragment in forbidden_fragments):
        return False
    if branch.startswith(("-", "/", ".")) or branch.endswith(("/", ".", ".lock")):
        return False
    return True


def parse_ahead_behind(text: str) -> tuple[int | None, int | None]:
    parts = text.strip().split()
    if len(parts) < 2:
        return None, None
    try:
        behind = int(parts[0])
        ahead = int(parts[1])
    except ValueError:
        return None, None
    return ahead, behind


def ahead_behind(repo_root: Path, *, timeout_seconds: float = 30.0) -> tuple[int | None, int | None]:
    proc = _run_git(repo_root, ["rev-list", "--left-right", "--count", "@{u}...HEAD"], timeout_seconds=timeout_seconds)
    if proc.returncode != 0:
        return None, None
    return parse_ahead_behind(_decode(proc.stdout))


def parse_porcelain_z(raw: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    parts = raw.split(b"\x00")
    index = 0
    while index < len(parts):
        item = parts[index]
        index += 1
        if not item:
            continue
        text = _decode(item)
        status = text[:2] if len(text) >= 2 else text.strip()
        path = text[3:] if len(text) >= 4 else text.strip()
        old_path = None
        if ("R" in status or "C" in status) and index < len(parts) and parts[index]:
            old_path = _decode(parts[index])
            index += 1
        record: dict[str, Any] = {
            "status": status,
            "path": path.replace("\\", "/"),
            "tracked": status != "??",
            "untracked": status == "??",
        }
        if old_path:
            record["oldPath"] = old_path.replace("\\", "/")
        rows.append(record)
    return rows


def git_dirty_state(repo_root: Path, *, timeout_seconds: float = 30.0) -> dict[str, Any]:
    proc = _run_git(
        repo_root,
        ["--no-pager", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        timeout_seconds=timeout_seconds,
    )
    if proc.returncode != 0:
        raise PushPreflightError("PUSH_STATUS_READ_FAILED", _decode(proc.stderr).strip())
    entries = parse_porcelain_z(proc.stdout)
    return {
        "status": "dirty" if entries else "clean",
        "dirty": bool(entries),
        "dirtyCount": len(entries),
        "entries": entries,
        "dirtyPaths": [str(entry["path"]) for entry in entries if entry.get("path")],
    }


def approval_token_for_facts(approval_facts: dict[str, Any]) -> str:
    payload = {
        "expectedHead": approval_facts.get("expectedHead"),
        "branch": approval_facts.get("branch"),
        "upstream": approval_facts.get("upstream"),
        "ahead": approval_facts.get("ahead"),
        "behind": approval_facts.get("behind"),
        "remoteName": approval_facts.get("remoteName"),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"PUSH-{digest[:16]}"


def preflight_safety(*, read_only: bool = True) -> dict[str, Any]:
    return {
        **safety_flags(),
        "readOnlyPreflight": read_only,
        "gitMutation": False,
        "remoteMutation": False,
        "localCommitOnly": False,
        "forcePush": False,
        "branchRewrite": False,
        "destructiveCleanup": False,
        "resetOrClean": False,
        "stashMutation": False,
        "arbitraryRefspec": False,
        "pushed": False,
        "providerWrites": False,
        "inputSent": False,
        "movementSent": False,
        "x64dbgAttach": False,
        "noCheatEngine": True,
        "applyFlagSent": False,
    }


def push_preflight(
    repo_root: Path,
    *,
    expected_head: str | None = None,
    branch: str | None = None,
    upstream: str | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    head: str | None = None
    current_branch_name: str | None = None
    upstream_ref: str | None = None
    remote_name = "origin"
    push_url: str | None = None
    ahead: int | None = None
    behind: int | None = None
    dirty_state: dict[str, Any] = {
        "status": "unknown",
        "dirty": None,
        "dirtyCount": None,
        "entries": [],
        "dirtyPaths": [],
    }

    try:
        head = current_head(repo_root, timeout_seconds=timeout_seconds)
    except PushPreflightError as exc:
        blockers.append(exc.code)
        if str(exc) != exc.code:
            warnings.append(str(exc))

    try:
        current_branch_name = current_branch(repo_root, timeout_seconds=timeout_seconds)
    except PushPreflightError as exc:
        blockers.append(exc.code)
        if str(exc) != exc.code:
            warnings.append(str(exc))
    if not current_branch_name:
        blockers.append("PUSH_BRANCH_UNNAMED")
    elif not branch_name_is_safe(current_branch_name):
        blockers.append("PUSH_BRANCH_UNSAFE")

    upstream_ref = current_upstream(repo_root, timeout_seconds=timeout_seconds)
    if not upstream_ref:
        blockers.append("PUSH_UPSTREAM_MISSING")
    elif current_branch_name and upstream_ref != f"{remote_name}/{current_branch_name}":
        blockers.append("PUSH_UPSTREAM_AMBIGUOUS")

    push_url = remote_url(repo_root, remote_name, timeout_seconds=timeout_seconds)
    if not push_url:
        blockers.append("PUSH_REMOTE_UNEXPECTED")
    elif any(char in push_url for char in "\r\n\x00"):
        blockers.append("PUSH_REMOTE_UNEXPECTED")

    if upstream_ref:
        ahead, behind = ahead_behind(repo_root, timeout_seconds=timeout_seconds)
        if ahead is None or behind is None:
            blockers.append("PUSH_AHEAD_BEHIND_UNAVAILABLE")
        else:
            if ahead <= 0:
                blockers.append("PUSH_NOTHING_TO_PUSH")
            if behind > 0:
                blockers.append("PUSH_BRANCH_BEHIND")
            if ahead > 0 and behind > 0:
                blockers.append("PUSH_DIVERGED")

    try:
        dirty_state = git_dirty_state(repo_root, timeout_seconds=timeout_seconds)
    except PushPreflightError as exc:
        blockers.append(exc.code)
        if str(exc) != exc.code:
            warnings.append(str(exc))
    if dirty_state.get("dirty"):
        blockers.append("PUSH_WORKTREE_DIRTY")

    if expected_head is not None and head is not None and expected_head != head:
        blockers.append("PUSH_HEAD_MISMATCH")
    if branch is not None and current_branch_name is not None and branch != current_branch_name:
        blockers.append("PUSH_BRANCH_MISMATCH")
    if upstream is not None and upstream_ref is not None and upstream != upstream_ref:
        blockers.append("PUSH_UPSTREAM_MISMATCH")

    approval_facts = {
        "expectedHead": head,
        "branch": current_branch_name,
        "upstream": upstream_ref,
        "ahead": ahead,
        "behind": behind,
        "remoteName": remote_name,
        "remoteUrl": push_url,
        "worktreeClean": dirty_state.get("dirty") is False,
        "protectedBranch": current_branch_name in PROTECTED_BRANCHES if current_branch_name else False,
    }
    status = "ready" if not blockers else "blocked"
    expected_token = approval_token_for_facts(approval_facts) if status == "ready" else None
    ref = f"refs/heads/{current_branch_name}" if current_branch_name else None
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "ready",
        "pushed": False,
        "currentHead": head,
        "branch": current_branch_name,
        "upstream": upstream_ref,
        "ahead": ahead,
        "behind": behind,
        "remoteName": remote_name,
        "remotePushUrl": push_url,
        "protectedBranch": current_branch_name in PROTECTED_BRANCHES if current_branch_name else False,
        "dirtyState": dirty_state,
        "approvalFacts": approval_facts,
        "expectedApprovalToken": expected_token,
        "futureCommands": {
            "gitPush": ["git", "push", remote_name, f"HEAD:{current_branch_name or '<branch>'}"],
            "verifyRemoteHead": ["git", "ls-remote", remote_name, ref or "refs/heads/<branch>"],
            "ciStatus": ["python", "tools\\riftreader_workflow\\mcp_ci_status.py", "--status", "--json"],
        },
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "safety": preflight_safety(read_only=True),
        "next": [
            "If ready, review approvalFacts and expectedApprovalToken before any future Stage 30 push execution helper.",
            "Stage 29 never runs git push, reset, clean, stash, branch rewrite, provider writes, live input, CE, or x64dbg.",
            "After any future approved push, verify current-head CI separately; push success is not CI success.",
        ],
    }


def parse_ls_remote_head(stdout: str, expected_ref: str) -> str | None:
    for line in stdout.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == expected_ref:
            return parts[0]
    return None


def push_execution_safety(*, mutation_attempted: bool, pushed: bool) -> dict[str, Any]:
    return {
        **safety_flags(),
        "readOnlyPreflight": False,
        "gitMutation": mutation_attempted,
        "remoteMutation": mutation_attempted,
        "localCommitOnly": False,
        "forcePush": False,
        "branchRewrite": False,
        "destructiveCleanup": False,
        "resetOrClean": False,
        "stashMutation": False,
        "arbitraryRefspec": False,
        "pushed": pushed,
        "providerWrites": False,
        "inputSent": False,
        "movementSent": False,
        "x64dbgAttach": False,
        "noCheatEngine": True,
        "applyFlagSent": False,
    }


def push_current_branch_apply(
    repo_root: Path,
    *,
    expected_head: str | None,
    branch: str | None,
    upstream: str | None,
    approval_token: str | None,
    timeout_seconds: float = 120.0,
) -> dict[str, Any]:
    """Perform one normal non-force push after re-running read-only preflight."""

    preflight = push_preflight(
        repo_root,
        expected_head=expected_head,
        branch=branch,
        upstream=upstream,
        timeout_seconds=min(timeout_seconds, 30.0),
    )
    blockers: list[str] = []
    warnings: list[str] = [str(item) for item in preflight.get("warnings") or []]
    commands: list[dict[str, Any]] = []
    mutation_attempted = False
    pushed = False
    remote_head: str | None = None
    local_head = preflight.get("currentHead")
    branch_name = preflight.get("branch")
    remote_name = preflight.get("remoteName") or "origin"

    if not preflight.get("ok"):
        blockers.extend(str(item) for item in preflight.get("blockers") or [])
    expected_token = preflight.get("expectedApprovalToken")
    if preflight.get("ok"):
        if not isinstance(approval_token, str) or not approval_token.strip():
            blockers.append("PUSH_APPROVAL_MISSING")
        elif approval_token.strip() != expected_token:
            blockers.append("PUSH_APPROVAL_TOKEN_MISMATCH")
    if not branch_name_is_safe(str(branch_name) if branch_name is not None else None):
        blockers.append("PUSH_BRANCH_UNSAFE")

    if blockers:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-push-current-branch-apply",
            "toolVersion": TOOL_VERSION,
            "generatedAtUtc": utc_iso(),
            "status": "blocked",
            "ok": False,
            "pushed": False,
            "currentHead": local_head,
            "branch": branch_name,
            "upstream": preflight.get("upstream"),
            "remoteHead": None,
            "preflight": preflight,
            "commands": commands,
            "blockers": sorted(set(blockers)),
            "warnings": sorted(set(warnings)),
            "safety": push_execution_safety(mutation_attempted=False, pushed=False),
            "next": [
                "Resolve blockers and rerun --preflight before attempting push execution again.",
                "No Git remote mutation was attempted for this blocked request.",
            ],
        }

    assert isinstance(branch_name, str)
    expected_ref = f"refs/heads/{branch_name}"
    push_args = ["git", "push", str(remote_name), f"HEAD:{branch_name}"]
    mutation_attempted = True
    push_result = run_command_envelope(
        "git-push-current-branch",
        push_args,
        repo_root,
        timeout_seconds=timeout_seconds,
    )
    commands.append(push_result)
    if not push_result.get("ok"):
        blockers.append("PUSH_GIT_COMMAND_FAILED")
    else:
        verify_args = ["git", "ls-remote", str(remote_name), expected_ref]
        verify_result = run_command_envelope(
            "git-ls-remote-verify-head",
            verify_args,
            repo_root,
            timeout_seconds=min(timeout_seconds, 30.0),
            capture_full_output=True,
        )
        commands.append({key: value for key, value in verify_result.items() if key not in {"stdout", "stderr"}})
        if not verify_result.get("ok"):
            blockers.append("PUSH_REMOTE_HEAD_VERIFY_FAILED")
        else:
            remote_head = parse_ls_remote_head(str(verify_result.get("stdout") or ""), expected_ref)
            if remote_head != local_head:
                blockers.append("PUSH_REMOTE_HEAD_VERIFY_FAILED")
            else:
                pushed = True

    status = "passed" if pushed and not blockers else "failed"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-push-current-branch-apply",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "passed",
        "pushed": pushed,
        "currentHead": local_head,
        "branch": branch_name,
        "upstream": preflight.get("upstream"),
        "remoteHead": remote_head,
        "preflight": preflight,
        "commands": commands,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "safety": push_execution_safety(mutation_attempted=mutation_attempted, pushed=pushed),
        "next": [
            "If passed, verify current-head CI with tools/riftreader_workflow/mcp_ci_status.py --status --json.",
            "Push success is not CI success; keep remote mutation and CI reporting as separate evidence.",
        ],
    }


def _temp_git(root: Path, args: list[str]) -> None:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        shell=False,
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {_decode(proc.stderr)}")


def run_self_test() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}
    blockers: list[str] = []
    with tempfile.TemporaryDirectory(prefix="riftreader-push-preflight-") as temp_dir:
        base = Path(temp_dir)
        origin = base / "origin.git"
        root = base / "work"
        origin.mkdir()
        root.mkdir()
        _temp_git(origin, ["init", "--bare"])
        (root / "agents.md").write_text("# test policy\n", encoding="utf-8")
        _temp_git(root, ["init", "-b", "main"])
        _temp_git(root, ["config", "user.email", "test@example.invalid"])
        _temp_git(root, ["config", "user.name", "RiftReader Test"])
        _temp_git(root, ["add", "agents.md"])
        _temp_git(root, ["commit", "-m", "initial"])
        _temp_git(root, ["remote", "add", "origin", str(origin)])
        _temp_git(root, ["push", "-u", "origin", "main"])
        (root / "agents.md").write_text("# test policy\n\nupdated\n", encoding="utf-8")
        _temp_git(root, ["add", "agents.md"])
        _temp_git(root, ["commit", "-m", "local update"])
        ready = push_preflight(root)
        details["ready"] = ready
        checks["ready_preflight"] = (
            ready.get("ok") is True
            and ready.get("status") == "ready"
            and ready.get("ahead") == 1
            and ready.get("behind") == 0
            and str(ready.get("expectedApprovalToken") or "").startswith("PUSH-")
            and ready.get("safety", {}).get("gitMutation") is False
        )
        approved_push = push_current_branch_apply(
            root,
            expected_head=str(ready.get("currentHead") or ""),
            branch=str(ready.get("branch") or ""),
            upstream=str(ready.get("upstream") or ""),
            approval_token=str(ready.get("expectedApprovalToken") or ""),
        )
        checks["approved_push"] = (
            approved_push.get("ok") is True
            and approved_push.get("pushed") is True
            and approved_push.get("remoteHead") == ready.get("currentHead")
            and approved_push.get("safety", {}).get("forcePush") is False
            and approved_push.get("safety", {}).get("branchRewrite") is False
        )
        details["approvedPush"] = approved_push

        (root / "untracked.txt").write_text("dirty\n", encoding="utf-8")
        dirty = push_preflight(root)
        checks["dirty_blocks"] = dirty.get("ok") is False and "PUSH_WORKTREE_DIRTY" in dirty.get("blockers", [])
        details["dirty"] = dirty

    for name, ok in checks.items():
        if not ok:
            blockers.append(f"self-test-failed:{name}")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-push-current-branch-self-test",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": utc_iso(),
        "status": "passed" if not blockers else "failed",
        "ok": not blockers,
        "checks": checks,
        "details": details,
        "blockers": blockers,
        "warnings": [],
        "safety": preflight_safety(read_only=True),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe push_current_branch preflight and approval-gated execution helper.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true", help="Run read-only push preflight.")
    mode.add_argument("--push", action="store_true", help="Run approval-gated normal non-force push after preflight.")
    mode.add_argument("--self-test", action="store_true", help="Run local self-test without touching the caller repo.")
    parser.add_argument("--repo-root", default=None, help="RiftReader repo root. Defaults to auto-detect.")
    parser.add_argument("--expected-head", default=None, help="Optional expected HEAD SHA to bind.")
    parser.add_argument("--branch", default=None, help="Optional expected current branch to bind.")
    parser.add_argument("--upstream", default=None, help="Optional expected upstream ref to bind.")
    parser.add_argument("--approval-token", default=None, help="Required PUSH-* approval token for --push.")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    return parser


def print_payload(payload: dict[str, Any], *, json_mode: bool) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.self_test:
            payload = run_self_test()
        elif args.push:
            repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
            payload = push_current_branch_apply(
                repo_root,
                expected_head=args.expected_head,
                branch=args.branch,
                upstream=args.upstream,
                approval_token=args.approval_token,
                timeout_seconds=args.timeout_seconds,
            )
        else:
            repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
            payload = push_preflight(
                repo_root,
                expected_head=args.expected_head,
                branch=args.branch,
                upstream=args.upstream,
                timeout_seconds=args.timeout_seconds,
            )
        print_payload(payload, json_mode=args.json)
        return 0 if payload.get("ok") else 2
    except Exception as exc:  # noqa: BLE001 - CLI must fail closed with structured JSON.
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-push-current-branch-preflight",
            "toolVersion": TOOL_VERSION,
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "ok": False,
            "blockers": [f"push-preflight-unexpected-error:{type(exc).__name__}"],
            "warnings": [str(exc)],
            "safety": preflight_safety(read_only=True),
        }
        print_payload(payload, json_mode=args.json)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
