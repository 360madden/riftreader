from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .reference_freshness_watchdog import path_text, safe_dict, safe_list
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
ADDON_NAME = "RiftReaderApiProbe"
DEFAULT_PROCESS_NAME = "rift_x64"
EXPECTED_IDENTIFIER = "RiftReaderApiProbe"


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


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def file_record(path: Path, repo_root: Path) -> dict[str, Any]:
    exists = path.exists() and path.is_file()
    stat = path.stat() if exists else None
    return {
        "path": path_text(path, repo_root),
        "exists": exists,
        "length": stat.st_size if stat else None,
        "lastWriteTimeUtc": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        if stat
        else None,
        "sha256": sha256_file(path) if exists else None,
    }


def split_env_paths(value: str | None) -> list[Path]:
    if not value:
        return []
    return [Path(part.strip().strip('"')) for part in re.split(r"[;|]", value) if part.strip()]


def default_addon_roots() -> list[Path]:
    roots: list[Path] = []
    roots.extend(split_env_paths(os.environ.get("RIFT_ADDONS_DIR")))
    user_profile = os.environ.get("USERPROFILE")
    one_drive = os.environ.get("OneDrive")
    if user_profile:
        roots.append(Path(user_profile) / "OneDrive" / "Documents" / "RIFT" / "Interface" / "AddOns")
        roots.append(Path(user_profile) / "Documents" / "RIFT" / "Interface" / "AddOns")
    if one_drive:
        roots.append(Path(one_drive) / "Documents" / "RIFT" / "Interface" / "AddOns")
    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        key = str(root).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def source_contract(main_text: str, toc_text: str) -> dict[str, Any]:
    checks = {
        "definesLiveGlobal": "RiftReaderApiProbe_Live" in main_text,
        "defaultStartingMarker": "RRAPICOORD1|status=starting|savedVariablesUse=none" in main_text,
        "formatsRrapicoordMarker": '"RRAPICOORD1"' in main_text and "schema=1" in main_text,
        "usesRiftApiSource": "source=rift-api" in main_text,
        "usesInspectUnitDetailPlayer": "Inspect.Unit.Detail(player)" in main_text,
        "emitsSavedVariablesUseNone": "savedVariablesUse=none" in main_text,
        "registersRapSlashCommand": 'Command.Slash.Register("rap")' in main_text,
        "registersStartupRefresh": "Event.Addon.Startup.End" in main_text and "refreshLiveApiCoord(true)" in main_text,
        "registersUpdateRefresh": "Event.System.Update.Begin" in main_text and "refreshLiveApiCoord(false)" in main_text,
        "tocIdentifierMatches": f'Identifier = "{EXPECTED_IDENTIFIER}"' in toc_text,
        "tocRunOnStartupMainLua": "RunOnStartup" in toc_text and '"main.lua"' in toc_text,
        "tocNoSavedVariablesDeclaration": re.search(r"(?im)^\s*SavedVariables\s*=", toc_text) is None,
    }
    missing = [name for name, ok in checks.items() if not ok]
    return {
        "checks": checks,
        "passed": not missing,
        "missing": missing,
    }


def repo_addon_summary(repo_root: Path) -> dict[str, Any]:
    addon_dir = repo_root / "addon" / ADDON_NAME
    main_path = addon_dir / "main.lua"
    toc_path = addon_dir / "RiftAddon.toc"
    readme_path = addon_dir / "README.md"
    main_text = main_path.read_text(encoding="utf-8") if main_path.exists() else ""
    toc_text = toc_path.read_text(encoding="utf-8") if toc_path.exists() else ""
    return {
        "name": ADDON_NAME,
        "path": path_text(addon_dir, repo_root),
        "exists": addon_dir.exists() and addon_dir.is_dir(),
        "files": {
            "main.lua": file_record(main_path, repo_root),
            "RiftAddon.toc": file_record(toc_path, repo_root),
            "README.md": file_record(readme_path, repo_root),
        },
        "sourceContract": source_contract(main_text, toc_text),
    }


def compare_file_records(repo_file: Mapping[str, Any], installed_file: Mapping[str, Any]) -> dict[str, Any]:
    repo_hash = repo_file.get("sha256")
    installed_hash = installed_file.get("sha256")
    return {
        "repoExists": repo_file.get("exists") is True,
        "installedExists": installed_file.get("exists") is True,
        "hashMatch": bool(repo_hash and installed_hash and repo_hash == installed_hash),
        "repoSha256": repo_hash,
        "installedSha256": installed_hash,
    }


def installed_addon_summary(root: Path, repo_root: Path, repo_addon: Mapping[str, Any]) -> dict[str, Any]:
    addon_dir = root / ADDON_NAME
    installed_files = {
        "main.lua": file_record(addon_dir / "main.lua", repo_root),
        "RiftAddon.toc": file_record(addon_dir / "RiftAddon.toc", repo_root),
        "README.md": file_record(addon_dir / "README.md", repo_root),
    }
    repo_files = safe_dict(repo_addon.get("files"))
    comparisons = {
        name: compare_file_records(safe_dict(repo_files.get(name)), record) for name, record in installed_files.items()
    }
    installed_exists = addon_dir.exists() and addon_dir.is_dir()
    all_required_match = all(
        safe_dict(comparisons.get(name)).get("hashMatch") is True for name in ("main.lua", "RiftAddon.toc")
    )
    return {
        "root": path_text(root, repo_root),
        "rootExists": root.exists() and root.is_dir(),
        "addonPath": path_text(addon_dir, repo_root),
        "installed": installed_exists,
        "files": installed_files,
        "comparisons": comparisons,
        "requiredFilesMatchRepo": installed_exists and all_required_match,
    }


def latest_file(paths: Sequence[Path]) -> Path | None:
    existing = [path for path in paths if path.exists() and path.is_file()]
    if not existing:
        return None
    return max(existing, key=lambda path: (path.stat().st_mtime, str(path)))


def latest_rrapicoord_diagnostic(repo_root: Path) -> Path | None:
    return latest_file(list((repo_root / "scripts" / "captures").glob("rrapicoord-scan-diagnostics-*/summary.json")))


def summarize_latest_scan_diagnostic(path: Path | None, repo_root: Path) -> dict[str, Any]:
    if path is None:
        return {
            "path": None,
            "exists": False,
            "status": "missing",
            "verdict": "missing",
            "usableMarkerCount": None,
            "inferredCauses": [],
            "blockers": ["rrapicoord-scan-diagnostic-not-found"],
        }
    try:
        document = load_json_object(path)
    except Exception as exc:
        return {
            "path": path_text(path, repo_root),
            "exists": True,
            "status": "read-failed",
            "verdict": "read-failed",
            "usableMarkerCount": None,
            "inferredCauses": [],
            "blockers": [f"rrapicoord-scan-diagnostic-read-failed:{type(exc).__name__}:{exc}"],
        }
    counts = safe_dict(document.get("counts"))
    return {
        "path": path_text(path, repo_root),
        "exists": True,
        "status": document.get("status"),
        "verdict": document.get("verdict"),
        "generatedAtUtc": document.get("generatedAtUtc"),
        "counts": {
            "scanFileCount": counts.get("scanFileCount"),
            "loadedHitCount": counts.get("loadedHitCount"),
            "rrapicoordTextHitCount": counts.get("rrapicoordTextHitCount"),
            "markerLikeCount": counts.get("markerLikeCount"),
            "usableMarkerCount": counts.get("usableMarkerCount"),
            "sourceTextHitCount": counts.get("sourceTextHitCount"),
        },
        "usableMarkerCount": counts.get("usableMarkerCount"),
        "inferredCauses": safe_list(document.get("inferredCauses")),
        "blockers": safe_list(document.get("blockers")),
    }


def derive_verdict(
    repo_addon: Mapping[str, Any],
    installed: Sequence[Mapping[str, Any]],
    scan: Mapping[str, Any],
) -> tuple[str, str, list[str], list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    inferred: list[str] = []
    if repo_addon.get("exists") is not True:
        blockers.append("repo-addon-missing")
    contract = safe_dict(repo_addon.get("sourceContract"))
    if contract.get("passed") is not True:
        blockers.extend(f"repo-addon-contract-missing:{name}" for name in safe_list(contract.get("missing")))
    matching_installs = [item for item in installed if safe_dict(item).get("requiredFilesMatchRepo") is True]
    if not matching_installs:
        blockers.append("installed-addon-not-found-or-does-not-match-repo")
    usable_marker_count = scan.get("usableMarkerCount")
    if usable_marker_count == 0:
        blockers.append("current-scan-has-no-usable-rrapicoord-live-marker")
        inferred.append("installed-source-is-present-but-runtime-live-marker-is-not-observed")
    elif usable_marker_count is None:
        warnings.append("latest-rrapicoord-scan-diagnostic-missing")
    if matching_installs and usable_marker_count == 0:
        inferred.append("next-step-requires-live-addon-runtime-refresh-or-manual-status-check")
    if matching_installs and any("scan-is-hitting-addon-source/static/error-context" == cause for cause in safe_list(scan.get("inferredCauses"))):
        inferred.append("scan-sees-addon-source-or-error-text-but-not-live-global-payload")
    if blockers:
        return "blocked", "blocked-live-reference-runtime-marker-not-observed", blockers, warnings, inferred
    if warnings:
        return "passed-with-warnings", "addon-installed-matches-repo-scan-diagnostic-missing", blockers, warnings, inferred
    return "passed", "addon-installed-and-live-marker-observed", blockers, warnings, inferred


def markdown_summary(summary: Mapping[str, Any]) -> str:
    repo_addon = safe_dict(summary.get("repoAddon"))
    scan = safe_dict(summary.get("latestRrapicoordScanDiagnostic"))
    lines = [
        "# RRAPICOORD addon state diagnostics",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Addon: `{ADDON_NAME}`",
        "",
        "## Safety",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    for key, value in safe_dict(summary.get("safety")).items():
        lines.append(f"| `{key}` | `{str(value).lower()}` |")
    lines.extend(
        [
            "",
            "## Repo addon",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| Exists | `{str(repo_addon.get('exists')).lower()}` |",
            f"| Contract passed | `{str(safe_dict(repo_addon.get('sourceContract')).get('passed')).lower()}` |",
        ]
    )
    missing = safe_list(safe_dict(repo_addon.get("sourceContract")).get("missing"))
    if missing:
        lines.append(f"| Missing contract checks | `{', '.join(str(item) for item in missing)}` |")
    lines.extend(
        [
            "",
            "## Installed copies",
            "",
            "| Root | Installed | Required files match repo |",
            "|---|---:|---:|",
        ]
    )
    for item in safe_list(summary.get("installedCopies")):
        row = safe_dict(item)
        lines.append(
            f"| `{row.get('root')}` | `{str(row.get('installed')).lower()}` | "
            f"`{str(row.get('requiredFilesMatchRepo')).lower()}` |"
        )
    lines.extend(
        [
            "",
            "## Latest RRAPICOORD scan diagnostic",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| Artifact | `{scan.get('path')}` |",
            f"| Status | `{scan.get('status')}` |",
            f"| Verdict | `{scan.get('verdict')}` |",
            f"| Usable markers | `{scan.get('usableMarkerCount')}` |",
        ]
    )
    counts = safe_dict(scan.get("counts"))
    if counts:
        lines.append(
            "| Counts | "
            f"`textHits={counts.get('rrapicoordTextHitCount')}; "
            f"markerLike={counts.get('markerLikeCount')}; "
            f"sourceText={counts.get('sourceTextHitCount')}` |"
        )
    if summary.get("inferredCauses"):
        lines.extend(["", "## Inferred causes", ""])
        lines.extend(f"- `{cause}`" for cause in safe_list(summary.get("inferredCauses")))
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{blocker}`" for blocker in safe_list(summary.get("blockers")))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in safe_list(summary.get("warnings")))
    lines.extend(["", "## Next", "", f"- {safe_dict(summary.get('next')).get('recommendedAction')}"])
    return "\n".join(lines).rstrip() + "\n"


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    output_root = args.output_root or repo_root / "scripts" / "captures" / f"rrapicoord-addon-state-diagnostics-{utc_stamp()}"
    output_root = output_root.resolve()
    addon_roots = [path.resolve() for path in (args.addons_root or default_addon_roots())]
    repo_addon = repo_addon_summary(repo_root)
    installed = [installed_addon_summary(root, repo_root, repo_addon) for root in addon_roots]
    scan_path = args.rrapicoord_scan_diagnostic or latest_rrapicoord_diagnostic(repo_root)
    scan = summarize_latest_scan_diagnostic(scan_path, repo_root)
    status, verdict, blockers, warnings, inferred = derive_verdict(repo_addon, installed, scan)
    inferred.extend(cause for cause in safe_list(scan.get("inferredCauses")) if cause not in inferred)
    summary_json = output_root / "summary.json"
    summary_md = output_root / "summary.md"
    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "rrapicoord-addon-state-diagnostics",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": verdict,
        "target": {
            "pid": args.target_pid,
            "processName": args.process_name,
        },
        "inputs": {
            "addonsRoots": [str(path) for path in addon_roots],
            "rrapicoordScanDiagnostic": str(scan_path) if scan_path else None,
        },
        "repoAddon": repo_addon,
        "installedCopies": installed,
        "latestRrapicoordScanDiagnostic": scan,
        "blockers": blockers,
        "warnings": warnings,
        "inferredCauses": inferred,
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
            "addonFilesWritten": False,
            "addonFilesReadOnly": True,
            "scanArtifactsOnly": True,
            "savedVariablesUsedAsLiveTruth": False,
            "candidateOnly": True,
            "promotionEligible": False,
        },
        "next": {
            "recommendedAction": (
                "Ask the operator to approve a bounded live addon runtime refresh/status check, then rerun coordinate_proof_preflight."
                if status == "blocked"
                else "Rerun coordinate_proof_preflight and proceed only if it reports a fresh reference."
            )
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(summary_json, summary)
    write_text_atomic(summary_md, markdown_summary(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only RRAPICOORD addon install/state diagnostic; does not deploy, reload UI, read live memory, or send input."
    )
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--addons-root", action="append", type=Path)
    parser.add_argument("--rrapicoord-scan-diagnostic", type=Path)
    parser.add_argument("--target-pid", type=int)
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
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
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']}")
        print(f"verdict={summary['verdict']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        if summary["blockers"]:
            print("blockers:")
            for blocker in summary["blockers"]:
                print(f"  - {blocker}")
    return 0 if summary["status"] in ("passed", "passed-with-warnings") else 2


if __name__ == "__main__":
    raise SystemExit(main())
