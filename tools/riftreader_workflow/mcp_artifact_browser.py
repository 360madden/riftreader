#!/usr/bin/env python3
"""Browse latest RiftReader MCP workflow artifacts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root
    from .mcp_workflow_state import ARTIFACT_KINDS, artifact_timeline, build_mcp_workflow_state
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root
    from riftreader_workflow.mcp_workflow_state import ARTIFACT_KINDS, artifact_timeline, build_mcp_workflow_state


def latest_payload(repo_root: Path) -> dict[str, Any]:
    state = build_mcp_workflow_state(repo_root)
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-artifact-browser-latest",
        "generatedAtUtc": state["generatedAtUtc"],
        "status": "ready",
        "ok": True,
        "latestArtifacts": state.get("latestArtifacts"),
        "counts": state.get("counts"),
        "recommendedNextAction": state.get("recommendedNextAction"),
        "warnings": state.get("warnings") or [],
        "safety": state.get("safety"),
    }


def open_latest_artifact(repo_root: Path, *, kind: str | None = None) -> dict[str, Any]:
    timeline = artifact_timeline(repo_root, kind=kind, limit=1)
    item = timeline["items"][0] if timeline.get("items") else None
    if not item:
        return {
            "schemaVersion": 1,
            "kind": "riftreader-mcp-artifact-browser-open-latest",
            "generatedAtUtc": timeline["generatedAtUtc"],
            "status": "blocked",
            "ok": False,
            "code": "NO_ARTIFACT_FOR_FILTER",
            "artifactKindFilter": kind,
            "blockers": ["no-artifact-for-filter"],
            "safety": timeline["safety"],
        }
    path = repo_root / str(item.get("path"))
    if not path.is_file():
        return {
            "schemaVersion": 1,
            "kind": "riftreader-mcp-artifact-browser-open-latest",
            "generatedAtUtc": timeline["generatedAtUtc"],
            "status": "blocked",
            "ok": False,
            "code": "ARTIFACT_FILE_MISSING",
            "artifact": item,
            "blockers": [f"artifact-file-missing:{path}"],
            "safety": timeline["safety"],
        }
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except AttributeError:
        return {
            "schemaVersion": 1,
            "kind": "riftreader-mcp-artifact-browser-open-latest",
            "generatedAtUtc": timeline["generatedAtUtc"],
            "status": "blocked",
            "ok": False,
            "code": "OPEN_LATEST_UNSUPPORTED_PLATFORM",
            "artifact": item,
            "blockers": ["open-latest-unsupported-platform"],
            "safety": timeline["safety"],
        }
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-artifact-browser-open-latest",
        "generatedAtUtc": timeline["generatedAtUtc"],
        "status": "passed",
        "ok": True,
        "artifactKindFilter": kind,
        "artifact": item,
        "openedPath": str(path),
        "safety": {
            **timeline["safety"],
            "readOnlyOpen": True,
        },
    }


def print_human(payload: dict[str, Any]) -> None:
    print(f"Status: {payload.get('status')}")
    latest = payload.get("latestArtifacts") if isinstance(payload.get("latestArtifacts"), dict) else {}
    if latest:
        for key, item in latest.items():
            if not item:
                print(f"- {key}: none")
                continue
            print(f"- {key}: {item.get('status')} ok={item.get('ok')} path={item.get('path')}")
    else:
        for item in payload.get("items") or []:
            print(f"- {item.get('artifactKind')}: {item.get('status')} ok={item.get('ok')} path={item.get('path')}")
    action = payload.get("recommendedNextAction")
    if isinstance(action, dict):
        print(f"Next: {action.get('key')} - {' '.join(action.get('command') or [])}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Browse latest RiftReader MCP artifacts.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--latest", action="store_true", help="Show latest artifact per MCP workflow kind.")
    mode.add_argument("--timeline", action="store_true", help="Show newest artifacts across MCP workflow kinds.")
    mode.add_argument("--kind", choices=ARTIFACT_KINDS, help="Show timeline for one artifact kind.")
    mode.add_argument("--open-latest", action="store_true", help="Open the newest discovered artifact locally.")
    parser.add_argument("--open-kind", choices=ARTIFACT_KINDS, help="Optional kind filter for --open-latest.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum timeline rows.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    if args.latest:
        payload = latest_payload(repo_root)
    elif args.timeline:
        payload = artifact_timeline(repo_root, limit=args.limit)
    elif args.open_latest:
        payload = open_latest_artifact(repo_root, kind=args.open_kind)
    else:
        payload = artifact_timeline(repo_root, kind=args.kind, limit=args.limit)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_human(payload)
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
