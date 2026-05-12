#!/usr/bin/env python3
# Version: riftreader-drive-outbox-export-v0.2.0
# Total-Character-Count: 11886
# Purpose: Export selected small, text-like RiftReader artifacts to the local Google Drive outbox with manifest, checksums, and safety metadata.

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_REPO_ROOT = Path(r"C:\RIFT MODDING\RiftReader")
DEFAULT_DRIVE_ROOT = Path(r"G:\My Drive\RiftReader")
DEFAULT_MAX_FILE_BYTES = 5_000_000

ALLOW_EXTENSIONS = {
    ".json", ".jsonl", ".md", ".txt", ".log", ".csv", ".html", ".htm", ".xml", ".yaml", ".yml",
}
BLOCKED_DIR_NAMES = {".git", ".venv", "venv", "__pycache__", "bin", "obj", "node_modules"}
BLOCKED_EXTENSIONS = {".bin", ".dmp", ".dump", ".exe", ".dll", ".pdb", ".zip", ".7z", ".rar", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".mp4", ".mov", ".avi"}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "openai_key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "slack_token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
}


@dataclass(frozen=True)
class FileDecision:
    source: Path
    relative_path: str
    include: bool
    reason: str
    size_bytes: int = 0
    sha256: str | None = None


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def is_text_like(path: Path, sample_bytes: int = 4096) -> bool:
    data = path.read_bytes()[:sample_bytes]
    return b"\x00" not in data


def contains_secret_pattern(path: Path, max_scan_bytes: int = 1_000_000) -> str | None:
    if path.stat().st_size > max_scan_bytes:
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    for name, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            return name
    return None


def normalize_rel(path_text: str) -> str:
    return path_text.replace("\\", "/").strip("/")


def ensure_under_root(path: Path, root: Path) -> None:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"path is outside repo root: {resolved_path}") from exc


def relative_to_repo(path: Path, repo_root: Path) -> str:
    return normalize_rel(str(path.resolve().relative_to(repo_root.resolve())))


def has_blocked_parent(path: Path, repo_root: Path) -> str | None:
    rel_parts = path.resolve().relative_to(repo_root.resolve()).parts
    for part in rel_parts[:-1]:
        if part in BLOCKED_DIR_NAMES:
            return part
    return None


def expand_sources(repo_root: Path, source_specs: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for spec in source_specs:
        candidate = Path(spec)
        if not candidate.is_absolute():
            candidate = repo_root / candidate
        if not candidate.exists():
            paths.append(candidate)
            continue
        if candidate.is_file():
            paths.append(candidate)
        else:
            for file_path in sorted(candidate.rglob("*")):
                if file_path.is_file():
                    paths.append(file_path)
    return paths


def decide_file(path: Path, repo_root: Path, max_file_bytes: int) -> FileDecision:
    try:
        ensure_under_root(path, repo_root)
        rel = relative_to_repo(path, repo_root)
    except Exception as exc:
        return FileDecision(path, str(path), False, f"path_invalid:{type(exc).__name__}:{exc}")

    if not path.exists():
        return FileDecision(path, rel, False, "missing")
    if not path.is_file():
        return FileDecision(path, rel, False, "not_file")

    blocked_parent = has_blocked_parent(path, repo_root)
    if blocked_parent:
        return FileDecision(path, rel, False, f"blocked_parent:{blocked_parent}")

    size = path.stat().st_size
    suffix = path.suffix.lower()
    if size > max_file_bytes:
        return FileDecision(path, rel, False, f"file_too_large:{size}", size_bytes=size)
    if suffix in BLOCKED_EXTENSIONS:
        return FileDecision(path, rel, False, f"blocked_extension:{suffix}", size_bytes=size)
    if suffix and suffix not in ALLOW_EXTENSIONS:
        return FileDecision(path, rel, False, f"extension_not_allowlisted:{suffix}", size_bytes=size)
    if not is_text_like(path):
        return FileDecision(path, rel, False, "binary_like_null_byte", size_bytes=size)

    secret = contains_secret_pattern(path)
    if secret:
        return FileDecision(path, rel, False, f"secret_pattern:{secret}", size_bytes=size)

    return FileDecision(path, rel, True, "included", size_bytes=size, sha256=sha256_file(path))


def default_sources(repo_root: Path) -> list[str]:
    candidates = [
        "docs/recovery/current-truth.md",
        "docs/recovery/current-proof-anchor-readback.json",
        "docs/recovery/automated-movement-stimulus-policy.md",
        "handoffs/current/PRE_UPDATE_GLYPH_PATCH_PENDING_HANDOFF_2026-05-11.md",
        "handoffs/current/post-update-baseline",
    ]
    return [item for item in candidates if (repo_root / item).exists()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def write_markdown_summary(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# RiftReader Drive outbox export",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Created UTC: `{manifest['createdUtc']}`",
        f"- Repo root: `{manifest['repoRoot']}`",
        f"- Drive root: `{manifest['driveRoot']}`",
        f"- Export directory: `{manifest['exportDirectory']}`",
        f"- Included files: `{manifest['counts']['included']}`",
        f"- Excluded files: `{manifest['counts']['excluded']}`",
        "",
        "## Included files",
        "",
    ]
    for item in manifest["filesIncluded"]:
        lines.append(f"- `{item['relativePath']}` (`{item['sizeBytes']}` bytes)")
    if manifest["filesExcluded"]:
        lines.extend(["", "## Excluded files", ""])
        for item in manifest["filesExcluded"]:
            lines.append(f"- `{item['relativePath']}` — `{item['reason']}`")
    lines.extend(["", "# END_OF_DOCUMENT_MARKER", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export selected RiftReader artifacts to local Google Drive outbox.")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--drive-root", default=str(DEFAULT_DRIVE_ROOT))
    parser.add_argument("--source", action="append", default=[], help="Repo-relative or absolute file/directory to export. Repeatable.")
    parser.add_argument("--default-sources", action="store_true", help="Include standard current status/recovery/baseline sources.")
    parser.add_argument("--outbox-subdir", default="run-summaries", choices=["run-summaries", "logs", "status"])
    parser.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    parser.add_argument("--label", default="manual")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    drive_root = Path(args.drive_root)

    if not repo_root.exists():
        raise FileNotFoundError(f"repo root not found: {repo_root}")
    if not (repo_root / ".git").exists():
        raise RuntimeError(f"repo root is not a git repository: {repo_root}")
    if not drive_root.exists():
        raise FileNotFoundError(f"drive root not found: {drive_root}")

    source_specs = list(args.source)
    if args.default_sources or not source_specs:
        source_specs.extend(default_sources(repo_root))
    if not source_specs:
        raise RuntimeError("no source paths supplied and no default sources exist")

    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "-", args.label).strip("-") or "manual"
    export_dir = drive_root / "outbox" / args.outbox_subdir / f"export-{safe_label}-{utc_stamp()}"
    files_dir = export_dir / "files"

    decisions = [decide_file(path, repo_root, args.max_file_bytes) for path in expand_sources(repo_root, source_specs)]
    included = [item for item in decisions if item.include]
    excluded = [item for item in decisions if not item.include]

    if not args.dry_run:
        export_dir.mkdir(parents=True, exist_ok=False)
        files_dir.mkdir(parents=True, exist_ok=True)
        for item in included:
            destination = files_dir / item.relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item.source, destination)

    files_included = [
        {
            "relativePath": item.relative_path,
            "source": str(item.source),
            "destination": str(files_dir / item.relative_path) if not args.dry_run else None,
            "sizeBytes": item.size_bytes,
            "sha256": item.sha256,
            "reason": item.reason,
        }
        for item in included
    ]
    files_excluded = [
        {
            "relativePath": item.relative_path,
            "source": str(item.source),
            "sizeBytes": item.size_bytes,
            "reason": item.reason,
        }
        for item in excluded
    ]

    manifest = {
        "schemaVersion": 1,
        "mode": "riftreader-drive-outbox-export",
        "status": "dry-run" if args.dry_run else "exported",
        "createdUtc": utc_iso(),
        "repoRoot": str(repo_root),
        "driveRoot": str(drive_root),
        "exportDirectory": str(export_dir),
        "outboxSubdir": args.outbox_subdir,
        "label": safe_label,
        "sourceSpecs": source_specs,
        "counts": {"included": len(files_included), "excluded": len(files_excluded)},
        "safety": {
            "repoWrites": False,
            "gitWrites": False,
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "googleDriveLocalWrites": not args.dry_run,
        },
        "filesIncluded": files_included,
        "filesExcluded": files_excluded,
    }

    if not args.dry_run:
        write_json(export_dir / "DRIVE_EXPORT_MANIFEST.json", manifest)
        write_json(export_dir / "files-included.json", files_included)
        write_json(export_dir / "files-excluded.json", files_excluded)
        write_markdown_summary(export_dir / "DRIVE_EXPORT_SUMMARY.md", manifest)

    if args.json:
        print(json.dumps(manifest, indent=2))
    else:
        print(json.dumps({
            "status": manifest["status"],
            "exportDirectory": manifest["exportDirectory"],
            "included": manifest["counts"]["included"],
            "excluded": manifest["counts"]["excluded"],
        }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

# End of script.
