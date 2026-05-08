from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rift_live_test.actor_yaw_readback_smoke import (
    build_capture_command,
    build_read_player_command,
    run_actor_yaw_readback_smoke,
)
from rift_live_test.commands import JsonCommandResult
from test_current_actor_yaw_disambiguation import valid_lead, valid_packet, write_json


class ActorYawReadbackSmokeTests(unittest.TestCase):
    def make_repo(self, root: Path) -> None:
        write_json(root / "docs" / "recovery" / "current-actor-yaw-disambiguation.json", valid_packet())
        write_json(root / "scripts" / "actor-facing-behavior-backed-lead.json", valid_lead())

    def test_command_builders_use_exact_pid_and_hwnd(self) -> None:
        root = Path("C:/RiftReader")
        read = build_read_player_command(repo_root=root, process_id=4242)
        capture = build_capture_command(
            repo_root=root,
            process_id=4242,
            target_window_handle="0x1234",
            process_name="rift_x64",
            output_file=root / "out.json",
            previous_file=root / "prev.json",
        )

        self.assertIn("--pid", read)
        self.assertIn("4242", read)
        self.assertIn("-TargetWindowHandle", capture)
        self.assertIn("0x1234", capture)
        self.assertIn("-OutputFile", capture)

    def test_smoke_passes_with_matching_stubbed_readbacks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            self.make_repo(root)

            def runner(args: list[str], cwd: Path, label: str, timeout: int | None) -> JsonCommandResult:
                if label == "read-player-orientation":
                    payload = {
                        "SelectedSourceAddress": "0xABCDEF00",
                        "BasisPrimaryForwardOffset": "0xD4",
                        "ResolutionMode": "live-behavior-backed-lead",
                        "PreferredEstimate": {"YawDegrees": 10.0, "PitchDegrees": 1.0},
                    }
                else:
                    payload = {
                        "ReaderOrientation": {
                            "SelectedSourceAddress": "0xABCDEF00",
                            "BasisForwardOffset": "0xD4",
                            "ResolutionMode": "behavior-backed-lead",
                            "PreferredEstimate": {"YawDegrees": 11.0, "PitchDegrees": 2.0},
                        }
                    }
                return JsonCommandResult(
                    label=label,
                    args=args,
                    exit_code=0,
                    stdout=json.dumps(payload),
                    stderr="",
                    json_data=payload,
                    json_text=json.dumps(payload),
                    parse_error=None,
                )

            summary = run_actor_yaw_readback_smoke(
                repo_root=root,
                process_id=4242,
                target_window_handle="0x1234",
                output_root=root / "scripts" / "captures",
                command_runner=runner,
            )

            self.assertTrue(summary["ok"], summary["issues"])
            self.assertEqual(summary["status"], "passed")
            self.assertFalse(summary["safety"]["movementSent"])
            self.assertFalse(summary["safety"]["movementAllowed"])
            self.assertTrue(Path(summary["summaryFile"]).exists())
            self.assertTrue(Path(summary["markdownFile"]).exists())
            self.assertTrue(Path(summary["latestPointerFile"]).exists())
            pointer = json.loads(Path(summary["latestPointerFile"]).read_text(encoding="utf-8"))
            self.assertEqual(pointer["mode"], "latest-actor-yaw-readback-smoke-pointer")
            self.assertEqual(pointer["status"], "passed")
            self.assertEqual(pointer["latestPointerFile"], summary["latestPointerFile"])
            self.assertEqual(pointer["summaryFile"], summary["summaryFile"])

    def test_smoke_fails_when_live_readback_selects_different_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            self.make_repo(root)

            def runner(args: list[str], cwd: Path, label: str, timeout: int | None) -> JsonCommandResult:
                if label == "read-player-orientation":
                    payload = {
                        "SelectedSourceAddress": "0xDEADBEEF",
                        "BasisPrimaryForwardOffset": "0xD4",
                        "ResolutionMode": "live-behavior-backed-lead",
                    }
                else:
                    payload = {
                        "ReaderOrientation": {
                            "SelectedSourceAddress": "0xABCDEF00",
                            "BasisForwardOffset": "0xD4",
                            "ResolutionMode": "behavior-backed-lead",
                        }
                    }
                return JsonCommandResult(
                    label=label,
                    args=args,
                    exit_code=0,
                    stdout=json.dumps(payload),
                    stderr="",
                    json_data=payload,
                    json_text=json.dumps(payload),
                    parse_error=None,
                )

            summary = run_actor_yaw_readback_smoke(
                repo_root=root,
                process_id=4242,
                target_window_handle="0x1234",
                output_root=root / "scripts" / "captures",
                command_runner=runner,
            )

            self.assertFalse(summary["ok"])
            self.assertIn("read_player_orientation_failed", summary["issues"])
            self.assertFalse(summary["readPlayerOrientation"]["sourceMatchesPromotedLead"])

    def test_smoke_refuses_output_inside_riftscan_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "RiftReader"
            riftscan = Path(temp) / "Riftscan"
            self.make_repo(root)

            with self.assertRaisesRegex(ValueError, "Refusing to write"):
                run_actor_yaw_readback_smoke(
                    repo_root=root,
                    process_id=4242,
                    target_window_handle="0x1234",
                    output_root=riftscan / "reports",
                    riftscan_root=riftscan,
                    command_runner=lambda args, cwd, label, timeout: JsonCommandResult(
                        label=label,
                        args=args,
                        exit_code=0,
                        stdout="{}",
                        stderr="",
                        json_data={},
                        json_text="{}",
                        parse_error=None,
                    ),
                )


if __name__ == "__main__":
    unittest.main()
