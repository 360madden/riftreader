#!/usr/bin/env python3
"""Navmesh overlay — transparent window showing explored terrain and waypoints."""

import json
import math
import os
import sys
import time
import tkinter as tk
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CAPTURES_DIR = str(REPO_ROOT / "scripts" / "captures")

try:
    import ctypes
    import ctypes.wintypes
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class NavmeshOverlay:
    def __init__(self, navmesh_path, pid, base):
        self.pid = pid
        self.base = base
        self.navmesh = self._load_navmesh(navmesh_path)
        self.player_pos = None
        self.waypoints = []
        self.target_waypoint = None

        # Recording state
        self.is_recording = False
        self.recorded_positions = []
        self.record_sample_count = 0
        self.record_interval_ms = 500

        # View settings
        self.scale = 2.0  # pixels per game unit
        self.offset_x = 0
        self.offset_y = 0

        # Setup tkinter
        self.root = tk.Tk()
        self.root.title("Navmesh Overlay")
        self.root.geometry("600x400+100+100")
        self.root.configure(bg="black")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.85)

        # Make window click-through (transparent to mouse)
        if HAS_WIN32:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            style |= 0x00000020  # WS_EX_TRANSPARENT
            style |= 0x00000008  # WS_EX_LAYERED
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)

        # Canvas
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Controls
        controls = tk.Frame(self.root, bg="black")
        controls.pack(fill=tk.X)

        # Recording buttons
        self.record_btn = tk.Button(controls, text="Record", command=self.toggle_recording,
                                    fg="white", bg="#333")
        self.record_btn.pack(side=tk.LEFT, padx=2)
        self.record_label = tk.Label(controls, text="", fg="gray", bg="black")
        self.record_label.pack(side=tk.LEFT, padx=4)

        # Separator
        tk.Frame(controls, width=2, bg="gray").pack(side=tk.LEFT, fill=tk.Y, padx=4)

        # View buttons
        tk.Button(controls, text="+", command=lambda: self.zoom(1.2)).pack(side=tk.LEFT)
        tk.Button(controls, text="-", command=lambda: self.zoom(0.8)).pack(side=tk.LEFT)
        tk.Button(controls, text="Center", command=self.center_on_player).pack(side=tk.LEFT)
        tk.Button(controls, text="Clear WP", command=self.clear_waypoints).pack(side=tk.LEFT)
        tk.Label(controls, text="Click=waypoint, Drag=pan", fg="gray", bg="black").pack(side=tk.RIGHT)

        # Bindings
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<MouseWheel>", self.on_scroll)

        self._drag_start = None
        self._draw()

    def _load_navmesh(self, path):
        with open(path) as f:
            data = json.load(f)
        nodes = {}
        for key, val in data.get("nodes", {}).items():
            parts = key.split(",")
            x, z = float(parts[0]), float(parts[1])
            nodes[(x, z)] = val
        return {"nodes": nodes, "grid_size": data.get("grid_size", 2.0)}

    def _read_player_pos(self):
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            h = kernel32.OpenProcess(0x0010, False, self.pid)
            if not h:
                return None
            try:
                buf = ctypes.create_string_buffer(8)
                br = ctypes.c_size_t(0)
                COORD_RVA = 0x32EBDC0
                if not kernel32.ReadProcessMemory(h, ctypes.c_void_p(self.base + COORD_RVA), buf, 8, ctypes.byref(br)):
                    return None
                obj = int.from_bytes(buf.raw[:8], "little")
                if not (0x10000 < obj < 0x7FFFFFFFFFFFFFFF):
                    return None
                x, y, z = 0.0, 0.0, 0.0
                for name, off in [("x", 0x320), ("y", 0x324), ("z", 0x328)]:
                    if not kernel32.ReadProcessMemory(h, ctypes.c_void_p(obj + off), buf, 4, ctypes.byref(br)):
                        return None
                    val = ctypes.c_float.from_buffer(buf).value
                    if name == "x": x = val
                    elif name == "y": y = val
                    else: z = val
                return (x, y, z)
            finally:
                kernel32.CloseHandle(h)
        except Exception:
            return None

    def _game_to_canvas(self, gx, gz):
        if self.player_pos is None:
            return 300, 200
        px, _, pz = self.player_pos
        cx = 300 + (gx - px) * self.scale + self.offset_x
        cy = 200 - (gz - pz) * self.scale + self.offset_y
        return cx, cy

    def _canvas_to_game(self, cx, cy):
        if self.player_pos is None:
            return 0, 0
        px, _, pz = self.player_pos
        gx = px + (cx - 300 - self.offset_x) / self.scale
        gz = pz - (cy - 200 - self.offset_y) / self.scale
        return gx, gz

    def _draw(self):
        self.canvas.delete("all")

        # Update player position
        pos = self._read_player_pos()
        if pos:
            self.player_pos = pos

        # Draw navmesh nodes and connections
        drawn_edges = set()
        for (x, z), val in self.navmesh["nodes"].items():
            cx, cy = self._game_to_canvas(x, z)

            # Draw connections
            for neighbor_key in val.get("neighbors", []):
                neighbor_tuple = tuple(neighbor_key) if isinstance(neighbor_key, list) else neighbor_key
                edge = tuple(sorted([(x, z), neighbor_tuple]))
                if edge in drawn_edges:
                    continue
                drawn_edges.add(edge)
                nx, nz = neighbor_tuple
                ncx, ncy = self._game_to_canvas(nx, nz)
                self.canvas.create_line(cx, cy, ncx, ncy, fill="#334455", width=1)

            # Draw node
            self.canvas.create_oval(cx-3, cy-3, cx+3, cy+3, fill="#446688", outline="")

        # Draw player
        if self.player_pos:
            px, py, pz = self.player_pos
            pcx, pcy = self._game_to_canvas(px, pz)
            self.canvas.create_oval(pcx-6, pcy-6, pcx+6, pcy+6, fill="#00ff00", outline="white")
            self.canvas.create_text(pcx, pcy-15, text=f"({px:.0f},{pz:.0f})",
                                   fill="#00ff00", font=("Arial", 8))

        # Draw waypoints
        for i, (wx, wz) in enumerate(self.waypoints):
            wcx, wcy = self._game_to_canvas(wx, wz)
            is_target = (self.target_waypoint == i)
            color = "#ff4444" if is_target else "#ffaa00"
            size = 8 if is_target else 5
            self.canvas.create_oval(wcx-size, wcy-size, wcx+size, wcy+size,
                                   fill=color, outline="white")
            self.canvas.create_text(wcx, wcy-12, text=f"WP{i+1}",
                                   fill=color, font=("Arial", 8))

        # Draw status
        node_count = len(self.navmesh["nodes"])
        wp_count = len(self.waypoints)
        status = f"Nodes: {node_count} | Waypoints: {wp_count}"
        if self.is_recording:
            status += f" | REC: {self.record_sample_count} samples"
        self.canvas.create_text(10, 10, text=status,
                               fill="#aabbcc", anchor=tk.NW, font=("Arial", 9))

        self.root.after(500, self._draw)

    def on_click(self, event):
        gx, gz = self._canvas_to_game(event.x, event.y)
        self.waypoints.append((gx, gz))
        if self.target_waypoint is None:
            self.target_waypoint = 0
        print(f"Waypoint set: ({gx:.1f}, {gz:.1f})")

    def on_drag(self, event):
        if self._drag_start:
            dx = event.x - self._drag_start[0]
            dy = event.y - self._drag_start[1]
            self.offset_x += dx
            self.offset_y += dy
        self._drag_start = (event.x, event.y)

    def on_scroll(self, event):
        factor = 1.2 if event.delta > 0 else 0.8
        self.zoom(factor)

    def zoom(self, factor):
        self.scale *= factor
        self.scale = max(0.2, min(10.0, self.scale))

    def center_on_player(self):
        self.offset_x = 0
        self.offset_y = 0

    def clear_waypoints(self):
        self.waypoints = []
        self.target_waypoint = None

    def toggle_recording(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self.is_recording = True
        self.recorded_positions = []
        self.record_sample_count = 0
        self.record_btn.config(text="Stop", bg="#933")
        self.record_label.config(text="0 pts", fg="red")
        self._sample_record_position()

    def _stop_recording(self):
        self.is_recording = False
        self.record_btn.config(text="Record", bg="#333")
        self.record_label.config(fg="gray")
        if self.recorded_positions:
            self._save_recorded()

    def _sample_record_position(self):
        if not self.is_recording:
            return
        if self.player_pos:
            x, y, z = self.player_pos
            self.recorded_positions.append([round(x, 2), round(y, 2), round(z, 2)])
            self.record_sample_count += 1
            self.record_label.config(text=f"{self.record_sample_count} pts")
            # Add to navmesh live
            gs = self.navmesh.get("grid_size", 2.0)
            key = (round(x / gs) * gs, round(z / gs) * gs)
            if key not in self.navmesh["nodes"]:
                self.navmesh["nodes"][key] = []
            self.navmesh["nodes"][key].append({"x": round(x, 1), "y": round(y, 1), "z": round(z, 1)})
        self.root.after(self.record_interval_ms, self._sample_record_position)

    def _save_recorded(self):
        if not self.recorded_positions:
            return
        rec_path = os.path.join(CAPTURES_DIR, "recorded-navmesh-overlay.json")
        with open(rec_path, "w") as f:
            json.dump({"positions": self.recorded_positions, "count": len(self.recorded_positions)}, f, indent=2)
        nm_path = os.path.join(CAPTURES_DIR, "navmesh-merged.json")
        with open(nm_path, "w") as f:
            json.dump({"nodes": {f"{k[0]},{k[1]}": v for k, v in self.navmesh["nodes"].items()},
                       "grid_size": self.navmesh.get("grid_size", 2.0)}, f, indent=2)
        print(f"Saved {len(self.recorded_positions)} positions -> {rec_path}")
        print(f"Navmesh saved -> {nm_path} ({len(self.navmesh['nodes'])} nodes)")

    def run(self):
        self.root.mainloop()


def find_base(pid):
    import ctypes
    kernel32 = ctypes.windll.kernel32
    h = kernel32.OpenProcess(0x0010, False, pid)
    if not h:
        return None
    try:
        for b in [0x7FF728B80000, 0x7FF700000000, 0x7FF600000000]:
            buf = ctypes.create_string_buffer(8)
            br = ctypes.c_size_t(0)
            if kernel32.ReadProcessMemory(h, ctypes.c_void_p(b + 0x32EBDC0), buf, 8, ctypes.byref(br)):
                v = int.from_bytes(buf.raw[:8], "little")
                if 0x10000 < v < 0x7FFFFFFFFFFFFFFF:
                    return b
        return None
    finally:
        kernel32.CloseHandle(h)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--navmesh", type=str, default="scripts/captures/navmesh-merged.json")
    args = p.parse_args()

    base = find_base(args.pid)
    if not base:
        print("ERROR: cannot find base"); sys.exit(1)

    overlay = NavmeshOverlay(args.navmesh, args.pid, base)
    overlay.run()
