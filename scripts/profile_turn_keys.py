#!/usr/bin/env python3
"""Profile Rift turn-key/back-end combinations with proof-gated readback.

Python owns the workflow orchestration. PowerShell scripts are used only as
existing leaf adapters for orientation capture, proof-coordinate readback,
window screenshots, and key delivery.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rift_live_test.turn_keys import (
    DEFAULT_INPUT_MODES,
    DEFAULT_SHELLS,
    DEFAULT_TURN_KEYS,
    TurnKeyProfileConfig,
    TurnKeyProfiler,
)


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Profile Rift turn-key input backends without sending forward navigation.",
    )
    parser.add_argument("--pid", type=int, required=True, help="Exact target process id.")
    parser.add_argument("--hwnd", required=True, help="Exact target window handle, e.g. 0xE0DB2.")
    parser.add_argument("--process-name", default="rift_x64", help="Expected process name.")
    parser.add_argument(
        "--keys",
        nargs="+",
        default=DEFAULT_TURN_KEYS,
        help="Keys to test. Default: %(default)s",
    )
    parser.add_argument(
        "--input-modes",
        nargs="+",
        choices=DEFAULT_INPUT_MODES,
        default=DEFAULT_INPUT_MODES,
        help="Input backends to test. Default: %(default)s",
    )
    parser.add_argument(
        "--shells",
        nargs="+",
        default=DEFAULT_SHELLS,
        help="PowerShell hosts to use for post-rift-key.ps1. Default: %(default)s",
    )
    parser.add_argument("--repeat", type=int, default=1, help="Repeat each key/mode/shell combo.")
    parser.add_argument("--hold-ms", type=int, default=125, help="Key hold duration in milliseconds.")
    parser.add_argument(
        "--post-input-wait-ms",
        type=int,
        default=250,
        help="Delay after input before after-samples are captured.",
    )
    parser.add_argument(
        "--min-yaw-delta-degrees",
        type=float,
        default=1.0,
        help="Minimum absolute yaw delta for a turn-candidate classification.",
    )
    parser.add_argument(
        "--max-coord-delta",
        type=float,
        default=0.25,
        help="Maximum proof-coordinate planar delta allowed for a turn-candidate.",
    )
    parser.add_argument(
        "--proof-max-age-seconds",
        type=int,
        default=60,
        help="Max allowed proof-anchor age for before/after readbacks.",
    )
    parser.add_argument(
        "--readback-sample-count",
        type=int,
        default=3,
        help="Proof-coordinate samples per readback.",
    )
    parser.add_argument(
        "--readback-interval-ms",
        type=int,
        default=100,
        help="Interval between proof-coordinate readback samples.",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Optional output root. Defaults to scripts/captures.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually send bounded turn-key input. Without this, only a plan is written.",
    )
    parser.add_argument(
        "--refresh-proof-first",
        action="store_true",
        help="Run live_test.py ProofOnly once before profiling to refresh the proof anchor.",
    )
    parser.add_argument(
        "--refresh-proof-before-each-attempt",
        action="store_true",
        help="Run live_test.py ProofOnly before every live key attempt. Slow, but keeps the 60s proof gate fresh.",
    )
    parser.add_argument(
        "--proof-profile",
        default="ProofOnly",
        help="Profile name used by --refresh-proof-first.",
    )
    parser.add_argument(
        "--capture-screenshots",
        action="store_true",
        help="Capture before/after WGC screenshots for each attempt.",
    )
    parser.add_argument(
        "--require-screenshots",
        action="store_true",
        help="Fail closed if a requested before screenshot is unusable.",
    )
    parser.add_argument(
        "--continue-after-movement",
        action="store_true",
        help="Continue profiling even if a key causes proof-coordinate movement.",
    )
    parser.add_argument(
        "--command-timeout-seconds",
        type=int,
        default=120,
        help="Timeout for readback/orientation/screenshot helper commands.",
    )
    parser.add_argument(
        "--input-timeout-seconds",
        type=int,
        default=30,
        help="Timeout for post-rift-key.ps1 input commands.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = repo_root_from_script()
    output_root = Path(args.output_root) if args.output_root else None
    config = TurnKeyProfileConfig(
        repo_root=repo_root,
        process_id=args.pid,
        target_window_handle=args.hwnd,
        process_name=args.process_name,
        keys=tuple(args.keys),
        input_modes=tuple(args.input_modes),
        shells=tuple(args.shells),
        repeats=args.repeat,
        hold_milliseconds=args.hold_ms,
        post_input_wait_milliseconds=args.post_input_wait_ms,
        min_yaw_delta_degrees=args.min_yaw_delta_degrees,
        max_coord_delta=args.max_coord_delta,
        proof_max_age_seconds=args.proof_max_age_seconds,
        readback_sample_count=args.readback_sample_count,
        readback_interval_milliseconds=args.readback_interval_ms,
        live=args.live,
        refresh_proof_first=args.refresh_proof_first,
        refresh_proof_before_each_attempt=args.refresh_proof_before_each_attempt,
        proof_profile=args.proof_profile,
        capture_screenshots=args.capture_screenshots,
        require_screenshots=args.require_screenshots,
        stop_on_movement=not args.continue_after_movement,
        output_root=output_root,
        command_timeout_seconds=args.command_timeout_seconds,
        input_timeout_seconds=args.input_timeout_seconds,
    )
    summary = TurnKeyProfiler(config).run()
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
