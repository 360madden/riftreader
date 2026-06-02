from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.navigation_sequence_summary_contract import build_report, validate_sequence_summary_contract


def _dry_run_sequence_summary(**overrides: object) -> dict[str, object]:
    summary: dict[str, object] = {
        "schemaVersion": 1,
        "kind": "static-owner-continuous-route-sequence",
        "status": "passed",
        "verdict": "sequence-dry-run-plan-built",
        "operator": {
            "dryRun": True,
            "movementApproved": False,
            "turnApproved": False,
            "allowCandidateTurnControl": False,
        },
        "total": {
            "totalLegs": 2,
            "legsPlanned": 1,
            "legsArrived": 0,
            "legsFailed": 0,
            "totalTurnsExecuted": 0,
            "totalForwardSteps": 0,
        },
        "legs": [
            {
                "status": "passed",
                "verdict": "dry-run-plan-built",
                "safety": {
                    "movementSent": False,
                    "inputSent": False,
                    "navigationControl": False,
                },
                "blockers": [],
                "warnings": ["dry-run-only-no-input-sent"],
                "errors": [],
            }
        ],
        "blockers": [],
        "warnings": ["sequence-dry-run-stopped-after-leg-1-plan-no-simulated-movement"],
        "errors": [],
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "navigationControl": False,
            "x64dbgAttach": False,
            "debuggerAttached": False,
            "providerWrites": False,
            "targetMemoryBytesWritten": False,
        },
    }
    summary.update(overrides)
    return summary


class NavigationSequenceSummaryContractTests(unittest.TestCase):
    def test_accepts_safe_dry_run_sequence_summary(self) -> None:
        contract = validate_sequence_summary_contract(_dry_run_sequence_summary())

        self.assertEqual(contract["status"], "passed")
        self.assertTrue(contract["consumable"])
        self.assertEqual(contract["firstUnreachedLegIndex"], 1)
        self.assertEqual(contract["legsPlanned"], 1)

    def test_blocks_summary_that_sent_input(self) -> None:
        summary = _dry_run_sequence_summary(
            safety={
                "movementSent": False,
                "inputSent": True,
                "navigationControl": False,
            }
        )

        contract = validate_sequence_summary_contract(summary)

        self.assertEqual(contract["status"], "blocked")
        self.assertFalse(contract["consumable"])
        self.assertIn("sequence-safety-inputSent-must-be-false", contract["blockers"])

    def test_blocks_non_dry_run_operator_summary(self) -> None:
        summary = _dry_run_sequence_summary(operator={"dryRun": False})

        contract = validate_sequence_summary_contract(summary)

        self.assertEqual(contract["status"], "blocked")
        self.assertIn("sequence-operator-dryRun-must-be-true", contract["blockers"])

    def test_build_report_writes_consumer_contract_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_path = tmp_path / "sequence-summary.json"
            source_path.write_text(json.dumps(_dry_run_sequence_summary()), encoding="utf-8")

            report = build_report(source_path, output_root=tmp_path / "out", root=tmp_path)

        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["kind"], "static-owner-continuous-route-sequence-contract-report")
        self.assertTrue(report["contract"]["consumable"])
        self.assertFalse(report["safety"]["inputSent"])
        self.assertFalse(report["safety"]["movementSent"])


if __name__ == "__main__":
    unittest.main()
