#!/usr/bin/env python3
"""Build a dry-run current-truth refresh plan from navigation discovery evidence.

This helper is deliberately non-applying. It reads the tracked
``docs/recovery/current-truth.json`` and the ignored navigation pointer
discovery dashboard, then writes an ignored proposal/diff under
``.riftreader-local``. It never edits tracked truth docs, sends live input,
reads target memory, attaches debuggers, writes providers, mutates Git, or
promotes proof/candidate chains.
"""

from __future__ import annotations

import argparse
import copy
import difflib
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, preview_text, repo_rel, safety_flags, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, preview_text, repo_rel, safety_flags, utc_iso


SCHEMA_VERSION = 1
TOOL_VERSION = "riftreader-current-truth-refresh-plan-v0.1.0"
DEFAULT_CURRENT_TRUTH_JSON = Path("docs") / "recovery" / "current-truth.json"
DEFAULT_DASHBOARD_JSON = Path(".riftreader-local") / "navigation-pointer-discovery" / "latest" / "summary.json"
DEFAULT_OUTPUT_DIR = Path(".riftreader-local") / "current-truth-refresh-plan" / "latest"


class CurrentTruthRefreshPlanError(RuntimeError):
    """Raised for controlled planner failures."""


def as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise CurrentTruthRefreshPlanError(f"malformed-json:{path}:{exc}") from exc
    except OSError as exc:
        raise CurrentTruthRefreshPlanError(f"json-read-failed:{path}:{exc}") from exc
    if not isinstance(payload, dict):
        raise CurrentTruthRefreshPlanError(f"json-root-not-object:{path}")
    return payload


def json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def build_unified_diff(before: dict[str, Any], after: dict[str, Any], *, fromfile: str, tofile: str) -> str:
    return "".join(
        difflib.unified_diff(
            json_text(before).splitlines(keepends=True),
            json_text(after).splitlines(keepends=True),
            fromfile=fromfile,
            tofile=tofile,
            lineterm="",
        )
    )


def get_path(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def set_path(payload: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = payload
    for part in path[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[path[-1]] = value


def pointer(path: tuple[str, ...]) -> str:
    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in path)


def append_unique_note(notes: Any, note: str) -> list[str]:
    result = [str(item) for item in as_list(notes)]
    if note not in result:
        result.append(note)
    return result


def truth_artifact_path(repo_root: Path, value: Any) -> str | None:
    if not value:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = repo_root / path
    return str(path)


def add_update(
    *,
    current_truth: dict[str, Any],
    proposed: dict[str, Any],
    updates: list[dict[str, Any]],
    path: tuple[str, ...],
    value: Any,
    reason: str,
) -> None:
    before = get_path(current_truth, path)
    if before == value:
        return
    set_path(proposed, path, value)
    updates.append(
        {
            "path": pointer(path),
            "before": before,
            "after": value,
            "reason": reason,
        }
    )


def target_identity(current_truth: dict[str, Any], dashboard: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    return as_mapping(current_truth.get("target")), as_mapping(dashboard.get("target"))


def validate_target_identity(current_truth: dict[str, Any], dashboard: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    truth_target, dashboard_target = target_identity(current_truth, dashboard)
    for field in ("processName", "processId", "targetWindowHandle", "processStartUtc", "moduleBase"):
        truth_value = truth_target.get(field)
        dashboard_value = dashboard_target.get(field)
        if truth_value is None or dashboard_value is None:
            blockers.append(f"target-identity-field-missing:{field}")
            continue
        if str(truth_value) != str(dashboard_value):
            blockers.append(f"target-identity-mismatch:{field}:truth={truth_value};dashboard={dashboard_value}")
    return blockers


def validate_dashboard_safety(dashboard: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    safety = as_mapping(dashboard.get("safety"))
    source_safety = as_mapping(dashboard.get("sourceSafety"))
    forbidden_true_flags = (
        "movementSent",
        "inputSent",
        "targetMemoryBytesRead",
        "targetMemoryBytesWritten",
        "proofPromotion",
        "actorChainPromotion",
        "facingPromotion",
        "gitMutation",
        "providerWrites",
        "x64dbgAttach",
    )
    for flag in forbidden_true_flags:
        if bool(safety.get(flag)):
            blockers.append(f"dashboard-safety-flag-true:{flag}")
    if not bool(safety.get("readOnlyArtifactIndex", False)):
        blockers.append("dashboard-not-read-only-artifact-index")
    if bool(source_safety.get("familySnapshotMovementSent")):
        # Historical source movement is allowed as evidence, but it must stay explicit.
        pass
    return blockers


def build_proposed_current_truth(
    *,
    repo_root: Path,
    current_truth: dict[str, Any],
    dashboard: dict[str, Any],
    generated_at_utc: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    proposed = copy.deepcopy(current_truth)
    updates: list[dict[str, Any]] = []
    target = as_mapping(dashboard.get("target"))
    sources = as_mapping(dashboard.get("sources"))
    coordinate_source = as_mapping(sources.get("coordinateReadback"))
    nav_state_source = as_mapping(sources.get("navState"))
    candidates = as_mapping(dashboard.get("candidates"))
    promoted = as_mapping(candidates.get("promotedCoordinate"))
    coordinate = as_mapping(promoted.get("coordinate"))
    latest_readback_at = promoted.get("latestReadbackAtUtc")
    latest_readback_json = truth_artifact_path(
        repo_root,
        promoted.get("latestReadbackJson") or coordinate_source.get("path"),
    )
    latest_nav_state_json = truth_artifact_path(repo_root, nav_state_source.get("path"))
    process_id = target.get("processId")
    hwnd = target.get("targetWindowHandle")
    verification_source = (
        f"Dry-run refresh plan from navigation pointer discovery dashboard generated {dashboard.get('generatedAtUtc')}. "
        f"Latest no-input static-chain readback for exact PID {process_id} / HWND {hwnd} passed at "
        f"{latest_readback_at}. API-now status is not refreshed by this planner; this planner performs no "
        "proof/facing/actor promotion."
    )
    readback_status = promoted.get("status") or "promoted-static-coordinate-resolver-readback-passed"
    live_status = f"current-pid-{process_id}-static-readback-refreshed-api-now-not-refreshed-by-plan"
    live_source = (
        "Promoted static owner coordinate resolver latest no-input readback. "
        "RRAPICOORD/API-now evidence remains the previous recorded validation unless separately refreshed."
    )
    live_view = (
        f"Current target PID {process_id} / HWND {hwnd} has a proposed tracked-truth refresh from "
        f"static-chain readback at {latest_readback_at}; no proof promotion or live input is performed."
    )
    coordinate_with_time = dict(coordinate)
    coordinate_with_time["recordedAtUtc"] = latest_readback_at
    note = (
        f"Dry-run current-truth refresh plan generated {generated_at_utc}; applying tracked truth remains a separate gate."
    )

    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("updatedAtUtc",),
        value=generated_at_utc,
        reason="mark proposed tracked truth refresh time",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("target", "lastVerifiedUtc"),
        value=latest_readback_at,
        reason="latest exact-target static-chain coordinate readback time",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("target", "verificationSource"),
        value=verification_source,
        reason="record dry-run source and non-promotion boundary",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("liveReferenceSurface", "status"),
        value=live_status,
        reason="separate static readback freshness from API-now/proof freshness",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("liveReferenceSurface", "source"),
        value=live_source,
        reason="avoid claiming fresh API-now evidence from a readback-only plan",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("liveReferenceSurface", "view"),
        value=live_view,
        reason="summarize exact-target readback plan without promotion",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("liveReferenceSurface", "currentCoordinateFromStaticChainCandidate"),
        value=coordinate_with_time,
        reason="latest promoted coordinate resolver readback coordinate",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("liveReferenceSurface", "notes"),
        value=append_unique_note(get_path(current_truth, ("liveReferenceSurface", "notes")), note),
        reason="preserve dry-run/apply boundary in tracked notes",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("staticChainStatus", "status"),
        value=readback_status,
        reason="align coordinate resolver status with latest dashboard promoted-coordinate status",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("staticChainStatus", "primaryCandidate", "ownerAddress"),
        value=promoted.get("ownerAddress"),
        reason="latest owner address for current target epoch",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("staticChainStatus", "primaryCandidate", "coordinateAddress"),
        value=promoted.get("coordinateAddress"),
        reason="latest coordinate address for current target epoch",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("staticChainStatus", "primaryCandidate", "coordinate"),
        value=coordinate,
        reason="latest promoted coordinate resolver readback",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("staticChainStatus", "primaryCandidate", "latestPromotedReadbackArtifact"),
        value=latest_readback_json,
        reason="latest artifact for promoted static resolver readback",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("staticChainStatus", "primaryCandidate", "latestCurrentReadbackArtifact"),
        value=latest_readback_json,
        reason="latest exact-target static-chain coordinate readback artifact",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("staticChainStatus", "primaryCandidate", "latestCurrentReadbackAtUtc"),
        value=latest_readback_at,
        reason="latest exact-target static-chain coordinate readback time",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("canonicalArtifacts", "latestCurrentPidStaticOwnerReadback"),
        value=latest_readback_json,
        reason="latest exact-target static-owner readback artifact",
    )
    add_update(
        current_truth=current_truth,
        proposed=proposed,
        updates=updates,
        path=("canonicalArtifacts", "latestCurrentPidNavStateReadback"),
        value=latest_nav_state_json,
        reason="latest exact-target nav-state readback artifact",
    )
    return proposed, updates


def build_current_truth_refresh_plan(
    repo_root: Path,
    *,
    current_truth_json: Path | None = None,
    dashboard_json: Path | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    generated = generated_at_utc or utc_iso()
    truth_path = repo_root / (current_truth_json or DEFAULT_CURRENT_TRUTH_JSON)
    dashboard_path = repo_root / (dashboard_json or DEFAULT_DASHBOARD_JSON)
    errors: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    current_truth: dict[str, Any] | None = None
    dashboard: dict[str, Any] | None = None
    try:
        current_truth = load_json_object(truth_path)
    except CurrentTruthRefreshPlanError as exc:
        errors.append(f"current-truth-load-failed:{preview_text(str(exc), max_lines=1, max_chars=500)}")
    try:
        dashboard = load_json_object(dashboard_path)
    except CurrentTruthRefreshPlanError as exc:
        errors.append(f"navigation-dashboard-load-failed:{preview_text(str(exc), max_lines=1, max_chars=500)}")

    if current_truth is None or dashboard is None:
        status = "failed"
        proposed: dict[str, Any] | None = None
        updates: list[dict[str, Any]] = []
        diff_text = ""
    else:
        if dashboard.get("kind") != "riftreader-navigation-pointer-discovery-status":
            blockers.append(f"navigation-dashboard-kind-unexpected:{dashboard.get('kind')}")
        if dashboard.get("status") != "passed":
            blockers.append(f"navigation-dashboard-not-passed:{dashboard.get('status')}")
        blockers.extend(validate_target_identity(current_truth, dashboard))
        blockers.extend(validate_dashboard_safety(dashboard))

        sources = as_mapping(dashboard.get("sources"))
        for source_key in ("coordinateReadback", "navState"):
            source = as_mapping(sources.get(source_key))
            freshness = as_mapping(source.get("freshness"))
            if source.get("status") != "passed":
                blockers.append(f"{source_key}-not-passed:{source.get('status')}")
            if freshness.get("status") != "fresh":
                blockers.append(f"{source_key}-not-fresh:{freshness.get('status')}")

        candidates = as_mapping(dashboard.get("candidates"))
        promoted = as_mapping(candidates.get("promotedCoordinate"))
        current_facing = as_mapping(current_truth.get("staticOwnerFacing"))
        if not promoted:
            blockers.append("promoted-coordinate-missing")
        else:
            if promoted.get("candidateOnly") is not False:
                blockers.append("promoted-coordinate-not-marked-promoted")
            if promoted.get("latestReadbackStatus") != "passed":
                blockers.append(f"promoted-coordinate-readback-not-passed:{promoted.get('latestReadbackStatus')}")
            if not isinstance(promoted.get("coordinate"), dict):
                blockers.append("promoted-coordinate-missing-coordinate")
            if not promoted.get("latestReadbackAtUtc"):
                blockers.append("promoted-coordinate-missing-latest-readback-time")
            if not promoted.get("ownerAddress") or not promoted.get("coordinateAddress"):
                blockers.append("promoted-coordinate-missing-current-addresses")

        freshness = as_mapping(dashboard.get("freshness"))
        stale_sources = as_list(freshness.get("staleSources"))
        if "currentTruth" not in [str(item) for item in stale_sources]:
            warnings.append("current-truth-not-marked-stale-by-dashboard")
        if any(str(item) in {"coordinateReadback", "navState"} for item in stale_sources):
            blockers.append("dashboard-has-stale-readback-source")
        if as_mapping(candidates.get("candidateFacingTarget")).get("promotionAllowed"):
            blockers.append("facing-target-promotion-unexpectedly-allowed")
        if as_mapping(candidates.get("candidateTurnRate")).get("promotionAllowed"):
            blockers.append("turn-rate-promotion-unexpectedly-allowed")
        if current_facing.get("promotionAllowed") is True and as_mapping(candidates.get("candidateFacingTarget")).get(
            "candidateOnly"
        ):
            warnings.append("current-truth-staticOwnerFacing-already-promoted-dashboard-candidate-only-plan-does-not-change-it")

        if blockers:
            proposed = None
            updates = []
            diff_text = ""
            status = "blocked"
        else:
            proposed, updates = build_proposed_current_truth(
                repo_root=repo_root,
                current_truth=current_truth,
                dashboard=dashboard,
                generated_at_utc=generated,
            )
            diff_text = build_unified_diff(
                current_truth,
                proposed,
                fromfile=repo_rel(repo_root, truth_path) or str(truth_path),
                tofile="proposed-current-truth.json",
            )
            status = "passed"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-current-truth-refresh-plan",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": generated,
        "status": status,
        "verdict": "dry-run-current-truth-refresh-plan-ready" if status == "passed" else status,
        "repoRoot": str(repo_root),
        "inputs": {
            "currentTruthJson": repo_rel(repo_root, truth_path),
            "navigationDashboardJson": repo_rel(repo_root, dashboard_path),
        },
        "target": as_mapping(dashboard).get("target") if dashboard else {},
        "updates": updates,
        "updateCount": len(updates),
        "proposedCurrentTruth": proposed,
        "diffPreview": preview_text(diff_text, max_lines=120, max_chars=12000),
        "blockers": blockers,
        "warnings": warnings,
        "errors": errors,
        "safety": {
            **safety_flags(),
            "dryRunOnly": True,
            "trackedTruthWritten": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "facingPromotion": False,
        },
        "artifacts": {},
        "next": {
            "recommendedAction": (
                "Review the ignored plan artifacts. Apply a tracked current-truth update only after explicitly opening "
                "the truth-refresh gate; do not treat this plan as proof promotion."
                if status == "passed"
                else "Resolve blockers before planning a tracked current-truth refresh."
            ),
            "requiresExplicitApprovalForApply": True,
        },
    }


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# RiftReader Current Truth Refresh Plan",
        "",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Update count: `{summary.get('updateCount')}`",
        f"- Apply requires explicit approval: `{as_mapping(summary.get('next')).get('requiresExplicitApprovalForApply')}`",
        "",
        "## Inputs",
        "",
    ]
    for key, value in as_mapping(summary.get("inputs")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Updates", "", "| Path | Reason |", "|---|---|"])
    for update in as_list(summary.get("updates")):
        item = as_mapping(update)
        lines.append(f"| `{item.get('path')}` | {item.get('reason')} |")
    if not as_list(summary.get("updates")):
        lines.append("| none | none |")
    lines.extend(["", "## Blockers", ""])
    for blocker in as_list(summary.get("blockers")) or ["none"]:
        lines.append(f"- `{blocker}`")
    lines.extend(["", "## Warnings", ""])
    for warning in as_list(summary.get("warnings")) or ["none"]:
        lines.append(f"- `{warning}`")
    lines.extend(["", "## Artifacts", ""])
    for key, value in as_mapping(summary.get("artifacts")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Diff preview",
            "",
            "```diff",
            str(summary.get("diffPreview") or ""),
            "```",
            "",
            "## Next action",
            "",
            str(as_mapping(summary.get("next")).get("recommendedAction") or "none"),
            "",
            "## Safety",
            "",
            "| Flag | Value |",
            "|---|---:|",
        ]
    )
    for key, value in as_mapping(summary.get("safety")).items():
        lines.append(f"| `{key}` | `{value}` |")
    return "\n".join(lines)


def write_outputs(repo_root: Path, summary: dict[str, Any], output_dir: Path | None = None) -> dict[str, str]:
    base = output_dir or DEFAULT_OUTPUT_DIR
    if not base.is_absolute():
        base = repo_root / base
    base.mkdir(parents=True, exist_ok=True)
    summary_json = base / "summary.json"
    summary_md = base / "summary.md"
    proposed_json = base / "proposed-current-truth.json"
    diff_path = base / "proposed-current-truth.diff"
    artifacts = {
        "outputDirectory": repo_rel(repo_root, base) or str(base),
        "summaryJson": repo_rel(repo_root, summary_json) or str(summary_json),
        "summaryMarkdown": repo_rel(repo_root, summary_md) or str(summary_md),
        "proposedCurrentTruthJson": repo_rel(repo_root, proposed_json) or str(proposed_json),
        "proposedCurrentTruthDiff": repo_rel(repo_root, diff_path) or str(diff_path),
    }
    summary["artifacts"] = artifacts
    summary_json.write_text(json_text(summary), encoding="utf-8")
    summary_md.write_text(build_markdown(summary) + "\n", encoding="utf-8")
    if isinstance(summary.get("proposedCurrentTruth"), dict):
        proposed_json.write_text(json_text(summary["proposedCurrentTruth"]), encoding="utf-8")
        diff_path.write_text(str(summary.get("diffPreview") or ""), encoding="utf-8")
    else:
        proposed_json.write_text("", encoding="utf-8")
        diff_path.write_text("", encoding="utf-8")
    return artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a dry-run current-truth refresh plan.")
    parser.add_argument("--repo-root", default=None, help="RiftReader repo root; defaults to auto-detect.")
    parser.add_argument("--current-truth-json", default=str(DEFAULT_CURRENT_TRUTH_JSON))
    parser.add_argument("--dashboard-json", default=str(DEFAULT_DASHBOARD_JSON))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--write", action="store_true", help="Write ignored plan artifacts.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    summary = build_current_truth_refresh_plan(
        repo_root,
        current_truth_json=Path(args.current_truth_json),
        dashboard_json=Path(args.dashboard_json),
    )
    if args.write:
        write_outputs(repo_root, summary, Path(args.output_dir))
    if args.json:
        print(json_text(summary), end="")
    else:
        print(build_markdown(summary))
    if summary["status"] == "failed":
        return 1
    if summary["status"] == "blocked":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
