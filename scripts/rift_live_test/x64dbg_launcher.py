from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .x64dbg_safety import live_attach_policy


DEFAULT_X64DBG_PATHS = (
    Path(r"C:\RIFT MODDING\Tools\x64dbg\release\x64\x64dbg.exe"),
    Path(r"C:\RIFT MODDING\RiftReader\tools\reverse-engineering\x64dbg\release\x64\x64dbg.exe"),
)
SW_MINIMIZE = 6


def candidate_paths(explicit_path: Path | None = None) -> list[Path]:
    paths: list[Path] = []
    if explicit_path is not None:
        paths.append(explicit_path)
    env_path = os.environ.get("RIFTREADER_X64DBG_EXE")
    if env_path:
        paths.append(Path(env_path))
    paths.extend(DEFAULT_X64DBG_PATHS)
    return paths


def find_x64dbg_path(explicit_path: Path | None = None) -> Path | None:
    for path in candidate_paths(explicit_path):
        if path.is_file():
            return path
    return None


def safety_lines() -> list[str]:
    policy = live_attach_policy()
    return [
        "[x64dbg] Safety: this launcher opens x64dbg only; it does not attach to RIFT.",
        (
            "[x64dbg] Before any RIFT attach: generate a plan packet, prebuild detach, "
            f"keep default {policy['maxLiveAttachSeconds']}s live window, "
            f"abort if Responding=False >{policy['unresponsiveAbortSeconds']}s."
        ),
        (
            "[x64dbg] Default: at most "
            f"{policy['maxGoAttempts']} go/run attempt; no exception-swallow retry loop; "
            "detach first, analyze second."
        ),
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch local x64dbg without attaching to RIFT.")
    parser.add_argument("--x64dbg-path", type=Path, default=None, help="Optional explicit x64dbg.exe path.")
    parser.add_argument(
        "--no-minimize-window",
        action="store_true",
        help="Launch x64dbg normally instead of requesting a minimized window.",
    )
    parser.add_argument(
        "--print-safety-only",
        "-PrintSafetyOnly",
        action="store_true",
        help="Print the live-attach guard and exit without launching x64dbg.",
    )
    parser.add_argument("--json", action="store_true", help="Emit a compact machine-readable result.")
    return parser


def build_result(
    *,
    status: str,
    launched: bool,
    x64dbg_path: Path | None,
    minimize_requested: bool = True,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "launched": launched,
        "x64dbgPath": str(x64dbg_path) if x64dbg_path is not None else None,
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "x64dbgLiveAttachStarted": False,
            "processAttachOrMemoryReadStarted": False,
            "x64dbgWindowMinimizeRequested": minimize_requested,
            "liveAttachPolicy": live_attach_policy(),
        },
        "errors": list(errors or []),
    }


def write_result(result: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, separators=(",", ":")))
        return
    for line in safety_lines():
        print(line)
    if result["status"] == "safety-only":
        print("[x64dbg] PrintSafetyOnly set; not launching x64dbg.")
    elif result["status"] == "launched":
        print(f"[x64dbg] Launched: {result['x64dbgPath']}")
        if result.get("safety", {}).get("x64dbgWindowMinimizeRequested"):
            print("[x64dbg] Window minimize was requested at process launch.")
    else:
        for error in result.get("errors", []):
            print(f"[x64dbg] ERROR: {error}", file=sys.stderr)


def launch_kwargs(*, minimize_window: bool) -> dict[str, Any]:
    if not minimize_window or sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = SW_MINIMIZE
    return {"startupinfo": startupinfo}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    minimize_window = not bool(args.no_minimize_window)

    if args.print_safety_only:
        result = build_result(
            status="safety-only",
            launched=False,
            x64dbg_path=None,
            minimize_requested=minimize_window,
        )
        write_result(result, json_output=args.json)
        return 0

    exe_path = find_x64dbg_path(args.x64dbg_path)
    if exe_path is None:
        checked = "; ".join(str(path) for path in candidate_paths(args.x64dbg_path))
        result = build_result(
            status="blocked",
            launched=False,
            x64dbg_path=None,
            minimize_requested=minimize_window,
            errors=[f"x64dbg was not found. Checked: {checked}"],
        )
        write_result(result, json_output=args.json)
        return 2

    subprocess.Popen([str(exe_path)], close_fds=True, **launch_kwargs(minimize_window=minimize_window))  # noqa: S603
    result = build_result(status="launched", launched=True, x64dbg_path=exe_path, minimize_requested=minimize_window)
    write_result(result, json_output=args.json)
    return 0
