from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from rift_live_test.x64dbg_no_attach_readiness_packet import build_parser, run_packet


class X64DbgNoAttachReadinessPacketTests(unittest.TestCase):
    def test_packet_orchestrates_no_attach_readiness_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            out = temp_path / "packet"
            calls: list[tuple[str, list[str]]] = []
            planner_summary = temp_path / "planner-summary.json"

            def fake_runner(name: str, _main_fn: Any, argv: list[str]) -> dict[str, Any]:
                calls.append((name, argv))
                if name == "x64dbg_preflight":
                    return {
                        "name": name,
                        "argv": argv,
                        "exitCode": 0,
                        "payload": {
                            "status": "passed",
                            "summaryJson": str(temp_path / "preflight-summary.json"),
                            "blockers": [],
                            "warnings": [],
                        },
                        "stdout": "",
                    }
                if name == "chromalink_world_state_reference":
                    return {
                        "name": name,
                        "argv": argv,
                        "exitCode": 0,
                        "payload": {
                            "status": "passed",
                            "referenceJson": str(temp_path / "rift-api-reference-currentpid-79184.json"),
                            "blockers": [],
                            "warnings": [],
                        },
                        "stdout": "",
                    }
                planner_summary.write_text(
                    json.dumps(
                        {
                            "status": "planned",
                            "readiness": {"status": "ready-for-current-turn-approval"},
                            "candidate": {
                                "candidateId": "api-family-hit-000001",
                                "address": "0x17382765E40",
                                "artifactPath": str(temp_path / "api-family-vec3-candidates.json"),
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                return {
                    "name": name,
                    "argv": argv,
                    "exitCode": 0,
                    "payload": {
                        "status": "planned",
                        "summaryJson": str(planner_summary),
                        "compactHandoffJson": str(temp_path / "handoff.json"),
                        "compactHandoffMarkdown": str(temp_path / "handoff.md"),
                        "blockers": [],
                        "warnings": [],
                    },
                    "stdout": "",
                }

            args = build_parser().parse_args(
                [
                    "--repo-root",
                    str(temp_path),
                    "--output-root",
                    str(out),
                    "--target-pid",
                    "79184",
                    "--target-hwnd",
                    "0xA90BFC",
                    "--expected-start-time-utc",
                    "2026-05-13T00:43:12.080812Z",
                    "--expected-module-base",
                    "0x7FF796B50000",
                ]
            )
            summary = run_packet(args, fake_runner)

            self.assertEqual(summary["status"], "passed")
            self.assertEqual(summary["readinessStatus"], "ready-for-current-turn-approval")
            self.assertTrue(summary["safety"]["noAttachWorkflow"])
            self.assertFalse(summary["safety"]["x64dbgLiveAttachStarted"])
            self.assertEqual([name for name, _ in calls], ["x64dbg_preflight", "chromalink_world_state_reference", "x64dbg_coord_chain_plan"])

            preflight_argv = calls[0][1]
            self.assertIn("--require-exact-target", preflight_argv)
            self.assertIn("--require-no-debugger-process", preflight_argv)
            self.assertIn("--expected-start-time-utc", preflight_argv)
            self.assertIn("--expected-module-base", preflight_argv)

            planner_argv = calls[2][1]
            self.assertIn("--candidate-file", planner_argv)
            self.assertIn("latest", planner_argv)
            self.assertIn("--candidate-id", planner_argv)
            self.assertIn("best", planner_argv)
            self.assertIn("--strict-live-debugger-readiness", planner_argv)
            self.assertTrue((out / "summary.json").is_file())
            self.assertTrue((out / "summary.md").is_file())

    def test_packet_stops_after_preflight_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            calls: list[str] = []

            def fake_runner(name: str, _main_fn: Any, argv: list[str]) -> dict[str, Any]:
                calls.append(name)
                return {
                    "name": name,
                    "argv": argv,
                    "exitCode": 2,
                    "payload": {
                        "status": "blocked",
                        "blockers": ["debugger-process-present"],
                        "warnings": [],
                    },
                    "stdout": "",
                }

            args = build_parser().parse_args(
                [
                    "--repo-root",
                    str(temp_path),
                    "--output-root",
                    str(temp_path / "packet"),
                    "--target-pid",
                    "79184",
                    "--target-hwnd",
                    "0xA90BFC",
                ]
            )
            summary = run_packet(args, fake_runner)

            self.assertEqual(summary["status"], "blocked")
            self.assertEqual(calls, ["x64dbg_preflight"])
            self.assertIn("x64dbg_preflight:debugger-process-present", summary["blockers"])


if __name__ == "__main__":
    unittest.main()
