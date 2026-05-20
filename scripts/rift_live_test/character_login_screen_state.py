from __future__ import annotations

import argparse
import glob
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
KIND = "riftreader-character-login-screen-state"
BASE_CLIENT_WIDTH = 640
BASE_CLIENT_HEIGHT = 360
DEFAULT_MAX_SCREENSHOT_AGE_SECONDS = 300.0

BASE_REGIONS: dict[str, dict[str, Any]] = {
    "playButton": {
        "bbox": [476, 329, 558, 357],
        "weight": 0.35,
        "description": "lower-right PLAY button landmark",
    },
    "characterRoster": {
        "bbox": [8, 3, 143, 240],
        "weight": 0.30,
        "description": "left character roster panel",
    },
    "shardLabel": {
        "bbox": [247, 319, 365, 334],
        "weight": 0.15,
        "description": "bottom-center current shard label",
    },
    "centerCharacter": {
        "bbox": [245, 75, 425, 321],
        "weight": 0.10,
        "description": "selected character/model area",
    },
    "clientSize": {
        "bbox": [0, 0, BASE_CLIENT_WIDTH, BASE_CLIENT_HEIGHT],
        "weight": 0.10,
        "description": "expected 640x360 client geometry",
    },
}


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def latest_mcp_screenshot(repo_root: Path) -> Path | None:
    screenshot_dir = repo_root / "tools" / "rift-game-mcp" / ".runtime" / "screenshots"
    matches = [Path(item) for item in glob.glob(str(screenshot_dir / "capture-*.png"))]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime).resolve()


def import_pillow() -> Any:
    try:
        from PIL import Image, ImageStat
    except Exception as exc:  # noqa: BLE001 - CLI summary should preserve dependency failure.
        raise RuntimeError(f"Pillow is required for screenshot screen-state classification: {exc}") from exc
    return Image, ImageStat


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def scaled_bbox(base_bbox: list[int], width: int, height: int) -> list[int]:
    sx = width / BASE_CLIENT_WIDTH
    sy = height / BASE_CLIENT_HEIGHT
    x1, y1, x2, y2 = base_bbox
    return [
        max(0, min(width, round(x1 * sx))),
        max(0, min(height, round(y1 * sy))),
        max(0, min(width, round(x2 * sx))),
        max(0, min(height, round(y2 * sy))),
    ]


def region_stats(image: Any, bbox: list[int]) -> dict[str, Any]:
    _Image, ImageStat = import_pillow()
    crop = image.crop(tuple(bbox)).convert("RGB")
    width, height = crop.size
    pixel_count = max(1, width * height)
    raw = crop.tobytes()
    bright = green = cyan = dark = red_or_orange = 0
    for index in range(0, len(raw), 3):
        r, g, b = raw[index], raw[index + 1], raw[index + 2]
        max_channel = max(r, g, b)
        if max_channel > 150:
            bright += 1
        if g > 90 and g >= r * 0.8 and g >= b * 0.8:
            green += 1
        if g > 80 and b > 80 and r < 110:
            cyan += 1
        if max_channel < 45:
            dark += 1
        if r > 120 and g > 65 and b < 80:
            red_or_orange += 1
    stat = ImageStat.Stat(crop)
    return {
        "bbox": bbox,
        "pixelCount": pixel_count,
        "meanRgb": [round(value, 3) for value in stat.mean[:3]],
        "brightFraction": bright / pixel_count,
        "greenFraction": green / pixel_count,
        "cyanFraction": cyan / pixel_count,
        "darkFraction": dark / pixel_count,
        "redOrOrangeFraction": red_or_orange / pixel_count,
    }


def score_play_button(stats: dict[str, Any]) -> float:
    green_component = clamp(float(stats.get("greenFraction") or 0.0) / 0.16)
    bright_component = clamp(float(stats.get("brightFraction") or 0.0) / 0.07)
    dark_component = clamp(float(stats.get("darkFraction") or 0.0) / 0.12)
    cyan_component = clamp(float(stats.get("cyanFraction") or 0.0) / 0.04)
    return round(0.35 * green_component + 0.30 * bright_component + 0.20 * dark_component + 0.15 * cyan_component, 4)


def score_roster(stats: dict[str, Any]) -> float:
    dark_component = clamp(float(stats.get("darkFraction") or 0.0) / 0.18)
    green_component = clamp(float(stats.get("greenFraction") or 0.0) / 0.12)
    cyan_component = clamp(float(stats.get("cyanFraction") or 0.0) / 0.07)
    bright_component = clamp(float(stats.get("brightFraction") or 0.0) / 0.05)
    return round(0.30 * dark_component + 0.30 * green_component + 0.25 * cyan_component + 0.15 * bright_component, 4)


def score_shard_label(stats: dict[str, Any]) -> float:
    dark_component = clamp(float(stats.get("darkFraction") or 0.0) / 0.35)
    bright_component = clamp(float(stats.get("brightFraction") or 0.0) / 0.03)
    cyan_component = clamp(float(stats.get("cyanFraction") or 0.0) / 0.04)
    return round(0.45 * dark_component + 0.25 * bright_component + 0.30 * cyan_component, 4)


def score_center_character(stats: dict[str, Any]) -> float:
    cyan_component = clamp(float(stats.get("cyanFraction") or 0.0) / 0.20)
    green_component = clamp(float(stats.get("greenFraction") or 0.0) / 0.10)
    dark_component = clamp(float(stats.get("darkFraction") or 0.0) / 0.08)
    return round(0.45 * cyan_component + 0.35 * green_component + 0.20 * dark_component, 4)


def size_score(width: int, height: int, expected_width: int, expected_height: int) -> float:
    if width == expected_width and height == expected_height:
        return 1.0
    expected_aspect = expected_width / expected_height
    actual_aspect = width / height if height else 0.0
    if abs(actual_aspect - expected_aspect) <= 0.03:
        return 0.5
    return 0.0


def classify_landmarks(image: Any, *, expected_width: int, expected_height: int) -> tuple[list[dict[str, Any]], float]:
    width, height = image.size
    landmarks: list[dict[str, Any]] = []
    total = 0.0
    for name, spec in BASE_REGIONS.items():
        weight = float(spec["weight"])
        if name == "clientSize":
            score = size_score(width, height, expected_width, expected_height)
            stats = {"width": width, "height": height, "expectedWidth": expected_width, "expectedHeight": expected_height}
            bbox = [0, 0, width, height]
        else:
            bbox = scaled_bbox(list(spec["bbox"]), width, height)
            stats = region_stats(image, bbox)
            if name == "playButton":
                score = score_play_button(stats)
            elif name == "characterRoster":
                score = score_roster(stats)
            elif name == "shardLabel":
                score = score_shard_label(stats)
            elif name == "centerCharacter":
                score = score_center_character(stats)
            else:
                score = 0.0
        total += score * weight
        landmarks.append(
            {
                "name": name,
                "description": spec["description"],
                "bbox": bbox,
                "weight": weight,
                "score": round(score, 4),
                "passed": score >= 0.55,
                "stats": stats,
            }
        )
    return landmarks, round(total, 4)


def classify_screen(landmarks: list[dict[str, Any]], confidence: float) -> str:
    by_name = {str(item.get("name")): item for item in landmarks}
    play_ok = by_name.get("playButton", {}).get("score", 0.0) >= 0.60
    roster_ok = by_name.get("characterRoster", {}).get("score", 0.0) >= 0.60
    size_ok = by_name.get("clientSize", {}).get("score", 0.0) >= 0.50
    if play_ok and roster_ok and size_ok and confidence >= 0.62:
        return "character-selection-not-in-world"
    if confidence <= 0.30:
        return "not-character-select-or-transition"
    return "unknown-needs-operator-review"


def build_summary(
    *,
    repo_root: Path,
    output_root: Path,
    screenshot: Path | None,
    expected_width: int,
    expected_height: int,
    max_screenshot_age_seconds: float,
    expect_character_select: bool,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    errors: list[dict[str, str]] = []
    artifacts: dict[str, Any] = {
        "summaryJson": str((output_root / "character-login-screen-state-summary.json").resolve()),
        "summaryMarkdown": str((output_root / "character-login-screen-state.md").resolve()),
    }
    screenshot_age_seconds: float | None = None
    width = height = None
    landmarks: list[dict[str, Any]] = []
    confidence = 0.0
    classification = "blocked-no-screenshot"

    if screenshot is None:
        blockers.append("missing-screenshot")
    elif not screenshot.exists():
        blockers.append("screenshot-not-found")
        artifacts["screenshot"] = str(screenshot)
    else:
        artifacts["screenshot"] = str(screenshot.resolve())
        try:
            screenshot_age_seconds = max(0.0, datetime.now(UTC).timestamp() - screenshot.stat().st_mtime)
            if screenshot_age_seconds > max_screenshot_age_seconds:
                blockers.append(f"screenshot-too-old:{screenshot_age_seconds:.3f}>{max_screenshot_age_seconds:.3f}")
            Image, _ImageStat = import_pillow()
            with Image.open(screenshot).convert("RGB") as image:
                width, height = image.size
                landmarks, confidence = classify_landmarks(
                    image,
                    expected_width=expected_width,
                    expected_height=expected_height,
                )
                classification = classify_screen(landmarks, confidence)
        except Exception as exc:  # noqa: BLE001 - durable summary should capture classification failures.
            errors.append({"type": type(exc).__name__, "message": str(exc), "stage": "classify-screenshot"})

    if expect_character_select and classification != "character-selection-not-in-world" and not errors:
        blockers.append(f"expected-character-select-but-classified:{classification}")

    if width != expected_width or height != expected_height:
        warnings.append(f"screenshot-size-is-{width}x{height}-expected-{expected_width}x{expected_height}")

    status = "failed" if errors else "blocked" if blockers else "classified-character-select" if classification == "character-selection-not-in-world" else "classified-non-character-select"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "status": status,
        "generatedAtUtc": utc_iso(),
        "classification": classification,
        "confidence": confidence,
        "blockers": blockers,
        "warnings": warnings,
        "errors": errors,
        "input": {
            "screenshot": str(screenshot.resolve()) if screenshot and screenshot.exists() else str(screenshot) if screenshot else None,
            "expectCharacterSelect": expect_character_select,
            "maxScreenshotAgeSeconds": max_screenshot_age_seconds,
        },
        "window": {
            "clientSize": {"width": width, "height": height},
            "expectedClientSize": {"width": expected_width, "height": expected_height},
        },
        "screenshotFreshness": {
            "ageSeconds": round(screenshot_age_seconds, 3) if screenshot_age_seconds is not None else None,
            "maxAgeSeconds": max_screenshot_age_seconds,
        },
        "landmarks": landmarks,
        "decision": {
            "characterSelectLandmarksPresent": classification == "character-selection-not-in-world",
            "safeToUseCharacterSelectClickTargets": status == "classified-character-select" and width == expected_width and height == expected_height,
            "canTreatAsInWorld": False,
            "postWorldProofRequired": True,
            "recommendedAction": "Use as read-only screen state evidence only. If this follows an approved Play click, treat non-character-select as transition evidence and still require fresh in-world telemetry plus ProofOnly.",
        },
        "safety": {
            "planOnly": True,
            "willExecuteLiveActions": False,
            "movementSent": False,
            "keyInputSent": False,
            "mouseClickSent": False,
            "worldEntryClicked": False,
            "clientLaunchAttempted": False,
            "cheatEngineUsed": False,
            "x64dbgAttachStarted": False,
            "savedVariablesUsedAsLiveTruth": False,
            "providerWrites": False,
            "gitMutation": False,
        },
        "artifacts": artifacts,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Character login screen-state classifier",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Classification: `{summary.get('classification')}`",
        f"- Confidence: `{summary.get('confidence')}`",
        f"- Screenshot: `{summary.get('artifacts', {}).get('screenshot')}`",
        "",
        "## Landmarks",
        "",
        "| Landmark | Score | Passed | BBox |",
        "|---|---:|---|---|",
    ]
    for item in summary.get("landmarks") or []:
        lines.append(f"| `{item.get('name')}` | `{item.get('score')}` | `{str(item.get('passed')).lower()}` | `{item.get('bbox')}` |")
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- `{item}`" for item in (summary.get("blockers") or [])] or ["- none"])
    lines.extend(["", "## Safety", "", "No click, key input, movement, client launch, CE, x64dbg attach, provider write, or Git mutation is performed.", ""])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify a RIFT character-login screenshot without sending input.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--screenshot", type=Path, help="Screenshot to classify. Defaults to latest Rift MCP capture.")
    parser.add_argument("--expected-client-width", type=int, default=BASE_CLIENT_WIDTH)
    parser.add_argument("--expected-client-height", type=int, default=BASE_CLIENT_HEIGHT)
    parser.add_argument("--max-screenshot-age-seconds", type=float, default=DEFAULT_MAX_SCREENSHOT_AGE_SECONDS)
    parser.add_argument("--expect-character-select", action="store_true")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_root = (
        args.output_root.resolve()
        if args.output_root
        else (repo_root / ".riftreader-local" / "character-login-screen-state" / f"run-{utc_stamp()}").resolve()
    )
    output_root.mkdir(parents=True, exist_ok=True)
    screenshot = args.screenshot.resolve() if args.screenshot else latest_mcp_screenshot(repo_root)
    summary = build_summary(
        repo_root=repo_root,
        output_root=output_root,
        screenshot=screenshot,
        expected_width=args.expected_client_width,
        expected_height=args.expected_client_height,
        max_screenshot_age_seconds=max(0.0, args.max_screenshot_age_seconds),
        expect_character_select=args.expect_character_select,
    )
    summary_json = output_root / "character-login-screen-state-summary.json"
    summary_markdown = output_root / "character-login-screen-state.md"
    summary["artifacts"]["summaryJson"] = str(summary_json.resolve())
    summary["artifacts"]["summaryMarkdown"] = str(summary_markdown.resolve())
    write_json(summary_json, summary)
    write_text_atomic(summary_markdown, render_markdown(summary))
    latest = repo_root / ".riftreader-local" / "character-login-screen-state" / "latest-run.txt"
    write_text_atomic(latest, str(output_root.resolve()))
    if args.json:
        print(json.dumps(summary, indent=2))
    if str(summary.get("status", "")).startswith("classified"):
        return 0
    if summary.get("status") == "blocked":
        return 2
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
