from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json_object(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return document


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def latest_file(paths: Sequence[Path]) -> Path | None:
    existing = [path for path in paths if path.exists() and path.is_file()]
    if not existing:
        return None
    return max(existing, key=lambda path: (path.stat().st_mtime, str(path)))


def path_text(path: Path | None, repo_root: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def normalize_hwnd(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        return f"0x{int(str(value), 0):X}"
    except ValueError:
        return str(value)


def target_mismatches(expected: Mapping[str, Any], observed: Mapping[str, Any]) -> list[str]:
    mismatches: list[str] = []
    expected_pid = expected.get("pid")
    observed_pid = observed.get("pid") or observed.get("processId")
    if expected_pid is not None and observed_pid is not None and int(expected_pid) != int(observed_pid):
        mismatches.append(f"pid:{expected_pid}!={observed_pid}")
    expected_hwnd = normalize_hwnd(expected.get("hwnd"))
    observed_hwnd = normalize_hwnd(observed.get("hwnd") or observed.get("targetWindowHandle"))
    if expected_hwnd and observed_hwnd and expected_hwnd != observed_hwnd:
        mismatches.append(f"hwnd:{expected_hwnd}!={observed_hwnd}")
    expected_process = str(expected.get("processName") or "").lower().removesuffix(".exe")
    observed_process = str(observed.get("processName") or "").lower().removesuffix(".exe")
    if expected_process and observed_process and expected_process != observed_process:
        mismatches.append(f"processName:{expected_process}!={observed_process}")
    return mismatches


def latest_reference_watchdog(repo_root: Path) -> Path | None:
    return latest_file(list((repo_root / "scripts" / "captures").glob("reference-freshness-watchdog-*/summary.json")))


def latest_milestone_review(repo_root: Path) -> Path | None:
    return latest_file(list((repo_root / "scripts" / "captures").glob("riftscan-milestone-review-*.json")))


def summarize_reference_watchdog(path: Path | None, repo_root: Path, expected_target: Mapping[str, Any]) -> dict[str, Any]:
    if path is None:
        return {
            "path": None,
            "status": "missing",
            "verdict": "missing-reference-watchdog",
            "usable": False,
            "blockers": ["reference-watchdog-summary-not-found"],
            "warnings": [],
        }
    try:
        document = load_json_object(path)
    except Exception as exc:
        return {
            "path": path_text(path, repo_root),
            "status": "read-failed",
            "verdict": "reference-watchdog-read-failed",
            "usable": False,
            "blockers": [f"reference-watchdog-read-failed:{type(exc).__name__}:{exc}"],
            "warnings": [],
        }
    mismatches = target_mismatches(expected_target, safe_dict(document.get("target")))
    blockers = list(safe_list(document.get("blockers")))
    blockers.extend(f"reference-watchdog-target-mismatch:{mismatch}" for mismatch in mismatches)
    return {
        "path": path_text(path, repo_root),
        "status": document.get("status"),
        "verdict": document.get("verdict"),
        "usable": document.get("status") == "passed" and not blockers,
        "generatedAtUtc": document.get("generatedAtUtc"),
        "target": document.get("target"),
        "blockers": blockers,
        "warnings": safe_list(document.get("warnings")),
    }


def summarize_milestone_review(path: Path | None, repo_root: Path, expected_target: Mapping[str, Any]) -> dict[str, Any]:
    if path is None:
        return {
            "path": None,
            "status": "missing",
            "readOnlyProofAllowed": False,
            "movementAllowed": False,
            "selectedCandidatePresent": False,
            "blockers": ["milestone-review-summary-not-found"],
            "warnings": [],
        }
    try:
        document = load_json_object(path)
    except Exception as exc:
        return {
            "path": path_text(path, repo_root),
            "status": "read-failed",
            "readOnlyProofAllowed": False,
            "movementAllowed": False,
            "selectedCandidatePresent": False,
            "blockers": [f"milestone-review-read-failed:{type(exc).__name__}:{exc}"],
            "warnings": [],
        }
    requested_target = safe_dict(document.get("requestedTarget"))
    mismatches = target_mismatches(expected_target, requested_target)
    strategy = safe_dict(document.get("strategy"))
    selected = safe_dict(document.get("selectedCandidate"))
    blockers = [f"milestone-target-mismatch:{mismatch}" for mismatch in mismatches]
    if document.get("status") == "blocked":
        blockers.append("milestone-review-blocked")
    if not selected.get("candidateFile"):
        blockers.append("milestone-selected-candidate-missing")
    return {
        "path": path_text(path, repo_root),
        "status": document.get("status"),
        "decision": strategy.get("decision"),
        "readOnlyProofAllowed": strategy.get("readOnlyProofAllowedByReview") is True,
        "movementAllowed": strategy.get("movementAllowedByReview") is True,
        "selectedCandidatePresent": bool(selected.get("candidateFile")),
        "selectedCandidate": {
            "source": selected.get("source"),
            "candidateId": selected.get("candidateId"),
            "candidateFile": selected.get("candidateFile"),
        },
        "generatedAtUtc": document.get("generatedAtUtc"),
        "target": requested_target,
        "blockers": blockers,
        "warnings": safe_list(document.get("issues")),
    }


def readiness_decision(reference: Mapping[str, Any], milestone: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    blockers.extend(f"reference:{blocker}" for blocker in safe_list(reference.get("blockers")))
    blockers.extend(f"milestone:{blocker}" for blocker in safe_list(milestone.get("blockers")))
    warnings.extend(f"reference:{warning}" for warning in safe_list(reference.get("warnings")))
    warnings.extend(f"milestone:{warning}" for warning in safe_list(milestone.get("warnings")))

    reference_ready = reference.get("usable") is True
    milestone_ready = milestone.get("readOnlyProofAllowed") is True and milestone.get("selectedCandidatePresent") is True
    if not reference_ready and "reference:not-fresh-reference" not in blockers:
        blockers.append("reference:not-fresh-reference")
    if not milestone_ready and "milestone:not-ready-for-read-only-proof" not in blockers:
        blockers.append("milestone:not-ready-for-read-only-proof")

    if reference_ready and milestone_ready and not blockers:
        return {
            "status": "passed",
            "verdict": "ready-for-read-only-proof",
            "readOnlyProofAllowed": True,
            "movementAllowed": False,
            "blockers": [],
            "warnings": warnings,
            "nextAction": "Run same-target read-only proof/readback, then rerun ProofOnly before movement.",
        }
    return {
        "status": "blocked",
        "verdict": "blocked-coordinate-proof-readiness",
        "readOnlyProofAllowed": False,
        "movementAllowed": False,
        "blockers": blockers,
        "warnings": warnings,
        "nextAction": "Fix fresh reference and milestone blockers before proof/readback or movement.",
    }


def markdown_summary(summary: Mapping[str, Any]) -> str:
    decision = safe_dict(summary.get("decision"))
    reference = safe_dict(summary.get("referenceWatchdog"))
    milestone = safe_dict(summary.get("milestoneReview"))
    lines = [
        "# Coordinate proof readiness gate",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Read-only proof allowed: `{str(decision.get('readOnlyProofAllowed')).lower()}`",
        f"- Movement allowed: `{str(decision.get('movementAllowed')).lower()}`",
        "",
        "## Inputs",
        "",
        "| Input | Status | Verdict/Decision | Artifact |",
        "|---|---|---|---|",
        f"| Reference watchdog | `{reference.get('status')}` | `{reference.get('verdict')}` | `{reference.get('path')}` |",
        f"| Milestone review | `{milestone.get('status')}` | `{milestone.get('decision')}` | `{milestone.get('path')}` |",
        "",
        "## Safety",
        "",
        "- No movement/input sent.",
        "- No CE/x64dbg used.",
        "- No target memory read or written by this gate.",
        "- Candidate-only until fresh reference and readback proof pass.",
    ]
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{blocker}`" for blocker in safe_list(summary.get("blockers")))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in safe_list(summary.get("warnings")))
    return "\n".join(lines).rstrip() + "\n"


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    output_root = args.output_root or repo_root / "scripts" / "captures" / f"coordinate-proof-readiness-gate-{utc_stamp()}"
    output_root = output_root.resolve()
    expected_target = {
        "processName": args.process_name,
        "pid": args.target_pid,
        "hwnd": args.target_hwnd,
    }
    reference_path = args.reference_watchdog_summary or latest_reference_watchdog(repo_root)
    milestone_path = args.milestone_review_summary or latest_milestone_review(repo_root)
    reference = summarize_reference_watchdog(reference_path, repo_root, expected_target)
    milestone = summarize_milestone_review(milestone_path, repo_root, expected_target)
    decision = readiness_decision(reference, milestone)
    summary_json = output_root / "summary.json"
    summary_md = output_root / "summary.md"
    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "coordinate-proof-readiness-gate",
        "generatedAtUtc": utc_iso(),
        "status": decision["status"],
        "verdict": decision["verdict"],
        "target": expected_target,
        "referenceWatchdog": reference,
        "milestoneReview": milestone,
        "decision": decision,
        "blockers": decision["blockers"],
        "warnings": decision["warnings"],
        "artifacts": {
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "x64dbgAttached": False,
            "cheatEngineUsed": False,
            "processMemoryReadByThisHelper": False,
            "targetMemoryWritten": False,
            "savedVariablesUsedAsLiveTruth": False,
            "candidateOnly": decision["status"] != "passed",
            "promotionEligible": False,
        },
        "next": {
            "recommendedAction": decision["nextAction"],
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(summary_json, summary)
    write_text_atomic(summary_md, markdown_summary(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fail-closed gate before coordinate proof/readback or movement.")
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--reference-watchdog-summary", type=Path)
    parser.add_argument("--milestone-review-summary", type=Path)
    parser.add_argument("--target-pid", type=int, required=True)
    parser.add_argument("--target-hwnd", required=True)
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = build_summary(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "verdict": summary["verdict"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "readOnlyProofAllowed": summary["decision"]["readOnlyProofAllowed"],
                    "movementAllowed": summary["decision"]["movementAllowed"],
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']}")
        print(f"verdict={summary['verdict']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        if summary["blockers"]:
            print("blockers:")
            for blocker in summary["blockers"]:
                print(f"  - {blocker}")
    return 0 if summary["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
