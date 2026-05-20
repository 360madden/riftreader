from __future__ import annotations

import base64
import contextlib
import io
import json
import subprocess
from datetime import datetime, timezone
from types import SimpleNamespace
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rift_live_test.baselines import (
    record_baseline_summary,
    select_baselines_for_fresh_summary,
)
from rift_live_test.commands import JsonCommandResult, extract_first_json, run_json_command
from rift_live_test.gui import (
    demo_progress_payload,
    format_child_command,
    format_elapsed,
    format_coord,
    format_delta,
    format_issues,
    format_latest_state,
    format_progress_age,
    format_progress_contract,
    format_proof_budget,
    format_recorder,
    format_run_health,
    format_run_gates,
    format_safety,
    format_summary_file,
    format_inspect_json,
    format_inspect_summary,
    format_api_status,
    format_copy_paths,
    format_current_target,
    format_epoch_warning,
    format_proof_epoch,
    inspect_latest_progress,
    inspect_progress_file,
    indicator_light_states,
    issue_severity,
    main as gui_main,
    progress_health,
    profile_gui_poll_milliseconds,
    resolve_progress_file_arg,
    format_riftscan_status,
    validate_progress_contract,
    resolve_latest_run,
    start_progress_gui,
    status_color,
    write_demo_progress,
)
from rift_live_test.profiles import load_profile
import rift_live_test.reports as reports
from rift_live_test.reports import write_json, write_markdown_summary
from rift_live_test.runner import LiveTestRunner, classify_run_health
from rift_live_test.status import (
    BLOCKED_LIVE_FLAG_REQUIRED,
    BLOCKED_PROMOTION_REFERENCE_MISMATCH,
    BLOCKED_REFERENCE_CAPTURE,
    BLOCKED_TARGET_DRIFT,
    BLOCKED_TARGET_MISMATCH,
    INPUT_NO_MOVEMENT,
)
from rift_live_test.target import verify_target


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def testdata_path(name: str) -> Path:
    return Path(__file__).resolve().parent / "rift_live_test" / "testdata" / name


def datetime_from_text(value: str) -> datetime:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class LiveTestOrchestratorTests(unittest.TestCase):
    @staticmethod
    def _write_pose_summary(
        path: Path,
        *,
        process_id: int = 123,
        hwnd: str = "0x123",
        x: float = 1.0,
        y: float = 2.0,
        z: float = 3.0,
        candidate_id: str = "rift-addon-coordinate-candidate-000001",
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "GeneratedAtUtc": "2026-05-07T00:00:00+00:00",
                    "ProcessName": "rift_x64",
                    "ProcessId": process_id,
                    "TargetWindowHandle": hwnd,
                    "NoCheatEngine": True,
                    "MovementSent": False,
                    "ReferenceCoordinate": {"X": x, "Y": y, "Z": z},
                    "BestReferenceMatches": [
                        {
                            "CandidateId": candidate_id,
                            "ReferenceMatchesReadback": True,
                            "StableAcrossReadbackSamples": True,
                            "FirstDecodedSample": {"X": x, "Y": y, "Z": z},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_extract_first_json_skips_noise(self) -> None:
        payload, text = extract_first_json('warning before\n{"Status":"valid"}\ntrailing')
        self.assertEqual(payload["Status"], "valid")
        self.assertEqual(text, '{"Status":"valid"}')

    def test_gui_formatters_are_compact(self) -> None:
        self.assertEqual(status_color("passed"), "ok")
        self.assertEqual(status_color("blocked-reference-capture"), "bad")
        self.assertIn(
            "X=1.235",
            format_coord(
                {
                    "x": 1.23456,
                    "y": 2.0,
                    "z": 3.0,
                    "recordedAtUtc": "2026-05-07T16:38:15.4855135Z",
                }
            ),
        )
        self.assertIn(
            "planar=0.226",
            format_delta(
                {
                    "deltaX": 0.05,
                    "deltaY": 0.0,
                    "deltaZ": -0.22,
                    "planarDistance": 0.2259,
                }
            ),
        )
        payload = demo_progress_payload(
            run_dir=Path("C:/demo/run"),
            progress_file=Path("C:/demo/run/run-progress.json"),
        )
        self.assertEqual(format_latest_state(payload["states"]), "live-input: passed")
        self.assertEqual(format_recorder(payload["coordinateRecordings"]), "1 pulse(s), 9 sample(s)")
        self.assertEqual(format_elapsed(payload), "28m 48s")
        self.assertEqual(
            format_child_command(payload["latestChildCommand"]),
            "live-input: completed (exit=0, json=passed, 0.4s)",
        )
        self.assertEqual(
            format_run_gates(payload["runGates"]),
            "live-input • exact target • live flag",
        )
        self.assertIn("anchor≤60s", format_proof_budget(payload["runGates"]))
        self.assertIn("no CE", format_safety(payload))
        self.assertIn("pending", format_summary_file(payload))
        self.assertEqual(
            format_progress_contract(payload, Path("C:/demo/run/run-progress.json")),
            "valid",
        )
        lights = indicator_light_states(payload, progress_file=Path("C:/demo/run/run-progress.json"))
        self.assertEqual(lights["progress"], "bad")
        self.assertEqual(lights["contract"], "ok")
        self.assertEqual(lights["epoch"], "warn")
        self.assertEqual(lights["safety"], "ok")
        self.assertIn("pid=47560", format_current_target(payload))
        self.assertIn("pending", format_epoch_warning(payload))
        self.assertIn("candidate", format_proof_epoch(payload))
        self.assertIn("chromalink-riftreader-world-state", format_api_status(payload))
        self.assertIn("allow-read-only-proof", format_riftscan_status(payload))
        self.assertIn(
            "run=",
            format_copy_paths(
                payload,
                run_dir=Path("C:/demo/run"),
                progress_file=Path("C:/demo/run/run-progress.json"),
            ),
        )
        proof_running_payload = json.loads(json.dumps(payload))
        for state in proof_running_payload["states"]:
            if state.get("state") == "proof-refresh":
                state["status"] = "running"
        self.assertEqual(
            indicator_light_states(
                proof_running_payload,
                progress_file=Path("C:/demo/run/run-progress.json"),
            )["proof"],
            "warn",
        )
        proof_failed_payload = json.loads(json.dumps(payload))
        for state in proof_failed_payload["states"]:
            if state.get("state") == "proof-refresh":
                state["status"] = "failed"
        self.assertEqual(
            indicator_light_states(
                proof_failed_payload,
                progress_file=Path("C:/demo/run/run-progress.json"),
            )["proof"],
            "bad",
        )
        self.assertEqual(
            format_riftscan_status({"runGates": {"candidateIdSource": "current-proof-pointer"}}),
            "not recorded",
        )
        self.assertIn(
            "coordinate invalid",
            format_api_status(
                {
                    "apiReference": {
                        "source": "chromalink-riftreader-world-state",
                        "status": "fresh",
                        "coordinate": {"x": "not-a-number", "y": 2.0, "z": 3.0},
                    }
                }
            ),
        )
        passed_payload = demo_progress_payload(
            run_dir=Path("C:/demo/run"),
            progress_file=Path("C:/demo/run/run-progress.json"),
            scenario="passed",
        )
        self.assertEqual(
            indicator_light_states(
                passed_payload,
                progress_file=Path("C:/demo/run/run-progress.json"),
            )["epoch"],
            "ok",
        )
        health = progress_health(payload, now=datetime_from_text("2026-05-07T17:05:01Z"))
        self.assertEqual(health["state"], "running")
        self.assertEqual(health["latestChildStatus"], "completed")
        self.assertTrue(health["latestChildOk"])
        self.assertIn("child=completed:ok", format_run_health({"runHealth": health}))
        self.assertEqual(issue_severity("target_window_handle_invalid:not-a-hwnd"), "error")
        self.assertEqual(issue_severity("proof_anchor_remaining_age_budget_too_low"), "warn")
        self.assertIn("ERROR • blocked-reference-capture", format_issues(["blocked-reference-capture"]))
        self.assertEqual(
            format_progress_age(
                payload,
                now=datetime_from_text("2026-05-07T17:06:05Z"),
            ),
            "stale: 1m 05s since update",
        )

    def test_write_json_overwrites_atomically_with_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "nested" / "artifact.json"
            write_json(path, {"status": "old"})
            write_json(path, {"status": "new", "count": 2})

            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["status"], "new")
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_write_json_retries_atomic_replace_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "artifact.json"
            real_replace = reports.os.replace
            calls = 0

            def flaky_replace(source: Path, destination: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise PermissionError("transient reader lock")
                real_replace(source, destination)

            with patch("rift_live_test.reports.os.replace", side_effect=flaky_replace), patch(
                "rift_live_test.reports.time.sleep"
            ) as sleep:
                write_json(path, {"status": "new"})

            self.assertEqual(calls, 2)
            sleep.assert_called_once()
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["status"], "new")

    def test_markdown_summary_includes_run_health(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "run-summary.md"
            write_markdown_summary(
                path,
                {
                    "profileName": "ProofOnly",
                    "status": "blocked-target-mismatch",
                    "ok": False,
                    "generatedAtUtc": "2026-05-07T00:00:00Z",
                    "runDirectory": str(Path(temp)),
                    "live": False,
                    "movementSent": False,
                    "runHealth": {
                        "state": "blocked",
                        "issueCount": 1,
                        "primaryIssue": "target_window_handle_invalid:not-a-hwnd",
                        "movementSent": False,
                        "movementAttempted": False,
                        "finalSummaryWritten": True,
                        "noCheatEngine": True,
                        "savedVariablesUsedAsLiveTruth": False,
                    },
                    "currentProofPointerUpdate": {
                        "updated": True,
                        "path": str(Path(temp) / "docs" / "recovery" / "current-proof-anchor-readback.json"),
                        "archivedSupersededPointer": {
                            "path": str(
                                Path(temp)
                                / "docs"
                                / "recovery"
                                / "historical"
                                / "old-pointer.json"
                            )
                        },
                    },
                    "states": [],
                },
            )

            text = path.read_text(encoding="utf-8")
            self.assertIn("## Run health", text)
            self.assertIn("| State | `blocked` |", text)
            self.assertIn("target_window_handle_invalid:not-a-hwnd", text)
            self.assertIn("## Current proof pointer update", text)
            self.assertIn("| Updated | `true` |", text)
            self.assertIn("old-pointer.json", text)

    def test_run_json_command_timeout_returns_artifact_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with patch("rift_live_test.commands.subprocess.run") as run:
                run.side_effect = TimeoutError("wrong timeout type")
                with self.assertRaises(TimeoutError):
                    run_json_command(["demo"], cwd=Path(temp), label="demo", timeout_seconds=1)

            with patch("rift_live_test.commands.subprocess.run") as run:
                run.side_effect = subprocess.TimeoutExpired(
                    cmd=["demo"],
                    timeout=1,
                    output=b"partial stdout",
                    stderr=b"partial stderr",
                )
                result = run_json_command(["demo"], cwd=Path(temp), label="demo", timeout_seconds=1)

            self.assertEqual(result.exit_code, 124)
            self.assertFalse(result.ok)
            self.assertIn("partial stdout", result.stdout)
            self.assertIn("partial stderr", result.stderr)
            self.assertIn("timed out", result.parse_error)

    def test_verify_target_rejects_invalid_hwnd_without_win32_calls(self) -> None:
        with patch("rift_live_test.target.os.name", "nt"), patch(
            "rift_live_test.target.ctypes.WinDLL",
            create=True,
        ) as windll:
            result = verify_target(123, "not-a-hwnd")

        windll.assert_not_called()
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "invalid-hwnd")
        self.assertIn("target_window_handle_invalid:not-a-hwnd", result["issues"])

    def test_run_health_classifies_statuses(self) -> None:
        self.assertEqual(classify_run_health("passed"), "ok")
        self.assertEqual(classify_run_health("running"), "running")
        self.assertEqual(classify_run_health("partial-series-stopped"), "warning")
        self.assertEqual(classify_run_health("blocked-target-mismatch"), "blocked")
        self.assertEqual(classify_run_health("input-no-movement"), "failed")
        self.assertEqual(classify_run_health("failed-internal-error"), "failed")

    def test_gui_launch_can_be_disabled_by_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            info = start_progress_gui(
                repo_root=root,
                progress_file=root / "run-progress.json",
                run_dir=root,
                profile_name="ProofOnly",
                profile={"showGui": False},
            )
            self.assertFalse(info["enabled"])
            self.assertEqual(info["reason"], "profile_showGui_false")

    def test_gui_launch_uses_subprocess_argument_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / "scripts" / "live_test_gui.py"
            script.parent.mkdir(parents=True)
            script.write_text("# placeholder\n", encoding="utf-8")
            with patch("rift_live_test.gui.subprocess.Popen") as popen:
                popen.return_value = SimpleNamespace(pid=456)
                info = start_progress_gui(
                    repo_root=root,
                    progress_file=root / "run-progress.json",
                    run_dir=root,
                    profile_name="Forward250",
                    profile={"showGui": True, "guiPollMilliseconds": 750},
                )

            self.assertTrue(info["enabled"])
            self.assertEqual(info["processId"], 456)
            args = popen.call_args.args[0]
            self.assertIsInstance(args, list)
            self.assertIn("--progress-file", args)
            self.assertIn("--poll-ms", args)
            self.assertEqual(args[args.index("--poll-ms") + 1], "750")

    def test_gui_poll_interval_is_clamped_and_fails_safe(self) -> None:
        self.assertEqual(profile_gui_poll_milliseconds({"guiPollMilliseconds": 100}), 250)
        self.assertEqual(profile_gui_poll_milliseconds({"guiPollMilliseconds": "bad"}), 500)

    def test_gui_launch_failure_is_reported_not_raised(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / "scripts" / "live_test_gui.py"
            script.parent.mkdir(parents=True)
            script.write_text("# placeholder\n", encoding="utf-8")
            with patch("rift_live_test.gui.subprocess.Popen", side_effect=OSError("no gui")):
                info = start_progress_gui(
                    repo_root=root,
                    progress_file=root / "run-progress.json",
                    run_dir=root,
                    profile_name="Forward250",
                    profile={"showGui": True},
                )

            self.assertFalse(info["enabled"])
            self.assertTrue(info["requested"])
            self.assertIn("OSError:no gui", info["error"])

    def test_latest_ok_cmd_launcher_is_dumb_wrapper(self) -> None:
        launcher = repo_root() / "cmd" / "live-gui-inspect-latest-ok.cmd"
        text = launcher.read_text(encoding="utf-8").replace("\r\n", "\n")

        self.assertEqual(
            text,
            '@echo off\n'
            'cd /d "C:\\RIFT MODDING\\RiftReader"\n'
            "python scripts\\live_test_gui.py --latest --inspect-progress "
            "--fail-on-warning --require-ok-run %*\n",
        )

    def test_gui_demo_progress_is_offline_and_informational(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            progress = root / "run-progress.json"
            payload = write_demo_progress(progress_file=progress, run_dir=root)

            self.assertTrue(progress.exists())
            self.assertEqual(payload["profileName"], "GuiDemo")
            self.assertIn("runHealth", payload)
            self.assertTrue(payload["noCheatEngine"])
            self.assertFalse(payload["savedVariablesUsedAsLiveTruth"])
            self.assertTrue(payload["coordinateRecordings"])
            loaded = json.loads(progress.read_text(encoding="utf-8"))
            self.assertEqual(loaded["status"], "running")

    def test_gui_demo_blocked_scenario_is_offline_and_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = write_demo_progress(
                progress_file=root / "run-progress.json",
                run_dir=root,
                scenario="blocked",
            )

            self.assertEqual(payload["status"], "blocked-target-mismatch")
            self.assertFalse(payload["live"])
            self.assertFalse(payload["movementSent"])
            self.assertEqual(payload["coordinateRecordings"], [])
            self.assertIn("target_window_handle_invalid:not-a-hwnd", payload["issues"])

    def test_gui_demo_reference_and_proof_blocked_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reference = write_demo_progress(
                progress_file=root / "reference" / "run-progress.json",
                run_dir=root / "reference",
                scenario="blocked-reference",
            )
            proof = write_demo_progress(
                progress_file=root / "proof" / "run-progress.json",
                run_dir=root / "proof",
                scenario="blocked-proof",
            )

            self.assertEqual(reference["status"], "blocked-reference-capture")
            self.assertFalse(reference["movementSent"])
            self.assertIn("parseError", reference["latestChildCommand"])
            self.assertEqual(proof["status"], "blocked-proof-expired")
            self.assertFalse(proof["movementSent"])
            self.assertEqual(proof["latestChildCommand"]["jsonStatus"], "blocked-preflight-proof-expired")

    def test_gui_demo_cli_can_write_without_opening_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            code = gui_main(
                [
                    "--demo",
                    "--write-demo-only",
                    "--demo-scenario",
                    "blocked",
                    "--demo-output-root",
                    str(root),
                    "--profile-name",
                    "DemoProfile",
                ]
            )

            progress = root / "run-progress.json"
            self.assertEqual(code, 0)
            self.assertTrue(progress.exists())
            payload = json.loads(progress.read_text(encoding="utf-8"))
            self.assertEqual(payload["profileName"], "DemoProfile")
            self.assertEqual(payload["status"], "blocked-target-mismatch")

    def test_gui_demo_cli_can_smoke_render_without_mainloop(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = io.StringIO()
            with patch(
                "rift_live_test.gui.smoke_render_hud",
                return_value={
                    "status": "smoke-render-passed",
                    "ok": True,
                    "progressFile": str(Path(temp) / "run-progress.json"),
                },
            ) as smoke, contextlib.redirect_stdout(out):
                code = gui_main(
                    [
                        "--demo",
                        "--demo-output-root",
                        temp,
                        "--smoke-render",
                        "--compact-json",
                    ]
                )

            self.assertEqual(code, 0)
            smoke.assert_called_once()
            self.assertEqual(json.loads(out.getvalue())["status"], "smoke-render-passed")

    def test_gui_demo_payload_uses_requested_paths(self) -> None:
        run_dir = Path("C:/demo/run")
        progress_file = run_dir / "progress.json"
        payload = demo_progress_payload(
            run_dir=run_dir,
            progress_file=progress_file,
            profile_name="Preview",
        )

        self.assertEqual(payload["profileName"], "Preview")
        self.assertEqual(payload["runProgressFile"], str(progress_file))
        self.assertIn("recorder", payload["coordinateSamplesFile"])

    def test_inspect_progress_reports_health_without_gui(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            progress = root / "run-progress.json"
            write_demo_progress(progress_file=progress, run_dir=root, scenario="blocked-reference")

            result = inspect_progress_file(progress)

            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "progress-valid")
            self.assertEqual(result["runStatus"], "blocked-reference-capture")
            self.assertEqual(result["runHealth"]["state"], "blocked")
            self.assertEqual(result["contract"]["status"], "valid")
            self.assertFalse(result["runSummaryFileExists"])
            self.assertEqual(result["issueCount"], 2)

    def test_inspect_progress_reports_malformed_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            progress = Path(temp) / "run-progress.json"
            progress.write_text("{bad json", encoding="utf-8")

            result = inspect_progress_file(progress)

            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "progress-unreadable")

    def test_inspect_progress_reports_contract_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            progress = Path(temp) / "run-progress.json"
            write_json(
                progress,
                {
                    "schemaVersion": 1,
                    "mode": "rift-live-test-progress",
                    "profileName": "BadProgress",
                    "status": "running",
                    "updatedAtUtc": "2026-05-07T00:00:00Z",
                    "runDirectory": str(Path(temp)),
                    "runProgressFile": str(progress),
                    "noCheatEngine": False,
                    "savedVariablesUsedAsLiveTruth": True,
                    "issues": [],
                    "states": [],
                    "runHealth": {},
                    "runGates": {},
                },
            )

            result = inspect_progress_file(progress)

            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "progress-valid")
            self.assertEqual(result["contract"]["status"], "invalid")
            self.assertIn("safety_no_cheat_engine_not_true", result["contract"]["issues"])

    def test_validate_progress_contract_allows_missing_new_health_as_warning(self) -> None:
        payload = demo_progress_payload(run_dir=Path("C:/demo/run"), progress_file=Path("C:/demo/run/progress.json"))
        payload.pop("runHealth")

        contract = validate_progress_contract(payload)

        self.assertTrue(contract["ok"])
        self.assertEqual(contract["status"], "warning")
        self.assertIn("runHealth_missing", contract["issues"])

    def test_inspect_progress_cli_exits_without_opening_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            progress = Path(temp) / "run-progress.json"
            write_demo_progress(progress_file=progress, run_dir=Path(temp), scenario="blocked-proof")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = gui_main(["--inspect-progress", "--progress-file", str(progress)])

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "progress-valid")
            self.assertEqual(payload["runHealth"]["state"], "blocked")

    def test_inspect_progress_cli_compact_json_outputs_single_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            progress = Path(temp) / "run-progress.json"
            write_demo_progress(progress_file=progress, run_dir=Path(temp), scenario="blocked-proof")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = gui_main(
                    [
                        "--inspect-progress",
                        "--progress-file",
                        str(progress),
                        "--compact-json",
                    ]
                )

            text = stdout.getvalue()
            payload = json.loads(text)
            self.assertEqual(code, 0)
            self.assertEqual(text.count("\n"), 1)
            self.assertNotIn("\n  ", text)
            self.assertEqual(payload["runHealth"]["state"], "blocked")

    def test_format_inspect_json_supports_pretty_and_compact(self) -> None:
        payload = {"status": "progress-valid", "ok": True}

        self.assertIn("\n  ", format_inspect_json(payload))
        self.assertEqual(
            format_inspect_json(payload, compact=True),
            '{"status":"progress-valid","ok":true}',
        )

    def test_format_inspect_summary_is_human_readable(self) -> None:
        result = inspect_progress_file(testdata_path("progress-blocked-reference.json"))

        text = format_inspect_summary(result)

        self.assertIn("RiftReader live-test inspect summary", text)
        self.assertIn("Run status: blocked-reference-capture", text)
        self.assertIn("Run health: blocked", text)
        self.assertIn("Contract: valid", text)

    def test_inspect_progress_cli_summary_outputs_text(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = gui_main(
                [
                    "--inspect-progress",
                    "--progress-file",
                    str(testdata_path("progress-blocked-reference.json")),
                    "--summary",
                ]
            )

        text = stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("Run status: blocked-reference-capture", text)
        self.assertIn("Run health: blocked", text)
        self.assertNotIn('"runHealth"', text)

    def test_inspect_progress_cli_accepts_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_demo_progress(progress_file=root / "run-progress.json", run_dir=root, scenario="blocked")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = gui_main(["--inspect-progress", "--run-directory", str(root)])

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["runStatus"], "blocked-target-mismatch")

    def test_inspect_progress_cli_fail_on_warning_keeps_clean_contract_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_demo_progress(
                progress_file=root / "run-progress.json",
                run_dir=root,
                scenario="blocked-reference",
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = gui_main(
                    [
                        "--inspect-progress",
                        "--run-directory",
                        str(root),
                        "--fail-on-warning",
                    ]
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(payload["strict"]["ok"])
            self.assertEqual(payload["strict"]["warnings"], [])

    def test_inspect_progress_cli_require_ok_run_exits_nonzero_for_blocked_health(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_demo_progress(
                progress_file=root / "run-progress.json",
                run_dir=root,
                scenario="blocked-reference",
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = gui_main(
                    [
                        "--inspect-progress",
                        "--run-directory",
                        str(root),
                        "--require-ok-run",
                    ]
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(code, 1)
            self.assertFalse(payload["runGate"]["ok"])
            self.assertIn(
                "run_not_ok:state=blocked;status=blocked-reference-capture",
                payload["runGate"]["issues"],
            )

    def test_inspect_progress_cli_require_ok_run_passes_for_ok_health(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = gui_main(
                [
                    "--latest",
                    "--latest-pointer",
                    str(testdata_path("latest-pointer.json")),
                    "--inspect-progress",
                    "--require-ok-run",
                    "--compact-json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(payload["runGate"]["ok"])
        self.assertEqual(payload["runGate"]["issues"], [])

    def test_inspect_progress_cli_fail_on_warning_exits_nonzero_for_contract_warning(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = gui_main(
                [
                    "--inspect-progress",
                    "--progress-file",
                    str(testdata_path("progress-passed.json")),
                    "--fail-on-warning",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(payload["strict"]["ok"])
        self.assertIn(
            "contract:run_summary_marked_written_but_missing",
            payload["strict"]["warnings"],
        )

    def test_inspect_progress_cli_fail_on_warning_exits_nonzero_for_stale_progress(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = gui_main(
                [
                    "--inspect-progress",
                    "--progress-file",
                    str(testdata_path("progress-running.json")),
                    "--stale-after-seconds",
                    "1",
                    "--fail-on-warning",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 1)
        self.assertIn("run_health_state:stale", payload["strict"]["warnings"])

    def test_checked_in_progress_fixtures_validate(self) -> None:
        running = inspect_progress_file(
            testdata_path("progress-running.json"),
            now=datetime_from_text("2026-05-07T17:06:00Z"),
            stale_after_seconds=30,
        )
        passed = inspect_progress_file(testdata_path("progress-passed.json"))
        blocked = inspect_progress_file(testdata_path("progress-blocked-reference.json"))

        self.assertTrue(running["ok"])
        self.assertEqual(running["runHealth"]["state"], "stale")
        self.assertEqual(running["contract"]["status"], "valid")
        self.assertTrue(passed["ok"])
        self.assertEqual(passed["runHealth"]["state"], "ok")
        self.assertEqual(passed["contract"]["status"], "warning")
        self.assertIn(
            "run_summary_marked_written_but_missing",
            passed["contract"]["issues"],
        )
        self.assertFalse(passed["runSummaryFileExists"])
        self.assertTrue(blocked["ok"])
        self.assertEqual(blocked["runHealth"]["state"], "blocked")
        self.assertEqual(blocked["contract"]["status"], "valid")

    def test_checked_in_latest_pointer_fixture_resolves(self) -> None:
        latest = resolve_latest_run(
            repo_root=repo_root(),
            pointer_file=testdata_path("latest-pointer.json"),
        )

        self.assertEqual(latest["profileName"], "FixturePassed")
        self.assertTrue(latest["progressFileExists"])
        self.assertFalse(latest["runSummaryFileExists"])
        self.assertEqual(latest["status"], "passed")
        self.assertEqual(latest["runHealth"]["state"], "ok")
        self.assertTrue(latest["finalSummaryWritten"])
        self.assertEqual(latest["progressFile"], testdata_path("progress-passed.json"))

    def test_checked_in_latest_pointer_drift_fixture_reports_warning(self) -> None:
        latest = resolve_latest_run(
            repo_root=repo_root(),
            pointer_file=testdata_path("latest-pointer-drift.json"),
        )
        result = inspect_latest_progress(
            latest,
            now=datetime_from_text("2026-05-07T17:05:10Z"),
            stale_after_seconds=30,
        )

        freshness = result["latestPointer"]["freshness"]
        self.assertEqual(latest["profileName"], "FixtureDriftedLatest")
        self.assertTrue(latest["progressFileExists"])
        self.assertEqual(result["runHealth"]["state"], "running")
        self.assertEqual(freshness["status"], "warning")
        self.assertEqual(freshness["timestampGapSeconds"], 125)
        self.assertIn("latest_pointer_timestamp_drift_seconds:125", freshness["issues"])
        self.assertIn(
            "latest_pointer_status_mismatch:pointer=passed;progress=running",
            freshness["issues"],
        )
        self.assertIn(
            "latest_pointer_health_mismatch:pointer=ok;progress=running",
            freshness["issues"],
        )

    def test_latest_pointer_outside_repo_reports_freshness_warning(self) -> None:
        with tempfile.TemporaryDirectory() as repo_temp:
            with tempfile.TemporaryDirectory() as external_temp:
                root = Path(repo_temp)
                external_run = Path(external_temp) / "live-test-ProofOnly"
                progress_file = external_run / "run-progress.json"
                progress = write_demo_progress(
                    progress_file=progress_file,
                    run_dir=external_run,
                    scenario="passed",
                )
                pointer = root / "scripts" / "captures" / "latest-live-test-run.json"
                write_json(
                    pointer,
                    {
                        "runProgressFile": str(progress_file),
                        "runSummaryFile": str(external_run / "run-summary.json"),
                        "runDirectory": str(external_run),
                        "profileName": "ExternalFixture",
                        "status": progress["status"],
                        "runHealth": progress["runHealth"],
                        "generatedAtUtc": progress["updatedAtUtc"],
                        "finalSummaryWritten": progress["finalSummaryWritten"],
                    },
                )

                latest = resolve_latest_run(repo_root=root, pointer_file=pointer)
                result = inspect_latest_progress(latest)

        freshness = result["latestPointer"]["freshness"]
        self.assertFalse(latest["runDirectoryInsideRepo"])
        self.assertFalse(latest["progressFileInsideRepo"])
        self.assertEqual(freshness["status"], "warning")
        self.assertIn("latest_pointer_run_directory_outside_repo", freshness["issues"])
        self.assertIn("latest_pointer_progress_file_outside_repo", freshness["issues"])

    def test_latest_inspect_cli_includes_pointer_metadata(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = gui_main(
                [
                    "--latest",
                    "--latest-pointer",
                    str(testdata_path("latest-pointer.json")),
                    "--inspect-progress",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["runHealth"]["state"], "ok")
        self.assertEqual(payload["runHealth"]["latestChildStatus"], "completed")
        self.assertTrue(payload["runHealth"]["latestChildOk"])
        self.assertEqual(payload["latestPointer"]["status"], "passed")
        self.assertEqual(payload["latestPointer"]["freshness"]["status"], "ok")
        self.assertEqual(payload["latestPointer"]["freshness"]["timestampGapSeconds"], 0)
        self.assertEqual(payload["latestPointer"]["runHealth"]["state"], "ok")
        self.assertTrue(payload["latestPointer"]["progressFileExists"])
        self.assertFalse(payload["latestPointer"]["runSummaryFileExists"])

    def test_latest_inspect_cli_fail_on_warning_exits_nonzero_for_freshness_warning(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = gui_main(
                [
                    "--latest",
                    "--latest-pointer",
                    str(testdata_path("latest-pointer-drift.json")),
                    "--inspect-progress",
                    "--fail-on-warning",
                    "--compact-json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(payload["strict"]["ok"])
        self.assertTrue(
            any(
                warning.startswith("latest_pointer_freshness:latest_pointer_status_mismatch")
                for warning in payload["strict"]["warnings"]
            )
        )

    def test_latest_inspect_cli_summary_with_strict_warnings(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = gui_main(
                [
                    "--latest",
                    "--latest-pointer",
                    str(testdata_path("latest-pointer-drift.json")),
                    "--inspect-progress",
                    "--fail-on-warning",
                    "--summary",
                ]
            )

        text = stdout.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("Latest pointer freshness: warning", text)
        self.assertIn("Strict: failed", text)
        self.assertIn("latest_pointer_status_mismatch:pointer=passed;progress=running", text)

    def test_latest_inspect_cli_summary_with_require_ok_run_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_demo_progress(
                progress_file=root / "run-progress.json",
                run_dir=root,
                scenario="blocked",
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = gui_main(
                    [
                        "--inspect-progress",
                        "--run-directory",
                        str(root),
                        "--require-ok-run",
                        "--summary",
                    ]
                )

            text = stdout.getvalue()
            self.assertEqual(code, 1)
            self.assertIn("Run gate: failed", text)
            self.assertIn("run_not_ok:state=blocked;status=blocked-target-mismatch", text)

    def test_resolve_progress_file_arg_prefers_explicit_file(self) -> None:
        self.assertEqual(
            resolve_progress_file_arg("C:/explicit/progress.json", "C:/run"),
            Path("C:/explicit/progress.json"),
        )
        self.assertEqual(
            resolve_progress_file_arg(None, "C:/run"),
            Path("C:/run") / "run-progress.json",
        )

    def test_resolve_latest_run_uses_latest_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = root / "scripts" / "captures" / "latest-live-test-run.json"
            pointer.parent.mkdir(parents=True)
            pointer.write_text(
                json.dumps(
                    {
                        "runProgressFile": "scripts/captures/run-a/run-progress.json",
                        "runDirectory": "scripts/captures/run-a",
                        "profileName": "ProofOnly",
                    }
                ),
                encoding="utf-8",
            )

            latest = resolve_latest_run(repo_root=root)

            self.assertEqual(latest["profileName"], "ProofOnly")
            self.assertFalse(latest["progressFileExists"])
            self.assertEqual(
                latest["progressFile"],
                root / "scripts" / "captures" / "run-a" / "run-progress.json",
            )
            self.assertEqual(latest["runDirectory"], root / "scripts" / "captures" / "run-a")

    def test_latest_gui_main_reports_missing_pointer_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = gui_main(
                    [
                        "--latest",
                        "--latest-pointer",
                        str(Path(temp) / "missing-latest.json"),
                    ]
                )

            self.assertEqual(code, 2)
            self.assertIn("latest-run-unavailable", stderr.getvalue())

    def test_resolve_latest_run_rejects_malformed_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = root / "latest.json"
            pointer.write_text("[1, 2, 3]", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "root must be an object"):
                resolve_latest_run(repo_root=root, pointer_file=pointer)

    def test_profile_merges_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "profiles.json"
            (root / "old.json").write_text("{}", encoding="utf-8")
            config.write_text(
                json.dumps(
                    {
                        "defaults": {
                            "processName": "rift_x64",
                            "outputRoot": "captures",
                            "showGui": True,
                            "promotionReferenceReadbackSummary": "old.json",
                            "maxHoldMilliseconds": 1000,
                            "maxPulseCount": 3,
                        },
                        "profiles": {
                            "Forward250": {
                                "mode": "live-input",
                                "input": {
                                    "key": "w",
                                    "holdMilliseconds": 250,
                                    "pulseCount": 1,
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            profile = load_profile(root, config, "Forward250")
            self.assertEqual(profile["processName"], "rift_x64")
            self.assertEqual(profile["input"]["holdMilliseconds"], 250)
            self.assertTrue(Path(profile["outputRoot"]).is_absolute())

    def test_profile_rejects_live_flag_opt_out_for_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "profiles.json"
            (root / "old.json").write_text("{}", encoding="utf-8")
            config.write_text(
                json.dumps(
                    {
                        "defaults": {
                            "outputRoot": "captures",
                            "promotionReferenceReadbackSummary": "old.json",
                        },
                        "profiles": {
                            "UnsafeForward": {
                                "mode": "live-input",
                                "requireLiveFlagForInput": False,
                                "input": {
                                    "key": "w",
                                    "holdMilliseconds": 250,
                                    "pulseCount": 1,
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "cannot disable requireLiveFlagForInput"):
                load_profile(root, config, "UnsafeForward")

    def test_runner_prefers_current_pointer_candidate_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            pointer.parent.mkdir(parents=True)
            pointer.write_text(
                json.dumps(
                    {
                        "mode": "current-proof-anchor-readback-pointer",
                        "status": "current-target-proofonly-passed",
                        "target": {
                            "processId": 123,
                            "processName": "rift_x64",
                            "targetWindowHandle": "0x123",
                        },
                        "riftscanCandidateSource": {
                            "candidateId": "fresh-riftscan-candidate-000123",
                            "matchFile": "C:/Riftscan/reports/generated/fresh.json",
                        },
                    }
                ),
                encoding="utf-8",
            )
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile={
                    "mode": "proof-only",
                    "input": None,
                    "outputRoot": str(root / "captures"),
                    "candidateId": "stale-profile-candidate",
                    "candidateIdSource": "current-proof-pointer",
                },
                process_id=123,
                target_window_handle="0x123",
                live=False,
            )

            self.assertEqual(runner._candidate_id(), "fresh-riftscan-candidate-000123")
            self.assertEqual(runner._run_gates()["candidateId"], "fresh-riftscan-candidate-000123")

    def test_runner_rejects_stale_pointer_candidate_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            pointer.parent.mkdir(parents=True)
            pointer.write_text(
                json.dumps(
                    {
                        "mode": "current-proof-anchor-readback-pointer",
                        "target": {
                            "processId": 33912,
                            "processName": "rift_x64",
                            "targetWindowHandle": "0xE0DB2",
                        },
                        "riftscanCandidateSource": {
                            "candidateId": "stale-pointer-candidate",
                            "matchFile": "C:/Riftscan/reports/generated/old.json",
                        },
                    }
                ),
                encoding="utf-8",
            )
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile={
                    "mode": "proof-only",
                    "input": None,
                    "outputRoot": str(root / "captures"),
                    "candidateId": "profile-fallback-candidate",
                    "candidateIdSource": "current-proof-pointer",
                },
                process_id=49504,
                target_window_handle="0x5121A",
                live=False,
            )

            self.assertEqual(runner._candidate_id(), "profile-fallback-candidate")
            self.assertEqual(runner._run_gates()["candidateId"], "profile-fallback-candidate")

    def test_blocked_current_pointer_without_candidate_does_not_call_pose_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            pointer.parent.mkdir(parents=True)
            write_json(
                pointer,
                {
                    "mode": "current-proof-anchor-readback-pointer",
                    "status": BLOCKED_TARGET_DRIFT,
                    "target": {
                        "processId": 49504,
                        "processName": "rift_x64",
                        "targetWindowHandle": "0x5121A",
                    },
                    "currentTruthClassification": {
                        "classification": "stale-target-drift-blocker",
                        "movementAllowed": False,
                    },
                },
            )
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile={
                    "mode": "proof-only",
                    "input": None,
                    "outputRoot": str(root / "captures"),
                    "writeMarkdownSummary": False,
                },
                process_id=49504,
                target_window_handle="0x5121A",
                live=False,
            )

            def fake_run_ps1(label: str, script_name: str, args: list[str]):
                self.assertEqual(script_name, "capture-rift-api-reference-coordinate.ps1")
                output_file = Path(args[args.index("-OutputFile") + 1])
                write_json(
                    output_file,
                    {
                        "source": "rrapicoord1-memory-scan",
                        "captured_at_utc": "2026-05-08T22:00:00Z",
                        "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
                    },
                )
                return SimpleNamespace(exit_code=0, json_data={"Status": "captured"})

            with patch(
                "rift_live_test.runner.verify_target",
                return_value={"valid": True, "status": "valid", "targetWindowHandle": "0x5121A"},
            ), patch.object(runner, "_run_ps1", side_effect=fake_run_ps1) as run_ps1:
                summary = runner.run()

            self.assertEqual(summary["status"], BLOCKED_TARGET_DRIFT)
            self.assertIn(
                "target_drift:current_proof_pointer_has_no_current_candidate:"
                "status=blocked-target-drift;candidateId=False;matchFile=False",
                summary["issues"],
            )
            self.assertEqual(run_ps1.call_count, 1)
            self.assertFalse(summary["movementSent"])

    def test_current_proof_anchor_wins_over_stale_pointer_for_candidate_seed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            pointer.parent.mkdir(parents=True)
            write_json(
                pointer,
                {
                    "mode": "current-proof-anchor-readback-pointer",
                    "target": {
                        "processId": 33912,
                        "processName": "rift_x64",
                        "targetWindowHandle": "0xE0DB2",
                    },
                    "riftscanCandidateSource": {
                        "candidateId": "old-pointer-candidate",
                        "matchFile": "C:/Riftscan/reports/generated/old.json",
                    },
                },
            )
            candidate_file = root / "current-candidates.json"
            write_json(
                candidate_file,
                {
                    "candidates": [
                        {
                            "candidate_id": "current-anchor-candidate",
                            "source_base_address_hex": "0x20000000",
                            "source_offset_hex": "0x100",
                        }
                    ]
                },
            )
            readback_summary = root / "current-readback-summary.json"
            write_json(readback_summary, {"SourceCandidateFile": str(candidate_file)})
            proof_anchor = root / "scripts" / "captures" / "telemetry-proof-coord-anchor.json"
            proof_anchor.parent.mkdir(parents=True)
            write_json(
                proof_anchor,
                {
                    "Mode": "proof-coord-anchor",
                    "ProcessName": "rift_x64",
                    "ProcessId": 49504,
                    "TargetWindowHandle": "0x5121A",
                    "ObjectBaseAddress": "0x20000100",
                    "Evidence": {
                        "CandidateId": "current-anchor-candidate",
                        "CandidateAddressHex": "0x20000100",
                        "PoseCount": 2,
                        "ReadbackSummaryFiles": [str(readback_summary)],
                    },
                },
            )
            stale_pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            write_json(
                stale_pointer,
                {
                    "mode": "current-proof-anchor-readback-pointer",
                    "target": {
                        "processName": "rift_x64",
                        "processId": 33912,
                        "targetWindowHandle": "0xE0DB2",
                    },
                    "riftscanCandidateSource": {
                        "matchFile": "C:/old.json",
                        "candidateId": "old-candidate",
                    },
                },
            )
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile={
                    "mode": "proof-only",
                    "input": None,
                    "outputRoot": str(root / "captures"),
                    "candidateId": "profile-fallback-candidate",
                    "candidateIdSource": "current-proof-pointer",
                    "proofAnchorFile": str(proof_anchor),
                },
                process_id=49504,
                target_window_handle="0x5121A",
                live=False,
            )

            self.assertEqual(runner._candidate_id(), "current-anchor-candidate")
            self.assertEqual(runner._proof_pose_candidate_file(), candidate_file)
            self.assertEqual(runner._run_gates()["candidateId"], "current-anchor-candidate")

    def test_stale_pointer_does_not_block_refresh_when_current_anchor_has_candidate_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            pointer.parent.mkdir(parents=True)
            write_json(
                pointer,
                {
                    "mode": "current-proof-anchor-readback-pointer",
                    "target": {
                        "processId": 33912,
                        "processName": "rift_x64",
                        "targetWindowHandle": "0xE0DB2",
                    },
                    "riftscanCandidateSource": {"candidateId": "old-pointer-candidate"},
                },
            )
            candidate_file = root / "current-candidates.json"
            write_json(
                candidate_file,
                {
                    "candidates": [
                        {
                            "candidate_id": "current-anchor-candidate",
                            "source_base_address_hex": "0x20000000",
                            "source_offset_hex": "0x100",
                        }
                    ]
                },
            )
            readback_summary = root / "current-readback-summary.json"
            write_json(readback_summary, {"SourceCandidateFile": str(candidate_file)})
            proof_anchor = root / "scripts" / "captures" / "telemetry-proof-coord-anchor.json"
            proof_anchor.parent.mkdir(parents=True)
            write_json(
                proof_anchor,
                {
                    "Mode": "proof-coord-anchor",
                    "ProcessName": "rift_x64",
                    "ProcessId": 49504,
                    "TargetWindowHandle": "0x5121A",
                    "ObjectBaseAddress": "0x20000100",
                    "Evidence": {
                        "CandidateId": "current-anchor-candidate",
                        "CandidateAddressHex": "0x20000100",
                        "PoseCount": 2,
                        "ReadbackSummaryFiles": [str(readback_summary)],
                    },
                },
            )
            stale_pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            write_json(
                stale_pointer,
                {
                    "mode": "current-proof-anchor-readback-pointer",
                    "target": {
                        "processName": "rift_x64",
                        "processId": 33912,
                        "targetWindowHandle": "0xE0DB2",
                    },
                    "riftscanCandidateSource": {
                        "candidateId": "old-candidate",
                        "matchFile": str(root / "old-candidates.json"),
                    },
                },
            )
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile={
                    "mode": "proof-only",
                    "input": None,
                    "outputRoot": str(root / "captures"),
                    "proofAnchorFile": str(proof_anchor),
                },
                process_id=49504,
                target_window_handle="0x5121A",
                live=False,
            )

            def fake_run_ps1(label: str, script_name: str, args: list[str]):
                if script_name == "capture-rift-api-reference-coordinate.ps1":
                    output_file = Path(args[args.index("-OutputFile") + 1])
                    write_json(
                        output_file,
                        {
                            "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
                            "captured_at_utc": "2026-05-08T22:00:00Z",
                        },
                    )
                    return SimpleNamespace(exit_code=0, json_data={"Status": "captured"})

                self.assertEqual(script_name, "capture-riftscan-proof-pose.ps1")
                self.assertIn("-CandidateFile", args)
                self.assertEqual(Path(args[args.index("-CandidateFile") + 1]), candidate_file)
                fresh_summary = root / "fresh-readback-summary.json"
                write_json(
                    fresh_summary,
                    {
                        "GeneratedAtUtc": "2026-05-08T22:00:01Z",
                        "ProcessName": "rift_x64",
                        "ProcessId": 49504,
                        "TargetWindowHandle": "0x5121A",
                        "NoCheatEngine": True,
                        "MovementSent": False,
                        "ReferenceCoordinate": {"X": 1.0, "Y": 2.0, "Z": 3.0},
                        "BestReferenceMatches": [
                            {
                                "CandidateId": "current-anchor-candidate",
                                "ReferenceMatchesReadback": True,
                                "StableAcrossReadbackSamples": True,
                                "FirstDecodedSample": {
                                    "X": 1.0,
                                    "Y": 2.0,
                                    "Z": 3.0,
                                    "RecordedAtUtc": "2026-05-08T22:00:01Z",
                                },
                            }
                        ],
                    },
                )
                return SimpleNamespace(
                    exit_code=0,
                    json_data={
                        "Status": "captured",
                        "ReadbackSummaryFile": str(fresh_summary),
                        "CurrentCoordinate": {"X": 1.0, "Y": 2.0, "Z": 3.0},
                    },
                    parse_error=None,
                    stderr="",
                    stdout="",
                )

            with patch.object(runner, "_run_ps1", side_effect=fake_run_ps1):
                captured = runner._capture_proof_pose_next()

            self.assertEqual(
                captured["poseReadbackSummaryFile"],
                str(root / "fresh-readback-summary.json"),
            )
            self.assertEqual(captured["currentCoordinate"]["X"], 1.0)

    def test_runner_can_use_profile_candidate_id_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile={
                    "mode": "proof-only",
                    "input": None,
                    "outputRoot": str(root / "captures"),
                    "candidateId": "explicit-profile-candidate",
                    "candidateIdSource": "profile",
                },
                process_id=123,
                target_window_handle="0x123",
                live=False,
            )

            self.assertEqual(runner._candidate_id(), "explicit-profile-candidate")

    def test_live_retry_is_blocked_after_any_movement_started(self) -> None:
        payload = {
            "Status": "blocked-preflight-age-budget",
            "MovementSent": True,
            "MovementAttempted": True,
            "Issues": ["proof_anchor_remaining_age_budget_too_low:remaining=3"],
        }
        self.assertTrue(LiveTestRunner._movement_started(payload))
        self.assertFalse(LiveTestRunner._safe_to_retry_live_input(payload))

    def test_auto_refresh_attempts_are_capped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="Forward250",
                profile={
                    "outputRoot": str(root / "captures"),
                    "maxAutoRefreshAttempts": 1,
                    "autoRefreshProofOnLowAgeBudget": True,
                },
                process_id=123,
                target_window_handle="0x123",
                live=False,
            )
            payload = {
                "Status": "blocked-preflight-age-budget",
                "MovementSent": False,
                "MovementAttempted": False,
                "Issues": ["proof_anchor_remaining_age_budget_too_low:remaining=3"],
            }
            self.assertTrue(runner._can_refresh_for(payload))
            self.assertEqual(runner.auto_refresh_attempts_used, 1)
            self.assertFalse(runner._can_refresh_for(payload))

    def test_input_profile_blocks_without_live_before_proof_refresh_even_if_profile_opts_out(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = {
                "mode": "live-input",
                "input": {"key": "w", "holdMilliseconds": 250, "pulseCount": 1},
                "outputRoot": str(root / "captures"),
                "requireLiveFlagForInput": False,
                "writeMarkdownSummary": False,
            }
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="Forward250",
                profile=profile,
                process_id=123,
                target_window_handle="0x123",
                live=False,
            )
            with patch(
                "rift_live_test.runner.verify_target",
                return_value={"valid": True, "status": "valid", "targetWindowHandle": "0x123"},
            ), patch.object(runner, "_refresh_proof") as refresh:
                summary = runner.run()
            self.assertEqual(summary["status"], BLOCKED_LIVE_FLAG_REQUIRED)
            self.assertFalse(summary["movementSent"])
            refresh.assert_not_called()

    def test_live_input_does_not_pass_when_sent_key_has_no_coordinate_delta(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = {
                "mode": "live-input",
                "input": {"key": "w", "holdMilliseconds": 250, "pulseCount": 1},
                "outputRoot": str(root / "captures"),
                "minimumMovementPlanarDistance": 0.05,
                "writeMarkdownSummary": False,
            }
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="Forward250",
                profile=profile,
                process_id=123,
                target_window_handle="0x123",
                live=True,
            )
            dry = {"Status": "dry-run-valid", "SummaryFile": "dry.json"}
            live_result = {
                "Status": "passed",
                "SummaryFile": "live.json",
                "MovementSent": True,
                "MovementAttempted": True,
                "CurrentCoordinate": {"X": 1.0, "Y": 2.0, "Z": 3.0},
                "PostReadback": {
                    "CurrentCoordinate": {"X": 1.0, "Y": 2.0, "Z": 3.0}
                },
                "CoordinateDelta": {
                    "DeltaX": 0.0,
                    "DeltaY": 0.0,
                    "DeltaZ": 0.0,
                    "PlanarDistance": 0.0,
                    "SpatialDistance": 0.0,
                },
            }

            with patch(
                "rift_live_test.runner.verify_target",
                return_value={"valid": True, "status": "valid", "targetWindowHandle": "0x123"},
            ), patch.object(
                runner,
                "_refresh_proof_next",
                return_value={"poseReadbackSummaryFile": "fresh.json"},
            ), patch.object(
                runner,
                "_run_gated_wrapper",
                side_effect=[dry, live_result],
            ), patch.object(runner, "_record_coordinate_pulse") as recorder:
                summary = runner.run()

            self.assertEqual(summary["status"], INPUT_NO_MOVEMENT)
            self.assertFalse(summary["ok"])
            self.assertTrue(summary["movementSent"])
            self.assertEqual(summary["runHealth"]["state"], "failed")
            self.assertIn("movement_delta_below_threshold", summary["issues"][0])
            self.assertEqual(summary["states"][-1]["status"], INPUT_NO_MOVEMENT)
            recorder.assert_called_once()

    def test_target_mismatch_blocks_before_any_proof_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = {
                "mode": "proof-only",
                "input": None,
                "outputRoot": str(root / "captures"),
                "writeMarkdownSummary": False,
            }
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile=profile,
                process_id=123,
                target_window_handle="0x123",
                live=False,
            )
            with patch(
                "rift_live_test.runner.verify_target",
                return_value={
                    "valid": False,
                    "status": "window-not-found",
                    "issues": ["target_window_not_found"],
                },
            ), patch.object(runner, "_refresh_proof") as refresh:
                summary = runner.run()
            self.assertEqual(summary["status"], BLOCKED_TARGET_MISMATCH)
            self.assertIn("target_window_not_found", summary["issues"])
            refresh.assert_not_called()

    def test_reference_capture_failure_is_blocked_not_internal_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = {
                "mode": "proof-only",
                "input": None,
                "outputRoot": str(root / "captures"),
                "writeMarkdownSummary": False,
            }
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile=profile,
                process_id=123,
                target_window_handle="0x123",
                live=False,
            )
            with patch(
                "rift_live_test.runner.verify_target",
                return_value={"valid": True, "status": "valid", "targetWindowHandle": "0x123"},
            ), patch.object(
                runner,
                "_run_ps1",
                return_value=SimpleNamespace(
                    exit_code=1,
                    json_data=None,
                    parse_error="No JSON object or array found in command output",
                    stderr="No usable RRAPICOORD1 marker was found",
                ),
            ):
                summary = runner.run()

            self.assertEqual(summary["status"], BLOCKED_REFERENCE_CAPTURE)
            self.assertIn("reference_marker_unavailable:no_usable_rrapicoord1", summary["issues"])
            self.assertFalse(summary["movementSent"])

    def test_stale_current_proof_pointer_after_restart_reacquires_current_state_and_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            pointer.parent.mkdir(parents=True)
            pointer.write_text(
                json.dumps(
                    {
                        "mode": "current-proof-anchor-readback-pointer",
                        "target": {
                            "processId": 33912,
                            "processName": "rift_x64",
                            "targetWindowHandle": "0xE0DB2",
                        },
                        "riftscanCandidateSource": {
                            "candidateId": "old-candidate",
                            "matchFile": "C:/RiftScan/old.json",
                        },
                    }
                ),
                encoding="utf-8",
            )
            profile = {
                "mode": "proof-only",
                "input": None,
                "outputRoot": str(root / "captures"),
                "writeMarkdownSummary": False,
            }
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile=profile,
                process_id=49504,
                target_window_handle="0x5121A",
                live=False,
            )

            def fake_run_ps1(label: str, script_name: str, args: list[str]):
                self.assertEqual(script_name, "capture-rift-api-reference-coordinate.ps1")
                output_file = Path(args[args.index("-OutputFile") + 1])
                output_file.write_text(
                    json.dumps(
                        {
                            "source": "rrapicoord1-memory-scan",
                            "captured_at_utc": "2026-05-08T20:49:00Z",
                            "coordinate": {"x": 7446.09, "y": 887.25, "z": 3027.58},
                            "processId": 49504,
                            "processName": "rift_x64",
                            "targetWindowHandle": "0x5121A",
                            "noCheatEngine": True,
                            "movementSent": False,
                            "savedVariablesUse": "none",
                        }
                    ),
                    encoding="utf-8",
                )
                return SimpleNamespace(exit_code=0, json_data={"Status": "captured"})

            with patch(
                "rift_live_test.runner.verify_target",
                return_value={"valid": True, "status": "valid", "targetWindowHandle": "0x5121A"},
            ), patch.object(runner, "_run_ps1", side_effect=fake_run_ps1) as run_ps1:
                summary = runner.run()

            self.assertEqual(summary["status"], BLOCKED_TARGET_DRIFT)
            self.assertEqual(summary["runHealth"]["state"], "blocked")
            self.assertFalse(summary["movementSent"])
            self.assertFalse(summary["movementAttempted"])
            self.assertEqual(summary["currentCoordinate"]["x"], 7446.09)
            self.assertIn(
                "target_drift:current_proof_pointer_pid_mismatch:actual=33912;expected=49504",
                summary["issues"],
            )
            self.assertEqual(run_ps1.call_count, 1)
            self.assertEqual(summary["states"][-1]["state"], "target-drift-reacquire")

            reacquire = json.loads(Path(summary["summaryFile"]).read_text(encoding="utf-8"))
            self.assertEqual(reacquire["Status"], BLOCKED_TARGET_DRIFT)
            self.assertEqual(reacquire["ReacquireStatus"], "api-reference-captured")
            self.assertFalse(reacquire["TargetDrift"]["proofAnchorPromoted"])
            self.assertTrue(reacquire["TargetDrift"]["currentProofPointerInvalidated"])
            self.assertTrue(reacquire["CurrentProofPointerInvalidation"]["updated"])
            self.assertEqual(
                reacquire["PreservedHistoricalEvidence"]["classification"],
                "historical-target-epoch-evidence",
            )
            self.assertEqual(
                reacquire["PreservedHistoricalEvidence"]["reacquireHints"]["candidateId"],
                "old-candidate",
            )
            self.assertIn(
                "do-not-use-as-current-proof",
                reacquire["PreservedHistoricalEvidence"]["reusePolicy"],
            )
            invalidated_pointer = json.loads(pointer.read_text(encoding="utf-8"))
            self.assertEqual(invalidated_pointer["status"], BLOCKED_TARGET_DRIFT)
            self.assertEqual(invalidated_pointer["target"]["processId"], 49504)
            self.assertEqual(invalidated_pointer["target"]["targetWindowHandle"], "0x5121A")
            self.assertEqual(
                invalidated_pointer["currentTruthClassification"]["classification"],
                "stale-target-drift-blocker",
            )
            self.assertFalse(invalidated_pointer["latestValidation"]["movementAllowed"])
            self.assertEqual(
                invalidated_pointer["staleProofPointer"]["preservedEvidence"]["reacquireHints"]["candidateId"],
                "old-candidate",
            )

    def test_target_drift_payload_does_not_loop_auto_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="Forward250",
                profile={
                    "outputRoot": str(root / "captures"),
                    "maxAutoRefreshAttempts": 1,
                    "writeMarkdownSummary": False,
                },
                process_id=49504,
                target_window_handle="0x5121A",
                live=False,
            )
            payload = {
                "Status": "blocked-preflight",
                "MovementSent": False,
                "MovementAttempted": False,
                "Issues": ["proof_anchor_pid_mismatch:anchor=33912;target=49504"],
            }

            self.assertFalse(runner._can_refresh_for(payload))
            self.assertEqual(runner.auto_refresh_attempts_used, 0)
            self.assertEqual(
                runner._map_blocked_status(payload, default="blocked-dry-run"),
                BLOCKED_TARGET_DRIFT,
            )

    def test_promotion_baseline_block_preserves_fresh_pose_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fresh = root / "fresh-summary.json"
            fresh.write_text("{}", encoding="utf-8")
            profile = {
                "mode": "proof-only",
                "input": None,
                "outputRoot": str(root / "captures"),
                "writeMarkdownSummary": False,
            }
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile=profile,
                process_id=123,
                target_window_handle="0x123",
                live=False,
            )
            captured = {
                "poseReadbackSummaryFile": str(fresh),
                "currentCoordinate": {
                    "X": 4.0,
                    "Y": 5.0,
                    "Z": 6.0,
                    "RecordedAtUtc": "2026-05-08T00:00:00Z",
                },
            }
            diagnostics = {
                "status": "no-compatible-displaced-baseline",
                "freshSummaryFile": str(fresh),
                "selected": [],
                "candidateCount": 1,
                "compatibleDisplacedCount": 0,
                "candidates": [],
            }
            with patch(
                "rift_live_test.runner.verify_target",
                return_value={"valid": True, "status": "valid", "targetWindowHandle": "0x123"},
            ), patch.object(
                runner,
                "_capture_proof_pose",
                return_value=captured,
            ), patch.object(
                runner,
                "_select_promotion_readback_files",
                return_value=([], diagnostics),
            ):
                summary = runner.run()

            self.assertEqual(summary["status"], BLOCKED_PROMOTION_REFERENCE_MISMATCH)
            self.assertEqual(summary["summaryFile"], str(fresh))
            self.assertEqual(summary["currentCoordinate"]["x"], 4.0)
            self.assertEqual(summary["currentCoordinate"]["y"], 5.0)
            self.assertEqual(summary["currentCoordinate"]["z"], 6.0)
            self.assertFalse(summary["movementSent"])
            self.assertFalse(summary["movementAttempted"])
            self.assertEqual(summary["states"][-1]["summaryFile"], str(fresh))

            progress = json.loads(runner.progress_file.read_text(encoding="utf-8"))
            self.assertEqual(progress["currentCoordinate"]["x"], 4.0)
            self.assertFalse(progress["movementSent"])
            selection = json.loads(
                (runner.run_dir / "promotion-baseline-selection.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(selection["freshCurrentCoordinate"]["X"], 4.0)

    def test_child_commands_receive_process_name_and_proof_anchor_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            proof_anchor = root / "custom-proof-anchor.json"
            profile = {
                "mode": "live-input",
                "input": {"key": "w", "holdMilliseconds": 250, "pulseCount": 1},
                "outputRoot": str(root / "captures"),
                "processName": "rift_x64",
                "proofAnchorFile": str(proof_anchor),
                "inputBackend": "csharp-scancode",
                "writeMarkdownSummary": False,
            }
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="Forward250",
                profile=profile,
                process_id=123,
                target_window_handle="0x123",
                live=True,
            )
            with patch.object(
                runner,
                "_run_ps1",
                return_value=SimpleNamespace(json_data={"Status": "valid"}, exit_code=0),
            ) as run_ps1:
                runner._assert_current_readback(label="readback")
                runner._run_gated_wrapper(dry_run=True, label="dry")

            readback_args = run_ps1.call_args_list[0].args[2]
            dry_args = run_ps1.call_args_list[1].args[2]
            for argv in (readback_args, dry_args):
                self.assertIn("-ProcessName", argv)
                self.assertIn("-ProofCoordAnchorFile", argv)
                self.assertEqual(argv[argv.index("-ProofCoordAnchorFile") + 1], str(proof_anchor))
            self.assertIn("-InputBackend", dry_args)
            self.assertEqual(dry_args[dry_args.index("-InputBackend") + 1], "csharp-scancode")

    def test_run_command_updates_latest_child_command_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile={
                    "mode": "proof-only",
                    "input": None,
                    "outputRoot": str(root / "captures"),
                    "writeMarkdownSummary": False,
                },
                process_id=123,
                target_window_handle="0x123",
                live=False,
            )
            with patch(
                "rift_live_test.runner.run_json_command",
                return_value=JsonCommandResult(
                    label="demo-child",
                    args=["demo"],
                    exit_code=0,
                    stdout='{"Status":"valid"}',
                    stderr="",
                    json_data={"Status": "valid"},
                    json_text='{"Status":"valid"}',
                    parse_error=None,
                ),
            ):
                runner._run_command("demo-child", ["demo"])

            self.assertEqual(runner.latest_child_command["label"], "demo-child")
            self.assertEqual(runner.latest_child_command["status"], "completed")
            self.assertEqual(runner.latest_child_command["exitCode"], 0)
            self.assertIn("durationSeconds", runner.latest_child_command)
            self.assertIsNone(runner.latest_child_command["parseError"])
            progress = json.loads(runner.progress_file.read_text(encoding="utf-8"))
            self.assertEqual(progress["latestChildCommand"]["jsonStatus"], "valid")

    def test_child_command_status_accepts_proof_validation_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile={"outputRoot": str(root / "captures")},
                process_id=123,
                target_window_handle="0x123",
                live=False,
            )

            self.assertEqual(
                runner._command_json_status({"ProofValidationStatus": "validated"}),
                "validated",
            )

    def test_promote_command_receives_process_name_and_proof_anchor_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            proof_anchor = root / "custom-proof-anchor.json"
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="Forward250",
                profile={
                    "outputRoot": str(root / "captures"),
                    "processName": "rift_x64",
                    "proofAnchorFile": str(proof_anchor),
                    "writeMarkdownSummary": False,
                },
                process_id=123,
                target_window_handle="0x123",
                live=True,
            )
            with patch.object(
                runner,
                "_run_command",
                return_value=SimpleNamespace(json_data={"ProofValidationStatus": "validated"}, exit_code=0),
            ) as run_command:
                runner._run_promote([str(root / "a.json"), str(root / "b.json")])

            encoded = run_command.call_args.args[1][-1]
            script = base64.b64decode(encoded).decode("utf-16le")
            self.assertIn("-ProcessName 'rift_x64'", script)
            self.assertIn(f"-OutputFile '{proof_anchor}'", script)

    def test_promotion_reference_target_mismatch_is_detected_before_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "ProcessName": "rift_x64",
                        "ProcessId": 999,
                        "TargetWindowHandle": "0x123",
                    }
                ),
                encoding="utf-8",
            )
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile={
                    "mode": "proof-only",
                    "input": None,
                    "outputRoot": str(root / "captures"),
                    "promotionReferenceReadbackSummary": str(baseline),
                    "writeMarkdownSummary": False,
                },
                process_id=123,
                target_window_handle="0x123",
                live=False,
            )
            issues = runner._validate_promotion_reference_target()
            self.assertIn("promotion_reference_pid_mismatch:actual=999;expected=123", issues)

    def test_progress_file_is_written_incrementally(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="Forward250",
                profile={
                    "mode": "live-input",
                    "input": {"key": "w", "holdMilliseconds": 250, "pulseCount": 1},
                    "outputRoot": str(root / "captures"),
                    "writeMarkdownSummary": False,
                },
                process_id=123,
                target_window_handle="0x123",
                live=True,
            )

            runner._state("verify-target", "passed", detail="pid=123;hwnd=0x123")

            progress = json.loads(runner.progress_file.read_text(encoding="utf-8"))
            self.assertEqual(progress["status"], "running")
            self.assertFalse(progress["finalSummaryWritten"])
            self.assertEqual(progress["states"][0]["state"], "verify-target")
            self.assertTrue(progress["runGates"]["requireExactTarget"])
            self.assertTrue(progress["runGates"]["requireLiveFlagForInput"])
            self.assertEqual(progress["runHealth"]["state"], "running")
            self.assertFalse(progress["runHealth"]["finalSummaryWritten"])
            self.assertTrue(progress["latestPointer"]["updateAllowed"])
            self.assertIsNone(progress["latestPointer"]["skipReason"])

            latest = json.loads(
                (root / "scripts" / "captures" / "latest-live-test-run.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(latest["runProgressFile"], str(runner.progress_file))
            self.assertFalse(latest["finalSummaryWritten"])
            self.assertTrue(latest["runDirectoryInsideRepo"])

    def test_external_output_root_does_not_update_repo_latest_pointer_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as repo_temp:
            with tempfile.TemporaryDirectory() as external_temp:
                root = Path(repo_temp)
                pointer = root / "scripts" / "captures" / "latest-live-test-run.json"
                write_json(pointer, {"status": "existing", "sentinel": True})
                runner = LiveTestRunner(
                    repo_root=root,
                    profile_name="ProofOnly",
                    profile={
                        "mode": "proof-only",
                        "input": None,
                        "outputRoot": str(Path(external_temp) / "captures"),
                        "writeMarkdownSummary": False,
                    },
                    process_id=123,
                    target_window_handle="0x123",
                    live=False,
                )

                runner._state("verify-target", "passed", detail="pid=123;hwnd=0x123")

                progress = json.loads(runner.progress_file.read_text(encoding="utf-8"))
                latest = json.loads(pointer.read_text(encoding="utf-8"))

        self.assertEqual(latest, {"status": "existing", "sentinel": True})
        self.assertFalse(progress["latestPointer"]["updateAllowed"])
        self.assertEqual(progress["latestPointer"]["skipReason"], "output_root_outside_repo")
        self.assertFalse(progress["latestPointer"]["runDirectoryInsideRepo"])

    def test_external_output_root_can_opt_into_repo_latest_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as repo_temp:
            with tempfile.TemporaryDirectory() as external_temp:
                root = Path(repo_temp)
                runner = LiveTestRunner(
                    repo_root=root,
                    profile_name="ProofOnly",
                    profile={
                        "mode": "proof-only",
                        "input": None,
                        "outputRoot": str(Path(external_temp) / "captures"),
                        "updateLatestPointerForExternalOutputRoot": True,
                        "writeMarkdownSummary": False,
                    },
                    process_id=123,
                    target_window_handle="0x123",
                    live=False,
                )

                runner._state("verify-target", "passed", detail="pid=123;hwnd=0x123")

                pointer = root / "scripts" / "captures" / "latest-live-test-run.json"
                latest = json.loads(pointer.read_text(encoding="utf-8"))
                progress = json.loads(runner.progress_file.read_text(encoding="utf-8"))

        self.assertTrue(progress["latestPointer"]["updateAllowed"])
        self.assertTrue(latest["runProgressFile"].endswith("run-progress.json"))
        self.assertFalse(latest["runDirectoryInsideRepo"])

    def test_final_summary_marks_progress_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile={
                    "mode": "proof-only",
                    "input": None,
                    "outputRoot": str(root / "captures"),
                    "writeMarkdownSummary": False,
                },
                process_id=123,
                target_window_handle="0x123",
                live=False,
            )

            summary = runner._finish(
                "passed-proof-only",
                final_json={
                    "Status": "valid",
                    "MovementSent": False,
                    "MovementAttempted": False,
                    "CurrentCoordinate": {"X": 1.0, "Y": 2.0, "Z": 3.0},
                },
            )

            progress = json.loads(runner.progress_file.read_text(encoding="utf-8"))
            self.assertTrue(progress["finalSummaryWritten"])
            self.assertEqual(progress["status"], "passed-proof-only")
            self.assertEqual(progress["runHealth"]["state"], "ok")
            self.assertTrue(progress["runHealth"]["finalSummaryWritten"])
            self.assertEqual(summary["runProgressFile"], str(runner.progress_file))
            self.assertEqual(summary["runHealth"]["state"], "ok")
            latest = json.loads(
                (root / "scripts" / "captures" / "latest-live-test-run.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(latest["runHealth"]["movementSent"])
            self.assertFalse(latest["runHealth"]["movementAttempted"])

    def test_proofonly_success_updates_tracked_current_proof_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_candidate_file = root / "current-candidates.json"
            write_json(
                source_candidate_file,
                {
                    "candidates": [
                        {
                            "candidate_id": "fresh-current-candidate",
                            "source_base_address_hex": "0x20000000",
                            "source_offset_hex": "0x80",
                            "source_absolute_address_hex": "0x20000080",
                        }
                    ]
                },
            )
            proof_pose_summary = root / "proof-pose-summary.json"
            write_json(proof_pose_summary, {"SourceCandidateFile": str(source_candidate_file)})
            proof_anchor = root / "scripts" / "captures" / "telemetry-proof-coord-anchor.json"
            proof_anchor.parent.mkdir(parents=True)
            write_json(
                proof_anchor,
                {
                    "Mode": "proof-coord-anchor",
                    "ProcessName": "rift_x64",
                    "ProcessId": 49504,
                    "TargetWindowHandle": "0x5121A",
                    "ObjectBaseAddress": "0x20000080",
                    "Match": {"MaxDeltaError": 0.01},
                    "Evidence": {
                        "CandidateId": "fresh-current-candidate",
                        "CandidateAddressHex": "0x20000080",
                        "PoseCount": 3,
                        "ReadbackSummaryFiles": [str(proof_pose_summary)],
                    },
                },
            )
            stale_pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            write_json(
                stale_pointer,
                {
                    "mode": "current-proof-anchor-readback-pointer",
                    "target": {
                        "processName": "rift_x64",
                        "processId": 33912,
                        "targetWindowHandle": "0xE0DB2",
                    },
                    "riftscanCandidateSource": {
                        "candidateId": "old-candidate",
                        "matchFile": str(root / "old-candidates.json"),
                    },
                },
            )
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ProofOnly",
                profile={
                    "mode": "proof-only",
                    "input": None,
                    "outputRoot": str(root / "captures"),
                    "proofAnchorFile": str(proof_anchor),
                    "writeMarkdownSummary": False,
                },
                process_id=49504,
                target_window_handle="0x5121A",
                live=False,
            )

            summary = runner._finish(
                "passed-proof-only",
                final_json={
                    "Status": "valid",
                    "MovementAllowed": True,
                    "MovementSent": False,
                    "MovementAttempted": False,
                    "SummaryFile": str(root / "fresh-readback.json"),
                    "CurrentCoordinate": {
                        "X": 1.0,
                        "Y": 2.0,
                        "Z": 3.0,
                        "RecordedAtUtc": "2026-05-08T22:00:00Z",
                    },
                },
            )

            pointer = json.loads(
                (root / "docs" / "recovery" / "current-proof-anchor-readback.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(pointer["target"]["processId"], 49504)
            self.assertEqual(pointer["target"]["targetWindowHandle"], "0x5121A")
            self.assertEqual(pointer["riftscanCandidateSource"]["candidateId"], "fresh-current-candidate")
            self.assertEqual(pointer["riftscanCandidateSource"]["matchFile"], str(source_candidate_file))
            self.assertEqual(pointer["riftscanCandidateSource"]["sourceBaseAddressHex"], "0x20000000")
            self.assertEqual(pointer["riftscanCandidateSource"]["sourceOffsetHex"], "0x80")
            self.assertEqual(pointer["riftscanCandidateSource"]["sourceAbsoluteAddressHex"], "0x20000080")
            self.assertEqual(pointer["latestProofOnly"]["status"], "passed-proof-only")
            self.assertEqual(pointer["latestProofOnly"]["readbackSummaryFile"], str(root / "fresh-readback.json"))
            self.assertTrue(runner.current_proof_pointer_update["updated"])
            self.assertTrue(runner.current_proof_pointer_update["archivedSupersededPointer"])
            self.assertEqual(
                summary["currentProofPointerUpdate"],
                runner.current_proof_pointer_update,
            )
            progress = json.loads(runner.progress_file.read_text(encoding="utf-8"))
            self.assertEqual(
                progress["currentProofPointerUpdate"],
                runner.current_proof_pointer_update,
            )
            latest = json.loads(
                (root / "scripts" / "captures" / "latest-live-test-run.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                latest["currentProofPointerUpdate"],
                runner.current_proof_pointer_update,
            )
            archive = Path(runner.current_proof_pointer_update["archivedSupersededPointer"]["path"])
            self.assertTrue(archive.exists())
            archived = json.loads(archive.read_text(encoding="utf-8"))
            self.assertEqual(archived["target"]["processId"], 33912)

    def test_baseline_pool_selects_compatible_displaced_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pool = root / "pool.json"
            old = root / "old.json"
            near = root / "near.json"
            wrong_pid = root / "wrong-pid.json"
            fresh = root / "fresh.json"
            self._write_pose_summary(old, x=8.0, z=18.0)
            self._write_pose_summary(near, x=10.1, z=20.1)
            self._write_pose_summary(wrong_pid, process_id=999, x=0.0, z=0.0)
            self._write_pose_summary(fresh, x=10.2, z=20.2)
            record_baseline_summary(pool_file=pool, summary_file=old, source="test-old")
            record_baseline_summary(pool_file=pool, summary_file=near, source="test-near")
            record_baseline_summary(pool_file=pool, summary_file=wrong_pid, source="test-wrong")

            selected, diagnostics = select_baselines_for_fresh_summary(
                fresh_summary_file=fresh,
                candidate_paths=[str(old), str(near), str(wrong_pid)],
                process_id=123,
                target_window_handle="0x123",
                process_name="rift_x64",
                candidate_id="rift-addon-coordinate-candidate-000001",
                min_reference_displacement=1.0,
                max_count=4,
            )

            self.assertEqual(diagnostics["status"], "selected")
            self.assertEqual(selected, [str(old.resolve()), str(fresh.resolve())])
            self.assertEqual(diagnostics["compatibleDisplacedCount"], 1)
            wrong = [item for item in diagnostics["candidates"] if "wrong-pid" in item["summaryFile"]][0]
            self.assertEqual(wrong["status"], "historical-target-mismatch")
            self.assertIn("preserve-as-historical-evidence-only", wrong["reusePolicy"])

    def test_baseline_pool_reports_no_displaced_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            near = root / "near.json"
            fresh = root / "fresh.json"
            self._write_pose_summary(near, x=1.0, z=1.0)
            self._write_pose_summary(fresh, x=1.1, z=1.1)

            selected, diagnostics = select_baselines_for_fresh_summary(
                fresh_summary_file=fresh,
                candidate_paths=[str(near)],
                process_id=123,
                target_window_handle="0x123",
                process_name="rift_x64",
                candidate_id="rift-addon-coordinate-candidate-000001",
                min_reference_displacement=1.0,
                max_count=4,
            )

            self.assertEqual(selected, [])
            self.assertEqual(diagnostics["status"], "no-compatible-displaced-baseline")

    def test_series_runs_one_wrapper_pulse_at_a_time(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ForwardSeries2x250",
                profile={
                    "mode": "live-input-series",
                    "input": {"key": "w", "holdMilliseconds": 250, "pulseCount": 2},
                    "outputRoot": str(root / "captures"),
                    "writeMarkdownSummary": False,
                },
                process_id=123,
                target_window_handle="0x123",
                live=True,
            )
            dry_1 = {"Status": "dry-run-valid", "SummaryFile": "dry-1.json"}
            live_1 = {
                "Status": "passed",
                "SummaryFile": "live-1.json",
                "MovementSent": True,
                "MovementAttempted": True,
                "Preflight": {
                    "CurrentCoordinate": {"X": 1.0, "Y": 2.0, "Z": 3.0}
                },
                "PostReadback": {
                    "CurrentCoordinate": {"X": 1.1, "Y": 2.0, "Z": 2.7}
                },
                "CoordinateDelta": {
                    "DeltaX": 0.1,
                    "DeltaY": 0.0,
                    "DeltaZ": -0.3,
                    "PlanarDistance": 0.316,
                    "SpatialDistance": 0.316,
                },
            }
            dry_2 = {"Status": "dry-run-valid", "SummaryFile": "dry-2.json"}
            live_2 = {
                "Status": "passed",
                "SummaryFile": "live-2.json",
                "MovementSent": True,
                "MovementAttempted": True,
                "Preflight": {
                    "CurrentCoordinate": {"X": 1.1, "Y": 2.0, "Z": 2.7}
                },
                "PostReadback": {
                    "CurrentCoordinate": {"X": 1.2, "Y": 2.0, "Z": 2.4}
                },
                "CoordinateDelta": {
                    "DeltaX": 0.1,
                    "DeltaY": 0.0,
                    "DeltaZ": -0.3,
                    "PlanarDistance": 0.316,
                    "SpatialDistance": 0.316,
                },
            }
            with patch.object(
                runner,
                "_run_gated_wrapper",
                side_effect=[dry_1, live_1, dry_2, live_2],
            ) as wrapper:
                summary = runner._run_live_input_series()

            self.assertEqual(summary["status"], "passed")
            self.assertEqual(summary["requestedPulseCount"], 2)
            self.assertEqual(summary["completedPulseCount"], 2)
            self.assertTrue(summary["movementSent"])
            self.assertEqual(len(summary["seriesPulses"]), 2)
            self.assertAlmostEqual(summary["seriesCoordinateDelta"]["deltaX"], 0.2)
            self.assertAlmostEqual(summary["seriesCoordinateDelta"]["deltaZ"], -0.6)
            for call in wrapper.call_args_list:
                self.assertEqual(call.kwargs["pulse_count"], 1)

    def test_series_stops_partial_after_prior_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ForwardSeries2x250",
                profile={
                    "mode": "live-input-series",
                    "input": {"key": "w", "holdMilliseconds": 250, "pulseCount": 2},
                    "outputRoot": str(root / "captures"),
                    "maxAutoRefreshAttempts": 0,
                    "writeMarkdownSummary": False,
                },
                process_id=123,
                target_window_handle="0x123",
                live=True,
            )
            dry_1 = {"Status": "dry-run-valid", "SummaryFile": "dry-1.json"}
            live_1 = {
                "Status": "passed",
                "SummaryFile": "live-1.json",
                "MovementSent": True,
                "MovementAttempted": True,
                "Preflight": {
                    "CurrentCoordinate": {"X": 1.0, "Y": 2.0, "Z": 3.0}
                },
                "PostReadback": {
                    "CurrentCoordinate": {"X": 1.1, "Y": 2.0, "Z": 2.7}
                },
            }
            dry_2 = {
                "Status": "blocked-preflight-age-budget",
                "SummaryFile": "dry-2.json",
                "Issues": ["proof_anchor_remaining_age_budget_too_low:remaining=3"],
            }
            with patch.object(
                runner,
                "_run_gated_wrapper",
                side_effect=[dry_1, live_1, dry_2],
            ):
                summary = runner._run_live_input_series()

            self.assertEqual(summary["status"], "partial-series-stopped")
            self.assertEqual(summary["completedPulseCount"], 1)
            self.assertTrue(summary["movementSent"])
            self.assertEqual(summary["seriesPulses"][1]["stage"], "dry-run")
            self.assertIn("proof_anchor_remaining_age_budget_too_low", summary["issues"][0])

    def test_coordinate_recorder_records_series_pulse_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = LiveTestRunner(
                repo_root=root,
                profile_name="ForwardSeries2x250",
                profile={
                    "mode": "live-input-series",
                    "input": {"key": "w", "holdMilliseconds": 250, "pulseCount": 2},
                    "recording": {"coordSamples": True},
                    "outputRoot": str(root / "captures"),
                    "writeMarkdownSummary": False,
                },
                process_id=123,
                target_window_handle="0x123",
                live=True,
            )
            dry = {
                "Status": "dry-run-valid",
                "SummaryFile": "dry-1.json",
                "Preflight": {
                    "CurrentCoordinate": {"X": 1.0, "Y": 2.0, "Z": 3.0},
                },
            }
            live = {
                "Status": "passed",
                "SummaryFile": "live-1.json",
                "MovementSent": True,
                "MovementAttempted": True,
                "Preflight": {
                    "AnchorReadback": {
                        "DecodedSamples": [
                            {
                                "SampleIndex": 0,
                                "RecordedAtUtc": "2026-05-07T00:00:00Z",
                                "X": 1.0,
                                "Y": 2.0,
                                "Z": 3.0,
                            },
                            {
                                "SampleIndex": 1,
                                "RecordedAtUtc": "2026-05-07T00:00:01Z",
                                "X": 1.0,
                                "Y": 2.0,
                                "Z": 3.0,
                            },
                        ]
                    },
                    "CurrentCoordinate": {"X": 1.0, "Y": 2.0, "Z": 3.0},
                    "SummaryFile": "pre-readback.json",
                },
                "PostReadback": {
                    "AnchorReadback": {
                        "DecodedSamples": [
                            {
                                "SampleIndex": 0,
                                "RecordedAtUtc": "2026-05-07T00:00:02Z",
                                "X": 1.2,
                                "Y": 2.0,
                                "Z": 2.6,
                            },
                            {
                                "SampleIndex": 1,
                                "RecordedAtUtc": "2026-05-07T00:00:03Z",
                                "X": 1.3,
                                "Y": 2.0,
                                "Z": 2.5,
                            },
                        ]
                    },
                    "CurrentCoordinate": {"X": 1.3, "Y": 2.0, "Z": 2.5},
                    "SummaryFile": "post-readback.json",
                },
                "CoordinateDelta": {
                    "DeltaX": 0.3,
                    "DeltaY": 0.0,
                    "DeltaZ": -0.5,
                    "PlanarDistance": 0.583,
                    "SpatialDistance": 0.583,
                },
            }

            runner._append_series_pulse(
                pulse_index=1,
                status="passed",
                stage="live-input",
                dry_run=dry,
                live_result=live,
            )

            pulse = runner.series_pulses[0]
            recording = pulse["coordinateRecording"]
            self.assertEqual(recording["sampleCount"], 5)
            self.assertEqual(recording["phases"]["dry-run-preflight"], 1)
            self.assertEqual(recording["phases"]["live-preflight"], 2)
            self.assertEqual(recording["phases"]["live-post-readback"], 2)
            self.assertTrue(Path(recording["samplesFile"]).exists())
            samples = [
                json.loads(line)
                for line in Path(recording["samplesFile"]).read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(samples[-1]["coordinate"]["x"], 1.3)
            self.assertTrue(samples[-1]["noCheatEngine"])
            self.assertFalse(samples[-1]["savedVariablesUsedAsLiveTruth"])


if __name__ == "__main__":
    unittest.main()
