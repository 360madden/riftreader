#!/usr/bin/env python3
# Version: riftreader-operator-status-v0.1.0
# Total-Character-Count: 0000009415
# Purpose: One-command Python-owned operator board: run compact status, run recovery classifier, write latest board artifacts.

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "riftreader-operator-status-v0.1.0"
SCHEMA_VERSION = 1


class OperatorStatusError(RuntimeError):
    pass


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for item in [current, *current.parents]:
        if (item / ".git").exists():
            return item
    return current


def rel(repo: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def run(args: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    out: dict[str, Any] = {"args": args, "cwd": str(cwd), "startedAtUtc": utc_iso(), "timeoutSeconds": timeout, "exitCode": None, "timedOut": False, "stdout": "", "stderr": ""}
    try:
        p = subprocess.run(args, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
        out["exitCode"] = p.returncode
        out["stdout"] = p.stdout or ""
        out["stderr"] = p.stderr or ""
    except subprocess.TimeoutExpired as exc:
        out["timedOut"] = True
        out["stdout"] = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "replace")
        out["stderr"] = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", "replace")
    out["completedAtUtc"] = utc_iso()
    return out


def ok(cmd: dict[str, Any], label: str, codes: set[int] | None = None) -> str:
    codes = codes or {0}
    if cmd.get("timedOut") or cmd.get("exitCode") not in codes:
        raise OperatorStatusError(f"{label} failed: exit={cmd.get('exitCode')} timeout={cmd.get('timedOut')} stderr={str(cmd.get('stderr') or '')[:700]}")
    return str(cmd.get("stdout") or "")


def parse_json(text: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except Exception as exc:
        raise OperatorStatusError(f"{label} did not emit JSON: {type(exc).__name__}: {exc}") from exc
    if not isinstance(value, dict):
        raise OperatorStatusError(f"{label} JSON is not an object")
    return value


def cmd_summary(cmd: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in cmd.items() if k not in {"stdout", "stderr"}}


def render_md(summary: dict[str, Any]) -> str:
    b = summary.get("board") if isinstance(summary.get("board"), dict) else {}
    c = summary.get("classifier") if isinstance(summary.get("classifier"), dict) else {}
    lines = [
        "# RiftReader Operator Status",
        "",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Status: `{summary.get('status')}`",
        "",
        "## Project Board",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Current lane | `{b.get('currentLane')}` |",
        f"| Now | `{b.get('now')}` |",
        f"| Next | `{b.get('next')}` |",
        f"| Later | `{b.get('later')}` |",
        f"| Blocked by | `{b.get('blockedBy')}` |",
        "",
        "## Next Recommended Action",
        "",
        str(c.get("nextRecommendedAction") or ""),
        "",
        "```text",
        str(c.get("nextRecommendedCommand") or ""),
        "```",
        "",
        "## Do Not Do",
        "",
    ]
    for item in c.get("doNotDo") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## END_OF_SCRIPT_MARKER", ""])
    return "\n".join(lines)


def write_artifacts(repo: Path, summary: dict[str, Any]) -> dict[str, str]:
    out = repo / ".riftreader-local" / "operator-status" / utc_stamp()
    latest = repo / ".riftreader-local" / "operator-status" / "latest"
    out.mkdir(parents=True, exist_ok=True)
    latest.mkdir(parents=True, exist_ok=True)
    for d in (out, latest):
        (d / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (d / "summary.md").write_text(render_md(summary), encoding="utf-8")
    return {"summaryJson": rel(repo, out / "summary.json"), "summaryMarkdown": rel(repo, out / "summary.md"), "latestJson": rel(repo, latest / "summary.json"), "latestMarkdown": rel(repo, latest / "summary.md")}


def build(repo: Path, timeout: int, write: bool) -> dict[str, Any]:
    status_py = repo / "tools" / "riftreader_workflow" / "status_packet.py"
    classifier_py = repo / "tools" / "riftreader_workflow" / "recovery_classifier.py"
    if not status_py.is_file():
        raise OperatorStatusError(f"Missing status helper: {status_py}")
    if not classifier_py.is_file():
        raise OperatorStatusError(f"Missing recovery classifier: {classifier_py}")

    commands = []
    a = run([sys.executable, str(status_py), "--compact-json", "--write"], repo, timeout)
    commands.append(a)
    compact = parse_json(ok(a, "compact status", {0, 2}), "compact status")

    b = run([sys.executable, "-m", "tools.riftreader_workflow.recovery_classifier", "--write", "--json"], repo, timeout)
    commands.append(b)
    classifier = parse_json(ok(b, "recovery classifier"), "recovery classifier")

    board = classifier.get("board") if isinstance(classifier.get("board"), dict) else {}
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-operator-status",
        "toolVersion": VERSION,
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "repoRoot": str(repo),
        "board": board,
        "classifier": {
            "classification": classifier.get("classification"),
            "confidence": classifier.get("confidence"),
            "reason": classifier.get("reason"),
            "blocker": classifier.get("blocker"),
            "nextRecommendedAction": classifier.get("nextRecommendedAction"),
            "nextRecommendedCommand": classifier.get("nextRecommendedCommand"),
            "safeAutomaticActions": classifier.get("safeAutomaticActions") or [],
            "approvalRequiredActions": classifier.get("approvalRequiredActions") or [],
            "doNotDo": classifier.get("doNotDo") or [],
            "artifacts": classifier.get("artifacts") or {},
        },
        "compactStatus": {
            "status": compact.get("status"),
            "generatedAtUtc": compact.get("generatedAtUtc"),
            "workflowClassification": compact.get("workflowClassification"),
            "blockers": compact.get("blockers") or [],
            "warnings": compact.get("warnings") or [],
            "git": compact.get("git") or {},
        },
        "commands": [cmd_summary(x) for x in commands],
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "gitMutation": False,
            "noCheatEngine": True,
            "x64dbgAttach": False,
            "proofPromotion": False,
            "currentTruthWritten": False,
        },
    }
    if write:
        summary["artifacts"] = write_artifacts(repo, summary)
    return summary


def self_test() -> dict[str, Any]:
    sample = {"status": "passed", "generatedAtUtc": utc_iso(), "board": {"currentLane": "static-chain-repair-needed", "now": "Static-chain repair", "next": "Use diagnostics", "later": "Later", "blockedBy": "root-pointer-null"}, "classifier": {"nextRecommendedAction": "Run diagnostics", "nextRecommendedCommand": "python example.py", "doNotDo": ["Do not rerun proof recovery."]}}
    md = render_md(sample)
    checks = [
        {"name": "board-rendered", "pass": "Project Board" in md},
        {"name": "lane-rendered", "pass": "static-chain-repair-needed" in md},
        {"name": "do-not-do-rendered", "pass": "Do not rerun proof recovery" in md},
    ]
    return {"schemaVersion": SCHEMA_VERSION, "kind": "riftreader-operator-status-self-test", "toolVersion": VERSION, "status": "passed" if all(x["pass"] for x in checks) else "failed", "checks": checks}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path)
    p.add_argument("--timeout-seconds", type=int, default=240)
    p.add_argument("--write", action="store_true")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    if args.self_test:
        payload = self_test()
    else:
        repo = args.repo_root.resolve() if args.repo_root else find_repo_root(Path.cwd())
        payload = build(repo, max(30, int(args.timeout_seconds)), bool(args.write))
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json or args.self_test else render_md(payload), end="" if not args.json and not args.self_test else "\n")
    return 0 if payload.get("status") == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())

# END_OF_SCRIPT_MARKER
