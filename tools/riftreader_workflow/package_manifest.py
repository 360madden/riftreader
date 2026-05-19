#!/usr/bin/env python3
"""Manifest validation utilities for RiftReader package intake."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any


MANIFEST_NAME = "riftreader-package-manifest.json"

DENIED_TARGET_PREFIXES = (
    ".git",
    ".riftreader-local",
    "scripts/captures",
    "scripts/sessions",
)

DENIED_COMMAND_FRAGMENTS = (
    "git add",
    "git commit",
    "git push",
    "git reset",
    "git clean",
    "send-rift-key",
    "post-rift-key",
    "cheatengine",
    "x64dbg",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(package_root: Path, manifest_name: str = MANIFEST_NAME) -> dict[str, Any]:
    manifest_path = package_root / manifest_name
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"manifest-not-json-object:{manifest_path}")
    return value


def _normalize_rel_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}-missing")
    raw = value.strip().replace("\\", "/")
    pure = PurePosixPath(raw)
    if pure.is_absolute():
        raise ValueError(f"{label}-absolute:{value}")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError(f"{label}-unsafe-segment:{value}")
    if ":" in raw:
        raise ValueError(f"{label}-contains-colon:{value}")
    return pure.as_posix()


def resolve_inside(base: Path, relative: str, label: str) -> Path:
    resolved_base = base.resolve()
    candidate = (resolved_base / relative).resolve()
    try:
        candidate.relative_to(resolved_base)
    except ValueError as exc:
        raise ValueError(f"{label}-outside-root:{relative}") from exc
    return candidate


def _validate_target_policy(relative: str) -> None:
    lowered = relative.lower()
    for prefix in DENIED_TARGET_PREFIXES:
        if lowered == prefix or lowered.startswith(f"{prefix}/"):
            raise ValueError(f"target-denied-prefix:{relative}")


def validate_target_path(value: Any, label: str = "target") -> str:
    """Normalize and validate a repo-relative package target path."""

    relative = _normalize_rel_path(value, label)
    _validate_target_policy(relative)
    return relative


def validate_check_definition(check: Any, index: int = 0) -> dict[str, Any]:
    """Validate an inert package check definition without executing it."""

    return _validate_check(check, index)


def _validate_check(check: Any, index: int) -> dict[str, Any]:
    if not isinstance(check, dict):
        raise ValueError(f"check-{index}-not-object")
    name = check.get("name")
    if not isinstance(name, str) or not name.strip():
        name = f"check-{index}"
    args = check.get("args")
    if not isinstance(args, list) or not args or not all(isinstance(item, str) and item for item in args):
        raise ValueError(f"check-{index}-args-invalid")
    joined = " ".join(args).lower()
    for fragment in DENIED_COMMAND_FRAGMENTS:
        if fragment in joined:
            raise ValueError(f"check-{index}-denied-command:{fragment}")
    expected = check.get("expectedExitCodes", [0])
    if not isinstance(expected, list) or not expected or not all(isinstance(item, int) for item in expected):
        raise ValueError(f"check-{index}-expected-exit-codes-invalid")
    timeout = check.get("timeoutSeconds", 120)
    if not isinstance(timeout, int | float) or timeout <= 0 or timeout > 1800:
        raise ValueError(f"check-{index}-timeout-invalid")
    return {
        "name": name.strip(),
        "args": args,
        "expectedExitCodes": expected,
        "timeoutSeconds": float(timeout),
    }


def validate_manifest(package_root: Path, repo_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    normalized_files: list[dict[str, Any]] = []
    normalized_checks: list[dict[str, Any]] = []

    if manifest.get("schemaVersion") != 1:
        errors.append(f"schema-version-unsupported:{manifest.get('schemaVersion')}")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        errors.append("files-missing-or-empty")
        files = []

    seen_targets: set[str] = set()
    for index, item in enumerate(files):
        try:
            if not isinstance(item, dict):
                raise ValueError(f"file-{index}-not-object")
            source_rel = _normalize_rel_path(item.get("source"), f"file-{index}-source")
            target_rel = validate_target_path(item.get("target"), f"file-{index}-target")
            if target_rel in seen_targets:
                raise ValueError(f"file-{index}-duplicate-target:{target_rel}")
            seen_targets.add(target_rel)
            source_path = resolve_inside(package_root, source_rel, f"file-{index}-source")
            target_path = resolve_inside(repo_root, target_rel, f"file-{index}-target")
            if not source_path.is_file():
                raise ValueError(f"file-{index}-source-missing:{source_rel}")
            expected_sha = item.get("sha256")
            if not isinstance(expected_sha, str) or len(expected_sha) != 64:
                raise ValueError(f"file-{index}-sha256-invalid")
            actual_sha = sha256_file(source_path)
            if actual_sha.lower() != expected_sha.lower():
                raise ValueError(f"file-{index}-sha256-mismatch:{source_rel}")
            normalized_files.append(
                {
                    "source": source_rel,
                    "target": target_rel,
                    "sourcePath": str(source_path),
                    "targetPath": str(target_path),
                    "sha256": actual_sha,
                    "exists": target_path.exists(),
                }
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    checks = manifest.get("checks", [])
    if checks is None:
        checks = []
    if not isinstance(checks, list):
        errors.append("checks-not-list")
        checks = []
    for index, check in enumerate(checks):
        try:
            normalized_checks.append(_validate_check(check, index))
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    if not checks:
        warnings.append("checks-empty")

    return {
        "schemaVersion": 1,
        "packageName": manifest.get("packageName"),
        "manifestVersion": manifest.get("manifestVersion"),
        "files": normalized_files,
        "checks": normalized_checks,
        "errors": errors,
        "warnings": warnings,
    }
