#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
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


class StatusPacketProofFreshnessTests(unittest.TestCase):
    def test_current_proof_summary_reports_proof_freshness(self) -> None:
        now = datetime(2026, 5, 27, 7, 2, tzinfo=timezone.utc)
        proof = {
            "status": "current-target-proofonly-passed",
            "lastUpdatedUtc": "2026-05-27T07:00:00Z",
            "latestValidation": {
                "status": "valid",
                "movementAllowed": True,
                "generatedAtUtc": "2026-05-27T07:01:30Z",
            },
            "latestProofOnly": {
                "status": "passed-proof-only",
                "generatedAtUtc": "2026-05-27T07:01:20Z",
            },
        }

        summary = status_packet.summarize_current_proof(proof, now=now)

        self.assertEqual(summary["proofFreshness"]["status"], "fresh")
        self.assertEqual(summary["proofFreshness"]["ageSeconds"], 30)
        self.assertEqual(summary["proofFreshness"]["observedSource"], "latestValidation.generatedAtUtc")

    def test_build_status_packet_blocks_stale_proof_anchor_movement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_text(root / "docs" / "handoffs" / "2026-05-27-handoff.md", "# Handoff\n\n## TL;DR\n\nproof stale")
            write_text(root / "docs" / "recovery" / "current-truth.md", "# Truth\n\n## Verdict\n\nMovement was allowed.")
            write_json(
                root / "docs" / "recovery" / "current-truth.json",
                {
                    "status": "current-target-proofonly-passed",
                    "updatedAtUtc": "2026-05-27T07:00:00Z",
                    "target": {"processName": "rift_x64", "processId": 12148, "targetWindowHandle": "0x640C0C"},
                    "movementGate": {
                        "allowed": True,
                        "status": "allowed-current-target-proofonly-passed-route-smoke-passed",
                        "reason": "historically allowed",
                    },
                    "currentBlockers": [],
                    "nextRecommendedAction": "historical next action",
                },
            )
            write_json(
                root / "docs" / "recovery" / "current-proof-anchor-readback.json",
                {
                    "status": "current-target-proofonly-passed",
                    "lastUpdatedUtc": "2026-05-27T07:00:00Z",
                    "target": {"processName": "rift_x64", "processId": 12148, "targetWindowHandle": "0x640C0C"},
                    "latestValidation": {
                        "status": "valid",
                        "movementAllowed": True,
                        "movementSent": False,
                        "generatedAtUtc": "2026-05-27T07:00:00Z",
                    },
                    "latestProofOnly": {
                        "status": "passed-proof-only",
                        "movementSent": False,
                        "movementAttempted": False,
                        "generatedAtUtc": "2026-05-27T07:00:00Z",
                    },
                },
            )

            packet = status_packet.build_status_packet(
                root,
                run_coordinate_status=False,
                check_opencode=False,
                collect_git_state=False,
                now=datetime(2026, 5, 27, 7, 2, tzinfo=timezone.utc),
            )

        movement_gate = packet["currentTruth"]["summary"]["movementGate"]
        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(movement_gate["allowed"])
        self.assertEqual(movement_gate["status"], "blocked-proof-anchor-age-out-of-range")
        self.assertEqual(movement_gate["proofFreshness"]["ageSeconds"], 120)
        self.assertIn("proof-anchor-stale-for-movement:ageSeconds=120;maxAgeSeconds=60", packet["blockers"])
        self.assertIn("movement-not-allowed:blocked-proof-anchor-age-out-of-range", packet["blockers"])
        self.assertIn("same-target ProofOnly/proof-anchor refresh", packet["nextRecommendedAction"])

    def test_compact_summary_reports_static_owner_navigation_bridge_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_text(root / "scripts" / "riftreader-actor-chain-no-debug-status.cmd", "@echo off\n")
            write_text(root / "scripts" / "static-owner-coordinate-chain-readback.cmd", "@echo off\n")
            write_text(root / "scripts" / "static-owner-nav-now.cmd", "@echo off\n")
            write_text(root / "scripts" / "static-owner-turn-aware-route-plan.cmd", "@echo off\n")
            write_text(root / "scripts" / "static-owner-nav-report-route-run.cmd", "@echo off\n")
            packet = {
                "schemaVersion": 1,
                "kind": "riftreader-local-workflow-status-packet",
                "generatedAtUtc": "2026-05-28T00:00:00Z",
                "status": "passed",
                "repoRoot": str(root),
                "blockers": [],
                "warnings": [],
                "errors": [],
                "git": {},
                "liveTarget": {},
                "launcher": {},
                "currentProof": {"summary": {}},
                "currentTruth": {"summary": {}},
                "latestHandoff": {},
                "coordinateRecoveryStatus": {},
                "opencode": {"retired": True, "checked": False},
                "safety": {"movementSent": False, "gitMutation": False},
                "nextRecommendedAction": "none",
                "artifacts": {},
            }

            compact = status_packet.compact_summary(packet)

        commands = {item["key"]: item for item in compact["bridgeCommands"]}
        self.assertTrue(commands["actor-chain-no-debug-status"]["exists"])
        self.assertIn("no promotion", commands["actor-chain-no-debug-status"]["safety"])
        self.assertTrue(commands["static-owner-coordinate-chain-readback"]["exists"])
        self.assertIn("live target memory readback only", commands["static-owner-coordinate-chain-readback"]["safety"])
        self.assertTrue(commands["static-owner-nav-now"]["exists"])
        self.assertIn("candidate-facing readback only", commands["static-owner-nav-now"]["safety"])
        self.assertTrue(commands["static-owner-turn-aware-plan"]["exists"])
        self.assertIn("dry-run route/turn planning only", commands["static-owner-turn-aware-plan"]["safety"])
        self.assertTrue(commands["static-owner-route-run-report"]["exists"])
        self.assertIn("saved route-run report only", commands["static-owner-route-run-report"]["safety"])


if __name__ == "__main__":
    unittest.main()
