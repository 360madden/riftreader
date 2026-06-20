#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.riftreader_workflow import unittest_discover_active


class FakeCase:
    def __init__(self, test_id: str):
        self._test_id = test_id

    def id(self) -> str:
        return self._test_id

    def countTestCases(self) -> int:
        return 1

    def __call__(self, *args: object, **kwargs: object) -> None:
        return None


class UnittestDiscoverActiveTests(unittest.TestCase):
    def test_exclusion_matches_package_qualified_module_basename(self):
        excluded = set(unittest_discover_active.DEFAULT_RETIRED_MODULES)

        self.assertTrue(
            unittest_discover_active.is_excluded_test_id(
                "scripts.test_opencode_bridge.OpenCodeBridgePromptTests.test_example",
                excluded,
            )
        )
        self.assertFalse(
            unittest_discover_active.is_excluded_test_id(
                "scripts.test_validation_ledger.ValidationLedgerTests.test_example",
                excluded,
            )
        )

    def test_filter_suite_skips_retired_module_and_keeps_active_test(self):
        suite = unittest.TestSuite(
            [
                FakeCase("scripts.test_opencode_bridge.OpenCodeBridgePromptTests.test_example"),
                FakeCase("scripts.test_validation_ledger.ValidationLedgerTests.test_example"),
            ]
        )
        skipped: list[str] = []

        filtered = unittest_discover_active.filter_suite(
            suite,
            excluded_modules=set(unittest_discover_active.DEFAULT_RETIRED_MODULES),
            skipped=skipped,
        )

        self.assertEqual(filtered.countTestCases(), 1)
        self.assertEqual(
            skipped,
            ["scripts.test_opencode_bridge.OpenCodeBridgePromptTests.test_example"],
        )

    def test_self_test_report_passes(self):
        report = unittest_discover_active.self_test_report()

        self.assertTrue(report["ok"])
        self.assertEqual(report["status"], "passed")

    def test_run_self_test_json_exits_successfully(self):
        self.assertEqual(unittest_discover_active.run(["--self-test", "--json"]), 0)

    def test_aggregate_module_timings_sums_and_flags_slow_modules(self):
        module_timings, slow_modules = unittest_discover_active.aggregate_module_timings(
            [
                {
                    "id": "scripts.test_one.ExampleTests.test_a",
                    "module": "scripts.test_one",
                    "durationSeconds": 0.4,
                },
                {
                    "id": "scripts.test_one.ExampleTests.test_b",
                    "module": "scripts.test_one",
                    "durationSeconds": 0.8,
                },
                {
                    "id": "scripts.test_two.ExampleTests.test_c",
                    "module": "scripts.test_two",
                    "durationSeconds": 0.1,
                },
            ],
            slow_module_threshold_seconds=1.0,
        )

        self.assertEqual(module_timings[0]["module"], "scripts.test_one")
        self.assertEqual(module_timings[0]["testCount"], 2)
        self.assertEqual(module_timings[0]["durationSeconds"], 1.2)
        self.assertEqual(slow_modules, [module_timings[0]])

    def test_timing_payload_shape_and_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "timings" / "active.json"
            payload = unittest_discover_active.build_timing_payload(
                ok=True,
                duration_seconds=1.23456789,
                active_count=1,
                test_timings=[
                    {
                        "id": "scripts.test_one.ExampleTests.test_a",
                        "module": "scripts.test_one",
                        "durationSeconds": 0.25,
                    }
                ],
                slow_module_threshold_seconds=0.1,
                output_path=output_path,
            )

            unittest_discover_active.write_timing_payload(output_path, payload)
            written = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(written["schemaVersion"], 1)
        self.assertEqual(written["mode"], unittest_discover_active.TIMINGS_MODE)
        self.assertEqual(written["status"], "passed")
        self.assertTrue(written["ok"])
        self.assertEqual(written["durationSeconds"], 1.234568)
        self.assertEqual(written["activeTestCount"], 1)
        self.assertEqual(written["moduleTimings"][0]["module"], "scripts.test_one")
        self.assertEqual(written["slowModules"], written["moduleTimings"])
        self.assertEqual(written["outputPath"], str(output_path.resolve()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
