#!/usr/bin/env python3
"""RIFT nav8: Full navigation with A*, obstacles, zones, targeting.

Uses FreshState for all reads — no stale data, no infinite loops.
"""

import argparse
import heapq
import json
import math
import subprocess
import sys
import time
from pathlib import Path

from fresh_state import get_fresh_state, FreshState

SENDINPUT_DLL = str(Path(__file__).parent.parent / "tools" / "RiftReader.SendInput" / "bin" / "Release" / "net10.0-windows" / "RiftReader.SendInput.exe")
CAPTURES_DIR = str(Path(__file__).parent / "captures")
TURN_RATE_DEG_PER_SEC = 172.0


def send_key(key, hold_ms):
    subprocess.run([SENDINPUT_DLL, "--key", key, "--hold-ms", str(hold_ms), "--json"],
                   capture_output=True, text=True, timeout=5)


def normalize_angle(a):
    while a >= 180:
        a -= 360
    while a < -180:
        a += 360
    return a


def dist_2d(a, b):
    return math.sqrt((b["x"] - a["x"]) ** 2 + (b["z"] - a["z"]) ** 2)


def dist_3d(a, b):
    return math.sqrt((b["x"] - a["x"]) ** 2 + (b["y"] - a["y"]) ** 2 + (b["z"] - a["z"]) ** 2)


# ─── A* PATHFINDING ───────────────────────────────────────────────

def load_navmesh(path):
    try:
        with open(path) as f:
            data = json.load(f)
        nodes = {}
        for key, val in data.get("nodes", {}).items():
            parts = key.split(",")
            x, z = float(parts[0]), float(parts[1])
            nodes[(x, z)] = val
        return nodes, data.get("grid_size", 2.0)
    except FileNotFoundError:
        return {}, 2.0


def find_nearest_node(nodes, pos, max_dist=500.0):
    best = None
    best_dist = max_dist
    for (nx, nz), _ in nodes.items():
        d = math.sqrt((nx - pos["x"]) ** 2 + (nz - pos["z"]) ** 2)
        if d < best_dist:
            best_dist = d
            best = (nx, nz)
    return best, best_dist


def heuristic(a, b):
    return math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)


def astar(nodes, start, goal):
    if start not in nodes or goal not in nodes:
        return None
    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, goal)}
    visited = set()
    while open_set:
        _, current = heapq.heappop(open_set)
        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            return path
        if current in visited:
            continue
        visited.add(current)
        for neighbor_key in nodes.get(current, {}).get("neighbors", []):
            neighbor = tuple(neighbor_key) if isinstance(neighbor_key, list) else neighbor_key
            if neighbor not in nodes:
                continue
            tentative_g = g_score[current] + heuristic(current, neighbor)
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score[neighbor] = tentative_g + heuristic(neighbor, goal)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))
    return None


def interpolate_path(path, max_step=8.0):
    if len(path) < 2:
        return path
    result = [path[0]]
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        dist = math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)
        if dist > max_step:
            steps = int(dist / max_step)
            for s in range(1, steps + 1):
                t = s / steps
                result.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        result.append(b)
    return result


# ─── NAVIGATION ───────────────────────────────────────────────────

def turn_to_heading(current_heading_deg, target_heading_deg, verbose=False):
    diff = normalize_angle(target_heading_deg - current_heading_deg)
    if abs(diff) < 2.0:
        return "none", 0
    hold_ms = min(1000, max(150, int(abs(diff) / TURN_RATE_DEG_PER_SEC * 1000)))
    if diff > 0:
        if verbose:
            print(f"    turn LEFT {abs(diff):.1f} ({hold_ms}ms)")
        send_key("A", hold_ms)
    else:
        if verbose:
            print(f"    turn RIGHT {abs(diff):.1f} ({hold_ms}ms)")
        send_key("D", hold_ms)
    return ("left" if diff > 0 else "right"), diff


def walk_and_verify(fs, hold_ms=400, verbose=False):
    """Walk forward, then WAIT for fresh position to confirm movement.
    
    Returns (new_state, moved_distance).
    Always uses FreshState — no stale reads.
    """
    state_before = fs.read(validate=True)
    if not state_before:
        return None, 0

    send_key("W", hold_ms)

    # Wait for position to actually update (up to 1.5s)
    deadline = time.time() + 1.5
    while time.time() < deadline:
        time.sleep(0.15)
        state_after = fs.read(validate=True)
        if state_after:
            d = dist_2d(state_before, state_after)
            if d > 0.3:
                return state_after, d

    # Timeout — read final position
    state_after = fs.read(validate=True)
    if state_after:
        d = dist_2d(state_before, state_after)
        return state_after, d
    return state_before, 0


def navigate_to_point(fs, target, radius=5.0, max_steps=40, walk_ms=400,
                      verbose=False, obstacle_handler=None):
    """Navigate to a single point. All reads go through FreshState."""
    for i in range(max_steps):
        state = fs.read(validate=True)
        if not state:
            if verbose:
                print("  cannot read state")
            break

        dist = dist_2d(state, target)
        if dist <= radius:
            if verbose:
                print(f"  ARRIVED ({state['x']:.1f}, {state['z']:.1f}) dist={dist:.1f}")
            return True, i, state

        heading_deg = math.degrees(state["heading"]) if state["heading"] is not None else 0
        target_bearing = math.degrees(math.atan2(target["x"] - state["x"], target["z"] - state["z"]))

        turn_to_heading(heading_deg, target_bearing, verbose)
        time.sleep(0.2)

        new_state, moved = walk_and_verify(fs, walk_ms, verbose)

        if verbose and moved < 0.3:
            print(f"    STUCK (moved={moved:.2f})")

        if moved < 0.3 and obstacle_handler:
            recovered = obstacle_handler(fs, state, target, verbose)
            if not recovered:
                if verbose:
                    print(f"  OBSTACLE BLOCKED at step {i}")
                return False, i, state

    state = fs.read(validate=True)
    final_dist = dist_2d(state, target) if state else -1
    return final_dist <= radius * 2, max_steps, state


# ─── OBSTACLE HANDLER ─────────────────────────────────────────────

class ObstacleHandler:
    """Handles stuck with recovery strategies. Uses FreshState for all reads."""

    def __init__(self, max_retries=5):
        self.consecutive_stucks = 0
        self.max_retries = max_retries

    def handle(self, fs, current_state, target, verbose):
        self.consecutive_stucks += 1
        if self.consecutive_stucks >= self.max_retries:
            if verbose:
                print(f"    GIVING UP after {self.max_retries} stuck attempts")
            return False

        # Strategy 1: back up
        if verbose:
            print(f"    recovery: backward")
        send_key("S", 300)
        time.sleep(0.3)
        _, d = walk_and_verify(fs, 300, False)
        if d > 0.3:
            self.consecutive_stucks = 0
            return True

        # Strategy 2: strafe left
        if verbose:
            print(f"    recovery: strafe left")
        send_key("Q", 300)
        time.sleep(0.3)
        _, d = walk_and_verify(fs, 300, False)
        if d > 0.3:
            self.consecutive_stucks = 0
            return True

        # Strategy 3: strafe right
        if verbose:
            print(f"    recovery: strafe right")
        send_key("E", 300)
        time.sleep(0.3)
        _, d = walk_and_verify(fs, 300, False)
        if d > 0.3:
            self.consecutive_stucks = 0
            return True

        # Strategy 4: turn 90 degrees and walk
        if verbose:
            print(f"    recovery: 90-turn + walk")
        state = fs.read(validate=True)
        if state and state["heading"] is not None:
            heading_deg = math.degrees(state["heading"])
            bearing = math.degrees(math.atan2(target["x"] - state["x"], target["z"] - state["z"]))
            diff = normalize_angle(bearing - heading_deg)
            jitter = 90 if diff > 0 else -90
            hold_ms = int(abs(jitter) / TURN_RATE_DEG_PER_SEC * 1000)
            send_key("D" if jitter < 0 else "A", hold_ms)
            time.sleep(0.3)
            _, d = walk_and_verify(fs, walk_ms=400, verbose=False)
            if d > 0.3:
                self.consecutive_stucks = 0
                return True

        return False

    def reset(self):
        self.consecutive_stucks = 0


# ─── ZONE DETECTION ───────────────────────────────────────────────

class ZoneDetector:
    def __init__(self):
        self.last_pos = None
        self.zone_id = "unknown"
        self.transition_count = 0

    def update(self, state):
        if state is None:
            return None
        if self.last_pos is not None:
            dist = dist_3d(self.last_pos, state)
            if dist > 100 or abs(state["y"] - self.last_pos["y"]) > 50:
                self.transition_count += 1
                self.zone_id = f"zone_{self.transition_count}"
                self.last_pos = state
                return self.zone_id
        self.last_pos = state
        return None


# ─── TARGETING ────────────────────────────────────────────────────

class TargetingSystem:
    def __init__(self, fs):
        self.fs = fs

    def face_target(self, target_pos, verbose=False):
        state = self.fs.read(validate=True)
        if not state or state["heading"] is None:
            return False
        heading_deg = math.degrees(state["heading"])
        bearing = math.degrees(math.atan2(target_pos["x"] - state["x"], target_pos["z"] - state["z"]))
        turn_to_heading(heading_deg, bearing, verbose)
        time.sleep(0.3)
        return True

    def interact(self, verbose=False):
        if verbose:
            print("    INTERACT (F)")
        send_key("F", 100)
        time.sleep(0.5)

    def target_nearest(self, verbose=False):
        if verbose:
            print("    TARGET (Tab)")
        send_key("Tab", 100)
        time.sleep(0.3)

    def face_and_interact(self, target_pos, verbose=False):
        state = self.fs.read(validate=True)
        if not state:
            return False
        dist = dist_2d(state, target_pos)
        if dist > 5:
            if verbose:
                print(f"  Walking to target (dist={dist:.1f})")
            navigate_to_point(self.fs, target_pos, radius=3.0, max_steps=15, verbose=verbose)
        self.face_target(target_pos, verbose)
        self.interact(verbose)
        return True


# ─── MAIN ─────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="RIFT nav8: full navigation system")
    p.add_argument("--pid", type=int, required=True)
    sub = p.add_subparsers(dest="command")

    nav = sub.add_parser("navigate", help="Navigate to coordinates")
    nav.add_argument("--target-x", type=float, required=True)
    nav.add_argument("--target-z", type=float, required=True)
    nav.add_argument("--navmesh", type=str, default="scripts/captures/navmesh-merged.json")
    nav.add_argument("--radius", type=float, default=5.0)
    nav.add_argument("--max-steps", type=int, default=60)
    nav.add_argument("--verbose", "-v", action="store_true")

    route = sub.add_parser("route", help="Show A* route without navigating")
    route.add_argument("--target-x", type=float, required=True)
    route.add_argument("--target-z", type=float, required=True)
    route.add_argument("--navmesh", type=str, default="scripts/captures/navmesh-merged.json")

    face = sub.add_parser("face", help="Face a target position")
    face.add_argument("--target-x", type=float, required=True)
    face.add_argument("--target-z", type=float, required=True)
    face.add_argument("--verbose", "-v", action="store_true")

    interact = sub.add_parser("interact", help="Face and interact with target")
    interact.add_argument("--target-x", type=float, required=True)
    interact.add_argument("--target-z", type=float, required=True)
    interact.add_argument("--verbose", "-v", action="store_true")

    sub.add_parser("status", help="Show current position and heading")

    args = p.parse_args()
    if not args.command:
        p.print_help()
        sys.exit(1)

    fs = get_fresh_state(args.pid)
    if not fs:
        print("ERROR: cannot initialize fresh state")
        sys.exit(1)

    if args.command == "status":
        state = fs.read(validate=True)
        if state:
            heading = math.degrees(state["heading"]) if state["heading"] else None
            print(json.dumps({
                "x": round(state["x"], 2), "y": round(state["y"], 2),
                "z": round(state["z"], 2),
                "heading_deg": round(heading, 1) if heading else None,
            }, indent=2))
        else:
            print("ERROR: cannot read state"); sys.exit(1)

    elif args.command == "route":
        nodes, _ = load_navmesh(args.navmesh)
        state = fs.read(validate=True)
        if not state:
            print("ERROR: cannot read state"); sys.exit(1)
        start_node, start_dist = find_nearest_node(nodes, state)
        goal_pos = {"x": args.target_x, "z": args.target_z}
        goal_node, goal_dist = find_nearest_node(nodes, goal_pos)
        if not start_node or not goal_node:
            print(json.dumps({"ok": False, "error": "cannot find navmesh nodes"}))
            sys.exit(1)
        path = astar(nodes, start_node, goal_node)
        if path:
            path = interpolate_path(path)
            total_dist = sum(heuristic(path[i], path[i+1]) for i in range(len(path)-1))
            print(json.dumps({
                "ok": True, "nodes": len(path),
                "start_node": list(start_node), "goal_node": list(goal_node),
                "start_dist": round(start_dist, 1), "goal_dist": round(goal_dist, 1),
                "total_dist": round(total_dist, 1),
                "path": [{"x": round(p[0], 1), "z": round(p[1], 1)} for p in path],
            }, indent=2))
        else:
            print(json.dumps({"ok": False, "error": "no path found"}))

    elif args.command == "navigate":
        nodes, _ = load_navmesh(args.navmesh)
        state = fs.read(validate=True)
        if not state:
            print("ERROR: cannot read state"); sys.exit(1)

        start_node, start_dist = find_nearest_node(nodes, state)
        goal_pos = {"x": args.target_x, "z": args.target_z}
        goal_node, goal_dist = find_nearest_node(nodes, goal_pos)

        path = None
        if start_node and goal_node:
            path = astar(nodes, start_node, goal_node)
            if path:
                path = interpolate_path(path)
                # Add final waypoint if goal_node is far from actual target
                if goal_dist > 8.0:
                    path.append((args.target_x, args.target_z))
        if not path:
            if args.verbose:
                print("No navmesh path — navigating directly")
            path = [{"x": args.target_x, "z": args.target_z}]

        obstacle_handler = ObstacleHandler()
        zone_detector = ZoneDetector()
        total_steps = 0
        zones_visited = []

        if args.verbose:
            print(f"Path: {len(path)} waypoints")
            print(f"Start: ({state['x']:.1f}, {state['z']:.1f})")
            print(f"Goal: ({args.target_x:.1f}, {args.target_z:.1f})")

        for i, wp in enumerate(path):
            if args.verbose:
                print(f"\n--- WP {i+1}/{len(path)}: ({wp[0]:.1f}, {wp[1]:.1f}) ---")

            cur = fs.read(validate=True)
            zone = zone_detector.update(cur)
            if zone:
                zones_visited.append(zone)
                if args.verbose:
                    print(f"  ZONE TRANSITION: {zone}")

            ok, steps, _ = navigate_to_point(
                fs, {"x": wp[0], "z": wp[1]},
                radius=3.0, max_steps=max(5, args.max_steps // len(path)),
                verbose=args.verbose, obstacle_handler=obstacle_handler.handle,
            )
            total_steps += steps

            if not ok and i == len(path) - 1:
                ok, steps, _ = navigate_to_point(
                    fs, {"x": wp[0], "z": wp[1]},
                    radius=args.radius, max_steps=10,
                    verbose=args.verbose, obstacle_handler=obstacle_handler.handle,
                )
                total_steps += steps

        final = fs.read(validate=True)
        final_dist = dist_2d(final, goal_pos) if final else -1

        print(json.dumps({
            "ok": final_dist <= args.radius,
            "method": "nav8-astar",
            "total_steps": total_steps,
            "pathwaypoints": len(path),
            "zones": zones_visited,
            "final": {"x": round(final["x"], 1), "z": round(final["z"], 1)} if final else None,
            "dist": round(final_dist, 1),
        }, indent=2))

    elif args.command == "face":
        ts = TargetingSystem(fs)
        ok = ts.face_target({"x": args.target_x, "z": args.target_z}, args.verbose)
        state = fs.read(validate=True)
        heading = math.degrees(state["heading"]) if state and state["heading"] else None
        print(json.dumps({"ok": ok, "heading_deg": round(heading, 1) if heading else None}))

    elif args.command == "interact":
        ts = TargetingSystem(fs)
        ok = ts.face_and_interact({"x": args.target_x, "z": args.target_z}, args.verbose)
        print(json.dumps({"ok": ok}))


if __name__ == "__main__":
    main()
