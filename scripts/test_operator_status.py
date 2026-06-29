#!/usr/bin/env python3
# Version: riftreader-test-operator-status-v0.2.0
# Total-Character-Count: 0000004092
# Purpose: Unit tests for the Stage 51 unified RiftReader operator status packet.

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.riftreader_workflow.operator_status import (  # noqa: E402
    compact_artifact,
    render_md,
    select_recommended_actions,
    self_test,
)


class OperatorStatusTests(unittest.TestCase):
    def test_self_test_passes(self) -> None:
        payload = self_test()
        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])

    def test_render_markdown_contains_unified_status_rows(self) -> None:
        payload = {
            "status": "passed",
            "generatedAtUtc": "2026-06-29T00:00:00Z",
            "overallState": "blocked",
            "git": {"branch": "main", "upstream": "origin/main", "ahead": 0, "behind": 0, "dirty": False, "headShort": "abc1234"},
            "handoff": {"pointerTarget": "docs\\handoffs\\latest.md", "newestTrackedHandoffPath": "docs\\handoffs\\latest.md"},
            "mcpRuntime": {"status": "blocked-query-failed", "ok": False, "localMcpUrl": "http://127.0.0.1:8770/mcp", "listenerCount": 0, "stdioCounterparts": {"count": 2}},
            "finalReadiness": {"status": "blocked", "ok": False, "blockers": ["proof:stale"], "warningCount": 1},
            "workflowArtifacts": {
                "latest": {
                    "trialReadiness": {"status": "stale", "ageSeconds": 10, "path": "readiness.json"},
                    "proposalSmoke": {"status": "fresh", "ageSeconds": 1, "path": "proposal.json"},
                    "actualClientProof": {"status": "stale", "ageSeconds": 20, "path": "proof.json"},
                }
            },
            "riftTargets": {"processCount": 0, "windowCount": 0},
            "decisionPacket": {"status": "blocked", "lane": "proof-recovery", "risk": "high"},
            "recommendedNextAction": {
                "key": "refresh-trial-readiness",
                "source": "finalReadiness",
                "why": "refresh",
                "command": ["scripts\\riftreader-operator-lite.cmd", "--mcp-trial-readiness", "--json"],
            },
            "safety": {"movementSent": False, "inputSent": False, "noCheatEngine": True},
        }
        rendered = render_md(payload)
        self.assertIn("RiftReader Unified Operator Status", rendered)
        self.assertIn("origin/main", rendered)
        self.assertIn("http://127.0.0.1:8770/mcp", rendered)
        self.assertIn("refresh-trial-readiness", rendered)

    def test_compact_artifact_classifies_missing_and_stale(self) -> None:
        self.assertEqual(compact_artifact("actual-client-proof", None)["status"], "missing")
        stale = compact_artifact("actual-client-proof", {"path": "proof.json", "artifactAgeSeconds": 90000, "status": "passed"})
        self.assertEqual(stale["status"], "stale")
        self.assertFalse(stale["fresh"])
        self.assertTrue(stale["passed"])

    def test_select_recommended_actions_orders_final_runtime_decision_target(self) -> None:
        payload = {
            "finalReadiness": {"recommendedNextAction": {"key": "refresh-trial-readiness", "reason": "stale", "command": ["trial"]}},
            "mcpRuntime": {"ok": False},
            "decisionPacket": {"safeNextAction": {"key": "refresh-targets", "why": "target drift", "command": ["targets"]}},
            "riftTargets": {"count": 0},
        }
        actions = select_recommended_actions(payload)
        self.assertEqual(actions[0]["key"], "refresh-trial-readiness")
        self.assertIn("start-full-http-mcp-runtime", [item["key"] for item in actions])
        self.assertIn("refresh-targets", [item["key"] for item in actions])
        self.assertIn("manual-start-rift-then-refresh-status", [item["key"] for item in actions])


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
