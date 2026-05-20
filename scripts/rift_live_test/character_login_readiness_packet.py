from __future__ import annotations

import argparse
import glob
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .character_login_executor_contract import expected_approval_token
from .character_login_resilience_plan import identities_match, target_identity
from .character_select_automation_plan import (
    CHARACTER_SELECT_CLASSIFICATION,
    normalize_name,
    repo_relative_or_absolute,
)
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
PACKET_KIND = "riftreader-character-login-readiness-packet"


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def newest_match(pattern: Path) -> Path | None:
    matches = [Path(item) for item in glob.glob(str(pattern))]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime).resolve()


def latest_environment_summary(repo_root: Path) -> Path | None:
    return newest_match(
        repo_root
        / ".riftreader-local"
        / "character-select-automation-env"
        / "run-*"
        / "character-select-automation-env-summary.json"
    )


def latest_select_plan_summary(repo_root: Path) -> Path | None:
    return newest_match(
        repo_root
        / ".riftreader-local"
        / "character-select-automation-plan"
        / "run-*"
        / "character-select-automation-plan-summary.json"
    )


def latest_resilience_plan_summary(repo_root: Path) -> Path | None:
    return newest_match(
        repo_root
        / ".riftreader-local"
        / "character-login-resilience-plan"
        / "run-*"
        / "character-login-resilience-plan-summary.json"
    )


def latest_executor_contract_summary(repo_root: Path) -> Path | None:
    return newest_match(
        repo_root
        / ".riftreader-local"
        / "character-login-executor-contract"
        / "run-*"
        / "character-login-executor-contract-summary.json"
    )


def resolve_repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def load_json_object(path: Path | None, errors: list[dict[str, str]], *, label: str) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("JSON root is not an object")
        return data
    except Exception as exc:  # noqa: BLE001 - packet must preserve durable diagnostic context.
        errors.append({"type": type(exc).__name__, "message": str(exc), "path": str(path), "label": label})
        return {}


def artifact_record(repo_root: Path, path: Path | None, *, label: str) -> dict[str, Any]:
    if path is None:
        return {"label": label, "path": None, "exists": False}
    exists = path.exists()
    mtime_utc = None
    age_seconds = None
    if exists:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        now = datetime.now(UTC)
        mtime_utc = mtime.isoformat(timespec="seconds").replace("+00:00", "Z")
        age_seconds = max(0.0, (now - mtime).total_seconds())
    return {
        "label": label,
        "path": str(path.resolve()),
        "repoPath": repo_relative_or_absolute(path, repo_root),
        "exists": exists,
        "lastWriteUtc": mtime_utc,
        "ageSeconds": age_seconds,
    }


def selected_character_name(env: dict[str, Any]) -> str | None:
    screen = env.get("screenState") if isinstance(env.get("screenState"), dict) else {}
    selected = str(screen.get("selectedCharacter") or "").strip()
    return selected or None


def visible_character_names(env: dict[str, Any]) -> list[str]:
    targets = env.get("targets") if isinstance(env.get("targets"), dict) else {}
    slots = targets.get("visibleCharacterSlots") if isinstance(targets.get("visibleCharacterSlots"), list) else []
    result: list[str] = []
    for slot in slots:
        if isinstance(slot, dict) and slot.get("name"):
            result.append(str(slot["name"]).strip())
    return result


def find_character_slot(env: dict[str, Any], character: str | None) -> dict[str, Any] | None:
    if not character:
        return None
    targets = env.get("targets") if isinstance(env.get("targets"), dict) else {}
    slots = targets.get("visibleCharacterSlots") if isinstance(targets.get("visibleCharacterSlots"), list) else []
    wanted = normalize_name(character)
    for slot in slots:
        if isinstance(slot, dict) and normalize_name(slot.get("name")) == wanted:
            return slot
    return None


def play_button(env: dict[str, Any], resilience: dict[str, Any]) -> dict[str, Any]:
    targets = env.get("targets") if isinstance(env.get("targets"), dict) else {}
    env_play = targets.get("playButton") if isinstance(targets.get("playButton"), dict) else {}
    readiness = resilience.get("readiness") if isinstance(resilience.get("readiness"), dict) else {}
    plan_play = readiness.get("playButton") if isinstance(readiness.get("playButton"), dict) else {}
    return env_play or plan_play


def append_identity_blockers(
    *,
    blockers: list[str],
    left_label: str,
    left: dict[str, Any],
    right_label: str,
    right: dict[str, Any],
) -> None:
    if not left or not right:
        return
    if not identities_match(left, right):
        blockers.append(f"{left_label}-target-does-not-match-{right_label}")


def classify_artifact_freshness(records: list[dict[str, Any]], *, warning_age_seconds: int) -> list[dict[str, Any]]:
    classifications: list[dict[str, Any]] = []
    for record in records:
        if not record.get("exists"):
            classifications.append({"label": record.get("label"), "classification": "missing"})
            continue
        age = record.get("ageSeconds")
        if isinstance(age, (int, float)) and age > warning_age_seconds:
            classifications.append(
                {
                    "label": record.get("label"),
                    "classification": "older-than-warning-threshold",
                    "ageSeconds": age,
                    "warningAgeSeconds": warning_age_seconds,
                }
            )
        else:
            classifications.append({"label": record.get("label"), "classification": "available"})
    return classifications


def build_packet(
    *,
    repo_root: Path,
    output_root: Path,
    env_summary_path: Path | None,
    select_plan_path: Path | None,
    resilience_plan_path: Path | None,
    executor_contract_path: Path | None,
    current_truth_path: Path,
    current_proof_path: Path,
    target_character: str | None,
    warning_age_seconds: int,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    data_blockers: list[str] = []
    execution_blockers: list[str] = []
    warnings: list[str] = []

    env = load_json_object(
        env_summary_path if env_summary_path and env_summary_path.exists() else None,
        errors,
        label="environment",
    )
    select_plan = load_json_object(
        select_plan_path if select_plan_path and select_plan_path.exists() else None,
        errors,
        label="select-plan",
    )
    resilience = load_json_object(
        resilience_plan_path if resilience_plan_path and resilience_plan_path.exists() else None,
        errors,
        label="resilience-plan",
    )
    contract = load_json_object(
        executor_contract_path if executor_contract_path and executor_contract_path.exists() else None,
        errors,
        label="executor-contract",
    )
    truth = load_json_object(current_truth_path if current_truth_path.exists() else None, errors, label="current-truth")
    proof = load_json_object(current_proof_path if current_proof_path.exists() else None, errors, label="current-proof")

    required_paths = {
        "environment-summary": env_summary_path,
        "resilience-plan": resilience_plan_path,
        "current-truth": current_truth_path,
        "current-proof": current_proof_path,
    }
    for label, path in required_paths.items():
        if path is None or not path.exists():
            data_blockers.append(f"missing-{label}")

    if select_plan_path is None or not select_plan_path.exists():
        warnings.append("missing-character-select-plan")
    if executor_contract_path is None or not executor_contract_path.exists():
        warnings.append("missing-executor-contract")

    if env and env.get("status") != "captured-read-only-character-select":
        data_blockers.append(f"environment-status-not-captured:{env.get('status')}")
    if resilience and resilience.get("status") != "planned":
        data_blockers.append(f"resilience-plan-not-planned:{resilience.get('status')}")
    if select_plan and select_plan.get("status") != "planned":
        warnings.append(f"select-plan-not-planned:{select_plan.get('status')}")
    if contract and contract.get("status") not in {"blocked", "ready-for-executor"}:
        warnings.append(f"executor-contract-unexpected-status:{contract.get('status')}")

    screen = env.get("screenState") if isinstance(env.get("screenState"), dict) else {}
    if screen.get("classification") != CHARACTER_SELECT_CLASSIFICATION:
        data_blockers.append("not-character-selection-screen")
    if screen.get("worldEntryPermittedNow") is not True:
        execution_blockers.append("world-entry-requires-explicit-current-run-approval")

    env_target = target_identity(env) if env else {}
    plan_target = target_identity(resilience, target_key="currentTarget") if resilience else {}
    truth_target = target_identity(truth) if truth else {}
    proof_target = target_identity(proof) if proof else {}
    append_identity_blockers(
        blockers=data_blockers,
        left_label="environment",
        left=env_target,
        right_label="current-truth",
        right=truth_target,
    )
    append_identity_blockers(
        blockers=data_blockers,
        left_label="environment",
        left=env_target,
        right_label="current-proof",
        right=proof_target,
    )
    append_identity_blockers(
        blockers=data_blockers,
        left_label="resilience-plan",
        left=plan_target,
        right_label="environment",
        right=env_target,
    )

    selected = selected_character_name(env)
    requested = str(target_character or selected or "").strip() or None
    slot = find_character_slot(env, requested)
    if requested is None:
        data_blockers.append("missing-target-character")
    elif slot is None:
        data_blockers.append("target-character-not-visible")
    selected_already = bool(
        slot and (slot.get("selected") is True or normalize_name(slot.get("name")) == normalize_name(selected))
    )
    if requested and not selected_already:
        execution_blockers.append("target-character-selection-requires-approved-click")

    contract_blockers = contract.get("blockers") if isinstance(contract.get("blockers"), list) else []
    for item in contract_blockers:
        text = str(item)
        if text not in execution_blockers:
            execution_blockers.append(text)

    proof_status = proof.get("status") if proof else None
    movement_gate = truth.get("movementGate") if isinstance(truth.get("movementGate"), dict) else {}
    if proof_status != "blocked-target-not-in-world":
        warnings.append(f"current-proof-status-not-character-select-blocker:{proof_status}")
    if movement_gate.get("allowed") is not False:
        data_blockers.append("movement-gate-not-explicitly-blocked")

    artifacts = {
        "environmentSummary": artifact_record(repo_root, env_summary_path, label="environment-summary"),
        "selectPlan": artifact_record(repo_root, select_plan_path, label="select-plan"),
        "resiliencePlan": artifact_record(repo_root, resilience_plan_path, label="resilience-plan"),
        "executorContract": artifact_record(repo_root, executor_contract_path, label="executor-contract"),
        "currentTruth": artifact_record(repo_root, current_truth_path, label="current-truth"),
        "currentProof": artifact_record(repo_root, current_proof_path, label="current-proof"),
    }
    freshness = classify_artifact_freshness(list(artifacts.values()), warning_age_seconds=warning_age_seconds)
    for item in freshness:
        if item.get("classification") == "older-than-warning-threshold":
            warnings.append(f"artifact-age-warning:{item.get('label')}")

    approval_token = contract.get("expectedApprovalToken") if isinstance(contract.get("expectedApprovalToken"), str) else None
    if approval_token is None and resilience:
        approval_token = expected_approval_token(resilience)

    env_artifacts = env.get("artifacts") if isinstance(env.get("artifacts"), dict) else {}
    play = play_button(env, resilience)
    retry_policy = resilience.get("retryPolicy") if isinstance(resilience.get("retryPolicy"), dict) else {}
    readiness = resilience.get("readiness") if isinstance(resilience.get("readiness"), dict) else {}

    status = "failed" if errors else "blocked" if data_blockers else "packet-ready"
    summary_json = output_root / "character-login-readiness-packet-summary.json"
    summary_markdown = output_root / "character-login-readiness-packet.md"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": PACKET_KIND,
        "status": status,
        "generatedAtUtc": utc_iso(),
        "dataBlockers": data_blockers,
        "executionBlockers": execution_blockers,
        "warnings": warnings,
        "errors": errors,
        "target": env_target or truth_target,
        "targetComparisons": {
            "environment": env_target,
            "resiliencePlan": plan_target,
            "currentTruth": truth_target,
            "currentProof": proof_target,
        },
        "screenState": {
            "classification": screen.get("classification"),
            "selectedCharacter": selected,
            "currentShard": screen.get("currentShard"),
            "worldEntryAvailableVisually": screen.get("worldEntryAvailableVisually"),
            "worldEntryPermittedNow": screen.get("worldEntryPermittedNow") is True,
        },
        "selection": {
            "targetCharacter": requested,
            "selectedCharacter": selected,
            "selectedAlready": selected_already,
            "targetSlot": slot,
            "visibleCharacters": visible_character_names(env),
        },
        "playButton": {
            "clickPoint": play.get("clickPoint"),
            "bbox": play.get("bbox"),
            "coordinateSpace": play.get("coordinateSpace", "client"),
            "source": "environment/resilience-plan",
        },
        "automationReadiness": {
            "canObserveCharacterSelect": status == "packet-ready",
            "canPlanCharacterLogin": status == "packet-ready" and readiness.get("canPlanLogin") is True,
            "canExecuteLiveActionsNow": False,
            "maySelectCharacterNow": False,
            "mayClickPlayNow": contract.get("status") == "ready-for-executor"
            and not data_blockers
            and not errors,
            "worldEntryApprovalRequired": True,
            "expectedApprovalToken": approval_token,
            "movementAllowed": False,
            "postWorldProofRequired": True,
        },
        "reloginPolicy": {
            "currentEpoch": env_target or truth_target,
            "maxReloginAttempts": retry_policy.get("maxReloginAttempts"),
            "backoffSeconds": retry_policy.get("backoffSeconds"),
            "discardOnCrash": [
                "PID/HWND-specific proof pointers",
                "absolute memory addresses",
                "stale screenshots/click coordinates unless geometry is reverified",
                "old approval tokens",
            ],
            "resumeAt": "detect-client",
            "stateMachine": resilience.get("stateMachine") if isinstance(resilience.get("stateMachine"), list) else [],
            "stateLog": resilience.get("stateLog") if isinstance(resilience.get("stateLog"), list) else [],
            "stopConditions": retry_policy.get("stopConditions"),
        },
        "futureExecutorContract": {
            "mustBindExactTarget": True,
            "mustRecaptureBeforeAnyClick": True,
            "mustUseClientCoordinates": True,
            "maxPlayClicks": 1,
            "requiresApprovalToken": approval_token,
            "postClickRequiredStates": [
                "wait for character-select screen transition",
                "rediscover exact PID/HWND/process start after world load",
                "collect fresh API/runtime coordinate truth",
                "run same-target ProofOnly",
                "keep movement blocked unless ProofOnly passes",
            ],
            "neverReuseAsCurrentTruth": [
                "prior PID 1948 in-world absolute coordinate address",
                "prior PID 60636 character-select HWND",
                "SavedVariables snapshots",
                "single-pose candidate evidence",
            ],
        },
        "evidence": {
            "freshness": freshness,
            "screenshot": env_artifacts.get("screenshot"),
            "annotatedScreenshot": env_artifacts.get("annotatedScreenshot"),
            "playButtonCrop": env_artifacts.get("playButtonCrop"),
            "characterListCrop": env_artifacts.get("characterListCrop"),
        },
        "commands": {
            "refreshEnvironment": (
                "scripts\\riftreader-character-select-env-capture.cmd "
                "--pid <PID> --hwnd <HWND> --process-start-utc <UTC> --module-base <BASE> --json"
            ),
            "refreshResiliencePlan": "scripts\\riftreader-character-login-resilience-plan.cmd --target-character ATANK --json",
            "validateExecutorContract": "scripts\\riftreader-character-login-executor-contract.cmd --json",
            "refreshReadinessPacket": "scripts\\riftreader-character-login-readiness-packet.cmd --target-character ATANK --json",
            "workflowStatus": "scripts\\riftreader-workflow-status.cmd --compact-json",
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
            **artifacts,
            "summaryJson": str(summary_json.resolve()),
            "summaryMarkdown": str(summary_markdown.resolve()),
        },
        "next": {
            "recommendedAction": (
                "If live world entry is explicitly approved later, rerun this packet immediately before a one-click executor. "
                "After world load, rediscover target and rerun ProofOnly before movement."
            )
        },
    }


def render_markdown(summary: dict[str, Any]) -> str:
    readiness = summary.get("automationReadiness") if isinstance(summary.get("automationReadiness"), dict) else {}
    selection = summary.get("selection") if isinstance(summary.get("selection"), dict) else {}
    target = summary.get("target") if isinstance(summary.get("target"), dict) else {}
    play = summary.get("playButton") if isinstance(summary.get("playButton"), dict) else {}
    relogin = summary.get("reloginPolicy") if isinstance(summary.get("reloginPolicy"), dict) else {}
    evidence = summary.get("evidence") if isinstance(summary.get("evidence"), dict) else {}
    data_blockers = summary.get("dataBlockers") or []
    execution_blockers = summary.get("executionBlockers") or []
    warnings = summary.get("warnings") or []
    lines = [
        "# Character login readiness packet",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Target: PID `{target.get('processId')}`, HWND `{target.get('windowHandle')}`",
        f"- Selected: `{selection.get('selectedCharacter')}`",
        f"- Target character: `{selection.get('targetCharacter')}`",
        f"- Play click point: `{play.get('clickPoint')}`",
        f"- Can plan login: `{str(readiness.get('canPlanCharacterLogin')).lower()}`",
        f"- Can execute live actions now: `{str(readiness.get('canExecuteLiveActionsNow')).lower()}`",
        f"- May click Play now: `{str(readiness.get('mayClickPlayNow')).lower()}`",
        f"- Movement allowed: `{str(readiness.get('movementAllowed')).lower()}`",
        "",
        "## Safety",
        "",
        "No click, key, movement, Cheat Engine, x64dbg attach, provider write, or Git mutation is performed by this packet.",
        "",
        "## Resume / relogin policy",
        "",
        f"- Resume state after crash/relaunch: `{relogin.get('resumeAt')}`",
        f"- Retry budget: `{relogin.get('maxReloginAttempts')}` attempts, backoff `{relogin.get('backoffSeconds')}` seconds",
        "- Old PID/HWND, stale screenshots, old approval tokens, and absolute addresses must be discarded after crash/relaunch.",
        "",
        "## Evidence",
        "",
        f"- Screenshot: `{evidence.get('screenshot')}`",
        f"- Annotated screenshot: `{evidence.get('annotatedScreenshot')}`",
        f"- Play crop: `{evidence.get('playButtonCrop')}`",
        "",
        "## Data blockers",
        "",
    ]
    lines.extend([f"- `{item}`" for item in data_blockers] or ["- none"])
    lines.extend(["", "## Execution blockers", ""])
    lines.extend([f"- `{item}`" for item in execution_blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- `{item}`" for item in warnings] or ["- none"])
    lines.extend(
        [
            "",
            "## Required future approval token",
            "",
            f"`{readiness.get('expectedApprovalToken')}`",
            "",
            "This token is a contract value, not approval by itself. A future executor must require explicit current-run approval and revalidate target/screenshot before any click.",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an input-free readiness packet for RIFT character login/relogin automation."
    )
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--env-summary", type=Path)
    parser.add_argument("--select-plan-summary", type=Path)
    parser.add_argument("--resilience-plan-summary", type=Path)
    parser.add_argument("--executor-contract-summary", type=Path)
    parser.add_argument("--current-truth", type=Path, default=Path("docs/recovery/current-truth.json"))
    parser.add_argument("--current-proof", type=Path, default=Path("docs/recovery/current-proof-anchor-readback.json"))
    parser.add_argument("--target-character")
    parser.add_argument("--warning-age-seconds", type=int, default=900)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_root = (
        args.output_root.resolve()
        if args.output_root
        else (repo_root / ".riftreader-local" / "character-login-readiness-packet" / f"run-{utc_stamp()}").resolve()
    )
    output_root.mkdir(parents=True, exist_ok=True)
    env_summary = args.env_summary.resolve() if args.env_summary else latest_environment_summary(repo_root)
    select_plan = args.select_plan_summary.resolve() if args.select_plan_summary else latest_select_plan_summary(repo_root)
    resilience_plan = (
        args.resilience_plan_summary.resolve()
        if args.resilience_plan_summary
        else latest_resilience_plan_summary(repo_root)
    )
    executor_contract = (
        args.executor_contract_summary.resolve()
        if args.executor_contract_summary
        else latest_executor_contract_summary(repo_root)
    )
    current_truth = resolve_repo_path(repo_root, args.current_truth)
    current_proof = resolve_repo_path(repo_root, args.current_proof)

    summary = build_packet(
        repo_root=repo_root,
        output_root=output_root,
        env_summary_path=env_summary,
        select_plan_path=select_plan,
        resilience_plan_path=resilience_plan,
        executor_contract_path=executor_contract,
        current_truth_path=current_truth,
        current_proof_path=current_proof,
        target_character=args.target_character,
        warning_age_seconds=max(0, args.warning_age_seconds),
    )
    summary_json = output_root / "character-login-readiness-packet-summary.json"
    summary_markdown = output_root / "character-login-readiness-packet.md"
    summary["artifacts"]["summaryJson"] = str(summary_json.resolve())
    summary["artifacts"]["summaryMarkdown"] = str(summary_markdown.resolve())
    write_json(summary_json, summary)
    write_text_atomic(summary_markdown, render_markdown(summary))
    latest = repo_root / ".riftreader-local" / "character-login-readiness-packet" / "latest-run.txt"
    write_text_atomic(latest, str(output_root.resolve()))

    if args.json:
        print(json.dumps(summary, indent=2))

    if summary.get("status") == "packet-ready":
        return 0
    if summary.get("status") == "blocked":
        return 2
    return 1
