from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from rift_live_test.x64dbg_no_attach_readiness_packet import build_parser, run_packet


TARGET_PID = "79184"
TARGET_HWND = "0xA90BFC"
TARGET_START_UTC = "2026-05-13T00:43:12.080812Z"
TARGET_MODULE_BASE = "0x7FF796B50000"


def write_candidate_file(path: Path, *, candidate_id: str = "family-snapshot-hit-000004") -> Path:
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "processId": int(TARGET_PID),
                "targetWindowHandle": TARGET_HWND,
                "candidates": [
                    {
                        "candidate_id": candidate_id,
                        "absolute_address_hex": "0x17382765E40",
                        "axis_order": "xyz",
                        "processId": int(TARGET_PID),
                        "targetWindowHandle": TARGET_HWND,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def write_current_truth(
    path: Path,
    *,
    candidate_file: Path,
    candidate_id: str = "family-snapshot-hit-000004",
    pid: int = int(TARGET_PID),
    hwnd: str = TARGET_HWND,
    start_utc: str = TARGET_START_UTC,
    module_base: str = TARGET_MODULE_BASE,
) -> Path:
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "kind": "riftreader-current-truth",
                "status": "candidate_only_movement_blocked",
                "target": {
                    "processId": pid,
                    "targetWindowHandle": hwnd,
                    "processStartUtc": start_utc,
                    "moduleBase": module_base,
                },
                "bestCurrentCandidate": {
                    "candidateId": candidate_id,
                    "candidateFile": str(candidate_file),
                    "status": "latest_readback_reference_match_candidate_only_not_movement_proof",
                },
            }
        ),
        encoding="utf-8",
    )
    return path


class X64DbgNoAttachReadinessPacketTests(unittest.TestCase):
    def test_packet_orchestrates_no_attach_readiness_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            out = temp_path / "packet"
            calls: list[tuple[str, list[str]]] = []
            planner_summary = temp_path / "planner-summary.json"
            candidate_file = write_candidate_file(temp_path / "family-import-candidates.json")
            current_truth = write_current_truth(temp_path / "current-truth.json", candidate_file=candidate_file)

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
                if name == "x64dbg_access_event_template":
                    template_summary = temp_path / "template-summary.json"
                    template_summary.write_text(
                        json.dumps(
                            {
                                "status": "passed",
                                "candidateEvidence": {
                                    "kind": "coordinate-family-ranking",
                                    "path": str(temp_path / "coordinate-family-rankings.json"),
                                    "candidateOnly": True,
                                    "promotionEligible": False,
                                    "poseGroupCount": 2,
                                    "selectedAddress": {
                                        "addressHex": "0x17382765E40",
                                        "supportPoseCount": 2,
                                    },
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
                            "status": "passed",
                            "summaryJson": str(template_summary),
                            "templateJson": str(temp_path / "x64dbg-manual-access-events-template.json"),
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
                                "candidateId": "family-snapshot-hit-000004",
                                "address": "0x17382765E40",
                                "artifactPath": str(candidate_file),
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
                    TARGET_PID,
                    "--target-hwnd",
                    TARGET_HWND,
                    "--expected-start-time-utc",
                    TARGET_START_UTC,
                    "--expected-module-base",
                    TARGET_MODULE_BASE,
                    "--current-truth-json",
                    str(current_truth),
                ]
            )
            summary = run_packet(args, fake_runner)

            self.assertEqual(summary["status"], "passed")
            self.assertEqual(summary["readinessStatus"], "ready-for-current-turn-approval")
            self.assertTrue(summary["safety"]["noAttachWorkflow"])
            self.assertFalse(summary["safety"]["x64dbgLiveAttachStarted"])
            self.assertEqual(
                [name for name, _ in calls],
                [
                    "x64dbg_preflight",
                    "chromalink_world_state_reference",
                    "x64dbg_coord_chain_plan",
                    "x64dbg_access_event_template",
                ],
            )

            preflight_argv = calls[0][1]
            self.assertIn("--require-exact-target", preflight_argv)
            self.assertIn("--require-no-debugger-process", preflight_argv)
            self.assertIn("--expected-start-time-utc", preflight_argv)
            self.assertIn("--expected-module-base", preflight_argv)

            planner_argv = calls[2][1]
            self.assertIn("--candidate-file", planner_argv)
            self.assertIn(str(candidate_file), planner_argv)
            self.assertIn("--candidate-id", planner_argv)
            self.assertIn("family-snapshot-hit-000004", planner_argv)
            self.assertNotIn("latest", planner_argv)
            self.assertNotIn("best", planner_argv)
            self.assertIn("--strict-live-debugger-readiness", planner_argv)
            self.assertEqual(summary["candidateSelection"]["source"], "current-truth")
            self.assertEqual(summary["candidateSelection"]["candidateFile"], str(candidate_file))
            self.assertEqual(summary["candidateSelection"]["candidateId"], "family-snapshot-hit-000004")

            template_argv = calls[3][1]
            self.assertIn("--planner-summary", template_argv)
            self.assertIn(str(planner_summary), template_argv)
            self.assertIn("--output-root", template_argv)
            self.assertEqual(
                summary["artifacts"]["accessEventTemplateJson"],
                str(temp_path / "x64dbg-manual-access-events-template.json"),
            )
            self.assertEqual(summary["candidateEvidence"]["kind"], "coordinate-family-ranking")
            self.assertEqual(summary["candidateEvidence"]["selectedAddress"]["supportPoseCount"], 2)
            self.assertFalse(summary["candidateEvidence"]["promotionEligible"])
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

    def test_packet_can_pass_rift_error_handler_ignore_to_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            supplied_api = temp_path / "api-reference.json"
            candidate_file = write_candidate_file(temp_path / "explicit-candidates.json", candidate_id="explicit-hit")
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
                if name == "x64dbg_access_event_template":
                    return {
                        "name": name,
                        "argv": argv,
                        "exitCode": 0,
                        "payload": {
                            "status": "passed",
                            "summaryJson": str(temp_path / "template-summary.json"),
                            "templateJson": str(temp_path / "x64dbg-manual-access-events-template.json"),
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
                                "candidateId": "explicit-hit",
                                "address": "0x17382765E40",
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
                    str(temp_path / "packet"),
                    "--target-pid",
                    TARGET_PID,
                    "--target-hwnd",
                    TARGET_HWND,
                    "--api-coordinate-file",
                    str(supplied_api),
                    "--candidate-file",
                    str(candidate_file),
                    "--candidate-id",
                    "explicit-hit",
                    "--ignore-rift-error-handler",
                ]
            )
            summary = run_packet(args, fake_runner)

            self.assertEqual(summary["status"], "passed")
            self.assertIn("--ignore-rift-error-handler", calls[0][1])
            self.assertTrue(summary["safety"]["riftErrorHandlerIgnored"])

    def test_packet_skips_chromalink_when_api_coordinate_file_supplied(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            supplied_api = temp_path / "api-reference.json"
            planner_summary = temp_path / "planner-summary.json"
            candidate_file = write_candidate_file(temp_path / "explicit-candidates.json", candidate_id="explicit-hit")
            calls: list[tuple[str, list[str]]] = []

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
                if name == "x64dbg_access_event_template":
                    return {
                        "name": name,
                        "argv": argv,
                        "exitCode": 0,
                        "payload": {
                            "status": "passed",
                            "summaryJson": str(temp_path / "template-summary.json"),
                            "templateJson": str(temp_path / "x64dbg-manual-access-events-template.json"),
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
                    str(temp_path / "packet"),
                    "--target-pid",
                    TARGET_PID,
                    "--target-hwnd",
                    TARGET_HWND,
                    "--api-coordinate-file",
                    str(supplied_api),
                    "--candidate-file",
                    str(candidate_file),
                    "--candidate-id",
                    "explicit-hit",
                ]
            )
            summary = run_packet(args, fake_runner)

            self.assertEqual(summary["status"], "passed")
            self.assertEqual(
                [name for name, _ in calls],
                ["x64dbg_preflight", "x64dbg_coord_chain_plan", "x64dbg_access_event_template"],
            )
            planner_argv = calls[1][1]
            self.assertIn("--api-coordinate-file", planner_argv)
            self.assertIn(str(supplied_api), planner_argv)
            self.assertIn("--candidate-file", planner_argv)
            self.assertIn(str(candidate_file), planner_argv)
            self.assertIn("--candidate-id", planner_argv)
            self.assertIn("explicit-hit", planner_argv)
            self.assertEqual(summary["candidateSelection"]["source"], "explicit")
            self.assertFalse(summary["apiCoordinateSource"]["fallbackUsed"])

    def test_packet_falls_back_to_latest_api_coordinate_when_chromalink_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            planner_summary = temp_path / "planner-summary.json"
            candidate_file = write_candidate_file(temp_path / "family-import-candidates.json")
            current_truth = write_current_truth(temp_path / "current-truth.json", candidate_file=candidate_file)
            calls: list[tuple[str, list[str]]] = []

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
                        "exitCode": 2,
                        "payload": {
                            "status": "blocked",
                            "blockers": ["chromalink-world-state-not-fresh"],
                            "warnings": [],
                        },
                        "stdout": "",
                    }
                if name == "x64dbg_access_event_template":
                    return {
                        "name": name,
                        "argv": argv,
                        "exitCode": 0,
                        "payload": {
                            "status": "passed",
                            "summaryJson": str(temp_path / "template-summary.json"),
                            "templateJson": str(temp_path / "x64dbg-manual-access-events-template.json"),
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
                    str(temp_path / "packet"),
                    "--target-pid",
                    TARGET_PID,
                    "--target-hwnd",
                    TARGET_HWND,
                    "--current-truth-json",
                    str(current_truth),
                ]
            )
            summary = run_packet(args, fake_runner)

            self.assertEqual(summary["status"], "passed")
            self.assertEqual(
                [name for name, _ in calls],
                [
                    "x64dbg_preflight",
                    "chromalink_world_state_reference",
                    "x64dbg_coord_chain_plan",
                    "x64dbg_access_event_template",
                ],
            )
            planner_argv = calls[2][1]
            self.assertIn("--api-coordinate-file", planner_argv)
            self.assertIn("latest", planner_argv)
            self.assertIn("--candidate-file", planner_argv)
            self.assertIn(str(candidate_file), planner_argv)
            self.assertIn("--candidate-id", planner_argv)
            self.assertIn("family-snapshot-hit-000004", planner_argv)
            self.assertTrue(summary["apiCoordinateSource"]["fallbackUsed"])
            self.assertFalse(summary["blockers"])
            self.assertTrue(any("fallback-recovered:chromalink-world-state-not-fresh" in warning for warning in summary["warnings"]))

    def test_packet_blocks_candidate_selection_without_current_truth_or_explicit_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            supplied_api = temp_path / "api-reference.json"
            calls: list[tuple[str, list[str]]] = []

            def fake_runner(name: str, _main_fn: Any, argv: list[str]) -> dict[str, Any]:
                calls.append((name, argv))
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

            args = build_parser().parse_args(
                [
                    "--repo-root",
                    str(temp_path),
                    "--output-root",
                    str(temp_path / "packet"),
                    "--target-pid",
                    TARGET_PID,
                    "--target-hwnd",
                    TARGET_HWND,
                    "--api-coordinate-file",
                    str(supplied_api),
                ]
            )
            summary = run_packet(args, fake_runner)

            self.assertEqual(summary["status"], "blocked")
            self.assertEqual([name for name, _ in calls], ["x64dbg_preflight"])
            self.assertIn(
                f"candidate_selection:current-truth-json-not-found:{temp_path / 'docs' / 'recovery' / 'current-truth.json'}",
                summary["blockers"],
            )
            self.assertIsNone(summary["artifacts"]["plannerSummaryJson"])

    def test_packet_blocks_current_truth_target_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            supplied_api = temp_path / "api-reference.json"
            candidate_file = write_candidate_file(temp_path / "family-import-candidates.json")
            current_truth = write_current_truth(
                temp_path / "current-truth.json",
                candidate_file=candidate_file,
                pid=12345,
            )
            calls: list[tuple[str, list[str]]] = []

            def fake_runner(name: str, _main_fn: Any, argv: list[str]) -> dict[str, Any]:
                calls.append((name, argv))
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

            args = build_parser().parse_args(
                [
                    "--repo-root",
                    str(temp_path),
                    "--output-root",
                    str(temp_path / "packet"),
                    "--target-pid",
                    TARGET_PID,
                    "--target-hwnd",
                    TARGET_HWND,
                    "--api-coordinate-file",
                    str(supplied_api),
                    "--current-truth-json",
                    str(current_truth),
                ]
            )
            summary = run_packet(args, fake_runner)

            self.assertEqual(summary["status"], "blocked")
            self.assertEqual([name for name, _ in calls], ["x64dbg_preflight"])
            self.assertIn("candidate_selection:current-truth-target-pid-mismatch:79184!=12345", summary["blockers"])

    def test_packet_latest_candidate_fallback_requires_explicit_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            supplied_api = temp_path / "api-reference.json"
            planner_summary = temp_path / "planner-summary.json"
            calls: list[tuple[str, list[str]]] = []

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
                if name == "x64dbg_access_event_template":
                    return {
                        "name": name,
                        "argv": argv,
                        "exitCode": 0,
                        "payload": {
                            "status": "passed",
                            "summaryJson": str(temp_path / "template-summary.json"),
                            "templateJson": str(temp_path / "x64dbg-manual-access-events-template.json"),
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
                    str(temp_path / "packet"),
                    "--target-pid",
                    TARGET_PID,
                    "--target-hwnd",
                    TARGET_HWND,
                    "--api-coordinate-file",
                    str(supplied_api),
                    "--allow-latest-candidate-fallback",
                ]
            )
            summary = run_packet(args, fake_runner)

            self.assertEqual(summary["status"], "passed")
            self.assertEqual([name for name, _ in calls], ["x64dbg_preflight", "x64dbg_coord_chain_plan", "x64dbg_access_event_template"])
            planner_argv = calls[1][1]
            self.assertIn("--candidate-file", planner_argv)
            self.assertIn("latest", planner_argv)
            self.assertIn("--candidate-id", planner_argv)
            self.assertIn("best", planner_argv)
            self.assertEqual(summary["candidateSelection"]["source"], "latest-fallback")
            self.assertTrue(summary["candidateSelection"]["allowLatestCandidateFallback"])
            self.assertTrue(any("latest-candidate-fallback-explicitly-allowed" in warning for warning in summary["warnings"]))

    def test_explicit_latest_candidate_alias_requires_allow_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            supplied_api = temp_path / "api-reference.json"
            calls: list[tuple[str, list[str]]] = []

            def fake_runner(name: str, _main_fn: Any, argv: list[str]) -> dict[str, Any]:
                calls.append((name, argv))
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

            args = build_parser().parse_args(
                [
                    "--repo-root",
                    str(temp_path),
                    "--output-root",
                    str(temp_path / "packet"),
                    "--target-pid",
                    TARGET_PID,
                    "--target-hwnd",
                    TARGET_HWND,
                    "--api-coordinate-file",
                    str(supplied_api),
                    "--candidate-file",
                    "latest",
                ]
            )
            summary = run_packet(args, fake_runner)

            self.assertEqual(summary["status"], "blocked")
            self.assertEqual([name for name, _ in calls], ["x64dbg_preflight"])
            self.assertIn(
                "candidate_selection:candidate-file-latest-requires-allow-latest-candidate-fallback",
                summary["blockers"],
            )


if __name__ == "__main__":
    unittest.main()
