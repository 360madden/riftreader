from __future__ import annotations

import argparse
import json
import re
import string
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .reference_freshness_watchdog import marker_fields, marker_is_usable, path_text, safe_dict, safe_list
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_LATEST_COUNT = 3
DEFAULT_MAX_EXAMPLES = 8

MARKER_LIKE_PATTERN = re.compile(r"RRAPICOORD1\|[^\x00\r\n\"'`<>]{0,700}")
RRAPICOORD_TOKEN_PATTERN = re.compile(r"RRAPICOORD1(?:\|[^\x00\r\n\"'`<>]{0,700})?")
CONTROL_TRANS = str.maketrans({ch: " " for ch in "".join(chr(i) for i in range(32)) if ch not in "\r\n\t"})
TEXT_TOKENS = (
    "RRAPICOORD1",
    "source=rift-api",
    "view=Inspect.Unit.Detail(player)",
    "status=pass",
    "status=starting",
    "savedVariablesUse=none",
    "x=",
    "y=",
    "z=",
    "RiftReaderApiProbe",
    "Inspect.Unit.Detail",
)
SOURCE_TEXT_HINTS = (
    "RiftReaderApiProbe",
    "function",
    "local ",
    "return ",
    "table.concat",
    "did not",
    "Inspect.Unit.Detail(player)",
)


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json_object(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return document


def parse_hex_bytes(value: Any) -> bytes:
    if not value:
        return b""
    try:
        return bytes.fromhex(str(value))
    except ValueError:
        return b""


def decode_context_bytes(hex_text: Any) -> list[dict[str, str]]:
    payload = parse_hex_bytes(hex_text)
    if not payload:
        return []
    decoded: list[dict[str, str]] = []
    for encoding in ("utf-8", "utf-16-le", "latin-1"):
        try:
            text = payload.decode(encoding, errors="ignore")
        except LookupError:
            continue
        if "RRAPICOORD1" in text:
            decoded.append({"source": f"bytes:{encoding}", "text": text})
    return decoded


def context_texts(hit: Mapping[str, Any]) -> list[dict[str, str]]:
    context = safe_dict(hit.get("Context"))
    texts: list[dict[str, str]] = []
    for key in ("AsciiPreview", "Utf16Preview"):
        value = context.get(key)
        if value:
            texts.append({"source": key, "text": str(value)})
    texts.extend(decode_context_bytes(context.get("BytesHex")))
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for item in texts:
        key = (item["source"], item["text"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def sanitize_snippet(text: str, max_length: int = 220) -> str:
    cleaned = text.translate(CONTROL_TRANS).replace("\r", " ").replace("\n", " ").replace("\t", " ")
    cleaned = "".join(ch if ch in string.printable or ord(ch) >= 128 else " " for ch in cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 1].rstrip() + "…"


def first_rrapicoord_snippet(text: str, max_length: int = 220) -> str | None:
    index = text.find("RRAPICOORD1")
    if index < 0:
        return None
    start = max(0, index - 70)
    end = min(len(text), index + max_length)
    return sanitize_snippet(text[start:end], max_length=max_length)


def marker_issue_codes(fields: Mapping[str, str]) -> list[str]:
    issues: list[str] = []
    if fields.get("status", "").lower() != "pass":
        issues.append(f"status:{fields.get('status') or 'missing'}")
    if fields.get("source", "").lower() != "rift-api":
        issues.append(f"source:{fields.get('source') or 'missing'}")
    if fields.get("savedVariablesUse", "").lower() != "none":
        issues.append(f"savedVariablesUse:{fields.get('savedVariablesUse') or 'missing'}")
    for axis in ("x", "y", "z"):
        try:
            float(fields[axis])
        except (KeyError, TypeError, ValueError):
            issues.append(f"{axis}:missing-or-not-number")
    return issues


def marker_record(raw: str) -> dict[str, Any]:
    fields = marker_fields(raw)
    issues = marker_issue_codes(fields)
    return {
        "raw": sanitize_snippet(raw, max_length=320),
        "fields": fields,
        "usable": marker_is_usable(fields),
        "issues": issues,
    }


def has_source_text_hint(text: str) -> bool:
    return any(hint in text for hint in SOURCE_TEXT_HINTS)


def analyze_hit(hit: Mapping[str, Any], *, max_examples: int) -> dict[str, Any]:
    texts = context_texts(hit)
    token_presence = {token: False for token in TEXT_TOKENS}
    markers: list[dict[str, Any]] = []
    snippets: list[dict[str, str]] = []
    contains_rrapicoord = False
    source_text_like = False
    seen_marker_raw: set[str] = set()
    seen_snippets: set[str] = set()
    for item in texts:
        text = item["text"]
        if "RRAPICOORD1" not in text:
            continue
        contains_rrapicoord = True
        source_text_like = source_text_like or has_source_text_hint(text)
        for token in token_presence:
            if token in text:
                token_presence[token] = True
        for match in MARKER_LIKE_PATTERN.finditer(text):
            raw = match.group(0).strip()
            if raw and raw not in seen_marker_raw:
                seen_marker_raw.add(raw)
                markers.append(marker_record(raw))
        if len(snippets) < max_examples:
            snippet = first_rrapicoord_snippet(text)
            if snippet and snippet not in seen_snippets:
                seen_snippets.add(snippet)
                snippets.append({"source": item["source"], "text": snippet})
    return {
        "address": hit.get("AddressHex") or hit.get("Address"),
        "encoding": hit.get("Encoding"),
        "classification": hit.get("Classification"),
        "containsRrapicoord": contains_rrapicoord,
        "sourceTextLike": source_text_like,
        "markerLikeCount": len(markers),
        "usableMarkerCount": sum(1 for marker in markers if marker.get("usable")),
        "markers": markers[:max_examples],
        "tokenPresence": token_presence,
        "snippets": snippets[:max_examples],
    }


def counter_to_sorted_dict(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def summarize_scan(path: Path, repo_root: Path, *, max_examples: int) -> dict[str, Any]:
    document = load_json_object(path)
    hits = [hit for hit in safe_list(document.get("Hits")) if isinstance(hit, dict)]
    analyzed_hits = [analyze_hit(hit, max_examples=max_examples) for hit in hits]
    text_hits = [hit for hit in analyzed_hits if hit.get("containsRrapicoord")]
    marker_hits = [hit for hit in analyzed_hits if int(hit.get("markerLikeCount") or 0) > 0]
    usable_markers: list[dict[str, Any]] = []
    issue_counts: Counter[str] = Counter()
    token_presence = {token: False for token in TEXT_TOKENS}
    examples: list[dict[str, Any]] = []
    for hit in analyzed_hits:
        for token, present in safe_dict(hit.get("tokenPresence")).items():
            token_presence[token] = token_presence.get(token, False) or bool(present)
        for marker in safe_list(hit.get("markers")):
            marker_dict = safe_dict(marker)
            if marker_dict.get("usable"):
                usable_markers.append(marker_dict)
            issue_counts.update(str(issue) for issue in safe_list(marker_dict.get("issues")))
        if hit.get("containsRrapicoord") and len(examples) < max_examples:
            examples.append(
                {
                    "address": hit.get("address"),
                    "classification": hit.get("classification"),
                    "sourceTextLike": hit.get("sourceTextLike"),
                    "markerLikeCount": hit.get("markerLikeCount"),
                    "usableMarkerCount": hit.get("usableMarkerCount"),
                    "snippets": safe_list(hit.get("snippets"))[:2],
                    "markers": safe_list(hit.get("markers"))[:2],
                }
            )
    marker_like_count = sum(int(hit.get("markerLikeCount") or 0) for hit in analyzed_hits)
    usable_marker_count = len(usable_markers)
    source_text_hit_count = sum(1 for hit in text_hits if hit.get("sourceTextLike"))
    return {
        "path": path_text(path, repo_root),
        "lastWriteTimeUtc": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "process": {
            "pid": document.get("ProcessId"),
            "name": document.get("ProcessName"),
        },
        "search": {
            "mode": document.get("Mode"),
            "text": document.get("SearchText"),
            "source": document.get("SearchSource"),
            "encoding": document.get("Encoding"),
            "contextBytes": document.get("ContextBytes"),
            "maxHits": document.get("MaxHits"),
        },
        "counts": {
            "reportedHitCount": document.get("HitCount"),
            "loadedHitCount": len(hits),
            "rrapicoordTextHitCount": len(text_hits),
            "sourceTextHitCount": source_text_hit_count,
            "sourceTextOnlyHitCount": sum(1 for hit in text_hits if hit.get("sourceTextLike") and int(hit.get("markerLikeCount") or 0) == 0),
            "markerHitCount": len(marker_hits),
            "markerLikeCount": marker_like_count,
            "partialMarkerCount": max(0, marker_like_count - usable_marker_count),
            "usableMarkerCount": usable_marker_count,
        },
        "tokenPresence": token_presence,
        "markerIssueCounts": counter_to_sorted_dict(issue_counts),
        "usableMarkers": usable_markers[:max_examples],
        "examples": examples,
    }


def latest_scan_paths(repo_root: Path, *, target_pid: int | None, latest_count: int) -> list[Path]:
    captures = repo_root / "scripts" / "captures"
    pattern = f"rift-api-reference-scan-currentpid-{target_pid}-*.json" if target_pid is not None else "rift-api-reference-scan-currentpid-*.json"
    paths = [path for path in captures.glob(pattern) if path.is_file()]
    return sorted(paths, key=lambda path: (path.stat().st_mtime, str(path)), reverse=True)[: max(1, latest_count)]


def resolve_scan_paths(args: argparse.Namespace, repo_root: Path) -> list[Path]:
    paths = [path.resolve() for path in args.scan_file]
    if not paths:
        paths = [path.resolve() for path in latest_scan_paths(repo_root, target_pid=args.target_pid, latest_count=args.latest_count)]
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def aggregate_counts(scans: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    totals: Counter[str] = Counter()
    for scan in scans:
        totals.update({key: int(value or 0) for key, value in safe_dict(scan.get("counts")).items() if isinstance(value, int)})
    return counter_to_sorted_dict(totals)


def aggregate_token_presence(scans: Sequence[Mapping[str, Any]]) -> dict[str, bool]:
    result = {token: False for token in TEXT_TOKENS}
    for scan in scans:
        for token, present in safe_dict(scan.get("tokenPresence")).items():
            result[token] = result.get(token, False) or bool(present)
    return result


def aggregate_issue_counts(scans: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for scan in scans:
        counter.update({str(key): int(value or 0) for key, value in safe_dict(scan.get("markerIssueCounts")).items()})
    return counter_to_sorted_dict(counter)


def infer_causes(counts: Mapping[str, int], tokens: Mapping[str, bool], issues: Mapping[str, int]) -> list[str]:
    causes: list[str] = []
    usable = int(counts.get("usableMarkerCount") or 0)
    marker_like = int(counts.get("markerLikeCount") or 0)
    text_hits = int(counts.get("rrapicoordTextHitCount") or 0)
    source_text_hits = int(counts.get("sourceTextHitCount") or 0)
    if usable > 0:
        return ["usable-rrapicoord-live-marker-present"]
    if text_hits == 0:
        causes.append("rrapicoord-token-not-found-in-selected-scan-artifacts")
    if marker_like == 0 and text_hits > 0:
        causes.append("rrapicoord-source-or-error-text-only-no-pipe-marker-record")
    if marker_like > 0:
        causes.append("rrapicoord-marker-like-records-present-but-not-usable")
    if source_text_hits > 0:
        causes.append("scan-is-hitting-addon-source/static/error-context")
    if not tokens.get("source=rift-api"):
        causes.append("live-source-field-not-observed")
    if not tokens.get("view=Inspect.Unit.Detail(player)"):
        causes.append("live-view-field-not-observed")
    if not (tokens.get("x=") and tokens.get("y=") and tokens.get("z=")):
        causes.append("coordinate-fields-not-observed")
    if any(key.startswith("status:starting") for key in issues):
        causes.append("only-starting/default-marker-observed")
    if not causes:
        causes.append("no-usable-rrapicoord-marker-observed")
    return causes


def target_mismatch_blockers(scans: Sequence[Mapping[str, Any]], *, target_pid: int | None, process_name: str | None) -> list[str]:
    blockers: list[str] = []
    normalized_expected = (process_name or "").lower().removesuffix(".exe")
    for scan in scans:
        process = safe_dict(scan.get("process"))
        pid = process.get("pid")
        name = str(process.get("name") or "").lower().removesuffix(".exe")
        if target_pid is not None and pid is not None and int(pid) != target_pid:
            blockers.append(f"scan-target-pid-mismatch:{scan.get('path')}:{pid}!={target_pid}")
        if normalized_expected and name and name != normalized_expected:
            blockers.append(f"scan-target-process-mismatch:{scan.get('path')}:{name}!={normalized_expected}")
    return blockers


def markdown_summary(summary: Mapping[str, Any]) -> str:
    counts = safe_dict(summary.get("counts"))
    lines = [
        "# RRAPICOORD scan diagnostics",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Scan files: `{counts.get('scanFileCount')}`",
        f"- RRAPICOORD text hits: `{counts.get('rrapicoordTextHitCount')}`",
        f"- Marker-like records: `{counts.get('markerLikeCount')}`",
        f"- Usable markers: `{counts.get('usableMarkerCount')}`",
        "",
        "## Inferred cause",
        "",
    ]
    lines.extend(f"- `{cause}`" for cause in safe_list(summary.get("inferredCauses")))
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "| Field | Value |",
            "|---|---|",
        ]
    )
    for key, value in safe_dict(summary.get("safety")).items():
        lines.append(f"| `{key}` | `{str(value).lower()}` |")
    lines.extend(
        [
            "",
            "## Scan files",
            "",
            "| File | Hits | RRAPICOORD hits | Source/static hits | Marker-like | Usable |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for scan in safe_list(summary.get("scans")):
        scan_counts = safe_dict(safe_dict(scan).get("counts"))
        lines.append(
            "| "
            f"`{safe_dict(scan).get('path')}` | "
            f"`{scan_counts.get('loadedHitCount')}` | "
            f"`{scan_counts.get('rrapicoordTextHitCount')}` | "
            f"`{scan_counts.get('sourceTextHitCount')}` | "
            f"`{scan_counts.get('markerLikeCount')}` | "
            f"`{scan_counts.get('usableMarkerCount')}` |"
        )
    issues = safe_dict(summary.get("markerIssueCounts"))
    if issues:
        lines.extend(["", "## Marker issue counts", "", "| Issue | Count |", "|---|---:|"])
        for issue, count in issues.items():
            lines.append(f"| `{issue}` | `{count}` |")
    examples: list[dict[str, Any]] = []
    for scan in safe_list(summary.get("scans")):
        for example in safe_list(safe_dict(scan).get("examples")):
            if len(examples) >= 8:
                break
            examples.append(safe_dict(example))
    if examples:
        lines.extend(["", "## Examples", ""])
        for index, example in enumerate(examples, 1):
            lines.append(f"### Example {index}: `{example.get('address')}`")
            lines.append("")
            for snippet in safe_list(example.get("snippets")):
                lines.append(f"- `{safe_dict(snippet).get('source')}`: `{safe_dict(snippet).get('text')}`")
            lines.append("")
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{blocker}`" for blocker in safe_list(summary.get("blockers")))
    lines.extend(["", "## Next", "", f"- {safe_dict(summary.get('next')).get('recommendedAction')}"])
    return "\n".join(lines).rstrip() + "\n"


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    output_root = args.output_root or repo_root / "scripts" / "captures" / f"rrapicoord-scan-diagnostics-{utc_stamp()}"
    output_root = output_root.resolve()
    scan_paths = resolve_scan_paths(args, repo_root)
    scans: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in scan_paths:
        try:
            scans.append(summarize_scan(path, repo_root, max_examples=args.max_examples))
        except Exception as exc:  # keep diagnostics durable even when one artifact is malformed
            errors.append(f"scan-read-failed:{path}:{type(exc).__name__}:{exc}")
    counts = aggregate_counts(scans)
    counts["scanFileCount"] = len(scans)
    tokens = aggregate_token_presence(scans)
    issues = aggregate_issue_counts(scans)
    usable_count = int(counts.get("usableMarkerCount") or 0)
    blockers: list[str] = []
    warnings: list[str] = []
    blockers.extend(errors)
    blockers.extend(target_mismatch_blockers(scans, target_pid=args.target_pid, process_name=args.process_name))
    if not scans:
        blockers.append("rrapicoord-scan-artifact-not-found")
    if usable_count == 0:
        blockers.append("rrapicoord-no-usable-marker")
    inferred_causes = infer_causes(counts, tokens, issues)
    status = "passed" if not blockers else "blocked"
    verdict = "rrapicoord-usable-marker-present" if usable_count > 0 and not errors else "blocked-rrapicoord-no-usable-marker"
    summary_json = output_root / "summary.json"
    summary_md = output_root / "summary.md"
    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "rrapicoord-scan-diagnostics",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": verdict,
        "target": {
            "pid": args.target_pid,
            "processName": args.process_name,
        },
        "inputs": {
            "scanFiles": [str(path) for path in scan_paths],
            "latestCount": args.latest_count,
            "maxExamples": args.max_examples,
        },
        "counts": counts,
        "tokenPresence": tokens,
        "markerIssueCounts": issues,
        "inferredCauses": inferred_causes,
        "scans": scans,
        "blockers": blockers,
        "warnings": warnings,
        "errors": errors,
        "artifacts": {
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "x64dbgAttached": False,
            "cheatEngineUsed": False,
            "processMemoryReadByThisHelper": False,
            "targetMemoryWritten": False,
            "scanArtifactsOnly": True,
            "savedVariablesUsedAsLiveTruth": False,
            "candidateOnly": True,
            "promotionEligible": usable_count > 0 and not blockers,
        },
        "next": {
            "recommendedAction": (
                "Use the newest usable RRAPICOORD marker as the fresh reference input to read-only proof gates."
                if usable_count > 0 and not blockers
                else "Restore a true live reference surface first; current artifacts show no usable RRAPICOORD live marker, so do not spend more proof tokens on stale references."
            )
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(summary_json, summary)
    write_text_atomic(summary_md, markdown_summary(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diagnose existing RRAPICOORD scan artifacts without reading live process memory or sending input."
    )
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--scan-file", action="append", type=Path, default=[])
    parser.add_argument("--latest-count", type=int, default=DEFAULT_LATEST_COUNT)
    parser.add_argument("--target-pid", type=int)
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--max-examples", type=int, default=DEFAULT_MAX_EXAMPLES)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = build_summary(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "verdict": summary["verdict"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
                    "inferredCauses": summary["inferredCauses"],
                    "counts": summary["counts"],
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']}")
        print(f"verdict={summary['verdict']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        print(f"summaryMarkdown={summary['artifacts']['summaryMarkdown']}")
        if summary["inferredCauses"]:
            print("inferredCauses:")
            for cause in summary["inferredCauses"]:
                print(f"  - {cause}")
        if summary["blockers"]:
            print("blockers:")
            for blocker in summary["blockers"]:
                print(f"  - {blocker}")
    return 0 if summary["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
