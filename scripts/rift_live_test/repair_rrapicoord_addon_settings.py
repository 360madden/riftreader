from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .reports import write_json, write_text_atomic
from .rrapicoord_addon_state_diagnostics import (
    ADDON_NAME,
    addon_settings_paths,
    default_addon_roots,
    parse_addon_settings,
)
from .reference_freshness_watchdog import path_text, safe_dict, safe_list


SCHEMA_VERSION = 1
DEFAULT_SCOPE = "latest"


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def backup_path_for(path: Path, backup_root: Path) -> Path:
    identity = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:12]
    return backup_root / f"{identity}-{path.name}"


def select_settings_paths(paths: Sequence[Path], *, scope: str, account_contains: str | None) -> list[Path]:
    filtered = list(paths)
    if account_contains:
        needle = account_contains.lower()
        filtered = [path for path in filtered if needle in str(path.parent.name).lower()]
    filtered = sorted(
        [path for path in filtered if path.exists() and path.is_file()],
        key=lambda path: (path.stat().st_mtime, str(path)),
        reverse=True,
    )
    if scope == "latest":
        return filtered[:1]
    if scope == "all":
        return filtered
    raise ValueError(f"Unsupported scope: {scope}")


def replace_or_insert_addon_setting(text: str, addon_name: str = ADDON_NAME) -> tuple[str, str]:
    lines = text.splitlines(keepends=True)
    in_addons = False
    addon_start = -1
    addon_end = -1
    existing_index = -1
    setting_pattern = re.compile(rf"^(\s*){re.escape(addon_name)}\s*=\s*\"([^\"]*)\"(,?.*)$")
    for index, line in enumerate(lines):
        if re.match(r"^\s*Addons\s*=\s*{", line):
            in_addons = True
            addon_start = index
            continue
        if in_addons:
            match = setting_pattern.match(line.rstrip("\r\n"))
            if match:
                existing_index = index
            if re.match(r"^\s*}", line):
                addon_end = index
                break
    if addon_start < 0 or addon_end < 0:
        raise ValueError("AddonSettings.lua does not contain a parseable Addons table")
    desired_line = f'  {addon_name} = "enabled",\n'
    if existing_index >= 0:
        current_line = lines[existing_index]
        newline = "\r\n" if current_line.endswith("\r\n") else "\n"
        lines[existing_index] = desired_line.rstrip("\n") + newline
        old_match = setting_pattern.match(current_line.rstrip("\r\n"))
        previous = old_match.group(2).lower() if old_match else "unknown"
        return "".join(lines), f"updated:{previous}->enabled"
    newline = "\r\n" if lines[addon_end].endswith("\r\n") else "\n"
    lines.insert(addon_end, desired_line.rstrip("\n") + newline)
    return "".join(lines), "inserted:missing->enabled"


def repair_file(path: Path, *, repo_root: Path, backup_root: Path, apply: bool) -> dict[str, Any]:
    original = path.read_text(encoding="utf-8-sig")
    settings_before = parse_addon_settings(original)
    status_before = settings_before.get(ADDON_NAME) or "missing"
    repaired, action = replace_or_insert_addon_setting(original)
    changed = repaired != original
    backup_path = backup_path_for(path, backup_root)
    record = {
        "path": path_text(path, repo_root),
        "exists": path.exists(),
        "statusBefore": status_before,
        "action": action,
        "changed": changed,
        "applied": False,
        "backupPath": path_text(backup_path, repo_root),
        "sha256Before": file_sha256(path),
        "sha256After": None,
    }
    if apply and changed:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)
        path.write_text(repaired, encoding="utf-8")
        record["applied"] = True
        record["sha256After"] = file_sha256(path)
        settings_after = parse_addon_settings(path.read_text(encoding="utf-8-sig"))
    else:
        settings_after = parse_addon_settings(repaired)
        record["sha256After"] = hashlib.sha256(repaired.encode("utf-8")).hexdigest().upper()
    record["statusAfter"] = settings_after.get(ADDON_NAME) or "missing"
    record["enabledAfter"] = record["statusAfter"] == "enabled"
    return record


def markdown_summary(summary: Mapping[str, Any]) -> str:
    lines = [
        "# RRAPICOORD AddonSettings repair",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Apply: `{str(safe_dict(summary.get('inputs')).get('apply')).lower()}`",
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
            "## Repairs",
            "",
            "| File | Before | After | Action | Applied | Backup |",
            "|---|---|---|---|---:|---|",
        ]
    )
    for item in safe_list(summary.get("repairs")):
        row = safe_dict(item)
        lines.append(
            f"| `{row.get('path')}` | `{row.get('statusBefore')}` | `{row.get('statusAfter')}` | "
            f"`{row.get('action')}` | `{str(row.get('applied')).lower()}` | `{row.get('backupPath')}` |"
        )
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
    output_root = args.output_root or repo_root / "scripts" / "captures" / f"rrapicoord-addon-settings-repair-{utc_stamp()}"
    output_root = output_root.resolve()
    backup_root = args.backup_root or repo_root / ".riftreader-local" / "backups" / "rrapicoord-addon-settings" / output_root.name
    backup_root = backup_root.resolve()
    addon_roots = [path.resolve() for path in (args.addons_root or default_addon_roots())]
    discovered = addon_settings_paths(addon_roots)
    selected = select_settings_paths(discovered, scope=args.scope, account_contains=args.account_contains)
    blockers: list[str] = []
    warnings: list[str] = []
    repairs: list[dict[str, Any]] = []
    if not selected:
        blockers.append("addon-settings-file-not-found")
    for path in selected:
        try:
            repairs.append(repair_file(path, repo_root=repo_root, backup_root=backup_root, apply=args.apply))
        except Exception as exc:
            blockers.append(f"repair-failed:{path}:{type(exc).__name__}:{exc}")
    enabled_count = sum(1 for repair in repairs if repair.get("enabledAfter") is True)
    changed_count = sum(1 for repair in repairs if repair.get("changed") is True)
    applied_count = sum(1 for repair in repairs if repair.get("applied") is True)
    if args.apply and repairs and enabled_count != len(repairs):
        blockers.append(f"not-all-selected-settings-enabled:{enabled_count}!={len(repairs)}")
    if not args.apply and changed_count:
        warnings.append("dry-run-only-no-files-written")
    status = "blocked" if blockers else "passed"
    verdict = "addon-settings-repaired" if args.apply and not blockers else "addon-settings-repair-dry-run" if not blockers else "blocked-addon-settings-repair"
    summary_json = output_root / "summary.json"
    summary_md = output_root / "summary.md"
    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "rrapicoord-addon-settings-repair",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": verdict,
        "inputs": {
            "apply": args.apply,
            "scope": args.scope,
            "accountContains": args.account_contains,
            "addonsRoots": [str(path) for path in addon_roots],
            "selectedCount": len(selected),
            "discoveredCount": len(discovered),
        },
        "counts": {
            "repairCount": len(repairs),
            "changedCount": changed_count,
            "appliedCount": applied_count,
            "enabledAfterCount": enabled_count,
        },
        "repairs": repairs,
        "blockers": blockers,
        "warnings": warnings,
        "artifacts": {
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
            "backupRoot": str(backup_root),
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "x64dbgAttached": False,
            "cheatEngineUsed": False,
            "processMemoryReadByThisHelper": False,
            "targetMemoryWritten": False,
            "addonSettingsWritten": bool(args.apply and applied_count),
            "addonSourceFilesWritten": False,
            "backupsWritten": bool(args.apply and applied_count),
            "savedVariablesUsedAsLiveTruth": False,
            "promotionEligible": False,
        },
        "next": {
            "recommendedAction": (
                "Rerun rrapicoord_addon_state_diagnostics.py, then reload/restart the client before expecting the live marker."
                if args.apply and not blockers
                else "Review dry-run summary, then rerun with --apply if the selected AddonSettings path is correct."
            )
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(summary_json, summary)
    write_text_atomic(summary_md, markdown_summary(summary))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely enable RiftReaderApiProbe in RIFT AddonSettings with backups; no game input or reload."
    )
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--backup-root", type=Path)
    parser.add_argument("--addons-root", action="append", type=Path)
    parser.add_argument("--scope", choices=("latest", "all"), default=DEFAULT_SCOPE)
    parser.add_argument("--account-contains")
    parser.add_argument("--apply", action="store_true")
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
                    "backupRoot": summary["artifacts"]["backupRoot"],
                    "counts": summary["counts"],
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
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
    return 0 if summary["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
