from __future__ import annotations

import argparse
import glob
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .character_select_automation_plan import (
    CHARACTER_SELECT_CLASSIFICATION,
    DEFAULT_EXPECTED_CLIENT_HEIGHT,
    DEFAULT_EXPECTED_CLIENT_WIDTH,
    ENV_KIND,
    as_bbox,
    as_click_point,
    normalize_name,
    repo_relative_or_absolute,
    validate_environment,
)
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
PLAN_KIND = "riftreader-character-login-resilience-plan"
DEFAULT_MAX_RELOGIN_ATTEMPTS = 3


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def latest_environment_summary(repo_root: Path) -> Path | None:
    pattern = str(
        repo_root
        / ".riftreader-local"
        / "character-select-automation-env"
        / "run-*"
        / "character-select-automation-env-summary.json"
    )
    matches = [Path(item) for item in glob.glob(pattern)]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime).resolve()


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_json_object(path: Path, errors: list[dict[str, str]]) -> dict[str, Any]:
    try:
        data = read_json_file(path)
        if not isinstance(data, dict):
            raise ValueError("JSON root is not an object")
        return data
    except Exception as exc:  # noqa: BLE001 - planning helper must preserve a durable failure reason.
        errors.append({"type": type(exc).__name__, "message": str(exc), "path": str(path)})
        return {}


def target_identity(document: dict[str, Any], *, target_key: str = "target") -> dict[str, Any]:
    target = document.get(target_key) if isinstance(document.get(target_key), dict) else {}
    hwnd = target.get("targetWindowHandle", target.get("windowHandle"))
    return {
        "processName": target.get("processName"),
        "processId": target.get("processId"),
        "windowHandle": hwnd,
        "processStartUtc": target.get("processStartUtc"),
        "windowTitle": target.get("windowTitle"),
        "moduleBase": target.get("moduleBase"),
    }


def _nonblank(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _same_optional_text(left: Any, right: Any) -> bool:
    left_text = _nonblank(left)
    right_text = _nonblank(right)
    if not left_text or not right_text:
        return True
    return normalize_name(left_text) == normalize_name(right_text)


def _parse_datetime(value: Any) -> datetime | None:
    text = _nonblank(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _same_optional_process_start(left: Any, right: Any, *, tolerance_seconds: float = 2.0) -> bool:
    left_text = _nonblank(left)
    right_text = _nonblank(right)
    if not left_text or not right_text:
        return True

    left_dt = _parse_datetime(left_text)
    right_dt = _parse_datetime(right_text)
    if left_dt is None or right_dt is None:
        return left_text == right_text

    if left_dt.tzinfo is None:
        left_dt = left_dt.replace(tzinfo=UTC)
    if right_dt.tzinfo is None:
        right_dt = right_dt.replace(tzinfo=UTC)
    return abs((left_dt - right_dt).total_seconds()) <= tolerance_seconds


def identities_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left.get("processId") == right.get("processId")
        and normalize_name(left.get("windowHandle")) == normalize_name(right.get("windowHandle"))
        and _same_optional_text(left.get("processName"), right.get("processName"))
        and _same_optional_process_start(left.get("processStartUtc"), right.get("processStartUtc"))
        and _same_optional_text(left.get("moduleBase"), right.get("moduleBase"))
    )


def visible_slot_names(env: dict[str, Any]) -> list[str]:
    targets = env.get("targets") if isinstance(env.get("targets"), dict) else {}
    slots = targets.get("visibleCharacterSlots") if isinstance(targets.get("visibleCharacterSlots"), list) else []
    return [str(slot.get("name") or "").strip() for slot in slots if isinstance(slot, dict) and slot.get("name")]


def selected_character(env: dict[str, Any]) -> str | None:
    screen = env.get("screenState") if isinstance(env.get("screenState"), dict) else {}
    selected = str(screen.get("selectedCharacter") or "").strip()
    return selected or None


def find_target_slot(env: dict[str, Any], target_character: str) -> dict[str, Any] | None:
    targets = env.get("targets") if isinstance(env.get("targets"), dict) else {}
    slots = targets.get("visibleCharacterSlots") if isinstance(targets.get("visibleCharacterSlots"), list) else []
    wanted = normalize_name(target_character)
    for slot in slots:
        if isinstance(slot, dict) and normalize_name(slot.get("name")) == wanted:
            return slot
    return None


def play_button(env: dict[str, Any]) -> dict[str, Any]:
    targets = env.get("targets") if isinstance(env.get("targets"), dict) else {}
    value = targets.get("playButton")
    return value if isinstance(value, dict) else {}


def build_state_machine(*, target_character: str | None, max_relogin_attempts: int) -> list[dict[str, Any]]:
    return [
        {
            "state": "detect-client",
            "goal": "Find a visible rift_x64/RIFT window and bind exact PID/HWND.",
            "guards": ["processName == rift_x64", "window title contains RIFT", "client size == 640x360"],
            "onFailure": "blocked-no-client-or-geometry-mismatch",
            "liveInputAllowed": False,
        },
        {
            "state": "capture-character-select",
            "goal": "Capture a fresh screen artifact and classify the UI state.",
            "guards": ["screen classification == character-selection-not-in-world"],
            "onFailure": "blocked-not-character-select",
            "liveInputAllowed": False,
        },
        {
            "state": "verify-target-character",
            "goal": f"Confirm target character {target_character or '<selected>'} is visible and selected or selectable.",
            "guards": ["target slot visible", "single selected slot", "slot click point inside bbox and client bounds"],
            "onFailure": "blocked-target-character-not-visible-or-ambiguous",
            "liveInputAllowed": False,
        },
        {
            "state": "future-select-character",
            "goal": "Only if explicitly approved in a future run, click one roster slot and recapture to verify selection.",
            "guards": ["explicit per-run approval", "fresh exact target", "fresh screenshot", "post-click recapture required"],
            "onFailure": "stop-before-play",
            "liveInputAllowed": "approval-required",
        },
        {
            "state": "future-click-play",
            "goal": "Only if explicitly approved, click Play once after selection verification.",
            "guards": ["explicit per-run approval", "Play click point inside bbox and client bounds", "worldEntryPermittedNow == true"],
            "onFailure": "stop-without-world-entry",
            "liveInputAllowed": "approval-required",
        },
        {
            "state": "wait-for-world-load",
            "goal": "Wait for character-select screen to leave and in-world visual/API surfaces to appear.",
            "guards": ["bounded timeout", "screen transition observed", "no repeated blind clicking"],
            "onFailure": "blocked-world-load-timeout",
            "liveInputAllowed": False,
        },
        {
            "state": "post-world-proof",
            "goal": "Rediscover PID/HWND and run fresh API-now vs memory-now ProofOnly before movement.",
            "guards": ["fresh API/runtime coordinate", "same-target memory readback", "ProofOnly passed"],
            "onFailure": "movement-remains-blocked",
            "liveInputAllowed": False,
        },
        {
            "state": "crash-recovery-loop",
            "goal": "If the client exits, discard PID/HWND-specific artifacts and restart at detect-client.",
            "guards": [f"attempts <= {max_relogin_attempts}", "new PID/HWND archived as a new epoch", "backoff before retry"],
            "onFailure": "blocked-crash-loop-limit",
            "liveInputAllowed": False,
        },
    ]


def build_retry_policy(max_relogin_attempts: int) -> dict[str, Any]:
    return {
        "maxReloginAttempts": max_relogin_attempts,
        "backoffSeconds": [2, 5, 10][: max(0, min(max_relogin_attempts, 3))],
        "stopConditions": [
            "target process missing after retry budget",
            "client geometry is not exactly 640x360",
            "target character not visible",
            "multiple selected slots or ambiguous roster state",
            "Play click point missing/outside bbox/outside client",
            "world load timeout",
            "post-world ProofOnly fails or is stale",
        ],
        "recoveryActions": [
            "archive old PID/HWND artifacts as historical-only",
            "recapture character-select environment for the new process epoch",
            "regenerate dry-run login plan",
            "do not reuse old absolute addresses or old click screenshots as current truth",
            "write JSON and Markdown summaries for each attempt",
        ],
    }


def build_logging_contract(output_root: Path) -> dict[str, Any]:
    return {
        "outputRoot": str(output_root.resolve()),
        "requiredArtifactsPerAttempt": [
            "bound target identity",
            "fresh screenshot path",
            "character-select environment summary",
            "dry-run login plan",
            "state transition log",
            "blockers/warnings/errors",
            "safety flags",
        ],
        "errorCapture": [
            "exception type/message/stage",
            "failed target identity",
            "failed artifact path",
            "exit code convention: 0 planned, 2 blocked, 1 failed",
        ],
        "privacySafety": {
            "savedVariablesUsedAsLiveTruth": False,
            "cheatEngineUsed": False,
            "x64dbgAttachStarted": False,
            "providerWrites": False,
            "gitMutation": False,
        },
    }


def build_state_log(summary: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = summary.get("blockers") if isinstance(summary.get("blockers"), list) else []
    readiness = summary.get("readiness") if isinstance(summary.get("readiness"), dict) else {}
    selection = summary.get("selection") if isinstance(summary.get("selection"), dict) else {}
    state_status: dict[str, str] = {
        "detect-client": "passed" if not any("target" in str(item) and "match" in str(item) for item in blockers) else "blocked",
        "capture-character-select": "passed"
        if not any("not-character-selection-screen" in str(item) for item in blockers)
        else "blocked",
        "verify-target-character": "passed"
        if selection.get("targetSlot") and not any("target-character" in str(item) for item in blockers)
        else "blocked",
        "future-select-character": "skipped-selected-already"
        if selection.get("selectedAlready") is True
        else "approval-required",
        "future-click-play": "approval-required" if readiness.get("canPlanLogin") else "blocked",
        "wait-for-world-load": "pending-after-approved-play",
        "post-world-proof": "pending-after-world-load",
        "crash-recovery-loop": "armed-dry-run-policy",
    }
    entries: list[dict[str, Any]] = []
    for index, state in enumerate(summary.get("stateMachine") or [], start=1):
        if not isinstance(state, dict):
            continue
        name = str(state.get("state") or f"state-{index}")
        entries.append(
            {
                "index": index,
                "state": name,
                "status": state_status.get(name, "planned"),
                "generatedAtUtc": summary.get("generatedAtUtc"),
                "liveInputAllowed": state.get("liveInputAllowed"),
                "onFailure": state.get("onFailure"),
                "safety": {
                    "movementSent": False,
                    "keyInputSent": False,
                    "mouseClickSent": False,
                    "worldEntryClicked": False,
                },
            }
        )
    return entries


def write_state_log(path: Path, entries: list[dict[str, Any]]) -> None:
    write_text_atomic(path, "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in entries))


def build_plan(
    *,
    repo_root: Path,
    output_root: Path,
    env_summary_path: Path | None,
    current_truth_path: Path,
    current_proof_path: Path,
    target_character: str | None,
    max_relogin_attempts: int,
    expected_client_width: int,
    expected_client_height: int,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    blockers: list[str] = []
    warnings: list[str] = []

    env: dict[str, Any] = {}
    truth: dict[str, Any] = {}
    proof: dict[str, Any] = {}

    if env_summary_path is None:
        blockers.append("missing-character-select-environment-summary")
    elif not env_summary_path.exists():
        blockers.append("character-select-environment-summary-not-found")
    else:
        env = load_json_object(env_summary_path, errors)

    if current_truth_path.exists():
        truth = load_json_object(current_truth_path, errors)
    else:
        warnings.append("current-truth-json-missing")
    if current_proof_path.exists():
        proof = load_json_object(current_proof_path, errors)
    else:
        warnings.append("current-proof-pointer-missing")

    if env:
        env_blockers, env_warnings = validate_environment(
            env,
            expected_client_width=expected_client_width,
            expected_client_height=expected_client_height,
        )
        blockers.extend(env_blockers)
        warnings.extend(env_warnings)

    env_identity = target_identity(env) if env else {}
    truth_identity = target_identity(truth) if truth else {}
    proof_identity = target_identity(proof) if proof else {}
    if env and truth and not identities_match(env_identity, truth_identity):
        blockers.append("environment-target-does-not-match-current-truth")
    if env and proof and not identities_match(env_identity, proof_identity):
        blockers.append("environment-target-does-not-match-current-proof")

    selected = selected_character(env) if env else None
    requested_character = str(target_character or selected or "").strip()
    if not requested_character:
        blockers.append("missing-target-character")
        target_slot = None
    else:
        target_slot = find_target_slot(env, requested_character) if env else None
        if target_slot is None:
            blockers.append("target-character-not-visible")

    play = play_button(env) if env else {}
    play_click = as_click_point(play.get("clickPoint"))
    play_bbox = as_bbox(play.get("bbox"))
    selected_already = bool(
        target_slot
        and (
            target_slot.get("selected") is True
            or normalize_name(selected) == normalize_name(requested_character)
        )
    )
    screen = env.get("screenState") if isinstance(env.get("screenState"), dict) else {}
    world_entry_permitted = screen.get("worldEntryPermittedNow") is True
    if not world_entry_permitted:
        warnings.append("world-entry-not-permitted-by-source-environment")

    can_plan_login = not blockers and bool(play_click) and bool(play_bbox) and selected_already
    status = "failed" if errors else "planned" if can_plan_login else "blocked"
    summary_json = output_root / "character-login-resilience-plan-summary.json"
    summary_markdown = output_root / "character-login-resilience-plan.md"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": PLAN_KIND,
        "status": status,
        "generatedAtUtc": utc_iso(),
        "blockers": blockers,
        "warnings": warnings,
        "errors": errors,
        "input": {
            "environmentSummary": str(env_summary_path.resolve()) if env_summary_path else None,
            "currentTruth": str(current_truth_path.resolve()),
            "currentProof": str(current_proof_path.resolve()),
            "targetCharacter": requested_character or None,
            "maxReloginAttempts": max_relogin_attempts,
            "dryRunOnly": True,
            "expectedClientSize": {
                "width": expected_client_width,
                "height": expected_client_height,
            },
        },
        "currentTarget": env_identity,
        "truthTarget": truth_identity,
        "proofTarget": proof_identity,
        "screenState": screen,
        "selection": {
            "selectedCharacter": selected,
            "targetCharacter": requested_character or None,
            "selectedAlready": selected_already,
            "targetSlot": target_slot,
            "visibleCharacters": visible_slot_names(env) if env else [],
        },
        "readiness": {
            "canPlanLogin": can_plan_login,
            "canExecuteLiveActionsNow": False,
            "whyNotExecute": "This helper is dry-run only. Character slot and Play clicks require explicit per-run approval and a separate executor.",
            "playButton": {
                "clickPoint": play_click,
                "bbox": play_bbox,
                "coordinateSpace": "client",
            },
        },
        "stateMachine": build_state_machine(
            target_character=requested_character or None,
            max_relogin_attempts=max_relogin_attempts,
        ),
        "retryPolicy": build_retry_policy(max_relogin_attempts),
        "loggingContract": build_logging_contract(output_root),
        "stateLog": [],
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
            "movementAllowed": False,
        },
        "artifacts": {
            "sourceEnvironmentSummary": repo_relative_or_absolute(env_summary_path, repo_root)
            if env_summary_path
            else None,
            "sourceScreenshot": (env.get("artifacts") or {}).get("screenshot")
            if isinstance(env.get("artifacts"), dict)
            else None,
            "summaryJson": str(summary_json.resolve()),
            "summaryMarkdown": str(summary_markdown.resolve()),
        },
        "next": {
            "recommendedAction": "Use this dry-run plan to design the login/relogin executor. Do not click Play until explicitly approved; after world load, rerun current-PID ProofOnly before movement.",
        },
    }


def render_markdown(summary: dict[str, Any]) -> str:
    readiness = summary.get("readiness") if isinstance(summary.get("readiness"), dict) else {}
    selection = summary.get("selection") if isinstance(summary.get("selection"), dict) else {}
    retry = summary.get("retryPolicy") if isinstance(summary.get("retryPolicy"), dict) else {}
    states = summary.get("stateMachine") if isinstance(summary.get("stateMachine"), list) else []
    state_log = summary.get("stateLog") if isinstance(summary.get("stateLog"), list) else []
    state_status_by_name = {
        str(item.get("state")): item.get("status")
        for item in state_log
        if isinstance(item, dict)
    }
    blockers = summary.get("blockers") or []
    warnings = summary.get("warnings") or []
    errors = summary.get("errors") or []

    lines = [
        "# Character login/relogin resilience dry-run plan",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Target character: `{selection.get('targetCharacter')}`",
        f"- Selected already: `{str(selection.get('selectedAlready')).lower()}`",
        f"- Can plan login: `{str(readiness.get('canPlanLogin')).lower()}`",
        f"- Can execute live actions now: `{str(readiness.get('canExecuteLiveActionsNow')).lower()}`",
        "",
        "## Safety",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Plan only | `{str(summary.get('safety', {}).get('planOnly')).lower()}` |",
        f"| Mouse click sent | `{str(summary.get('safety', {}).get('mouseClickSent')).lower()}` |",
        f"| World entry clicked | `{str(summary.get('safety', {}).get('worldEntryClicked')).lower()}` |",
        f"| Movement allowed | `{str(summary.get('safety', {}).get('movementAllowed')).lower()}` |",
        "",
        "## State machine",
        "",
        "| # | State | Status | Goal | Failure | Live input |",
        "|---:|---|---|---|---|---|",
    ]
    for index, state in enumerate(states, start=1):
        state_name = str(state.get("state"))
        lines.append(
            f"| {index} | `{state_name}` | `{state_status_by_name.get(state_name, 'planned')}` | {state.get('goal')} | `{state.get('onFailure')}` | `{state.get('liveInputAllowed')}` |"
        )
    lines.extend(
        [
            "",
            "## Retry policy",
            "",
            f"- Max relogin attempts: `{retry.get('maxReloginAttempts')}`",
            f"- Backoff seconds: `{retry.get('backoffSeconds')}`",
            "",
            "## Blockers",
            "",
        ]
    )
    lines.extend([f"- `{item}`" for item in blockers] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- `{item}`" for item in warnings] or ["- none"])
    lines.extend(["", "## Errors", ""])
    lines.extend([f"- `{item}`" for item in errors] or ["- none"])
    lines.extend(
        [
            "",
            "This artifact is a dry-run design/validation plan only. It does not click a character, click Play, enter world, launch RIFT, send keys, or allow movement.",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a defensive dry-run plan for character login/relogin automation.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--env-summary", type=Path)
    parser.add_argument("--current-truth", type=Path, default=Path("docs/recovery/current-truth.json"))
    parser.add_argument("--current-proof", type=Path, default=Path("docs/recovery/current-proof-anchor-readback.json"))
    parser.add_argument("--target-character")
    parser.add_argument("--max-relogin-attempts", type=int, default=DEFAULT_MAX_RELOGIN_ATTEMPTS)
    parser.add_argument("--expected-client-width", type=int, default=DEFAULT_EXPECTED_CLIENT_WIDTH)
    parser.add_argument("--expected-client-height", type=int, default=DEFAULT_EXPECTED_CLIENT_HEIGHT)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_root = (
        args.output_root.resolve()
        if args.output_root
        else (repo_root / ".riftreader-local" / "character-login-resilience-plan" / f"run-{utc_stamp()}").resolve()
    )
    output_root.mkdir(parents=True, exist_ok=True)

    env_summary = args.env_summary.resolve() if args.env_summary else latest_environment_summary(repo_root)
    current_truth = args.current_truth if args.current_truth.is_absolute() else repo_root / args.current_truth
    current_proof = args.current_proof if args.current_proof.is_absolute() else repo_root / args.current_proof
    max_attempts = max(0, args.max_relogin_attempts)
    summary = build_plan(
        repo_root=repo_root,
        output_root=output_root,
        env_summary_path=env_summary,
        current_truth_path=current_truth,
        current_proof_path=current_proof,
        target_character=args.target_character,
        max_relogin_attempts=max_attempts,
        expected_client_width=args.expected_client_width,
        expected_client_height=args.expected_client_height,
    )

    summary_json = output_root / "character-login-resilience-plan-summary.json"
    summary_markdown = output_root / "character-login-resilience-plan.md"
    state_log_jsonl = output_root / "character-login-resilience-state-log.jsonl"
    state_log = build_state_log(summary)
    summary["stateLog"] = state_log
    summary.setdefault("artifacts", {})
    summary["artifacts"]["summaryJson"] = str(summary_json.resolve())
    summary["artifacts"]["summaryMarkdown"] = str(summary_markdown.resolve())
    summary["artifacts"]["stateLogJsonl"] = str(state_log_jsonl.resolve())
    write_state_log(state_log_jsonl, state_log)
    write_json(summary_json, summary)
    write_text_atomic(summary_markdown, render_markdown(summary))
    latest = repo_root / ".riftreader-local" / "character-login-resilience-plan" / "latest-run.txt"
    write_text_atomic(latest, str(output_root.resolve()))

    if args.json:
        print(json.dumps(summary, indent=2))

    if summary.get("status") == "planned":
        return 0
    if summary.get("status") == "blocked":
        return 2
    return 1
