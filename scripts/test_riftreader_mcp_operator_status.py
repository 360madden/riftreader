#!/usr/bin/env python3
# Version: riftreader-mcp-operator-status-tests-v0.1.0
# Purpose: Unit tests for operator-facing ChatGPT MCP connection guidance.

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.riftreader_mcp.operator_status import build_blockers, build_chatgpt_connection_guidance  # noqa: E402


class RiftReaderMcpOperatorStatusTests(unittest.TestCase):
    def test_public_static_bearer_route_is_diagnostic_not_chatgpt_ready(self) -> None:
        tunnel = {
            "status": "blocked",
            "blockers": [
                "Install tunnel-client or set TUNNEL_CLIENT_EXE to its full path.",
                "Set CONTROL_PLANE_TUNNEL_ID to the OpenAI tunnel id for this ChatGPT app.",
            ],
        }

        guidance = build_chatgpt_connection_guidance(
            public_ready=True,
            auth_required=True,
            openai_tunnel_runtime=tunnel,
        )
        blockers = build_blockers(
            public_ready=True,
            auth_required=True,
            openai_tunnel_runtime=tunnel,
        )

        self.assertTrue(guidance["publicHostnameDiagnosticReady"])
        self.assertFalse(guidance["directPublicHostnameChatGptReady"])
        self.assertIn("static bearer token", guidance["directPublicHostnameBlockedReason"])
        self.assertIn("Secure MCP Tunnel", guidance["whySecureTunnelPreferredForCurrentAuth"])
        self.assertTrue(any("static bearer-token auth" in item for item in blockers))

    def test_noauth_public_route_can_be_marked_direct_ready(self) -> None:
        guidance = build_chatgpt_connection_guidance(
            public_ready=True,
            auth_required=False,
            openai_tunnel_runtime={"status": "blocked", "blockers": []},
        )

        self.assertTrue(guidance["directPublicHostnameChatGptReady"])
        self.assertIsNone(guidance["directPublicHostnameBlockedReason"])


if __name__ == "__main__":
    unittest.main()
