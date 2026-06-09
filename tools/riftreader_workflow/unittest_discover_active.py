#!/usr/bin/env python3
"""Run active RiftReader unittest discovery while excluding retired suites.

OpenCode is a retired workflow surface in this repo. The historical OpenCode
unit tests remain available for explicit maintenance runs, but they should not
block the default active full-local validation tier.
"""

from __future__ import annotations

import argparse
import json
import sys
import unittest
from collections.abc import Sequence
from pathlib import Path


DEFAULT_RETIRED_MODULES = ("test_opencode_bridge", "test_opencode_status_packet")


def is_excluded_test_id(test_id: str, excluded_modules: set[str]) -> bool:
    parts = test_id.split(".")
    module = ".".join(parts[:-2]) if len(parts) >= 3 else parts[0]
    module_basename = module.rsplit(".", 1)[-1]
    return module in excluded_modules or module_basename in excluded_modules


def filter_suite(
    suite: unittest.TestSuite,
    *,
    excluded_modules: set[str],
    skipped: list[str],
) -> unittest.TestSuite:
    filtered = unittest.TestSuite()
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            nested = filter_suite(item, excluded_modules=excluded_modules, skipped=skipped)
            if nested.countTestCases():
                filtered.addTest(nested)
            continue
        test_id = item.id()
        if is_excluded_test_id(test_id, excluded_modules):
            skipped.append(test_id)
            continue
        filtered.addTest(item)
    return filtered


def build_summary(
    *,
    start_directory: str,
    pattern: str,
    excluded_modules: set[str],
    skipped: list[str],
    active_count: int,
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "mode": "riftreader-active-unittest-discover",
        "status": "ready",
        "startDirectory": start_directory,
        "pattern": pattern,
        "excludedModules": sorted(excluded_modules),
        "skippedTestCount": len(skipped),
        "activeTestCount": active_count,
    }


def self_test_report() -> dict[str, object]:
    excluded = set(DEFAULT_RETIRED_MODULES)
    checks = [
        {
            "name": "package-qualified-retired-opencode-id-is-excluded",
            "passed": is_excluded_test_id(
                "scripts.test_opencode_bridge.OpenCodeBridgePromptTests.test_example",
                excluded,
            ),
        },
        {
            "name": "active-module-id-is-not-excluded",
            "passed": not is_excluded_test_id(
                "scripts.test_decision_packet.DecisionPacketTests.test_example",
                excluded,
            ),
        },
    ]
    ok = all(bool(item["passed"]) for item in checks)
    return {
        "schemaVersion": 1,
        "mode": "riftreader-active-unittest-discover-self-test",
        "status": "passed" if ok else "failed",
        "ok": ok,
        "checks": checks,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run active RiftReader unittest discovery.")
    parser.add_argument("--start-directory", default="scripts")
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--top-level-directory", default=".")
    parser.add_argument(
        "--exclude-module",
        action="append",
        default=None,
        help="Module basename to exclude, e.g. test_opencode_bridge. Defaults to retired OpenCode suites.",
    )
    parser.add_argument("--include-retired-opencode", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print the discovery summary as JSON.")
    parser.add_argument("--self-test", action="store_true", help="Run internal checks without unittest discovery.")
    parser.add_argument("--verbosity", type=int, default=1)
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        report = self_test_report()
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(report)
        return 0 if report["ok"] else 1

    repo_root = Path.cwd()
    start_directory = str((repo_root / args.start_directory).resolve())
    top_level = str((repo_root / args.top_level_directory).resolve()) if args.top_level_directory else None
    excluded_modules = set(args.exclude_module or ())
    if not args.include_retired_opencode and args.exclude_module is None:
        excluded_modules.update(DEFAULT_RETIRED_MODULES)

    loader = unittest.TestLoader()
    discovered = loader.discover(start_directory, pattern=args.pattern, top_level_dir=top_level)
    skipped: list[str] = []
    suite = filter_suite(discovered, excluded_modules=excluded_modules, skipped=skipped)

    summary = build_summary(
        start_directory=args.start_directory,
        pattern=args.pattern,
        excluded_modules=excluded_modules,
        skipped=skipped,
        active_count=suite.countTestCases(),
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    else:
        print(summary, flush=True)
    if skipped:
        print("Skipped retired/inactive unittest modules:")
        for test_id in skipped[:40]:
            print(f"- {test_id}")
        if len(skipped) > 40:
            print(f"- ... {len(skipped) - 40} more")

    result = unittest.TextTestRunner(verbosity=args.verbosity).run(suite)
    return 0 if result.wasSuccessful() else 1


def main() -> int:
    try:
        return run()
    except (OSError, ImportError, AttributeError, TypeError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "mode": "riftreader-active-unittest-discover",
                    "status": "failed",
                    "ok": False,
                    "errorType": type(exc).__name__,
                    "error": str(exc),
                },
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
