#!/usr/bin/env python3
# Purpose: Regression checks for the Stage 48 ChatGPT MCP eval-suite checklist.
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import chatgpt_mcp_eval_suite as eval_suite  # noqa: E402
from riftreader_workflow import mcp_tool_surface  # noqa: E402


class ChatGptMcpEvalSuiteTests(unittest.TestCase):
    def test_build_eval_suite_covers_profiles_denials_and_actual_client_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = eval_suite.build_eval_suite(Path(temp_dir))

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["stage"], 48)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["toolSurface"]["fullProfile"]["toolCount"], mcp_tool_surface.EXPECTED_CHATGPT_MCP_TOOL_COUNT)
        self.assertEqual(
            payload["toolSurface"]["publicReadOnlyProfile"]["toolCount"],
            mcp_tool_surface.PUBLIC_READ_ONLY_TOOL_COUNT,
        )
        command_keys = {item["key"] for item in payload["localEvalCommands"]}
        self.assertIn("stage48-focused-unit-tests", command_keys)
        self.assertIn("stage48-broader-mcp-regression", command_keys)
        self.assertIn("sdk-validate-full", command_keys)
        self.assertIn("sdk-validate-public-read-only", command_keys)
        self.assertTrue(all(not item["startsServer"] for item in payload["localEvalCommands"]))
        self.assertTrue(all(not item["startsTunnel"] for item in payload["localEvalCommands"]))
        self.assertTrue(all(not item["mutatesRepo"] for item in payload["localEvalCommands"]))

        matrix = {item["key"]: item for item in payload["evalMatrix"]}
        self.assertIn("auth-profile-policy", matrix)
        self.assertIn("APPLY_APPROVAL_MISSING", matrix["package-apply-denial"]["expectedBlockers"])
        self.assertIn("COMMIT_APPROVAL_MISSING", matrix["commit-denial"]["expectedBlockers"])
        self.assertIn("PUSH_APPROVAL_MISSING", matrix["push-denial"]["expectedBlockers"])
        self.assertIn("LIVE_APPROVAL_MISSING", matrix["live-control-denial"]["expectedBlockers"])
        self.assertIn("DEBUGGER_APPROVAL_MISSING", matrix["debugger-ce-denial"]["expectedBlockers"])

        checklist = payload["actualClientChecklist"]
        self.assertEqual(checklist["serverUrl"], "https://mcp.360madden.com/mcp")
        self.assertEqual(checklist["authMode"], "No Authentication")
        self.assertEqual(checklist["requiredObservedFields"]["toolCount"], mcp_tool_surface.EXPECTED_CHATGPT_MCP_TOOL_COUNT)
        self.assertEqual(checklist["requiredObservedFields"]["toolOutputSchemaCount"], mcp_tool_surface.EXPECTED_CHATGPT_MCP_TOOL_COUNT)
        self.assertEqual(checklist["requiredObservedFields"]["clientTransportStatus"], "tool-call-succeeded")
        self.assertTrue(checklist["requiredObservedFields"]["authRolePolicyObserved"])
        self.assertFalse(payload["safety"]["serverStarted"])
        self.assertFalse(payload["safety"]["publicTunnelStarted"])
        self.assertFalse(payload["safety"]["gitMutation"])
        self.assertFalse(payload["safety"]["inputSent"])
        self.assertFalse(payload["safety"]["x64dbgAttach"])

    def test_write_eval_suite_writes_only_ignored_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = eval_suite.write_eval_suite(root)

            artifacts = payload["artifactPaths"]
            summary_json = root / artifacts["summaryJson"]
            summary_md = root / artifacts["summaryMarkdown"]
            latest_json = root / artifacts["latestJson"]
            latest_md = root / artifacts["latestMarkdown"]

            self.assertTrue(summary_json.is_file())
            self.assertTrue(summary_md.is_file())
            self.assertTrue(latest_json.is_file())
            self.assertTrue(latest_md.is_file())
            self.assertTrue(summary_json.is_relative_to(root / ".riftreader-local"))
            self.assertTrue(summary_md.is_relative_to(root / ".riftreader-local"))
            round_trip = json.loads(summary_json.read_text(encoding="utf-8"))

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["safety"]["localIgnoredArtifactWrite"])
        self.assertEqual(round_trip["kind"], "riftreader-chatgpt-mcp-stage48-eval-suite")

    def test_render_markdown_includes_eval_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            markdown = eval_suite.render_markdown(eval_suite.build_eval_suite(Path(temp_dir)))

        self.assertIn("Stage 48 eval suite", markdown)
        self.assertIn("Local eval commands", markdown)
        self.assertIn("Denial / proof matrix", markdown)
        self.assertIn("Actual-client checklist", markdown)
        self.assertIn("APPLY_APPROVAL_MISSING", markdown)


if __name__ == "__main__":
    unittest.main()
