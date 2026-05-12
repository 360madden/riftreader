#!/usr/bin/env python3
# Version: riftreader-drive-inbox-helper-v0.1.0
# Total-Character-Count: 11694
# Purpose: Manage the RiftReader Google Drive package inbox/status structure, import downloaded artifacts with SHA-256 verification, and emit clean JSON for ChatGPT Desktop, Codex CLI, or local scripts.
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

VERSION = "riftreader-drive-inbox-helper-v0.1.0"
PURPOSE = "Manage the RiftReader Google Drive package inbox/status structure and verified artifact imports."
DEFAULT_DRIVE_ROOT = r"G:\My Drive\RiftReader"
VALID_LANES = ("packages", "scripts", "prompts", "handoffs")
DIR_CONTRACT = (
    "inbox",
    "inbox/packages",
    "inbox/scripts",
    "inbox/prompts",
    "inbox/handoffs",
    "inbox/manifests",
    "package-archive",
    "status",
    "status/imports",
    "handoffs",
    "handoffs/current",
    "logs",
)


def utc_now() -> _dt.datetime:
    return _dt.datetime.now(tz=_dt.timezone.utc)


def iso_utc() -> str:
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def mkdirs(root: Path) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    for rel in DIR_CONTRACT:
        p = root / rel
        existed = p.exists()
        p.mkdir(parents=True, exist_ok=True)
        entries.append({"relative_path": rel, "path": str(p), "existed": existed, "exists": p.exists()})
    return {"directories": entries}


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def recent_files(path: Path, limit: int) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    files = [p for p in path.iterdir() if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    out: List[Dict[str, Any]] = []
    for p in files[:limit]:
        st = p.stat()
        out.append({
            "name": p.name,
            "path": str(p),
            "size_bytes": st.st_size,
            "modified_utc": _dt.datetime.fromtimestamp(st.st_mtime, tz=_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        })
    return out


def unique_destination(directory: Path, name: str) -> Path:
    candidate = directory / name
    if not candidate.exists():
        return candidate
    src = Path(name)
    suffix = "".join(src.suffixes)
    if suffix:
        stem = name[: -len(suffix)]
    else:
        stem = name
    return directory / f"{stem}.{stamp()}{suffix}"


def status_markdown(data: Dict[str, Any]) -> str:
    lines = [
        "# RiftReader Drive Inbox Status",
        "",
        f"- Version: `{VERSION}`",
        f"- Created UTC: `{data.get('created_utc')}`",
        f"- Drive root: `{data.get('drive_root')}`",
        f"- OK: `{data.get('ok')}`",
        f"- Code: `{data.get('code')}`",
        "",
        "## Directory Contract",
        "",
        "| Relative path | Exists |",
        "|---|---:|",
    ]
    for row in data.get("directories", []):
        lines.append(f"| `{row.get('relative_path')}` | `{row.get('exists')}` |")
    if data.get("recent"):
        lines.extend(["", "## Recent Inbox Files", "", "| Lane | File | Size | Modified UTC |", "|---|---|---:|---|"])
        for lane, rows in data["recent"].items():
            for row in rows:
                lines.append(f"| `{lane}` | `{row.get('name')}` | `{row.get('size_bytes')}` | `{row.get('modified_utc')}` |")
    lines.append("")
    return "\n".join(lines)


def import_markdown(data: Dict[str, Any]) -> str:
    lines = [
        "# RiftReader Drive Inbox Import Summary",
        "",
        f"- Version: `{VERSION}`",
        f"- Created UTC: `{data.get('created_utc')}`",
        f"- OK: `{data.get('ok')}`",
        f"- Code: `{data.get('code')}`",
        f"- Lane: `{data.get('lane')}`",
        f"- Source: `{data.get('source_path')}`",
        f"- Destination: `{data.get('destination_path')}`",
        f"- Size bytes: `{data.get('size_bytes')}`",
        f"- Source SHA-256: `{data.get('source_sha256')}`",
        f"- Destination SHA-256: `{data.get('destination_sha256')}`",
        f"- Removed source after verify: `{data.get('removed_source_after_verify')}`",
        f"- Manifest: `{data.get('manifest_path')}`",
        "",
    ]
    return "\n".join(lines)


def result_base(code: str, ok: bool, drive_root: Optional[Path] = None) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "ok": ok,
        "code": code,
        "version": VERSION,
        "purpose": PURPOSE,
        "created_utc": iso_utc(),
    }
    if drive_root is not None:
        data["drive_root"] = str(drive_root)
    return data


def emit(data: Dict[str, Any], json_mode: bool) -> None:
    if json_mode:
        sys.stdout.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
        return
    print(f"RiftReader Drive Inbox Helper {VERSION}")
    print(f"OK        : {data.get('ok')}")
    print(f"Code      : {data.get('code')}")
    if data.get("drive_root"):
        print(f"Drive root: {data.get('drive_root')}")
    if data.get("source_path"):
        print(f"Source    : {data.get('source_path')}")
    if data.get("destination_path"):
        print(f"Dest      : {data.get('destination_path')}")
    if data.get("manifest_path"):
        print(f"Manifest  : {data.get('manifest_path')}")
    if data.get("status_json_path"):
        print(f"Status JSON: {data.get('status_json_path')}")
    if data.get("status_md_path"):
        print(f"Status MD  : {data.get('status_md_path')}")
    if data.get("error"):
        print(f"Error     : {data.get('error')}")


def cmd_bootstrap(args: argparse.Namespace) -> Dict[str, Any]:
    root = Path(args.drive_root)
    data = result_base("BOOTSTRAP_COMPLETE", True, root)
    data.update(mkdirs(root))
    if args.write_status:
        status_json = root / "status" / "RIFTREADER_DRIVE_INBOX_STATUS.json"
        status_md = root / "status" / "RIFTREADER_DRIVE_INBOX_STATUS.md"
        write_json(status_json, data)
        write_text(status_md, status_markdown(data))
        data["status_json_path"] = str(status_json)
        data["status_md_path"] = str(status_md)
    return data


def cmd_status(args: argparse.Namespace) -> Dict[str, Any]:
    root = Path(args.drive_root)
    data = result_base("STATUS_COMPLETE", True, root)
    dirs: List[Dict[str, Any]] = []
    missing: List[str] = []
    for rel in DIR_CONTRACT:
        p = root / rel
        exists = p.exists()
        dirs.append({"relative_path": rel, "path": str(p), "exists": exists})
        if not exists:
            missing.append(rel)
    data["directories"] = dirs
    data["missing_directories"] = missing
    data["recent"] = {
        lane: recent_files(root / "inbox" / lane, args.limit)
        for lane in VALID_LANES
    }
    data["ok"] = len(missing) == 0
    data["code"] = "STATUS_COMPLETE" if data["ok"] else "STATUS_MISSING_DIRECTORIES"
    if args.write_status:
        status_json = root / "status" / "RIFTREADER_DRIVE_INBOX_STATUS.json"
        status_md = root / "status" / "RIFTREADER_DRIVE_INBOX_STATUS.md"
        write_json(status_json, data)
        write_text(status_md, status_markdown(data))
        data["status_json_path"] = str(status_json)
        data["status_md_path"] = str(status_md)
    return data


def cmd_import(args: argparse.Namespace) -> Dict[str, Any]:
    root = Path(args.drive_root)
    lane = args.lane
    if lane not in VALID_LANES:
        return {**result_base("INVALID_LANE", False, root), "lane": lane, "valid_lanes": list(VALID_LANES)}
    mkdirs(root)
    source = Path(args.source)
    if not source.exists() or not source.is_file():
        return {**result_base("SOURCE_NOT_FOUND", False, root), "source_path": str(source)}
    dest_dir = root / "inbox" / lane
    dest_dir.mkdir(parents=True, exist_ok=True)
    source_hash = sha256_file(source)
    dest = unique_destination(dest_dir, source.name)
    shutil.copy2(source, dest)
    dest_hash = sha256_file(dest)
    size = dest.stat().st_size
    verified = source_hash == dest_hash and source.stat().st_size == size
    data = result_base("IMPORT_VERIFIED" if verified else "IMPORT_VERIFY_FAILED", verified, root)
    data.update({
        "lane": lane,
        "source_path": str(source),
        "destination_path": str(dest),
        "size_bytes": size,
        "source_sha256": source_hash,
        "destination_sha256": dest_hash,
        "removed_source_after_verify": False,
    })
    manifest_path = root / "inbox" / "manifests" / f"{stamp()}_{dest.name}.import.json"
    data["manifest_path"] = str(manifest_path)
    if verified and args.remove_source_after_verify:
        source.unlink()
        data["removed_source_after_verify"] = True
    write_json(manifest_path, data)
    if args.write_status:
        summary_json = root / "status" / "imports" / f"{stamp()}_{dest.name}.json"
        summary_md = root / "status" / "imports" / f"{stamp()}_{dest.name}.md"
        write_json(summary_json, data)
        write_text(summary_md, import_markdown(data))
        data["status_json_path"] = str(summary_json)
        data["status_md_path"] = str(summary_md)
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=PURPOSE)
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("bootstrap", "status"):
        p = sub.add_parser(name)
        p.add_argument("--drive-root", default=DEFAULT_DRIVE_ROOT)
        p.add_argument("--json", action="store_true")
        p.add_argument("--write-status", action="store_true")
        if name == "status":
            p.add_argument("--limit", type=int, default=10)

    p = sub.add_parser("import")
    p.add_argument("--drive-root", default=DEFAULT_DRIVE_ROOT)
    p.add_argument("--source", required=True)
    p.add_argument("--lane", choices=VALID_LANES, default="packages")
    p.add_argument("--json", action="store_true")
    p.add_argument("--write-status", action="store_true")
    p.add_argument("--remove-source-after-verify", action="store_true")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    json_mode = bool(getattr(args, "json", False))
    try:
        if args.command == "bootstrap":
            data = cmd_bootstrap(args)
        elif args.command == "status":
            data = cmd_status(args)
        elif args.command == "import":
            data = cmd_import(args)
        else:
            data = {**result_base("UNKNOWN_COMMAND", False), "command": args.command}
        emit(data, json_mode)
        return 0 if data.get("ok") else 1
    except Exception as exc:
        data = {**result_base("UNHANDLED_EXCEPTION", False), "error": str(exc), "exception_type": type(exc).__name__}
        emit(data, json_mode)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
