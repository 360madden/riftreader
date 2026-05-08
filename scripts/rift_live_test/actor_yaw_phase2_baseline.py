from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .actor_yaw_disambiguation_validation import as_dict, normalize_hex
from .reports import write_json, write_text_atomic
from .target import verify_target


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def powershell_process_info(process_id: int) -> dict[str, Any]:
    command = [
        "powershell",
        "-NoLogo",
        "-NoProfile",
        "-Command",
        (
            "$p=Get-Process -Id {0} -ErrorAction Stop; "
            "[pscustomobject]@{{"
            "processName=$p.ProcessName;"
            "processId=$p.Id;"
            "targetWindowHandle=('0x{{0:X}}' -f $p.MainWindowHandle);"
            "mainWindowTitle=$p.MainWindowTitle;"
            "responding=$p.Responding;"
            "processStartTimeUtc=$p.StartTime.ToUniversalTime().ToString('O')"
            "}} | ConvertTo-Json -Compress"
        ).format(process_id),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Failed to query live process {process_id}: {completed.stderr or completed.stdout}"
        )
    data = json.loads(completed.stdout)
    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected process query output: {completed.stdout}")
    return data


def compact_basis_signature(capture_file: Path) -> dict[str, Any]:
    if not capture_file.exists():
        return {"status": "missing", "file": str(capture_file)}
    capture = load_json(capture_file)
    reader = as_dict(capture.get("ReaderOrientation"))
    live_source = as_dict(reader.get("LiveSourceSample"))
    basis = (
        as_dict(reader.get("ResolvedBasis"))
        or as_dict(reader.get("PreferredBasis"))
        or as_dict(live_source.get("ResolvedBasis"))
        or as_dict(capture.get("PreferredBasis"))
    )
    estimate = as_dict(reader.get("PreferredEstimate")) or as_dict(capture.get("PreferredEstimate"))
    return {
        "status": "captured" if basis else "basis-missing",
        "file": str(capture_file),
        "basisName": basis.get("Name"),
        "forward": basis.get("Forward"),
        "up": basis.get("Up"),
        "right": basis.get("Right"),
        "determinant": basis.get("Determinant"),
        "isOrthonormal": basis.get("IsOrthonormal"),
        "preferredYawDegrees": estimate.get("YawDegrees"),
        "preferredPitchDegrees": estimate.get("PitchDegrees"),
        "preferredMagnitude": estimate.get("Magnitude"),
    }


def normalize_path_string(value: Any) -> str | None:
    if not value:
        return None
    return str(Path(str(value)))


def build_phase2_baseline(
    *,
    repo_root: Path,
    process_id: int | None = None,
    target_window_handle: str | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    disambiguation_file = repo_root / "docs" / "recovery" / "current-actor-yaw-disambiguation.json"
    lead_file = repo_root / "scripts" / "actor-facing-behavior-backed-lead.json"
    yaw_pointer_file = repo_root / "scripts" / "captures" / "latest-actor-yaw-readback-smoke.json"
    live_pointer_file = repo_root / "scripts" / "captures" / "latest-live-test-run.json"

    disambiguation = load_json(disambiguation_file)
    lead = load_json(lead_file)
    yaw_pointer = load_json(yaw_pointer_file)
    live_pointer = load_json(live_pointer_file)
    proof_summary_file = Path(str(live_pointer.get("runSummaryFile")))
    proof_summary = load_json(proof_summary_file)

    lead_diagnostics = as_dict(lead.get("CandidateDiagnostics"))
    survivor = as_dict(disambiguation.get("singleSurvivor"))
    promoted = as_dict(disambiguation.get("promotedLead"))
    yaw_read = as_dict(yaw_pointer.get("readPlayerOrientation"))
    yaw_capture = as_dict(yaw_pointer.get("captureActorOrientation"))

    effective_process_id = int(
        process_id
        or lead_diagnostics.get("ProcessId")
        or disambiguation.get("processId")
        or as_dict(yaw_pointer.get("target")).get("processId")
    )
    process_info = powershell_process_info(effective_process_id)
    effective_hwnd = (
        target_window_handle
        or str(lead_diagnostics.get("TargetWindowHandle") or "")
        or str(disambiguation.get("targetWindowHandle") or "")
        or str(as_dict(yaw_pointer.get("target")).get("targetWindowHandle") or "")
    )
    target_verification = verify_target(effective_process_id, effective_hwnd, "rift_x64")
    if not target_verification.get("valid"):
        raise ValueError(f"Exact target verification failed: {target_verification}")

    source_address = str(lead.get("SourceAddress") or promoted.get("sourceAddress") or survivor.get("sourceAddress"))
    basis_offset = str(
        lead.get("BasisForwardOffset") or promoted.get("basisForwardOffset") or survivor.get("basisForwardOffset")
    )
    candidate_key = str(lead_diagnostics.get("CandidateKey") or survivor.get("candidateKey"))
    yaw_capture_file = Path(str(yaw_capture.get("file"))) if yaw_capture.get("file") else Path()

    proof_coord = as_dict(proof_summary.get("currentCoordinate"))
    packet = {
        "schemaVersion": 1,
        "mode": "current-actor-yaw-restart-check",
        "lastUpdatedUtc": utc_now(),
        "status": "phase2-pre-restart-baseline-ready",
        "sessionBound": True,
        "target": {
            "processName": "rift_x64",
            "processId": effective_process_id,
            "targetWindowHandle": effective_hwnd,
            "processStartTimeUtc": process_info.get("processStartTimeUtc"),
            "mainWindowTitle": process_info.get("mainWindowTitle"),
            "responding": process_info.get("responding"),
            "verification": target_verification,
            "character": "Atank",
            "location": "Sanctum of the Vigil",
        },
        "actorFacing": {
            "status": "behavior-backed-current-session",
            "sourceAddress": source_address,
            "basisForwardOffset": basis_offset,
            "candidateKey": candidate_key,
            "yawFormula": lead.get("CanonicalYawFormula") or "atan2(forwardZ, forwardX)",
            "pitchFormula": lead.get("CanonicalPitchFormula")
            or "atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))",
            "duplicateAgreementStrong": False,
            "currentYawDegrees": yaw_capture.get("preferredYawDegrees") or yaw_read.get("preferredYawDegrees"),
            "currentPitchDegrees": yaw_capture.get("preferredPitchDegrees") or yaw_read.get("preferredPitchDegrees"),
            "basisSignature": compact_basis_signature(yaw_capture_file) if yaw_capture_file else {},
            "validation": {
                "method": "isolated-disambiguation-survivor-plus-no-input-readback",
                "validationArtifact": normalize_path_string(
                    lead_diagnostics.get("ValidationArtifact") or promoted.get("validationArtifact") or survivor.get("file")
                ),
                "disambiguationArtifact": str(disambiguation_file),
                "readbackSmokeSummary": normalize_path_string(yaw_pointer.get("summaryFile")),
                "yawDeltaDegrees": survivor.get("yawDeltaDegrees"),
                "reverseYawDeltaDegrees": survivor.get("reverseYawDeltaDegrees"),
                "truthLike": survivor.get("truthLike"),
                "candidateResponsive": survivor.get("candidateResponsive"),
                "reversibleCandidateCount": survivor.get("reversibleCandidateCount"),
                "reversibleCycleCount": survivor.get("reversibleCycleCount"),
                "playerCoordDeltaMagnitude": survivor.get("playerCoordDeltaMagnitude"),
                "readPlayerOrientationStatus": yaw_read.get("status"),
                "captureActorOrientationStatus": yaw_capture.get("status"),
                "readPlayerSelectedSourceAddress": yaw_read.get("selectedSourceAddress"),
                "captureSelectedSourceAddress": yaw_capture.get("selectedSourceAddress"),
                "readPlayerBasisForwardOffset": yaw_read.get("basisForwardOffset"),
                "captureBasisForwardOffset": yaw_capture.get("basisForwardOffset"),
                "movementSent": as_dict(yaw_pointer.get("safety")).get("movementSent"),
                "noCheatEngine": as_dict(yaw_pointer.get("safety")).get("noCheatEngine"),
                "writesToRiftScan": as_dict(yaw_pointer.get("safety")).get("writesToRiftScan"),
                "savedVariablesUsedAsLiveTruth": as_dict(yaw_pointer.get("safety")).get(
                    "savedVariablesUsedAsLiveTruth"
                ),
            },
            "leadFile": str(lead_file),
        },
        "coordinate": {
            "status": "proof-grade-before-restart",
            "latestReadMode": "ProofOnly",
            "latestProofOnlyStatus": proof_summary.get("status"),
            "proofOnlyRunSummary": normalize_path_string(live_pointer.get("runSummaryFile")),
            "proofOnlyRunDirectory": normalize_path_string(live_pointer.get("runDirectory")),
            "proofReadbackSummary": normalize_path_string(proof_summary.get("summaryFile")),
            "sample": {
                "x": proof_coord.get("x"),
                "y": proof_coord.get("y"),
                "z": proof_coord.get("z"),
                "recordedAtUtc": proof_coord.get("recordedAtUtc"),
            },
            "movementSent": proof_summary.get("movementSent"),
            "movementAttempted": proof_summary.get("movementAttempted"),
            "noCheatEngine": proof_summary.get("noCheatEngine"),
            "savedVariablesUsedAsLiveTruth": proof_summary.get("savedVariablesUsedAsLiveTruth"),
        },
        "movementGate": {
            "activeMovementAllowed": False,
            "reason": "Phase 2 is restart/rebind actor-yaw recovery only; movement and auto-turn remain blocked.",
        },
        "phase2": {
            "readyForRestartRebind": True,
            "scope": "actor-yaw-restart-rebind-only",
            "fallbackOrder": [
                "Rebind exact new PID/HWND and run actor_yaw_readback_smoke.py first.",
                "If direct readback fails, search near the prior behavior-backed source/candidate structure.",
                "If narrow rebind fails, rerun orientation candidate search with ledger penalties.",
                "Promote only after controlled turn-only yaw validation and zero proof-coordinate movement.",
                "Keep movement and auto-turn blocked until separate gates pass.",
            ],
        },
        "safety": {
            "noCheatEngine": True,
            "movementSent": False,
            "movementAttempted": False,
            "movementAllowed": False,
            "writesToRiftScan": False,
            "savedVariablesUsedAsLiveTruth": False,
        },
        "artifacts": {
            "disambiguationPacket": str(disambiguation_file),
            "leadFile": str(lead_file),
            "latestActorYawReadbackPointer": str(yaw_pointer_file),
            "latestActorYawReadbackSummary": normalize_path_string(yaw_pointer.get("summaryFile")),
            "latestProofOnlyPointer": str(live_pointer_file),
            "latestProofOnlyRunSummary": normalize_path_string(live_pointer.get("runSummaryFile")),
            "latestProofOnlyReadbackSummary": normalize_path_string(proof_summary.get("summaryFile")),
        },
    }
    return packet


def markdown_for_packet(packet: dict[str, Any]) -> str:
    target = as_dict(packet.get("target"))
    actor = as_dict(packet.get("actorFacing"))
    validation = as_dict(actor.get("validation"))
    coordinate = as_dict(packet.get("coordinate"))
    artifacts = as_dict(packet.get("artifacts"))
    fallback = as_dict(packet.get("phase2")).get("fallbackOrder") or []
    lines = [
        "# Actor-Yaw Phase 2 Pre-Restart Baseline",
        "",
        "| Fact | Value |",
        "|---|---|",
        f"| Status | `{packet.get('status')}` |",
        f"| Target | `{target.get('processName')}` PID `{target.get('processId')}`, HWND `{target.get('targetWindowHandle')}` |",
        f"| Process start UTC | `{target.get('processStartTimeUtc')}` |",
        f"| Window | `{target.get('mainWindowTitle')}` / responding `{str(target.get('responding')).lower()}` |",
        f"| Actor-yaw lead | `{actor.get('sourceAddress')} @ {actor.get('basisForwardOffset')}` |",
        f"| Candidate key | `{actor.get('candidateKey')}` |",
        f"| Validation method | `{validation.get('method')}` |",
        f"| Yaw readbacks | read-player `{validation.get('readPlayerOrientationStatus')}`, capture `{validation.get('captureActorOrientationStatus')}` |",
        f"| Coordinate proof | `{coordinate.get('latestProofOnlyStatus')}` at `{as_dict(coordinate.get('sample')).get('recordedAtUtc')}` |",
        f"| Movement allowed | `{str(as_dict(packet.get('movementGate')).get('activeMovementAllowed')).lower()}` |",
        f"| No Cheat Engine | `{str(as_dict(packet.get('safety')).get('noCheatEngine')).lower()}` |",
        "",
        "## Artifacts",
        "",
        "| Artifact | Path |",
        "|---|---|",
    ]
    for key, value in artifacts.items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(["", "## Phase 2 fallback order", ""])
    for index, action in enumerate(fallback, start=1):
        lines.append(f"{index}. {action}")
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    repo_root = default_repo_root()
    parser = argparse.ArgumentParser(description="Build current actor-yaw Phase 2 pre-restart baseline.")
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument("--pid", type=int, default=None)
    parser.add_argument("--hwnd", type=str, default=None)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=repo_root / "docs" / "recovery" / "current-actor-yaw-restart-check.json",
    )
    parser.add_argument("--output-markdown", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print the packet JSON to stdout.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write output files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    packet = build_phase2_baseline(repo_root=args.repo_root, process_id=args.pid, target_window_handle=args.hwnd)
    if args.json:
        print(json.dumps(packet, indent=2))
    if not args.dry_run:
        write_json(args.output_json, packet)
        markdown_path = args.output_markdown or args.output_json.with_suffix(".md")
        write_text_atomic(markdown_path, markdown_for_packet(packet))
    return 0
