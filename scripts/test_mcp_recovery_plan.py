#!/usr/bin/env python3
"""Tests for the Stage 52 MCP readiness recovery plan."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.riftreader_workflow.mcp_recovery_plan import build_plan_from_status, self_test  # noqa: E402


def sample_status(*, final_ok: bool = False, runtime_ok: bool = False, blockers: list[str] | None = None) -> dict[str, object]:
    final_blockers = blockers if blockers is not None else ["proof:stale", "artifact:trial-readiness-stale", "artifact:proposal-smoke-stale"]
    return {
        "kind": "riftreader-unified-operator-status",
        "generatedAtUtc": "2026-06-29T00:00:00Z",
        "overallState": "ready" if final_ok and runtime_ok else "blocked",
        "git": {"dirty": False},
        "finalReadiness": {"ok": final_ok, "status": "passed" if final_ok else "blocked", "blockers": [] if final_ok else final_blockers},
        "mcpRuntime": {
            "ok": runtime_ok,
            "status": "running-current" if runtime_ok else "blocked-query-failed",
            "blockers": [] if runtime_ok else ["local-mcp-server-listener-query-failed"],
            "dependencySequence": [],
        },
        "workflowArtifacts": {
            "latest": {
                "trialReadiness": {"status": "fresh" if final_ok else "stale"},
                "proposalSmoke": {"status": "fresh" if final_ok else "stale"},
                "actualClientProof": {"status": "fresh" if final_ok else "stale"},
            }
        },
        "riftTargets": {"count": 0},
        "decisionPacket": {"blockers": [], "safeNextAction": {"command": []}},
    }


class McpRecoveryPlanTests(unittest.TestCase):
    def test_self_test_passes(self) -> None:
        payload = self_test()
        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])

    def test_stale_proof_and_missing_runtime_emit_ordered_steps(self) -> None:
        plan = build_plan_from_status(Path("C:/RIFT MODDING/RiftReader"), sample_status())
        keys = [step["key"] for step in plan["steps"]]
        self.assertEqual(plan["status"], "blocked")
        self.assertIn("refresh-trial-readiness", keys)
        self.assertIn("refresh-proposal-transport-smoke", keys)
        self.assertIn("start-full-http-mcp-runtime", keys)
        self.assertIn("refresh-actual-client-proof", keys)
        runtime_step = next(step for step in plan["steps"] if step["key"] == "start-full-http-mcp-runtime")
        self.assertFalse(runtime_step["autoRunAllowed"])
        self.assertTrue(runtime_step["operatorStep"])
        self.assertTrue(runtime_step["commands"][0]["startsRuntime"])

    def test_passed_final_gate_keeps_only_deferred_and_verification_steps(self) -> None:
        plan = build_plan_from_status(Path("C:/RIFT MODDING/RiftReader"), sample_status(final_ok=True, runtime_ok=True))
        release_steps = [step for step in plan["steps"] if step["releaseBlocker"]]
        self.assertEqual(release_steps, [])
        self.assertEqual(plan["status"], "passed")

    def test_ci_in_progress_maps_to_wait_and_recheck(self) -> None:
        plan = build_plan_from_status(
            Path("C:/RIFT MODDING/RiftReader"),
            sample_status(blockers=["phase2:not-ready", "ci:not-completed:RiftReader Policy:in_progress"]),
        )
        keys = [step["key"] for step in plan["steps"]]
        self.assertIn("wait-for-ci-then-recheck-final-readiness", keys)


if __name__ == "__main__":
    unittest.main()

