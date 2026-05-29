#!/usr/bin/env python3
"""
Agent Snapshot Tool
Creates a timestamped backup of all custom agent definitions in .agents/.
Run this before creating or modifying any agent files.

Usage:
    python scripts/agent-snapshot.py              # create snapshot
    python scripts/agent-snapshot.py --list       # list existing snapshots
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
    snapshots = sorted(
        [p for p in BACKUP_DIR.iterdir() if p.is_dir() and p.name.startswith(SNAPSHOT_PATTERN)],
        key=lambda p: p.name,
        reverse=True,
    )
    return snapshots


def create_snapshot() -> dict:
    """Create a timestamped snapshot of agent files. Returns summary dict."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    snapshot_dir = BACKUP_DIR / f"{SNAPSHOT_PATTERN}{timestamp}"

    # Collect agent .ts files (skip types/ and backup/)
    agent_files = []
    for f in AGENTS_DIR.iterdir():
        if f.is_file() and f.suffix == ".ts":
            agent_files.append(f)

    if not agent_files:
        return {
            "status": "warning",
            "message": "No agent .ts files found to snapshot",
            "snapshotDir": str(snapshot_dir),
            "filesCopied": 0,
        }

    snapshot_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    for src in agent_files:
        dst = snapshot_dir / src.name
        shutil.copy2(src, dst)
        copied.append({"name": src.name, "size": src.stat().st_size})

    # Write manifest
    manifest = {
        "snapshotCreatedUtc": datetime.now(timezone.utc).isoformat(),
        "snapshotDir": str(snapshot_dir),
        "files": copied,
    }
    manifest_path = snapshot_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return {
        "status": "ok",
        "snapshotDir": str(snapshot_dir),
        "snapshotName": snapshot_dir.name,
        "filesCopied": len(copied),
        "manifestPath": str(manifest_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Agent snapshot tool")
    parser.add_argument("--list", action="store_true", help="List existing snapshots")
    args = parser.parse_args()

    if args.list:
        snapshots = list_snapshots()
        if not snapshots:
            print("No snapshots found.")
            return 0
        print(f"{'Snapshot Name':<30} {'Files':<8} {'Created'}")
        print("-" * 70)
        for snap in snapshots:
            manifest = snap / "manifest.json"
            if manifest.exists():
                data = json.loads(manifest.read_text(encoding="utf-8"))
                print(f"{snap.name:<30} {data.get('filesCopied', '?'):<8} "
                      f"{data.get('snapshotCreatedUtc', '?')}")
            else:
                print(f"{snap.name:<30} {'?':<8} {'(no manifest)'}")
        return 0

    result = create_snapshot()
    print(json.dumps(result, indent=2))
    if result["status"] == "ok":
        print(f"\nSnapshot created: {result['snapshotName']}")
        print(f"  Files copied: {result['filesCopied']}")
        print(f"  Directory:    {result['snapshotDir']}")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
