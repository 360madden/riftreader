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

    def test_mcp_doc_preserves_cloudflare_named_tunnel_route_and_deprecated_legacy_paths(self) -> None:
        text = self.read_doc("docs/workflow/riftreader-chatgpt-mcp.md")
        self.assertIn("public-host/domain Server URL", text)
        self.assertIn("--manual-public-ip-plan --public-mcp-host mcp.360madden.com --json", text)
        self.assertIn("--proof-run-packet-md", text)
        self.assertIn("https://mcp.360madden.com/mcp", text)
        self.assertIn("Cloudflare named Tunnel", text)
        self.assertIn("riftreader-mcp-360madden", text)
        self.assertIn("http://127.0.0.1:8770", text)
        self.assertIn("Caddy/router/direct public-IP route", text)
        self.assertIn("deprecated", text)
        self.assertIn("OpenAI Secure MCP Tunnel", text)
        self.assertIn("not backups", text)
        self.assertIn("trycloudflare.com", text)

    def test_non_codex_policy_blocks_codex_owned_runtime_as_final_proof(self) -> None:
        text = self.read_doc("docs/workflow/non-codex-desktop-chatgpt-workflow.md")
        self.assertIn("ChatGPT MCP runtime rule", text)
        self.assertIn("scripts\\riftreader-chatgpt-mcp.cmd --operator-launch-plan --json", text)
        self.assertIn("--manual-public-ip-plan", text)
        self.assertIn("--proof-run-packet-md", text)
        self.assertIn("Cloudflare named Tunnel", text)
        self.assertIn("riftreader-mcp-360madden", text)
        self.assertIn("the MCP runtime must be", text)
        self.assertIn("started by the operator outside Codex", text)
        self.assertIn("A Codex-launched", text)
        self.assertIn("not final\nproof", text)

    def test_agents_policy_points_to_existing_mcp_adapter(self) -> None:
        text = self.read_doc("AGENTS.md")
        self.assertIn("ChatGPT MCP runtime invariant", text)
        self.assertIn("scripts\\riftreader-chatgpt-mcp.cmd", text)
        self.assertIn("Do not confuse `scripts\\riftreader-bridge-tunnel-session.cmd`", text)

    def test_bounded_command_design_forbids_arbitrary_shell_and_live_actions(self) -> None:
        text = self.read_doc("docs/workflow/riftreader-chatgpt-mcp-bounded-command-design.md")
        self.assertIn("Stage: **32", text)
        self.assertIn("run_bounded_repo_command", text)
        self.assertIn("versioned allowlist registry", text)
        self.assertIn("argvTemplate", text)
        self.assertIn("Arbitrary shell", text)
        self.assertIn("Live RIFT input", text)
        self.assertIn("Provider writes", text)
        self.assertIn("Debugger/CE", text)
        self.assertIn("does not accept shell strings", text)
        self.assertIn("stage38_consideration_status", text)
        self.assertIn("stage38_approval_packet", text)
        self.assertIn("Does not add an MCP tool or start live RIFT tooling", text)

    def test_mcp_doc_includes_runtime_and_proof_status_tools(self) -> None:
        text = self.read_doc("docs/workflow/riftreader-chatgpt-mcp.md")
        self.assertIn("37-tool narrow adapter", text)
        self.assertIn("get_mcp_runtime_status", text)
        self.assertIn("get_tool_surface_diff", text)
        self.assertIn("run_mcp_restart_preflight", text)
        self.assertIn("restart_mcp_runtime", text)
        self.assertIn("get_tunnel_status", text)
        self.assertIn("get_chatgpt_connector_setup_packet", text)
        self.assertIn("get_final_readiness_status", text)
        self.assertIn("submit_actual_client_observation", text)
        self.assertIn("get_actual_client_proof_status", text)
        self.assertIn("get_live_rift_readonly_state", text)
        self.assertIn("get_live_target_identity_gate", text)
        self.assertIn("get_live_no_input_proof_status", text)
        self.assertIn("plan_live_control_action", text)
        self.assertIn("list_bounded_repo_commands", text)
        self.assertIn("final 37-tool proof", text)

    def test_stage38_docs_record_no_input_surface_and_historical_consideration_gate(self) -> None:
        plan = self.read_doc("docs/workflow/riftreader-chatgpt-mcp-50-stage-plan.md")
        final = self.read_doc("docs/workflow/riftreader-chatgpt-mcp-final-readiness.md")
        live_control = self.read_doc("docs/workflow/riftreader-chatgpt-mcp-live-control-design.md")
        self.assertIn("scripts\\riftreader-stage38-consideration.cmd --status --compact-json", plan)
        self.assertIn("scripts\\riftreader-stage38-consideration.cmd --write-approval-packet --json", plan)
        self.assertIn("get_live_rift_readonly_state", plan)
        self.assertIn("get_live_target_identity_gate", plan)
        self.assertIn("get_live_no_input_proof_status", plan)
        self.assertIn("read-only/no-input", plan)
        self.assertIn("Stage 38 consideration guard", final)
        self.assertIn("approval-required", final)
        self.assertIn("--write-approval-packet", final)
        self.assertIn("never starts live RIFT tooling", final)
        self.assertIn("clientTransportStatus=tool-call-succeeded", final)
        self.assertIn("healthCallSucceeded=true", final)
        self.assertIn("Codex Apps wrapper", final)
        self.assertIn("does not replace the\n   non-Codex ChatGPT Web/Desktop actual-client proof", final)
        self.assertIn("Transport closed", plan)
        self.assertIn("not a substitute for the non-Codex ChatGPT Web/Desktop proof artifact", plan)
        self.assertIn("prior 19-tool product", plan)
        self.assertNotIn("current 19-tool product", plan)
        self.assertIn("current ChatGPT Web/Desktop proof contract\nis 37 tools", live_control)
        self.assertIn("clientTransportStatus=tool-call-succeeded", live_control)
        self.assertIn("healthCallSucceeded=true", live_control)
        self.assertIn("Transport closed", live_control)
        self.assertNotIn("current 19-tool", live_control)

    def test_stage41_live_control_design_is_non_executing_and_separates_risks(self) -> None:
        plan = self.read_doc("docs/workflow/riftreader-chatgpt-mcp-50-stage-plan.md")
        live_control = self.read_doc("docs/workflow/riftreader-chatgpt-mcp-live-control-design.md")
        self.assertIn("Post-Stage-42 live-control plan-only surface", plan)
        self.assertIn("Stage 41 is a\ndesign-only live-control boundary", plan)
        self.assertIn("Stage 43 is the next implementation boundary", plan)
        self.assertIn("| 41 | Live movement/control design spec", plan)
        self.assertIn("without changing the tool surface. | complete-local |", plan)
        self.assertIn("Stage 42 complete-local plan-only surface", live_control)
        self.assertIn("Design contract only; no new MCP tool", live_control)
        self.assertIn("Stage 41 design contract", live_control)
        self.assertIn("Action taxonomy", live_control)
        self.assertIn("no-input-read", live_control)
        self.assertIn("ui-action", live_control)
        self.assertIn("displacement-stimulus", live_control)
        self.assertIn("movement-control", live_control)
        self.assertIn("proof-only", live_control)
        self.assertIn("Required future plan envelope", live_control)
        self.assertIn("never a reusable broad approval token", live_control)
        self.assertIn("inputSent=false", live_control)
        self.assertIn("movementSent=false", live_control)
        self.assertIn("savedVariablesUsedAsLiveTruth=false", live_control)
        self.assertIn("plan_live_control_action", live_control)
        self.assertIn("| 42 | `plan_live_control_action` planning tool.", live_control)
        self.assertIn("| 42 | Live control dry-run/planning tool", plan)
        self.assertIn("| complete-local |", plan.split("| 42 |", 1)[1].splitlines()[0])
        self.assertNotIn("execute_live_control_action` | Smallest approved", live_control.split("| 42 |", 1)[0])

    def test_provider_write_planning_keeps_external_repos_disabled(self) -> None:
        text = self.read_doc("docs/workflow/riftreader-chatgpt-mcp-provider-write-planning.md")
        self.assertIn("Stage: **36", text)
        self.assertIn("providerWriteIntent", text)
        self.assertIn("Provider roots must not be discovered through arbitrary filesystem search", text)
        self.assertIn("Provider repo write support remains **not exposed**", text)
        self.assertIn("No provider root should be written", text)
        self.assertIn("Stage 37 extends the proposal/draft flow", text)
        self.assertIn("blocked by default", text)


if __name__ == "__main__":
    unittest.main()
