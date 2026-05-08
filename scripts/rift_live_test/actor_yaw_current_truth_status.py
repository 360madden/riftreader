from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .actor_yaw_disambiguation_validation import (
    as_dict,
    as_int,
    build_disambiguation_validation,
    load_json,
)


def failed_checks(validation: dict[str, Any]) -> list[dict[str, Any]]:
    checks = validation.get("checks") if isinstance(validation.get("checks"), list) else []
    return [
        check
        for check in checks
        if isinstance(check, dict)
        and check.get("status") == "fail"
        and check.get("severity") == "blocker"
    ]


def compact_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidateKey": candidate.get("candidateKey"),
        "sourceAddress": candidate.get("sourceAddress"),
        "basisForwardOffset": candidate.get("basisForwardOffset"),
        "status": candidate.get("status"),
        "truthLike": candidate.get("truthLike"),
        "candidateResponsive": candidate.get("candidateResponsive"),
        "reversibleCandidateCount": candidate.get("reversibleCandidateCount"),
        "playerCoordDeltaMagnitude": candidate.get("playerCoordDeltaMagnitude"),
    }


def build_current_truth_status(
    *,
    packet_file: Path,
    lead_file: Path,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    packet_file = packet_file.resolve()
    lead_file = lead_file.resolve()
    repo_root = repo_root.resolve() if repo_root else packet_file.parents[2]

    validation = build_disambiguation_validation(
        packet_file=packet_file,
        lead_file=lead_file,
        repo_root=repo_root,
    )
    packet, packet_error = load_json(packet_file) if packet_file.exists() else (None, "packet file missing")
    lead, lead_error = load_json(lead_file) if lead_file.exists() else (None, "lead file missing")
    packet = packet or {}
    lead = lead or {}

    lead_diagnostics = as_dict(lead.get("CandidateDiagnostics"))
    promoted_lead = as_dict(packet.get("promotedLead"))
    single_survivor = as_dict(packet.get("singleSurvivor"))
    previous_control = as_dict(packet.get("currentPromotedLeadControl"))
    promotion_validation = as_dict(packet.get("promotionValidation"))
    read_orientation = as_dict(promotion_validation.get("readPlayerOrientation"))
    capture_orientation = as_dict(promotion_validation.get("captureActorOrientation"))

    validation_passed = validation.get("status") == "pass"
    status = "current" if validation_passed else "blocked"
    decision = "use-promoted-actor-yaw-lead" if validation_passed else "repair-current-actor-yaw-truth"

    current_lead = {
        "sourceAddress": lead.get("SourceAddress") or promoted_lead.get("sourceAddress") or single_survivor.get("sourceAddress"),
        "basisForwardOffset": lead.get("BasisForwardOffset")
        or promoted_lead.get("basisForwardOffset")
        or single_survivor.get("basisForwardOffset"),
        "candidateKey": lead_diagnostics.get("CandidateKey")
        or promoted_lead.get("candidateKey")
        or single_survivor.get("candidateKey"),
        "status": lead.get("Status") or promoted_lead.get("status"),
        "operationalStatus": lead.get("OperationalStatus") or promoted_lead.get("operationalStatus"),
        "validatedAtUtc": lead.get("ValidatedAtUtc") or promoted_lead.get("validatedAtUtc"),
        "validationArtifact": lead_diagnostics.get("ValidationArtifact") or promoted_lead.get("validationArtifact"),
    }

    failed = failed_checks(validation)
    issues = validation.get("issues") if isinstance(validation.get("issues"), list) else []

    return {
        "schemaVersion": 1,
        "mode": "actor-yaw-current-truth-status",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "decision": decision,
        "repoRoot": str(repo_root),
        "target": {
            "processName": packet.get("processName"),
            "processId": as_int(packet.get("processId")),
            "targetWindowHandle": packet.get("targetWindowHandle"),
        },
        "currentActorYawLead": current_lead,
        "singleSurvivor": compact_candidate(single_survivor),
        "previousLeadControl": compact_candidate(previous_control),
        "safety": {
            "noCheatEngine": packet.get("noCheatEngine"),
            "movementSent": packet.get("movementSent"),
            "movementAllowed": False,
            "writesToRiftScan": packet.get("writesToRiftScan"),
            "savedVariablesUsedAsLiveTruth": packet.get("savedVariablesUsedAsLiveTruth"),
        },
        "promotionValidation": {
            "actorFacingProofSuiteStatus": as_dict(promotion_validation.get("actorFacingProofSuite")).get("status"),
            "targetedDotnetTestsStatus": as_dict(promotion_validation.get("targetedDotnetTests")).get("status"),
            "readPlayerOrientation": {
                "status": read_orientation.get("status"),
                "resolutionMode": read_orientation.get("resolutionMode"),
                "selectedSourceAddress": read_orientation.get("selectedSourceAddress"),
                "basisForwardOffset": read_orientation.get("basisForwardOffset"),
                "liveMemoryRead": read_orientation.get("liveMemoryRead"),
                "file": read_orientation.get("file"),
            },
            "captureActorOrientation": {
                "status": capture_orientation.get("status"),
                "resolutionMode": capture_orientation.get("resolutionMode"),
                "selectedSourceAddress": capture_orientation.get("selectedSourceAddress"),
                "basisForwardOffset": capture_orientation.get("basisForwardOffset"),
                "liveMemoryRead": capture_orientation.get("liveMemoryRead"),
                "file": capture_orientation.get("file"),
            },
        },
        "validation": {
            "status": validation.get("status"),
            "issueCount": len(issues),
            "failedBlockerCount": len(failed),
            "issues": issues,
            "failedChecks": failed,
        },
        "artifacts": {
            "packetFile": str(packet_file),
            "leadFile": str(lead_file),
            "packetLoadError": packet_error,
            "leadLoadError": lead_error,
        },
        "nextActions": next_actions(validation_passed),
    }


def next_actions(validation_passed: bool) -> list[dict[str, str]]:
    if validation_passed:
        return [
            {
                "action": "Use this as actor-facing truth only after rebinding the same live PID/HWND.",
                "why": "The promoted source is session-bound to the recorded process target.",
            },
            {
                "action": "Run a fresh ProofOnly gate before any movement or navigation attempt.",
                "why": "Actor-yaw truth does not authorize coordinate-driven movement.",
            },
            {
                "action": "Keep auto-turn blocked until a separate turn backend is promoted.",
                "why": "Facing truth is not an input-delivery proof.",
            },
        ]
    return [
        {
            "action": "Fix the failed disambiguation validation issues before using actor-facing truth.",
            "why": "A blocked status means the lead file and recovery packet no longer prove the same truth.",
        },
        {
            "action": "Re-run isolated actor-yaw disambiguation if the live target changed.",
            "why": "The current source address is session-bound and may not survive restart.",
        },
    ]


def markdown_for_status(status: dict[str, Any]) -> str:
    target = as_dict(status.get("target"))
    lead = as_dict(status.get("currentActorYawLead"))
    safety = as_dict(status.get("safety"))
    validation = as_dict(status.get("validation"))
    previous = as_dict(status.get("previousLeadControl"))
    actions = status.get("nextActions") if isinstance(status.get("nextActions"), list) else []

    lines = [
        "# Actor-Yaw Current Truth Status",
        "",
        "| Fact | Value |",
        "|---|---|",
        f"| Status | `{status.get('status')}` |",
        f"| Decision | `{status.get('decision')}` |",
        f"| Target | `{target.get('processName')}` PID `{target.get('processId')}`, HWND `{target.get('targetWindowHandle')}` |",
        f"| Current lead | `{lead.get('sourceAddress')} @ {lead.get('basisForwardOffset')}` |",
        f"| Candidate key | `{lead.get('candidateKey')}` |",
        f"| Previous rejected control | `{previous.get('sourceAddress')} @ {previous.get('basisForwardOffset')}` / `{previous.get('status')}` |",
        f"| Validation | `{validation.get('status')}`; issues `{validation.get('issueCount')}` |",
        f"| Movement allowed | `{str(safety.get('movementAllowed')).lower()}` |",
        f"| No Cheat Engine | `{str(safety.get('noCheatEngine')).lower()}` |",
        f"| SavedVariables live truth | `{str(safety.get('savedVariablesUsedAsLiveTruth')).lower()}` |",
        f"| RiftScan writes | `{str(safety.get('writesToRiftScan')).lower()}` |",
        "",
        "## Next actions",
        "",
        "| # | Action | Why |",
        "|---:|---|---|",
    ]
    for index, action in enumerate(actions, start=1):
        item = as_dict(action)
        lines.append(f"| {index} | {item.get('action')} | {item.get('why')} |")
    return "\n".join(lines) + "\n"


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_arg_parser() -> argparse.ArgumentParser:
    repo_root = default_repo_root()
    parser = argparse.ArgumentParser(description="Report current promoted actor-yaw truth status.")
    parser.add_argument(
        "--packet-file",
        type=Path,
        default=repo_root / "docs" / "recovery" / "current-actor-yaw-disambiguation.json",
        help="Path to current-actor-yaw-disambiguation.json.",
    )
    parser.add_argument(
        "--lead-file",
        type=Path,
        default=repo_root / "scripts" / "actor-facing-behavior-backed-lead.json",
        help="Path to actor-facing-behavior-backed-lead.json.",
    )
    parser.add_argument("--repo-root", type=Path, default=repo_root, help="RiftReader repo root.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    status = build_current_truth_status(
        packet_file=args.packet_file,
        lead_file=args.lead_file,
        repo_root=args.repo_root,
    )
    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print(markdown_for_status(status), end="")
    return 0 if status["status"] == "current" else 1
