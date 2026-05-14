from __future__ import annotations

import argparse
import html
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def path_text(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def number_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def coerce_coordinate(source: dict[str, Any]) -> dict[str, float | str | None]:
    coordinate = dict_or_empty(source.get("coordinate") or source.get("Coordinate") or source.get("reference") or source)
    x = number_or_none(coordinate.get("x", coordinate.get("X")))
    y = number_or_none(coordinate.get("y", coordinate.get("Y")))
    z = number_or_none(coordinate.get("z", coordinate.get("Z")))
    if x is None or y is None or z is None:
        raise ValueError("reference coordinate missing x/y/z")
    return {
        "x": x,
        "y": y,
        "z": z,
        "capturedAtUtc": coordinate.get("capturedAtUtc") or coordinate.get("CapturedAtUtc") or source.get("capturedAtUtc"),
    }


def load_reference(path: Path) -> dict[str, Any]:
    doc = read_json(path)
    if not isinstance(doc, dict):
        raise ValueError(f"reference file is not an object: {path}")
    coordinate = coerce_coordinate(doc)
    return {"path": str(path), "coordinate": coordinate}


def candidate_records(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [item for item in doc if isinstance(item, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("candidates", "safe_candidates", "rankedCandidates", "matches"):
        values = doc.get(key)
        if isinstance(values, list):
            return [item for item in values if isinstance(item, dict)]
    if "candidate_id" in doc or "candidateId" in doc:
        return [doc]
    return []


def candidate_value(candidate: dict[str, Any]) -> tuple[float, float, float] | None:
    preview = candidate.get("value_preview") or candidate.get("valuePreview")
    if isinstance(preview, list) and len(preview) >= 3:
        x = number_or_none(preview[0])
        y = number_or_none(preview[1])
        z = number_or_none(preview[2])
        if x is not None and y is not None and z is not None:
            return x, y, z
    x = number_or_none(candidate.get("best_memory_x", candidate.get("bestMemoryX")))
    y = number_or_none(candidate.get("best_memory_y", candidate.get("bestMemoryY")))
    z = number_or_none(candidate.get("best_memory_z", candidate.get("bestMemoryZ")))
    if x is not None and y is not None and z is not None:
        return x, y, z
    return None


def candidate_id(candidate: dict[str, Any], index: int) -> str:
    return str(candidate.get("candidate_id") or candidate.get("candidateId") or f"candidate-{index:06d}")


def candidate_address(candidate: dict[str, Any]) -> str | None:
    for key in ("absolute_address_hex", "absoluteAddressHex", "source_absolute_address_hex", "sourceAbsoluteAddressHex", "addressHex", "address"):
        value = candidate.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def discover_candidate_files(repo_root: Path) -> list[Path]:
    captures = repo_root / "scripts" / "captures"
    if not captures.exists():
        return []
    names = {
        "api-family-vec3-candidates.json",
        "family-import-candidates.json",
        "coordinate-family-rankings.json",
        "candidate-vec3.json",
    }
    candidates = [path for path in captures.rglob("*.json") if path.name in names]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates


def compare_file(
    path: Path,
    reference: dict[str, Any],
    repo_root: Path,
    tolerance: float,
    max_records: int,
    displaced_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc = read_json(path)
    records = candidate_records(doc)
    ref = reference["coordinate"]
    displaced_ref = displaced_reference["coordinate"] if displaced_reference else None
    rows: list[dict[str, Any]] = []
    for index, record in enumerate(records[:max_records], start=1):
        value = candidate_value(record)
        if value is None:
            rows.append(
                {
                    "candidateId": candidate_id(record, index),
                    "address": candidate_address(record),
                    "status": "missing-value-preview",
                    "maxAbsDelta": None,
                }
            )
            continue
        x, y, z = value
        dx = x - float(ref["x"])
        dy = y - float(ref["y"])
        dz = z - float(ref["z"])
        max_abs = max(abs(dx), abs(dy), abs(dz))
        baseline_match = max_abs <= tolerance
        row = {
            "candidateId": candidate_id(record, index),
            "address": candidate_address(record),
            "status": "matches-current-api" if baseline_match else "stale-or-different-pose",
            "x": x,
            "y": y,
            "z": z,
            "deltaX": dx,
            "deltaY": dy,
            "deltaZ": dz,
            "maxAbsDelta": max_abs,
            "supportCount": record.get("support_count") or record.get("supportCount"),
            "classification": record.get("classification"),
        }
        if displaced_ref is not None:
            ddx = x - float(displaced_ref["x"])
            ddy = y - float(displaced_ref["y"])
            ddz = z - float(displaced_ref["z"])
            displaced_max_abs = max(abs(ddx), abs(ddy), abs(ddz))
            displaced_match = displaced_max_abs <= tolerance
            if baseline_match and displaced_match:
                two_reference_status = "matches-both-references"
            elif baseline_match:
                two_reference_status = "baseline-only"
            elif displaced_match:
                two_reference_status = "displaced-only"
            else:
                two_reference_status = "matches-neither-reference"
            row.update(
                {
                    "displacedDeltaX": ddx,
                    "displacedDeltaY": ddy,
                    "displacedDeltaZ": ddz,
                    "displacedMaxAbsDelta": displaced_max_abs,
                    "displacedStatus": "matches-displaced-api" if displaced_match else "stale-or-not-displaced-pose",
                    "twoReferenceStatus": two_reference_status,
                }
            )
        rows.append(row)
    matching = [row for row in rows if row.get("status") == "matches-current-api"]
    displaced_matching = [row for row in rows if row.get("displacedStatus") == "matches-displaced-api"]
    both_matching = [row for row in rows if row.get("twoReferenceStatus") == "matches-both-references"]
    best = min(
        [row for row in rows if isinstance(row.get("maxAbsDelta"), float)],
        key=lambda row: float(row["maxAbsDelta"]),
        default=None,
    )
    return {
        "path": path_text(path, repo_root),
        "recordCount": len(records),
        "comparedCount": len(rows),
        "matchCount": len(matching),
        "displacedMatchCount": len(displaced_matching) if displaced_reference else None,
        "bothReferenceMatchCount": len(both_matching) if displaced_reference else None,
        "best": best,
        "rows": rows,
    }


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Coordinate candidate comparison",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Reference file: `{summary.get('reference', {}).get('path')}`",
        f"- Displaced reference file: `{summary.get('displacedReference', {}).get('path')}`",
        f"- Tolerance: `{summary.get('tolerance')}`",
        f"- Movement sent: `{str(summary.get('safety', {}).get('movementSent')).lower()}`",
        "",
        "## Files",
        "",
        "| File | Records | Baseline matches | Displaced matches | Both-ref matches | Best candidate | Best max abs delta |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    for file_result in summary.get("candidateFiles") or []:
        best = dict_or_empty(file_result.get("best"))
        lines.append(
            f"| `{file_result.get('path')}` | `{file_result.get('recordCount')}` | `{file_result.get('matchCount')}` | "
            f"`{file_result.get('displacedMatchCount')}` | `{file_result.get('bothReferenceMatchCount')}` | "
            f"`{best.get('candidateId')}` | `{best.get('maxAbsDelta')}` |"
        )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in summary.get("blockers") or [])
    lines.extend(["", "This report is offline/read-only and does not read target memory or send input.", ""])
    return "\n".join(lines)


def build_html(summary: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape("" if value is None else str(value), quote=True)

    rows = "\n".join(
        "<tr>"
        f"<td><code>{esc(item.get('path'))}</code></td>"
        f"<td>{esc(item.get('recordCount'))}</td>"
        f"<td>{esc(item.get('matchCount'))}</td>"
        f"<td>{esc(item.get('displacedMatchCount'))}</td>"
        f"<td>{esc(item.get('bothReferenceMatchCount'))}</td>"
        f"<td><code>{esc(dict_or_empty(item.get('best')).get('candidateId'))}</code></td>"
        f"<td>{esc(dict_or_empty(item.get('best')).get('maxAbsDelta'))}</td>"
        "</tr>"
        for item in summary.get("candidateFiles") or []
    )
    blockers = "".join(f"<li><code>{esc(item)}</code></li>" for item in summary.get("blockers") or []) or "<li>None</li>"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Coordinate candidate comparison - {esc(summary.get('status'))}</title>
<style>
body {{ margin:0; background:#07111f; color:#e5eefb; font-family:"Segoe UI", system-ui, sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:32px 22px 48px; }}
.hero {{ border:1px solid #263a57; border-radius:22px; padding:24px; background:linear-gradient(135deg, rgba(56,189,248,.15), rgba(167,139,250,.10)); }}
table {{ width:100%; border-collapse:collapse; background:#0f1b2e; border:1px solid #263a57; border-radius:14px; overflow:hidden; }}
th, td {{ padding:11px 13px; border-bottom:1px solid #263a57; text-align:left; vertical-align:top; }}
th {{ color:#bae6fd; }}
code {{ background:#020817; border:1px solid #263a57; padding:2px 6px; border-radius:6px; color:#bfdbfe; }}
</style>
</head>
<body><main>
<section class="hero">
<h1>Coordinate candidate comparison</h1>
<p>Status: <code>{esc(summary.get('status'))}</code></p>
<p>Reference: <code>{esc(summary.get('reference', {}).get('path'))}</code></p>
<p>Displaced reference: <code>{esc(summary.get('displacedReference', {}).get('path'))}</code></p>
</section>
<h2>Files</h2>
<table><tr><th>File</th><th>Records</th><th>Baseline matches</th><th>Displaced matches</th><th>Both-ref matches</th><th>Best candidate</th><th>Best max abs delta</th></tr>{rows}</table>
<h2>Blockers</h2>
<ul>{blockers}</ul>
</main></body></html>
"""


def default_candidate_files(repo_root: Path, explicit_files: Sequence[Path], discover: bool) -> list[Path]:
    files = [path if path.is_absolute() else repo_root / path for path in explicit_files]
    if discover:
        files.extend(discover_candidate_files(repo_root))
    dedup: list[Path] = []
    seen: set[Path] = set()
    for path in files:
        resolved = path.resolve()
        if resolved not in seen:
            dedup.append(path)
            seen.add(resolved)
    return dedup


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare existing coordinate candidate files against a fresh API reference.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--api-reference", type=Path, required=True)
    parser.add_argument("--displaced-api-reference", type=Path)
    parser.add_argument("--candidate-file", type=Path, action="append", default=[])
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--tolerance", type=float, default=0.25)
    parser.add_argument("--max-records-per-file", type=int, default=100)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    run_dir = (args.output_root or repo_root / "scripts" / "captures" / f"coordinate-candidate-comparison-{utc_stamp()}").resolve()
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    summary_html = run_dir / "summary.html"
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-coordinate-candidate-comparison",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "blockers": [],
        "warnings": [],
        "errors": [],
        "repoRoot": str(repo_root),
        "tolerance": args.tolerance,
        "candidateFiles": [],
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
        api_reference = args.api_reference if args.api_reference.is_absolute() else repo_root / args.api_reference
        if not api_reference.exists():
            summary["blockers"].append(f"api-reference-missing:{args.api_reference}")
            summary["status"] = "blocked"
            return 2
        reference = load_reference(api_reference)
        summary["reference"] = {"path": path_text(api_reference, repo_root), "coordinate": reference["coordinate"]}
        displaced_reference = None
        if args.displaced_api_reference is not None:
            displaced_api_reference = args.displaced_api_reference if args.displaced_api_reference.is_absolute() else repo_root / args.displaced_api_reference
            if not displaced_api_reference.exists():
                summary["blockers"].append(f"displaced-api-reference-missing:{args.displaced_api_reference}")
                summary["status"] = "blocked"
                return 2
            displaced_reference = load_reference(displaced_api_reference)
            summary["displacedReference"] = {
                "path": path_text(displaced_api_reference, repo_root),
                "coordinate": displaced_reference["coordinate"],
            }
        files = default_candidate_files(repo_root, args.candidate_file, args.discover)
        if not files:
            summary["blockers"].append("candidate-file-required")
            summary["status"] = "blocked"
            return 2
        for file_path in files:
            if not file_path.exists():
                summary["warnings"].append(f"candidate-file-missing:{file_path}")
                continue
            try:
                summary["candidateFiles"].append(
                    compare_file(
                        file_path,
                        reference,
                        repo_root,
                        args.tolerance,
                        args.max_records_per_file,
                        displaced_reference=displaced_reference,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - keep comparing other files.
                summary["warnings"].append(f"candidate-file-unreadable:{file_path}:{type(exc).__name__}:{exc}")
        if not summary["candidateFiles"]:
            summary["blockers"].append("no-readable-candidate-files")
            summary["status"] = "blocked"
            return 2
        if displaced_reference is not None:
            summary["status"] = (
                "api-candidate-two-reference-match"
                if any(item.get("bothReferenceMatchCount", 0) > 0 for item in summary["candidateFiles"])
                else "candidate-only-no-two-reference-match"
            )
        else:
            summary["status"] = (
                "api-candidate-match"
                if any(item.get("matchCount", 0) > 0 for item in summary["candidateFiles"])
                else "candidate-only-no-current-api-match"
            )
        return 0 if summary["status"] in {"api-candidate-match", "api-candidate-two-reference-match"} else 2
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        return 1
    finally:
        write_json(summary_json, summary)
        write_text_atomic(summary_md, build_markdown(summary))
        write_text_atomic(summary_html, build_html(summary))
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(json.dumps({"status": summary.get("status"), "summaryJson": str(summary_json)}, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
