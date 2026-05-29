#!/usr/bin/env python3
"""
Agent Rollback Tool
Restores agent definition files from a timestamped snapshot.

Usage:
    python scripts/agent-rollback.py --list                        # list snapshots
    python scripts/agent-rollback.py --snapshot snapshot-YYYYMMDD-HHMMSS  # restore
    python scripts/agent-rollback.py --snapshot latest             # restore newest
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / ".agents"
BACKUP_DIR = AGENTS_DIR / "backup"
SNAPSHOT_PATTERN = "snapshot-"


def list_snapshots() -> list[Path]:
    """Return existing snapshot directories sorted by name (newest first)."""
    if not BACKUP_DIR.exists():
        return []
    return sorted(
        [p for p in BACKUP_DIR.iterdir()
         if p.is_dir() and p.name.startswith(SNAPSHOT_PATTERN)],
        key=lambda p: p.name,
        reverse=True,
    )


def validate_snapshot(snapshot_dir: Path) -> tuple[bool, str]:
    """Check that a snapshot directory has a manifest and files."""
    if not snapshot_dir.exists():
        return False, f"Snapshot directory {snapshot_dir} does not exist"
    manifest = snapshot_dir / "manifest.json"
    if not manifest.exists():
        return False, f"No manifest.json in {snapshot_dir}"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    files = data.get("files", [])
    if not files:
        return False, "Manifest has no files listed"
    for f in files:
        src = snapshot_dir / f["name"]
        if not src.exists():
            return False, f"Missing file in snapshot: {f['name']}"
    return True, "valid"


def rollback(snapshot_dir: Path, dry_run: bool = False) -> dict:
    """Restore agent files from snapshot. Returns summary dict."""
    valid, msg = validate_snapshot(snapshot_dir)
    if not valid:
        return {"status": "error", "message": msg}

    manifest = json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))

    # Create a pre-rollback safety snapshot
    if not dry_run:
        safety_snap = BACKUP_DIR / f"pre-rollback-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        safety_snap.mkdir(parents=True, exist_ok=True)
        for f in AGENTS_DIR.iterdir():
            if f.is_file() and f.suffix == ".ts" and f.name != "types":
                shutil.copy2(f, safety_snap / f.name)

    restored = []
    for file_info in manifest["files"]:
        src = snapshot_dir / file_info["name"]
        dst = AGENTS_DIR / file_info["name"]
        if dry_run:
            restored.append({"name": file_info["name"], "action": "would restore"})
        else:
            shutil.copy2(src, dst)
            restored.append({"name": file_info["name"], "action": "restored"})

    result = {
        "status": "ok",
        "snapshotRestored": snapshot_dir.name,
        "restoredAtUtc": datetime.now(timezone.utc).isoformat(),
        "dryRun": dry_run,
        "files": restored,
    }

    if not dry_run:
        result["preRollbackSnapshot"] = safety_snap.name

    return result


def main():
    parser = argparse.ArgumentParser(description="Agent rollback tool")
    parser.add_argument("--list", action="store_true", help="List available snapshots")
    parser.add_argument("--snapshot", type=str, help="Snapshot name or 'latest'")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be restored without doing it")
    args = parser.parse_args()

    snapshots = list_snapshots()

    if args.list:
        if not snapshots:
            print("No snapshots found.")
            return 0
        print(f"{'#':<4} {'Snapshot Name':<30} {'Files':<8} {'Created'}")
        print("-" * 70)
        for i, snap in enumerate(snapshots, 1):
            manifest = snap / "manifest.json"
            if manifest.exists():
                data = json.loads(manifest.read_text(encoding="utf-8"))
                print(f"{i:<4} {snap.name:<30} {data.get('filesCopied', '?'):<8} "
                      f"{data.get('snapshotCreatedUtc', '?')}")
        return 0

    if not args.snapshot:
        parser.print_help()
        print("\nError: --snapshot is required (or use --list)")
        return 1

    if args.snapshot == "latest":
        if not snapshots:
            print("Error: No snapshots available for rollback.")
            return 1
        snapshot_dir = snapshots[0]
    else:
        snapshot_dir = BACKUP_DIR / args.snapshot

    print(f"Snapshot: {snapshot_dir.name}")
    print(f"Dry run:  {args.dry_run}")

    result = rollback(snapshot_dir, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))

    if result["status"] == "error":
        return 1

    if not args.dry_run:
        print(f"\nRollback complete. Pre-rollback safety snapshot: {result.get('preRollbackSnapshot')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
