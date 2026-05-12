from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.x64dbg_coord_chain_plan import main


class X64DbgCoordChainPlanTests(unittest.TestCase):
    def test_self_test_writes_plan_and_template_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "plan"
            with redirect_stdout(StringIO()):
                code = main(["--self-test", "--output-root", str(out), "--json"])

            self.assertEqual(code, 0)
            summary = json.loads((out / "coord-chain-plan-summary.json").read_text(encoding="utf-8"))
            template = json.loads((out / "x64dbg-coordinate-chain-candidate-template.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "planned")
            self.assertFalse(summary["safety"]["movementSent"])
            self.assertFalse(summary["safety"]["x64dbgLiveAttachStarted"])
            self.assertFalse(summary["safety"]["x64dbgCommandsExecuted"])
            self.assertFalse(summary["safety"]["movementAllowed"])
            self.assertEqual(template["watchWindow"]["sizeBytes"], 12)
            self.assertEqual(template["derivedChain"]["fieldOffsets"]["z"], "0x8")
            self.assertTrue((out / "coord-chain-plan.md").is_file())
            self.assertTrue((out / "x64dbg-coordinate-chain-session-checklist.md").is_file())

    def test_missing_required_inputs_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "blocked"
            with redirect_stdout(StringIO()):
                code = main(["--output-root", str(out), "--json"])

            self.assertEqual(code, 2)
            summary = json.loads((out / "coord-chain-plan-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("missing-candidate-address", summary["blockers"])
            self.assertIn("missing-api-coordinate", summary["blockers"])
            self.assertIn("missing-process-start-time-utc", summary["blockers"])

    def test_rift_plan_without_live_approval_warns_but_does_not_attach(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "rift-plan"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--output-root",
                        str(out),
                        "--candidate-address",
                        "0x20005B30800",
                        "--target-pid",
                        "63412",
                        "--target-hwnd",
                        "0xB70082",
                        "--process-start-time-utc",
                        "2026-05-12T19:00:00Z",
                        "--api-x",
                        "7376.87",
                        "--api-y",
                        "863.82",
                        "--api-z",
                        "2990.35",
                        "--api-sampled-at-utc",
                        "2026-05-12T19:38:31Z",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            summary = json.loads((out / "coord-chain-plan-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "planned")
            self.assertFalse(summary["safety"]["x64dbgLiveDebuggerApprovedForFutureSession"])
            self.assertFalse(summary["safety"]["x64dbgLiveAttachStarted"])
            self.assertTrue(any("not authorized" in warning for warning in summary["warnings"]))

    def test_allow_live_debugger_only_marks_future_approval_and_still_does_not_attach(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "approved-plan"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--output-root",
                        str(out),
                        "--candidate-address",
                        "0x20005B30800",
                        "--target-pid",
                        "63412",
                        "--target-hwnd",
                        "0xB70082",
                        "--process-start-time-utc",
                        "2026-05-12T19:00:00Z",
                        "--api-x",
                        "7376.87",
                        "--api-y",
                        "863.82",
                        "--api-z",
                        "2990.35",
                        "--api-sampled-at-utc",
                        "2026-05-12T19:38:31Z",
                        "--allow-live-debugger",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            summary = json.loads((out / "coord-chain-plan-summary.json").read_text(encoding="utf-8"))
            self.assertTrue(summary["safety"]["x64dbgLiveDebuggerApprovedForFutureSession"])
            self.assertFalse(summary["safety"]["x64dbgLiveAttachStarted"])
            self.assertFalse(summary["safety"]["x64dbgCommandsExecuted"])


if __name__ == "__main__":
    unittest.main()
