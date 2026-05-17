#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import status_packet  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


class OpenCodeStatusPacketTests(unittest.TestCase):
    def test_opencode_version_command_uses_windows_shim_safe_form(self) -> None:
        command = status_packet.opencode_version_command()

        self.assertEqual(command[-2:], ["opencode", "--version"])
        if sys.platform == "win32":
            self.assertEqual(command[:3], ["cmd", "/d", "/c"])
        else:
            self.assertEqual(command, ["opencode", "--version"])

    def test_find_latest_handoff_selects_newest_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            handoff_dir = root / "docs" / "handoffs"
            older = handoff_dir / "2026-05-15-old.md"
            newer = handoff_dir / "2026-05-16-new.md"
            write_text(older, "# Old handoff\n\n## TL;DR\n\nold")
            write_text(newer, "# New handoff\n\n## TL;DR\n\nnew")
            os.utime(older, (1_700_000_000, 1_700_000_000))
            os.utime(newer, (1_800_000_000, 1_800_000_000))

            latest = status_packet.find_latest_handoff(root)
            summary = status_packet.summarize_handoff(root, latest, [], [])

        self.assertEqual(latest, newer)
        self.assertEqual(summary["title"], "New handoff")
        self.assertEqual(summary["tldr"], "new")

    def test_summarize_blocked_proof_preserves_stale_anchor_boundary(self) -> None:
        proof = {
            "status": "blocked-target-drift",
            "lastUpdatedUtc": "2026-05-16T16:46:11Z",
            "target": {
                "processName": "rift_x64",
                "processId": 27552,
                "targetWindowHandle": "0x3411E2",
            },
            "latestValidation": {"status": "blocked-target-drift", "movementAllowed": False},
            "latestProofOnly": {"status": "blocked-target-drift", "movementSent": False},
            "staleProofPointer": {
                "archivedPointer": "docs\\recovery\\historical\\old.json",
                "reusePolicy": "do-not-use-as-current-proof",
                "preservedEvidence": {
                    "riftscanCandidateSource": {
                        "candidateId": "api-family-hit-000001",
                        "sourceAbsoluteAddressHex": "0x27B1ED850C0",
                        "matchFile": "candidates.jsonl",
                    }
                },
            },
        }

        summary = status_packet.summarize_current_proof(proof)

        self.assertEqual(summary["status"], "blocked-target-drift")
        self.assertFalse(summary["latestValidation"]["movementAllowed"])
        self.assertEqual(summary["staleAnchor"]["candidateId"], "api-family-hit-000001")
        self.assertEqual(summary["staleAnchor"]["addressHex"], "0x27B1ED850C0")
        self.assertEqual(summary["staleAnchor"]["reusePolicy"], "do-not-use-as-current-proof")

    def test_build_status_packet_reports_no_live_target_blocker_without_git_or_opencode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_text(root / "docs" / "handoffs" / "2026-05-16-handoff.md", "# Handoff\n\n## TL;DR\n\nblocked")
            write_text(root / "docs" / "recovery" / "current-truth.md", "# Truth\n\n## Verdict\n\nMovement is blocked.")
            write_json(
                root / "docs" / "recovery" / "current-truth.json",
                {
                    "status": "no_current_candidate_movement_blocked_reacquisition_required",
                    "updatedAtUtc": "2026-05-16T16:46:11Z",
                    "target": {"processName": "rift_x64", "processId": 27552, "targetWindowHandle": "0x3411E2"},
                    "movementGate": {
                        "allowed": False,
                        "status": "blocked-no-live-target-reacquisition-required",
                        "reason": "No live rift_x64 process is available.",
                    },
                    "currentBlockers": ["live-target-not-running:rift_x64"],
                    "nextRecommendedAction": "Load RIFT in-world before recovery.",
                },
            )
            write_json(
                root / "docs" / "recovery" / "current-proof-anchor-readback.json",
                {
                    "status": "blocked-target-drift",
                    "lastUpdatedUtc": "2026-05-16T16:46:11Z",
                    "target": {"processName": "rift_x64", "processId": 27552, "targetWindowHandle": "0x3411E2"},
                    "latestValidation": {"status": "blocked-target-drift", "movementAllowed": False},
                    "latestProofOnly": {"status": "blocked-target-drift", "movementSent": False},
                },
            )

            packet = status_packet.build_status_packet(
                root,
                run_coordinate_status=False,
                check_opencode=False,
                collect_git_state=False,
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("live-target-not-running:rift_x64", packet["blockers"])
        self.assertIn("current-proof-status:blocked-target-drift", packet["blockers"])
        self.assertIn("movement-not-allowed:blocked-no-live-target-reacquisition-required", packet["blockers"])
        self.assertFalse(packet["safety"]["movementSent"])
        self.assertFalse(packet["safety"]["gitMutation"])

    def test_build_status_packet_explains_live_artifact_pid_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_text(root / "docs" / "handoffs" / "2026-05-17-handoff.md", "# Handoff\n\n## TL;DR\n\nlive stale")
            write_text(root / "docs" / "recovery" / "current-truth.md", "# Truth\n\n## Verdict\n\nMovement is blocked.")
            write_json(
                root / "docs" / "recovery" / "current-truth.json",
                {
                    "status": "no_current_candidate_movement_blocked_reacquisition_required",
                    "updatedAtUtc": "2026-05-16T16:46:11Z",
                    "target": {"processName": "rift_x64", "processId": 27552, "targetWindowHandle": "0x3411E2"},
                    "movementGate": {"allowed": False, "status": "blocked-no-live-target-reacquisition-required"},
                    "currentBlockers": ["No live rift_x64 process was detected during offline recovery."],
                    "nextRecommendedAction": "Start/load RIFT into the character world.",
                },
            )
            write_json(
                root / "docs" / "recovery" / "current-proof-anchor-readback.json",
                {
                    "status": "blocked-target-drift",
                    "target": {"processName": "rift_x64", "processId": 27552, "targetWindowHandle": "0x3411E2"},
                    "latestValidation": {"status": "blocked-target-drift", "movementAllowed": False},
                    "latestProofOnly": {"status": "blocked-target-drift", "movementSent": False},
                },
            )
            coordinate_script = root / "scripts" / "coordinate_recovery_status.py"
            write_text(
                coordinate_script,
                "\n".join(
                    [
                        "import json, sys",
                        "print(json.dumps({",
                        "  'status': 'blocked',",
                        "  'blockers': ['artifact-target-pid-not-running:artifact=27552;live=22304'],",
                        "  'liveTarget': {",
                        "    'status': 'passed',",
                        "    'verdict': 'artifact-pid-stale',",
                        "    'artifactProcessName': 'rift_x64',",
                        "    'artifactPid': 27552,",
                        "    'artifactHwnd': '0x3411E2',",
                        "    'livePids': [22304]",
                        "  }",
                        "}))",
                        "raise SystemExit(2)",
                    ]
                ),
            )

            packet = status_packet.build_status_packet(
                root,
                run_coordinate_status=True,
                check_opencode=False,
                collect_git_state=False,
            )

        self.assertTrue(packet["liveTarget"]["artifactPidStale"])
        self.assertEqual(packet["liveTarget"]["livePids"], [22304])
        self.assertIn(
            "current-truth-stale-live-target-detected:artifact=27552;live=22304",
            packet["warnings"],
        )
        self.assertIn("Live RIFT is running with PID(s) [22304]", packet["nextRecommendedAction"])
        self.assertIn("do not reuse stale proof", packet["nextRecommendedAction"])

    def test_run_command_records_envelope_and_stdout_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            envelope = status_packet.run_command(
                "python-echo",
                [sys.executable, "-c", "print('ok')"],
                Path(temp_dir),
            )

        self.assertTrue(envelope["ok"])
        self.assertEqual(envelope["exitCode"], 0)
        self.assertEqual(envelope["stdoutPreview"].strip(), "ok")
        self.assertIn("durationSeconds", envelope)

    def test_write_outputs_uses_ignored_local_status_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = {
                "schemaVersion": 1,
                "kind": "riftreader-opencode-non-codex-status-packet",
                "generatedAtUtc": "2026-05-16T00:00:00Z",
                "status": "blocked",
                "blockers": ["live-target-not-running:rift_x64"],
                "warnings": [],
                "errors": [],
                "git": {},
                "currentProof": {"summary": {}},
                "currentTruth": {"summary": {}},
                "latestHandoff": {},
                "coordinateRecoveryStatus": {},
                "opencode": {},
                "safety": {"movementSent": False, "gitMutation": False},
                "nextRecommendedAction": "Load RIFT in-world before recovery.",
                "artifacts": {},
            }

            artifacts = status_packet.write_outputs(packet, root)

            summary_json = root / artifacts["summaryJson"]
            summary_md = root / artifacts["summaryMarkdown"]

            self.assertTrue(artifacts["summaryJson"].startswith(".riftreader-local\\opencode-status\\"))
            self.assertTrue(summary_json.is_file())
            self.assertTrue(summary_md.is_file())


if __name__ == "__main__":
    unittest.main()
