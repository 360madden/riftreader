from __future__ import annotations

import argparse
import html
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

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


def float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def format_hex(value: int) -> str:
    return f"0x{value:X}"


def parse_address(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value), 0)
    except (TypeError, ValueError):
        return None


def candidate_id(candidate: dict[str, Any], index: int) -> str:
    return str(candidate.get("candidate_id") or candidate.get("candidateId") or f"candidate-{index:06d}")


def candidate_address(candidate: dict[str, Any]) -> str | None:
    for key in (
        "absolute_address_hex",
        "absoluteAddressHex",
        "source_absolute_address_hex",
        "sourceAbsoluteAddressHex",
        "addressHex",
        "address",
    ):
        value = candidate.get(key)
        if value not in (None, ""):
            return str(value)
    return None


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


def find_latest_comparison_summary(repo_root: Path) -> Path | None:
    truth_path = repo_root / "docs" / "recovery" / "current-truth.json"
    if truth_path.exists():
        try:
            truth = dict_or_empty(read_json(truth_path))
            routing = dict_or_empty(truth.get("visualEvidenceRouting"))
            value = routing.get("latestCandidateComparison")
            if value:
                path = Path(str(value))
                path = path if path.is_absolute() else repo_root / path
                if path.exists():
                    return path
        except Exception:  # noqa: BLE001 - fall back to capture discovery.
            pass
    captures = repo_root / "scripts" / "captures"
    if not captures.exists():
        return None
    candidates = sorted(
        captures.rglob("coordinate-candidate-comparison-*/summary.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def resolve_comparison_summary(repo_root: Path, value: Path | None) -> tuple[Path | None, str | None, str | None]:
    if value is None or str(value).strip().lower() == "latest":
        latest = find_latest_comparison_summary(repo_root)
        if latest is None:
            return None, "latest", "comparison-summary-latest-not-found"
        return latest, "latest", None
    return value if value.is_absolute() else repo_root / value, None, None


def centers_from_comparison_summary(path: Path, repo_root: Path) -> list[dict[str, Any]]:
    document = dict_or_empty(read_json(path))
    centers: list[dict[str, Any]] = []
    for file_result in list_or_empty(document.get("candidateFiles")):
        if not isinstance(file_result, dict):
            continue
        source = str(file_result.get("path") or path_text(path, repo_root))
        for row in list_or_empty(file_result.get("rows")):
            if not isinstance(row, dict):
                continue
            address_int = parse_address(row.get("address"))
            if address_int is None:
                continue
            centers.append(
                {
                    "label": str(row.get("candidateId") or f"comparison-center-{len(centers) + 1:06d}"),
                    "address": format_hex(address_int),
                    "addressInt": address_int,
                    "source": source,
                    "candidateId": row.get("candidateId"),
                    "maxAbsDelta": float_or_none(row.get("maxAbsDelta")),
                    "status": row.get("status"),
                    "twoReferenceStatus": row.get("twoReferenceStatus"),
                }
            )
    return centers


def centers_from_candidate_file(path: Path, repo_root: Path) -> list[dict[str, Any]]:
    document = read_json(path)
    centers: list[dict[str, Any]] = []
    for index, record in enumerate(candidate_records(document), start=1):
        address_int = parse_address(candidate_address(record))
        if address_int is None:
            continue
        center_id = candidate_id(record, index)
        centers.append(
            {
                "label": center_id,
                "address": format_hex(address_int),
                "addressInt": address_int,
                "source": path_text(path, repo_root),
                "candidateId": center_id,
                "maxAbsDelta": float_or_none(record.get("best_max_abs_distance") or record.get("maxAbsDelta")),
                "status": record.get("status") or record.get("classification"),
            }
        )
    return centers


def rank_and_deduplicate_centers(centers: Sequence[dict[str, Any]], max_centers: int) -> list[dict[str, Any]]:
    dedup: dict[int, dict[str, Any]] = {}
    for center in centers:
        address_int = center.get("addressInt")
        if not isinstance(address_int, int):
            continue
        existing = dedup.get(address_int)
        if existing is None:
            dedup[address_int] = dict(center)
            continue
        current_delta = float("inf") if center.get("maxAbsDelta") is None else float(center["maxAbsDelta"])
        existing_delta = float("inf") if existing.get("maxAbsDelta") is None else float(existing["maxAbsDelta"])
        if current_delta < existing_delta:
            dedup[address_int] = dict(center)
    ranked = sorted(
        dedup.values(),
        key=lambda item: (
            float("inf") if item.get("maxAbsDelta") is None else float(item["maxAbsDelta"]),
            str(item.get("candidateId") or ""),
            int(item.get("addressInt") or 0),
        ),
    )
    trimmed = ranked[:max(0, max_centers)]
    for index, center in enumerate(trimmed, start=1):
        center["rank"] = index
    return trimmed


def build_center_file(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-coordinate-scan-centers",
        "generatedAtUtc": summary.get("generatedAtUtc"),
        "sourceSummary": summary.get("comparisonSummary"),
        "centers": summary.get("centers") or [],
        "safety": summary.get("safety"),
    }


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Coordinate scan center file",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Comparison summary: `{summary.get('comparisonSummary')}`",
        f"- Center count: `{len(summary.get('centers') or [])}`",
        f"- Center file: `{summary.get('artifacts', {}).get('centerFile')}`",
        "",
        "## Centers",
        "",
        "| Rank | Label | Address | Max abs delta | Source |",
        "|---:|---|---|---:|---|",
    ]
    for center in summary.get("centers") or []:
        lines.append(
            f"| `{center.get('rank')}` | `{center.get('label')}` | `{center.get('address')}` | "
            f"`{center.get('maxAbsDelta')}` | `{center.get('source')}` |"
        )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in summary.get("blockers") or [])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{item}`" for item in summary.get("warnings") or [])
    lines.extend(["", "This helper is offline/read-only and does not read target memory or send input.", ""])
    return "\n".join(lines)


def build_html(summary: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape("" if value is None else str(value), quote=True)

    rows = "\n".join(
        "<tr>"
        f"<td>{esc(center.get('rank'))}</td>"
        f"<td><code>{esc(center.get('label'))}</code></td>"
        f"<td><code>{esc(center.get('address'))}</code></td>"
        f"<td>{esc(center.get('maxAbsDelta'))}</td>"
        f"<td><code>{esc(center.get('source'))}</code></td>"
        "</tr>"
        for center in summary.get("centers") or []
    )
    blockers = "".join(f"<li><code>{esc(item)}</code></li>" for item in summary.get("blockers") or []) or "<li>None</li>"
    warnings = "".join(f"<li><code>{esc(item)}</code></li>" for item in summary.get("warnings") or []) or "<li>None</li>"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Coordinate scan center file - {esc(summary.get('status'))}</title>
<style>
body {{ margin:0; background:#07111f; color:#e5eefb; font-family:"Segoe UI", system-ui, sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:32px 22px 48px; }}
.hero {{ border:1px solid #263a57; border-radius:22px; padding:24px; background:linear-gradient(135deg, rgba(16,185,129,.15), rgba(56,189,248,.10)); }}
table {{ width:100%; border-collapse:collapse; background:#0f1b2e; border:1px solid #263a57; border-radius:14px; overflow:hidden; }}
th, td {{ padding:11px 13px; border-bottom:1px solid #263a57; text-align:left; vertical-align:top; }}
th {{ color:#bae6fd; }}
code {{ background:#020817; border:1px solid #263a57; padding:2px 6px; border-radius:6px; color:#bfdbfe; overflow-wrap:anywhere; }}
</style>
</head>
<body><main>
<section class="hero">
<h1>Coordinate scan center file</h1>
<p>Status: <code>{esc(summary.get('status'))}</code></p>
<p>Comparison summary: <code>{esc(summary.get('comparisonSummary'))}</code></p>
<p>Center file: <code>{esc(summary.get('artifacts', {}).get('centerFile'))}</code></p>
</section>
<h2>Centers</h2>
<table><tr><th>Rank</th><th>Label</th><th>Address</th><th>Max abs delta</th><th>Source</th></tr>{rows}</table>
<h2>Blockers</h2><ul>{blockers}</ul>
<h2>Warnings</h2><ul>{warnings}</ul>
<p>This helper is offline/read-only and does not read target memory or send input.</p>
</main></body></html>
"""


def upsert_markdown_table_rows(text: str, heading_prefix: str, rows: dict[str, str]) -> str:
    lines = text.splitlines()
    heading_index = next((index for index, line in enumerate(lines) if line.startswith(heading_prefix)), None)
    if heading_index is None:
        appended = [
            "",
            heading_prefix,
            "",
            "| Field | Value |",
            "|---|---|",
            *[f"| {label} | `{value}` |" for label, value in rows.items()],
        ]
        return "\n".join([*lines, *appended]).rstrip() + "\n"
    table_start = None
    for index in range(heading_index + 1, len(lines)):
        if lines[index].strip() == "| Field | Value |":
            table_start = index
            break
        if index > heading_index and lines[index].startswith("## "):
            break
    if table_start is None:
        lines[heading_index + 1:heading_index + 1] = [
            "",
            "| Field | Value |",
            "|---|---|",
            *[f"| {label} | `{value}` |" for label, value in rows.items()],
        ]
        return "\n".join(lines).rstrip() + "\n"
    table_end = table_start + 2
    while table_end < len(lines) and lines[table_end].startswith("|"):
        table_end += 1
    updated: set[str] = set()
    for index in range(table_start + 2, table_end):
        parts = [part.strip() for part in lines[index].strip().strip("|").split("|")]
        if len(parts) < 2:
            continue
        label = parts[0]
        if label in rows:
            lines[index] = f"| {label} | `{rows[label]}` |"
            updated.add(label)
    lines[table_end:table_end] = [f"| {label} | `{value}` |" for label, value in rows.items() if label not in updated]
    return "\n".join(lines).rstrip() + "\n"


def update_current_truth(summary: dict[str, Any], repo_root: Path) -> None:
    truth_path = repo_root / "docs" / "recovery" / "current-truth.json"
    if not truth_path.exists():
        summary.setdefault("warnings", []).append(f"current-truth-json-missing:{truth_path}")
        return
    document = dict_or_empty(read_json(truth_path))
    routing = document.setdefault("visualEvidenceRouting", {})
    artifacts = dict_or_empty(summary.get("artifacts"))
    if artifacts.get("centerFile"):
        routing["latestGeneratedCenterFile"] = path_text(Path(str(artifacts["centerFile"])), repo_root)
    if artifacts.get("summaryJson"):
        routing["latestGeneratedCenterFileSummary"] = path_text(Path(str(artifacts["summaryJson"])), repo_root)
    if artifacts.get("summaryHtml"):
        routing["latestGeneratedCenterFileHtml"] = path_text(Path(str(artifacts["summaryHtml"])), repo_root)
    write_json(truth_path, document)

    markdown_path = repo_root / "docs" / "recovery" / "current-truth.md"
    if not markdown_path.exists():
        summary.setdefault("warnings", []).append(f"current-truth-markdown-missing:{markdown_path}")
        return
    rows = {
        "Latest generated center file": routing.get("latestGeneratedCenterFile", ""),
        "Latest generated center file summary": routing.get("latestGeneratedCenterFileSummary", ""),
        "Latest generated center file HTML": routing.get("latestGeneratedCenterFileHtml", ""),
    }
    updated = upsert_markdown_table_rows(
        markdown_path.read_text(encoding="utf-8"),
        "## Visual/capture proof-route policy",
        {key: value for key, value in rows.items() if value},
    )
    write_text_atomic(markdown_path, updated)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a coordinate scan center file from existing candidate evidence.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--comparison-summary", type=Path)
    parser.add_argument("--candidate-file", type=Path, action="append", default=[])
    parser.add_argument("--max-centers", type=int, default=16)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--update-current-truth", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    run_dir = (args.output_root or repo_root / "scripts" / "captures" / f"coordinate-center-file-{utc_stamp()}").resolve()
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    summary_html = run_dir / "summary.html"
    center_file = run_dir / "coordinate-scan-centers.json"
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-coordinate-center-file",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "blockers": [],
        "warnings": [],
        "errors": [],
        "repoRoot": str(repo_root),
        "comparisonSummary": None,
        "comparisonSummaryResolvedFromAlias": None,
        "candidateFiles": [],
        "centers": [],
        "artifacts": {
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
            "summaryHtml": str(summary_html),
            "centerFile": str(center_file),
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgAttached": False,
            "processAttachOrMemoryReadStarted": False,
            "providerWrite": False,
            "githubConnectorWrites": False,
        },
    }
    try:
        centers: list[dict[str, Any]] = []
        comparison_summary, comparison_alias, comparison_error = resolve_comparison_summary(repo_root, args.comparison_summary)
        summary["comparisonSummaryResolvedFromAlias"] = comparison_alias
        if comparison_error and not args.candidate_file:
            summary["blockers"].append(comparison_error)
        if comparison_summary is not None:
            summary["comparisonSummary"] = path_text(comparison_summary, repo_root)
            if comparison_summary.exists():
                centers.extend(centers_from_comparison_summary(comparison_summary, repo_root))
            elif not args.candidate_file:
                summary["blockers"].append(f"comparison-summary-missing:{comparison_summary}")

        for candidate_value in args.candidate_file:
            candidate_path = candidate_value if candidate_value.is_absolute() else repo_root / candidate_value
            summary["candidateFiles"].append(path_text(candidate_path, repo_root))
            if not candidate_path.exists():
                summary["warnings"].append(f"candidate-file-missing:{candidate_path}")
                continue
            try:
                centers.extend(centers_from_candidate_file(candidate_path, repo_root))
            except Exception as exc:  # noqa: BLE001 - preserve partial center generation.
                summary["warnings"].append(f"candidate-file-unreadable:{candidate_path}:{type(exc).__name__}:{exc}")

        summary["centers"] = rank_and_deduplicate_centers(centers, args.max_centers)
        if not summary["centers"]:
            summary["blockers"].append("no-center-addresses-found")
            summary["status"] = "blocked"
            return 2
        summary["status"] = "passed"
        return 0
    except Exception as exc:  # noqa: BLE001 - durable error capture.
        summary["status"] = "failed"
        summary["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        return 1
    finally:
        if summary.get("centers"):
            write_json(center_file, build_center_file(summary))
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
