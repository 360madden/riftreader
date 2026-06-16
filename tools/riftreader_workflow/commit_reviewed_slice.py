#!/usr/bin/env python3
"""Read-only preflight for a future explicit-path RiftReader commit helper.

Stage 24 intentionally performs no Git mutation. It verifies that a requested
commit slice is bounded, validation-bound, and ready for a later approval-gated
local commit helper.
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
    from .common import find_repo_root, safety_flags, utc_iso
    from .tracked_repo_context import ContextError, normalize_repo_path, path_policy
except ImportError:  # pragma: no cover - direct script execution fallback.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, safety_flags, utc_iso
    from riftreader_workflow.tracked_repo_context import ContextError, normalize_repo_path, path_policy


SCHEMA_VERSION = 1
TOOL_VERSION = "riftreader-commit-reviewed-slice-v0.1.0"
KIND = "riftreader-commit-reviewed-slice-preflight"

EVIDENCE_LOCAL_PREFIXES = (
    ".riftreader-local/validation-runs/",
    ".riftreader-local/package-intake/",
)
EVIDENCE_SUFFIXES = {".json"}
SECRET_WORD_RE = re.compile(r"(secret|credential|token|password|private[-_]?key)", re.IGNORECASE)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class CommitPreflightError(RuntimeError):
    """Internal structured failure for preflight setup failures."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _run_git(repo_root: Path, args: list[str], *, timeout_seconds: float = 30.0) -> subprocess.CompletedProcess[bytes]:
    if not args:
        raise CommitPreflightError("COMMIT_GIT_ARGS_INVALID")
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
        raise CommitPreflightError("COMMIT_GIT_NOT_FOUND", "git executable was not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise CommitPreflightError("COMMIT_GIT_TIMEOUT", f"git command timed out after {timeout_seconds}s") from exc


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def current_head(repo_root: Path, *, timeout_seconds: float = 30.0) -> str:
    proc = _run_git(repo_root, ["rev-parse", "HEAD"], timeout_seconds=timeout_seconds)
    if proc.returncode != 0:
        raise CommitPreflightError("COMMIT_HEAD_READ_FAILED", _decode(proc.stderr).strip())
    return _decode(proc.stdout).strip()


def _status_record(status: str, path: str, old_path: str | None = None) -> dict[str, Any]:
    normalized = path.replace("\\", "/")
    record: dict[str, Any] = {
        "status": status,
        "path": normalized,
        "indexStatus": status[:1],
        "worktreeStatus": status[1:2],
        "tracked": status != "??",
        "untracked": status == "??",
    }
    if old_path:
        record["oldPath"] = old_path.replace("\\", "/")
    return record


def parse_porcelain_z(raw: bytes) -> list[dict[str, Any]]:
    """Parse `git status --porcelain=v1 -z` enough for explicit-path gating."""

    rows: list[dict[str, Any]] = []
    parts = raw.split(b"\x00")
    index = 0
    while index < len(parts):
        item = parts[index]
        index += 1
        if not item:
            continue
        text = _decode(item)
        if len(text) < 4:
            rows.append(_status_record(text.strip() or "??", text.strip()))
            continue
        status = text[:2]
        path = text[3:]
        old_path: str | None = None
        if "R" in status or "C" in status:
            if index < len(parts) and parts[index]:
                old_path = _decode(parts[index])
                index += 1
        rows.append(_status_record(status, path, old_path=old_path))
    return rows


def git_dirty_state(repo_root: Path, *, timeout_seconds: float = 30.0) -> dict[str, Any]:
    proc = _run_git(
        repo_root,
        ["--no-pager", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        timeout_seconds=timeout_seconds,
    )
    if proc.returncode != 0:
        raise CommitPreflightError("COMMIT_STATUS_READ_FAILED", _decode(proc.stderr).strip())
    entries = parse_porcelain_z(proc.stdout)
    return {
        "status": "dirty" if entries else "clean",
        "dirty": bool(entries),
        "dirtyCount": len(entries),
        "entries": entries,
        "dirtyPaths": [str(entry["path"]) for entry in entries if entry.get("path")],
    }


def _has_wildcards(raw_path: str) -> bool:
    return any(char in raw_path for char in "*?[")


def normalize_commit_path(raw_path: str) -> tuple[str | None, str | None]:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None, "empty-path"
    if _has_wildcards(raw_path):
        return None, "wildcard-path"
    try:
        normalized = normalize_repo_path(raw_path)
    except ContextError as exc:
        return None, exc.reason
    policy = path_policy(normalized)
    if not policy.allowed:
        return policy.path, policy.reason or "path-blocked"
    return policy.path, None


def normalize_commit_paths(raw_paths: list[str] | None) -> tuple[list[str], list[dict[str, str]]]:
    normalized: list[str] = []
    seen: set[str] = set()
    forbidden: list[dict[str, str]] = []
    for raw in raw_paths or []:
        path, reason = normalize_commit_path(raw)
        if reason:
            forbidden.append({"path": str(raw), "reason": reason})
            continue
        assert path is not None
        if path not in seen:
            normalized.append(path)
            seen.add(path)
    return normalized, forbidden


def normalize_evidence_path(raw_path: str | None) -> tuple[str | None, str | None]:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None, "missing-path"
    if _has_wildcards(raw_path):
        return None, "wildcard-path"
    try:
        normalized = normalize_repo_path(raw_path)
    except ContextError as exc:
        return None, exc.reason
    suffix = Path(normalized).suffix.lower()
    if suffix not in EVIDENCE_SUFFIXES:
        return normalized, "validation-summary-must-be-json"
    lower = normalized.lower()
    if lower.startswith(".riftreader-local/"):
        if not any(lower.startswith(prefix) for prefix in EVIDENCE_LOCAL_PREFIXES):
            return normalized, "blocked-local-evidence-directory"
        return normalized, None
    policy = path_policy(normalized)
    if not policy.allowed:
        return policy.path, policy.reason or "path-blocked"
    return policy.path, None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validation_status(summary: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    status = str(summary.get("status") or "").strip().lower()
    ok_value = summary.get("ok")
    if ok_value is False:
        blockers.append("COMMIT_VALIDATION_FAILED")
    if status in {"failed", "failure", "blocked", "error"}:
        blockers.append("COMMIT_VALIDATION_FAILED")
    if status and status not in {"passed", "ready", "ok", "success", "succeeded"}:
        if "COMMIT_VALIDATION_FAILED" not in blockers:
            blockers.append("COMMIT_VALIDATION_FAILED")
    if ok_value is not True and status not in {"passed", "ready", "ok", "success", "succeeded"}:
        blockers.append("COMMIT_VALIDATION_FAILED")

    raw_blockers = summary.get("blockers")
    if isinstance(raw_blockers, list) and raw_blockers:
        blockers.append("COMMIT_VALIDATION_FAILED")
    raw_errors = summary.get("errors")
    if isinstance(raw_errors, list) and raw_errors:
        blockers.append("COMMIT_VALIDATION_FAILED")

    commands = summary.get("commands")
    if isinstance(commands, list):
        failed_commands = [
            str(item.get("label") or item.get("args") or index)
            for index, item in enumerate(commands, start=1)
            if isinstance(item, dict) and item.get("ok") is False
        ]
        if failed_commands:
            blockers.append("COMMIT_VALIDATION_FAILED")
            warnings.append(f"validation_failed_commands:{len(failed_commands)}")
    return not blockers, sorted(set(blockers)), warnings


def inspect_validation_summary(
    repo_root: Path,
    validation_summary_path: str | None,
    validation_digest: str | None,
    requested_paths: list[str],
    current_head_value: str,
) -> dict[str, Any]:
    normalized, reason = normalize_evidence_path(validation_summary_path)
    blockers: list[str] = []
    warnings: list[str] = []
    payload: dict[str, Any] = {
        "path": normalized,
        "exists": False,
        "sha256": None,
        "status": None,
        "ok": False,
        "blockers": blockers,
        "warnings": warnings,
    }
    if reason:
        blockers.append("COMMIT_VALIDATION_MISSING" if reason == "missing-path" else f"COMMIT_VALIDATION_FORBIDDEN:{reason}")
        return payload
    assert normalized is not None
    evidence_path = (repo_root / normalized).resolve()
    try:
        evidence_path.relative_to(repo_root.resolve())
    except ValueError:
        blockers.append("COMMIT_VALIDATION_FORBIDDEN:path-outside-repo")
        return payload
    if not evidence_path.is_file():
        blockers.append("COMMIT_VALIDATION_MISSING")
        return payload

    payload["exists"] = True
    digest = sha256_file(evidence_path)
    payload["sha256"] = digest
    if not isinstance(validation_digest, str) or not validation_digest.strip():
        blockers.append("COMMIT_VALIDATION_MISSING")
    elif digest.lower() != validation_digest.strip().lower():
        blockers.append("COMMIT_VALIDATION_DIGEST_MISMATCH")

    try:
        summary = json.loads(evidence_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - evidence parse must be fail-closed.
        blockers.append("COMMIT_VALIDATION_FAILED")
        payload["parseError"] = f"{type(exc).__name__}:{exc}"
        return payload
    if not isinstance(summary, dict):
        blockers.append("COMMIT_VALIDATION_FAILED")
        payload["parseError"] = "json-not-object"
        return payload

    payload["kind"] = summary.get("kind")
    payload["status"] = summary.get("status")
    payload["okValue"] = summary.get("ok")
    validation_ok, validation_blockers, validation_warnings = _validation_status(summary)
    if not validation_ok:
        blockers.extend(validation_blockers)
    warnings.extend(validation_warnings)

    validation_head = None
    git = summary.get("git")
    if isinstance(git, dict) and isinstance(git.get("head"), str):
        validation_head = git.get("head")
    if validation_head:
        payload["head"] = validation_head
        if not (current_head_value.startswith(validation_head) or validation_head.startswith(current_head_value)):
            blockers.append("COMMIT_VALIDATION_HEAD_MISMATCH")

    try:
        evidence_mtime = evidence_path.stat().st_mtime
        path_mtimes = [
            (repo_root / path).stat().st_mtime
            for path in requested_paths
            if (repo_root / path).exists()
        ]
        if path_mtimes and evidence_mtime + 1.0 < max(path_mtimes):
            blockers.append("COMMIT_VALIDATION_STALE")
    except OSError as exc:
        blockers.append("COMMIT_VALIDATION_STALE")
        warnings.append(f"validation_mtime_check_failed:{type(exc).__name__}")

    payload["ok"] = not blockers
    return payload


def validate_commit_message(commit_message: str | None) -> tuple[str | None, list[str]]:
    if not isinstance(commit_message, str):
        return None, ["missing"]
    message = commit_message.strip()
    reasons: list[str] = []
    if not message:
        reasons.append("empty")
    if len(message) > 120:
        reasons.append("too-long")
    if CONTROL_CHAR_RE.search(message):
        reasons.append("control-character")
    if SECRET_WORD_RE.search(message):
        reasons.append("secret-like")
    return message or None, reasons


def approval_token_for_facts(approval_facts: dict[str, Any]) -> str:
    payload = {
        "expectedHead": approval_facts.get("expectedHead"),
        "paths": approval_facts.get("paths"),
        "commitMessage": approval_facts.get("commitMessage"),
        "validationDigest": approval_facts.get("validationDigest"),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"COMMIT-{digest[:16]}"


def commit_preflight(
    repo_root: Path,
    *,
    expected_head: str | None,
    paths: list[str] | None,
    commit_message: str | None,
    validation_summary_path: str | None,
    validation_digest: str | None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    normalized_paths, forbidden_paths = normalize_commit_paths(paths)
    for item in forbidden_paths:
        blockers.append(f"COMMIT_PATH_FORBIDDEN:{item['path']}:{item['reason']}")
    if not normalized_paths:
        blockers.append("COMMIT_PATHS_EMPTY")

    normalized_message, message_reasons = validate_commit_message(commit_message)
    if message_reasons:
        blockers.append("COMMIT_MESSAGE_INVALID:" + ",".join(message_reasons))

    try:
        head = current_head(repo_root, timeout_seconds=timeout_seconds)
        dirty_state = git_dirty_state(repo_root, timeout_seconds=timeout_seconds)
    except CommitPreflightError as exc:
        head = None
        dirty_state = {"status": "unknown", "dirty": None, "dirtyCount": None, "entries": [], "dirtyPaths": []}
        blockers.append(exc.code)
        if str(exc) != exc.code:
            warnings.append(str(exc))

    if head is not None:
        if not isinstance(expected_head, str) or not expected_head.strip():
            blockers.append("COMMIT_HEAD_MISMATCH")
        elif expected_head.strip() != head:
            blockers.append("COMMIT_HEAD_MISMATCH")

    dirty_entries = dirty_state.get("entries") if isinstance(dirty_state.get("entries"), list) else []
    dirty_by_path = {
        str(entry.get("path")): entry
        for entry in dirty_entries
        if isinstance(entry, dict) and isinstance(entry.get("path"), str)
    }
    dirty_paths = set(dirty_by_path)
    requested_set = set(normalized_paths)
    for path in normalized_paths:
        if path not in dirty_paths:
            blockers.append(f"COMMIT_PATH_NOT_DIRTY:{path}")
    unrelated = sorted(dirty_paths - requested_set)
    if unrelated:
        blockers.append(f"COMMIT_UNRELATED_DIRTY_PATHS:{len(unrelated)}")

    validation = inspect_validation_summary(
        repo_root,
        validation_summary_path,
        validation_digest,
        normalized_paths,
        head or "",
    )
    blockers.extend(str(item) for item in validation.get("blockers") or [])
    warnings.extend(str(item) for item in validation.get("warnings") or [])

    approval_facts = {
        "expectedHead": expected_head.strip() if isinstance(expected_head, str) else expected_head,
        "currentHead": head,
        "paths": normalized_paths,
        "commitMessage": normalized_message,
        "validationSummaryPath": validation.get("path"),
        "validationDigest": validation_digest.strip().lower() if isinstance(validation_digest, str) else validation_digest,
        "validationSha256": validation.get("sha256"),
        "dirtyPathCount": len(dirty_paths),
    }
    status = "ready" if not blockers else "blocked"
    expected_token = approval_token_for_facts(approval_facts) if status == "ready" else None
    future_commands = {
        "gitAdd": ["git", "add", "--", *normalized_paths],
        "preCommit": ["pre-commit", "run", "--files", *normalized_paths],
        "gitCommit": ["git", "commit", "-m", normalized_message or ""],
    }
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "ready",
        "committed": False,
        "repoRoot": str(repo_root),
        "expectedHead": expected_head,
        "currentHead": head,
        "requestedPaths": normalized_paths,
        "dirtyState": dirty_state,
        "selectedDirtyEntries": [dirty_by_path[path] for path in normalized_paths if path in dirty_by_path],
        "unrelatedDirtyPaths": unrelated,
        "validation": validation,
        "approvalFacts": approval_facts,
        "expectedApprovalToken": expected_token,
        "futureCommands": future_commands,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "safety": {
            **safety_flags(),
            "readOnlyPreflight": True,
            "gitMutation": False,
            "localCommitOnly": False,
            "remoteMutation": False,
            "branchRewrite": False,
            "destructiveCleanup": False,
            "explicitPathsOnly": True,
            "stagedFiles": False,
            "committed": False,
            "pushed": False,
            "providerWrites": False,
            "inputSent": False,
            "movementSent": False,
            "x64dbgAttach": False,
            "noCheatEngine": True,
            "applyFlagSent": False,
        },
        "next": [
            "If ready, review approvalFacts and expectedApprovalToken before any future local commit execution helper.",
            "Stage 24 never runs git add, pre-commit, git commit, git push, reset, clean, provider writes, live input, CE, or x64dbg.",
            "Use the future Stage 25 helper for approval-gated local commit execution only after this preflight contract is still current.",
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


def _make_validation_summary(root: Path, head: str) -> tuple[str, str]:
    evidence_dir = root / ".riftreader-local" / "validation-runs" / "self-test"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    summary_path = evidence_dir / "summary.json"
    summary = {
        "schemaVersion": 1,
        "kind": "riftreader-validation-ledger",
        "status": "passed",
        "ok": True,
        "git": {"head": head},
        "commands": [{"label": "self-test-validation", "ok": True}],
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    digest = sha256_file(summary_path)
    return str(summary_path.relative_to(root)).replace("\\", "/"), digest


def run_self_test() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}
    blockers: list[str] = []
    with tempfile.TemporaryDirectory(prefix="riftreader-commit-preflight-") as temp_dir:
        root = Path(temp_dir)
        (root / "agents.md").write_text("# test policy\n", encoding="utf-8")
        (root / ".gitignore").write_text(".riftreader-local/\n", encoding="utf-8")
        (root / "docs").mkdir()
        tracked = root / "docs" / "slice.md"
        tracked.write_text("before\n", encoding="utf-8")
        _temp_git(root, ["init"])
        _temp_git(root, ["config", "user.email", "test@example.invalid"])
        _temp_git(root, ["config", "user.name", "RiftReader Test"])
        _temp_git(root, ["add", ".gitignore", "agents.md", "docs/slice.md"])
        _temp_git(root, ["commit", "-m", "initial"])
        head = current_head(root)

        tracked.write_text("after\n", encoding="utf-8")
        validation_path, digest = _make_validation_summary(root, head)
        ready = commit_preflight(
            root,
            expected_head=head,
            paths=["docs/slice.md"],
            commit_message="Update test slice",
            validation_summary_path=validation_path,
            validation_digest=digest,
        )
        checks["ready_preflight"] = (
            ready.get("ok") is True
            and ready.get("status") == "ready"
            and ready.get("committed") is False
            and ready.get("futureCommands", {}).get("gitAdd") == ["git", "add", "--", "docs/slice.md"]
            and str(ready.get("expectedApprovalToken") or "").startswith("COMMIT-")
        )
        details["ready"] = ready

        stale = commit_preflight(
            root,
            expected_head="0" * 40,
            paths=["docs/slice.md"],
            commit_message="Update test slice",
            validation_summary_path=validation_path,
            validation_digest=digest,
        )
        checks["stale_head_blocked"] = stale.get("ok") is False and "COMMIT_HEAD_MISMATCH" in stale.get("blockers", [])

        forbidden = commit_preflight(
            root,
            expected_head=head,
            paths=["docs/*.md", "../outside.md", ".riftreader-local/capture.json"],
            commit_message="Update test slice",
            validation_summary_path=validation_path,
            validation_digest=digest,
        )
        checks["forbidden_paths_blocked"] = forbidden.get("ok") is False and any(
            str(item).startswith("COMMIT_PATH_FORBIDDEN") for item in forbidden.get("blockers", [])
        )

        (root / "docs" / "other.md").write_text("other\n", encoding="utf-8")
        unrelated = commit_preflight(
            root,
            expected_head=head,
            paths=["docs/slice.md"],
            commit_message="Update test slice",
            validation_summary_path=validation_path,
            validation_digest=digest,
        )
        checks["unrelated_dirty_blocked"] = unrelated.get("ok") is False and any(
            str(item).startswith("COMMIT_UNRELATED_DIRTY_PATHS") for item in unrelated.get("blockers", [])
        )

        missing_validation = commit_preflight(
            root,
            expected_head=head,
            paths=["docs/slice.md"],
            commit_message="Update test slice",
            validation_summary_path=None,
            validation_digest=None,
        )
        checks["missing_validation_blocked"] = (
            missing_validation.get("ok") is False and "COMMIT_VALIDATION_MISSING" in missing_validation.get("blockers", [])
        )

    for name, ok in checks.items():
        if not ok:
            blockers.append(name)
    status = "passed" if not blockers else "failed"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-commit-reviewed-slice-self-test",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "passed",
        "checks": checks,
        "blockers": blockers,
        "details": {
            "readyStatus": details.get("ready", {}).get("status"),
            "readyTokenPrefix": str(details.get("ready", {}).get("expectedApprovalToken") or "")[:7],
        },
        "safety": {
            **safety_flags(),
            "tempRepoOnly": True,
            "readOnlyPreflight": True,
            "gitMutation": False,
            "remoteMutation": False,
            "branchRewrite": False,
            "destructiveCleanup": False,
            "providerWrites": False,
            "inputSent": False,
            "movementSent": False,
            "x64dbgAttach": False,
            "noCheatEngine": True,
            "applyFlagSent": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only explicit-path commit preflight for RiftReader.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true", help="Run read-only commit preflight. Does not stage or commit.")
    mode.add_argument("--self-test", action="store_true", help="Run a synthetic temp-repo self-test.")
    parser.add_argument("--repo-root", default=None, help="RiftReader repo root; auto-detected by default.")
    parser.add_argument("--expected-head", default=None)
    parser.add_argument("--path", action="append", dest="paths", default=[])
    parser.add_argument("--commit-message", default=None)
    parser.add_argument("--validation-summary-path", default=None)
    parser.add_argument("--validation-digest", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--json", action="store_true", help="Emit JSON. Present for wrapper consistency.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        payload = run_self_test()
    else:
        repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
        payload = commit_preflight(
            repo_root,
            expected_head=args.expected_head,
            paths=args.paths,
            commit_message=args.commit_message,
            validation_summary_path=args.validation_summary_path,
            validation_digest=args.validation_digest,
            timeout_seconds=args.timeout_seconds,
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    if payload.get("ok"):
        return 0
    if payload.get("status") == "blocked":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
