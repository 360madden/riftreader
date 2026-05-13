from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.x64dbg_coord_chain_plan import main


class X64DbgCoordChainPlanTests(unittest.TestCase):
    def write_preflight_summary(self, path: Path, *, status: str = "passed", pid: int = 79184, hwnd: str = "0xA90BFC") -> None:
        path.write_text(
            json.dumps(
                {
                    "status": status,
                    "selectedTarget": {
                        "processName": "rift_x64",
                        "pid": pid,
                        "hwndHex": hwnd,
                        "startTimeUtc": "2026-05-13T00:43:12.080812Z",
                        "moduleBaseAddressHex": "0x7FF796B50000",
                        "responding": True,
                    },
                    "debuggerProcessCount": 0,
                    "blockers": [],
                    "warnings": [],
                }
            ),
            encoding="utf-8",
        )

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
            self.assertEqual(summary["safety"]["liveAttachPolicy"]["maxLiveAttachSeconds"], 30)
            self.assertEqual(summary["safety"]["liveAttachPolicy"]["unresponsiveAbortSeconds"], 15)
            self.assertEqual(summary["safety"]["liveAttachPolicy"]["maxGoAttempts"], 1)
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

    def test_overlong_live_attach_window_blocks_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "overlong-plan"
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
                        "--max-live-attach-seconds",
                        "91",
                        "--json",
                    ]
                )

            self.assertEqual(code, 2)
            summary = json.loads((out / "coord-chain-plan-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("max-live-attach-seconds-exceeds-hard-limit:91>90", summary["blockers"])

    def test_preflight_summary_populates_target_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            preflight = temp_path / "preflight-summary.json"
            self.write_preflight_summary(preflight)
            out = temp_path / "plan"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--output-root",
                        str(out),
                        "--preflight-summary",
                        str(preflight),
                        "--candidate-address",
                        "0x20005B30800",
                        "--api-x",
                        "7376.87",
                        "--api-y",
                        "863.82",
                        "--api-z",
                        "2990.35",
                        "--api-sampled-at-utc",
                        "2026-05-13T01:00:00Z",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            summary = json.loads((out / "coord-chain-plan-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["process"]["pid"], 79184)
            self.assertEqual(summary["process"]["hwnd"], "0xA90BFC")
            self.assertEqual(summary["process"]["startTimeUtc"], "2026-05-13T00:43:12.080812Z")
            self.assertEqual(summary["preflight"]["summaryPath"], str(preflight))

    def test_preflight_summary_mismatch_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            preflight = temp_path / "preflight-summary.json"
            self.write_preflight_summary(preflight, pid=79184)
            out = temp_path / "plan"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--output-root",
                        str(out),
                        "--preflight-summary",
                        str(preflight),
                        "--target-pid",
                        "12345",
                        "--candidate-address",
                        "0x20005B30800",
                        "--api-x",
                        "7376.87",
                        "--api-y",
                        "863.82",
                        "--api-z",
                        "2990.35",
                        "--api-sampled-at-utc",
                        "2026-05-13T01:00:00Z",
                        "--json",
                    ]
                )

            self.assertEqual(code, 2)
            summary = json.loads((out / "coord-chain-plan-summary.json").read_text(encoding="utf-8"))
            self.assertIn("target-pid-mismatch-preflight:12345!=79184", summary["blockers"])


if __name__ == "__main__":
    unittest.main()
