#!/usr/bin/env python3
"""Emit a stable read-only navigation state contract for external consumers.

The helper reads the promoted static-owner coordinate + facing/yaw resolver and
returns a compact JSON object intended for other local projects. It deliberately
keeps turn-rate/support fields diagnostic-only and never sends input, attaches a
debugger, writes target memory, updates current truth, or mutates Git.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

try:
    from .nav_state_readback import read_nav_state
    from .workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, write_json
except ImportError:  # pragma: no cover - supports direct script execution.
    from nav_state_readback import read_nav_state
    from workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, write_json


SCHEMA_VERSION = 1
TOOL_VERSION = "riftreader-navigation-consumer-state-v0.1.0"
DEFAULT_OUTPUT_DIR = Path(".riftreader-local") / "navigation-consumer-state" / "latest"
POSTUPDATE_RECOVERY_GLOB = "postupdate-global-container-coordinate-readback-*/summary.json"


def chain_state(current_truth: Mapping[str, Any], key: str) -> str:
    chains = safe_mapping(current_truth.get("navigationControlChains"))
    entry = safe_mapping(chains.get(key))
    state = entry.get("state")
    if state:
        return str(state)

    if key == "position":
        static_status = safe_mapping(current_truth.get("staticChainStatus"))
        if static_status.get("promotionAllowed") is True:
            return "promoted"
    if key == "facingYaw":
        facing_status = safe_mapping(current_truth.get("staticOwnerFacing"))
        if facing_status.get("promotionAllowed") is True:
            return "promoted"
    return "unknown"


def chain_expression(current_truth: Mapping[str, Any], key: str, fallback: str) -> str:
    chains = safe_mapping(current_truth.get("navigationControlChains"))
    entry = safe_mapping(chains.get(key))
    chain = entry.get("chain")
    if chain:
        return str(chain)
    if key == "position":
        candidate = safe_mapping(safe_mapping(current_truth.get("staticChainStatus")).get("primaryCandidate"))
        if candidate.get("chain"):
            return str(candidate["chain"])
    if key == "facingYaw":
        candidate = safe_mapping(safe_mapping(current_truth.get("staticOwnerFacing")).get("primaryCandidate"))
        if candidate.get("expression"):
            return str(candidate["expression"])
    return fallback


def latest_summary_path(root: Path, pattern: str) -> Path | None:
    capture_root = root / "scripts" / "captures"
    if not capture_root.exists():
        return None
    matches = [path for path in capture_root.glob(pattern) if path.is_file()]
    return max(matches, key=lambda path: path.stat().st_mtime) if matches else None


def build_post_update_recovery(summary: Mapping[str, Any], *, summary_path: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    best = safe_mapping(summary.get("bestReadback"))
    polling = safe_mapping(summary.get("polling"))
    target = safe_mapping(summary.get("target"))
    artifacts = safe_mapping(summary.get("artifacts"))
    summary_json = artifacts.get("summaryJson")
    if summary_path is not None:
        summary_json = str(summary_path if root is None else summary_path.resolve())

    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "generatedAtUtc": summary.get("generatedAtUtc"),
        "candidateOnly": True,
        "promotionEligible": bool(summary.get("promotionEligible")),
        "routeControlAuthorized": False,
        "actionableForNavigation": False,
        "chain": best.get("chain"),
        "coordinate": dict(best.get("coordinate")) if isinstance(best.get("coordinate"), Mapping) else None,
        "deltaVsReference": best.get("deltaVsReference"),
        "globalRva": best.get("globalRva"),
        "parentOffset": best.get("parentOffset"),
        "coordinateOffset": best.get("coordinateOffset"),
        "sourceFunctionRva": best.get("sourceFunctionRva"),
        "sourceInstructionRva": best.get("sourceInstructionRva"),
        "target": {
            "processId": target.get("pid") or target.get("processId"),
            "targetWindowHandle": target.get("hwnd") or target.get("targetWindowHandle"),
            "processStartUtc": target.get("expectedProcessStartUtc") or target.get("actualProcessStartUtc"),
            "moduleBase": target.get("moduleBase"),
        },
        "polling": {
            "sampleCount": polling.get("sampleCount"),
            "bestMatchingSampleCount": polling.get("bestMatchingSampleCount"),
            "allSamplesMatchedReference": polling.get("allSamplesMatchedReference"),
            "stationaryDriftWithinLimit": polling.get("stationaryDriftWithinLimit"),
            "bestCoordinateDrift": polling.get("bestCoordinateDrift"),
        },
        "sourceArtifacts": {
            "summaryJson": summary_json,
            "summaryMarkdown": artifacts.get("summaryMarkdown"),
            "readbackStatus": summary.get("status"),
            "readbackVerdict": summary.get("verdict"),
        },
        "blockers": [str(item) for item in summary.get("blockers", []) if item]
        if isinstance(summary.get("blockers"), list)
        else [],
        "warnings": [str(item) for item in summary.get("warnings", []) if item]
        if isinstance(summary.get("warnings"), list)
        else [],
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "targetMemoryBytesWritten": False,
            "currentTruthUpdate": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "candidateOnly": True,
        },
    }


def load_latest_post_update_recovery(root: Path) -> dict[str, Any] | None:
    latest = latest_summary_path(root, POSTUPDATE_RECOVERY_GLOB)
    if latest is None:
        return None
    try:
        data = load_json_object(latest)
    except Exception:
        return None
    return build_post_update_recovery(data, summary_path=latest, root=root)


def compact_target(raw_summary: Mapping[str, Any], current_truth: Mapping[str, Any]) -> dict[str, Any]:
    raw_target = safe_mapping(raw_summary.get("target"))
    truth_target = safe_mapping(current_truth.get("target"))
    return {
        "processName": raw_target.get("processName") or truth_target.get("processName"),
        "processId": raw_target.get("processId") or truth_target.get("processId"),
        "targetWindowHandle": raw_target.get("targetWindowHandle") or truth_target.get("targetWindowHandle"),
        "processStartUtc": raw_target.get("actualProcessStartUtc")
        or raw_target.get("expectedProcessStartUtc")
        or truth_target.get("processStartUtc"),
        "moduleBase": raw_target.get("moduleBase") or truth_target.get("moduleBase"),
        "moduleBaseCheck": raw_target.get("moduleBaseCheck") or raw_summary.get("moduleBaseCheck"),
        "processStartCheck": raw_target.get("processStartCheck"),
        "hwndCheck": raw_target.get("hwndCheck"),
    }


def build_consumer_state(
    *,
    nav_result: Mapping[str, Any],
    current_truth: Mapping[str, Any],
    post_update_recovery: Mapping[str, Any] | None = None,
    generated_at_utc: str | None = None,
    max_age_seconds: float = 5.0,
    current_truth_json: str = "docs/recovery/current-truth.json",
) -> dict[str, Any]:
    generated_at_utc = generated_at_utc or utc_iso()
    raw_summary = safe_mapping(nav_result.get("rawJson"))
    raw_reads = safe_mapping(raw_summary.get("reads"))
    raw_nav_state = safe_mapping(raw_reads.get("navState")) or safe_mapping(raw_summary.get("navState"))
    raw_artifacts = safe_mapping(raw_summary.get("artifacts"))
    raw_safety = safe_mapping(raw_summary.get("safety"))

    coordinate = (
        nav_result.get("playerCoordinate")
        or raw_nav_state.get("coordinate")
        or raw_reads.get("coordinate")
        or raw_summary.get("coordinate")
    )
    facing = nav_result.get("facingTargetCoordinate") or raw_nav_state.get("facingTargetCoordinate")
    yaw = nav_result.get("yawDegrees")
    pitch = nav_result.get("pitchDegrees")
    blockers: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []

    if not nav_result.get("ok"):
        blockers.append(f"nav-state-readback-not-ok:{nav_result.get('status')}")
    if not isinstance(coordinate, Mapping):
        blockers.append("position-coordinate-missing")
    if yaw is None:
        blockers.append("yaw-degrees-missing")
    if chain_state(current_truth, "position") != "promoted":
        blockers.append("position-chain-not-promoted")
    if chain_state(current_truth, "facingYaw") != "promoted":
        blockers.append("facing-yaw-chain-not-promoted")

    post_update_recovery = safe_mapping(post_update_recovery)
    if post_update_recovery:
        warnings.append("post-update-coordinate-candidate-visible-not-promoted")
        if post_update_recovery.get("candidateOnly") is not True:
            blockers.append("post-update-recovery-candidate-flag-missing")
        if post_update_recovery.get("routeControlAuthorized") is not False:
            blockers.append("post-update-recovery-route-control-not-blocked")

    for item in raw_summary.get("warnings", []) if isinstance(raw_summary.get("warnings"), list) else []:
        warnings.append(str(item))
    if nav_result.get("turnRate0x304") is not None or raw_nav_state.get("turnRate0x304") is not None:
        warnings.append("turn-rate-0x304-is-diagnostic-only-not-control")
    if raw_summary.get("errors"):
        errors.extend(str(item) for item in raw_summary.get("errors", []) if item)
    if nav_result.get("error"):
        errors.append(str(nav_result["error"]))

    status = "passed" if not blockers and not errors else "blocked" if blockers and not errors else "failed"
    verdict = "consumer-navigation-state-ready" if status == "passed" else "consumer-navigation-state-not-ready"

    safety = base_safety()
    safety.update(
        {
            "targetMemoryBytesRead": bool(raw_safety.get("targetMemoryBytesRead") or nav_result.get("ok")),
            "targetMemoryBytesWritten": False,
            "consumerReadOnly": True,
            "currentTruthWritten": False,
            "routeControlAuthorized": False,
            "candidateControlUsed": False,
        }
    )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-navigation-consumer-state",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": generated_at_utc,
        "status": status,
        "verdict": verdict,
        "target": compact_target(raw_summary, current_truth),
        "consumerContract": {
            "version": "navigation-consumer-state/v1",
            "readOnly": True,
            "maxConsumerAgeSeconds": float(max_age_seconds),
            "usableFor": [
                "current-player-position",
                "current-player-yaw",
                "route-dry-run-input",
                "external-consumer-pose-feed",
            ],
            "notUsableFor": [
                "unattended-route-control",
                "movement-authorization",
                "turn-rate-control",
                "post-update-candidate-as-promoted-truth",
                "proof-promotion",
                "actor-chain-promotion",
                "target-memory-write",
            ],
            "requiredConsumerChecks": [
                "reject-status-other-than-passed",
                "reject-payload-older-than-maxConsumerAgeSeconds",
                "verify-processId-targetWindowHandle-processStartUtc-moduleBase-before-live-input",
                "consume-only-navigation.position-and-navigation.orientation-as-promoted-fields",
                "treat-navigation.diagnostics-as-non-control-evidence",
                "treat-postUpdateRecovery-as-candidate-only",
            ],
        },
        "postUpdateRecovery": dict(post_update_recovery) if post_update_recovery else None,
        "navigation": {
            "position": {
                "state": chain_state(current_truth, "position"),
                "chain": chain_expression(
                    current_truth,
                    "position",
                    "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                ),
                "coordinate": dict(coordinate) if isinstance(coordinate, Mapping) else None,
                "sourceOffset": "0x320",
                "source": "promoted-static-owner-coordinate-readback",
            },
            "orientation": {
                "state": chain_state(current_truth, "facingYaw"),
                "chain": chain_expression(
                    current_truth,
                    "facingYaw",
                    "[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314",
                ),
                "yawDegrees": yaw,
                "pitchDegrees": pitch,
                "facingTargetCoordinate": dict(facing) if isinstance(facing, Mapping) else None,
                "planarLookaheadDistance": nav_result.get("planarLookaheadDistance"),
                "sourceOffset": "0x30C",
                "source": "promoted-static-owner-facing-yaw-readback",
            },
            "diagnostics": {
                "turnRate0x304": {
                    "state": "candidate-diagnostic-only",
                    "offset": "0x304",
                    "value": nav_result.get("turnRate0x304"),
                    "classification": nav_result.get("turnRateClassification"),
                    "controlAllowed": False,
                    "reason": "owner+0x304 semantic review classifies it as yaw-adjacent, not promoted active turn-rate",
                },
                "supportFields": raw_nav_state.get("catalogSupportFields") or {},
            },
            "routeControl": {
                "authorized": False,
                "movementPermission": False,
                "turnPermission": False,
                "reason": "consumer state is a read-only pose contract; route control remains a separate gated workflow",
            },
        },
        "sourceArtifacts": {
            "currentTruthJson": current_truth_json,
            "readbackSummaryJson": raw_artifacts.get("summaryJson") or raw_summary.get("summaryJson"),
            "readbackSummaryMarkdown": raw_artifacts.get("summaryMarkdown") or raw_summary.get("summaryMarkdown"),
            "readbackGeneratedAtUtc": raw_summary.get("generatedAtUtc") or generated_at_utc,
            "readbackStatus": raw_summary.get("status") or nav_result.get("status"),
            "readbackVerdict": raw_summary.get("verdict") or nav_result.get("verdict"),
        },
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
        "safety": safety,
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    navigation = safe_mapping(summary.get("navigation"))
    position = safe_mapping(navigation.get("position"))
    orientation = safe_mapping(navigation.get("orientation"))
    contract = safe_mapping(summary.get("consumerContract"))
    post_update = safe_mapping(summary.get("postUpdateRecovery"))
    target = safe_mapping(summary.get("target"))
    lines = [
        "# RiftReader navigation consumer state",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Target",
        "",
        f"- PID/HWND: `{target.get('processId')}` / `{target.get('targetWindowHandle')}`",
        f"- Process start: `{target.get('processStartUtc')}`",
        f"- Module base: `{target.get('moduleBase')}`",
        "",
        "## Consumer pose",
        "",
        f"- Position: `{position.get('coordinate')}`",
        f"- Yaw degrees: `{orientation.get('yawDegrees')}`",
        f"- Pitch degrees: `{orientation.get('pitchDegrees')}`",
        f"- Max consumer age seconds: `{contract.get('maxConsumerAgeSeconds')}`",
        "",
        "## Safety",
        "",
        "- This payload is read-only and does not authorize movement or turn control.",
        "- `owner+0x304` and support fields are diagnostics only.",
    ]
    if post_update:
        lines.extend(
            [
                "",
                "## Post-update recovery candidate",
                "",
                f"- Status: `{post_update.get('status')}`",
                f"- Chain: `{post_update.get('chain')}`",
                f"- Coordinate: `{post_update.get('coordinate')}`",
                "- Candidate-only: `true`; route control remains unauthorized.",
            ]
        )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in summary.get("blockers", []))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{item}`" for item in summary.get("warnings", []))
    if summary.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- `{item}`" for item in summary.get("errors", []))
    return "\n".join(lines) + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root")
    parser.add_argument("--current-truth-json", default="docs/recovery/current-truth.json")
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--hwnd")
    parser.add_argument("--module-base")
    parser.add_argument("--use-current-truth", action="store_true", default=True)
    parser.add_argument("--no-current-truth", action="store_false", dest="use_current_truth")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--max-consumer-age-seconds", type=float, default=5.0)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    truth_path = Path(args.current_truth_json)
    if not truth_path.is_absolute():
        truth_path = root / truth_path

    try:
        current_truth = load_json_object(truth_path)
        post_update_recovery = load_latest_post_update_recovery(root)
        nav_result = read_nav_state(
            root=root,
            pid=args.pid,
            hwnd=args.hwnd,
            module_base=args.module_base,
            process_name=args.process_name,
            current_truth_json=str(truth_path),
            use_current_truth=bool(args.use_current_truth),
            timeout_seconds=float(args.timeout_seconds),
        )
        summary = build_consumer_state(
            nav_result=nav_result,
            current_truth=current_truth,
            post_update_recovery=post_update_recovery,
            max_age_seconds=float(args.max_consumer_age_seconds),
            current_truth_json=str(truth_path),
        )
    except Exception as exc:  # noqa: BLE001
        summary = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-navigation-consumer-state",
            "toolVersion": TOOL_VERSION,
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "verdict": "consumer-navigation-state-error",
            "blockers": [],
            "warnings": [],
            "errors": [f"{type(exc).__name__}:{exc}"],
            "safety": {
                **base_safety(),
                "targetMemoryBytesRead": False,
                "targetMemoryBytesWritten": False,
                "consumerReadOnly": True,
                "currentTruthWritten": False,
            },
        }

    if args.write:
        out_dir = Path(args.output_dir)
        if not out_dir.is_absolute():
            out_dir = root / out_dir
        summary_json = out_dir / "summary.json"
        summary_md = out_dir / "summary.md"
        summary.setdefault("artifacts", {})
        summary["artifacts"] = {
            "outputDirectory": str(out_dir),
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
        }
        write_json(summary_json, summary)
        summary_md.parent.mkdir(parents=True, exist_ok=True)
        summary_md.write_text(build_markdown(summary), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(build_markdown(summary))

    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
