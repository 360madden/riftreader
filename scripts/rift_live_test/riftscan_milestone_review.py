from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .riftscan_coordination import (
    DEFAULT_RIFTSCAN_ROOT,
    coerce_int,
    is_relative_to,
    normalize_hwnd,
    read_json_file,
)
from .riftscan_feedback import build_feedback_packet


def check_item(
    name: str,
    passed: bool,
    *,
    severity: str,
    detail: str,
) -> dict[str, str]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "detail": detail,
    }


def has_pointer_mismatch(issues: list[Any]) -> bool:
    return any(str(issue).startswith("pointer_") for issue in issues)


def build_checks(packet: dict[str, Any]) -> list[dict[str, str]]:
    boundary = packet.get("riftScanBoundary") if isinstance(packet.get("riftScanBoundary"), dict) else {}
    selected = packet.get("selectedCandidate") if isinstance(packet.get("selectedCandidate"), dict) else {}
    artifacts = packet.get("riftReaderArtifacts") if isinstance(packet.get("riftReaderArtifacts"), dict) else {}
    latest_live = (
        artifacts.get("latestLiveTestPointer")
        if isinstance(artifacts.get("latestLiveTestPointer"), dict)
        else {}
    )
    run_health = latest_live.get("runHealth") if isinstance(latest_live.get("runHealth"), dict) else {}
    issues = packet.get("issues") if isinstance(packet.get("issues"), list) else []
    consumer = (
        packet.get("riftScanCandidateConsumer")
        if isinstance(packet.get("riftScanCandidateConsumer"), dict)
        else {}
    )
    consumer_safety = consumer.get("safety") if isinstance(consumer.get("safety"), dict) else {}

    selected_file = selected.get("candidateFile")
    selected_source = selected.get("source")
    latest_status = str(latest_live.get("status") or "")

    return [
        check_item(
            "riftscan-read-only-boundary",
            boundary.get("writeAllowed") is False and boundary.get("feedbackWritesToRiftScan") is False,
            severity="blocker",
            detail="RiftScan provider writes must remain disabled.",
        ),
        check_item(
            "no-cheat-engine-boundary",
            boundary.get("noCheatEngine") is True,
            severity="blocker",
            detail="No CE path is allowed for this lane.",
        ),
        check_item(
            "no-movement-sent",
            boundary.get("movementSent") is False,
            severity="blocker",
            detail="Milestone review must not send movement/input.",
        ),
        check_item(
            "selected-candidate-present",
            bool(selected_file),
            severity="blocker",
            detail=f"Selected candidate source: {selected_source or 'none'}.",
        ),
        check_item(
            "target-pointer-match",
            not has_pointer_mismatch(issues),
            severity="blocker",
            detail="Current proof pointer target metadata must match requested PID/process/HWND.",
        ),
        check_item(
            "latest-proofonly-pointer",
            latest_status == "passed-proof-only",
            severity="warning",
            detail=f"Latest live-test pointer status: {latest_status or 'missing'}.",
        ),
        check_item(
            "latest-proof-no-ce",
            run_health.get("noCheatEngine") is True if run_health else False,
            severity="warning",
            detail="Latest live-test pointer should record noCheatEngine=true.",
        ),
        check_item(
            "latest-proof-no-movement",
            run_health.get("movementSent") is False if run_health else False,
            severity="warning",
            detail="Latest ProofOnly pointer should record movementSent=false.",
        ),
        check_item(
            "provider-consumer-offline-safe",
            consumer_safety.get("liveActionAuthorized") is False
            and consumer_safety.get("movementOrInputSent") is False
            and consumer_safety.get("processAttachOrMemoryReadStarted") is False,
            severity="warning",
            detail="Provider consumer summary should remain offline-only evidence.",
        ),
    ]


def review_status(checks: list[dict[str, str]], packet: dict[str, Any]) -> str:
    if any(check["status"] == "fail" and check["severity"] == "blocker" for check in checks):
        return "blocked"
    packet_status = str(packet.get("status") or "blocked")
    if packet_status == "ready-for-read-only-proof":
        return "ready-for-read-only-proof"
    return packet_status


def build_strategy(review_status_value: str, packet: dict[str, Any]) -> dict[str, Any]:
    selected = packet.get("selectedCandidate") if isinstance(packet.get("selectedCandidate"), dict) else {}
    if review_status_value == "blocked":
        return {
            "decision": "block",
            "movementAllowedByReview": False,
            "readOnlyProofAllowedByReview": False,
            "nextAction": "Fix blocker issues or refresh the exact target proof pointer before discovery expands.",
            "why": "A milestone blocker means current RiftScan evidence cannot be safely consumed for this target.",
        }

    if review_status_value == "ready-for-read-only-proof":
        return {
            "decision": "proceed-read-only-proof-first",
            "movementAllowedByReview": False,
            "readOnlyProofAllowedByReview": True,
            "nextAction": "Use the selected candidate with explicit -CandidateFile for read-only proof/readback, then rerun fresh ProofOnly before any movement.",
            "why": f"Selected source {selected.get('source')} has no current target mismatch and preserves the read-only/no-CE boundary.",
        }

    return {
        "decision": "review-before-proof",
        "movementAllowedByReview": False,
        "readOnlyProofAllowedByReview": False,
        "nextAction": "Review candidate/target mismatch before running proof or movement.",
        "why": f"Feedback packet status is {packet.get('status')}.",
    }


def build_recommended_actions(review_status_value: str) -> list[dict[str, str]]:
    common = [
        {
            "action": "Re-run this milestone review after every handoff, commit, push, or live target change.",
            "why": "It re-checks the exact PID/HWND, selected RiftScan evidence, no-CE boundary, and no-write boundary.",
        },
        {
            "action": "Keep RiftScan-derived readbacks on explicit -CandidateFile paths.",
            "why": "This avoids accidental provider-side sessions/reports while RiftScan is read-only.",
        },
        {
            "action": "Treat this review as a strategy gate, not movement permission.",
            "why": "Movement still requires a fresh proof/preflight immediately before the live movement slice.",
        },
    ]
    if review_status_value == "ready-for-read-only-proof":
        return [
            {
                "action": "Run the read-only proof-pose/readback command from nextCommands if more evidence is needed.",
                "why": "The selected candidate is ready for RiftReader-owned proof without writing RiftScan.",
            },
            *common,
        ]
    return [
        {
            "action": "Resolve blocker checks before expanding discovery scope.",
            "why": "Target mismatch or missing candidate evidence can make later proof misleading.",
        },
        *common,
    ]


def _first_present(mapping: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = mapping.get(name)
        if value not in (None, ""):
            return value
    return None


def _target_from_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    process_id = coerce_int(_first_present(mapping, "processId", "ProcessId", "pid"))
    target_window_handle = _first_present(
        mapping,
        "targetWindowHandle",
        "TargetWindowHandle",
        "hwnd",
    )
    process_name = _first_present(mapping, "processName", "ProcessName")
    return {
        "processId": process_id,
        "targetWindowHandle": normalize_hwnd(target_window_handle),
        "processName": process_name,
    }


def infer_latest_live_target(repo_root: Path) -> dict[str, Any]:
    """Infer the current target from the latest live-test pointer/run summary.

    The docs/recovery proof pointer can legitimately lag after a client restart.
    This review is normally run after live milestones, so defaulting to the most
    recent live-test target prevents stale PID/HWND recommendations.
    """
    pointer_path = repo_root / "scripts" / "captures" / "latest-live-test-run.json"
    result: dict[str, Any] = {
        "source": "latest-live-test-run",
        "path": str(pointer_path),
        "exists": pointer_path.exists(),
        "processId": None,
        "targetWindowHandle": None,
        "processName": None,
        "issues": [],
    }
    if not pointer_path.exists():
        result["issues"].append("latest_live_test_pointer_missing")
        return result

    try:
        pointer = read_json_file(pointer_path)
    except Exception as exc:  # noqa: BLE001 - review should report stale/unreadable target state.
        result["issues"].append(f"latest_live_test_pointer_unreadable:{type(exc).__name__}:{exc}")
        return result

    candidate_sources: list[tuple[str, dict[str, Any]]] = [("latest-live-test-pointer", pointer)]
    for key in ("runSummaryFile", "runProgressFile"):
        file_value = pointer.get(key)
        if not file_value:
            continue
        file_path = Path(str(file_value))
        try:
            candidate_sources.append((key, read_json_file(file_path)))
        except Exception as exc:  # noqa: BLE001 - keep going with other sources.
            result["issues"].append(f"{key}_target_unreadable:{type(exc).__name__}:{exc}")

    for source_name, data in candidate_sources:
        target = _target_from_mapping(data)
        if target["processId"] is not None:
            result["processId"] = target["processId"]
        if target["targetWindowHandle"]:
            result["targetWindowHandle"] = target["targetWindowHandle"]
        if target["processName"]:
            result["processName"] = target["processName"]

        if result["processId"] is not None and result["targetWindowHandle"]:
            result["source"] = source_name
            break

    if result["processId"] is None:
        result["issues"].append("latest_live_test_target_pid_missing")
    if not result["targetWindowHandle"]:
        result["issues"].append("latest_live_test_target_hwnd_missing")
    return result


def build_milestone_review(
    *,
    repo_root: Path,
    riftscan_root: Path,
    current_proof_pointer: Path,
    candidate_consumer_summary: Path | None = None,
    process_id: int | None = None,
    target_window_handle: str | None = None,
    process_name: str | None = "rift_x64",
    limit: int = 8,
) -> dict[str, Any]:
    inferred_target = infer_latest_live_target(repo_root)
    effective_process_id = process_id
    if effective_process_id is None:
        effective_process_id = coerce_int(inferred_target.get("processId"))
    effective_target_window_handle = target_window_handle
    if not effective_target_window_handle:
        effective_target_window_handle = inferred_target.get("targetWindowHandle")
    effective_process_name = process_name
    if not effective_process_name:
        effective_process_name = inferred_target.get("processName") or "rift_x64"

    packet = build_feedback_packet(
        repo_root=repo_root,
        riftscan_root=riftscan_root,
        current_proof_pointer=current_proof_pointer,
        candidate_consumer_summary=candidate_consumer_summary,
        process_id=effective_process_id,
        target_window_handle=effective_target_window_handle,
        process_name=effective_process_name,
        limit=limit,
    )
    checks = build_checks(packet)
    status = review_status(checks, packet)
    strategy = build_strategy(status, packet)

    return {
        "schemaVersion": 1,
        "mode": "riftscan-riftreader-major-milestone-review",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "strategy": strategy,
        "checks": checks,
        "issues": packet.get("issues", []),
        "repoRoot": str(repo_root),
        "riftScanBoundary": packet.get("riftScanBoundary"),
        "requestedTarget": {
            "processName": effective_process_name,
            "processId": effective_process_id,
            "targetWindowHandle": normalize_hwnd(effective_target_window_handle),
        },
        "targetInference": {
            **inferred_target,
            "explicitProcessId": process_id,
            "explicitTargetWindowHandle": normalize_hwnd(target_window_handle),
            "explicitProcessName": process_name,
        },
        "selectedCandidate": packet.get("selectedCandidate"),
        "currentProofPointer": packet.get("currentProofPointer"),
        "riftReaderArtifacts": packet.get("riftReaderArtifacts"),
        "forbiddenDownstreamUses": packet.get("forbiddenDownstreamUses", []),
        "recommendedActions": build_recommended_actions(status),
        "nextCommands": packet.get("nextCommands", {}),
    }


def write_review(review: dict[str, Any], output_file: Path, *, riftscan_root: Path) -> None:
    if is_relative_to(output_file, riftscan_root):
        raise ValueError(f"Refusing to write milestone review output inside RiftScan: {output_file}")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")


def markdown_for_review(review: dict[str, Any]) -> str:
    selected = review.get("selectedCandidate") if isinstance(review.get("selectedCandidate"), dict) else {}
    strategy = review.get("strategy") if isinstance(review.get("strategy"), dict) else {}
    target = review.get("requestedTarget") if isinstance(review.get("requestedTarget"), dict) else {}
    checks = review.get("checks") if isinstance(review.get("checks"), list) else []
    actions = review.get("recommendedActions") if isinstance(review.get("recommendedActions"), list) else []
    lines = [
        "# RiftScan/RiftReader Major Milestone Review",
        "",
        "| Fact | Value |",
        "|---|---|",
        f"| Status | `{review.get('status')}` |",
        f"| Decision | `{strategy.get('decision')}` |",
        f"| Target | `{target.get('processName')}` PID `{target.get('processId')}`, HWND `{target.get('targetWindowHandle')}` |",
        f"| Selected candidate | `{selected.get('candidateId')}` from `{selected.get('source')}` |",
        f"| Candidate file | `{selected.get('candidateFile')}` |",
        f"| Movement allowed by review | `{strategy.get('movementAllowedByReview')}` |",
        "",
        "## Checks",
        "",
        "| Check | Status | Severity | Detail |",
        "|---|---|---|---|",
    ]
    for check in checks:
        lines.append(
            f"| `{check.get('name')}` | `{check.get('status')}` | `{check.get('severity')}` | {check.get('detail')} |"
        )
    lines.extend(
        [
            "",
            "## Recommended next actions",
            "",
            "| # | Action | Why |",
            "|---:|---|---|",
        ]
    )
    for index, action in enumerate(actions, start=1):
        lines.append(f"| {index} | {action.get('action')} | {action.get('why')} |")
    lines.append("")
    return "\n".join(lines)


def write_markdown_review(review: dict[str, Any], output_file: Path, *, riftscan_root: Path) -> None:
    if is_relative_to(output_file, riftscan_root):
        raise ValueError(f"Refusing to write milestone review Markdown inside RiftScan: {output_file}")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(markdown_for_review(review), encoding="utf-8")


def default_summary_file(repo_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return repo_root / "scripts" / "captures" / f"riftscan-milestone-review-{stamp}.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a RiftReader-owned RiftScan strategy checkpoint for major milestones."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="RiftReader repo root.",
    )
    parser.add_argument(
        "--riftscan-root",
        type=Path,
        default=DEFAULT_RIFTSCAN_ROOT,
        help="RiftScan provider repo root. This tool reads it but never writes it.",
    )
    parser.add_argument(
        "--current-proof-pointer",
        type=Path,
        help="Current proof pointer JSON. Defaults to docs/recovery/current-proof-anchor-readback.json.",
    )
    parser.add_argument(
        "--candidate-consumer-summary",
        type=Path,
        help="RiftScan candidate-ledger consumer summary. Defaults to the provider current handoff path.",
    )
    parser.add_argument("--pid", type=int, help="Expected current RIFT process id.")
    parser.add_argument("--hwnd", help="Expected current RIFT window handle.")
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument(
        "--write-summary",
        action="store_true",
        help="Write the milestone review JSON under RiftReader scripts/captures.",
    )
    parser.add_argument("--summary-file", type=Path, help="Explicit milestone review JSON output file.")
    parser.add_argument(
        "--write-markdown",
        action="store_true",
        help="Write a Markdown companion next to the JSON summary.",
    )
    parser.add_argument("--markdown-file", type=Path, help="Explicit milestone review Markdown output file.")
    parser.add_argument(
        "--compact-json",
        action="store_true",
        help="Emit a single-line JSON object to stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    riftscan_root = args.riftscan_root.resolve()
    pointer = args.current_proof_pointer or (
        repo_root / "docs" / "recovery" / "current-proof-anchor-readback.json"
    )
    review = build_milestone_review(
        repo_root=repo_root,
        riftscan_root=riftscan_root,
        current_proof_pointer=pointer,
        candidate_consumer_summary=args.candidate_consumer_summary,
        process_id=args.pid,
        target_window_handle=args.hwnd,
        process_name=args.process_name,
        limit=args.limit,
    )
    output_file = args.summary_file or default_summary_file(repo_root)
    if args.write_summary or args.summary_file or args.write_markdown or args.markdown_file:
        review["summaryFile"] = str(output_file)
        write_review(review, output_file, riftscan_root=riftscan_root)

    if args.write_markdown or args.markdown_file:
        markdown_file = args.markdown_file or output_file.with_suffix(".md")
        review["markdownFile"] = str(markdown_file)
        write_markdown_review(review, markdown_file, riftscan_root=riftscan_root)

    if args.compact_json:
        print(json.dumps(review, separators=(",", ":")))
    else:
        print(json.dumps(review, indent=2))
    return 0 if review["status"] != "blocked" else 2


if __name__ == "__main__":
    sys.exit(main())
