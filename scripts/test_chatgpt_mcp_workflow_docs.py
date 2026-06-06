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
        self.assertIn("scripts\\riftreader-bridge-tunnel-session.cmd", text)
        self.assertIn("Do not recreate it under a new name", text)
        self.assertIn("do not fork the workflow into another near-duplicate script", text)

    def test_mcp_doc_preserves_primary_and_deprecated_paths(self) -> None:
        text = self.read_doc("docs/workflow/riftreader-chatgpt-mcp.md")
        self.assertIn("OpenAI Secure MCP Tunnel", text)
        self.assertIn("Cloudflare quick tunnels and ngrok-style public URLs are now fallback/dev-only", text)
        self.assertIn("trycloudflare.com", text)
        self.assertIn("--chatgpt-trial-session --chatgpt-session-seconds 3600 --json", text)

    def test_non_codex_policy_blocks_codex_owned_runtime_as_final_proof(self) -> None:
        text = self.read_doc("docs/workflow/non-codex-desktop-chatgpt-workflow.md")
        self.assertIn("ChatGPT MCP runtime rule", text)
        self.assertIn("the MCP runtime must be", text)
        self.assertIn("started by the operator outside Codex", text)
        self.assertIn("A Codex-launched", text)
        self.assertIn("is not final proof", text)

    def test_agents_policy_points_to_existing_mcp_adapter(self) -> None:
        text = self.read_doc("AGENTS.md")
        self.assertIn("ChatGPT MCP runtime invariant", text)
        self.assertIn("scripts\\riftreader-chatgpt-mcp.cmd", text)
        self.assertIn("Do not confuse `scripts\\riftreader-bridge-tunnel-session.cmd`", text)


if __name__ == "__main__":
    unittest.main()
