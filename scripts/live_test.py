#!/usr/bin/env python3
"""Profile-driven RiftReader live-test orchestrator.

Python owns the workflow state machine. Existing PowerShell scripts are leaf
adapters only until their behavior is intentionally ported.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rift_live_test.profiles import load_profile, load_profiles
from rift_live_test.runner import LiveTestRunner


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a bounded RiftReader live-test profile."
    )
    parser.add_argument("--profile", help="Profile name from live-test config.")
    parser.add_argument("--pid", type=int, help="Exact target process id.")
    parser.add_argument("--hwnd", help="Exact target window handle, e.g. 0x2122E.")
    parser.add_argument(
        "--process-name",
        default=None,
        help="Expected process name override; default comes from profile.",
    )
    parser.add_argument("--profiles-file", default=None, help="Optional profile JSON path.")
    parser.add_argument("--output-root", default=None, help="Optional output root override.")
    parser.add_argument("--live", action="store_true", help="Allow live input profiles.")
    parser.add_argument("--list-profiles", action="store_true", help="List profiles and exit.")
    parser.add_argument(
        "--validate-profiles",
        action="store_true",
        help="Validate the profile config and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = repo_root_from_script()
    profiles_file = (
        Path(args.profiles_file)
        if args.profiles_file
        else repo_root / "configs" / "live-test-profiles.json"
    )

    if args.list_profiles or args.validate_profiles:
        config = load_profiles(profiles_file)
        names = sorted(config.get("profiles", {}).keys())
        if args.list_profiles:
            print(json.dumps({"profilesFile": str(profiles_file), "profiles": names}, indent=2))
        if args.validate_profiles:
            for name in names:
                load_profile(repo_root, profiles_file, name)
            print(
                json.dumps(
                    {
                        "status": "valid",
                        "profilesFile": str(profiles_file),
                        "profileCount": len(names),
                    },
                    indent=2,
                )
            )
        return 0

    if not args.profile:
        print("--profile is required unless listing/validating profiles", file=sys.stderr)
        return 2
    if args.pid is None:
        print("--pid is required for a live-test run", file=sys.stderr)
        return 2
    if not args.hwnd:
        print("--hwnd is required for a live-test run", file=sys.stderr)
        return 2

    profile = load_profile(repo_root, profiles_file, args.profile)
    if args.process_name:
        profile["processName"] = args.process_name
    if args.output_root:
        profile["outputRoot"] = args.output_root

    runner = LiveTestRunner(
        repo_root=repo_root,
        profile_name=args.profile,
        profile=profile,
        process_id=args.pid,
        target_window_handle=args.hwnd,
        live=args.live,
    )
    summary = runner.run()
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
