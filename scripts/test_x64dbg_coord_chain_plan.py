from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.x64dbg_coord_chain_plan import main


class X64DbgCoordChainPlanTests(unittest.TestCase):
    def write_preflight_summary(
        self,
        path: Path,
        *,
        status: str = "passed",
        pid: int = 79184,
        hwnd: str = "0xA90BFC",
        generated_at: str = "2026-05-13T01:00:00Z",
        module_base: str = "0x7FF796B50000",
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "kind": "x64dbg-target-preflight",
                    "generatedAtUtc": generated_at,
                    "status": status,
                    "selectedTarget": {
                        "processName": "rift_x64",
                        "pid": pid,
                        "hwndHex": hwnd,
                        "startTimeUtc": "2026-05-13T00:43:12.080812Z",
                        "moduleBaseAddressHex": module_base,
                        "responding": True,
                    },
                    "debuggerProcessCount": 0,
                    "blockers": [],
                    "warnings": [],
                }
            ),
            encoding="utf-8",
        )

    def write_api_reference(
        self,
        path: Path,
        *,
        pid: int = 79184,
        hwnd: str = "0xA90BFC",
        x: float = 7376.87,
        y: float = 863.82,
        z: float = 2990.35,
        captured_at_utc: str = "2026-05-13T01:00:00Z",
        movement_sent: bool = False,
        no_cheat_engine: bool = True,
        saved_variables_use: str = "none",
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "source": "rrapicoord1-memory-scan",
                    "captured_at_utc": captured_at_utc,
                    "coordinate": {
                        "x": x,
                        "y": y,
                        "z": z,
                    },
                    "processId": pid,
                    "processName": "rift_x64",
                    "targetWindowHandle": hwnd,
                    "noCheatEngine": no_cheat_engine,
                    "movementSent": movement_sent,
                    "savedVariablesUse": saved_variables_use,
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
            self.assertEqual(template["process"]["moduleBaseAddressHex"], "0x7FF796B50000")
            self.assertTrue((out / "coord-chain-plan.md").is_file())
            self.assertTrue((out / "x64dbg-coordinate-chain-session-checklist.md").is_file())
            self.assertTrue((out / "x64dbg-coordinate-chain-rerun-command.txt").is_file())

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
            self.assertEqual(summary["process"]["moduleBaseAddressHex"], "0x7FF796B50000")
            self.assertEqual(summary["preflight"]["requestedSummary"], str(preflight))
            self.assertIsNone(summary["preflight"]["resolvedFromAlias"])
            self.assertEqual(summary["preflight"]["summaryPath"], str(preflight))

    def test_latest_preflight_summary_uses_newest_passed_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            old_preflight = temp_path / "scripts" / "captures" / "x64dbg-target-preflight-old" / "summary.json"
            blocked_preflight = temp_path / "scripts" / "captures" / "x64dbg-target-preflight-blocked" / "summary.json"
            latest_preflight = temp_path / "scripts" / "captures" / "x64dbg-target-preflight-new" / "summary.json"
            self.write_preflight_summary(
                old_preflight,
                pid=11111,
                hwnd="0x111",
                generated_at="2026-05-13T01:00:00Z",
            )
            self.write_preflight_summary(
                blocked_preflight,
                status="blocked",
                pid=22222,
                hwnd="0x222",
                generated_at="2026-05-13T03:00:00Z",
            )
            self.write_preflight_summary(
                latest_preflight,
                pid=33333,
                hwnd="0x333",
                generated_at="2026-05-13T02:00:00Z",
            )
            out = temp_path / "plan"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--repo-root",
                        str(temp_path),
                        "--output-root",
                        str(out),
                        "--preflight-summary",
                        "latest",
                        "--candidate-address",
                        "0x20005B30800",
                        "--api-x",
                        "7376.87",
                        "--api-y",
                        "863.82",
                        "--api-z",
                        "2990.35",
                        "--api-sampled-at-utc",
                        "2026-05-13T03:30:00Z",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            summary = json.loads((out / "coord-chain-plan-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["process"]["pid"], 33333)
            self.assertEqual(summary["process"]["hwnd"], "0x333")
            self.assertEqual(summary["process"]["moduleBaseAddressHex"], "0x7FF796B50000")
            self.assertEqual(summary["preflight"]["requestedSummary"], "latest")
            self.assertEqual(summary["preflight"]["resolvedFromAlias"], "latest")
            self.assertEqual(summary["preflight"]["summaryPath"], str(latest_preflight))

    def test_latest_preflight_summary_blocks_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            out = temp_path / "plan"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--repo-root",
                        str(temp_path),
                        "--output-root",
                        str(out),
                        "--preflight-summary",
                        "latest",
                        "--candidate-address",
                        "0x20005B30800",
                        "--api-x",
                        "7376.87",
                        "--api-y",
                        "863.82",
                        "--api-z",
                        "2990.35",
                        "--api-sampled-at-utc",
                        "2026-05-13T03:30:00Z",
                        "--json",
                    ]
                )

            self.assertEqual(code, 2)
            summary = json.loads((out / "coord-chain-plan-summary.json").read_text(encoding="utf-8"))
            self.assertIn(
                f"preflight-summary-latest-not-found:{temp_path / 'scripts' / 'captures' / 'x64dbg-target-preflight-*/summary.json'}",
                summary["blockers"],
            )
            self.assertEqual(summary["preflight"]["requestedSummary"], "latest")
            self.assertEqual(summary["preflight"]["resolvedFromAlias"], "latest")
            self.assertIsNone(summary["preflight"]["summaryPath"])

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

    def test_preflight_summary_module_base_mismatch_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            preflight = temp_path / "preflight-summary.json"
            self.write_preflight_summary(preflight, module_base="0x7FF796B50000")
            out = temp_path / "plan"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--output-root",
                        str(out),
                        "--preflight-summary",
                        str(preflight),
                        "--module-base",
                        "0x11110000",
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
            self.assertIn(
                "module-base-mismatch-preflight:0x11110000!=0x7FF796B50000",
                summary["blockers"],
            )

    def test_api_coordinate_file_populates_truth_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            preflight = temp_path / "preflight-summary.json"
            api_file = temp_path / "api-reference.json"
            self.write_preflight_summary(preflight)
            self.write_api_reference(api_file)
            out = temp_path / "plan"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--output-root",
                        str(out),
                        "--preflight-summary",
                        str(preflight),
                        "--api-coordinate-file",
                        str(api_file),
                        "--candidate-address",
                        "0x20005B30800",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            summary = json.loads((out / "coord-chain-plan-summary.json").read_text(encoding="utf-8"))
            template = json.loads((out / "x64dbg-coordinate-chain-candidate-template.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["truthSurface"]["source"], "rrapicoord1-memory-scan")
            self.assertEqual(summary["truthSurface"]["sampledAtUtc"], "2026-05-13T01:00:00Z")
            self.assertEqual(summary["truthSurface"]["x"], 7376.87)
            self.assertEqual(summary["truthSurface"]["artifactPath"], str(api_file))
            self.assertEqual(summary["apiCoordinateFile"]["path"], str(api_file))
            self.assertEqual(template["truthSurface"]["artifactPath"], str(api_file))
            command_text = (out / "x64dbg-coordinate-chain-rerun-command.txt").read_text(encoding="utf-8")
            self.assertIn(f"--preflight-summary '{preflight}'", command_text)
            self.assertIn(f"--api-coordinate-file '{api_file}'", command_text)
            self.assertIn("--candidate-address '0x20005B30800'", command_text)

    def test_api_coordinate_file_accepts_capture_summary_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            api_summary = temp_path / "api-reference-summary.json"
            api_summary.write_text(
                json.dumps(
                    {
                        "Mode": "rift-api-reference-coordinate-capture",
                        "Status": "captured",
                        "ProcessName": "rift_x64",
                        "ProcessId": 79184,
                        "TargetWindowHandle": "0xA90BFC",
                        "NoCheatEngine": True,
                        "MovementSent": False,
                        "SavedVariablesUsedAsLiveTruth": False,
                        "ReferenceFile": "C:\\captures\\reference.json",
                        "Coordinate": {
                            "X": 100.25,
                            "Y": 200.5,
                            "Z": 300.75,
                            "CapturedAtUtc": "2026-05-13T01:05:00Z",
                        },
                    }
                ),
                encoding="utf-8",
            )
            out = temp_path / "plan"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--output-root",
                        str(out),
                        "--api-coordinate-file",
                        str(api_summary),
                        "--candidate-address",
                        "0x20005B30800",
                        "--process-start-time-utc",
                        "2026-05-13T01:00:00Z",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            summary = json.loads((out / "coord-chain-plan-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["truthSurface"]["source"], "rift-api-reference-coordinate-capture")
            self.assertEqual(summary["truthSurface"]["x"], 100.25)
            self.assertEqual(summary["truthSurface"]["sampledAtUtc"], "2026-05-13T01:05:00Z")
            self.assertEqual(summary["apiCoordinateFile"]["referenceFile"], "C:\\captures\\reference.json")

    def test_api_coordinate_file_target_mismatch_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            preflight = temp_path / "preflight-summary.json"
            api_file = temp_path / "api-reference.json"
            self.write_preflight_summary(preflight, pid=79184)
            self.write_api_reference(api_file, pid=12345)
            out = temp_path / "plan"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--output-root",
                        str(out),
                        "--preflight-summary",
                        str(preflight),
                        "--api-coordinate-file",
                        str(api_file),
                        "--candidate-address",
                        "0x20005B30800",
                        "--json",
                    ]
                )

            self.assertEqual(code, 2)
            summary = json.loads((out / "coord-chain-plan-summary.json").read_text(encoding="utf-8"))
            self.assertIn("target-pid-mismatch-api-coordinate:79184!=12345", summary["blockers"])

    def test_api_coordinate_file_safety_fields_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            api_file = temp_path / "api-reference.json"
            self.write_api_reference(api_file, movement_sent=True)
            out = temp_path / "plan"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--output-root",
                        str(out),
                        "--api-coordinate-file",
                        str(api_file),
                        "--candidate-address",
                        "0x20005B30800",
                        "--process-start-time-utc",
                        "2026-05-13T01:00:00Z",
                        "--json",
                    ]
                )

            self.assertEqual(code, 2)
            summary = json.loads((out / "coord-chain-plan-summary.json").read_text(encoding="utf-8"))
            self.assertIn("api-coordinate-file-movement-sent", summary["blockers"])

    def test_api_coordinate_file_explicit_coordinate_mismatch_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            api_file = temp_path / "api-reference.json"
            self.write_api_reference(api_file, x=7376.87)
            out = temp_path / "plan"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--output-root",
                        str(out),
                        "--api-coordinate-file",
                        str(api_file),
                        "--candidate-address",
                        "0x20005B30800",
                        "--process-start-time-utc",
                        "2026-05-13T01:00:00Z",
                        "--api-x",
                        "1.0",
                        "--json",
                    ]
                )

            self.assertEqual(code, 2)
            summary = json.loads((out / "coord-chain-plan-summary.json").read_text(encoding="utf-8"))
            self.assertIn("api-coordinate-x-mismatch-file:1.0!=7376.87", summary["blockers"])


if __name__ == "__main__":
    unittest.main()
