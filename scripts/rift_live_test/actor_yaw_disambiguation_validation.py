from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HEX_RE = re.compile(r"^0[xX][0-9a-fA-F]+$")


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower = value.strip().lower()
        if lower == "true":
            return True
        if lower == "false":
            return False
    return None


def as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_hex(value: Any) -> str:
    return str(value or "").strip().lower()


def is_hex(value: Any) -> bool:
    return bool(HEX_RE.match(str(value or "").strip()))


def same_hex(left: Any, right: Any) -> bool:
    return is_hex(left) and is_hex(right) and normalize_hex(left) == normalize_hex(right)


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), None
    except Exception as exc:  # noqa: BLE001 - this is a validator boundary.
        return None, str(exc)


def make_check(name: str, passed: bool, *, severity: str, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "detail": detail,
    }


def build_disambiguation_validation(
    *,
    packet_file: Path,
    lead_file: Path,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    packet_file = packet_file.resolve()
    lead_file = lead_file.resolve()
    repo_root = repo_root.resolve() if repo_root else packet_file.parents[2]

    checks: list[dict[str, str]] = []
    issues: list[str] = []

    def add_check(name: str, passed: bool, *, severity: str, detail: str, issue: str | None = None) -> None:
        checks.append(make_check(name, passed, severity=severity, detail=detail))
        if not passed and severity == "blocker":
            issues.append(issue or name)

    packet: dict[str, Any] | None = None
    lead: dict[str, Any] | None = None

    if not packet_file.exists():
        add_check(
            "packet-present",
            False,
            severity="blocker",
            detail=f"Disambiguation packet was not found: {packet_file}",
            issue="missing_packet",
        )
    else:
        packet, error = load_json(packet_file)
        add_check(
            "packet-json",
            packet is not None,
            severity="blocker",
            detail=error or "Disambiguation packet is valid JSON.",
            issue="invalid_packet_json",
        )

    if not lead_file.exists():
        add_check(
            "lead-file-present",
            False,
            severity="blocker",
            detail=f"Behavior-backed lead file was not found: {lead_file}",
            issue="missing_lead_file",
        )
    else:
        lead, error = load_json(lead_file)
        add_check(
            "lead-file-json",
            lead is not None,
            severity="blocker",
            detail=error or "Behavior-backed lead file is valid JSON.",
            issue="invalid_lead_json",
        )

    if packet is None:
        return finish_validation(
            repo_root=repo_root,
            packet_file=packet_file,
            lead_file=lead_file,
            checks=checks,
            issues=issues,
        )

    single_survivor = as_dict(packet.get("singleSurvivor"))
    promoted_lead = as_dict(packet.get("promotedLead"))
    current_control = as_dict(packet.get("currentPromotedLeadControl"))
    promotion_validation = as_dict(packet.get("promotionValidation"))
    candidate_results = as_list(packet.get("candidateResults"))

    survivor_key = str(single_survivor.get("candidateKey") or "")
    survivor_source = single_survivor.get("sourceAddress")
    survivor_offset = single_survivor.get("basisForwardOffset")

    add_check(
        "packet-mode",
        packet.get("schemaVersion") == 1 and packet.get("mode") == "current-actor-yaw-disambiguation",
        severity="blocker",
        detail="Packet must use schemaVersion=1 and mode=current-actor-yaw-disambiguation.",
        issue="bad_packet_mode",
    )
    add_check(
        "promoted-status",
        packet.get("status") == "single-survivor-promoted-to-behavior-backed-lead"
        and packet.get("decision") == "promoted-and-validation-passed",
        severity="blocker",
        detail="Packet must represent a completed, validated promotion.",
        issue="promotion_not_completed",
    )
    add_check(
        "safety-boundary",
        packet.get("noCheatEngine") is True
        and packet.get("movementSent") is False
        and packet.get("writesToRiftScan") is False
        and packet.get("savedVariablesUsedAsLiveTruth") is False,
        severity="blocker",
        detail="Packet must preserve no-CE/no-movement/no-RiftScan-write/no-SavedVariables-live-truth boundaries.",
        issue="unsafe_boundary",
    )
    add_check(
        "movement-still-blocked",
        packet.get("movementAllowed") is False,
        severity="blocker",
        detail="Actor-yaw promotion must not authorize movement.",
        issue="movement_allowed_by_yaw_packet",
    )
    add_check(
        "promotion-applied",
        packet.get("promotionAllowed") is True and packet.get("actorFacingPromotionApplied") is True,
        severity="blocker",
        detail="Packet must record that actor-facing promotion was applied.",
        issue="promotion_not_marked_applied",
    )
    add_check(
        "target-present",
        packet.get("processName") == "rift_x64"
        and (as_int(packet.get("processId")) or 0) > 0
        and is_hex(packet.get("targetWindowHandle")),
        severity="blocker",
        detail="Packet target must include rift_x64, positive processId, and hex targetWindowHandle.",
        issue="bad_target",
    )
    add_check(
        "single-survivor-present",
        bool(survivor_key)
        and is_hex(survivor_source)
        and is_hex(survivor_offset)
        and packet.get("truthLikeSurvivorCount") == 1,
        severity="blocker",
        detail="Packet must identify exactly one truth-like survivor.",
        issue="bad_single_survivor",
    )
    add_check(
        "single-survivor-truth-like",
        single_survivor.get("status") == "truth-like"
        and single_survivor.get("truthLike") is True
        and single_survivor.get("candidateResponsive") is True
        and single_survivor.get("playerStayedMostlyStill") is True
        and as_int(single_survivor.get("truthLikeCandidateCount")) == 1
        and as_int(single_survivor.get("reversibleCandidateCount")) == 1
        and as_float(single_survivor.get("playerCoordDeltaMagnitude")) == 0.0,
        severity="blocker",
        detail="Single survivor must be truth-like, reversible, responsive, still, and zero coord drift.",
        issue="survivor_not_truth_like",
    )

    truth_like_results = [result for result in candidate_results if as_dict(result).get("truthLike") is True]
    add_check(
        "candidate-results-single-truth-like",
        len(truth_like_results) == 1 and as_dict(truth_like_results[0]).get("candidateKey") == survivor_key,
        severity="blocker",
        detail="candidateResults must contain exactly one truth-like result and it must match singleSurvivor.",
        issue="candidate_results_ambiguous",
    )

    add_check(
        "promoted-lead-matches-survivor",
        promoted_lead.get("candidateKey") == survivor_key
        and same_hex(promoted_lead.get("sourceAddress"), survivor_source)
        and same_hex(promoted_lead.get("basisForwardOffset"), survivor_offset)
        and promoted_lead.get("status") == "preferred-solved-lead"
        and promoted_lead.get("operationalStatus") == "behavior-backed-lead",
        severity="blocker",
        detail="Packet promotedLead must match the single survivor and be behavior-backed.",
        issue="promoted_lead_mismatch",
    )

    add_check(
        "previous-lead-control-rejected",
        bool(current_control)
        and current_control.get("truthLike") is False
        and as_int(current_control.get("reversibleCandidateCount")) == 0,
        severity="blocker",
        detail="Previous promoted lead control must be recorded as rejected/non-reversible.",
        issue="previous_lead_not_rejected",
    )

    for section_name, allowed_modes in {
        "readPlayerOrientation": {"live-behavior-backed-lead"},
        "captureActorOrientation": {"behavior-backed-lead", "live-behavior-backed-lead"},
    }.items():
        section = as_dict(promotion_validation.get(section_name))
        add_check(
            f"{section_name}-validation",
            section.get("status") == "passed"
            and section.get("liveMemoryRead") is True
            and same_hex(section.get("selectedSourceAddress"), survivor_source)
            and same_hex(section.get("basisForwardOffset"), survivor_offset)
            and str(section.get("resolutionMode") or "") in allowed_modes,
            severity="blocker",
            detail=f"{section_name} must pass from a live memory read of the promoted source.",
            issue=f"{section_name}_validation_failed",
        )

    proof_suite = as_dict(promotion_validation.get("actorFacingProofSuite"))
    targeted_tests = as_dict(promotion_validation.get("targetedDotnetTests"))
    add_check(
        "actor-facing-proof-suite-passed",
        proof_suite.get("status") == "passed",
        severity="blocker",
        detail="Actor-facing proof suite must pass after promotion.",
        issue="proof_suite_not_passed",
    )
    add_check(
        "targeted-dotnet-tests-passed",
        targeted_tests.get("status") == "passed" and as_int(targeted_tests.get("failedCount")) == 0,
        severity="blocker",
        detail="Targeted C# validation must pass after promotion.",
        issue="targeted_tests_not_passed",
    )

    if lead is not None:
        lead_diagnostics = as_dict(lead.get("CandidateDiagnostics"))
        previous_lead = as_dict(lead.get("PreviousLead"))
        rejected_controls = as_list(lead_diagnostics.get("RejectedControls"))

        add_check(
            "lead-file-matches-packet",
            same_hex(lead.get("SourceAddress"), survivor_source)
            and same_hex(lead.get("BasisForwardOffset"), survivor_offset)
            and lead.get("Status") == "preferred-solved-lead"
            and lead.get("OperationalStatus") == "behavior-backed-lead"
            and lead_diagnostics.get("CandidateKey") == survivor_key
            and as_int(lead_diagnostics.get("ProcessId")) == as_int(packet.get("processId"))
            and same_hex(lead_diagnostics.get("TargetWindowHandle"), packet.get("targetWindowHandle")),
            severity="blocker",
            detail="Behavior-backed lead file must match packet survivor, target, and candidate key.",
            issue="lead_file_mismatch",
        )
        add_check(
            "lead-preserves-rejected-controls",
            len(rejected_controls) > 0
            and all(as_dict(control).get("truthLike") is False for control in rejected_controls)
            and any(
                same_hex(as_dict(control).get("sourceAddress"), current_control.get("sourceAddress"))
                and same_hex(as_dict(control).get("basisForwardOffset"), current_control.get("basisForwardOffset"))
                for control in rejected_controls
            )
            and same_hex(previous_lead.get("SourceAddress"), current_control.get("sourceAddress"))
            and same_hex(previous_lead.get("BasisForwardOffset"), current_control.get("basisForwardOffset")),
            severity="blocker",
            detail="Lead file must preserve rejected controls and the previous lead replacement record.",
            issue="lead_rejected_controls_missing",
        )

    return finish_validation(
        repo_root=repo_root,
        packet_file=packet_file,
        lead_file=lead_file,
        checks=checks,
        issues=issues,
    )


def finish_validation(
    *,
    repo_root: Path,
    packet_file: Path,
    lead_file: Path,
    checks: list[dict[str, str]],
    issues: list[str],
) -> dict[str, Any]:
    status = "fail" if any(check["status"] == "fail" and check["severity"] == "blocker" for check in checks) else "pass"
    return {
        "schemaVersion": 1,
        "mode": "current-actor-yaw-disambiguation-validation",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "repoRoot": str(repo_root),
        "packetFile": str(packet_file),
        "leadFile": str(lead_file),
        "movementAllowed": False,
        "checks": checks,
        "issues": issues,
    }


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_arg_parser() -> argparse.ArgumentParser:
    repo_root = default_repo_root()
    parser = argparse.ArgumentParser(description="Validate current actor-yaw disambiguation promotion truth.")
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
    parser.add_argument("--json", action="store_true", help="Emit JSON result.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = build_disambiguation_validation(
        packet_file=args.packet_file,
        lead_file=args.lead_file,
        repo_root=args.repo_root,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    elif result["status"] == "pass":
        print(f"Current actor-yaw disambiguation validation passed: {result['packetFile']}")
    else:
        print(f"Current actor-yaw disambiguation validation failed: {result['packetFile']}", file=sys.stderr)
        for issue in result["issues"]:
            print(f" - {issue}", file=sys.stderr)
    return 0 if result["status"] == "pass" else 1
