#!/usr/bin/env python3
"""Record hand-picked absolute C2M waypoints from live static-chain pose.

No game input. Operator walks to clear ground, then:

  python scripts/c2m_route_record.py mark --name my-route
  python scripts/c2m_route_record.py mark
  python scripts/c2m_route_record.py finish
  python scripts/c2m_route_record.py status

Writes under scripts/routes/ (in-progress .partial.json + final .json).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Reuse pose helper bits via c2m_run_to_goal
SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from c2m_run_to_goal import (  # noqa: E402
    DEFAULT_ROOT_RVA,
    find_module_base,
    find_target,
    load_root_rva,
    read_heading_deg,
    read_static_chain_pose,
)


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def routes_dir() -> Path:
    d = REPO / "scripts" / "routes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def partial_path(name: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in name).strip("-") or "hand-picked"
    return routes_dir() / f"{safe}.partial.json"


def final_path(name: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in name).strip("-") or "hand-picked"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return routes_dir() / f"{safe}-{stamp}.json"


def load_partial(path: Path) -> dict:
    if not path.exists():
        return {
            "schemaVersion": 1,
            "kind": "riftreader-c2m-route-partial",
            "name": path.stem.replace(".partial", ""),
            "coordinateMode": "absolute",
            "defaultArrivalRadius": 3.0,
            "notes": "Hand-picked clear-ground waypoints (operator walked).",
            "createdAtUtc": utc_iso(),
            "waypoints": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def sample_pose() -> dict:
    t = find_target()
    if not t:
        raise RuntimeError("no-rift-target")
    root = load_root_rva(REPO)
    base = find_module_base(t["pid"])
    pose = read_static_chain_pose(t["pid"], module_base=base, root_rva=root)
    if not pose:
        raise RuntimeError("static-chain-pose-failed")
    heading = read_heading_deg(t["pid"], module_base=base, root_rva=root)
    return {
        "pid": t["pid"],
        "hwnd": t["hwndHex"],
        "moduleBase": pose.get("moduleBase"),
        "rootRva": pose.get("rootRva") or hex(root),
        "x": float(pose["x"]),
        "y": float(pose["y"]),
        "z": float(pose["z"]),
        "headingDeg": heading,
        "atUtc": utc_iso(),
    }


def cmd_mark(args: argparse.Namespace) -> int:
    name = args.name or "hand-picked"
    path = partial_path(name)
    doc = load_partial(path)
    if args.name:
        doc["name"] = args.name
    pose = sample_pose()
    n = len(doc["waypoints"]) + 1
    wp = {
        "id": args.id or f"wp-{n:02d}",
        "x": pose["x"],
        "y": pose["y"],
        "z": pose["z"],
        "arrivalRadius": float(args.arrival_radius),
        "markedAtUtc": pose["atUtc"],
        "headingDeg": pose["headingDeg"],
    }
    doc["waypoints"].append(wp)
    doc["lastPose"] = pose
    doc["updatedAtUtc"] = utc_iso()
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    out = {
        "status": "marked",
        "name": doc["name"],
        "count": len(doc["waypoints"]),
        "waypoint": wp,
        "partialPath": str(path),
        "hint": "Walk to next clear spot, then: python scripts/c2m_route_record.py mark"
        + (f" --name {doc['name']}" if doc.get("name") else "")
        + "  |  finish when done",
    }
    print(json.dumps(out, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    name = args.name or "hand-picked"
    path = partial_path(name)
    if not path.exists():
        print(json.dumps({"status": "empty", "partialPath": str(path), "count": 0}, indent=2))
        return 0
    doc = load_partial(path)
    print(
        json.dumps(
            {
                "status": "in-progress",
                "name": doc.get("name"),
                "count": len(doc.get("waypoints") or []),
                "waypoints": doc.get("waypoints"),
                "partialPath": str(path),
            },
            indent=2,
        )
    )
    return 0


def cmd_finish(args: argparse.Namespace) -> int:
    name = args.name or "hand-picked"
    path = partial_path(name)
    if not path.exists():
        print(json.dumps({"status": "failed", "error": "no-partial", "partialPath": str(path)}, indent=2))
        return 1
    doc = load_partial(path)
    wps = doc.get("waypoints") or []
    if len(wps) < 2:
        print(json.dumps({"status": "failed", "error": "need-at-least-2-waypoints", "count": len(wps)}, indent=2))
        return 1
    final = {
        "schemaVersion": 1,
        "kind": "riftreader-c2m-route",
        "name": doc.get("name") or name,
        "coordinateMode": "absolute",
        "defaultArrivalRadius": float(doc.get("defaultArrivalRadius") or args.arrival_radius),
        "zoneHint": "hand-picked clear ground — session absolute",
        "notes": doc.get("notes")
        or "Operator walked clear spots; re-run only in same zone/area.",
        "recordedAtUtc": utc_iso(),
        "waypoints": [
            {
                "id": w["id"],
                "x": w["x"],
                "y": w["y"],
                "z": w["z"],
                "arrivalRadius": w.get("arrivalRadius", doc.get("defaultArrivalRadius", 3.0)),
            }
            for w in wps
        ],
    }
    out_path = Path(args.output) if args.output else final_path(final["name"])
    out_path.write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")
    if not args.keep_partial:
        path.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "status": "finished",
                "count": len(final["waypoints"]),
                "routePath": str(out_path),
                "run": (
                    "python scripts/c2m_run_to_goal.py --execute --stimulus-approved "
                    "--use-current-truth --aim-mode w2s --pose-source static-chain "
                    "--heading-prestep "
                    f"--waypoints-json {out_path} --json"
                ),
            },
            indent=2,
        )
    )
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    name = args.name or "hand-picked"
    path = partial_path(name)
    if path.exists():
        path.unlink()
        print(json.dumps({"status": "cleared", "partialPath": str(path)}, indent=2))
    else:
        print(json.dumps({"status": "already-empty", "partialPath": str(path)}, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name, help_text in (
        ("mark", "Snapshot current pose as next waypoint"),
        ("status", "Show in-progress waypoints"),
        ("finish", "Write final absolute route JSON"),
        ("clear", "Delete in-progress partial"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--name", default="hand-picked", help="Route name (default hand-picked)")
        p.add_argument("--arrival-radius", type=float, default=3.0)
        if name == "mark":
            p.add_argument("--id", default=None, help="Optional waypoint id")
        if name == "finish":
            p.add_argument("--output", default=None, help="Optional output path")
            p.add_argument("--keep-partial", action="store_true")

    args = ap.parse_args()
    try:
        if args.cmd == "mark":
            return cmd_mark(args)
        if args.cmd == "status":
            return cmd_status(args)
        if args.cmd == "finish":
            return cmd_finish(args)
        if args.cmd == "clear":
            return cmd_clear(args)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
