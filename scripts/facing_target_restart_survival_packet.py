#!/usr/bin/env python3
"""Build a report-only restart/relog survival packet for candidate facing target.

This helper compares pre/post restart `static-owner-nav-state-readback` summary
JSON files.  It proves nothing by itself unless the target process epoch changes
and the same candidate offsets are recovered after restart.  It sends no input,
does not restart the game, and never promotes candidate facing truth.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

try:
    from .workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution path
    from workflow_common import base_safety, load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
REQUIRED_KIND = "static-owner-nav-state-readback"
REQUIRED_STATUS = "passed"
REQUIRED_FACING_TARGET_OFFSET = "0x30C"
REQUIRED_POSITION_OFFSET = "0x320"
SUPPORT_ONLY_TURN_RATE_OFFSET = "0x304"


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def resolve_under_repo(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def repo_rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def process_start_utc(nav_summary: Mapping[str, Any]) -> Any:
    target = safe_mapping(nav_summary.get("target"))
    return target.get("actualProcessStartUtc") or target.get("expectedProcessStartUtc") or target.get("processStartUtc")


def target_process_id(nav_summary: Mapping[str, Any]) -> Any:
    return safe_mapping(nav_summary.get("target")).get("processId")


def target_hwnd(nav_summary: Mapping[str, Any]) -> Any:
    return safe_mapping(nav_summary.get("target")).get("targetWindowHandle")


def summarize_nav_state(root: Path, path: Path, data: Mapping[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if data.get("kind") != REQUIRED_KIND:
        blockers.append(f"nav-state-kind-mismatch:{data.get('kind')}")
    if data.get("status") != REQUIRED_STATUS:
        blockers.append(f"nav-state-status-not-passed:{data.get('status')}")
    latest_state = safe_mapping(data.get("latestState"))
    target = safe_mapping(data.get("target"))
    safety = safe_mapping(data.get("safety"))
    if latest_state.get("facingTargetOffset") != REQUIRED_FACING_TARGET_OFFSET:
        blockers.append(f"facing-target-offset-mismatch:{latest_state.get('facingTargetOffset')}")
    if latest_state.get("positionOffset") != REQUIRED_POSITION_OFFSET:
        blockers.append(f"position-offset-mismatch:{latest_state.get('positionOffset')}")
    if latest_state.get("turnRateOffset") and latest_state.get("turnRateOffset") != SUPPORT_ONLY_TURN_RATE_OFFSET:
        warnings.append(f"unexpected-support-turn-rate-offset:{latest_state.get('turnRateOffset')}")
    if not safe_mapping(latest_state.get("facingTargetCoordinate")):
        blockers.append("facing-target-coordinate-missing")
    if not safe_mapping(latest_state.get("coordinate")):
        blockers.append("promoted-coordinate-missing")
    if safety.get("targetMemoryBytesRead") is not True:
        blockers.append("nav-state-target-memory-read-flag-not-true")
    if safety.get("targetMemoryBytesWritten"):
        blockers.append("nav-state-target-memory-written")
    for forbidden_flag in ("movementSent", "inputSent", "proofPromotion", "actorChainPromotion", "facingPromotion", "providerWrites"):
        if safety.get(forbidden_flag):
            blockers.append(f"nav-state-forbidden-flag:{forbidden_flag}")
    return (
        {
            "summaryJson": repo_rel(root, path),
            "generatedAtUtc": data.get("generatedAtUtc"),
            "target": {
                "processName": target.get("processName"),
                "processId": target.get("processId"),
                "targetWindowHandle": target.get("targetWindowHandle"),
                "actualProcessStartUtc": target.get("actualProcessStartUtc"),
                "expectedProcessStartUtc": target.get("expectedProcessStartUtc"),
                "moduleBase": target.get("moduleBase"),
            },
            "ownerAddress": latest_state.get("ownerAddress"),
            "positionOffset": latest_state.get("positionOffset"),
            "facingTargetOffset": latest_state.get("facingTargetOffset"),
            "turnRateOffset": latest_state.get("turnRateOffset"),
            "coordinate": latest_state.get("coordinate"),
            "facingTargetCoordinate": latest_state.get("facingTargetCoordinate"),
            "yawDegrees": latest_state.get("yawDegrees"),
            "sourceSafety": {
                "targetMemoryBytesRead": bool(safety.get("targetMemoryBytesRead")),
                "targetMemoryBytesWritten": bool(safety.get("targetMemoryBytesWritten")),
                "movementSent": bool(safety.get("movementSent")),
                "inputSent": bool(safety.get("inputSent")),
            },
        },
        blockers,
        warnings,
    )


def build_restart_survival_packet(args: argparse.Namespace, root: Path, run_dir: Path) -> tuple[dict[str, Any], int]:
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "facing-target-restart-survival-packet",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "verdict": "restart-survival-packet-not-built",
        "repoRoot": str(root),
        "runDirectory": str(run_dir),
        "preRestart": {},
        "postRestart": {},
        "analysis": {
            "candidateOnly": True,
            "promotionAllowed": False,
            "restartRelogSurvived": False,
            "facingTargetOffset": REQUIRED_FACING_TARGET_OFFSET,
            "positionOffset": REQUIRED_POSITION_OFFSET,
            "supportOnlyTurnRateOffset": SUPPORT_ONLY_TURN_RATE_OFFSET,
        },
        "promotionReadinessInputs": {
            "preRestartNavStateSummaryJson": None,
            "postRestartNavStateSummaryJson": None,
            "restartSurvivalSummaryJson": str(run_dir / "summary.json"),
            "promotionReviewRequired": True,
        },
        "blockers": [],
        "warnings": ["report-only-no-restart-or-live-input-sent", "candidate-facing-target-only-no-promotion"],
        "errors": [],
        "safety": {
            **base_safety(),
            "reportOnly": True,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
        },
        "sourceSafety": {
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "movementSent": False,
            "inputSent": False,
        },
        "artifacts": {
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
        "next": {
            "recommendedAction": "After a real restart/relog, rerun nav-state readback and rebuild this packet with distinct pre/post process-start epochs.",
            "recommendedActions": [
                "Capture a post-restart static-owner nav-state readback on the exact new target PID/HWND.",
                "Rebuild this packet with pre and post nav-state summaries from different process-start epochs.",
                "Use the packet only as one input to a separate proof/promotion review.",
            ],
        },
    }

    pre_arg = getattr(args, "pre_restart_nav_summary_json", None)
    post_arg = getattr(args, "post_restart_nav_summary_json", None)
    if not pre_arg or not post_arg:
        summary["status"] = "blocked"
        summary["verdict"] = "pre-and-post-nav-state-summaries-required"
        summary["blockers"].append("pre-restart-nav-summary-json-required" if not pre_arg else "post-restart-nav-summary-json-required")
        return summary, 2

    paths = {
        "preRestart": resolve_under_repo(root, Path(str(pre_arg))),
        "postRestart": resolve_under_repo(root, Path(str(post_arg))),
    }
    try:
        loaded: dict[str, dict[str, Any]] = {}
        for label, path in paths.items():
            if not path.is_file():
                summary["blockers"].append(f"{label}-nav-summary-not-found:{path}")
                continue
            try:
                loaded[label] = load_json_object(path)
            except Exception as exc:  # noqa: BLE001
                summary["errors"].append(f"{label}-nav-summary-malformed:{path}:{type(exc).__name__}:{exc}")
        if summary["errors"]:
            summary["status"] = "failed"
            summary["verdict"] = "restart-survival-packet-error"
            return summary, 1
        if set(loaded) != {"preRestart", "postRestart"}:
            summary["status"] = "blocked"
            summary["verdict"] = "restart-survival-packet-blocked"
            return summary, 2

        pre_summary, pre_blockers, pre_warnings = summarize_nav_state(root, paths["preRestart"], loaded["preRestart"])
        post_summary, post_blockers, post_warnings = summarize_nav_state(root, paths["postRestart"], loaded["postRestart"])
        summary["preRestart"] = pre_summary
        summary["postRestart"] = post_summary
        summary["promotionReadinessInputs"]["preRestartNavStateSummaryJson"] = repo_rel(root, paths["preRestart"])
        summary["promotionReadinessInputs"]["postRestartNavStateSummaryJson"] = repo_rel(root, paths["postRestart"])
        summary["blockers"].extend(f"pre:{item}" for item in pre_blockers)
        summary["blockers"].extend(f"post:{item}" for item in post_blockers)
        summary["warnings"].extend(f"pre:{item}" for item in pre_warnings)
        summary["warnings"].extend(f"post:{item}" for item in post_warnings)
        for state in (pre_summary, post_summary):
            source_safety = safe_mapping(state.get("sourceSafety"))
            for key in summary["sourceSafety"]:
                summary["sourceSafety"][key] = bool(summary["sourceSafety"][key]) or bool(source_safety.get(key))

        pre_start = process_start_utc(loaded["preRestart"])
        post_start = process_start_utc(loaded["postRestart"])
        process_start_changed = bool(pre_start and post_start and str(pre_start) != str(post_start))
        process_id_changed = str(target_process_id(loaded["preRestart"])) != str(target_process_id(loaded["postRestart"]))
        hwnd_changed = str(target_hwnd(loaded["preRestart"])) != str(target_hwnd(loaded["postRestart"]))
        offsets_stable = (
            pre_summary.get("facingTargetOffset") == post_summary.get("facingTargetOffset") == REQUIRED_FACING_TARGET_OFFSET
            and pre_summary.get("positionOffset") == post_summary.get("positionOffset") == REQUIRED_POSITION_OFFSET
        )
        owner_address_changed = bool(
            pre_summary.get("ownerAddress")
            and post_summary.get("ownerAddress")
            and str(pre_summary.get("ownerAddress")) != str(post_summary.get("ownerAddress"))
        )
        summary["analysis"].update(
            {
                "preProcessStartUtc": pre_start,
                "postProcessStartUtc": post_start,
                "processStartChanged": process_start_changed,
                "processIdChanged": process_id_changed,
                "windowHandleChanged": hwnd_changed,
                "ownerAddressChanged": owner_address_changed,
                "offsetsStable": offsets_stable,
            }
        )
        if not process_start_changed:
            summary["blockers"].append("process-start-not-changed-or-missing")
        if not offsets_stable:
            summary["blockers"].append("candidate-offsets-not-stable")

        if summary["blockers"]:
            summary["status"] = "blocked"
            summary["verdict"] = "restart-survival-packet-blocked"
            exit_code = 2
        else:
            summary["status"] = "passed"
            summary["verdict"] = "candidate-facing-target-restart-relog-survival-passed"
            summary["analysis"]["restartRelogSurvived"] = True
            exit_code = 0
        summary["blockers"] = sorted(set(str(item) for item in summary["blockers"]))
        summary["warnings"] = sorted(set(str(item) for item in summary["warnings"]))
        summary["errors"] = sorted(set(str(item) for item in summary["errors"]))
        return summary, exit_code
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "restart-survival-packet-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
        return summary, 1


def build_markdown(summary: Mapping[str, Any]) -> str:
    analysis = safe_mapping(summary.get("analysis"))
    lines = [
        "# Facing-target restart/relog survival packet",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Run directory: `{summary.get('runDirectory')}`",
        f"- Restart/relog survived: `{analysis.get('restartRelogSurvived')}`",
        f"- Promotion allowed: `{analysis.get('promotionAllowed')}`",
        "",
        "## Analysis",
        "",
    ]
    for key, value in analysis.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Inputs", ""])
    for key in ("preRestart", "postRestart"):
        state = safe_mapping(summary.get(key))
        lines.append(f"### {key}")
        lines.append("")
        lines.append(f"- Summary JSON: `{state.get('summaryJson')}`")
        lines.append(f"- PID/HWND: `{safe_mapping(state.get('target')).get('processId')}` / `{safe_mapping(state.get('target')).get('targetWindowHandle')}`")
        lines.append(f"- Process start: `{safe_mapping(state.get('target')).get('actualProcessStartUtc') or safe_mapping(state.get('target')).get('expectedProcessStartUtc')}`")
        lines.append(f"- Owner: `{state.get('ownerAddress')}`")
        lines.append(f"- Offsets: facing `{state.get('facingTargetOffset')}`, coordinate `{state.get('positionOffset')}`, support turn `{state.get('turnRateOffset')}`")
        lines.append("")
    lines.extend(["## Promotion readiness inputs", ""])
    for key, value in safe_mapping(summary.get("promotionReadinessInputs")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Blockers", ""])
    for item in safe_list(summary.get("blockers")) or ["none"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Warnings", ""])
    for item in safe_list(summary.get("warnings")) or ["none"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Errors", ""])
    for item in safe_list(summary.get("errors")) or ["none"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Safety", "", "| Flag | Value |", "|---|---:|"])
    for key, value in safe_mapping(summary.get("safety")).items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(["", "## Next", ""])
    for item in safe_list(safe_mapping(summary.get("next")).get("recommendedActions")):
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_outputs(summary: dict[str, Any]) -> None:
    artifacts = safe_mapping(summary.get("artifacts"))
    summary_json = Path(str(artifacts.get("summaryJson")))
    summary_md = Path(str(artifacts.get("summaryMarkdown")))
    write_json(summary_json, summary)
    summary_md.parent.mkdir(parents=True, exist_ok=True)
    summary_md.write_text(build_markdown(summary), encoding="utf-8")


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    analysis = safe_mapping(summary.get("analysis"))
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "restartRelogSurvived": analysis.get("restartRelogSurvived"),
        "processStartChanged": analysis.get("processStartChanged"),
        "offsetsStable": analysis.get("offsetsStable"),
        "promotionAllowed": analysis.get("promotionAllowed"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
        "safety": summary.get("safety", {}),
        "sourceSafety": summary.get("sourceSafety", {}),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--output-root", default=Path("scripts") / "captures")
    parser.add_argument("--pre-restart-nav-summary-json")
    parser.add_argument("--post-restart-nav-summary-json")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def self_test_payload() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp_name:
        root = Path(temp_name)
        paths: list[Path] = []
        for label, pid, start, owner in [
            ("pre", 100, "2026-06-01T00:00:00Z", "0x1000"),
            ("post", 200, "2026-06-01T00:10:00Z", "0x2000"),
        ]:
            path = root / "scripts" / "captures" / f"nav-{label}" / "summary.json"
            write_json(
                path,
                {
                    "kind": REQUIRED_KIND,
                    "status": REQUIRED_STATUS,
                    "generatedAtUtc": start,
                    "target": {
                        "processName": "rift_x64",
                        "processId": pid,
                        "targetWindowHandle": f"0x{pid:X}",
                        "actualProcessStartUtc": start,
                        "moduleBase": "0x7FF600000000",
                    },
                    "latestState": {
                        "ownerAddress": owner,
                        "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
                        "facingTargetCoordinate": {"x": 10.0, "y": 2.0, "z": 20.0},
                        "positionOffset": REQUIRED_POSITION_OFFSET,
                        "facingTargetOffset": REQUIRED_FACING_TARGET_OFFSET,
                        "turnRateOffset": SUPPORT_ONLY_TURN_RATE_OFFSET,
                    },
                    "safety": {"targetMemoryBytesRead": True},
                },
            )
            paths.append(path)
        args = argparse.Namespace(pre_restart_nav_summary_json=str(paths[0]), post_restart_nav_summary_json=str(paths[1]))
        summary, _ = build_restart_survival_packet(args, root, root / "scripts" / "captures" / "restart-survival-self-test")
    return {
        "status": "passed" if summary.get("status") == "passed" else "failed",
        "checks": {
            "restartRelogSurvived": safe_mapping(summary.get("analysis")).get("restartRelogSurvived"),
            "promotionAllowed": safe_mapping(summary.get("analysis")).get("promotionAllowed"),
            "helperInputSent": safe_mapping(summary.get("safety")).get("inputSent"),
        },
        "safety": summary.get("safety", {}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        payload = self_test_payload()
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"self-test:{payload['status']}")
        return 0 if payload.get("status") == "passed" else 1

    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = resolve_under_repo(root, Path(args.output_root))
    run_dir = output_root / f"facing-target-restart-survival-packet-{utc_stamp()}"
    summary, exit_code = build_restart_survival_packet(args, root, run_dir)
    write_outputs(summary)
    if args.json:
        print(json.dumps(compact(summary), indent=2))
    else:
        print(f"{summary['status']}: {safe_mapping(summary.get('artifacts')).get('summaryMarkdown')}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
