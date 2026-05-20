from __future__ import annotations

import argparse
import glob
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .character_login_resilience_plan import identities_match, target_identity
from .character_select_automation_plan import normalize_name
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
CONTRACT_KIND = "riftreader-character-login-executor-contract"


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def latest_plan_summary(repo_root: Path) -> Path | None:
    pattern = str(
        repo_root
        / ".riftreader-local"
        / "character-login-resilience-plan"
        / "run-*"
        / "character-login-resilience-plan-summary.json"
    )
    matches = [Path(item) for item in glob.glob(pattern)]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime).resolve()


def load_json_object(path: Path, errors: list[dict[str, str]]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("JSON root is not an object")
        return data
    except Exception as exc:  # noqa: BLE001 - CLI should preserve durable error details.
        errors.append({"type": type(exc).__name__, "message": str(exc), "path": str(path)})
        return {}


def expected_approval_token(plan: dict[str, Any]) -> str | None:
    selection = plan.get("selection") if isinstance(plan.get("selection"), dict) else {}
    target = plan.get("currentTarget") if isinstance(plan.get("currentTarget"), dict) else {}
    character = str(selection.get("targetCharacter") or "").strip()
    pid = target.get("processId")
    hwnd = str(target.get("windowHandle") or "").strip()
    if not character or not pid or not hwnd:
        return None
    if hwnd.lower().startswith("0x"):
        hwnd = "0x" + hwnd[2:].upper()
    return f"ENTER-WORLD:{character}:{pid}:{hwnd}"


def build_contract(
    *,
    repo_root: Path,
    output_root: Path,
    plan_path: Path | None,
    current_truth_path: Path,
    current_proof_path: Path,
    approval_token: str | None,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    blockers: list[str] = []
    warnings: list[str] = []

    if plan_path is None:
        blockers.append("missing-login-resilience-plan")
        plan = {}
    elif not plan_path.exists():
        blockers.append("login-resilience-plan-not-found")
        plan = {}
    else:
        plan = load_json_object(plan_path, errors)
    truth = load_json_object(current_truth_path, errors) if current_truth_path.exists() else {}
    proof = load_json_object(current_proof_path, errors) if current_proof_path.exists() else {}
    if not truth:
        blockers.append("missing-current-truth")
    if not proof:
        blockers.append("missing-current-proof")

    if plan.get("status") != "planned":
        blockers.append(f"login-plan-not-planned:{plan.get('status')}")
    readiness = plan.get("readiness") if isinstance(plan.get("readiness"), dict) else {}
    if readiness.get("canPlanLogin") is not True:
        blockers.append("login-plan-readiness-false")
    if readiness.get("canExecuteLiveActionsNow") is True:
        blockers.append("login-plan-unexpectedly-allows-live-actions")

    screen = plan.get("screenState") if isinstance(plan.get("screenState"), dict) else {}
    if screen.get("classification") != "character-selection-not-in-world":
        blockers.append("login-plan-not-character-select")
    if screen.get("worldEntryPermittedNow") is True:
        warnings.append("source-environment-world-entry-permitted")
    else:
        blockers.append("world-entry-not-permitted-by-source-environment")

    selection = plan.get("selection") if isinstance(plan.get("selection"), dict) else {}
    if selection.get("selectedAlready") is not True:
        blockers.append("target-character-not-selected")
    target_character = str(selection.get("targetCharacter") or "").strip()
    if normalize_name(target_character) != normalize_name(selection.get("selectedCharacter")):
        blockers.append("target-character-selection-mismatch")

    plan_target = plan.get("currentTarget") if isinstance(plan.get("currentTarget"), dict) else {}
    truth_target = target_identity(truth) if truth else {}
    proof_target = target_identity(proof) if proof else {}
    if truth and not identities_match(plan_target, truth_target):
        blockers.append("login-plan-target-does-not-match-current-truth")
    if proof and not identities_match(plan_target, proof_target):
        blockers.append("login-plan-target-does-not-match-current-proof")

    play = readiness.get("playButton") if isinstance(readiness.get("playButton"), dict) else {}
    if play.get("clickPoint") != [517, 343]:
        blockers.append("unexpected-play-click-point")
    if play.get("bbox") != [476, 329, 558, 357]:
        blockers.append("unexpected-play-bbox")

    expected_token = expected_approval_token(plan)
    approval_provided = str(approval_token or "").strip()
    approval_matches = bool(expected_token and approval_provided == expected_token)
    if not approval_matches:
        blockers.append("explicit-world-entry-approval-token-missing-or-mismatched")

    executor_may_click_play = not errors and not blockers and approval_matches
    status = "failed" if errors else "ready-for-executor" if executor_may_click_play else "blocked"
    summary_json = output_root / "character-login-executor-contract-summary.json"
    summary_markdown = output_root / "character-login-executor-contract.md"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": CONTRACT_KIND,
        "status": status,
        "generatedAtUtc": utc_iso(),
        "blockers": blockers,
        "warnings": warnings,
        "errors": errors,
        "input": {
            "planSummary": str(plan_path.resolve()) if plan_path else None,
            "currentTruth": str(current_truth_path.resolve()),
            "currentProof": str(current_proof_path.resolve()),
            "approvalTokenProvided": bool(approval_provided),
        },
        "expectedApprovalToken": expected_token,
        "approval": {
            "required": True,
            "provided": bool(approval_provided),
            "matches": approval_matches,
            "note": "This validator does not click. A future executor must require this exact token again in the same run.",
        },
        "target": plan_target,
        "selection": selection,
        "playButton": play,
        "executorContract": {
            "mayClickPlay": executor_may_click_play,
            "mustRecaptureBeforeClick": True,
            "mustUseBoundClientCoordinates": True,
            "maxClicks": 1,
            "postClickRequiredStates": [
                "wait-for-world-load",
                "rediscover exact PID/HWND",
                "sample fresh API/runtime coordinates",
                "run same-target ProofOnly",
                "keep movement blocked unless ProofOnly passes",
            ],
            "failClosedOn": [
                "target mismatch",
                "geometry mismatch",
                "missing screenshot",
                "target character not selected",
                "approval token mismatch",
                "world load timeout",
                "ProofOnly stale or failed",
            ],
        },
        "safety": {
            "planOnly": True,
            "willExecuteLiveActions": False,
            "movementSent": False,
            "keyInputSent": False,
            "mouseClickSent": False,
            "worldEntryClicked": False,
            "cheatEngineUsed": False,
            "x64dbgAttachStarted": False,
            "savedVariablesUsedAsLiveTruth": False,
            "providerWrites": False,
            "gitMutation": False,
        },
        "artifacts": {
            "summaryJson": str(summary_json.resolve()),
            "summaryMarkdown": str(summary_markdown.resolve()),
        },
        "next": {
            "recommendedAction": "Do not execute live clicks unless this contract is ready-for-executor and the future executor also revalidates target/screenshot/approval in the same run.",
        },
    }


def render_markdown(summary: dict[str, Any]) -> str:
    blockers = summary.get("blockers") or []
    warnings = summary.get("warnings") or []
    approval = summary.get("approval") if isinstance(summary.get("approval"), dict) else {}
    contract = summary.get("executorContract") if isinstance(summary.get("executorContract"), dict) else {}
    lines = [
        "# Character login executor contract",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Approval provided: `{str(approval.get('provided')).lower()}`",
        f"- Approval matches: `{str(approval.get('matches')).lower()}`",
        f"- May click Play: `{str(contract.get('mayClickPlay')).lower()}`",
        "",
        "## Required approval token",
        "",
        f"`{summary.get('expectedApprovalToken')}`",
        "",
        "## Blockers",
        "",
    ]
    lines.extend([f"- `{item}`" for item in blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- `{item}`" for item in warnings] or ["- none"])
    lines.extend(
        [
            "",
            "This artifact validates the future executor contract only. It never clicks Play, sends keys, enters world, or enables movement.",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a future character-login executor contract.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--plan-summary", type=Path)
    parser.add_argument("--current-truth", type=Path, default=Path("docs/recovery/current-truth.json"))
    parser.add_argument("--current-proof", type=Path, default=Path("docs/recovery/current-proof-anchor-readback.json"))
    parser.add_argument("--approval-token")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_root = (
        args.output_root.resolve()
        if args.output_root
        else (repo_root / ".riftreader-local" / "character-login-executor-contract" / f"run-{utc_stamp()}").resolve()
    )
    output_root.mkdir(parents=True, exist_ok=True)
    plan_path = args.plan_summary.resolve() if args.plan_summary else latest_plan_summary(repo_root)
    current_truth = args.current_truth if args.current_truth.is_absolute() else repo_root / args.current_truth
    current_proof = args.current_proof if args.current_proof.is_absolute() else repo_root / args.current_proof
    summary = build_contract(
        repo_root=repo_root,
        output_root=output_root,
        plan_path=plan_path,
        current_truth_path=current_truth,
        current_proof_path=current_proof,
        approval_token=args.approval_token,
    )
    summary_json = output_root / "character-login-executor-contract-summary.json"
    summary_markdown = output_root / "character-login-executor-contract.md"
    summary["artifacts"]["summaryJson"] = str(summary_json.resolve())
    summary["artifacts"]["summaryMarkdown"] = str(summary_markdown.resolve())
    write_json(summary_json, summary)
    write_text_atomic(summary_markdown, render_markdown(summary))
    latest = repo_root / ".riftreader-local" / "character-login-executor-contract" / "latest-run.txt"
    write_text_atomic(latest, str(output_root.resolve()))
    if args.json:
        print(json.dumps(summary, indent=2))
    if summary.get("status") == "ready-for-executor":
        return 0
    if summary.get("status") == "blocked":
        return 2
    return 1
