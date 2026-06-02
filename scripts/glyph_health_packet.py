from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .workflow_common import base_safety, repo_root, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution
    from workflow_common import base_safety, repo_root, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
KIND = "riftreader-glyph-health-packet"


def latest_inventory_summary(root: Path) -> Path | None:
    capture_root = root / "scripts" / "captures"
    candidates = sorted(capture_root.glob("glyph-forensics-inventory-*/summary.json"), key=lambda path: path.stat().st_mtime)
    return candidates[-1] if candidates else None


def latest_ghidra_summary(root: Path) -> Path | None:
    capture_root = root / "scripts" / "captures"
    candidates = sorted(
        capture_root.glob("glyph-ghidra-static-export-*/glyph-static-summary.json"),
        key=lambda path: path.stat().st_mtime,
    )
    return candidates[-1] if candidates else None


def load_summary(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"summary-not-object:{path}")
    return data


def manifest_versions(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    manifests = summary.get("manifestInventory") if isinstance(summary.get("manifestInventory"), list) else []
    rows: list[dict[str, Any]] = []
    for item in manifests:
        if not isinstance(item, Mapping) or item.get("status") != "passed":
            continue
        rows.append(
            {
                "path": item.get("path"),
                "version": item.get("version"),
                "entryCount": item.get("entryCount"),
                "totalSizeBytesFromParsedEntries": item.get("totalSizeBytesFromParsedEntries"),
            }
        )
    return rows


def process_rows(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for proc in summary.get("processes", []):
        if not isinstance(proc, Mapping) or not str(proc.get("Name", "")).lower().startswith("glyph"):
            continue
        rows.append(
            {
                "pid": proc.get("ProcessId"),
                "parentPid": proc.get("ParentProcessId"),
                "name": proc.get("Name"),
                "path": proc.get("ExecutablePath"),
                "creationDate": proc.get("CreationDate"),
            }
        )
    return rows


def top_endpoints(summary: Mapping[str, Any], *, limit: int) -> list[dict[str, Any]]:
    endpoints = summary.get("endpointInventory") if isinstance(summary.get("endpointInventory"), list) else []
    rows: list[dict[str, Any]] = []
    for item in endpoints[:limit]:
        if isinstance(item, Mapping):
            rows.append({"value": item.get("value"), "count": item.get("count"), "sources": item.get("sources", [])[:5]})
    return rows


def top_count_rows(counts: Mapping[str, Any], *, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, value in counts.items():
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        rows.append({"name": key, "count": count})
    return sorted(rows, key=lambda item: item["count"], reverse=True)[:limit]


def static_focus_packet(ghidra_summary: Mapping[str, Any], *, ghidra_path: Path, category_limit: int = 8, function_limit: int = 5) -> dict[str, Any]:
    function_summary = safe_mapping(ghidra_summary.get("functionSummary"))
    string_summary = safe_mapping(ghidra_summary.get("interestingStringSummary"))
    category_reference_counts = safe_mapping(string_summary.get("categoryReferenceCounts"))
    category_counts = safe_mapping(string_summary.get("categoryCounts"))
    top_functions_by_category = safe_mapping(string_summary.get("topReferencedFunctionsByCategory"))
    categories = [row["name"] for row in top_count_rows(category_reference_counts, limit=category_limit)]
    functions: dict[str, list[dict[str, Any]]] = {}
    for category in categories:
        rows = top_functions_by_category.get(category)
        if not isinstance(rows, list):
            continue
        functions[category] = [
            {
                "functionName": item.get("functionName"),
                "functionEntry": item.get("functionEntry"),
                "count": item.get("count"),
            }
            for item in rows[:function_limit]
            if isinstance(item, Mapping)
        ]
    return {
        "sourceGhidraJson": str(ghidra_path),
        "programName": ghidra_summary.get("programName"),
        "languageId": ghidra_summary.get("languageId"),
        "compilerSpecId": ghidra_summary.get("compilerSpecId"),
        "functionCount": function_summary.get("functionCount"),
        "instructionCount": function_summary.get("instructionCount"),
        "capturedStringCount": string_summary.get("capturedStringCount"),
        "scannedStringDataCount": string_summary.get("scannedStringDataCount"),
        "totalReferencesCaptured": string_summary.get("totalReferencesCaptured"),
        "topCategoryCounts": top_count_rows(category_counts, limit=category_limit),
        "topCategoryReferenceCounts": top_count_rows(category_reference_counts, limit=category_limit),
        "topReferencedFunctionsByCategory": functions,
    }


def build_health_packet(
    summary: Mapping[str, Any],
    *,
    summary_path: Path,
    endpoint_limit: int,
    ghidra_summary: Mapping[str, Any] | None = None,
    ghidra_path: Path | None = None,
) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    selection = safe_mapping(summary.get("selectionServerSummary"))
    executable_trust = safe_mapping(summary.get("executableTrustSummary"))
    dependency_trust = safe_mapping(summary.get("dependencyTrustSummary"))
    config = safe_mapping(summary.get("configInventory"))
    module_summary = safe_mapping(summary.get("moduleOriginSummary"))
    loaded_module_trust = safe_mapping(summary.get("loadedModuleTrustSummary"))
    module_inventory_rows = summary.get("moduleInventory") if isinstance(summary.get("moduleInventory"), list) else []
    timeline = safe_mapping(summary.get("logTimeline"))
    safety = base_safety()
    safety.update(
        {
            "readOnlyForensics": True,
            "debuggerAttach": False,
            "processMemoryDumped": False,
            "processMemoryRead": False,
            "processModuleEnumeration": bool(module_summary) or bool(module_inventory_rows),
            "staticGhidraOnly": ghidra_summary is not None,
            "tokensRedacted": True,
        }
    )
    packet = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "sourceSummaryJson": str(summary_path),
        "sourceGeneratedAtUtc": summary.get("generatedAtUtc"),
        "sourceSummaryMarkdown": artifacts.get("summaryMarkdown"),
        "processes": process_rows(summary),
        "debugger": {
            "debuggerLikeProcessCount": len(summary.get("debuggerProcessScan", [])),
            "indicators": summary.get("debuggerIndicators", []),
        },
        "network": {
            "activeConnectionCount": len(summary.get("activeNetworkConnections", [])),
            "selectionServerStatus": selection.get("status"),
            "selectionServerFailureCount": selection.get("failureCount"),
            "selectionServerEndpoints": selection.get("endpoints", []),
            "topEndpoints": top_endpoints(summary, limit=endpoint_limit),
        },
        "manifests": manifest_versions(summary),
        "install": {
            "autorunCount": len(summary.get("autorunInventory", [])),
            "uninstallEntryCount": len(summary.get("uninstallInventory", [])),
            "serviceCount": len(summary.get("serviceInventory", [])),
            "scheduledTaskCount": len(summary.get("scheduledTaskInventory", [])),
        },
        "trust": {
            "executableSignatureStatusCounts": executable_trust.get("statusCounts", {}),
            "dependencySignatureStatusCounts": dependency_trust.get("statusCounts", {}),
            "dependencyNonValidSignatureCount": dependency_trust.get("nonValidCount"),
        },
        "config": {
            "fileCount": config.get("fileCount"),
            "parserCounts": config.get("parserCounts", {}),
            "statusCounts": config.get("statusCounts", {}),
            "endpointReferenceCount": config.get("endpointReferenceCount"),
            "files": [
                {
                    "path": item.get("path"),
                    "parser": item.get("parser"),
                    "status": item.get("status"),
                    "rootTag": item.get("rootTag"),
                    "keyCount": item.get("keyCount"),
                    "elementCountCaptured": item.get("elementCountCaptured"),
                    "endpointCount": len(item.get("endpoints", [])) if isinstance(item.get("endpoints"), list) else 0,
                }
                for item in (config.get("files") if isinstance(config.get("files"), list) else [])[:20]
                if isinstance(item, Mapping)
            ],
        },
        "modules": {
            "processCount": module_summary.get("processCount"),
            "totalModuleCount": module_summary.get("totalModuleCount"),
            "originCounts": module_summary.get("categoryCounts", {}),
            "nonWindowsNonGlyphCount": module_summary.get("nonWindowsNonGlyphCount"),
            "nonWindowsNonGlyphModules": module_summary.get("nonWindowsNonGlyphModules", [])[:25],
            "signatureCheckedCount": loaded_module_trust.get("signatureCheckedCount"),
            "signatureStatusCounts": loaded_module_trust.get("statusCounts", {}),
            "categorySignatureStatusCounts": loaded_module_trust.get("categoryStatusCounts", {}),
            "nonValidSignatureCount": loaded_module_trust.get("nonValidCount"),
            "glyphInstallNonValidSignatureCount": loaded_module_trust.get("glyphInstallNonValidCount"),
            "nonWindowsNonGlyphNonValidSignatureCount": loaded_module_trust.get("nonWindowsNonGlyphNonValidCount"),
            "nonWindowsNonGlyphNonValidModules": loaded_module_trust.get("nonWindowsNonGlyphNonValidModules", [])[:25],
        },
        "counts": {
            "targetedFileCount": len([item for item in summary.get("targetedFileInventory", []) if isinstance(item, Mapping) and item.get("exists")]),
            "dependencyCount": len(summary.get("dependencyMetadata", [])),
            "manifestCount": len([item for item in summary.get("manifestInventory", []) if isinstance(item, Mapping) and item.get("status") == "passed"]),
            "endpointCount": len(summary.get("endpointInventory", [])),
            "logTimelineEvents": timeline.get("eventCount"),
        },
        "safety": safety,
    }
    if ghidra_summary is not None and ghidra_path is not None:
        packet["staticReverseEngineering"] = static_focus_packet(ghidra_summary, ghidra_path=ghidra_path)
    return packet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit a compact Glyph health packet from the latest Glyph forensics inventory")
    parser.add_argument("--repo-root")
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--ghidra-json", type=Path)
    parser.add_argument("--no-ghidra", action="store_true")
    parser.add_argument("--endpoint-limit", type=int, default=12)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    summary_path = args.summary_json.resolve() if args.summary_json else latest_inventory_summary(root)
    if summary_path is None:
        print(json.dumps({"status": "failed", "error": "glyph-forensics-summary-not-found", "safety": base_safety()}, indent=2))
        return 1
    summary = load_summary(summary_path)
    ghidra_path = None
    ghidra_summary = None
    if not args.no_ghidra:
        ghidra_path = args.ghidra_json.resolve() if args.ghidra_json else latest_ghidra_summary(root)
        if ghidra_path is not None:
            ghidra_summary = load_summary(ghidra_path)
    packet = build_health_packet(
        summary,
        summary_path=summary_path,
        endpoint_limit=int(args.endpoint_limit),
        ghidra_summary=ghidra_summary,
        ghidra_path=ghidra_path,
    )
    if args.write:
        run_dir = root / "scripts" / "captures" / f"glyph-health-packet-{utc_stamp()}"
        packet["artifacts"] = {"summaryJson": str(run_dir / "summary.json")}
        write_json(run_dir / "summary.json", packet)
    print(json.dumps(packet, indent=2 if not args.json else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
