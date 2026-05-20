from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .character_select_automation_plan import (
    CHARACTER_SELECT_CLASSIFICATION,
    DEFAULT_EXPECTED_CLIENT_HEIGHT,
    DEFAULT_EXPECTED_CLIENT_WIDTH,
)
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
ENV_KIND = "riftreader-character-select-automation-environment"


CHARACTER_SLOTS: list[dict[str, Any]] = [
    {
        "slot": 1,
        "name": "SYRACUSE",
        "bbox": [10, 5, 140, 48],
        "clickPoint": [75, 27],
        "level": 51,
        "race": "Mathosian",
        "class": "Warrior",
        "faction": "Guardian",
        "location": "Sanctum",
        "selected": False,
    },
    {
        "slot": 2,
        "name": "CEBU",
        "bbox": [10, 52, 140, 96],
        "clickPoint": [75, 74],
        "level": 4,
        "race": "High Elf",
        "class": "Warrior",
        "faction": "Guardian",
        "location": "Mathosia",
        "selected": False,
    },
    {
        "slot": 3,
        "name": "ATANK",
        "bbox": [10, 99, 140, 143],
        "clickPoint": [75, 121],
        "level": 45,
        "race": "Mathosian",
        "class": "Warrior",
        "faction": "Guardian",
        "location": "Sanctum",
        "selected": True,
    },
    {
        "slot": 4,
        "name": "SHADOWKORN",
        "bbox": [10, 147, 140, 190],
        "clickPoint": [75, 169],
        "level": 10,
        "race": "Dwarf",
        "class": "Rogue",
        "faction": "Guardian",
        "location": "Silverwood",
        "selected": False,
    },
    {
        "slot": 5,
        "name": "ALBANIA",
        "bbox": [10, 195, 140, 238],
        "clickPoint": [75, 216],
        "level": 33,
        "race": "Mathosian",
        "class": "Rogue",
        "faction": "Guardian",
        "location": "Sanctum",
        "selected": False,
    },
]


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def latest_mcp_screenshot(repo_root: Path) -> Path | None:
    screenshot_dir = repo_root / "tools" / "rift-game-mcp" / ".runtime" / "screenshots"
    matches = list(screenshot_dir.glob("capture-*.png"))
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime).resolve()


def selected_slot(selected_character: str) -> dict[str, Any] | None:
    wanted = selected_character.strip().casefold()
    for slot in CHARACTER_SLOTS:
        if str(slot.get("name") or "").casefold() == wanted:
            return slot
    return None


def import_pillow() -> Any:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:  # noqa: BLE001 - preserve dependency failure in CLI summary.
        raise RuntimeError(f"Pillow is required to annotate character-select screenshots: {exc}") from exc
    return Image, ImageDraw, ImageFont


def build_targets(selected_character: str) -> dict[str, Any]:
    slots = [dict(slot, selected=str(slot["name"]).casefold() == selected_character.casefold()) for slot in CHARACTER_SLOTS]
    selected = selected_slot(selected_character)
    if selected is None:
        selected = dict(slots[0], selected=False)
    else:
        selected = dict(selected, selected=True)
    return {
        "characterListRegion": {"bbox": [8, 3, 143, 240], "description": "left vertical character roster"},
        "visibleCharacterSlots": slots,
        "selectedCharacter": selected,
        "playButton": {
            "bbox": [476, 329, 558, 357],
            "clickPoint": [517, 343],
            "description": "large lower-right PLAY button; use only after explicit approval to enter world",
            "measurementNote": "Measured at 640x360 character-select layout; recapture/remeasure if client size or UI scale changes.",
        },
        "bottomActionBar": {
            "bbox": [100, 333, 466, 357],
            "visibleActions": ["QUIT", "DELETE", "PLAY INTRO", "SETTINGS", "ADDONS", "TRANSFER", "SHARD", "CREATE"],
            "note": "Small bottom action buttons are landmarks only. For world entry prefer targets.playButton.",
        },
        "currentShardLabel": {"bbox": [247, 319, 365, 334], "text": "Current Shard: Deepwood"},
        "centerCharacterRegion": {
            "bbox": [245, 75, 425, 321],
            "description": "selected character model region; useful for screen-state verification, not a click target",
        },
    }


def annotate_and_crop(screenshot: Path, targets: dict[str, Any], output_root: Path) -> dict[str, str]:
    Image, ImageDraw, ImageFont = import_pillow()
    image = Image.open(screenshot).convert("RGB")
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        font = ImageFont.load_default()

    def rect(label: str, bbox: list[int], color: tuple[int, int, int]) -> None:
        draw.rectangle(bbox, outline=color, width=2)
        x, y = bbox[0] + 2, max(0, bbox[1] - 13)
        draw.text((x, y), label, fill=color, font=font)

    play = targets["playButton"]
    rect(f"PLAY center={tuple(play['clickPoint'])}", play["bbox"], (0, 255, 0))
    rect("char list", targets["characterListRegion"]["bbox"], (255, 255, 0))
    for slot in targets["visibleCharacterSlots"]:
        color = (0, 255, 255) if slot.get("selected") else (255, 180, 0)
        rect(f"{slot['slot']} {slot['name']} {tuple(slot['clickPoint'])}", slot["bbox"], color)
    rect("shard label", targets["currentShardLabel"]["bbox"], (255, 0, 255))

    annotated_path = output_root / "character-select-automation-targets-annotated.png"
    play_crop = output_root / "play-button-crop-6x.png"
    character_crop = output_root / "character-list-crop-3x.png"
    annotated.save(annotated_path)
    crop = image.crop(tuple(play["bbox"]))
    crop.resize((crop.width * 6, crop.height * 6)).save(play_crop)
    character = image.crop(tuple(targets["characterListRegion"]["bbox"]))
    character.resize((character.width * 3, character.height * 3)).save(character_crop)
    return {
        "annotatedScreenshot": str(annotated_path.resolve()),
        "playButtonCrop": str(play_crop.resolve()),
        "characterListCrop": str(character_crop.resolve()),
    }


def build_environment(
    *,
    screenshot: Path | None,
    output_root: Path,
    process_id: int | None,
    window_handle: str | None,
    process_start_utc: str | None,
    module_base: str | None,
    selected_character: str,
    shard: str,
    world_entry_permitted_now: bool,
    expected_client_width: int,
    expected_client_height: int,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    errors: list[dict[str, str]] = []
    width = height = None

    if screenshot is None:
        blockers.append("missing-screenshot")
    elif not screenshot.exists():
        blockers.append("screenshot-not-found")
    else:
        try:
            Image, _ImageDraw, _ImageFont = import_pillow()
            with Image.open(screenshot) as image:
                width, height = image.size
        except Exception as exc:  # noqa: BLE001
            errors.append({"type": type(exc).__name__, "message": str(exc), "stage": "read-screenshot"})

    if width != expected_client_width or height != expected_client_height:
        blockers.append(f"screenshot-size-mismatch-expected-{expected_client_width}x{expected_client_height}")
    if process_id is None:
        blockers.append("missing-process-id")
    if not window_handle:
        blockers.append("missing-window-handle")
    if not process_start_utc:
        warnings.append("missing-process-start-utc")
    if selected_slot(selected_character) is None:
        blockers.append("selected-character-not-in-known-layout")

    targets = build_targets(selected_character)
    artifact_paths: dict[str, str] = {}
    if not blockers and not errors and screenshot is not None:
        artifact_paths = annotate_and_crop(screenshot, targets, output_root)

    summary_json = output_root / "character-select-automation-env-summary.json"
    summary_markdown = output_root / "character-select-automation-env-summary.md"
    status = "failed" if errors else "blocked" if blockers else "captured-read-only-character-select"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": ENV_KIND,
        "status": status,
        "generatedAtUtc": utc_iso(),
        "blockers": blockers,
        "warnings": warnings,
        "errors": errors,
        "target": {
            "processName": "rift_x64",
            "processId": process_id,
            "windowHandle": window_handle,
            "windowTitle": "RIFT",
            "processStartUtc": process_start_utc,
            "moduleBase": module_base,
        },
        "window": {
            "clientSize": {"width": width, "height": height},
            "coordinateSystem": "client coordinates, origin top-left of the captured client area",
            "screenCoordinateFormula": "screenX = clientRect.left + clientX; screenY = clientRect.top + clientY for the exact window instance",
        },
        "screenState": {
            "classification": CHARACTER_SELECT_CLASSIFICATION,
            "selectedCharacter": selected_character,
            "currentShard": shard,
            "worldEntryAvailableVisually": True,
            "worldEntryPermittedNow": world_entry_permitted_now,
            "reasonWorldEntryNotPermittedNow": None
            if world_entry_permitted_now
            else "No explicit approval to click Play or enter world in this dry-run capture.",
        },
        "targets": targets,
        "futureAutomationPlan": {
            "safeSequence": [
                "bind exact PID/HWND and verify title/process/client size",
                "capture screenshot and verify character-select visual landmarks",
                "if required character is not selected, click that character slot center once and recapture/verify selection highlight",
                "only after explicit user approval, click playButton.clickPoint (currently [517,343]) to enter world",
                "wait for screen transition and in-world visual/telemetry readiness",
                "run current-PID ProofOnly before any movement/input automation",
            ],
            "clickTargetsUseClientCoordinates": True,
            "doNotUseUntilApproved": ["playButton", "character slot click", "any key input"],
        },
        "validationLimits": [
            "Coordinates are measured for the 640x360 character-select layout only.",
            "If client size, UI scale, selected shard, or roster layout changes, recapture and remeasure before clicking.",
            "Character-select screen exposes roster/shard information only; it does not provide fresh world coordinates.",
        ],
        "safety": {
            "movementSent": False,
            "keyInputSent": False,
            "mouseClickSent": False,
            "worldEntryClicked": False,
            "cheatEngineUsed": False,
            "x64dbgAttachStarted": False,
            "savedVariablesUsedAsLiveTruth": False,
        },
        "artifacts": {
            "screenshot": str(screenshot.resolve()) if screenshot else None,
            "summaryJson": str(summary_json.resolve()),
            "summaryMarkdown": str(summary_markdown.resolve()),
            **artifact_paths,
        },
    }


def render_markdown(summary: dict[str, Any]) -> str:
    play = ((summary.get("targets") or {}).get("playButton") or {}) if isinstance(summary.get("targets"), dict) else {}
    return "\n".join(
        [
            "# RIFT character-select automation environment",
            "",
            f"Status: **{summary.get('status')}**",
            "",
            f"- Target: PID `{summary.get('target', {}).get('processId')}`, HWND `{summary.get('target', {}).get('windowHandle')}`",
            f"- Client: `{summary.get('window', {}).get('clientSize', {}).get('width')}x{summary.get('window', {}).get('clientSize', {}).get('height')}`",
            f"- Screen state: `{summary.get('screenState', {}).get('classification')}`",
            f"- Current shard: `{summary.get('screenState', {}).get('currentShard')}`",
            f"- Selected character: `{summary.get('screenState', {}).get('selectedCharacter')}`",
            f"- Future Play target: client center `{play.get('clickPoint')}`, bbox `{play.get('bbox')}`",
            "- No clicks, keys, movement, CE, or debugger attach were used.",
            "",
            "## Blockers",
            "",
            *[f"- `{item}`" for item in (summary.get("blockers") or [])],
            *(["- none"] if not summary.get("blockers") else []),
            "",
            "## Artifacts",
            "",
            *[f"- `{key}`: `{value}`" for key, value in (summary.get("artifacts") or {}).items()],
            "",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a character-select environment summary from a fresh screenshot.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--screenshot", type=Path, help="Fresh 640x360 character-select screenshot. Defaults to latest MCP capture.")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--hwnd")
    parser.add_argument("--process-start-utc")
    parser.add_argument("--module-base")
    parser.add_argument("--selected-character", default="ATANK")
    parser.add_argument("--shard", default="Deepwood")
    parser.add_argument("--world-entry-permitted-now", action="store_true")
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
        else (repo_root / ".riftreader-local" / "character-select-automation-env" / f"run-{utc_stamp()}").resolve()
    )
    output_root.mkdir(parents=True, exist_ok=True)
    screenshot = args.screenshot.resolve() if args.screenshot else latest_mcp_screenshot(repo_root)
    summary = build_environment(
        screenshot=screenshot,
        output_root=output_root,
        process_id=args.pid,
        window_handle=args.hwnd,
        process_start_utc=args.process_start_utc,
        module_base=args.module_base,
        selected_character=args.selected_character,
        shard=args.shard,
        world_entry_permitted_now=args.world_entry_permitted_now,
        expected_client_width=args.expected_client_width,
        expected_client_height=args.expected_client_height,
    )
    summary_json = output_root / "character-select-automation-env-summary.json"
    summary_markdown = output_root / "character-select-automation-env-summary.md"
    summary["artifacts"]["summaryJson"] = str(summary_json.resolve())
    summary["artifacts"]["summaryMarkdown"] = str(summary_markdown.resolve())
    write_json(summary_json, summary)
    write_text_atomic(summary_markdown, render_markdown(summary))
    latest = repo_root / ".riftreader-local" / "character-select-automation-env" / "latest-run.txt"
    write_text_atomic(latest, str(output_root.resolve()))
    if args.json:
        print(json.dumps(summary, indent=2))
    if summary.get("status") == "captured-read-only-character-select":
        return 0
    if summary.get("status") == "blocked":
        return 2
    return 1
