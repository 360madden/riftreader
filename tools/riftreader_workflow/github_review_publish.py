# Version: riftreader-github-review-publish-v0.1.1
# Total-Character-Count: 24108
# Purpose: Python-owned safe review snapshot, explicit staging, review-branch commit, push, and remote-SHA verification for RiftReader ChatGPT workflows.

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
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

TOOL_VERSION = "riftreader-github-review-publish-v0.1.1"
SNAPSHOT_MD = "handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.md"
SNAPSHOT_JSON = "handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.json"
DEFAULT_PROFILES = [
    "local-artifact-bridge",
    "transport-probe",
    "package-flow",
    "github-review-publish",
]

ALLOWED_STAGE_PATHS = frozenset({
    "docs/workflow/chatgpt-development-standards.md",
    "docs/workflow/github-review-publish.md",
    "docs/workflow/local-artifact-bridge.md",
    "docs/workflow/package-flow.md",
    "docs/workflow/transport-probe.md",
    "handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.json",
    "handoffs/current/RIFTREADER_REVIEW_SNAPSHOT.md",
    "scripts/riftreader-github-review-publish.cmd",
    "scripts/riftreader-local-artifact-bridge.cmd",
    "scripts/riftreader-package-flow.cmd",
    "scripts/riftreader-transport-probe.cmd",
    "scripts/test_github_review_publish.py",
    "scripts/test_local_artifact_bridge.py",
    "scripts/test_package_flow.py",
    "scripts/test_transport_probe.py",
    "tools/riftreader_workflow/github_review_publish.py",
    "tools/riftreader_workflow/local_artifact_bridge.py",
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

BLOCKED_STAGE_PREFIXES = IGNORED_DIRTY_PREFIXES
SAFE_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,120}$")


class ReviewPublishError(RuntimeError):
    """Raised for controlled review-publish failures."""


@dataclass(frozen=True)
class StatusEntry:
    raw: str
    index_status: str
    worktree_status: str
    path: str


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_repo_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewPublishError("empty repo-relative path")
    raw = value.replace("\\", "/").strip()
    if raw.startswith("/") or raw.startswith("//"):
        raise ReviewPublishError(f"absolute path rejected: {value}")
    if len(raw) >= 2 and raw[1] == ":":
        raise ReviewPublishError(f"drive-rooted path rejected: {value}")
    parts = [part for part in raw.split("/") if part]
    if any(part in (".", "..") for part in parts):
        raise ReviewPublishError(f"path traversal rejected: {value}")
    return "/".join(parts)


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
        raise ReviewPublishError("empty command")
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
        stdout_tail = completed.stdout[-1200:].replace("\n", "\\n")
        stderr_tail = completed.stderr[-1200:].replace("\n", "\\n")
        raise ReviewPublishError(
            "command failed rc={0}: {1}; stdout_tail={2!r}; stderr_tail={3!r}".format(
                completed.returncode,
                " ".join(command),
                stdout_tail,
                stderr_tail,
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
        raise ReviewPublishError(f"not inside a Git repo: {requested}")
    return Path(completed.stdout.strip()).resolve()


def parse_status_porcelain(text: str) -> List[StatusEntry]:
    entries: List[StatusEntry] = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        if len(raw_line) < 4:
            raise ReviewPublishError(f"unexpected git status line: {raw_line!r}")
        index_status = raw_line[0]
        worktree_status = raw_line[1]
        path_text = raw_line[3:]
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        path = normalize_repo_path(path_text.strip().strip('"'))
        entries.append(StatusEntry(raw=raw_line, index_status=index_status, worktree_status=worktree_status, path=path))
    return entries


def git_status_entries(repo_root: Path, timeout_seconds: int) -> List[StatusEntry]:
    report = git(repo_root, ["status", "--porcelain=v1"], timeout_seconds)
    return parse_status_porcelain(str(report["stdout"]))


def is_ignored_dirty(path: str) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in IGNORED_DIRTY_PREFIXES)


def is_blocked_stage_path(path: str) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in BLOCKED_STAGE_PREFIXES)


def categorize_dirty(entries: Iterable[StatusEntry]) -> Dict[str, List[str]]:
    allowed: List[str] = []
    ignored: List[str] = []
    unexpected: List[str] = []
    for entry in entries:
        path = entry.path
        if path in ALLOWED_STAGE_PATHS:
            allowed.append(path)
        elif is_ignored_dirty(path):
            ignored.append(path)
        else:
            unexpected.append(path)
    return {
        "allowed": sorted(set(allowed)),
        "ignored": sorted(set(ignored)),
        "unexpected": sorted(set(unexpected)),
    }


def validate_branch_name(branch_name: str) -> str:
    if not SAFE_BRANCH_RE.match(branch_name):
        raise ReviewPublishError(f"unsafe branch name rejected: {branch_name}")
    if ".." in branch_name or branch_name.endswith("/") or branch_name.endswith(".lock"):
        raise ReviewPublishError(f"unsafe branch name rejected: {branch_name}")
    return branch_name


def default_review_branch() -> str:
    return validate_branch_name("chatgpt/review-" + utc_stamp())


def package_flow_script(repo_root: Path) -> Path:
    return repo_join(repo_root, "scripts/riftreader-package-flow.cmd")


def validate_profiles(repo_root: Path, profiles: Sequence[str], timeout_seconds: int) -> List[Dict[str, Any]]:
    script = package_flow_script(repo_root)
    if not script.is_file():
        raise ReviewPublishError(f"package-flow wrapper missing: {script}")
    results: List[Dict[str, Any]] = []
    for profile in profiles:
        command = [str(script), "--json", "validate-current", "--profile", profile]
        report = run_command(repo_root, command, timeout_seconds)
        try:
            parsed = json.loads(str(report["stdout"]))
        except json.JSONDecodeError as exc:
            raise ReviewPublishError(f"profile validation did not emit JSON: {profile}") from exc
        if not parsed.get("ok"):
            raise ReviewPublishError(f"profile validation failed: {profile}")
        results.append({"profile": profile, "ok": True, "report": parsed})
    return results


def write_review_snapshot(repo_root: Path, payload: Dict[str, Any]) -> Dict[str, str]:
    json_path = repo_join(repo_root, SNAPSHOT_JSON)
    md_path = repo_join(repo_root, SNAPSHOT_MD)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    json_payload = json.dumps(payload, indent=2, sort_keys=True)
    json_path.write_text(json_payload + "\n", encoding="utf-8")

    lines = [
        "# RiftReader Review Snapshot",
        "",
        f"Created UTC: {payload['createdUtc']}",
        f"Tool: {payload['tool']}",
        f"Current branch: {payload.get('currentBranch', '')}",
        f"HEAD: {payload.get('head', '')}",
        "",
        "## Validation profiles",
    ]
    for item in payload.get("validationProfiles", []):
        lines.append(f"- {item['profile']}: ok={item['ok']}")
    lines.extend([
        "",
        "## Allowed dirty paths",
    ])
    for path in payload.get("dirtyPaths", {}).get("allowed", []):
        lines.append(f"- `{path}`")
    lines.extend([
        "",
        "## Ignored/generated dirty paths",
    ])
    for path in payload.get("dirtyPaths", {}).get("ignored", []):
        lines.append(f"- `{path}`")
    lines.extend([
        "",
        "## Unexpected dirty paths",
    ])
    unexpected = payload.get("dirtyPaths", {}).get("unexpected", [])
    if unexpected:
        for path in unexpected:
            lines.append(f"- `{path}`")
    else:
        lines.append("None.")
    lines.extend([
        "",
        "## Policy",
        "- Python owns workflow logic.",
        "- CMD/PowerShell wrappers stay thin.",
        "- Stage explicit allowlisted paths only.",
        "- Do not stage generated payload artifacts.",
        "- Review branches are preferred over direct main pushes.",
        "",
        "# END_OF_REVIEW_SNAPSHOT",
    ])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": SNAPSHOT_JSON, "markdown": SNAPSHOT_MD}


def current_branch(repo_root: Path, timeout_seconds: int) -> str:
    return str(git(repo_root, ["branch", "--show-current"], timeout_seconds)["stdout"]).strip()


def current_head(repo_root: Path, timeout_seconds: int) -> str:
    return str(git(repo_root, ["rev-parse", "HEAD"], timeout_seconds)["stdout"]).strip()


def build_snapshot_payload(repo_root: Path, profiles: Sequence[str], validation: List[Dict[str, Any]], timeout_seconds: int) -> Dict[str, Any]:
    entries = git_status_entries(repo_root, timeout_seconds)
    dirty = categorize_dirty(entries)
    return {
        "schemaVersion": 1,
        "tool": TOOL_VERSION,
        "createdUtc": utc_iso(),
        "currentBranch": current_branch(repo_root, timeout_seconds),
        "head": current_head(repo_root, timeout_seconds),
        "profileSet": list(profiles),
        "validationProfiles": [{"profile": item["profile"], "ok": item["ok"]} for item in validation],
        "dirtyPaths": dirty,
        "allowedStagePaths": sorted(ALLOWED_STAGE_PATHS),
        "ignoredDirtyPrefixes": list(IGNORED_DIRTY_PREFIXES),
        "blockedStagePrefixes": list(BLOCKED_STAGE_PREFIXES),
    }


def refresh_snapshot(repo_root: Path, profiles: Sequence[str], timeout_seconds: int) -> Dict[str, Any]:
    validation = validate_profiles(repo_root, profiles, timeout_seconds)
    payload = build_snapshot_payload(repo_root, profiles, validation, timeout_seconds)
    paths = write_review_snapshot(repo_root, payload)
    entries_after = git_status_entries(repo_root, timeout_seconds)
    dirty_after = categorize_dirty(entries_after)
    payload["dirtyPathsAfterSnapshot"] = dirty_after
    payload["snapshotPaths"] = paths
    if dirty_after["unexpected"]:
        raise ReviewPublishError("unexpected dirty paths block review publish: " + ", ".join(dirty_after["unexpected"]))
    return payload


def existing_allowed_paths(repo_root: Path, dirty_allowed_paths: Sequence[str]) -> List[str]:
    result: List[str] = []
    for rel in dirty_allowed_paths:
        if is_blocked_stage_path(rel):
            raise ReviewPublishError(f"blocked path cannot be staged: {rel}")
        path = repo_join(repo_root, rel)
        if path.exists():
            result.append(rel)
    return sorted(set(result))


def verify_cached_paths(repo_root: Path, timeout_seconds: int) -> List[str]:
    report = git(repo_root, ["diff", "--cached", "--name-only"], timeout_seconds)
    paths = [normalize_repo_path(line) for line in str(report["stdout"]).splitlines() if line.strip()]
    unexpected = [path for path in paths if path not in ALLOWED_STAGE_PATHS]
    blocked = [path for path in paths if is_blocked_stage_path(path)]
    if unexpected or blocked:
        raise ReviewPublishError(
            "staged path policy violation: unexpected={0} blocked={1}".format(unexpected, blocked)
        )
    if not paths:
        raise ReviewPublishError("nothing staged for commit")
    return sorted(paths)


def stage_commit_push_branch(
    repo_root: Path,
    branch_name: str,
    commit_message: str,
    paths_to_stage: Sequence[str],
    timeout_seconds: int,
    return_to_start_branch: bool = False,
) -> Dict[str, Any]:
    branch = validate_branch_name(branch_name)
    starting_branch = current_branch(repo_root, timeout_seconds)
    if return_to_start_branch and not starting_branch:
        raise ReviewPublishError("--return-to-start-branch requires a named starting branch")
    if not paths_to_stage:
        raise ReviewPublishError("no allowlisted paths to stage")

    switched_to_review_branch = False
    try:
        git(repo_root, ["switch", "-c", branch], timeout_seconds)
        switched_to_review_branch = True
        git(repo_root, ["add", "--", *paths_to_stage], timeout_seconds)
        cached_paths = verify_cached_paths(repo_root, timeout_seconds)
        git(repo_root, ["commit", "-m", commit_message], timeout_seconds)
        local_head = current_head(repo_root, timeout_seconds)
        git(repo_root, ["push", "-u", "origin", branch], timeout_seconds)
        remote_report = git(repo_root, ["ls-remote", "origin", "refs/heads/" + branch], timeout_seconds)
        remote_lines = [line for line in str(remote_report["stdout"]).splitlines() if line.strip()]
        if not remote_lines:
            raise ReviewPublishError("remote branch SHA not found after push")
        remote_sha = remote_lines[0].split()[0]
        if remote_sha != local_head:
            raise ReviewPublishError(f"remote SHA mismatch: remote={remote_sha} local={local_head}")
    except Exception as exc:
        if return_to_start_branch and starting_branch and switched_to_review_branch:
            try:
                git(repo_root, ["switch", starting_branch], timeout_seconds)
            except Exception as return_exc:
                raise ReviewPublishError(
                    "publish failed and return-to-start-branch also failed: "
                    f"publish_error={exc}; return_error={return_exc}"
                ) from return_exc
        raise

    returned_to_start_branch = False
    if return_to_start_branch:
        git(repo_root, ["switch", starting_branch], timeout_seconds)
        returned_to_start_branch = True

    return {
        "branch": branch,
        "commit": local_head,
        "remoteSha": remote_sha,
        "stagedPaths": cached_paths,
        "startingBranch": starting_branch,
        "returnedToStartBranch": returned_to_start_branch,
        "finalBranch": current_branch(repo_root, timeout_seconds),
    }


def profile_list(raw: str) -> List[str]:
    profiles = [part.strip() for part in raw.split(",") if part.strip()]
    return profiles or list(DEFAULT_PROFILES)


def command_validate_ready(args: argparse.Namespace) -> Dict[str, Any]:
    repo_root = repo_root_from(args.repo_root, args.timeout_seconds)
    profiles = profile_list(args.profiles)
    payload = refresh_snapshot(repo_root, profiles, args.timeout_seconds)
    return {
        "schemaVersion": 1,
        "tool": TOOL_VERSION,
        "command": "validate-ready",
        "ok": True,
        "snapshot": payload,
    }


def command_publish_branch(args: argparse.Namespace) -> Dict[str, Any]:
    repo_root = repo_root_from(args.repo_root, args.timeout_seconds)
    profiles = profile_list(args.profiles)
    snapshot = refresh_snapshot(repo_root, profiles, args.timeout_seconds)
    dirty = snapshot["dirtyPathsAfterSnapshot"]
    if dirty["unexpected"]:
        raise ReviewPublishError("unexpected dirty paths block publish")
    stage_paths = existing_allowed_paths(repo_root, dirty["allowed"])
    branch = args.branch or default_review_branch()
    message = args.message or "Add ChatGPT review workflow snapshot"

    plan = {
        "branch": branch,
        "message": message,
        "pathsToStage": stage_paths,
        "ignoredDirtyPaths": dirty["ignored"],
        "returnToStartBranch": bool(args.return_to_start_branch),
    }
    if not args.yes_push:
        return {
            "schemaVersion": 1,
            "tool": TOOL_VERSION,
            "command": "publish-branch",
            "ok": True,
            "dryRun": True,
            "plan": plan,
            "snapshot": snapshot,
            "note": "Pass --yes-push to create branch, commit, push, and verify remote SHA.",
        }
    publish = stage_commit_push_branch(
        repo_root,
        branch,
        message,
        stage_paths,
        args.timeout_seconds,
        return_to_start_branch=bool(args.return_to_start_branch),
    )
    return {
        "schemaVersion": 1,
        "tool": TOOL_VERSION,
        "command": "publish-branch",
        "ok": True,
        "dryRun": False,
        "plan": plan,
        "publish": publish,
        "snapshot": snapshot,
    }


def command_self_test(_args: argparse.Namespace) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    try:
        normalize_repo_path("../bad")
        checks.append({"name": "traversal_rejected", "pass": False})
    except ReviewPublishError:
        checks.append({"name": "traversal_rejected", "pass": True})

    status_text = "?? docs/workflow/github-review-publish.md\n?? artifacts/chatgpt-payloads/\n?? random.tmp\n"
    entries = parse_status_porcelain(status_text)
    dirty = categorize_dirty(entries)
    checks.append({"name": "allowed_dirty_detected", "pass": "docs/workflow/github-review-publish.md" in dirty["allowed"]})
    checks.append({"name": "ignored_artifact_detected", "pass": "artifacts/chatgpt-payloads" in dirty["ignored"]})
    checks.append({"name": "unexpected_detected", "pass": "random.tmp" in dirty["unexpected"]})

    with tempfile.TemporaryDirectory(prefix="riftreader-review-publish-selftest-") as temp_name:
        temp = Path(temp_name)
        payload = {
            "schemaVersion": 1,
            "tool": TOOL_VERSION,
            "createdUtc": utc_iso(),
            "currentBranch": "main",
            "head": "0" * 40,
            "profileSet": ["github-review-publish"],
            "validationProfiles": [{"profile": "github-review-publish", "ok": True}],
            "dirtyPaths": {"allowed": [], "ignored": [], "unexpected": []},
            "allowedStagePaths": sorted(ALLOWED_STAGE_PATHS),
            "ignoredDirtyPrefixes": list(IGNORED_DIRTY_PREFIXES),
            "blockedStagePrefixes": list(BLOCKED_STAGE_PREFIXES),
        }
        paths = write_review_snapshot(temp, payload)
        checks.append({"name": "snapshot_written", "pass": (temp / paths["json"]).is_file() and (temp / paths["markdown"]).is_file()})

    try:
        validate_branch_name("bad..branch")
        checks.append({"name": "unsafe_branch_rejected", "pass": False})
    except ReviewPublishError:
        checks.append({"name": "unsafe_branch_rejected", "pass": True})

    ok = all(check["pass"] for check in checks)
    return {
        "schemaVersion": 1,
        "tool": TOOL_VERSION,
        "selfTest": True,
        "ok": ok,
        "checkCount": len(checks),
        "checks": checks,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish sanitized RiftReader review snapshots to GitHub review branches.")
    parser.add_argument("--json", action="store_true", help="Emit clean JSON only.")
    sub = parser.add_subparsers(dest="command", required=True)

    ready = sub.add_parser("validate-ready", help="Validate profiles and write review snapshot without Git commit or push.")
    ready.add_argument("--repo-root", default=None, help="Repo root. Defaults to current Git repo.")
    ready.add_argument("--profiles", default=",".join(DEFAULT_PROFILES), help="Comma-separated profiles to validate.")
    ready.add_argument("--timeout-seconds", type=int, default=240, help="Timeout per native command.")

    publish = sub.add_parser("publish-branch", help="Validate, snapshot, explicit-stage, commit, push review branch, and verify remote SHA.")
    publish.add_argument("--repo-root", default=None, help="Repo root. Defaults to current Git repo.")
    publish.add_argument("--profiles", default=",".join(DEFAULT_PROFILES), help="Comma-separated profiles to validate.")
    publish.add_argument("--timeout-seconds", type=int, default=240, help="Timeout per native command.")
    publish.add_argument("--branch", default=None, help="Review branch name. Defaults to chatgpt/review-<UTC>.")
    publish.add_argument("--message", default=None, help="Commit message.")
    publish.add_argument("--yes-push", action="store_true", help="Actually create branch, commit, push, and verify remote SHA.")
    publish.add_argument(
        "--return-to-start-branch",
        action="store_true",
        help="After a successful publish, switch back to the branch that was active before publish-branch ran.",
    )

    sub.add_parser("self-test", help="Run internal synthetic checks without network or repo mutation.")
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
    if "publish" in report:
        print(f"branch: {report['publish'].get('branch')}")
        print(f"commit: {report['publish'].get('commit')}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-ready":
            report = command_validate_ready(args)
        elif args.command == "publish-branch":
            report = command_publish_branch(args)
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
    except (ReviewPublishError, subprocess.TimeoutExpired, OSError, json.JSONDecodeError) as exc:
        error_report = {
            "schemaVersion": 1,
            "tool": TOOL_VERSION,
            "ok": False,
            "errorType": type(exc).__name__,
            "error": str(exc),
        }
        print_report(error_report, args.json)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
