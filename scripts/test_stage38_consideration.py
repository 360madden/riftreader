#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import stage38_consideration as stage38  # noqa: E402
from riftreader_workflow.mcp_tool_surface import EXPECTED_CHATGPT_MCP_TOOL_COUNT  # noqa: E402


def final_payload(*, ok: bool = True) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "passed" if ok else "blocked",
        "ok": ok,
        "blockers": [] if ok else [f"proof:replay-failed:tool-count-not-{EXPECTED_CHATGPT_MCP_TOOL_COUNT}:20"],
        "warnings": [],
        "currentHead": "012345",
        "ci": {"status": "passed", "ok": True},
        "phase2": {
            "status": "passed" if ok else "blocked",
            "ok": ok,
            "ciStatus": {"status": "passed", "ok": True, "currentHead": "012345", "blockers": []},
            "proofReplay": {
                "status": "passed" if ok else "blocked",
                "ok": ok,
                "blockers": [] if ok else [f"tool-count-not-{EXPECTED_CHATGPT_MCP_TOOL_COUNT}:20"],
                "proofFreshness": {"status": "fresh"},
            },
            "artifactFreshness": {
                "status": "fresh",
                "items": {
                    "readiness": {"status": "fresh"},
                    "proposal-smoke": {"status": "fresh"},
                },
            },
        },
        "artifacts": {"freshness": {"status": "fresh"}},
        "recommendedNextAction": {
            "key": "check-actual-client-proof-input",
            "command": ["scripts\\riftreader-chatgpt-trial-recorder.cmd", "--check-input"],
        },
        "safety": {},
    }
    return payload


def runtime_payload(*, ok: bool = True) -> dict[str, object]:
    return {
        "status": "running-current" if ok else "not-running",
        "ok": ok,
        "blockers": [] if ok else ["local-backend-not-running:127.0.0.1:8770"],
        "warnings": [],
        "selectedListener": {"owningProcess": 1234} if ok else None,
        "runtimeSurface": {
            "status": "passed" if ok else "blocked",
            "ok": ok,
            "observedToolCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT if ok else 0,
        },
        "runtimeSourceFreshness": {"status": "passed" if ok else "blocked", "ok": ok},
        "stdioCounterparts": {"status": "not-running", "ok": True},
    }


def tunnel_payload(*, ok: bool = True) -> dict[str, object]:
    return {
        "status": "passed" if ok else "blocked",
        "ok": ok,
        "blockers": [] if ok else ["public-route-probe-failed"],
        "warnings": [],
        "publicMcpUrl": stage38.DEFAULT_PUBLIC_MCP_URL,
        "connectionMode": "cloudflare-named-tunnel",
        "publicRouteProbe": {"status": "passed" if ok else "blocked", "ok": ok},
        "localRuntime": {"status": "running-current", "ok": True},
    }


class Stage38ConsiderationTests(unittest.TestCase):
    def status(
        self,
        *,
        final_ok: bool = True,
        runtime_ok: bool = True,
        tunnel_ok: bool = True,
        approval_token: str | None = None,
    ) -> dict[str, object]:
        return stage38.build_stage38_consideration_status(
            REPO_ROOT,
            approval_token=approval_token,
            final_payload=final_payload(ok=final_ok),
            runtime_payload=runtime_payload(ok=runtime_ok),
            tunnel_payload=tunnel_payload(ok=tunnel_ok),
        )

    def test_all_prerequisites_require_explicit_live_boundary_approval(self) -> None:
        payload = self.status()

        self.assertEqual(payload["status"], "approval-required")
        self.assertFalse(payload["ok"])
        self.assertIn("stage38:explicit-live-boundary-approval-required", payload["blockers"])
        self.assertFalse(payload["stage38Started"])

    def test_approved_prerequisites_pass_without_starting_stage38(self) -> None:
        payload = self.status(approval_token=stage38.STAGE38_APPROVAL_TOKEN)

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["stage38Started"])
        self.assertFalse(payload["stage38Active"])
        self.assertFalse(payload["safety"]["inputSent"])  # type: ignore[index]
        self.assertFalse(payload["safety"]["movementSent"])  # type: ignore[index]

    def test_final_readiness_blocks_stage38_consideration(self) -> None:
        payload = self.status(final_ok=False)

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("stage38:final-readiness-not-passed:blocked", payload["blockers"])
        self.assertIn(f"proof:replay-failed:tool-count-not-{EXPECTED_CHATGPT_MCP_TOOL_COUNT}:20", payload["blockers"])
        self.assertEqual(payload["recommendedNextAction"]["key"], "check-actual-client-proof-input")  # type: ignore[index]

    def test_runtime_not_current_blocks_before_final_proof_work(self) -> None:
        payload = self.status(runtime_ok=False, final_ok=False)

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("stage38:mcp-runtime-not-current:not-running", payload["blockers"])
        self.assertEqual(payload["recommendedNextAction"]["key"], "fix-mcp-runtime-before-stage38")  # type: ignore[index]

    def test_tunnel_failure_blocks_after_runtime(self) -> None:
        payload = self.status(tunnel_ok=False)

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("stage38:public-route-not-passed:blocked", payload["blockers"])
        self.assertEqual(payload["recommendedNextAction"]["key"], "fix-cloudflare-route-before-stage38")  # type: ignore[index]

    def test_self_test_passes(self) -> None:
        payload = stage38.self_test()

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])

    def test_approval_packet_ready_to_review_when_prerequisites_wait_for_approval(self) -> None:
        status = self.status()

        packet = stage38.build_stage38_approval_packet(status)

        self.assertEqual(packet["status"], "ready-to-review")
        self.assertTrue(packet["ok"])
        self.assertFalse(packet["stage38Started"])
        self.assertIn(stage38.STAGE38_APPROVAL_TOKEN, packet["markdown"])
        self.assertIn("--approval-token", packet["approvalCommand"])

    def test_approval_packet_blocks_when_consideration_gate_is_blocked(self) -> None:
        status = self.status(final_ok=False)

        packet = stage38.build_stage38_approval_packet(status)

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["ok"])
        self.assertIn("stage38-approval-packet-not-ready:blocked", packet["blockers"])
        self.assertIn(f"proof:replay-failed:tool-count-not-{EXPECTED_CHATGPT_MCP_TOOL_COUNT}:20", packet["blockers"])
        self.assertFalse(packet["safety"]["stage38Started"])  # type: ignore[index]
        self.assertFalse(packet["safety"]["inputSent"])  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
