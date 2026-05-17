#!/usr/bin/env python3
"""Validate and optionally apply a RiftReader desktop ChatGPT package."""

from __future__ import annotations

import argparse
import difflib
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, run_command_envelope as run_command
    from .common import repo_rel as rel
    from .common import safety_flags, timestamped_output_dir, utc_iso
    from .package_manifest import MANIFEST_NAME, load_manifest, validate_manifest
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, run_command_envelope as run_command
    from riftreader_workflow.common import repo_rel as rel
    from riftreader_workflow.common import safety_flags, timestamped_output_dir, utc_iso
    from riftreader_workflow.package_manifest import MANIFEST_NAME, load_manifest, validate_manifest


def prepare_package(package_path: Path, intake_dir: Path) -> Path:
    package_path = package_path.resolve()
    if package_path.is_dir():
        return package_path
    if package_path.is_file() and package_path.suffix.lower() == ".zip":
        extract_dir = intake_dir / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(package_path) as archive:
            for member in archive.infolist():
                name = member.filename.replace("\\", "/")
                if name.startswith("/") or ".." in Path(name).parts:
                    raise ValueError(f"zip-member-unsafe:{member.filename}")
            archive.extractall(extract_dir)
        return extract_dir
    raise ValueError(f"package-path-not-directory-or-zip:{package_path}")


def read_bytes_if_exists(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()


def text_diff(before: bytes | None, after: bytes, target: str) -> str:
    before_text = "" if before is None else before.decode("utf-8", errors="replace")
    after_text = after.decode("utf-8", errors="replace")
    before_lines = before_text.splitlines(keepends=True)
    after_lines = after_text.splitlines(keepends=True)
    fromfile = f"a/{target}" if before is not None else "/dev/null"
    tofile = f"b/{target}"
    return "".join(difflib.unified_diff(before_lines, after_lines, fromfile=fromfile, tofile=tofile))


def backup_target(repo_root: Path, backup_root: Path, target_path: Path, target_rel: str) -> dict[str, Any]:
    backup_path = backup_root / target_rel
    result = {
        "target": target_rel,
        "existed": target_path.exists(),
        "backupPath": rel(repo_root, backup_path),
    }
    if target_path.exists():
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target_path, backup_path)
    return result


def restore_backups(repo_root: Path, backups: list[dict[str, Any]]) -> list[str]:
    restored: list[str] = []
    for item in reversed(backups):
        target = repo_root / str(item["target"]).replace("\\", "/")
        backup = repo_root / str(item["backupPath"]).replace("\\", "/")
        if item.get("existed"):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)
            restored.append(str(item["target"]))
        elif target.exists():
            target.unlink()
            restored.append(str(item["target"]))
    return restored


def write_diff(repo_root: Path, intake_dir: Path, files: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for item in files:
        before = item.get("beforeBytes")
        after = Path(str(item["sourcePath"])).read_bytes()
        chunks.append(text_diff(before if isinstance(before, bytes) else None, after, str(item["target"])))
    diff_path = intake_dir / "package.diff"
    diff_path.write_text("\n".join(chunk for chunk in chunks if chunk), encoding="utf-8")
    return rel(repo_root, diff_path)


def apply_files(repo_root: Path, intake_dir: Path, files: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    backups: list[dict[str, Any]] = []
    backup_root = intake_dir / "backups"
    for item in files:
        source_path = Path(str(item["sourcePath"]))
        target_path = Path(str(item["targetPath"]))
        item["beforeBytes"] = read_bytes_if_exists(target_path)
        backups.append(backup_target(repo_root, backup_root, target_path, str(item["target"])))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
    diff_path = write_diff(repo_root, intake_dir, files)
    for item in files:
        item.pop("beforeBytes", None)
    return backups, diff_path


def run_checks(repo_root: Path, checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for check in checks:
        results.append(
            run_command(
                str(check["name"]),
                list(check["args"]),
                repo_root,
                timeout_seconds=float(check["timeoutSeconds"]),
                expected_exit_codes=set(int(item) for item in check["expectedExitCodes"]),
            )
        )
    return results


def build_summary(
    repo_root: Path,
    package_path: Path,
    intake_dir: Path,
    *,
    apply_requested: bool,
    run_declared_checks: bool,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    changed_files: list[str] = []
    backups: list[dict[str, Any]] = []
    check_results: list[dict[str, Any]] = []
    diff_path: str | None = None
    rollback: dict[str, Any] = {"performed": False, "restored": []}
    package_root: Path | None = None

    try:
        package_root = prepare_package(package_path, intake_dir)
        manifest = load_manifest(package_root)
        validation = validate_manifest(package_root, repo_root, manifest)
        warnings.extend(validation["warnings"])
        errors.extend(validation["errors"])
        files = validation["files"]
        checks = validation["checks"]
        changed_files = [str(item["target"]) for item in files]
        if errors:
            status = "failed"
        elif not apply_requested:
            status = "passed"
        else:
            backups, diff_path = apply_files(repo_root, intake_dir, files)
            if run_declared_checks and checks:
                check_results = run_checks(repo_root, checks)
                failed = [item for item in check_results if not item.get("ok")]
                if failed:
                    blockers.extend(f"check-failed:{item.get('label')}:{item.get('exitCode')}" for item in failed)
                    rollback["performed"] = True
                    rollback["restored"] = restore_backups(repo_root, backups)
                    status = "blocked"
                else:
                    status = "passed"
            else:
                if checks and not run_declared_checks:
                    warnings.append("declared-checks-skipped")
                status = "passed"
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{type(exc).__name__}:{exc}")
        status = "failed"

    summary = {
        "schemaVersion": 1,
        "kind": "riftreader-package-intake-summary",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "dryRun": not apply_requested,
        "repoRoot": str(repo_root),
        "packagePath": str(package_path.resolve()),
        "packageRoot": str(package_root) if package_root else None,
        "blockers": blockers,
        "warnings": warnings,
        "errors": errors,
        "changedFiles": changed_files,
        "backups": backups,
        "checks": check_results,
        "rollback": rollback,
        "artifacts": {
            "intakeDir": rel(repo_root, intake_dir),
            "summaryJson": rel(repo_root, intake_dir / "package-intake-summary.json"),
            "diff": diff_path,
        },
        "safety": safety_flags(),
    }
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate or apply a RiftReader desktop ChatGPT package.")
    parser.add_argument("--package", required=True, help="Package directory or .zip containing riftreader-package-manifest.json.")
    parser.add_argument("--repo-root", default=None, help="RiftReader repo root; auto-detected by default.")
    parser.add_argument("--apply", action="store_true", help="Apply files after validation. Default is dry-run/inspect only.")
    parser.add_argument("--no-checks", action="store_true", help="Skip manifest-declared checks after applying.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary only.")
    parser.add_argument("--output-dir", default=None, help="Override ignored intake output root.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    output_root = Path(args.output_dir) if args.output_dir else repo_root / ".riftreader-local" / "package-intake"
    if not output_root.is_absolute():
        output_root = repo_root / output_root
    intake_dir = timestamped_output_dir(output_root)

    summary = build_summary(
        repo_root,
        Path(args.package),
        intake_dir,
        apply_requested=args.apply,
        run_declared_checks=not args.no_checks,
    )
    summary_path = intake_dir / "package-intake-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Status: {summary['status']}")
        print(f"Dry run: {summary['dryRun']}")
        print(f"Summary: {summary['artifacts']['summaryJson']}")
        print(f"Diff: {summary['artifacts']['diff']}")
        if summary["blockers"]:
            print("Blockers:")
            for blocker in summary["blockers"]:
                print(f"- {blocker}")
        if summary["errors"]:
            print("Errors:")
            for error in summary["errors"]:
                print(f"- {error}")
    if summary["status"] == "failed":
        return 1
    if summary["status"] == "blocked":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
