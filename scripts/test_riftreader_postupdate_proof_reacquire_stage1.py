#!/usr/bin/env python3
# Version: riftreader-postupdate-proof-reacquire-stage1-python-tests-v0.1.0
# Total-Character-Count: 3289
# Purpose: Unit tests for the Python-first RiftReader post-update proof reacquisition stage-1 helper. Tests are offline and do not touch RIFT, Git, Drive, or live input.

from __future__ import annotations

import json
import unittest
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import riftreader_postupdate_proof_reacquire_stage1 as helper


class Stage1HelperTests(unittest.TestCase):
    def test_safe_json_loads_plain_object(self) -> None:
        self.assertEqual(helper.safe_json_loads('{"ok": true}')["ok"], True)

    def test_safe_json_loads_noisy_stdout(self) -> None:
        parsed = helper.safe_json_loads("noise before\n{\"status\":\"passed\",\"ok\":true}\n")
        self.assertEqual(parsed["status"], "passed")
        self.assertTrue(parsed["ok"])

    def test_candidate_jsonl_from_scan(self) -> None:
        value = helper.candidate_jsonl_from_scan({"artifacts": {"candidateJsonl": "C:/x/candidates.jsonl"}})
        self.assertEqual(value, "C:/x/candidates.jsonl")

    def test_candidate_jsonl_missing(self) -> None:
        self.assertIsNone(helper.candidate_jsonl_from_scan({"artifacts": {}}))
        self.assertIsNone(helper.candidate_jsonl_from_scan(None))

    def test_visual_gate_ready(self) -> None:
        self.assertTrue(helper.visual_gate_ready({"readyForLiveInput": True}))
        self.assertFalse(helper.visual_gate_ready({"readyForLiveInput": False}))
        self.assertFalse(helper.visual_gate_ready(None))

    def test_should_run_batch_requires_all_gates(self) -> None:
        self.assertTrue(helper.should_run_batch(
            allow_movement_stimulus=True,
            visual_summary={"readyForLiveInput": True},
            candidate_jsonl="x.jsonl",
        ))
        self.assertFalse(helper.should_run_batch(
            allow_movement_stimulus=False,
            visual_summary={"readyForLiveInput": True},
            candidate_jsonl="x.jsonl",
        ))
        self.assertFalse(helper.should_run_batch(
            allow_movement_stimulus=True,
            visual_summary={"readyForLiveInput": False},
            candidate_jsonl="x.jsonl",
        ))
        self.assertFalse(helper.should_run_batch(
            allow_movement_stimulus=True,
            visual_summary={"readyForLiveInput": True},
            candidate_jsonl=None,
        ))

    def test_markdown_summary_contains_end_marker(self) -> None:
        text = helper.markdown_summary({
            "status": "candidate-file-ready",
            "ok": True,
            "repoRoot": "C:/repo",
            "runRoot": "C:/repo/scripts/captures/x",
            "target": {"processId": 1},
            "visualGateStatus": "passed-visual-baseline",
            "familyScanStatus": "passed",
            "candidateJsonl": "candidates.jsonl",
            "allowMovementStimulus": False,
            "movementSent": False,
            "batchStatus": "not-run",
            "nextAction": "next",
        })
        self.assertIn("END_OF_DOCUMENT_MARKER", text)


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
