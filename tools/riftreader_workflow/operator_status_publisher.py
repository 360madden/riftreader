#!/usr/bin/env python3
# Version: riftreader-operator-status-publisher-v0.1.0
# Total-Character-Count: 0000010943
# Purpose: Publish latest operator-status board to a dedicated GitHub branch for ChatGPT inspection without manual JSON paste.

from __future__ import annotations

import argparse, contextlib, json, shutil, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "riftreader-operator-status-publisher-v0.1.0"
DEFAULT_BRANCH = "chatgpt/operator-status"
STATUS_JSON = Path(".riftreader-local/operator-status/latest/summary.json")
STATUS_MD = Path(".riftreader-local/operator-status/latest/summary.md")
SNAPSHOT_JSON = Path("handoffs/current/RIFTREADER_OPERATOR_STATUS.json")
SNAPSHOT_MD = Path("handoffs/current/RIFTREADER_OPERATOR_STATUS.md")
EXPECTED = sorted([SNAPSHOT_JSON.as_posix(), SNAPSHOT_MD.as_posix()])

class PublishError(RuntimeError): pass

def utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def repo_root(start: Path) -> Path:
    p = start.resolve()
    for c in [p, *p.parents]:
        if (c / ".git").exists():
            return c
    raise PublishError("Could not find git repo root")

def run(args: list[str], cwd: Path, timeout: int = 180, check: bool = True) -> subprocess.CompletedProcess[str]:
    r = subprocess.run(args, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    if check and r.returncode != 0:
        raise PublishError(json.dumps({"args": args, "cwd": str(cwd), "returncode": r.returncode, "stdoutTail": r.stdout[-2000:], "stderrTail": r.stderr[-2000:]}, indent=2))
    return r

def valid_branch(branch: str) -> str:
    if not branch or branch.startswith(("/", ".")) or branch.endswith(("/", ".")):
        raise PublishError(f"Unsafe branch: {branch!r}")
    if any(x in branch for x in ("..", "\\", "@{", "//")):
        raise PublishError(f"Unsafe branch: {branch!r}")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._/-")
    if any(ch not in allowed for ch in branch):
        raise PublishError(f"Unsafe branch: {branch!r}")
    return branch

def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PublishError(f"Missing JSON artifact: {path}")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise PublishError(f"JSON artifact is not object: {path}")
    return data

def read_text(path: Path) -> str:
    if not path.is_file():
        raise PublishError(f"Missing text artifact: {path}")
    return path.read_text(encoding="utf-8", errors="replace")

def run_operator_status(repo: Path, timeout: int) -> dict[str, Any]:
    r = run([sys.executable, "-m", "tools.riftreader_workflow.operator_status", "--write", "--json"], repo, timeout=timeout)
    data = json.loads(r.stdout)
    if not isinstance(data, dict) or data.get("status") != "passed":
        raise PublishError("operator_status did not pass")
    return data

def build_snapshot(repo: Path, status: dict[str, Any], status_md: str, head: str) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-operator-status-github-snapshot",
        "toolVersion": VERSION,
        "generatedAtUtc": utc(),
        "source": {"repoRoot": str(repo), "baseHead": head, "operatorStatusJson": STATUS_JSON.as_posix(), "operatorStatusMarkdown": STATUS_MD.as_posix()},
        "board": status.get("board") if isinstance(status.get("board"), dict) else {},
        "classifier": status.get("classifier") if isinstance(status.get("classifier"), dict) else {},
        "compactStatus": status.get("compactStatus") if isinstance(status.get("compactStatus"), dict) else {},
        "operatorStatus": status,
        "operatorStatusMarkdown": status_md,
        "safety": {"mainWorktreeMutation": False, "snapshotBranchMutation": True, "movementSent": False, "inputSent": False, "targetMemoryBytesRead": False, "targetMemoryBytesWritten": False, "noCheatEngine": True, "x64dbgAttach": False, "proofPromotion": False, "currentTruthWritten": False},
    }

def render_md(s: dict[str, Any]) -> str:
    b = s.get("board") or {}
    c = s.get("classifier") or {}
    lines = [
        "# RiftReader Operator Status Snapshot", "",
        f"- Generated UTC: `{s.get('generatedAtUtc')}`",
        f"- Base HEAD: `{s.get('source', {}).get('baseHead')}`", "",
        "## Project Board", "",
        "| Field | Value |", "|---|---|",
        f"| Current lane | `{b.get('currentLane')}` |",
        f"| Now | `{b.get('now')}` |",
        f"| Next | `{b.get('next')}` |",
        f"| Later | `{b.get('later')}` |",
        f"| Blocked by | `{b.get('blockedBy')}` |", "",
        "## Classifier", "",
        f"- Classification: `{c.get('classification')}`",
        f"- Confidence: `{c.get('confidence')}`",
        f"- Blocker: `{c.get('blocker')}`",
        f"- Reason: {c.get('reason')}", "",
        "## Next Recommended Action", "",
        str(c.get("nextRecommendedAction") or ""), "",
        "```text", str(c.get("nextRecommendedCommand") or ""), "```", "",
        "## Do Not Do", "",
    ]
    for item in c.get("doNotDo") or []:
        lines.append(f"- {item}")
    lines += ["", "## Raw operator-status markdown", "", "```markdown", str(s.get("operatorStatusMarkdown") or "").rstrip(), "```", "", "<!-- END_OF_SCRIPT_MARKER -->", ""]
    return "\n".join(lines)

def write_files(worktree: Path, snap: dict[str, Any]) -> dict[str, Any]:
    md = render_md(snap)
    js = json.dumps(snap, indent=2, sort_keys=True) + "\n"
    for rel, text in ((SNAPSHOT_MD, md), (SNAPSHOT_JSON, js)):
        p = worktree / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    return {"markdownPath": SNAPSHOT_MD.as_posix(), "jsonPath": SNAPSHOT_JSON.as_posix(), "markdownBytes": len(md.encode()), "jsonBytes": len(js.encode())}

def publish(repo: Path, branch: str, run_status: bool, push: bool, timeout: int) -> dict[str, Any]:
    branch = valid_branch(branch)
    status = run_operator_status(repo, timeout) if run_status else load_json(repo / STATUS_JSON)
    status_md = read_text(repo / STATUS_MD)
    head = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
    tmp = Path(tempfile.mkdtemp(prefix="riftreader-operator-status-publish-"))
    wt = tmp / "worktree"
    try:
        run(["git", "worktree", "add", "--detach", str(wt), head], repo, timeout=180)
        run(["git", "checkout", "-B", branch], wt, timeout=120)
        snap = build_snapshot(repo, status, status_md, head)
        files = write_files(wt, snap)
        run(["git", "add", "--", *EXPECTED], wt)
        staged = sorted(run(["git", "diff", "--cached", "--name-only"], wt).stdout.splitlines())
        if staged != EXPECTED:
            raise PublishError(f"Staged path mismatch. Expected {EXPECTED}; got {staged}")
        run(["git", "--no-pager", "diff", "--cached", "--check"], wt)
        changed = run(["git", "diff", "--cached", "--quiet"], wt, check=False)
        committed = False
        if changed.returncode == 1:
            run(["git", "commit", "-m", "Publish operator status snapshot"], wt, timeout=180)
            committed = True
        elif changed.returncode != 0:
            raise PublishError(changed.stderr)
        sha = run(["git", "rev-parse", "HEAD"], wt).stdout.strip()
        remote_sha = None
        if push:
            run(["git", "push", "--force-with-lease", "origin", f"HEAD:refs/heads/{branch}"], wt, timeout=240)
            line = run(["git", "ls-remote", "origin", f"refs/heads/{branch}"], repo, timeout=120).stdout.strip()
            remote_sha = line.split()[0] if line else ""
            if remote_sha != sha:
                raise PublishError(f"Remote SHA mismatch: local={sha}; remote={remote_sha}")
        return {"status": "passed", "branch": branch, "baseHead": head, "commitSha": sha, "remoteSha": remote_sha, "committed": committed, "pushed": push, "files": files, "board": snap["board"], "classification": snap["classifier"].get("classification"), "blocker": snap["classifier"].get("blocker")}
    finally:
        with contextlib.suppress(Exception):
            run(["git", "worktree", "remove", "--force", str(wt)], repo, timeout=120, check=False)
        shutil.rmtree(tmp, ignore_errors=True)

def self_test() -> dict[str, Any]:
    sample = {"board": {"currentLane": "static-chain-repair-needed", "now": "Static-chain repair", "next": "Use diagnostics", "later": "Later", "blockedBy": "root-pointer-null"}, "classifier": {"classification": "static-chain-repair-needed", "confidence": "high", "reason": "test", "blocker": "root-pointer-null", "nextRecommendedAction": "Run diagnostics", "nextRecommendedCommand": "python example.py", "doNotDo": ["Do not rerun proof recovery."]}, "compactStatus": {"blockers": ["root-pointer-null"]}}
    snap = build_snapshot(Path("C:/RIFT MODDING/RiftReader"), sample, "# Test", "abc123")
    md = render_md(snap)
    checks = [{"name": "renders-board", "pass": "Project Board" in md}, {"name": "renders-lane", "pass": "static-chain-repair-needed" in md}, {"name": "renders-do-not-do", "pass": "Do not rerun proof recovery" in md}]
    return {"schemaVersion": 1, "kind": "riftreader-operator-status-publisher-self-test", "toolVersion": VERSION, "status": "passed" if all(x["pass"] for x in checks) else "failed", "checks": checks}

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Publish operator status to GitHub transport branch.")
    p.add_argument("--repo-root", type=Path)
    p.add_argument("--branch", default=DEFAULT_BRANCH)
    p.add_argument("--run-status", action="store_true")
    p.add_argument("--push", action="store_true")
    p.add_argument("--timeout-seconds", type=int, default=240)
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        if a.self_test:
            out = self_test()
        else:
            repo = a.repo_root.resolve() if a.repo_root else repo_root(Path.cwd())
            out = {"schemaVersion": 1, "kind": "riftreader-operator-status-publisher", "toolVersion": VERSION, "generatedAtUtc": utc(), "repoRoot": str(repo), **publish(repo, a.branch, bool(a.run_status), bool(a.push), max(30, int(a.timeout_seconds)))}
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0 if out.get("status") == "passed" else 1
    except Exception as exc:
        print(json.dumps({"schemaVersion": 1, "kind": "riftreader-operator-status-publisher", "toolVersion": VERSION, "generatedAtUtc": utc(), "status": "failed", "error": f"{type(exc).__name__}: {exc}"}, indent=2, sort_keys=True))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
