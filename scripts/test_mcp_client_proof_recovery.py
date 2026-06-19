#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import mcp_client_proof_recovery as recovery  # noqa: E402
from riftreader_workflow import mcp_tool_surface as surface  # noqa: E402


def server_payload(tool_count: int | None = None) -> dict[str, object]:
    count = surface.EXPECTED_CHATGPT_MCP_TOOL_COUNT if tool_count is None else tool_count
    names = list(surface.EXPECTED_CHATGPT_MCP_TOOL_NAMES[:count])
    return {
        "status": "running-current",
        "ok": True,
        "localMcpUrl": "http://127.0.0.1:8770/mcp",
        "runtimeSurface": {
            "status": "passed" if count == surface.EXPECTED_CHATGPT_MCP_TOOL_COUNT else "blocked",
            "ok": count == surface.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
            "expectedToolCount": surface.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
            "observedToolCount": count,
            "observedToolNames": names,
            "healthToolCount": count,
        },
    }


def domain_payload(ok: bool = True) -> dict[str, object]:
    return {"status": "passed" if ok else "blocked", "ok": ok, "publicSmoke": {"ok": ok}}


def proof_payload(tool_count: int | None = None) -> dict[str, object]:
    count = surface.EXPECTED_CHATGPT_MCP_TOOL_COUNT if tool_count is None else tool_count
    names = list(surface.EXPECTED_CHATGPT_MCP_TOOL_NAMES[:count])
    return {
        "status": "passed" if count == surface.EXPECTED_CHATGPT_MCP_TOOL_COUNT else "blocked",
        "ok": count == surface.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        "proofPath": ".riftreader-local\\proof.json",
        "proofSummary": {
            "toolCount": count,
            "toolNames": names,
            "toolOutputSchemaCount": count,
            "toolOutputSchemaToolNames": names,
            "clientTransportStatus": "tool-call-succeeded",
            "healthCallSucceeded": True,
        },
    }


def template_state(current: bool = True) -> dict[str, object]:
    return {"status": "current" if current else "stale-or-invalid", "ok": current, "current": current, "path": "proof-input.json"}


class McpClientProofRecoveryTests(unittest.TestCase):
    def test_classifies_stale_actual_client_when_backend_and_route_are_current(self) -> None:
        payload = recovery.classify_recovery_state(
            server_payload=server_payload(),
            domain_payload=domain_payload(),
            final_payload={
                "status": "blocked",
                "ok": False,
                "blockers": [f"proof:replay-failed:tool-count-not-{surface.EXPECTED_CHATGPT_MCP_TOOL_COUNT}:39"],
            },
            proof_payload=proof_payload(surface.EXPECTED_CHATGPT_MCP_TOOL_COUNT - 1),
            template_state=template_state(),
        )

        self.assertEqual(payload["status"], "blocked-actual-client-refresh-required")
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["actualClientRefreshRequired"])
        self.assertIn(surface.EXPECTED_CHATGPT_MCP_TOOL_NAMES[-1], payload["actualClientProof"]["missingToolsFromProof"])

    def test_classifies_passed_when_final_gate_is_ready(self) -> None:
        payload = recovery.classify_recovery_state(
            server_payload=server_payload(),
            domain_payload=domain_payload(),
            final_payload={"status": "passed", "ok": True, "blockers": []},
            proof_payload=proof_payload(),
            template_state=template_state(),
        )

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["actualClientRefreshRequired"])

    def test_classifies_local_recovery_when_backend_is_not_current(self) -> None:
        payload = recovery.classify_recovery_state(
            server_payload={"status": "missing", "ok": False},
            domain_payload=domain_payload(False),
            final_payload={"status": "blocked", "ok": False, "blockers": []},
            proof_payload=proof_payload(surface.EXPECTED_CHATGPT_MCP_TOOL_COUNT - 1),
            template_state=template_state(False),
        )

        self.assertEqual(payload["status"], "blocked-local-recovery-required")
        self.assertFalse(payload["actualClientRefreshRequired"])
        self.assertIn("backend:not-running-current", payload["localBlockers"])
        self.assertIn("public-route:not-passed", payload["localBlockers"])
        self.assertIn("proof-template:not-current", payload["localBlockers"])


if __name__ == "__main__":
    unittest.main()
