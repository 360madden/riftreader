from __future__ import annotations

import argparse
import glob
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
ENV_KIND = "riftreader-character-select-automation-environment"
PLAN_KIND = "riftreader-character-select-automation-plan"
CHARACTER_SELECT_CLASSIFICATION = "character-selection-not-in-world"
DEFAULT_EXPECTED_CLIENT_WIDTH = 640
DEFAULT_EXPECTED_CLIENT_HEIGHT = 360


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def repo_relative_or_absolute(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


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


def normalize_name(value: Any) -> str:
    return str(value or "").strip().casefold()


def first_selected_slot(slots: list[dict[str, Any]]) -> dict[str, Any] | None:
    for slot in slots:
        if slot.get("selected") is True:
            return slot
    return None


def find_slot(slots: list[dict[str, Any]], target_character: str) -> dict[str, Any] | None:
    wanted = normalize_name(target_character)
    for slot in slots:
        if normalize_name(slot.get("name")) == wanted:
            return slot
    return None


def as_click_point(value: Any) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 2:
        return None
    try:
        return [int(value[0]), int(value[1])]
    except (TypeError, ValueError):
        return None


def as_bbox(value: Any) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        left, top, right, bottom = (int(item) for item in value)
    except (TypeError, ValueError):
        return None
    if right <= left or bottom <= top:
        return None
    return [left, top, right, bottom]


def point_inside_client(point: list[int], *, width: int, height: int) -> bool:
    return 0 <= point[0] < width and 0 <= point[1] < height


def point_inside_bbox(point: list[int], bbox: list[int]) -> bool:
    left, top, right, bottom = bbox
    return left <= point[0] <= right and top <= point[1] <= bottom


def validate_click_target(
    *,
    label: str,
    target: dict[str, Any],
    expected_client_width: int,
    expected_client_height: int,
    blockers: list[str],
) -> None:
    click_point = as_click_point(target.get("clickPoint"))
    bbox = as_bbox(target.get("bbox"))
    if click_point is None:
        blockers.append(f"{label}-missing-click-point")
        return
    if not point_inside_client(
        click_point,
        width=expected_client_width,
        height=expected_client_height,
    ):
        blockers.append(f"{label}-click-point-out-of-client-bounds")
    if bbox is not None and not point_inside_bbox(click_point, bbox):
        blockers.append(f"{label}-click-point-outside-bbox")


def build_action(
    *,
    action: str,
    description: str,
    will_execute: bool = False,
    requires_explicit_approval: bool = False,
    requires_recapture_verification: bool = False,
    client_click: list[int] | None = None,
    target: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "action": action,
        "description": description,
        "willExecute": will_execute,
        "requiresExplicitApproval": requires_explicit_approval,
        "requiresRecaptureVerification": requires_recapture_verification,
    }
    if client_click is not None:
        result["clientClick"] = client_click
        result["coordinateSpace"] = "client"
    if target is not None:
        result["target"] = target
    return result


def validate_environment(
    env: dict[str, Any],
    *,
    expected_client_width: int,
    expected_client_height: int,
) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []

    if env.get("kind") != ENV_KIND:
        warnings.append("unexpected-environment-kind")

    screen_state = env.get("screenState") if isinstance(env.get("screenState"), dict) else {}
    if screen_state.get("classification") != CHARACTER_SELECT_CLASSIFICATION:
        blockers.append("not-character-selection-screen")

    window = env.get("window") if isinstance(env.get("window"), dict) else {}
    client_size = window.get("clientSize") if isinstance(window.get("clientSize"), dict) else {}
    if client_size.get("width") != expected_client_width or client_size.get("height") != expected_client_height:
        blockers.append(
            f"client-size-mismatch-expected-{expected_client_width}x{expected_client_height}"
        )

    targets = env.get("targets") if isinstance(env.get("targets"), dict) else {}
    slots = targets.get("visibleCharacterSlots")
    if not isinstance(slots, list) or not slots:
        blockers.append("missing-visible-character-slots")
    else:
        selected_count = 0
        for index, slot in enumerate(slots, start=1):
            if not isinstance(slot, dict):
                blockers.append(f"character-slot-{index}-not-object")
                continue
            if slot.get("selected") is True:
                selected_count += 1
            validate_click_target(
                label=f"character-slot-{slot.get('slot') or index}",
                target=slot,
                expected_client_width=expected_client_width,
                expected_client_height=expected_client_height,
                blockers=blockers,
            )
        if selected_count > 1:
            blockers.append("multiple-selected-character-slots")

    play_button = targets.get("playButton")
    if not isinstance(play_button, dict):
        blockers.append("missing-play-button-click-point")
    else:
        validate_click_target(
            label="play-button",
            target=play_button,
            expected_client_width=expected_client_width,
            expected_client_height=expected_client_height,
            blockers=blockers,
        )

    safety = env.get("safety") if isinstance(env.get("safety"), dict) else {}
    if safety.get("worldEntryClicked") is True:
        blockers.append("environment-already-recorded-world-entry-click")
    if safety.get("movementSent") is True or safety.get("keyInputSent") is True:
        blockers.append("environment-summary-recorded-live-input")

    if screen_state.get("worldEntryPermittedNow") is False:
        warnings.append("source-environment-says-world-entry-not-permitted-now")

    return blockers, warnings


def build_plan(
    env: dict[str, Any],
    *,
    env_summary_path: Path | None,
    target_character: str | None,
    plan_enter_world: bool,
    expected_client_width: int,
    expected_client_height: int,
    output_root: Path,
    repo_root: Path,
) -> dict[str, Any]:
    blockers, warnings = validate_environment(
        env,
        expected_client_width=expected_client_width,
        expected_client_height=expected_client_height,
    )

    targets = env.get("targets") if isinstance(env.get("targets"), dict) else {}
    slots_raw = targets.get("visibleCharacterSlots") if isinstance(targets.get("visibleCharacterSlots"), list) else []
    slots = [slot for slot in slots_raw if isinstance(slot, dict)]
    selected_slot = first_selected_slot(slots)
    selected_name = (
        str(selected_slot.get("name")).strip()
        if selected_slot and selected_slot.get("name") is not None
        else str((env.get("screenState") or {}).get("selectedCharacter") or "").strip()
    )
    requested_character = str(target_character or selected_name or "").strip()

    target_slot = find_slot(slots, requested_character) if requested_character else None
    if not requested_character:
        blockers.append("missing-target-character")
    elif target_slot is None:
        blockers.append("target-character-not-visible")

    play_button = targets.get("playButton") if isinstance(targets.get("playButton"), dict) else {}
    play_click = as_click_point(play_button.get("clickPoint")) if isinstance(play_button, dict) else None

    planned_actions: list[dict[str, Any]] = [
        build_action(
            action="bind-target-window",
            description="Verify the exact PID/HWND/title/client size before any future live click.",
        ),
        build_action(
            action="verify-character-select-landmarks",
            description="Capture and verify character-select roster, selected character, shard label, and Play button landmarks.",
        ),
    ]

    selected_already = False
    if target_slot is not None:
        selected_already = target_slot.get("selected") is True or normalize_name(target_slot.get("name")) == normalize_name(selected_name)
        target_name = str(target_slot.get("name") or requested_character).strip()
        if selected_already:
            planned_actions.append(
                build_action(
                    action="keep-selected-character",
                    description=f"Target character {target_name} is already selected; do not click the roster.",
                    target={"character": target_name, "slot": target_slot.get("slot")},
                )
            )
        else:
            target_click = as_click_point(target_slot.get("clickPoint"))
            if target_click is None:
                blockers.append("target-character-missing-click-point")
            planned_actions.append(
                build_action(
                    action="click-character-slot",
                    description=f"Future approved automation would click {target_name}'s roster slot once, then recapture to verify selection.",
                    client_click=target_click,
                    requires_explicit_approval=True,
                    requires_recapture_verification=True,
                    target={"character": target_name, "slot": target_slot.get("slot")},
                )
            )

    if plan_enter_world:
        planned_actions.append(
            build_action(
                action="click-play-button",
                description="Future approved automation would click Play only after selection verification; this planner never clicks it.",
                client_click=play_click,
                requires_explicit_approval=True,
                requires_recapture_verification=True,
                target={"button": "Play"},
            )
        )
        planned_actions.extend(
            [
                build_action(
                    action="wait-for-world-load",
                    description="After an approved Play click, wait for transition/loading and verify in-world state.",
                ),
                build_action(
                    action="run-current-pid-proofonly-before-movement",
                    description="Before any movement automation, reacquire current PID/HWND proof and require ProofOnly to pass.",
                ),
            ]
        )
    else:
        warnings.append("world-entry-not-planned")

    status = "blocked" if blockers else "planned"
    summary_json = output_root / "character-select-automation-plan-summary.json"
    summary_markdown = output_root / "character-select-automation-plan.md"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": PLAN_KIND,
        "status": status,
        "generatedAtUtc": utc_iso(),
        "blockers": blockers,
        "warnings": warnings,
        "input": {
            "environmentSummary": str(env_summary_path.resolve()) if env_summary_path else None,
            "targetCharacter": requested_character or None,
            "planEnterWorld": plan_enter_world,
            "dryRunOnly": True,
            "expectedClientSize": {
                "width": expected_client_width,
                "height": expected_client_height,
            },
        },
        "target": env.get("target") if isinstance(env.get("target"), dict) else {},
        "window": env.get("window") if isinstance(env.get("window"), dict) else {},
        "screenState": env.get("screenState") if isinstance(env.get("screenState"), dict) else {},
        "selection": {
            "selectedCharacter": selected_name or None,
            "targetCharacter": requested_character or None,
            "selectedAlready": selected_already,
            "targetSlot": target_slot,
            "visibleCharacters": [
                {
                    "slot": slot.get("slot"),
                    "name": slot.get("name"),
                    "selected": slot.get("selected") is True,
                    "clickPoint": as_click_point(slot.get("clickPoint")),
                }
                for slot in slots
            ],
        },
        "plannedActions": planned_actions,
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
            "recommendedAction": "Review the dry-run plan. Do not click Play until explicitly approved; after entry, rerun current-PID proof gates before movement.",
        },
    }


def render_markdown(summary: dict[str, Any]) -> str:
    actions = summary.get("plannedActions") if isinstance(summary.get("plannedActions"), list) else []
    action_rows = []
    for index, action in enumerate(actions, start=1):
        click = action.get("clientClick")
        click_text = f"`{click}`" if click is not None else ""
        action_rows.append(
            "| {index} | `{action}` | `{will}` | `{approval}` | {click} | {description} |".format(
                index=index,
                action=action.get("action"),
                will=str(action.get("willExecute")).lower(),
                approval=str(action.get("requiresExplicitApproval")).lower(),
                click=click_text,
                description=action.get("description"),
            )
        )
    blockers = summary.get("blockers") or []
    warnings = summary.get("warnings") or []
    return "\n".join(
        [
            "# Character-select automation dry-run plan",
            "",
            f"- Status: `{summary.get('status')}`",
            f"- Generated: `{summary.get('generatedAtUtc')}`",
            f"- Target character: `{summary.get('selection', {}).get('targetCharacter')}`",
            f"- Selected already: `{str(summary.get('selection', {}).get('selectedAlready')).lower()}`",
            f"- Plan enters world: `{str(summary.get('input', {}).get('planEnterWorld')).lower()}`",
            "",
            "## Safety",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| Plan only | `{str(summary.get('safety', {}).get('planOnly')).lower()}` |",
            f"| Will execute live actions | `{str(summary.get('safety', {}).get('willExecuteLiveActions')).lower()}` |",
            f"| Mouse click sent | `{str(summary.get('safety', {}).get('mouseClickSent')).lower()}` |",
            f"| World entry clicked | `{str(summary.get('safety', {}).get('worldEntryClicked')).lower()}` |",
            f"| Movement allowed | `{str(summary.get('safety', {}).get('movementAllowed')).lower()}` |",
            "",
            "## Planned actions",
            "",
            "| # | Action | Will execute | Requires approval | Client click | Description |",
            "|---:|---|---|---|---|---|",
            *action_rows,
            "",
            "## Blockers",
            "",
            *(f"- `{item}`" for item in blockers),
            *(["- none"] if not blockers else []),
            "",
            "## Warnings",
            "",
            *(f"- `{item}`" for item in warnings),
            *(["- none"] if not warnings else []),
            "",
            "This artifact is a dry-run plan only. It does not select a character, click Play, enter world, send keys, or allow movement.",
            "",
        ]
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a dry-run plan for RIFT character-select automation.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--env-summary", type=Path, help="Path to character-select automation environment summary JSON.")
    parser.add_argument("--target-character", help="Character to select. Defaults to the currently selected character.")
    parser.add_argument(
        "--plan-enter-world",
        action="store_true",
        help="Include a gated future Play-click step in the plan. The tool still never clicks.",
    )
    parser.add_argument("--expected-client-width", type=int, default=DEFAULT_EXPECTED_CLIENT_WIDTH)
    parser.add_argument("--expected-client-height", type=int, default=DEFAULT_EXPECTED_CLIENT_HEIGHT)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true", help="Print the summary JSON to stdout.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_root = (
        args.output_root.resolve()
        if args.output_root
        else (repo_root / ".riftreader-local" / "character-select-automation-plan" / f"run-{utc_stamp()}").resolve()
    )
    output_root.mkdir(parents=True, exist_ok=True)

    env_summary_path = args.env_summary.resolve() if args.env_summary else latest_environment_summary(repo_root)
    if env_summary_path is None or not env_summary_path.exists():
        summary = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": PLAN_KIND,
            "status": "blocked",
            "generatedAtUtc": utc_iso(),
            "blockers": ["missing-environment-summary"],
            "warnings": [],
            "input": {
                "environmentSummary": str(env_summary_path) if env_summary_path else None,
                "targetCharacter": args.target_character,
                "planEnterWorld": args.plan_enter_world,
                "dryRunOnly": True,
            },
            "plannedActions": [],
            "safety": {
                "planOnly": True,
                "willExecuteLiveActions": False,
                "movementSent": False,
                "keyInputSent": False,
                "mouseClickSent": False,
                "worldEntryClicked": False,
                "movementAllowed": False,
            },
            "artifacts": {
                "summaryJson": str((output_root / "character-select-automation-plan-summary.json").resolve()),
                "summaryMarkdown": str((output_root / "character-select-automation-plan.md").resolve()),
            },
            "next": {
                "recommendedAction": "Capture a character-select environment summary before planning automation.",
            },
        }
    else:
        try:
            env = read_json_file(env_summary_path)
            if not isinstance(env, dict):
                raise ValueError("environment summary JSON root is not an object")
            summary = build_plan(
                env,
                env_summary_path=env_summary_path,
                target_character=args.target_character,
                plan_enter_world=args.plan_enter_world,
                expected_client_width=args.expected_client_width,
                expected_client_height=args.expected_client_height,
                output_root=output_root,
                repo_root=repo_root,
            )
        except Exception as exc:  # noqa: BLE001 - command-line helper should preserve a durable failure summary.
            summary = {
                "schemaVersion": SCHEMA_VERSION,
                "kind": PLAN_KIND,
                "status": "failed",
                "generatedAtUtc": utc_iso(),
                "blockers": [],
                "warnings": [],
                "errors": [
                    {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "stage": "load-or-build-plan",
                    }
                ],
                "input": {
                    "environmentSummary": str(env_summary_path),
                    "targetCharacter": args.target_character,
                    "planEnterWorld": args.plan_enter_world,
                    "dryRunOnly": True,
                },
                "plannedActions": [],
                "safety": {
                    "planOnly": True,
                    "willExecuteLiveActions": False,
                    "movementSent": False,
                    "keyInputSent": False,
                    "mouseClickSent": False,
                    "worldEntryClicked": False,
                    "movementAllowed": False,
                },
                "artifacts": {
                    "summaryJson": str((output_root / "character-select-automation-plan-summary.json").resolve()),
                    "summaryMarkdown": str((output_root / "character-select-automation-plan.md").resolve()),
                },
                "next": {
                    "recommendedAction": "Fix the environment summary or recapture the character-select screen.",
                },
            }

    summary_json = output_root / "character-select-automation-plan-summary.json"
    summary_markdown = output_root / "character-select-automation-plan.md"
    summary.setdefault("artifacts", {})
    summary["artifacts"]["summaryJson"] = str(summary_json.resolve())
    summary["artifacts"]["summaryMarkdown"] = str(summary_markdown.resolve())
    write_json(summary_json, summary)
    write_text_atomic(summary_markdown, render_markdown(summary))
    latest = repo_root / ".riftreader-local" / "character-select-automation-plan" / "latest-run.txt"
    write_text_atomic(latest, str(output_root.resolve()))

    if args.json:
        print(json.dumps(summary, indent=2))

    if summary.get("status") == "planned":
        return 0
    if summary.get("status") == "blocked":
        return 2
    return 1
