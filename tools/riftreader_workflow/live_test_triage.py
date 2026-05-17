#!/usr/bin/env python3
"""Offline live-test/discovery triage for RiftReader workflow status."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .common import repo_rel as rel
    from .common import safety_flags, timestamped_output_dir, utc_iso
    from .status_packet import build_status_packet, find_repo_root, render_markdown as render_status_markdown
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import repo_rel as rel
    from riftreader_workflow.common import safety_flags, timestamped_output_dir, utc_iso
    from riftreader_workflow.status_packet import build_status_packet, find_repo_root, render_markdown as render_status_markdown


DEFAULT_OUTPUT_DIR = Path(".riftreader-local") / "live-test-triage"


def _first_blocked_stage(stage_timings: Any) -> dict[str, Any] | None:
    if not isinstance(stage_timings, list):
        return None
    for stage in reversed(stage_timings):
        if not isinstance(stage, dict):
            continue
        status = str(stage.get("status") or "").lower()
        if status in {"blocked", "failed", "error"}:
            return stage
    return None


def _live_target_next_action(live_verdict: str, live_target: dict[str, Any]) -> str:
    live_pids = live_target.get("livePids")
    artifact_pid = live_target.get("artifactPid")
    artifact_hwnd = live_target.get("artifactHwnd")
    if live_verdict == "artifact-pid-stale":
        return (
            f"Live RIFT is running with PID(s) {live_pids}, but the current proof artifact points "
            f"at historical PID {artifact_pid} / HWND {artifact_hwnd}. "
            "Keep movement blocked, do not reuse stale proof, and run safe current-target "
            "reacquisition/status refresh before ProofOnly or movement."
        )
    if live_verdict == "artifact-pid-missing":
        return (
            f"Live RIFT target status is visible with PID(s) {live_pids}, but the proof artifact has no "
            "target PID. Keep movement blocked and run safe current-target status/reacquisition before "
            "ProofOnly or movement."
        )
    return (
        "No live rift_x64 process is currently visible. Keep movement blocked, load RIFT into the "
        "character/world when available, then rerun no-input status triage."
    )


def classify_packet(packet: dict[str, Any]) -> dict[str, Any]:
    blockers = [str(item) for item in packet.get("blockers") or []]
    errors = [str(item) for item in packet.get("errors") or []]
    current_proof = ((packet.get("currentProof") or {}).get("summary") or {})
    current_truth = ((packet.get("currentTruth") or {}).get("summary") or {})
    coord_status = packet.get("coordinateRecoveryStatus") or {}
    live_target = coord_status.get("liveTarget") if isinstance(coord_status.get("liveTarget"), dict) else {}
    proof = coord_status.get("proof") if isinstance(coord_status.get("proof"), dict) else {}
    recovery_profile = coord_status.get("recoveryProfile") if isinstance(coord_status.get("recoveryProfile"), dict) else {}
    movement_gate = current_truth.get("movementGate") if isinstance(current_truth.get("movementGate"), dict) else {}
    latest_validation = current_proof.get("latestValidation") if isinstance(current_proof.get("latestValidation"), dict) else {}
    latest_proofonly = current_proof.get("latestProofOnly") if isinstance(current_proof.get("latestProofOnly"), dict) else {}
    proof_status = str(current_proof.get("status") or proof.get("status") or "")
    live_verdict = str(live_target.get("verdict") or "")
    blocked_stage = _first_blocked_stage(recovery_profile.get("stageTimings"))

    if errors:
        return {
            "status": "failed",
            "failedStage": "status-packet",
            "blockerCategory": "status-packet-error",
            "reason": "; ".join(errors),
            "nextRecommendedAction": "Fix the status packet error before live-test triage.",
        }
    if live_verdict in {"no-live-process", "artifact-pid-stale", "artifact-pid-missing"}:
        return {
            "status": "blocked",
            "failedStage": "live-target",
            "blockerCategory": live_verdict,
            "reason": "; ".join(item for item in blockers if "live-target" in item or "artifact-target" in item)
            or f"Live target verdict is {live_verdict}.",
            "nextRecommendedAction": _live_target_next_action(live_verdict, live_target),
        }
    if proof_status.startswith("blocked-target-drift"):
        return {
            "status": "blocked",
            "failedStage": "proof-target-drift",
            "blockerCategory": "blocked-target-drift",
            "reason": "Current proof pointer belongs to a stale target epoch.",
            "nextRecommendedAction": "Invalidate stale proof as historical only, then run current-PID family recovery after fresh API/runtime truth exists.",
        }
    if movement_gate.get("allowed") is False:
        return {
            "status": "blocked",
            "failedStage": "movement-gate",
            "blockerCategory": str(movement_gate.get("status") or "movement-not-allowed"),
            "reason": str(movement_gate.get("reason") or "Movement gate is not open."),
            "nextRecommendedAction": "Do not run movement. Complete current proof/readback/ProofOnly requirements first.",
        }
    validation_status = str(latest_validation.get("status") or "")
    if validation_status.startswith("blocked") or validation_status.startswith("failed"):
        return {
            "status": "blocked",
            "failedStage": "proof-validation",
            "blockerCategory": validation_status,
            "reason": "Latest proof validation is blocked or failed.",
            "nextRecommendedAction": "Inspect current proof readback and rerun the relevant proof validation helper.",
        }
    proofonly_status = str(latest_proofonly.get("status") or "")
    if proofonly_status.startswith("blocked") or proofonly_status.startswith("failed"):
        return {
            "status": "blocked",
            "failedStage": "proofonly",
            "blockerCategory": proofonly_status,
            "reason": "Latest ProofOnly run is blocked or failed.",
            "nextRecommendedAction": "Rerun same-target ProofOnly only after target and coordinate freshness gates pass.",
        }
    if blocked_stage:
        return {
            "status": "blocked",
            "failedStage": str(blocked_stage.get("phase") or blocked_stage.get("label") or "recovery-stage"),
            "blockerCategory": str(blocked_stage.get("status") or "blocked"),
            "reason": f"Latest blocked recovery stage: {blocked_stage.get('label')}",
            "nextRecommendedAction": "Inspect the referenced recovery stage artifact before expanding live work.",
        }
    if blockers:
        return {
            "status": "blocked",
            "failedStage": "unknown-blocker",
            "blockerCategory": "generic-blocker",
            "reason": "; ".join(blockers),
            "nextRecommendedAction": str(packet.get("nextRecommendedAction") or "Resolve blockers before live work."),
        }
    return {
        "status": "passed",
        "failedStage": None,
        "blockerCategory": None,
        "reason": "No blocker detected by offline triage.",
        "nextRecommendedAction": "Proceed only with the next explicitly approved, gate-appropriate validation step.",
    }


def build_triage(repo_root: Path, *, write_status_packet: bool = False) -> dict[str, Any]:
    packet = build_status_packet(
        repo_root,
        commit_count=20,
        ref_count=10,
        run_coordinate_status=True,
        check_opencode=False,
        collect_git_state=True,
    )
    classification = classify_packet(packet)
    result = {
        "schemaVersion": 1,
        "kind": "riftreader-live-test-triage",
        "generatedAtUtc": utc_iso(),
        "status": classification["status"],
        "failedStage": classification["failedStage"],
        "blockerCategory": classification["blockerCategory"],
        "reason": classification["reason"],
        "blockers": packet.get("blockers") or [],
        "warnings": packet.get("warnings") or [],
        "errors": packet.get("errors") or [],
        "evidence": {
            "latestHandoff": (packet.get("latestHandoff") or {}).get("path"),
            "currentProof": (packet.get("currentProof") or {}).get("path"),
            "currentTruth": ((packet.get("currentTruth") or {}).get("jsonPath")),
            "coordinateLiveTarget": ((packet.get("coordinateRecoveryStatus") or {}).get("liveTarget") or {}),
            "movementGate": (((packet.get("currentTruth") or {}).get("summary") or {}).get("movementGate") or {}),
        },
        "nextRecommendedAction": classification["nextRecommendedAction"],
        "statusPacket": packet if write_status_packet else None,
        "artifacts": {},
        "safety": safety_flags(),
    }
    return result


def render_markdown(triage: dict[str, Any]) -> str:
    evidence = triage.get("evidence") or {}
    live_target = evidence.get("coordinateLiveTarget") or {}
    movement_gate = evidence.get("movementGate") or {}
    lines = [
        "# RiftReader Live-Test Fast-Lane Triage",
        "",
        f"- Generated UTC: `{triage.get('generatedAtUtc')}`",
        f"- Status: `{triage.get('status')}`",
        f"- Failed stage: `{triage.get('failedStage')}`",
        f"- Blocker category: `{triage.get('blockerCategory')}`",
        f"- Reason: {triage.get('reason')}",
        f"- Live target verdict: `{live_target.get('verdict')}`; live PIDs `{live_target.get('livePids')}`",
        f"- Movement gate: `{movement_gate.get('allowed')}` / `{movement_gate.get('status')}`",
        "",
        "## Evidence",
        "",
        f"- Latest handoff: `{evidence.get('latestHandoff')}`",
        f"- Current proof: `{evidence.get('currentProof')}`",
        f"- Current truth: `{evidence.get('currentTruth')}`",
        "",
        "## Blockers",
        "",
    ]
    for blocker in triage.get("blockers") or ["none"]:
        lines.append(f"- `{blocker}`")
    lines.extend(["", "## Next recommended action", "", str(triage.get("nextRecommendedAction") or "none")])
    lines.extend(["", "## Safety", "", "| Flag | Value |", "|---|---:|"])
    for key, value in (triage.get("safety") or {}).items():
        lines.append(f"| `{key}` | `{value}` |")
    artifacts = triage.get("artifacts") or {}
    if artifacts:
        lines.extend(["", "## Artifacts", ""])
        for key, value in artifacts.items():
            lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines)


def write_outputs(repo_root: Path, triage: dict[str, Any], output_root: Path | None = None) -> dict[str, str]:
    base = output_root if output_root else repo_root / DEFAULT_OUTPUT_DIR
    if not base.is_absolute():
        base = repo_root / base
    output_dir = timestamped_output_dir(base)
    json_path = output_dir / "live-test-triage-summary.json"
    md_path = output_dir / "LIVE_TEST_TRIAGE.md"
    status_md_path = output_dir / "STATUS_PACKET.md"
    triage["artifacts"] = {
        "outputDir": rel(repo_root, output_dir),
        "summaryJson": rel(repo_root, json_path),
        "summaryMarkdown": rel(repo_root, md_path),
    }
    packet = triage.get("statusPacket")
    if isinstance(packet, dict):
        triage["artifacts"]["statusPacketMarkdown"] = rel(repo_root, status_md_path)
        status_md_path.write_text(render_status_markdown(packet) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(triage, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(triage) + "\n", encoding="utf-8")
    return triage["artifacts"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify the current RiftReader live-test blocker from offline artifacts.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--include-status-packet", action="store_true")
    parser.add_argument("--output-dir", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    triage = build_triage(repo_root, write_status_packet=args.include_status_packet)
    if args.write:
        write_outputs(repo_root, triage, Path(args.output_dir) if args.output_dir else None)
    if args.json:
        print(json.dumps(triage, indent=2))
    else:
        print(render_markdown(triage))
    if triage["status"] == "failed":
        return 1
    if triage["status"] == "blocked":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
