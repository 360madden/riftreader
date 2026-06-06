#!/usr/bin/env python3
# Purpose: Regression checks for durable ChatGPT MCP workflow documentation.
from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class ChatGptMcpWorkflowDocsTests(unittest.TestCase):
    def read_doc(self, relative_path: str) -> str:
        return (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    def test_mcp_doc_preserves_existing_launcher_inventory(self) -> None:
        text = self.read_doc("docs/workflow/riftreader-chatgpt-mcp.md")
        self.assertIn("Non-Codex runtime invariant and existing launcher inventory", text)
        self.assertIn("scripts\\riftreader-chatgpt-mcp.cmd", text)
        self.assertIn("--operator-launch-plan", text)
        self.assertIn("scripts\\riftreader-bridge-tunnel-session.cmd", text)
        self.assertIn("Do not recreate it under a new name", text)
        self.assertIn("do not fork the workflow into another near-duplicate script", text)

    def test_mcp_doc_preserves_manual_public_ip_and_retired_tunnel_paths(self) -> None:
        text = self.read_doc("docs/workflow/riftreader-chatgpt-mcp.md")
        self.assertIn("manual external-IP Server URL", text)
        self.assertIn("--manual-public-ip-plan --public-mcp-host <current-external-ip> --json", text)
        self.assertIn("manual-public-ip", text)
        self.assertIn("OpenAI Secure MCP Tunnel", text)
        self.assertIn("not backup paths", text)
        self.assertIn("trycloudflare.com", text)

    def test_non_codex_policy_blocks_codex_owned_runtime_as_final_proof(self) -> None:
        text = self.read_doc("docs/workflow/non-codex-desktop-chatgpt-workflow.md")
        self.assertIn("ChatGPT MCP runtime rule", text)
        self.assertIn("scripts\\riftreader-chatgpt-mcp.cmd --operator-launch-plan --json", text)
        self.assertIn("--manual-public-ip-plan", text)
        self.assertIn("the MCP runtime must be", text)
        self.assertIn("started by the operator outside Codex", text)
        self.assertIn("A Codex-launched", text)
        self.assertIn("not final\nproof", text)

    def test_agents_policy_points_to_existing_mcp_adapter(self) -> None:
        text = self.read_doc("AGENTS.md")
        self.assertIn("ChatGPT MCP runtime invariant", text)
        self.assertIn("scripts\\riftreader-chatgpt-mcp.cmd", text)
        self.assertIn("Do not confuse `scripts\\riftreader-bridge-tunnel-session.cmd`", text)


if __name__ == "__main__":
    unittest.main()
