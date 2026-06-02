from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .glyph_forensics_inventory import redact_text
    from .workflow_common import base_safety, repo_root, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution
    from glyph_forensics_inventory import redact_text  # type: ignore
    from workflow_common import base_safety, repo_root, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
KIND = "riftreader-glyph-static-focus"
URL_RE = re.compile(r"(?i)\bhttps?://[^\s\"'<>]+")
HOST_RE = re.compile(r"(?i)\b(?:[a-z0-9-]+\.)+(?:com|net|org|io|gg|tv|cloud|cdn|games|trionworlds)\b")


def latest_ghidra_summary(root: Path) -> Path | None:
    capture_root = root / "scripts" / "captures"
    candidates = sorted(
        capture_root.glob("glyph-ghidra-static-export-*/glyph-static-summary.json"),
        key=lambda path: path.stat().st_mtime,
    )
    return candidates[-1] if candidates else None


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"json-not-object:{path}")
    return data


def count_rows(counts: Mapping[str, Any], *, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, value in counts.items():
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        rows.append({"name": str(name), "count": count})
    return sorted(rows, key=lambda item: (-item["count"], item["name"]))[:limit]


def string_endpoints(value: str) -> list[str]:
    endpoints: list[str] = []
    for pattern in (URL_RE, HOST_RE):
        for match in pattern.finditer(value):
            endpoint = redact_text(match.group(0).strip().rstrip(".,;)'>]\""))
            if endpoint and endpoint not in endpoints:
                endpoints.append(endpoint)
    return endpoints


def interesting_strings_for_function(
    ghidra_summary: Mapping[str, Any],
    *,
    category: str,
    function_entry: str,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    strings = ghidra_summary.get("interestingStrings") if isinstance(ghidra_summary.get("interestingStrings"), list) else []
    rows: list[dict[str, Any]] = []
    match_count = 0
    for item in strings:
        if not isinstance(item, Mapping):
            continue
        categories = item.get("categories") if isinstance(item.get("categories"), list) else []
        if category not in categories:
            continue
        refs = item.get("references") if isinstance(item.get("references"), list) else []
        matching_refs = [ref for ref in refs if isinstance(ref, Mapping) and str(ref.get("functionEntry") or "").lower() == function_entry.lower()]
        if not matching_refs:
            continue
        match_count += len(matching_refs)
        if len(rows) >= limit:
            continue
        value = redact_text(str(item.get("value") or ""))[:500]
        rows.append(
            {
                "address": item.get("address"),
                "categories": categories,
                "value": value,
                "endpoints": string_endpoints(value),
                "referenceCountInFunction": len(matching_refs),
                "references": [
                    {
                        "from": ref.get("from"),
                        "type": ref.get("type"),
                    }
                    for ref in matching_refs[:8]
                ],
            }
        )
    return rows, match_count


def build_focus_report(
    ghidra_summary: Mapping[str, Any],
    *,
    ghidra_path: Path,
    category_limit: int,
    function_limit: int,
    strings_per_function: int,
) -> dict[str, Any]:
    string_summary = safe_mapping(ghidra_summary.get("interestingStringSummary"))
    function_summary = safe_mapping(ghidra_summary.get("functionSummary"))
    category_reference_counts = safe_mapping(string_summary.get("categoryReferenceCounts"))
    top_functions_by_category = safe_mapping(string_summary.get("topReferencedFunctionsByCategory"))
    categories = [row["name"] for row in count_rows(category_reference_counts, limit=category_limit)]
    category_rows: list[dict[str, Any]] = []
    unique_functions: dict[str, dict[str, Any]] = {}
    endpoint_values: dict[str, int] = {}
    for category in categories:
        function_rows: list[dict[str, Any]] = []
        raw_functions = top_functions_by_category.get(category)
        if not isinstance(raw_functions, list):
            continue
        for raw in raw_functions[:function_limit]:
            if not isinstance(raw, Mapping):
                continue
            function_entry = str(raw.get("functionEntry") or "")
            strings, observed_ref_count = interesting_strings_for_function(
                ghidra_summary,
                category=category,
                function_entry=function_entry,
                limit=strings_per_function,
            )
            for row in strings:
                for endpoint in row.get("endpoints", []):
                    endpoint_values[endpoint] = endpoint_values.get(endpoint, 0) + 1
            function_row = {
                "functionName": raw.get("functionName"),
                "functionEntry": function_entry,
                "reportedReferenceCount": raw.get("count"),
                "observedReferenceCount": observed_ref_count,
                "capturedStringCount": len(strings),
                "strings": strings,
            }
            function_rows.append(function_row)
            unique = unique_functions.setdefault(
                function_entry,
                {
                    "functionName": raw.get("functionName"),
                    "functionEntry": function_entry,
                    "categories": [],
                    "totalReportedReferenceCount": 0,
                },
            )
            if category not in unique["categories"]:
                unique["categories"].append(category)
            try:
                unique["totalReportedReferenceCount"] = int(unique["totalReportedReferenceCount"]) + int(raw.get("count") or 0)
            except (TypeError, ValueError):
                pass
        category_rows.append(
            {
                "category": category,
                "referenceCount": category_reference_counts.get(category),
                "functions": function_rows,
            }
        )
    safety = base_safety()
    safety.update(
        {
            "staticGhidraOnly": True,
            "debuggerAttach": False,
            "processMemoryDumped": False,
            "processMemoryRead": False,
            "tokensRedacted": True,
        }
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "sourceGhidraJson": str(ghidra_path),
        "programName": ghidra_summary.get("programName"),
        "languageId": ghidra_summary.get("languageId"),
        "compilerSpecId": ghidra_summary.get("compilerSpecId"),
        "functionCount": function_summary.get("functionCount"),
        "instructionCount": function_summary.get("instructionCount"),
        "capturedStringCount": string_summary.get("capturedStringCount"),
        "totalReferencesCaptured": string_summary.get("totalReferencesCaptured"),
        "categoryLimit": category_limit,
        "functionLimit": function_limit,
        "stringsPerFunction": strings_per_function,
        "topCategories": count_rows(category_reference_counts, limit=category_limit),
        "categories": category_rows,
        "uniqueFunctionCount": len(unique_functions),
        "uniqueFunctions": sorted(
            unique_functions.values(),
            key=lambda item: (-int(item.get("totalReportedReferenceCount") or 0), str(item.get("functionEntry") or "")),
        )[: category_limit * function_limit],
        "endpointMentions": sorted(
            [{"value": key, "count": value} for key, value in endpoint_values.items()],
            key=lambda item: (-int(item["count"]), str(item["value"]).lower()),
        )[:80],
        "warnings": [],
        "errors": [],
        "safety": safety,
    }


def build_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Glyph static focus report",
        "",
        f"Generated: `{report.get('generatedAtUtc')}`",
        f"Source: `{report.get('sourceGhidraJson')}`",
        f"Program: `{report.get('programName')}`",
        "",
        "## Summary",
        "",
        f"- function count: `{report.get('functionCount')}`",
        f"- instruction count: `{report.get('instructionCount')}`",
        f"- captured string count: `{report.get('capturedStringCount')}`",
        f"- total references captured: `{report.get('totalReferencesCaptured')}`",
        f"- unique focus functions: `{report.get('uniqueFunctionCount')}`",
        "",
        "## Top categories",
        "",
    ]
    for row in report.get("topCategories", []):
        if isinstance(row, Mapping):
            lines.append(f"- `{row.get('name')}` references=`{row.get('count')}`")
    lines.extend(["", "## Focus functions", ""])
    for category in report.get("categories", []):
        if not isinstance(category, Mapping):
            continue
        lines.append(f"### {category.get('category')} (`{category.get('referenceCount')}` refs)")
        for function in category.get("functions", []):
            if not isinstance(function, Mapping):
                continue
            lines.append(
                f"- `{function.get('functionName')}` @ `{function.get('functionEntry')}` "
                f"reportedRefs=`{function.get('reportedReferenceCount')}` capturedStrings=`{function.get('capturedStringCount')}`"
            )
            for item in function.get("strings", [])[:3]:
                if isinstance(item, Mapping):
                    value = str(item.get("value") or "").replace("\n", "\\n")
                    lines.append(f"  - `{item.get('address')}` {value[:180]}")
        lines.append("")
    endpoints = report.get("endpointMentions") if isinstance(report.get("endpointMentions"), list) else []
    if endpoints:
        lines.extend(["## Endpoint mentions in focus strings", ""])
        for item in endpoints[:30]:
            if isinstance(item, Mapping):
                lines.append(f"- `{item.get('value')}` count=`{item.get('count')}`")
    lines.extend(["", "## Safety", ""])
    safety = safe_mapping(report.get("safety"))
    for key in ("staticGhidraOnly", "debuggerAttach", "processMemoryDumped", "processMemoryRead", "tokensRedacted"):
        lines.append(f"- {key}: `{safety.get(key)}`")
    return "\n".join(lines) + "\n"


def compact(report: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(report.get("artifacts"))
    return {
        "status": report.get("status"),
        "kind": report.get("kind"),
        "programName": report.get("programName"),
        "uniqueFocusFunctionCount": report.get("uniqueFunctionCount"),
        "topCategories": report.get("topCategories", []),
        "endpointMentionCount": len(report.get("endpointMentions", [])) if isinstance(report.get("endpointMentions"), list) else 0,
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "safety": {
            key: safe_mapping(report.get("safety")).get(key)
            for key in ("staticGhidraOnly", "debuggerAttach", "processMemoryDumped", "processMemoryRead", "tokensRedacted")
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build an offline Glyph static focus report from a Ghidra JSON export")
    parser.add_argument("--repo-root")
    parser.add_argument("--ghidra-json", type=Path)
    parser.add_argument("--category-limit", type=int, default=8)
    parser.add_argument("--function-limit", type=int, default=5)
    parser.add_argument("--strings-per-function", type=int, default=8)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    ghidra_path = args.ghidra_json.resolve() if args.ghidra_json else latest_ghidra_summary(root)
    if ghidra_path is None:
        print(json.dumps({"status": "failed", "error": "glyph-ghidra-summary-not-found", "safety": base_safety()}, indent=2))
        return 1
    ghidra_summary = load_json_object(ghidra_path)
    report = build_focus_report(
        ghidra_summary,
        ghidra_path=ghidra_path,
        category_limit=int(args.category_limit),
        function_limit=int(args.function_limit),
        strings_per_function=int(args.strings_per_function),
    )
    if args.write:
        run_dir = root / "scripts" / "captures" / f"glyph-static-focus-{utc_stamp()}"
        report["artifacts"] = {
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        }
        write_json(run_dir / "summary.json", report)
        (run_dir / "summary.md").write_text(build_markdown(report), encoding="utf-8")
    print(json.dumps(compact(report), indent=2 if not args.json else None))
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
