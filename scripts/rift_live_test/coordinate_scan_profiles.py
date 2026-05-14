from __future__ import annotations

import argparse
import html
import json
import math
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ScanProfile:
    name: str
    max_seconds: int
    max_hits: int
    chunk_bytes: int
    scan_stride: int
    tolerance: float


PROFILES: dict[str, ScanProfile] = {
    "quick": ScanProfile("quick", max_seconds=20, max_hits=128, chunk_bytes=4 * 1024 * 1024, scan_stride=4, tolerance=0.25),
    "wide": ScanProfile("wide", max_seconds=75, max_hits=512, chunk_bytes=8 * 1024 * 1024, scan_stride=4, tolerance=0.25),
    "wide-stride1": ScanProfile("wide-stride1", max_seconds=75, max_hits=512, chunk_bytes=4 * 1024 * 1024, scan_stride=1, tolerance=0.25),
    "historical-neighborhood": ScanProfile(
        "historical-neighborhood",
        max_seconds=20,
        max_hits=128,
        chunk_bytes=2 * 1024 * 1024,
        scan_stride=4,
        tolerance=0.25,
    ),
}

DEFAULT_HISTORICAL_CENTERS = [
    ("0x268D5A80730", "pid2928-last-readback-reference-match"),
    ("0x268DF21ED30", "pid2928-best-focused-offset-copy-candidate"),
    ("0x268DF21ED20", "pid2928-broad-delta-offset-copy-candidate"),
    ("0x268DF200000", "pid2928-offset-copy-family-base"),
    ("0x1FF07570000", "pid60628-destination-copy-family"),
    ("0x1FF08502BC8", "pid60628-best-exact-threepose-candidate"),
    ("0x2400EA32120", "older-riftscan-first-proof-anchor"),
]

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


def file_mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def path_text(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def normalize_hwnd(value: str) -> str:
    text = str(value).strip()
    try:
        return f"0x{int(text, 0):X}"
    except ValueError:
        return text


def parse_center(value: str) -> tuple[int, str]:
    if "=" in value:
        label, address = value.split("=", 1)
    else:
        label, address = "manual-center", value
    return int(address, 0), label.strip() or "manual-center"


def format_hex(value: int) -> str:
    return f"0x{max(0, value):X}"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON file is not an object: {path}")
    return value


def dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def json_hwnd(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return normalize_hwnd(str(value))


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


def displaced_reference_marker(path: Path, document: dict[str, Any]) -> str | None:
    text_parts = [str(path).replace("\\", "/").lower()]
    for key in (
        "pose",
        "poseLabel",
        "label",
        "source",
        "notes",
        "description",
        "mode",
        "captureContext",
        "referenceKind",
    ):
        value = document.get(key)
        if value not in (None, ""):
            text_parts.append(str(value).lower())
    for marker in DISPLACED_REFERENCE_MARKERS:
        if any(marker in text for text in text_parts):
            return marker
    return None


def find_latest_reference_file(
    repo_root: Path,
    *,
    pid: int | None,
    hwnd: str | None,
    require_displaced: bool = False,
) -> Path | None:
    captures = repo_root / "scripts" / "captures"
    if not captures.exists():
        return None
    candidates = sorted(
        captures.rglob("rift-api-reference-currentpid-*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    normalized_hwnd = normalize_hwnd(hwnd) if hwnd else None
    for path in candidates:
        try:
            document = read_json(path)
        except Exception:  # noqa: BLE001 - skip unreadable historical artifacts.
            continue
        candidate_pid = json_pid(document.get("processId") or document.get("ProcessId"))
        candidate_hwnd = json_hwnd(document.get("targetWindowHandle") or document.get("TargetWindowHandle"))
        if pid is not None and candidate_pid is not None and candidate_pid != pid:
            continue
        if normalized_hwnd and candidate_hwnd and candidate_hwnd != normalized_hwnd:
            continue
        if require_displaced and displaced_reference_marker(path, document) is None:
            continue
        return path
    return None


def resolve_reference_file(repo_root: Path, value: Path | None, *, pid: int | None, hwnd: str | None) -> tuple[Path | None, str | None, str | None]:
    if value is None:
        return None, None, None
    alias = str(value).strip().lower()
    if alias in {"latest", "latest-displaced"}:
        latest = find_latest_reference_file(repo_root, pid=pid, hwnd=hwnd, require_displaced=alias == "latest-displaced")
        if latest is None:
            error = "displaced-reference-latest-not-found" if alias == "latest-displaced" else "reference-file-latest-not-found"
            return None, alias, error
        return latest, alias, None
    path = value if value.is_absolute() else repo_root / value
    return path, None, None


def load_center_file(path: Path) -> list[tuple[int, str]]:
    document = read_json(path)
    values: Any = document.get("centers") if isinstance(document, dict) else document
    if isinstance(values, dict):
        values = [values]
    centers: list[tuple[int, str]] = []
    for item in values if isinstance(values, list) else []:
        if isinstance(item, str):
            centers.append(parse_center(item))
            continue
        if isinstance(item, dict):
            address = item.get("address") or item.get("addressHex") or item.get("centerAddress")
            label = str(item.get("label") or item.get("name") or "center-file")
            if address not in (None, ""):
                centers.append((int(str(address), 0), label))
    return centers


def all_centers(extra_centers: Iterable[str], center_files: Iterable[Path], repo_root: Path) -> list[tuple[int, str]]:
    centers = default_centers(extra_centers)
    for file_value in center_files:
        path = file_value if file_value.is_absolute() else repo_root / file_value
        centers.extend(load_center_file(path))
    dedup: dict[int, str] = {}
    for address, label in centers:
        dedup.setdefault(address, label)
    return [(address, label) for address, label in dedup.items()]


def run_command(args: list[str], cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    started = time.monotonic()
    started_at = utc_iso()
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "args": args,
            "cwd": str(cwd),
            "startedAtUtc": started_at,
            "completedAtUtc": utc_iso(),
            "durationSeconds": round(time.monotonic() - started, 3),
            "exitCode": proc.returncode,
            "stdoutPreview": proc.stdout[:4000],
            "stderrPreview": proc.stderr[:4000],
            "timedOut": False,
            "stdoutJson": parse_stdout_json(proc.stdout),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "args": args,
            "cwd": str(cwd),
            "startedAtUtc": started_at,
            "completedAtUtc": utc_iso(),
            "durationSeconds": round(time.monotonic() - started, 3),
            "exitCode": None,
            "stdoutPreview": (exc.stdout or "")[:4000],
            "stderrPreview": (exc.stderr or "")[:4000],
            "timedOut": True,
            "timeoutSeconds": timeout_seconds,
        }


def parse_stdout_json(text: str) -> Any | None:
    value = (text or "").strip()
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        starts = [idx for idx in (value.find("{"), value.find("[")) if idx >= 0]
        if not starts:
            return None
        try:
            parsed, _ = json.JSONDecoder().raw_decode(value[min(starts):])
            return parsed
        except json.JSONDecodeError:
            return None


def profile_commands(
    *,
    repo_root: Path,
    pid: int,
    hwnd: str,
    process_name: str,
    reference_file: Path,
    profiles: Sequence[str],
    centers: Sequence[tuple[int, str]],
    historical_radius_bytes: int,
) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    scan_script = repo_root / "scripts" / "scan_current_pid_coordinate_family.py"
    for name in profiles:
        profile = PROFILES[name]
        base_args = [
            sys.executable,
            str(scan_script),
            "--pid",
            str(pid),
            "--hwnd",
            hwnd,
            "--process-name",
            process_name,
            "--reference-file",
            str(reference_file),
            "--max-seconds",
            str(profile.max_seconds),
            "--max-hits",
            str(profile.max_hits),
            "--chunk-bytes",
            str(profile.chunk_bytes),
            "--scan-stride",
            str(profile.scan_stride),
            "--tolerance",
            str(profile.tolerance),
            "--json",
        ]
        if name == "historical-neighborhood":
            for address, label in centers:
                minimum = max(0, address - historical_radius_bytes)
                maximum = address + historical_radius_bytes
                commands.append(
                    {
                        "profile": name,
                        "label": label,
                        "centerAddress": format_hex(address),
                        "args": [
                            *base_args,
                            "--min-address",
                            format_hex(minimum),
                            "--max-address",
                            format_hex(maximum),
                        ],
                        "timeoutSeconds": profile.max_seconds + 60,
                    }
                )
        else:
            commands.append(
                {
                    "profile": name,
                    "label": name,
                    "args": base_args,
                    "timeoutSeconds": profile.max_seconds + 60,
                }
            )
    return commands


def rank_profile_runs(profile_runs: Sequence[dict[str, Any]], repo_root: Path) -> list[dict[str, Any]]:
    rankings: list[dict[str, Any]] = []
    for run in profile_runs:
        parsed = dict_or_empty(run.get("stdoutJson"))
        scan = dict_or_empty(parsed.get("scan"))
        best_hit = dict_or_empty(scan.get("bestHit") or parsed.get("bestHit"))
        artifacts = dict_or_empty(parsed.get("artifacts"))
        hit_count = int_or_zero(scan.get("hitCount"))
        best_max_abs_delta = float_or_none(best_hit.get("maxAbsDelta") or best_hit.get("best_max_abs_distance"))
        bytes_scanned = int_or_zero(scan.get("bytesScanned"))
        rankings.append(
            {
                "profile": run.get("profile"),
                "label": run.get("label"),
                "exitCode": run.get("exitCode"),
                "status": parsed.get("status"),
                "hitCount": hit_count,
                "bestMaxAbsDelta": best_max_abs_delta,
                "bytesScanned": bytes_scanned,
                "summaryJson": artifacts.get("summaryJson"),
                "candidateJson": artifacts.get("candidateJson"),
                "candidateJsonl": artifacts.get("candidateJsonl"),
            }
        )
    rankings.sort(
        key=lambda item: (
            -int_or_zero(item.get("hitCount")),
            float("inf") if item.get("bestMaxAbsDelta") is None else float(item["bestMaxAbsDelta"]),
            -int_or_zero(item.get("bytesScanned")),
            str(item.get("profile") or ""),
            str(item.get("label") or ""),
        )
    )
    for rank, item in enumerate(rankings, start=1):
        item["rank"] = rank
        for key in ("summaryJson", "candidateJson", "candidateJsonl"):
            value = item.get(key)
            if value:
                item[key] = path_text(Path(str(value)), repo_root)
    return rankings


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Coordinate scan profile run",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Target: `{summary.get('processName')}` PID `{summary.get('processId')}`, HWND `{summary.get('targetWindowHandle')}`",
        f"- Reference file: `{summary.get('referenceFile')}`",
        f"- Movement sent: `{str(summary.get('safety', {}).get('movementSent')).lower()}`",
        f"- Input sent: `{str(summary.get('safety', {}).get('inputSent')).lower()}`",
        f"- No Cheat Engine: `{str(summary.get('safety', {}).get('noCheatEngine')).lower()}`",
        "",
        "## Profiles",
        "",
        "| Profile | Label | Exit | Status | Hits | Summary |",
        "|---|---|---:|---|---:|---|",
    ]
    for run in summary.get("profileRuns") or []:
        parsed = run.get("stdoutJson") if isinstance(run.get("stdoutJson"), dict) else {}
        lines.append(
            f"| `{run.get('profile')}` | `{run.get('label')}` | `{run.get('exitCode')}` | "
            f"`{parsed.get('status')}` | `{(parsed.get('scan') or {}).get('hitCount')}` | "
            f"`{(parsed.get('artifacts') or {}).get('summaryJson')}` |"
        )
    if summary.get("profileRankings"):
        lines.extend(
            [
                "",
                "## Profile rankings",
                "",
                "| Rank | Profile | Label | Hits | Best max abs delta | Bytes scanned | Summary |",
                "|---:|---|---|---:|---:|---:|---|",
            ]
        )
        for item in summary.get("profileRankings") or []:
            lines.append(
                f"| `{item.get('rank')}` | `{item.get('profile')}` | `{item.get('label')}` | "
                f"`{item.get('hitCount')}` | `{item.get('bestMaxAbsDelta')}` | `{item.get('bytesScanned')}` | "
                f"`{item.get('summaryJson')}` |"
            )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in summary.get("blockers") or [])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{item}`" for item in summary.get("warnings") or [])
    lines.extend(["", "Movement remains blocked. This helper never sends input and never uses CE/x64dbg.", ""])
    return "\n".join(lines)


def build_html(summary: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape("" if value is None else str(value), quote=True)

    rows = "\n".join(
        "<tr>"
        f"<td><code>{esc(run.get('profile'))}</code></td>"
        f"<td><code>{esc(run.get('label'))}</code></td>"
        f"<td>{esc(run.get('exitCode'))}</td>"
        f"<td><code>{esc((run.get('stdoutJson') or {}).get('status') if isinstance(run.get('stdoutJson'), dict) else None)}</code></td>"
        f"<td>{esc(((run.get('stdoutJson') or {}).get('scan') or {}).get('hitCount') if isinstance(run.get('stdoutJson'), dict) else None)}</td>"
        f"<td><code>{esc(((run.get('stdoutJson') or {}).get('artifacts') or {}).get('summaryJson') if isinstance(run.get('stdoutJson'), dict) else None)}</code></td>"
        "</tr>"
        for run in summary.get("profileRuns") or []
    )
    planned_rows = "\n".join(
        "<tr>"
        f"<td><code>{esc(item.get('profile'))}</code></td>"
        f"<td><code>{esc(item.get('label'))}</code></td>"
        f"<td><code>{esc(' '.join(item.get('args') or []))}</code></td>"
        "</tr>"
        for item in summary.get("plannedCommands") or []
    )
    ranking_rows = "\n".join(
        "<tr>"
        f"<td>{esc(item.get('rank'))}</td>"
        f"<td><code>{esc(item.get('profile'))}</code></td>"
        f"<td><code>{esc(item.get('label'))}</code></td>"
        f"<td>{esc(item.get('hitCount'))}</td>"
        f"<td>{esc(item.get('bestMaxAbsDelta'))}</td>"
        f"<td>{esc(item.get('bytesScanned'))}</td>"
        f"<td><code>{esc(item.get('summaryJson'))}</code></td>"
        "</tr>"
        for item in summary.get("profileRankings") or []
    )
    blockers = "".join(f"<li><code>{esc(item)}</code></li>" for item in summary.get("blockers") or []) or "<li>None</li>"
    warnings = "".join(f"<li><code>{esc(item)}</code></li>" for item in summary.get("warnings") or []) or "<li>None</li>"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Coordinate scan profiles - {esc(summary.get('status'))}</title>
<style>
body {{ margin:0; background:#07111f; color:#e5eefb; font-family:"Segoe UI", system-ui, sans-serif; }}
main {{ max-width:1180px; margin:0 auto; padding:32px 22px 48px; }}
.hero {{ border:1px solid #263a57; border-radius:22px; padding:24px; background:linear-gradient(135deg, rgba(56,189,248,.15), rgba(167,139,250,.10)); }}
table {{ width:100%; border-collapse:collapse; background:#0f1b2e; border:1px solid #263a57; border-radius:14px; overflow:hidden; }}
th, td {{ padding:11px 13px; border-bottom:1px solid #263a57; text-align:left; vertical-align:top; }}
th {{ color:#bae6fd; }}
code {{ background:#020817; border:1px solid #263a57; padding:2px 6px; border-radius:6px; color:#bfdbfe; overflow-wrap:anywhere; }}
</style>
</head>
<body><main>
<section class="hero">
<h1>Coordinate scan profile run</h1>
<p>Status: <code>{esc(summary.get('status'))}</code></p>
<p>Target: <code>{esc(summary.get('processName'))}</code> PID <code>{esc(summary.get('processId'))}</code>, HWND <code>{esc(summary.get('targetWindowHandle'))}</code></p>
<p>Reference: <code>{esc(summary.get('referenceFile'))}</code></p>
</section>
<h2>Profile runs</h2>
<table><tr><th>Profile</th><th>Label</th><th>Exit</th><th>Status</th><th>Hits</th><th>Summary</th></tr>{rows}</table>
<h2>Profile rankings</h2>
<table><tr><th>Rank</th><th>Profile</th><th>Label</th><th>Hits</th><th>Best max abs delta</th><th>Bytes scanned</th><th>Summary</th></tr>{ranking_rows}</table>
<h2>Planned commands</h2>
<table><tr><th>Profile</th><th>Label</th><th>Command</th></tr>{planned_rows}</table>
<h2>Blockers</h2><ul>{blockers}</ul>
<h2>Warnings</h2><ul>{warnings}</ul>
<p>Movement remains blocked. This helper never sends input and never uses CE/x64dbg.</p>
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
        insert_at = heading_index + 1
        new_table = ["", "| Field | Value |", "|---|---|", *[f"| {label} | `{value}` |" for label, value in rows.items()]]
        lines[insert_at:insert_at] = new_table
        return "\n".join(lines).rstrip() + "\n"

    table_end = table_start + 2
    while table_end < len(lines) and lines[table_end].startswith("|"):
        table_end += 1

    existing_labels: set[str] = set()
    for index in range(table_start + 2, table_end):
        parts = [part.strip() for part in lines[index].strip().strip("|").split("|")]
        if len(parts) < 2:
            continue
        label = parts[0]
        if label in rows:
            lines[index] = f"| {label} | `{rows[label]}` |"
            existing_labels.add(label)
    additions = [f"| {label} | `{value}` |" for label, value in rows.items() if label not in existing_labels]
    lines[table_end:table_end] = additions
    return "\n".join(lines).rstrip() + "\n"


def update_current_truth(summary: dict[str, Any], repo_root: Path) -> None:
    truth_path = repo_root / "docs" / "recovery" / "current-truth.json"
    if not truth_path.exists():
        summary.setdefault("warnings", []).append(f"current-truth-json-missing:{truth_path}")
        return
    document = read_json(truth_path)
    routing = document.setdefault("visualEvidenceRouting", {})
    artifacts = summary.get("artifacts") or {}
    is_dry_run = "dry-run requested; no profile commands executed" in (summary.get("warnings") or [])
    if not is_dry_run:
        routing["latestScanProfileRun"] = path_text(Path(str(artifacts.get("summaryJson"))), repo_root)
        routing["latestScanProfileHtml"] = path_text(Path(str(artifacts.get("summaryHtml"))), repo_root)
        if summary.get("profileRankings"):
            routing["latestScanProfileRanking"] = path_text(Path(str(artifacts.get("summaryJson"))), repo_root)
    if is_dry_run:
        routing["latestScanProfilePlan"] = path_text(Path(str(artifacts.get("summaryJson"))), repo_root)
        routing["latestScanProfilePlanHtml"] = path_text(Path(str(artifacts.get("summaryHtml"))), repo_root)
    if any(item in (summary.get("blockers") or []) for item in ("manual-displaced-reference-required", "displaced-reference-latest-not-found")):
        routing["latestManualDisplacementBlocker"] = path_text(Path(str(artifacts.get("summaryJson"))), repo_root)
        routing["latestManualDisplacementBlockerHtml"] = path_text(Path(str(artifacts.get("summaryHtml"))), repo_root)
    write_json(truth_path, document)
    markdown_path = repo_root / "docs" / "recovery" / "current-truth.md"
    if not markdown_path.exists():
        summary.setdefault("warnings", []).append(f"current-truth-markdown-missing:{markdown_path}")
        return
    markdown_rows = {
    }
    if routing.get("latestScanProfileRun"):
        markdown_rows["Latest scan-profile run"] = routing["latestScanProfileRun"]
        markdown_rows["Latest scan-profile run HTML"] = routing["latestScanProfileHtml"]
    if routing.get("latestScanProfilePlan"):
        markdown_rows["Latest scan-profile plan"] = routing["latestScanProfilePlan"]
        markdown_rows["Latest scan-profile plan HTML"] = routing["latestScanProfilePlanHtml"]
    if routing.get("latestManualDisplacementBlocker"):
        markdown_rows["Latest manual displacement blocker"] = routing["latestManualDisplacementBlocker"]
        markdown_rows["Latest manual displacement blocker HTML"] = routing["latestManualDisplacementBlockerHtml"]
    if routing.get("latestScanProfileRanking"):
        markdown_rows["Latest scan-profile ranking"] = routing["latestScanProfileRanking"]
    updated_markdown = upsert_markdown_table_rows(
        markdown_path.read_text(encoding="utf-8"),
        "## Visual/capture proof-route policy",
        markdown_rows,
    )
    write_text_atomic(markdown_path, updated_markdown)


def final_status(summary: dict[str, Any]) -> tuple[str, int]:
    if summary.get("errors"):
        return "failed", 1
    if summary.get("blockers"):
        return "blocked", 2
    hits = [
        ((run.get("stdoutJson") or {}).get("scan") or {}).get("hitCount")
        for run in summary.get("profileRuns") or []
        if isinstance(run.get("stdoutJson"), dict)
    ]
    if any(isinstance(hit, int) and hit > 0 for hit in hits):
        return "passed", 0
    return "blocked", 2


def default_centers(extra_centers: Iterable[str]) -> list[tuple[int, str]]:
    centers = [(int(address, 0), label) for address, label in DEFAULT_HISTORICAL_CENTERS]
    centers.extend(parse_center(value) for value in extra_centers)
    dedup: dict[int, str] = {}
    for address, label in centers:
        dedup.setdefault(address, label)
    return [(address, label) for address, label in dedup.items()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run repeatable no-input coordinate family scan profiles.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--pid", type=int)
    parser.add_argument("--hwnd")
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--reference-file", type=Path)
    parser.add_argument("--displaced-reference-file", type=Path)
    parser.add_argument("--require-displaced-pose", action="store_true")
    parser.add_argument("--profile", choices=sorted(PROFILES), action="append", default=[])
    parser.add_argument("--historical-center", action="append", default=[], help="Optional label=0xADDRESS center.")
    parser.add_argument("--historical-center-file", type=Path, action="append", default=[], help="JSON file with centers as strings or objects.")
    parser.add_argument("--historical-radius-bytes", type=lambda v: int(v, 0), default=16 * 1024 * 1024)
    parser.add_argument("--update-current-truth", action="store_true")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    run_dir = (args.output_root or repo_root / "scripts" / "captures" / f"coordinate-scan-profiles-{utc_stamp()}").resolve()
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    summary_html = run_dir / "summary.html"
    profiles = args.profile or ["quick", "historical-neighborhood"]
    hwnd = normalize_hwnd(args.hwnd or "0x0")
    reference_file, reference_alias, reference_error = resolve_reference_file(repo_root, args.reference_file, pid=args.pid, hwnd=hwnd)
    displaced_reference_file, displaced_reference_alias, displaced_reference_error = resolve_reference_file(
        repo_root,
        args.displaced_reference_file,
        pid=args.pid,
        hwnd=hwnd,
    )
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-coordinate-scan-profiles",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "blockers": [],
        "warnings": [],
        "errors": [],
        "repoRoot": str(repo_root),
        "processName": args.process_name,
        "processId": args.pid,
        "targetWindowHandle": hwnd,
        "referenceFile": str(reference_file) if reference_file else None,
        "referenceFileModifiedUtc": file_mtime_utc(reference_file) if reference_file and reference_file.exists() else None,
        "referenceFileResolvedFromAlias": reference_alias,
        "displacedReferenceFile": str(displaced_reference_file) if displaced_reference_file else None,
        "displacedReferenceFileModifiedUtc": file_mtime_utc(displaced_reference_file) if displaced_reference_file and displaced_reference_file.exists() else None,
        "displacedReferenceFileResolvedFromAlias": displaced_reference_alias,
        "profiles": profiles,
        "profileRuns": [],
        "artifacts": {"summaryJson": str(summary_json), "summaryMarkdown": str(summary_md), "summaryHtml": str(summary_html), "runDirectory": str(run_dir)},
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgAttached": False,
            "providerWrite": False,
            "githubConnectorWrites": False,
        },
    }
    try:
        if args.self_test:
            summary["status"] = "passed"
            summary["warnings"].append("self-test only; no live process scan executed")
            return_code = 0
            return return_code
        if args.pid is None:
            summary["blockers"].append("target-pid-required")
        if not args.hwnd:
            summary["blockers"].append("target-hwnd-required")
        if reference_error:
            summary["blockers"].append(reference_error)
        if displaced_reference_error:
            summary["blockers"].append(displaced_reference_error)
        if reference_file is None:
            summary["blockers"].append("reference-file-required")
        elif not reference_file.exists():
            summary["blockers"].append(f"reference-file-missing:{reference_file}")
        if args.require_displaced_pose and displaced_reference_file is None:
            summary["blockers"].append("manual-displaced-reference-required")
        if displaced_reference_file is not None and not displaced_reference_file.exists():
            summary["blockers"].append(f"displaced-reference-file-missing:{displaced_reference_file}")
        if reference_file is not None and reference_file.exists() and displaced_reference_file is not None and displaced_reference_file.exists():
            if displaced_reference_file.stat().st_mtime < reference_file.stat().st_mtime:
                summary["warnings"].append("displaced-reference-older-than-baseline-reference")
        for profile in profiles:
            if profile not in PROFILES:
                summary["blockers"].append(f"unknown-profile:{profile}")
        centers: list[tuple[int, str]] = []
        try:
            centers = all_centers(args.historical_center, args.historical_center_file, repo_root)
        except Exception as exc:  # noqa: BLE001 - center files are operator input.
            summary["blockers"].append(f"historical-center-file-unreadable:{type(exc).__name__}:{exc}")
        if summary["blockers"]:
            summary["status"] = "blocked"
            return 2
        commands = profile_commands(
            repo_root=repo_root,
            pid=int(args.pid),
            hwnd=hwnd,
            process_name=args.process_name,
            reference_file=reference_file.resolve(),
            profiles=profiles,
            centers=centers,
            historical_radius_bytes=args.historical_radius_bytes,
        )
        summary["plannedCommands"] = commands
        if args.dry_run:
            summary["status"] = "blocked"
            summary["warnings"].append("dry-run requested; no profile commands executed")
            return 2
        for command in commands:
            envelope = run_command(command["args"], repo_root, command["timeoutSeconds"])
            summary["profileRuns"].append({**command, **envelope})
        summary["profileRankings"] = rank_profile_runs(summary["profileRuns"], repo_root)
        summary["bestProfileRun"] = summary["profileRankings"][0] if summary["profileRankings"] else None
        status, return_code = final_status(summary)
        summary["status"] = status
        if status == "blocked" and not summary["blockers"]:
            summary["blockers"].append("no-profile-found-current-coordinate-triplets")
        return return_code
    except Exception as exc:  # noqa: BLE001 - preserve durable blocker evidence.
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
            except Exception as exc:  # noqa: BLE001 - preserve run output even if truth update fails.
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
