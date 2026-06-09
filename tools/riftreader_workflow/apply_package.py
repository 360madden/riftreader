#!/usr/bin/env python3
"""Validate and optionally apply a RiftReader desktop ChatGPT package."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root
    from .common import repo_rel as rel
    from .common import safety_flags, timestamped_output_dir, utc_iso
    from .package_manifest import MANIFEST_NAME, load_manifest, sha256_file, validate_manifest
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root
    from riftreader_workflow.common import repo_rel as rel
    from riftreader_workflow.common import safety_flags, timestamped_output_dir, utc_iso
    from riftreader_workflow.package_manifest import MANIFEST_NAME, load_manifest, sha256_file, validate_manifest


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


def write_preview_diff(repo_root: Path, intake_dir: Path, files: list[dict[str, Any]]) -> str:
    for item in files:
        item["beforeBytes"] = read_bytes_if_exists(Path(str(item["targetPath"])))
    try:
        return write_diff(repo_root, intake_dir, files)
    finally:
        for item in files:
            item.pop("beforeBytes", None)


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


def preview_output(value: str, limit: int = 4000) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    if len(normalized) <= limit:
        return normalized
    return normalized[-limit:]


def run_command_with_env(
    label: str,
    args: list[str],
    cwd: Path,
    *,
    timeout_seconds: float,
    expected_exit_codes: set[int],
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = utc_iso()
    start_monotonic = time.monotonic()
    envelope: dict[str, Any] = {
        "label": label,
        "args": args,
        "cwd": str(cwd),
        "startedAtUtc": started,
        "timeoutSeconds": timeout_seconds,
        "exitCode": None,
        "ok": False,
        "timedOut": False,
        "stdoutPreview": "",
        "stderrPreview": "",
    }
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env=env,
        )
        envelope["exitCode"] = completed.returncode
        envelope["ok"] = completed.returncode in expected_exit_codes
        envelope["stdoutPreview"] = preview_output(completed.stdout)
        envelope["stderrPreview"] = preview_output(completed.stderr)
    except subprocess.TimeoutExpired as exc:
        envelope["timedOut"] = True
        envelope["error"] = f"TimeoutExpired:{exc}"
        envelope["stdoutPreview"] = preview_output(exc.stdout if isinstance(exc.stdout, str) else "")
        envelope["stderrPreview"] = preview_output(exc.stderr if isinstance(exc.stderr, str) else "")
    except FileNotFoundError as exc:
        envelope["error"] = f"FileNotFoundError:{exc}"
    except Exception as exc:  # noqa: BLE001 - command envelope must capture unexpected local failures.
        envelope["error"] = f"{type(exc).__name__}:{exc}"
    finally:
        envelope["endedAtUtc"] = utc_iso()
        envelope["durationSeconds"] = round(time.monotonic() - start_monotonic, 3)
    return envelope


def run_checks(
    repo_root: Path,
    checks: list[dict[str, Any]],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    check_cwd = cwd if cwd is not None else repo_root
    for check in checks:
        results.append(
            run_command_with_env(
                str(check["name"]),
                list(check["args"]),
                check_cwd,
                timeout_seconds=float(check["timeoutSeconds"]),
                expected_exit_codes=set(int(item) for item in check["expectedExitCodes"]),
                env=env,
            )
        )
    return results


def git_tracked_files(repo_root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=False,
        timeout=30,
    )
    if completed.returncode != 0:
        return []
    return [item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]


def copy_repo_snapshot(repo_root: Path, workspace: Path) -> None:
    tracked = git_tracked_files(repo_root)
    if tracked:
        for relative in tracked:
            source = repo_root / relative
            if not source.is_file():
                continue
            target = workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return

    skipped_dirs = {".git", ".riftreader-local", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
    for source in repo_root.rglob("*"):
        relative_path = source.relative_to(repo_root)
        if any(part in skipped_dirs for part in relative_path.parts):
            continue
        if not source.is_file():
            continue
        target = workspace / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def overlay_package_files(workspace: Path, files: list[dict[str, Any]]) -> None:
    for item in files:
        source = Path(str(item["sourcePath"]))
        target = workspace / str(item["target"]).replace("\\", "/")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def dry_run_check_env(repo_root: Path, workspace: Path, intake_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    git_dir_probe = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--git-dir"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if git_dir_probe.returncode != 0:
        return env

    git_dir = Path(git_dir_probe.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = repo_root / git_dir
    env["GIT_DIR"] = str(git_dir.resolve())
    env["GIT_WORK_TREE"] = str(workspace.resolve())
    env["GIT_INDEX_FILE"] = str((intake_dir / "dry-run-check.index").resolve())
    subprocess.run(
        ["git", "read-tree", "HEAD"],
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    return env


def run_dry_run_checks(repo_root: Path, intake_dir: Path, files: list[dict[str, Any]], checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    workspace_root = intake_dir / "dry-run-workspaces"
    workspace_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="workspace-", dir=workspace_root) as workspace_name:
        workspace = Path(workspace_name)
        copy_repo_snapshot(repo_root, workspace)
        overlay_package_files(workspace, files)
        env = dry_run_check_env(repo_root, workspace, intake_dir)
        return run_checks(repo_root, checks, cwd=workspace, env=env)


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
    declared_checks: list[dict[str, Any]] = []
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
        declared_checks = checks
        changed_files = [str(item["target"]) for item in files]
        if errors:
            status = "failed"
        elif not apply_requested:
            diff_path = write_preview_diff(repo_root, intake_dir, files)
            if run_declared_checks and checks:
                check_results = run_dry_run_checks(repo_root, intake_dir, files, checks)
                failed = [item for item in check_results if not item.get("ok")]
                if failed:
                    blockers.extend(f"check-failed:{item.get('label')}:{item.get('exitCode')}" for item in failed)
                    status = "blocked"
                else:
                    status = "passed"
            else:
                if checks and not run_declared_checks:
                    warnings.append("declared-checks-skipped")
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
        "declaredChecks": declared_checks,
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


SELF_TEST_TARGET = "docs/workflow/package-intake-selftest-preview.md"


def create_self_test_package(package_root: Path) -> dict[str, str]:
    package_root.mkdir(parents=True, exist_ok=True)
    source = package_root / "files" / "package-intake-selftest-preview.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "# Package Intake Self-Test Preview\n\n"
        "This file is generated inside a temporary package to prove dry-run package intake.\n",
        encoding="utf-8",
    )
    manifest = {
        "schemaVersion": 1,
        "packageName": "riftreader-package-intake-selftest",
        "manifestVersion": "self-test",
        "files": [
            {
                "source": "files/package-intake-selftest-preview.md",
                "target": SELF_TEST_TARGET,
                "sha256": sha256_file(source),
            }
        ],
        "checks": [],
    }
    (package_root / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"target": SELF_TEST_TARGET, "source": "files/package-intake-selftest-preview.md"}


def build_self_test_summary(repo_root: Path, run_root: Path) -> tuple[dict[str, Any], Path]:
    package_root = run_root / "package"
    intake_dir = run_root / "intake"
    package_info = create_self_test_package(package_root)
    intake_dir.mkdir(parents=True, exist_ok=True)
    target_path = repo_root / package_info["target"]
    before = read_bytes_if_exists(target_path)
    summary = build_summary(
        repo_root,
        package_root,
        intake_dir,
        apply_requested=False,
        run_declared_checks=True,
    )
    after = read_bytes_if_exists(target_path)
    no_target_write = before == after
    summary["selfTest"] = {
        "enabled": True,
        "runRoot": rel(repo_root, run_root),
        "packageRoot": rel(repo_root, package_root),
        "target": package_info["target"],
        "targetExistedBefore": before is not None,
        "noTargetWrite": no_target_write,
    }
    if not no_target_write:
        summary["errors"].append("self-test-target-mutated")
        summary["status"] = "failed"
    return summary, intake_dir


def next_recommended_action(summary: dict[str, Any]) -> str:
    if summary.get("status") == "failed":
        return "Fix package manifest/path/checksum errors before apply or review."
    if summary.get("status") == "blocked":
        return "Do not commit. Inspect blockers, rollback state, checks, and package diff before retrying."
    if summary.get("dryRun"):
        return "Review changed files and package diff; apply only after explicit approval with --apply."
    return "Review applied diff and validation output; stage/commit/push only through explicit user-approved Git commands."


def compact_summary(summary: dict[str, Any]) -> dict[str, Any]:
    checks = summary.get("checks") or []
    declared_checks = summary.get("declaredChecks") or []
    failed_checks = [item for item in checks if not item.get("ok")]
    return {
        "schemaVersion": 1,
        "kind": "riftreader-package-intake-compact-summary",
        "generatedAtUtc": summary.get("generatedAtUtc"),
        "status": summary.get("status"),
        "dryRun": summary.get("dryRun"),
        "packagePath": summary.get("packagePath"),
        "packageRoot": summary.get("packageRoot"),
        "changedFiles": summary.get("changedFiles") or [],
        "changedFileCount": len(summary.get("changedFiles") or []),
        "checks": {
            "declaredCount": len(declared_checks),
            "runCount": len(checks),
            "failedCount": len(failed_checks),
        },
        "blockers": summary.get("blockers") or [],
        "warnings": summary.get("warnings") or [],
        "errors": summary.get("errors") or [],
        "rollback": summary.get("rollback") or {},
        "selfTest": summary.get("selfTest") or {},
        "artifacts": summary.get("artifacts") or {},
        "safety": summary.get("safety") or {},
        "nextRecommendedAction": next_recommended_action(summary),
    }


def render_compact_markdown(summary: dict[str, Any]) -> str:
    compact = compact_summary(summary)
    lines = [
        "# RiftReader Package Intake Compact Summary",
        "",
        f"- Generated UTC: `{compact.get('generatedAtUtc')}`",
        f"- Status: `{compact.get('status')}`",
        f"- Dry run: `{compact.get('dryRun')}`",
        f"- Package: `{compact.get('packagePath')}`",
        f"- Changed file count: `{compact.get('changedFileCount')}`",
        f"- Diff: `{(compact.get('artifacts') or {}).get('diff')}`",
        f"- Next: {compact.get('nextRecommendedAction')}",
        "",
        "## Changed files",
        "",
    ]
    for changed in compact.get("changedFiles") or ["none"]:
        lines.append(f"- `{changed}`")
    self_test = compact.get("selfTest") or {}
    if self_test:
        lines.extend(
            [
                "",
                "## Self-test",
                "",
                f"- Run root: `{self_test.get('runRoot')}`",
                f"- Target: `{self_test.get('target')}`",
                f"- No target write: `{self_test.get('noTargetWrite')}`",
            ]
        )
    lines.extend(["", "## Blockers / warnings / errors", ""])
    for label in ("blockers", "warnings", "errors"):
        values = compact.get(label) or ["none"]
        lines.append(f"### {label}")
        for value in values:
            lines.append(f"- `{value}`")
        lines.append("")
    lines.extend(["## Safety", "", "| Flag | Value |", "|---|---:|"])
    for key, value in (compact.get("safety") or {}).items():
        lines.append(f"| `{key}` | `{value}` |")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate or apply a RiftReader desktop ChatGPT package.")
    parser.add_argument("--package", default=None, help="Package directory or .zip containing riftreader-package-manifest.json.")
    parser.add_argument("--self-test", action="store_true", help="Create and dry-run a temporary package to smoke-test package intake.")
    parser.add_argument("--repo-root", default=None, help="RiftReader repo root; auto-detected by default.")
    parser.add_argument("--apply", action="store_true", help="Apply files after validation. Default is dry-run/inspect only.")
    parser.add_argument("--no-checks", action="store_true", help="Skip manifest-declared checks after applying.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary only.")
    parser.add_argument("--compact-json", action="store_true", help="Print compact JSON summary for desktop ChatGPT/OpenCode.")
    parser.add_argument("--compact", action="store_true", help="Print compact Markdown summary for desktop ChatGPT/OpenCode.")
    parser.add_argument("--output-dir", default=None, help="Override ignored intake output root.")
    return parser


def write_summary_outputs(repo_root: Path, intake_dir: Path, summary: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    summary_path = intake_dir / "package-intake-summary.json"
    compact_json_path = intake_dir / "compact-package-intake-summary.json"
    compact_md_path = intake_dir / "COMPACT_PACKAGE_INTAKE.md"
    summary["artifacts"]["summaryJson"] = rel(repo_root, summary_path)
    summary["artifacts"]["compactJson"] = rel(repo_root, compact_json_path)
    summary["artifacts"]["compactMarkdown"] = rel(repo_root, compact_md_path)
    compact = compact_summary(summary)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    compact_json_path.write_text(json.dumps(compact, indent=2), encoding="utf-8")
    compact_md_path.write_text(render_compact_markdown(summary) + "\n", encoding="utf-8")
    return summary, compact


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    if not args.self_test and not args.package:
        print("error: --package is required unless --self-test is used", file=sys.stderr)
        return 1
    if args.self_test and args.apply:
        print("error: --self-test cannot be combined with --apply", file=sys.stderr)
        return 1
    default_output = repo_root / ".riftreader-local" / ("package-intake-selftest" if args.self_test else "package-intake")
    output_root = Path(args.output_dir) if args.output_dir else default_output
    if not output_root.is_absolute():
        output_root = repo_root / output_root
    if args.self_test:
        run_root = timestamped_output_dir(output_root)
        summary, intake_dir = build_self_test_summary(repo_root, run_root)
    else:
        intake_dir = timestamped_output_dir(output_root)
        summary = build_summary(
            repo_root,
            Path(args.package),
            intake_dir,
            apply_requested=args.apply,
            run_declared_checks=not args.no_checks,
        )
    summary, compact = write_summary_outputs(repo_root, intake_dir, summary)
    if args.compact_json:
        print(json.dumps(compact, indent=2))
    elif args.compact:
        print(render_compact_markdown(summary))
    elif args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Status: {summary['status']}")
        print(f"Dry run: {summary['dryRun']}")
        print(f"Summary: {summary['artifacts']['summaryJson']}")
        print(f"Compact: {summary['artifacts']['compactMarkdown']}")
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
