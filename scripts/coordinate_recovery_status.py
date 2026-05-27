#!/usr/bin/env python3
"""Print a compact coordinate-recovery truth/status snapshot.

This is intentionally read-only: it reads the current proof-anchor pointer and
restart profile, then prints the operator fields needed after a client restart.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PROOF_PATH = Path("docs") / "recovery" / "current-proof-anchor-readback.json"
DEFAULT_PROFILE_PATH = Path("docs") / "recovery" / "coordinate-recovery-profile.json"
DEFAULT_CURRENT_TRUTH_PATH = Path("docs") / "recovery" / "current-truth.json"


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() and (candidate / "scripts").is_dir():
            return candidate
    raise RuntimeError(f"Could not find RiftReader repo root from {start}")


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def load_json(path: Path, blockers: list[str], warnings: list[str], label: str) -> dict[str, Any] | None:
    if not path.is_file():
        blockers.append(f"{label}-missing:{path}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        blockers.append(f"{label}-read-failed:{type(exc).__name__}:{exc}")
        return None
    if not isinstance(value, dict):
        blockers.append(f"{label}-not-json-object:{path}")
        return None
    if value.get("status") in {"blocked", "failed"}:
        warnings.append(f"{label}-status:{value.get('status')}")
    return value


def compact_coordinate(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "x": first_present(value.get("x"), value.get("X")),
        "y": first_present(value.get("y"), value.get("Y")),
        "z": first_present(value.get("z"), value.get("Z")),
        "recordedAtUtc": first_present(value.get("recordedAtUtc"), value.get("RecordedAtUtc")),
    }


def summarize_static_resolver(truth: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(truth, dict):
        return {"promoted": False, "status": None, "source": "current-truth.staticChainStatus"}
    static_status = truth.get("staticChainStatus") if isinstance(truth.get("staticChainStatus"), dict) else {}
    best_candidate = truth.get("bestCurrentCandidate") if isinstance(truth.get("bestCurrentCandidate"), dict) else {}
    primary_candidate = (
        static_status.get("primaryCandidate") if isinstance(static_status.get("primaryCandidate"), dict) else {}
    )
    latest_api_validation = (
        static_status.get("latestApiNowValidation") if isinstance(static_status.get("latestApiNowValidation"), dict) else {}
    )
    promotion_review = static_status.get("promotionReview") if isinstance(static_status.get("promotionReview"), dict) else {}
    chain = first_present(primary_candidate.get("chain"), best_candidate.get("chain"))
    root_rva = first_present(primary_candidate.get("rootRva"), best_candidate.get("rootRva"))
    promotion_allowed = bool(static_status.get("promotionAllowed") or best_candidate.get("promotionEligible"))
    complete = bool(chain and root_rva)
    return {
        "promoted": bool(promotion_allowed and complete),
        "promotionAllowed": promotion_allowed,
        "complete": complete,
        "status": static_status.get("status"),
        "chain": chain,
        "rootModule": first_present(primary_candidate.get("rootModule"), best_candidate.get("rootModule")),
        "rootRva": root_rva,
        "rootAddress": first_present(primary_candidate.get("rootAddress"), best_candidate.get("rootAddress")),
        "ownerAddress": first_present(primary_candidate.get("ownerAddress"), best_candidate.get("currentOwnerAddress")),
        "coordinateAddress": first_present(
            primary_candidate.get("coordinateAddress"), best_candidate.get("currentCoordinateAddress")
        ),
        "apiNowValidationStatus": first_present(latest_api_validation.get("status"), promotion_review.get("status")),
        "source": "current-truth.staticChainStatus",
        "doesNotPromote": True,
    }


def truth_target_summary(truth: dict[str, Any] | None) -> dict[str, Any]:
    target = truth.get("target") if isinstance(truth, dict) and isinstance(truth.get("target"), dict) else {}
    return {
        "processName": target.get("processName"),
        "pid": target.get("processId"),
        "hwnd": target.get("targetWindowHandle"),
    }


def _process_image_name(process_name: Any) -> str | None:
    if not isinstance(process_name, str) or not process_name.strip():
        return None
    value = process_name.strip()
    if not value.lower().endswith(".exe"):
        value = f"{value}.exe"
    return value


def probe_live_processes(process_name: Any) -> dict[str, Any]:
    """Return a minimal, read-only live process inventory for process_name.

    The helper intentionally uses only tasklist metadata. It does not attach to
    the process, read target memory, send input, or query game state.
    """

    image_name = _process_image_name(process_name)
    result: dict[str, Any] = {
        "checkedAtUtc": utc_iso(),
        "status": "skipped",
        "processName": process_name,
        "imageName": image_name,
        "processes": [],
    }
    if not image_name:
        result["error"] = "missing-process-name"
        return result

    try:
        completed = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
    except Exception as exc:  # noqa: BLE001
        result["status"] = "unavailable"
        result["error"] = f"{type(exc).__name__}:{exc}"
        return result

    result["exitCode"] = completed.returncode
    if completed.returncode != 0:
        result["status"] = "unavailable"
        result["error"] = (completed.stderr or completed.stdout or "").strip()
        return result

    rows = [line for line in completed.stdout.splitlines() if line.strip()]
    if not rows or any(line.lstrip().startswith("INFO:") for line in rows):
        result["status"] = "passed"
        return result

    processes: list[dict[str, Any]] = []
    try:
        for row in csv.reader(rows):
            if len(row) < 2:
                continue
            try:
                pid = int(row[1])
            except ValueError:
                continue
            processes.append({"imageName": row[0], "pid": pid})
    except Exception as exc:  # noqa: BLE001
        result["status"] = "unavailable"
        result["error"] = f"tasklist-csv-parse:{type(exc).__name__}:{exc}"
        return result

    result["status"] = "passed"
    result["processes"] = processes
    return result


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def evaluate_live_target(
    summary_target: dict[str, Any],
    blockers: list[str],
    warnings: list[str],
    live_process_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    process_name = summary_target.get("processName")
    artifact_pid = _as_int(summary_target.get("pid"))
    snapshot = live_process_snapshot if live_process_snapshot is not None else probe_live_processes(process_name)
    processes = snapshot.get("processes") if isinstance(snapshot.get("processes"), list) else []
    live_pids = sorted(
        pid
        for pid in (_as_int(process.get("pid")) for process in processes if isinstance(process, dict))
        if pid is not None
    )
    live_target = {
        "enabled": True,
        "status": snapshot.get("status"),
        "checkedAtUtc": snapshot.get("checkedAtUtc"),
        "artifactProcessName": process_name,
        "artifactPid": artifact_pid,
        "artifactHwnd": summary_target.get("hwnd"),
        "livePids": live_pids,
        "verdict": "unknown",
    }

    if snapshot.get("status") == "skipped":
        warnings.append(f"live-target-check-skipped:{snapshot.get('error', 'unknown')}")
        live_target["verdict"] = "check-skipped"
    elif snapshot.get("status") != "passed":
        warnings.append(f"live-target-check-unavailable:{snapshot.get('error', 'unknown')}")
        live_target["verdict"] = "check-unavailable"
    elif artifact_pid is None:
        blockers.append("artifact-target-pid-missing")
        live_target["verdict"] = "artifact-pid-missing"
    elif not live_pids:
        blockers.append(f"live-target-not-running:{process_name}")
        live_target["verdict"] = "no-live-process"
    elif artifact_pid not in live_pids:
        blockers.append(f"artifact-target-pid-not-running:artifact={artifact_pid};live={','.join(str(pid) for pid in live_pids)}")
        live_target["verdict"] = "artifact-pid-stale"
    else:
        live_target["verdict"] = "artifact-pid-running"

    return live_target


def build_status(
    repo_root: Path,
    proof_path: Path,
    profile_path: Path,
    current_truth_path: Path | None = None,
    *,
    live_target_check: bool = False,
    live_process_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    proof = load_json(proof_path, blockers, warnings, "current-proof")
    profile = load_json(profile_path, blockers, warnings, "restart-profile")
    truth = load_json(current_truth_path, blockers, warnings, "current-truth") if current_truth_path else None
    static_resolver = summarize_static_resolver(truth)

    target = {}
    proof_anchor = {}
    stale_anchor = {}
    latest_validation = {}
    latest_proofonly = {}
    input_backend_incident = {}
    if proof:
        proof_status = str(proof.get("status") or "")
        if proof_status.startswith("blocked"):
            blockers.append(f"current-proof-status:{proof_status}")
        target = proof.get("target") if isinstance(proof.get("target"), dict) else {}
        source = proof.get("riftscanCandidateSource") if isinstance(proof.get("riftscanCandidateSource"), dict) else {}
        latest_validation = proof.get("latestValidation") if isinstance(proof.get("latestValidation"), dict) else {}
        latest_proofonly = proof.get("latestProofOnly") if isinstance(proof.get("latestProofOnly"), dict) else {}
        input_backend_incident = (
            proof.get("inputBackendIncident") if isinstance(proof.get("inputBackendIncident"), dict) else {}
        )
        stale_pointer = proof.get("staleProofPointer") if isinstance(proof.get("staleProofPointer"), dict) else {}
        preserved = stale_pointer.get("preservedEvidence") if isinstance(stale_pointer.get("preservedEvidence"), dict) else {}
        preserved_source = (
            preserved.get("riftscanCandidateSource")
            if isinstance(preserved.get("riftscanCandidateSource"), dict)
            else {}
        )
        proof_anchor = {
            "candidateId": first_present(source.get("candidateId"), latest_validation.get("proofAnchorCandidateId")),
            "addressHex": first_present(
                source.get("sourceAbsoluteAddressHex"),
                latest_validation.get("proofAnchorCandidateAddressHex"),
            ),
            "supportCount": first_present(source.get("proofSupportCount"), source.get("supportCount")),
            "candidateFile": source.get("matchFile"),
        }
        stale_anchor = {
            "candidateId": preserved_source.get("candidateId"),
            "addressHex": preserved_source.get("sourceAbsoluteAddressHex"),
            "supportCount": first_present(preserved_source.get("proofSupportCount"), preserved_source.get("supportCount")),
            "candidateFile": preserved_source.get("matchFile"),
            "archivedPointer": stale_pointer.get("archivedPointer"),
            "reusePolicy": stale_pointer.get("reusePolicy"),
        }

    profile_target = {}
    best_range = {}
    stage_timings = []
    if profile:
        profile_target = profile.get("target") if isinstance(profile.get("target"), dict) else {}
        best_range = profile.get("bestScanRange") if isinstance(profile.get("bestScanRange"), dict) else {}
        stage_timings = profile.get("stageTimings") if isinstance(profile.get("stageTimings"), list) else []

    summary_target = {
        "processName": first_present(target.get("processName"), profile_target.get("processName")),
        "pid": first_present(target.get("processId"), profile_target.get("pid")),
        "hwnd": first_present(target.get("targetWindowHandle"), profile_target.get("hwnd")),
    }
    if static_resolver.get("promoted"):
        resolver_target = truth_target_summary(truth)
        summary_target = {
            "processName": first_present(resolver_target.get("processName"), summary_target.get("processName")),
            "pid": first_present(resolver_target.get("pid"), summary_target.get("pid")),
            "hwnd": first_present(resolver_target.get("hwnd"), summary_target.get("hwnd")),
        }
        warnings.append("proof-anchor-status-superseded-by-promoted-static-resolver")
    live_target = {"enabled": False, "verdict": "not-checked"}
    if live_target_check:
        live_target = evaluate_live_target(summary_target, blockers, warnings, live_process_snapshot)

    status = "blocked" if blockers else "passed"
    return {
        "schemaVersion": 1,
        "kind": "riftreader-coordinate-recovery-status",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "repoRoot": str(repo_root),
        "paths": {
            "currentProofAnchorReadback": str(proof_path),
            "coordinateRecoveryProfile": str(profile_path),
            "currentTruth": str(current_truth_path) if current_truth_path else None,
        },
        "target": summary_target,
        "liveTarget": live_target,
        "proof": {
            "status": proof.get("status") if proof else None,
            "lastUpdatedUtc": proof.get("lastUpdatedUtc") if proof else None,
            "movementAllowed": latest_validation.get("movementAllowed"),
            "movementAllowedEffective": bool(latest_validation.get("movementAllowed"))
            and not bool(input_backend_incident.get("automationMovementPaused")),
            "latestValidationStatus": latest_validation.get("status"),
            "proofOnlyStatus": latest_proofonly.get("status"),
            "proofOnlyGeneratedAtUtc": latest_proofonly.get("generatedAtUtc"),
            "inputBackendIncident": {
                "status": input_backend_incident.get("status"),
                "automationMovementPaused": input_backend_incident.get("automationMovementPaused"),
                "emergencyKeyReleaseSummary": (
                    input_backend_incident.get("emergencyKeyRelease", {}).get("summaryJson")
                    if isinstance(input_backend_incident.get("emergencyKeyRelease"), dict)
                    else None
                ),
            },
            "anchor": proof_anchor,
            "staleAnchor": stale_anchor,
            "currentCoordinate": compact_coordinate(
                first_present(latest_proofonly.get("currentCoordinate"), latest_validation.get("currentCoordinate"))
            ),
        },
        "recoveryProfile": {
            "generatedAtUtc": profile.get("generatedAtUtc") if profile else None,
            "referenceProvider": profile.get("referenceProvider") if profile else None,
            "profileScanUsed": profile.get("profileScanUsed") if profile else None,
            "candidateJsonl": profile.get("candidateJsonl") if profile else None,
            "bestScanRange": {
                "rank": best_range.get("rank"),
                "minAddressHex": best_range.get("minAddressHex"),
                "maxAddressHex": best_range.get("maxAddressHex"),
                "hitCount": best_range.get("hitCount"),
                "durationSeconds": best_range.get("durationSeconds"),
                "summaryJson": best_range.get("summaryJson"),
            },
            "stageTimings": stage_timings,
        },
        "staticResolver": static_resolver,
        "safety": {
            "noCheatEngine": True,
            "x64dbgMode": "offline-read-only",
            "savedVariablesUsedAsLiveTruth": False,
            "movementSentByStatusCommand": False,
            "providerWrites": False,
            "gitMutation": False,
            "liveTargetCheck": live_target_check,
        },
    }


def render_text(status: dict[str, Any]) -> str:
    proof = status.get("proof") or {}
    anchor = proof.get("anchor") or {}
    profile = status.get("recoveryProfile") or {}
    static_resolver = status.get("staticResolver") or {}
    best_range = profile.get("bestScanRange") or {}
    target = status.get("target") or {}
    live_target = status.get("liveTarget") or {}
    lines = [
        "# Coordinate recovery status",
        "",
        f"- Status: `{status.get('status')}`",
        f"- Target: PID `{target.get('pid')}`, HWND `{target.get('hwnd')}`, process `{target.get('processName')}`",
        f"- Live target check: `{live_target.get('verdict')}`; live PIDs `{live_target.get('livePids')}`",
        f"- Proof: `{proof.get('status')}` / ProofOnly `{proof.get('proofOnlyStatus')}`",
        f"- Anchor: `{anchor.get('addressHex')}` (`{anchor.get('candidateId')}`), support `{anchor.get('supportCount')}`",
        f"- Coordinate: `{proof.get('currentCoordinate')}`",
        f"- Static resolver: promoted `{static_resolver.get('promoted')}`, chain `{static_resolver.get('chain')}`, root `{static_resolver.get('rootRva')}`",
        f"- Profile provider: `{profile.get('referenceProvider')}`, profileScanUsed `{profile.get('profileScanUsed')}`",
        f"- Best range: rank `{best_range.get('rank')}`, `{best_range.get('minAddressHex')}` -> `{best_range.get('maxAddressHex')}`, hits `{best_range.get('hitCount')}`, seconds `{best_range.get('durationSeconds')}`",
        "",
        "## Stage timings",
        "",
        "| Stage | Phase | Status | Seconds |",
        "|---|---|---:|---:|",
    ]
    for stage in profile.get("stageTimings") or []:
        if not isinstance(stage, dict):
            continue
        lines.append(
            f"| `{stage.get('label')}` | `{stage.get('phase')}` | `{stage.get('status')}` | {stage.get('durationSeconds')} |"
        )
    if not profile.get("stageTimings"):
        lines.append("| none | none | none | none |")
    lines.extend(
        [
            "",
            "## Blockers",
            "",
            *[f"- `{item}`" for item in status.get("blockers") or ["none"]],
            "",
            "## Warnings",
            "",
            *[f"- `{item}`" for item in status.get("warnings") or ["none"]],
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print compact current coordinate recovery/proof status.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--proof-path", default=str(DEFAULT_PROOF_PATH))
    parser.add_argument("--profile-path", default=str(DEFAULT_PROFILE_PATH))
    parser.add_argument("--current-truth-path", default=str(DEFAULT_CURRENT_TRUTH_PATH))
    parser.add_argument(
        "--skip-live-target-check",
        action="store_true",
        help="Artifact-only mode: do not check whether the stored proof PID is running now.",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    proof_path = Path(args.proof_path)
    profile_path = Path(args.profile_path)
    current_truth_path = Path(args.current_truth_path)
    if not proof_path.is_absolute():
        proof_path = (repo_root / proof_path).resolve()
    if not profile_path.is_absolute():
        profile_path = (repo_root / profile_path).resolve()
    if not current_truth_path.is_absolute():
        current_truth_path = (repo_root / current_truth_path).resolve()

    status = build_status(
        repo_root,
        proof_path,
        profile_path,
        current_truth_path,
        live_target_check=not args.skip_live_target_check,
    )
    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print(render_text(status))
    return 2 if status.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
