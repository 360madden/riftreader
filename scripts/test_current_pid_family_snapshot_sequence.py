#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import current_pid_family_snapshot_sequence as sequence


def write_current_truth(
    path: Path,
    *,
    pid: int = 79184,
    hwnd: str = "0xA90BFC",
    address: str = "0x268D5A80730",
    duplicate_addresses: list[str] | None = None,
    movement_gate: dict | None = None,
    client_geometry: dict | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "riftreader-current-truth",
                "target": {
                    "processName": "rift_x64",
                    "processId": pid,
                    "targetWindowHandle": hwnd,
                    "processStartUtc": "2026-05-13T00:43:12.080812Z",
                    "moduleBase": "0x7FF796B50000",
                    **({"clientGeometry": client_geometry} if client_geometry is not None else {}),
                },
                "bestCurrentCandidate": {
                    "candidateId": "family-snapshot-hit-000004",
                    "addressHex": address,
                    "candidateFile": "scripts/captures/coordinate-family-snapshot-currentpid-79184/family-import-candidates.json",
                },
                "latestCoordinateReacquisition": {
                    "latestDuplicateCopyRankedAddresses": duplicate_addresses or [],
                },
                **({"movementGate": movement_gate} if movement_gate is not None else {}),
            }
        ),
        encoding="utf-8",
    )
    return path


def args(**overrides) -> argparse.Namespace:
    values = {
        "pid": None,
        "hwnd": None,
        "process_name": "rift_x64",
        "expected_start_time_utc": None,
        "expected_module_base": None,
        "current_truth_json": None,
        "disable_current_truth": False,
        "self_test": False,
        "top_count": 1,
        "max_total_ranges": 4,
        "max_prior_ranges": 3,
        "disable_default_priors": True,
        "prior_address": ["lead=0x200123"],
        "prior_family": [],
        "prior_radius": 0x2000,
        "prior_family_span": 0x10000,
        "prior_family_step": 0x10000,
        "prior_neighbor_family_count": 1,
        "prior_alignment": 0x1000,
        "auto_displacement_timeout_seconds": 15,
        "auto_displacement_input_backend": "csharp-scancode",
        "require_client_width": None,
        "require_client_height": None,
        "disable_emergency_key_release_guard": False,
        "allow_current_truth_movement_gate_override": False,
        "allow_window_message_auto_displacement": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class CurrentPidFamilySnapshotSequenceTests(unittest.TestCase):
    def test_prior_ranges_are_selected_before_generic_scan_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            scan_plan = Path(temp) / "scan-plan.json"
            scan_plan.write_text(
                json.dumps(
                    {
                        "ranges": [
                            {
                                "rank": 1,
                                "minAddressHex": "0x900000",
                                "maxAddressHex": "0xA00000",
                                "spanMiB": 1.0,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            selected, strategy = sequence.select_adaptive_scan_ranges(scan_plan, args())

            self.assertGreater(strategy["priorRangeCount"], 0)
            self.assertEqual(selected[0]["source"], "prior-exact-window")
            self.assertTrue(any(item["source"] == "current-pid-scan-plan" for item in selected))
            self.assertLess(
                selected.index(next(item for item in selected if item["source"] == "prior-exact-window")),
                selected.index(next(item for item in selected if item["source"] == "current-pid-scan-plan")),
            )

    def test_documented_default_priors_exist_when_not_disabled(self) -> None:
        ranges = sequence.build_prior_ranges(args(disable_default_priors=False, prior_address=[], max_prior_ranges=24))

        labels = {item["label"].split(":")[0] for item in ranges}
        self.assertIn("pid2928-best-focused-offset-copy-candidate", labels)
        self.assertIn("pid2928-offset-copy-family-base", labels)
        self.assertIn("pid60628-destination-copy-family", labels)
        self.assertIn("pid60628-best-moving-slot-family", labels)

    def test_operator_prior_outranks_documented_historical_priors(self) -> None:
        ranges = sequence.build_prior_ranges(
            args(
                disable_default_priors=False,
                prior_address=["currentTruth=0x268D5A80730"],
                max_prior_ranges=4,
            )
        )

        self.assertEqual(ranges[0]["label"], "currentTruth")
        self.assertEqual(ranges[0]["source"], "prior-exact-window")
        self.assertLess(ranges[0]["priority"], 10)
        self.assertTrue(any("currentTruth" in item["label"] for item in ranges))

    def test_current_truth_context_fills_target_and_candidate_prior(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            truth = write_current_truth(temp_path / "docs" / "recovery" / "current-truth.json")
            parsed = args(current_truth_json=truth, prior_address=[])

            context = sequence.apply_current_truth_context(parsed, temp_path)

            self.assertTrue(context["loaded"])
            self.assertEqual(parsed.pid, 79184)
            self.assertEqual(parsed.hwnd, "0xA90BFC")
            self.assertEqual(parsed.expected_start_time_utc, "2026-05-13T00:43:12.080812Z")
            self.assertEqual(parsed.expected_module_base, "0x7FF796B50000")
            self.assertIn("currentTruth=0x268D5A80730", parsed.prior_address)
            self.assertEqual(context["targetDefaultsApplied"], ["pid", "hwnd", "expected-start-time-utc", "expected-module-base"])
            self.assertFalse(context["blockers"])

    def test_current_truth_context_records_movement_gate_and_geometry_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            truth = write_current_truth(
                temp_path / "docs" / "recovery" / "current-truth.json",
                movement_gate={
                    "allowed": False,
                    "status": "blocked-live-input-spin-incident",
                    "automationMovementPaused": True,
                    "liveInputIncident": {"status": "agent-live-movement-paused-after-spin-incident"},
                },
                client_geometry={
                    "requiredClientWidth": 640,
                    "requiredClientHeight": 360,
                    "lastVerifiedAtUtc": "2026-05-20T01:20:10Z",
                },
            )
            parsed = args(current_truth_json=truth, prior_address=[])

            context = sequence.apply_current_truth_context(parsed, temp_path)

            self.assertEqual(parsed.require_client_width, 640)
            self.assertEqual(parsed.require_client_height, 360)
            self.assertEqual(context["movementGate"]["status"], "blocked-live-input-spin-incident")
            self.assertTrue(context["movementGate"]["automationMovementPaused"])
            self.assertEqual(
                sequence.current_truth_auto_displacement_blockers(parsed),
                [
                    "current-truth-movement-gate-blocked:blocked-live-input-spin-incident",
                    "current-truth-automation-movement-paused",
                    "current-truth-live-input-incident:agent-live-movement-paused-after-spin-incident",
                ],
            )

    def test_current_truth_context_adds_duplicate_copy_priors_after_best_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            truth = write_current_truth(
                temp_path / "docs" / "recovery" / "current-truth.json",
                address="0x268D5A80730",
                duplicate_addresses=["0x268D5A80730", "0x268D5FC52B0", "0x268D5F6C8E0"],
            )
            parsed = args(current_truth_json=truth, prior_address=[])

            context = sequence.apply_current_truth_context(parsed, temp_path)

            self.assertEqual(
                parsed.prior_address,
                [
                    "currentTruth=0x268D5A80730",
                    "duplicateCopy2=0x268D5FC52B0",
                    "duplicateCopy3=0x268D5F6C8E0",
                ],
            )
            self.assertEqual(context["priorDefaultsApplied"], parsed.prior_address)

    def test_current_truth_context_blocks_explicit_target_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            truth = write_current_truth(temp_path / "docs" / "recovery" / "current-truth.json")
            parsed = args(current_truth_json=truth, pid=12345, hwnd="0xA90BFC", prior_address=[])

            context = sequence.apply_current_truth_context(parsed, temp_path)

            self.assertIn("current-truth-target-pid-mismatch:12345!=79184", context["blockers"])
            self.assertIn("currentTruth=0x268D5A80730", parsed.prior_address)

    def test_plan_only_can_bootstrap_from_current_truth_without_manual_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            write_current_truth(temp_path / "docs" / "recovery" / "current-truth.json")
            scan_plan = (
                temp_path
                / "scripts"
                / "captures"
                / "memory-region-inventory-currentpid-79184-test"
                / "scan-plan.json"
            )
            scan_plan.parent.mkdir(parents=True, exist_ok=True)
            scan_plan.write_text(
                json.dumps(
                    {
                        "ranges": [
                            {
                                "rank": 1,
                                "minAddressHex": "0x900000",
                                "maxAddressHex": "0xA00000",
                                "spanMiB": 1.0,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out = temp_path / "sequence"

            original_argv = None
            import sys

            original_argv = sys.argv
            try:
                sys.argv = [
                    "current_pid_family_snapshot_sequence.py",
                    "--repo-root",
                    str(temp_path),
                    "--output-root",
                    str(out),
                    "--plan-only",
                    "--disable-default-priors",
                    "--max-prior-ranges",
                    "1",
                    "--json",
                ]
                with redirect_stdout(StringIO()):
                    code = sequence.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["processId"], 79184)
            self.assertEqual(summary["targetWindowHandle"], "0xA90BFC")
            self.assertTrue(summary["currentTruth"]["loaded"])
            self.assertEqual(manifest["scanRanges"][0]["label"], "currentTruth")

    def test_auto_displacement_fails_closed_when_current_truth_movement_gate_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            write_current_truth(
                temp_path / "docs" / "recovery" / "current-truth.json",
                movement_gate={
                    "allowed": False,
                    "status": "blocked-live-input-spin-incident",
                    "automationMovementPaused": True,
                    "liveInputIncident": {"status": "agent-live-movement-paused-after-spin-incident"},
                },
                client_geometry={"requiredClientWidth": 640, "requiredClientHeight": 360},
            )
            scan_plan = (
                temp_path
                / "scripts"
                / "captures"
                / "memory-region-inventory-currentpid-79184-test"
                / "scan-plan.json"
            )
            scan_plan.parent.mkdir(parents=True, exist_ok=True)
            scan_plan.write_text(
                json.dumps(
                    {
                        "ranges": [
                            {
                                "rank": 1,
                                "minAddressHex": "0x900000",
                                "maxAddressHex": "0xA00000",
                                "spanMiB": 1.0,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out = temp_path / "sequence"
            import sys

            original_argv = sys.argv
            original_run_command = sequence.run_command
            try:
                sys.argv = [
                    "current_pid_family_snapshot_sequence.py",
                    "--repo-root",
                    str(temp_path),
                    "--output-root",
                    str(out),
                    "--auto-displacement-key",
                    "W",
                    "--json",
                ]
                sequence.run_command = lambda *args, **kwargs: self.fail("run_command should not be called")  # type: ignore[assignment]
                with redirect_stdout(StringIO()):
                    code = sequence.main()
            finally:
                sequence.run_command = original_run_command
                sys.argv = original_argv

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "blocked")
            self.assertFalse(summary["safety"]["movementSent"])
            self.assertFalse(summary["safety"]["inputSent"])
            self.assertIn("current-truth-movement-gate-blocked:blocked-live-input-spin-incident", summary["blockers"])
            self.assertEqual(json.loads((out / "command-envelopes.json").read_text(encoding="utf-8")), [])

    def test_auto_displacement_blocks_retired_window_message_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            write_current_truth(
                temp_path / "docs" / "recovery" / "current-truth.json",
                movement_gate={"allowed": True, "status": "operator-cleared"},
                client_geometry={"requiredClientWidth": 640, "requiredClientHeight": 360},
            )
            scan_plan = (
                temp_path
                / "scripts"
                / "captures"
                / "memory-region-inventory-currentpid-79184-test"
                / "scan-plan.json"
            )
            scan_plan.parent.mkdir(parents=True, exist_ok=True)
            scan_plan.write_text(
                json.dumps(
                    {
                        "ranges": [
                            {
                                "rank": 1,
                                "minAddressHex": "0x900000",
                                "maxAddressHex": "0xA00000",
                                "spanMiB": 1.0,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out = temp_path / "sequence"
            import sys

            original_argv = sys.argv
            original_run_command = sequence.run_command
            try:
                sys.argv = [
                    "current_pid_family_snapshot_sequence.py",
                    "--repo-root",
                    str(temp_path),
                    "--output-root",
                    str(out),
                    "--auto-displacement-key",
                    "W",
                    "--auto-displacement-input-backend",
                    "window-message",
                    "--json",
                ]
                sequence.run_command = lambda *args, **kwargs: self.fail("run_command should not be called")  # type: ignore[assignment]
                with redirect_stdout(StringIO()):
                    code = sequence.main()
            finally:
                sequence.run_command = original_run_command
                sys.argv = original_argv

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "blocked")
            self.assertFalse(summary["safety"]["movementSent"])
            self.assertFalse(summary["safety"]["inputSent"])
            self.assertIn("auto-displacement-window-message-backend-retired-use-csharp-scancode", summary["blockers"])
            self.assertIn("--auto-displacement-input-backend csharp-scancode", summary["next"]["recommendedAction"])
            self.assertEqual(json.loads((out / "command-envelopes.json").read_text(encoding="utf-8")), [])

    def test_auto_displacement_uses_exact_hwnd_csharp_scancode_backend(self) -> None:
        captured = {}

        def fake_run_command(command, cwd, timeout_seconds):  # noqa: ANN001
            captured["command"] = command
            captured["timeout_seconds"] = timeout_seconds
            return {"exitCode": 0, "timedOut": False, "stdout": "ok", "stderr": ""}

        original = sequence.run_command
        try:
            sequence.run_command = fake_run_command
            ok, envelope = sequence.run_auto_displacement(
                Path("C:/repo"),
                args(
                    pid=1234,
                    hwnd="0xABC",
                    auto_displacement_key="w",
                    auto_displacement_hold_ms=750,
                    auto_displacement_timeout_seconds=9,
                ),
            )
        finally:
            sequence.run_command = original

        self.assertTrue(ok)
        self.assertEqual(envelope["exitCode"], 0)
        command = captured["command"]
        self.assertIn("send-rift-key-csharp.ps1", " ".join(command))
        self.assertIn("--pid", command)
        self.assertIn("1234", command)
        self.assertIn("--hwnd", command)
        self.assertIn("0xABC", command)
        self.assertIn("--input-mode", command)
        self.assertIn("ScanCode", command)
        self.assertIn("--json", command)

    def test_emergency_key_release_guard_uses_exact_target_and_output_root(self) -> None:
        captured = {}

        def fake_run_command(command, cwd, timeout_seconds):  # noqa: ANN001
            captured["command"] = command
            captured["timeout_seconds"] = timeout_seconds
            return {"exitCode": 0, "timedOut": False, "stdout": "{}", "stderr": ""}

        original = sequence.run_command
        try:
            sequence.run_command = fake_run_command
            ok, envelope = sequence.run_emergency_key_release(
                Path("C:/repo"),
                args(
                    pid=1234,
                    hwnd="0xABC",
                    process_name="rift_x64",
                    auto_displacement_timeout_seconds=9,
                ),
                Path("C:/repo/scripts/captures/run"),
                stage="pre-auto-displacement",
            )
        finally:
            sequence.run_command = original

        self.assertTrue(ok)
        self.assertEqual(envelope["emergencyReleaseStage"], "pre-auto-displacement")
        command = captured["command"]
        self.assertIn("rift_emergency_key_release.py", " ".join(command))
        self.assertIn("--pid", command)
        self.assertIn("1234", command)
        self.assertIn("--hwnd", command)
        self.assertIn("0xABC", command)
        self.assertIn("--process-name", command)
        self.assertIn("rift_x64", command)
        self.assertIn("--include-mouse-buttons", command)
        self.assertIn("--output-root", command)
        self.assertTrue(any("emergency-key-release" in item for item in command))

    def test_required_client_geometry_blocks_mismatch_before_input(self) -> None:
        original = sequence.inspect_client_geometry
        try:
            sequence.inspect_client_geometry = lambda hwnd: {  # type: ignore[assignment]
                "hwnd": hwnd,
                "left": 0,
                "top": 0,
                "right": 800,
                "bottom": 600,
                "width": 800,
                "height": 600,
            }
            blockers, geometry = sequence.required_client_geometry_blockers(
                args(hwnd="0xABC", require_client_width=640, require_client_height=360)
            )
        finally:
            sequence.inspect_client_geometry = original

        self.assertEqual(blockers, ["client-width-mismatch:800!=640", "client-height-mismatch:600!=360"])
        self.assertEqual(geometry["actual"]["width"], 800)

    def test_rrapicoord_reference_uses_robust_capture_helper(self) -> None:
        captured = {}
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            reference = temp_path / "rift-api-reference-currentpid-1234.json"
            reference.write_text(
                json.dumps(
                    {
                        "source": "rrapicoord1-memory-scan",
                        "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0, "capturedAtUtc": "2026-05-13T01:00:00Z"},
                        "processId": 1234,
                        "targetWindowHandle": "0xABC",
                    }
                ),
                encoding="utf-8",
            )

            def fake_run_command(command, cwd, timeout_seconds):  # noqa: ANN001
                captured["command"] = command
                captured["timeout_seconds"] = timeout_seconds
                return {
                    "exitCode": 0,
                    "timedOut": False,
                    "stdout": json.dumps({"Status": "captured", "ReferenceFile": str(reference)}),
                    "stderr": "",
                }

            original = sequence.run_command
            try:
                sequence.run_command = fake_run_command
                loaded, reference_path, envelope = sequence.capture_rrapicoord_reference(
                    Path("C:/repo"),
                    args(
                        pid=1234,
                        hwnd="0xABC",
                        reference_scan_context_bytes=4096,
                        reference_max_hits=512,
                        reference_scan_attempts=5,
                        reference_scan_retry_delay_milliseconds=1500,
                        reference_tolerance=0.25,
                        reference_timeout_seconds=45,
                    ),
                    temp_path,
                )
            finally:
                sequence.run_command = original

            self.assertEqual(reference_path, reference.resolve())
            self.assertEqual(loaded["source"], "rrapicoord1-memory-scan")
            self.assertEqual(envelope["exitCode"], 0)
            command = captured["command"]
            self.assertIn("capture-rift-api-reference-coordinate.ps1", " ".join(command))
            self.assertIn("-ProcessId", command)
            self.assertIn("1234", command)
            self.assertIn("-TargetWindowHandle", command)
            self.assertIn("0xABC", command)
            self.assertIn("-ScanContextBytes", command)
            self.assertIn("4096", command)
            self.assertIn("-MaxHits", command)
            self.assertIn("512", command)
            self.assertIn("-ScanAttempts", command)
            self.assertIn("5", command)
            self.assertIn("-ScanRetryDelayMilliseconds", command)
            self.assertIn("1500", command)
            self.assertIn("-Json", command)

    def test_rrapicoord_reference_failure_preserves_command_envelope(self) -> None:
        captured = {}

        def fake_run_command(command, cwd, timeout_seconds):  # noqa: ANN001
            captured["command"] = command
            return {
                "args": command,
                "cwd": str(cwd),
                "exitCode": None,
                "timedOut": True,
                "stdout": "",
                "stderr": "",
            }

        original = sequence.run_command
        try:
            sequence.run_command = fake_run_command
            with self.assertRaises(sequence.CommandEnvelopeError) as context:
                sequence.capture_rrapicoord_reference(
                    Path("C:/repo"),
                    args(
                        pid=1234,
                        hwnd="0xABC",
                        reference_scan_context_bytes=4096,
                        reference_max_hits=512,
                        reference_scan_attempts=5,
                        reference_scan_retry_delay_milliseconds=1500,
                        reference_tolerance=0.25,
                        reference_timeout_seconds=45,
                    ),
                    Path("C:/out"),
                )
        finally:
            sequence.run_command = original

        self.assertIn("reference_capture_failed: source=rrapicoord", str(context.exception))
        self.assertTrue(context.exception.envelope["timedOut"])
        self.assertEqual(context.exception.envelope["args"], captured["command"])
        compact = sequence.compact_envelope(context.exception.envelope, "reference:baseline")
        self.assertEqual(compact["stage"], "reference:baseline")
        self.assertIn("capture-rift-api-reference-coordinate.ps1", " ".join(compact["args"]))


if __name__ == "__main__":
    unittest.main()
