#!/usr/bin/env python3
"""Validate and optionally apply a dry-run current-truth refresh proposal.

The paired planner remains non-applying by design.  This helper is the explicit
apply gate: it validates the latest ignored proposal, records a backup and
apply summary, and only writes `docs/recovery/current-truth.json` when `--apply`
is supplied.

It never sends live input, reads/writes target memory, attaches debuggers, writes
provider repositories, mutates Git refs, or performs proof/facing/actor
promotion.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, repo_rel, safety_flags, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, repo_rel, safety_flags, utc_iso


SCHEMA_VERSION = 1
TOOL_VERSION = "riftreader-current-truth-refresh-apply-v0.1.0"
DEFAULT_PLAN_SUMMARY = Path(".riftreader-local") / "current-truth-refresh-plan" / "latest" / "summary.json"
DEFAULT_CURRENT_TRUTH_JSON = Path("docs") / "recovery" / "current-truth.json"
DEFAULT_OUTPUT_DIR = Path(".riftreader-local") / "current-truth-refresh-apply" / "latest"
FORBIDDEN_PLAN_SAFETY_FLAGS = {
    "movementSent",
    "inputSent",
    "reloaduiSent",
    "screenshotKeySent",
    "x64dbgAttach",
    "providerWrites",
    "gitMutation",
    "targetMemoryBytesWritten",
    "proofPromotion",
    "actorChainPromotion",
    "facingPromotion",
}


class CurrentTruthRefreshApplyError(RuntimeError):
    """Raised for controlled apply helper failures."""


def safe_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def resolve_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise CurrentTruthRefreshApplyError(f"malformed-json:{path}:{exc}") from exc
    if not isinstance(data, dict):
        raise CurrentTruthRefreshApplyError(f"json-root-not-object:{path}")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def annotate_applied_current_truth(
    proposed: dict[str, Any],
    *,
    applied_at_utc: str,
    plan_generated_at_utc: Any,
) -> dict[str, Any]:
    """Return tracked current-truth payload annotated as applied, not proposed."""

    applied = copy.deepcopy(proposed)
    live_surface = safe_mapping(applied.get("liveReferenceSurface"))
    view = live_surface.get("view")
    if isinstance(view, str):
        live_surface["view"] = view.replace("has a proposed tracked-truth refresh", "has an applied tracked-truth refresh")
    applied_warning = (
        f"Tracked current-truth refresh applied {applied_at_utc} from dry-run plan generated "
        f"{plan_generated_at_utc}; no proof/facing/actor promotion was performed by the apply helper."
    )

    for note_key in ("warnings", "notes"):
        live_notes = safe_list(live_surface.get(note_key))
        for index, item in enumerate(live_notes):
            if isinstance(item, str) and item.startswith("Dry-run current-truth refresh plan generated "):
                live_notes[index] = applied_warning
                break
        if live_notes:
            live_surface[note_key] = live_notes

    warnings = safe_list(applied.get("currentWarnings"))
    replaced = False
    for index, item in enumerate(warnings):
        if isinstance(item, str) and item.startswith("Dry-run current-truth refresh plan generated "):
            warnings[index] = applied_warning
            replaced = True
            break
    if not replaced:
        warnings.append(applied_warning)
    applied["currentWarnings"] = warnings
    return applied


def same_target_identity(summary_target: dict[str, Any], proposed_target: dict[str, Any]) -> bool:
    for key in ("processName", "processId", "targetWindowHandle", "processStartUtc", "moduleBase"):
        if str(summary_target.get(key)) != str(proposed_target.get(key)):
            return False
    return True


def validate_plan_summary(plan: dict[str, Any], proposed: dict[str, Any], current_truth: dict[str, Any]) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if plan.get("kind") != "riftreader-current-truth-refresh-plan":
        blockers.append(f"plan-kind-unexpected:{plan.get('kind')}")
    if plan.get("status") != "passed":
        blockers.append(f"plan-status-not-passed:{plan.get('status')}")
    if safe_list(plan.get("blockers")):
        blockers.extend(f"plan-blocker:{item}" for item in safe_list(plan.get("blockers")))
    if safe_list(plan.get("errors")):
        blockers.extend(f"plan-error:{item}" for item in safe_list(plan.get("errors")))

    plan_safety = safe_mapping(plan.get("safety"))
    for flag in sorted(FORBIDDEN_PLAN_SAFETY_FLAGS):
        if plan_safety.get(flag):
            blockers.append(f"plan-forbidden-safety-flag:{flag}")
    if plan_safety.get("noCheatEngine") is not True:
        blockers.append("plan-noCheatEngine-not-true")
    if plan_safety.get("dryRunOnly") is not True:
        blockers.append("plan-dryRunOnly-not-true")
    if plan_safety.get("trackedTruthWritten") is not False:
        blockers.append("plan-trackedTruthWritten-not-false")
    if plan_safety.get("applyFlagSent") is not False:
        blockers.append("plan-applyFlagSent-not-false")

    if proposed.get("kind") != "riftreader-current-truth":
        blockers.append(f"proposed-current-truth-kind-unexpected:{proposed.get('kind')}")
    if current_truth.get("kind") != "riftreader-current-truth":
        blockers.append(f"tracked-current-truth-kind-unexpected:{current_truth.get('kind')}")
    summary_target = safe_mapping(plan.get("target"))
    proposed_target = safe_mapping(proposed.get("target"))
    if not same_target_identity(summary_target, proposed_target):
        blockers.append("proposed-target-does-not-match-plan-target")
    static_status = safe_mapping(proposed.get("staticChainStatus"))
    latest_api = safe_mapping(static_status.get("latestApiNowValidation"))
    api_status = str(latest_api.get("status") or latest_api.get("currentApiNowStatus") or "")
    if not api_status.startswith("passed-current-pid-"):
        blockers.append(f"proposed-api-now-not-passed:{api_status}")
    movement_gate = safe_mapping(proposed.get("movementGate"))
    if movement_gate.get("allowed") is not True:
        warnings.append(f"proposed-movement-gate-not-allowed:{movement_gate.get('status')}")

    # This apply helper may preserve historical facing metadata, but must not be
    # the surface that newly promotes facing/actor/proof truth.
    if plan_safety.get("facingPromotion") is False:
        warnings.append("no-facing-promotion-performed-by-apply-helper")
    return blockers, warnings


def build_summary(args: argparse.Namespace, repo_root: Path) -> tuple[dict[str, Any], int]:
    output_dir = resolve_path(repo_root, Path(args.output_dir))
    plan_summary_path = resolve_path(repo_root, Path(args.summary_json))
    current_truth_path = resolve_path(repo_root, Path(args.current_truth_json))
    generated = utc_iso()
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-current-truth-refresh-apply",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": generated,
        "status": "failed",
        "verdict": "current-truth-refresh-apply-not-run",
        "repoRoot": str(repo_root),
        "applyRequested": bool(args.apply),
        "inputs": {
            "planSummaryJson": repo_rel(repo_root, plan_summary_path),
            "currentTruthJson": repo_rel(repo_root, current_truth_path),
            "proposedCurrentTruthJson": None,
        },
        "hashes": {},
        "blockers": [],
        "warnings": [],
        "errors": [],
        "safety": {
            **safety_flags(),
            "dryRunOnly": not bool(args.apply),
            "trackedTruthWritten": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "facingPromotion": False,
        },
        "artifacts": {
            "outputDirectory": repo_rel(repo_root, output_dir),
            "summaryJson": repo_rel(repo_root, output_dir / "summary.json"),
            "summaryMarkdown": repo_rel(repo_root, output_dir / "summary.md"),
            "backupCurrentTruthJson": repo_rel(repo_root, output_dir / "current-truth-before-apply.json"),
        },
        "next": {
            "recommendedAction": "Review generated status/decision packets before further proof or movement work.",
        },
    }
    try:
        if not plan_summary_path.is_file():
            summary["blockers"].append(f"plan-summary-not-found:{plan_summary_path}")
            summary["status"] = "blocked"
            summary["verdict"] = "current-truth-refresh-apply-blocked"
            return summary, 2
        if not current_truth_path.is_file():
            summary["blockers"].append(f"current-truth-not-found:{current_truth_path}")
            summary["status"] = "blocked"
            summary["verdict"] = "current-truth-refresh-apply-blocked"
            return summary, 2

        plan = load_json_object(plan_summary_path)
        artifacts = safe_mapping(plan.get("artifacts"))
        proposed_path_text = args.proposed_current_truth_json or artifacts.get("proposedCurrentTruthJson")
        if not proposed_path_text:
            summary["blockers"].append("proposed-current-truth-json-missing")
            summary["status"] = "blocked"
            summary["verdict"] = "current-truth-refresh-apply-blocked"
            return summary, 2
        proposed_path = resolve_path(repo_root, Path(str(proposed_path_text)))
        summary["inputs"]["proposedCurrentTruthJson"] = repo_rel(repo_root, proposed_path)
        if not proposed_path.is_file():
            summary["blockers"].append(f"proposed-current-truth-json-not-found:{proposed_path}")
            summary["status"] = "blocked"
            summary["verdict"] = "current-truth-refresh-apply-blocked"
            return summary, 2

        proposed = load_json_object(proposed_path)
        current_truth = load_json_object(current_truth_path)
        blockers, warnings = validate_plan_summary(plan, proposed, current_truth)
        summary["blockers"].extend(blockers)
        summary["warnings"].extend(warnings)
        summary["target"] = safe_mapping(plan.get("target"))
        summary["plan"] = {
            "status": plan.get("status"),
            "verdict": plan.get("verdict"),
            "updateCount": len(safe_list(plan.get("updates"))),
            "generatedAtUtc": plan.get("generatedAtUtc"),
        }
        summary["hashes"] = {
            "trackedBeforeSha256": sha256_file(current_truth_path),
            "proposedSha256": sha256_file(proposed_path),
        }
        if summary["blockers"]:
            summary["status"] = "blocked"
            summary["verdict"] = "current-truth-refresh-apply-blocked"
            return summary, 2

        output_dir.mkdir(parents=True, exist_ok=True)
        backup_path = output_dir / "current-truth-before-apply.json"
        if args.apply:
            shutil.copy2(current_truth_path, backup_path)
            applied_truth = annotate_applied_current_truth(
                proposed,
                applied_at_utc=generated,
                plan_generated_at_utc=plan.get("generatedAtUtc"),
            )
            applied_text = json.dumps(applied_truth, indent=2) + "\n"
            current_truth_path.write_text(applied_text, encoding="utf-8")
            summary["status"] = "passed"
            summary["verdict"] = "current-truth-refresh-applied"
            summary["safety"]["applyFlagSent"] = True
            summary["safety"]["dryRunOnly"] = False
            summary["safety"]["trackedTruthWritten"] = True
            summary["hashes"]["appliedPayloadSha256"] = hashlib.sha256(applied_text.encode("utf-8")).hexdigest()
            summary["hashes"]["trackedAfterSha256"] = sha256_file(current_truth_path)
            exit_code = 0
        else:
            summary["status"] = "passed"
            summary["verdict"] = "current-truth-refresh-apply-dry-run-ready"
            summary["artifacts"]["backupCurrentTruthJson"] = None
            summary["next"][
                "recommendedAction"
            ] = "Run again with --apply after reviewing the validated proposal and current approval scope."
            exit_code = 0
        return summary, exit_code
    except Exception as exc:  # noqa: BLE001 - helper must report controlled summary.
        summary["status"] = "failed"
        summary["verdict"] = "current-truth-refresh-apply-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
        return summary, 1


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# RiftReader current-truth refresh apply",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Apply requested: `{summary.get('applyRequested')}`",
        "",
        "## Inputs",
        "",
    ]
    for key, value in safe_mapping(summary.get("inputs")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Plan", ""])
    for key, value in safe_mapping(summary.get("plan")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Hashes", ""])
    for key, value in safe_mapping(summary.get("hashes")).items():
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
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(repo_root: Path, summary: dict[str, Any], output_dir: Path) -> None:
    resolved = resolve_path(repo_root, output_dir)
    resolved.mkdir(parents=True, exist_ok=True)
    (resolved / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (resolved / "summary.md").write_text(build_markdown(summary), encoding="utf-8")


def compact(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "applyRequested": summary.get("applyRequested"),
        "target": summary.get("target"),
        "plan": summary.get("plan"),
        "hashes": summary.get("hashes", {}),
        "artifacts": summary.get("artifacts"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
        "safety": summary.get("safety", {}),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_PLAN_SUMMARY)
    parser.add_argument("--proposed-current-truth-json", type=Path)
    parser.add_argument("--current-truth-json", type=Path, default=DEFAULT_CURRENT_TRUTH_JSON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--apply", action="store_true", help="Write proposed current-truth JSON to the tracked current-truth file.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root(Path.cwd())
    summary, exit_code = build_summary(args, repo_root)
    write_outputs(repo_root, summary, Path(args.output_dir))
    if args.json:
        print(json.dumps(compact(summary), indent=2, sort_keys=True))
    else:
        print(build_markdown(summary), end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
