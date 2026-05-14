from __future__ import annotations

import argparse
import html
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DISPLACED_REFERENCE_MARKERS = (
    "displaced",
    "manual-displaced",
    "operator-displaced",
    "moved-pose",
    "second-pose",
    "alternate-pose",
)


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def path_text(path: Path | None, repo_root: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON file is not an object: {path}")
    return value


def dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def number_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def json_pid(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(str(value), 0)
        except (TypeError, ValueError):
            return None


def normalize_hwnd(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        return f"0x{int(text, 0):X}"
    except ValueError:
        return text


def file_mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def displaced_reference_marker(path: Path, document: Mapping[str, Any]) -> str | None:
    text_parts = [str(path).replace("\\", "/").lower()]
    for key in ("pose", "poseLabel", "label", "source", "notes", "description", "mode", "captureContext", "referenceKind"):
        value = document.get(key)
        if value not in (None, ""):
            text_parts.append(str(value).lower())
    for marker in DISPLACED_REFERENCE_MARKERS:
        if any(marker in text for text in text_parts):
            return marker
    return None


def coerce_coordinate(document: Mapping[str, Any]) -> dict[str, float]:
    source = dict_or_empty(document.get("coordinate") or document.get("Coordinate") or document.get("reference") or document)
    x = number_or_none(source.get("x", source.get("X")))
    y = number_or_none(source.get("y", source.get("Y")))
    z = number_or_none(source.get("z", source.get("Z")))
    if x is None or y is None or z is None:
        raise ValueError("reference coordinate missing x/y/z")
    return {"x": x, "y": y, "z": z}


def reference_target(document: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "processId": json_pid(document.get("processId") or document.get("ProcessId")),
        "targetWindowHandle": normalize_hwnd(document.get("targetWindowHandle") or document.get("TargetWindowHandle")),
        "processName": document.get("processName") or document.get("ProcessName"),
    }


def find_latest_reference(repo_root: Path, *, pid: int | None, hwnd: str | None, displaced: bool) -> Path | None:
    captures = repo_root / "scripts" / "captures"
    if not captures.exists():
        return None
    normalized_hwnd = normalize_hwnd(hwnd)
    candidates = sorted(captures.rglob("rift-api-reference-currentpid-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            document = read_json(path)
        except Exception:  # noqa: BLE001 - skip unreadable historical artifacts.
            continue
        target = reference_target(document)
        candidate_pid = json_pid(target.get("processId"))
        candidate_hwnd = normalize_hwnd(target.get("targetWindowHandle"))
        if pid is not None and candidate_pid is not None and candidate_pid != pid:
            continue
        if normalized_hwnd and candidate_hwnd and candidate_hwnd != normalized_hwnd:
            continue
        marker = displaced_reference_marker(path, document)
        if displaced and marker is None:
            continue
        if not displaced and marker is not None:
            continue
        return path
    return None


def resolve_reference(repo_root: Path, value: Path, *, pid: int | None, hwnd: str | None, displaced: bool) -> tuple[Path | None, str | None, str | None]:
    alias = str(value).strip().lower()
    if alias in {"latest", "latest-displaced"}:
        path = find_latest_reference(repo_root, pid=pid, hwnd=hwnd, displaced=displaced or alias == "latest-displaced")
        if path is None:
            blocker = "displaced-reference-latest-not-found" if displaced or alias == "latest-displaced" else "reference-file-latest-not-found"
            return None, alias, blocker
        return path, alias, None
    path = value if value.is_absolute() else repo_root / value
    return path, None, None


def compare_targets(expected_pid: int | None, expected_hwnd: str | None, baseline: Mapping[str, Any], displaced: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    baseline_pid = json_pid(baseline.get("processId"))
    displaced_pid = json_pid(displaced.get("processId"))
    baseline_hwnd = normalize_hwnd(baseline.get("targetWindowHandle"))
    displaced_hwnd = normalize_hwnd(displaced.get("targetWindowHandle"))
    normalized_expected_hwnd = normalize_hwnd(expected_hwnd)
    if expected_pid is not None and baseline_pid is not None and baseline_pid != expected_pid:
        blockers.append(f"baseline-target-pid-mismatch:{baseline_pid}!={expected_pid}")
    if expected_pid is not None and displaced_pid is not None and displaced_pid != expected_pid:
        blockers.append(f"displaced-target-pid-mismatch:{displaced_pid}!={expected_pid}")
    if baseline_pid is not None and displaced_pid is not None and baseline_pid != displaced_pid:
        blockers.append(f"reference-pid-mismatch:{baseline_pid}!={displaced_pid}")
    if normalized_expected_hwnd and baseline_hwnd and baseline_hwnd != normalized_expected_hwnd:
        blockers.append(f"baseline-target-hwnd-mismatch:{baseline_hwnd}!={normalized_expected_hwnd}")
    if normalized_expected_hwnd and displaced_hwnd and displaced_hwnd != normalized_expected_hwnd:
        blockers.append(f"displaced-target-hwnd-mismatch:{displaced_hwnd}!={normalized_expected_hwnd}")
    if baseline_hwnd and displaced_hwnd and baseline_hwnd != displaced_hwnd:
        blockers.append(f"reference-hwnd-mismatch:{baseline_hwnd}!={displaced_hwnd}")
    return blockers


def build_markdown(summary: Mapping[str, Any]) -> str:
    delta = dict_or_empty(summary.get("delta"))
    lines = [
        "# Displaced reference readiness",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Baseline: `{summary.get('baselineReference', {}).get('path')}`",
        f"- Displaced: `{summary.get('displacedReference', {}).get('path')}`",
        f"- Age delta seconds: `{summary.get('ageDeltaSeconds')}`",
        f"- Planar displacement: `{delta.get('planarDistance')}`",
        f"- Movement sent: `{str(summary.get('safety', {}).get('movementSent')).lower()}`",
        "",
    ]
    if summary.get("blockers"):
        lines.extend(["## Blockers", ""])
        lines.extend(f"- `{item}`" for item in summary.get("blockers") or [])
        lines.append("")
    if summary.get("warnings"):
        lines.extend(["## Warnings", ""])
        lines.extend(f"- `{item}`" for item in summary.get("warnings") or [])
        lines.append("")
    lines.append("This helper is offline/read-only and never sends movement or input.")
    return "\n".join(lines) + "\n"


def build_html(summary: Mapping[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape("" if value is None else str(value), quote=True)

    blockers = "".join(f"<li><code>{esc(item)}</code></li>" for item in summary.get("blockers") or []) or "<li>None</li>"
    warnings = "".join(f"<li><code>{esc(item)}</code></li>" for item in summary.get("warnings") or []) or "<li>None</li>"
    delta = dict_or_empty(summary.get("delta"))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Displaced reference readiness - {esc(summary.get('status'))}</title>
<style>
body {{ margin:0; background:#07111f; color:#e5eefb; font-family:"Segoe UI", system-ui, sans-serif; }}
main {{ max-width:1050px; margin:0 auto; padding:32px 22px 48px; }}
.hero {{ border:1px solid #263a57; border-radius:22px; padding:24px; background:linear-gradient(135deg, rgba(56,189,248,.15), rgba(167,139,250,.10)); }}
table {{ width:100%; border-collapse:collapse; background:#0f1b2e; border:1px solid #263a57; border-radius:14px; overflow:hidden; }}
th, td {{ padding:11px 13px; border-bottom:1px solid #263a57; text-align:left; vertical-align:top; }}
th {{ color:#bae6fd; width:260px; }}
code {{ background:#020817; border:1px solid #263a57; padding:2px 6px; border-radius:6px; color:#bfdbfe; overflow-wrap:anywhere; }}
</style>
</head>
<body><main>
<section class="hero">
<h1>Displaced reference readiness</h1>
<p>Status: <code>{esc(summary.get('status'))}</code></p>
<p>This helper is offline/read-only and never sends movement or input.</p>
</section>
<h2>Facts</h2>
<table>
<tr><th>Baseline</th><td><code>{esc(summary.get('baselineReference', {}).get('path'))}</code></td></tr>
<tr><th>Displaced</th><td><code>{esc(summary.get('displacedReference', {}).get('path'))}</code></td></tr>
<tr><th>Age delta seconds</th><td>{esc(summary.get('ageDeltaSeconds'))}</td></tr>
<tr><th>Planar displacement</th><td>{esc(delta.get('planarDistance'))}</td></tr>
</table>
<h2>Blockers</h2><ul>{blockers}</ul>
<h2>Warnings</h2><ul>{warnings}</ul>
</main></body></html>
"""


def upsert_markdown_table_rows(text: str, heading_prefix: str, rows: Mapping[str, str]) -> str:
    lines = text.splitlines()
    heading_index = next((index for index, line in enumerate(lines) if line.startswith(heading_prefix)), None)
    if heading_index is None:
        appended = ["", heading_prefix, "", "| Field | Value |", "|---|---|", *[f"| {label} | `{value}` |" for label, value in rows.items()]]
        return "\n".join([*lines, *appended]).rstrip() + "\n"
    table_start = next((index for index in range(heading_index + 1, len(lines)) if lines[index].strip() == "| Field | Value |"), None)
    if table_start is None:
        lines[heading_index + 1:heading_index + 1] = ["", "| Field | Value |", "|---|---|", *[f"| {label} | `{value}` |" for label, value in rows.items()]]
        return "\n".join(lines).rstrip() + "\n"
    table_end = table_start + 2
    while table_end < len(lines) and lines[table_end].startswith("|"):
        table_end += 1
    updated: set[str] = set()
    for index in range(table_start + 2, table_end):
        parts = [part.strip() for part in lines[index].strip().strip("|").split("|")]
        if len(parts) >= 2 and parts[0] in rows:
            lines[index] = f"| {parts[0]} | `{rows[parts[0]]}` |"
            updated.add(parts[0])
    lines[table_end:table_end] = [f"| {label} | `{value}` |" for label, value in rows.items() if label not in updated]
    return "\n".join(lines).rstrip() + "\n"


def update_current_truth(summary: Mapping[str, Any], repo_root: Path) -> None:
    truth_path = repo_root / "docs" / "recovery" / "current-truth.json"
    if not truth_path.exists():
        return
    document = read_json(truth_path)
    routing = document.setdefault("visualEvidenceRouting", {})
    artifacts = dict_or_empty(summary.get("artifacts"))
    routing["latestDisplacedReferenceReadiness"] = path_text(Path(str(artifacts.get("summaryJson"))), repo_root)
    routing["latestDisplacedReferenceReadinessHtml"] = path_text(Path(str(artifacts.get("summaryHtml"))), repo_root)
    routing["latestDisplacedReferenceReadinessStatus"] = str(summary.get("status"))
    routing["latestDisplacedReferencePlanarDistance"] = dict_or_empty(summary.get("delta")).get("planarDistance")
    write_json(truth_path, document)

    markdown_path = repo_root / "docs" / "recovery" / "current-truth.md"
    if not markdown_path.exists():
        return
    rows = {
        "Latest displaced-reference readiness": str(routing.get("latestDisplacedReferenceReadiness") or ""),
        "Latest displaced-reference readiness HTML": str(routing.get("latestDisplacedReferenceReadinessHtml") or ""),
        "Latest displaced-reference readiness status": str(routing.get("latestDisplacedReferenceReadinessStatus") or ""),
    }
    updated = upsert_markdown_table_rows(
        markdown_path.read_text(encoding="utf-8"),
        "## Visual/capture proof-route policy",
        rows,
    )
    write_text_atomic(markdown_path, updated)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check whether baseline/displaced API references are fresh enough for two-pose candidate scoring.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--pid", type=int)
    parser.add_argument("--hwnd")
    parser.add_argument("--api-reference", type=Path, default=Path("latest"))
    parser.add_argument("--displaced-api-reference", type=Path, default=Path("latest-displaced"))
    parser.add_argument("--max-age-delta-seconds", type=float, default=300.0)
    parser.add_argument("--min-planar-displacement", type=float, default=1.0)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--update-current-truth", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    run_dir = (args.output_root or repo_root / "scripts" / "captures" / f"coordinate-displaced-reference-readiness-{utc_stamp()}").resolve()
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    summary_html = run_dir / "summary.html"
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-coordinate-displaced-reference-readiness",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "blockers": [],
        "warnings": [],
        "errors": [],
        "repoRoot": str(repo_root),
        "artifacts": {"summaryJson": str(summary_json), "summaryMarkdown": str(summary_md), "summaryHtml": str(summary_html)},
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgAttached": False,
            "processAttachOrMemoryReadStarted": False,
            "providerWrite": False,
        },
    }
    try:
        baseline_path, baseline_alias, baseline_error = resolve_reference(repo_root, args.api_reference, pid=args.pid, hwnd=args.hwnd, displaced=False)
        displaced_path, displaced_alias, displaced_error = resolve_reference(repo_root, args.displaced_api_reference, pid=args.pid, hwnd=args.hwnd, displaced=True)
        summary["baselineReferenceResolvedFromAlias"] = baseline_alias
        summary["displacedReferenceResolvedFromAlias"] = displaced_alias
        if baseline_error:
            summary["blockers"].append(baseline_error)
        if displaced_error:
            summary["blockers"].append(displaced_error)
        if baseline_path is None or not baseline_path.exists():
            summary["blockers"].append(f"baseline-reference-missing:{baseline_path}")
        if displaced_path is None or not displaced_path.exists():
            summary["blockers"].append(f"displaced-reference-missing:{displaced_path}")
        if summary["blockers"]:
            summary["status"] = "blocked"
            return 2
        assert baseline_path is not None
        assert displaced_path is not None
        baseline_doc = read_json(baseline_path)
        displaced_doc = read_json(displaced_path)
        baseline_coord = coerce_coordinate(baseline_doc)
        displaced_coord = coerce_coordinate(displaced_doc)
        baseline_target = reference_target(baseline_doc)
        displaced_target = reference_target(displaced_doc)
        summary["baselineReference"] = {
            "path": path_text(baseline_path, repo_root),
            "coordinate": baseline_coord,
            "target": baseline_target,
            "modifiedAtUtc": file_mtime_utc(baseline_path),
        }
        summary["displacedReference"] = {
            "path": path_text(displaced_path, repo_root),
            "coordinate": displaced_coord,
            "target": displaced_target,
            "modifiedAtUtc": file_mtime_utc(displaced_path),
            "marker": displaced_reference_marker(displaced_path, displaced_doc),
        }
        summary["blockers"].extend(compare_targets(args.pid, args.hwnd, baseline_target, displaced_target))
        age_delta = abs(baseline_path.stat().st_mtime - displaced_path.stat().st_mtime)
        summary["ageDeltaSeconds"] = round(age_delta, 3)
        if displaced_path.stat().st_mtime < baseline_path.stat().st_mtime:
            summary["warnings"].append("displaced-reference-older-than-baseline-reference")
        if age_delta > args.max_age_delta_seconds:
            summary["blockers"].append(f"displaced-reference-age-exceeded:{round(age_delta, 3)}>{args.max_age_delta_seconds}")
        dx = displaced_coord["x"] - baseline_coord["x"]
        dy = displaced_coord["y"] - baseline_coord["y"]
        dz = displaced_coord["z"] - baseline_coord["z"]
        planar = math.hypot(dx, dy)
        summary["delta"] = {
            "deltaX": dx,
            "deltaY": dy,
            "deltaZ": dz,
            "planarDistance": planar,
            "maxAbsDelta": max(abs(dx), abs(dy), abs(dz)),
        }
        if planar < args.min_planar_displacement:
            summary["blockers"].append(f"displaced-reference-planar-distance-too-small:{round(planar, 6)}<{args.min_planar_displacement}")
        summary["status"] = "passed" if not summary["blockers"] else "blocked"
        return 0 if summary["status"] == "passed" else 2
    except Exception as exc:  # noqa: BLE001 - durable error capture.
        summary["status"] = "failed"
        summary["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        return 1
    finally:
        write_json(summary_json, summary)
        write_text_atomic(summary_md, build_markdown(summary))
        write_text_atomic(summary_html, build_html(summary))
        if args.update_current_truth:
            try:
                update_current_truth(summary, repo_root)
            except Exception as exc:  # noqa: BLE001 - preserve core output.
                summary.setdefault("warnings", []).append(f"current-truth-update-failed:{type(exc).__name__}:{exc}")
                write_json(summary_json, summary)
                write_text_atomic(summary_md, build_markdown(summary))
                write_text_atomic(summary_html, build_html(summary))
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(json.dumps({"status": summary.get("status"), "summaryJson": str(summary_json)}, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
