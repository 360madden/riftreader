#!/usr/bin/env python3

from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
