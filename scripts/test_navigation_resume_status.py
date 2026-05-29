from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rift_live_test.navigation_resume_status import (
    NavigationResumeStatusOptions,
    build_navigation_resume_status,
)


class NavigationResumeStatusTests(unittest.TestCase):
    def test_blocks_when_current_truth_not_promoted_and_proof_target_differs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_current_truth(root, "Coordinate truth is not promoted. RIFT MMO navigation.")
            self._write_target_control(root, pid=2928, hwnd="0xC0994", ready=True)
            self._write_visual_gate(root, pid=2928, hwnd="0xC0994", ready=True)
            self._write_proof_only(root, pid=57656, hwnd="0x5417BC", passed=True)
            self._write_navigation_run(root)
            self._write_turn_evidence(root, promoted=False)

            summary = build_navigation_resume_status(NavigationResumeStatusOptions(repo_root=root))

        self.assertEqual("blocked-for-live-input", summary["status"])
        self.assertIn("current-truth-coordinate-proof-not-promoted", summary["blockers"])
        self.assertIn("latest-proofonly-target-differs-from-latest-visual-gate", summary["blockers"])
        self.assertIn("latest-proofonly-hwnd-differs-from-latest-visual-gate", summary["blockers"])
        self.assertFalse(summary["focus"]["liveInputSentByThisHelper"])

    def test_ready_for_pre_live_recheck_when_offline_evidence_aligns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_current_truth(root, "Navigation-first. Current proof anchor promoted.")
            self._write_target_control(root, pid=2928, hwnd="0xC0994", ready=True)
            self._write_visual_gate(root, pid=2928, hwnd="0xC0994", ready=True)
            self._write_proof_only(root, pid=2928, hwnd="0xC0994", passed=True)
            self._write_navigation_run(root, pid=2928)
            self._write_turn_evidence(root, promoted=True)

            summary = build_navigation_resume_status(NavigationResumeStatusOptions(repo_root=root))

        self.assertEqual("ready-for-pre-live-recheck", summary["status"])
        self.assertEqual([], summary["blockers"])
        self.assertEqual("native-window-message", summary["evidence"]["latestNavigationRun"]["movementBackend"])

    def test_writes_summary_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "out"
            self._write_current_truth(root, "Coordinate truth is not promoted. Navigation-first.")

            summary = build_navigation_resume_status(
                NavigationResumeStatusOptions(
                    repo_root=root,
                    output_dir=output_dir,
                    write_summary=True,
                )
            )

            summary_json = Path(summary["artifacts"]["summaryJson"])
            summary_md = Path(summary["artifacts"]["summaryMarkdown"])
            self.assertTrue(summary_json.exists())
            self.assertTrue(summary_md.exists())
            self.assertIn("Navigation resume status", summary_md.read_text(encoding="utf-8"))

    @staticmethod
    def _write_current_truth(root: Path, text: str) -> None:
        path = root / "docs" / "recovery" / "current-truth.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    @staticmethod
    def _write_target_control(root: Path, *, pid: int, hwnd: str, ready: bool) -> None:
        path = root / "scripts" / "captures" / "target-control-current" / "target-control-status.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "status": "passed-target-control" if ready else "blocked-target-control",
                    "classification": "exact-hwnd-foreground" if ready else "target-window-missing",
                    "ok": ready,
                    "readyForReadOnlyProof": ready,
                    "readyForVisualGate": ready,
                    "readyForLiveInput": ready,
                    "target": {
                        "processName": "rift_x64",
                        "processId": pid,
                        "requestedWindowHandle": hwnd,
                    },
                    "window": {
                        "processId": pid,
                        "windowHandleHex": hwnd,
                    },
                    "movementSent": False,
                    "inputSent": False,
                    "noCheatEngine": True,
                    "blockers": [] if ready else ["target-window-missing"],
                }
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_visual_gate(root: Path, *, pid: int, hwnd: str, ready: bool) -> None:
        path = root / "scripts" / "captures" / "visual-gate-current" / "visual-gate-status.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "status": "passed-visual-baseline" if ready else "blocked-visual-baseline",
                    "ok": ready,
                    "readyForLiveInput": ready,
                    "processId": pid,
                    "targetWindowHandle": hwnd,
                    "focusConfirmedForeground": ready,
                    "movementSent": False,
                    "inputSent": False,
                    "noCheatEngine": True,
                    "blockers": [] if ready else ["visual-blocked"],
                }
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_proof_only(root: Path, *, pid: int, hwnd: str, passed: bool) -> None:
        path = root / "scripts" / "captures" / "live-test-ProofOnly-current" / "run-summary.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "status": "passed-proof-only" if passed else "blocked-proof-only",
                    "ok": passed,
                    "processId": pid,
                    "targetWindowHandle": hwnd,
                    "movementSent": False,
                    "movementAttempted": False,
                    "noCheatEngine": True,
                    "savedVariablesUsedAsLiveTruth": False,
                    "currentCoordinate": {"x": 1.0, "y": 2.0, "z": 3.0, "recordedAtUtc": "now"},
                }
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_navigation_run(root: Path, *, pid: int = 49504) -> None:
        path = root / "scripts" / "captures" / "navigation-run" / "navigate-waypoints-run-summary.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "Status": "success",
                    "ProcessId": pid,
                    "ProcessName": "rift_x64",
                    "MovementBackend": "native-window-message",
                    "PulseCount": 4,
                    "StopReason": "arrived",
                    "FinalPlanarDistance": 0.5,
                    "ArrivalRadius": 0.75,
                    "AnchorSource": "coord-trace-anchor",
                }
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_turn_evidence(root: Path, *, promoted: bool) -> None:
        path = root / "docs" / "recovery" / "turn-key-profile-evidence.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"promotedCandidates": [{"key": "Right"}] if promoted else []}),
            encoding="utf-8",
        )

    @staticmethod
    def _write_route_run_report(
        root: Path,
        *,
        arrived: bool = True,
        steps_run: int = 2,
        terrain_blocked: bool = False,
        drifted_back: bool = False,
    ) -> None:
        steps = []
        for i in range(1, steps_run + 1):
            is_last = i == steps_run
            route_status = "arrived" if (is_last and arrived) else "progress"
            step = {
                "stepNumber": i,
                "status": "passed",
                "verdict": "route-step-live-movement-progress-validated",
                "routeStatus": route_status,
                "stopReason": "within-arrival-radius" if route_status == "arrived" else "distance-decreased",
                "totalProgressDistance": 1.5,
                "movementSent": True,
                "inputSent": True,
            }
            if not arrived and is_last and terrain_blocked:
                step["routeStatus"] = "no-progress"
                step["stopReason"] = "minimum-progress-not-met"
                step["noProgressSubClassification"] = "blocked-stationary-no-movement"
                step["status"] = "blocked"
                step["verdict"] = "route-step-blocked"
            steps.append(step)

        aggregate = {
            "status": "passed" if arrived else "blocked",
            "verdict": "route-run-arrived" if arrived else "route-run-blocked",
            "stepsRun": steps_run,
            "maxSteps": steps_run,
            "arrived": arrived,
            "arrivalStep": steps_run if arrived else None,
            "lastRouteStatus": "arrived" if arrived else "no-progress",
            "totalProgressDistance": 1.5 * (steps_run - (0 if arrived else 1)),
            "finalPlanarDistance": 1.0 if arrived else 7.5,
            "movementSent": True,
            "inputSent": True,
        }

        report = {
            "schemaVersion": 1,
            "kind": "static-owner-nav-route-run-report",
            "generatedAtUtc": "2026-05-29T00:00:00Z",
            "status": "passed" if arrived else "blocked",
            "sourceSummaryJson": "fixture/summary.json",
            "source": {
                "kind": "static-owner-nav-route-run",
                "status": "passed" if arrived else "blocked",
                "verdict": "route-run-arrived" if arrived else "route-run-blocked",
                "generatedAtUtc": "2026-05-29T00:00:00Z",
                "aggregate": aggregate,
                "steps": steps,
            },
            "contract": {
                "status": "passed",
                "blockers": [],
                "stepsRun": steps_run,
                "arrived": arrived,
            },
            "blockers": [],
            "warnings": [],
            "errors": [],
        }

        path = root / "scripts" / "captures" / "static-owner-nav-route-run-report-20260529" / "summary.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report), encoding="utf-8")

    def test_clean_route_run_report_no_terrain_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_current_truth(root, "Navigation-first. Current proof anchor promoted.")
            self._write_target_control(root, pid=2928, hwnd="0xC0994", ready=True)
            self._write_visual_gate(root, pid=2928, hwnd="0xC0994", ready=True)
            self._write_proof_only(root, pid=2928, hwnd="0xC0994", passed=True)
            self._write_navigation_run(root, pid=2928)
            self._write_turn_evidence(root, promoted=True)
            self._write_route_run_report(root, arrived=True, steps_run=2, terrain_blocked=False)

            summary = build_navigation_resume_status(NavigationResumeStatusOptions(repo_root=root))

        evidence = summary["evidence"]["latestRouteRunReport"]
        self.assertEqual("passed", evidence["status"])
        self.assertEqual("route-run-arrived", evidence["sourceVerdict"])
        self.assertEqual(2, evidence["stepsRun"])
        self.assertTrue(evidence["arrived"])
        self.assertEqual(0, evidence["noProgressStepCount"])
        self.assertEqual({}, evidence["terrainSubClassifications"])
        self.assertFalse(evidence["terrainBlockerPresent"])
        self.assertEqual("ready-for-pre-live-recheck", summary["status"])

    def test_route_run_report_with_terrain_blocked_stationary_warns_operator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_current_truth(root, "Navigation-first. Current proof anchor promoted.")
            self._write_target_control(root, pid=2928, hwnd="0xC0994", ready=True)
            self._write_visual_gate(root, pid=2928, hwnd="0xC0994", ready=True)
            self._write_proof_only(root, pid=2928, hwnd="0xC0994", passed=True)
            self._write_navigation_run(root, pid=2928)
            self._write_turn_evidence(root, promoted=True)
            self._write_route_run_report(root, arrived=False, steps_run=3, terrain_blocked=True)

            summary = build_navigation_resume_status(NavigationResumeStatusOptions(repo_root=root))

        evidence = summary["evidence"]["latestRouteRunReport"]
        self.assertEqual("blocked", evidence["status"])
        self.assertEqual("route-run-blocked", evidence["sourceVerdict"])
        self.assertEqual(3, evidence["stepsRun"])
        self.assertFalse(evidence["arrived"])
        self.assertEqual(1, evidence["noProgressStepCount"])
        self.assertEqual({"blocked-stationary-no-movement": 1}, evidence["terrainSubClassifications"])
        self.assertTrue(evidence["terrainBlockerPresent"])

        warnings = summary["warnings"]
        self.assertTrue(any("prior-route-run-had-no-progress-steps:count=1" in w for w in warnings))
        self.assertTrue(any("prior-route-run-terrain-blocked-stationary" in w for w in warnings))
        self.assertEqual("ready-for-pre-live-recheck", summary["status"])

    def test_route_run_report_missing_graceful(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_current_truth(root, "Navigation-first. Current proof anchor promoted.")
            self._write_target_control(root, pid=2928, hwnd="0xC0994", ready=True)
            self._write_visual_gate(root, pid=2928, hwnd="0xC0994", ready=True)
            self._write_proof_only(root, pid=2928, hwnd="0xC0994", passed=True)
            self._write_navigation_run(root, pid=2928)
            self._write_turn_evidence(root, promoted=True)

            summary = build_navigation_resume_status(NavigationResumeStatusOptions(repo_root=root))

        evidence = summary["evidence"]["latestRouteRunReport"]
        self.assertEqual("route-run-report-missing", evidence["status"])
        self.assertEqual(0, evidence.get("noProgressStepCount", 0))
        self.assertIn("no-route-run-report-available-for-terrain-context", summary["warnings"])
        self.assertEqual("ready-for-pre-live-recheck", summary["status"])

    def test_markdown_includes_route_run_report_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "out"
            self._write_current_truth(root, "Coordinate truth is not promoted. Navigation-first.")
            self._write_route_run_report(root, arrived=False, steps_run=2, terrain_blocked=True)

            summary = build_navigation_resume_status(
                NavigationResumeStatusOptions(
                    repo_root=root,
                    output_dir=output_dir,
                    write_summary=True,
                )
            )

            summary_md = Path(summary["artifacts"]["summaryMarkdown"])
            md_text = summary_md.read_text(encoding="utf-8")

        self.assertIn("Route-run report", md_text)
        self.assertIn("Terrain classification", md_text)
        self.assertIn("blocked-stationary-no-movement", md_text)


if __name__ == "__main__":
    unittest.main()
