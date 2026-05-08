from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .riftscan_coordination import (
    DEFAULT_RIFTSCAN_ROOT,
    build_coordination_plan,
    is_relative_to,
    normalize_hwnd,
    read_json_file,
    utc_from_mtime,
)


def summarize_path(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "lastWriteUtc": utc_from_mtime(path) if path.exists() else None,
        "sizeBytes": path.stat().st_size if path.exists() and path.is_file() else None,
    }


def newest_file(root: Path, pattern: str) -> Path | None:
    if not root.exists():
        return None
    files = sorted(
        (path for path in root.glob(pattern) if path.is_file()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


def summarize_optional_path(path: Path | None) -> dict[str, Any] | None:
    return summarize_path(path) if path else None


def summarize_live_test_pointer(path: Path) -> dict[str, Any]:
    summary = summarize_path(path)
    if not path.exists():
        return summary

    try:
        data = read_json_file(path)
    except Exception as exc:  # noqa: BLE001 - artifact packets should report unreadable state.
        summary["status"] = "unreadable"
        summary["issue"] = f"latest_live_test_pointer_unreadable:{type(exc).__name__}:{exc}"
        return summary

    run_summary_file = data.get("runSummaryFile")
    run_progress_file = data.get("runProgressFile")
    run_directory = data.get("runDirectory")
    summary.update(
        {
            "status": data.get("status"),
            "profileName": data.get("profileName"),
            "generatedAtUtc": data.get("generatedAtUtc"),
            "runSummaryFile": summarize_optional_path(Path(run_summary_file))
            if run_summary_file
            else None,
            "runProgressFile": summarize_optional_path(Path(run_progress_file))
            if run_progress_file
            else None,
            "runDirectory": str(run_directory) if run_directory else None,
            "runHealth": data.get("runHealth") if isinstance(data.get("runHealth"), dict) else None,
        }
    )
    return summary


def build_riftreader_artifacts(repo_root: Path) -> dict[str, Any]:
    captures = repo_root / "scripts" / "captures"
    handoffs = repo_root / "docs" / "handoffs"
    latest_handoff = newest_file(handoffs, "*.md")
    latest_coordination = newest_file(captures, "riftscan-coordination-plan-*.json")
    latest_feedback = newest_file(captures, "riftscan-feedback-packet-*.json")
    latest_live_test = newest_file(captures, "live-test-*.json")
    latest_live_test_pointer = captures / "latest-live-test-run.json"

    return {
        "currentTruth": summarize_path(repo_root / "docs" / "recovery" / "current-truth.md"),
        "currentProofPointer": summarize_path(
            repo_root / "docs" / "recovery" / "current-proof-anchor-readback.json"
        ),
        "currentCoordProofBlocker": summarize_path(
            repo_root / "docs" / "recovery" / "current-coord-proof-blocker.json"
        ),
        "turnKeyProfileEvidence": summarize_path(
            repo_root / "docs" / "recovery" / "turn-key-profile-evidence.json"
        ),
        "latestHandoff": summarize_optional_path(latest_handoff),
        "latestCoordinationPlan": summarize_optional_path(latest_coordination),
        "latestFeedbackPacket": summarize_optional_path(latest_feedback),
        "latestLiveTestPointer": summarize_live_test_pointer(latest_live_test_pointer),
        "latestLiveTestCapture": summarize_optional_path(latest_live_test),
    }


def feedback_status(coordination_plan: dict[str, Any]) -> str:
    status = str(coordination_plan.get("status") or "").lower()
    selected = coordination_plan.get("selectedCandidate")
    has_candidate = bool(isinstance(selected, dict) and selected.get("candidateFile"))
    if status == "ok" and has_candidate:
        return "ready-for-read-only-proof"
    if status == "needs-review" and has_candidate:
        return "needs-review-before-proof"
    return "blocked"


def build_feedback_recommendations(coordination_plan: dict[str, Any]) -> list[dict[str, str]]:
    selected = coordination_plan.get("selectedCandidate")
    source = selected.get("source") if isinstance(selected, dict) else None
    recommendations = [
        {
            "action": "Re-run target preflight before any live action.",
            "why": "PID/HWND proof is session-specific and can drift after handoffs or client restarts.",
        },
        {
            "action": "Use the selected candidate only through RiftReader-owned wrappers.",
            "why": "The read-only boundary forbids creating or mutating RiftScan sessions/reports from this lane.",
        },
        {
            "action": "Keep CandidateFile explicit for readback/proof-pose commands.",
            "why": "Explicit candidate files avoid accidental provider-side capture paths.",
        },
        {
            "action": "Treat provider offline consumer rows as evidence, not live authorization.",
            "why": "RiftReader must re-prove anchors for the current PID/HWND before movement decisions.",
        },
        {
            "action": "Block movement on any target mismatch.",
            "why": "A stale proof pointer or wrong window can turn valid coordinates into unsafe live input.",
        },
    ]
    if source == "current-proof-pointer":
        recommendations.insert(
            0,
            {
                "action": "Prefer the current proof pointer candidate for this target.",
                "why": "It is already tied to RiftReader's current movement-grade pointer metadata.",
            },
        )
    elif source == "latest-riftscan-match-file":
        recommendations.insert(
            0,
            {
                "action": "Run proof-pose/readback before promotion.",
                "why": "The selected provider match file is only read-only candidate evidence for this target.",
            },
        )
    return recommendations


def build_feedback_packet(
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
    coordination_plan = build_coordination_plan(
        repo_root=repo_root,
        riftscan_root=riftscan_root,
        current_proof_pointer=current_proof_pointer,
        candidate_consumer_summary=candidate_consumer_summary,
        process_id=process_id,
        target_window_handle=target_window_handle,
        process_name=process_name,
        limit=limit,
    )
    status = feedback_status(coordination_plan)
    forbidden = [
        "movement",
        "input",
        "live_capture",
        "process_attach",
        "memory_read",
        "offset_validation",
        "riftreader_command",
        "reloadui",
        "riftscan_write",
    ]

    return {
        "schemaVersion": 1,
        "mode": "riftscan-riftreader-feedback-packet",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "coordinationStatus": coordination_plan.get("status"),
        "issues": coordination_plan.get("issues", []),
        "repoRoot": str(repo_root),
        "riftScanBoundary": {
            "root": str(riftscan_root),
            "mode": "read-only",
            "writeAllowed": False,
            "noCheatEngine": True,
            "movementSent": False,
            "feedbackWritesToRiftScan": False,
        },
        "requestedTarget": {
            "processName": process_name,
            "processId": process_id,
            "targetWindowHandle": normalize_hwnd(target_window_handle),
        },
        "selectedCandidate": coordination_plan.get("selectedCandidate"),
        "currentProofPointer": coordination_plan.get("currentProofPointer"),
        "riftScanCandidateConsumer": coordination_plan.get("riftScanCandidateConsumer"),
        "pointerMatchFile": coordination_plan.get("pointerMatchFile"),
        "latestRiftScanMatchFiles": coordination_plan.get("latestRiftScanMatchFiles", []),
        "riftReaderArtifacts": build_riftreader_artifacts(repo_root),
        "allowedDownstreamUses": [
            "offline_review",
            "report_generation",
            "provider_feedback_review",
            "riftreader_readonly_proof_planning",
        ],
        "forbiddenDownstreamUses": forbidden,
        "recommendations": build_feedback_recommendations(coordination_plan),
        "coordinationNotes": coordination_plan.get("coordinationNotes", []),
        "majorMilestoneReview": coordination_plan.get("majorMilestoneReview", []),
        "nextCommands": coordination_plan.get("nextCommands", {}),
    }


def write_feedback_packet(packet: dict[str, Any], output_file: Path, *, riftscan_root: Path) -> None:
    if is_relative_to(output_file, riftscan_root):
        raise ValueError(f"Refusing to write feedback output inside RiftScan: {output_file}")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")


def default_summary_file(repo_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return repo_root / "scripts" / "captures" / f"riftscan-feedback-packet-{stamp}.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a RiftReader-owned read-only feedback packet for RiftScan coordination."
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
        help="Write the feedback packet under RiftReader scripts/captures.",
    )
    parser.add_argument("--summary-file", type=Path, help="Explicit feedback packet output file.")
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
    packet = build_feedback_packet(
        repo_root=repo_root,
        riftscan_root=riftscan_root,
        current_proof_pointer=pointer,
        candidate_consumer_summary=args.candidate_consumer_summary,
        process_id=args.pid,
        target_window_handle=args.hwnd,
        process_name=args.process_name,
        limit=args.limit,
    )
    if args.write_summary or args.summary_file:
        output_file = args.summary_file or default_summary_file(repo_root)
        packet["summaryFile"] = str(output_file)
        write_feedback_packet(packet, output_file, riftscan_root=riftscan_root)

    if args.compact_json:
        print(json.dumps(packet, separators=(",", ":")))
    else:
        print(json.dumps(packet, indent=2))
    return 0 if packet["status"] != "blocked" else 2


if __name__ == "__main__":
    sys.exit(main())
