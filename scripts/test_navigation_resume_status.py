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


if __name__ == "__main__":
    unittest.main()
