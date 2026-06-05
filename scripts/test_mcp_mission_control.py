#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import mcp_mission_control as mission  # noqa: E402


def make_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "agents.md").write_text("# policy\n", encoding="utf-8")
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "riftreader-operator-lite.cmd").write_text(
        '@echo off\necho {"ok":true,"status":"passed"}\nexit /b 0\n',
        encoding="utf-8",
    )
    (scripts / "riftreader-chatgpt-mcp.cmd").write_text(
        '@echo off\necho {"ok":true,"status":"passed"}\nexit /b 0\n',
        encoding="utf-8",
    )


class McpMissionControlTests(unittest.TestCase):
    def test_dashboard_lists_commands_without_starting_public_tunnel(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = mission.mission_control(root)

        self.assertEqual(payload["kind"], "riftreader-mcp-mission-control")
        self.assertIn("readiness", payload["pasteSafeCommands"])
        self.assertIn("proposalSmoke", payload["pasteSafeCommands"])
        self.assertIn("trialSession", payload["pasteSafeCommands"])
        self.assertIn("trialProofTemplate", payload["pasteSafeCommands"])
        self.assertIn("phase2Status", payload["pasteSafeCommands"])
        self.assertIn("phase2CompactStatus", payload["pasteSafeCommands"])
        self.assertIn("finalStatus", payload["pasteSafeCommands"])
        self.assertIn("finalCompactStatus", payload["pasteSafeCommands"])
        self.assertIn("artifactBrowser", payload["pasteSafeCommands"])
        self.assertIn("safeCommitPlan", payload["pasteSafeCommands"])
        self.assertIn("ciStatus", payload)
        self.assertIn("finalStatus", payload)
        self.assertIn("finalProductProgress", payload)
        self.assertIn("operatorNextAction", payload)
        self.assertEqual(payload["finalProductProgress"]["kind"], "riftreader-mcp-final-product-progress")
        self.assertEqual(payload["finalProductProgress"]["phases"][4]["phase"], 5)
        self.assertEqual(payload["finalProductProgress"]["phases"][4]["status"], "completed")
        self.assertFalse(payload["safety"]["publicTunnelStarted"])
        self.assertFalse(payload["safety"]["gitMutation"])

    def test_dashboard_prefers_final_gate_truth_over_raw_artifact_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            state = {
                "status": "ready",
                "ok": True,
                "blockers": [],
                "warnings": [],
                "latestArtifacts": {
                    "actual-client-proof": {
                        "status": "passed",
                        "ok": True,
                        "chatGptRegistrationSucceeded": None,
                        "toolCount": 8,
                    }
                },
                "counts": {},
                "gitDirtyState": {"dirty": False, "dirtyCount": 0, "entries": []},
                "recommendedNextAction": {
                    "key": "docs-or-commit",
                    "reason": "Raw artifact state is stale.",
                    "command": ["scripts\\riftreader-safe-commit-packager.cmd", "--plan", "--json"],
                },
            }
            final_payload = {
                "status": "blocked",
                "ok": False,
                "warnings": [],
                "recommendedNextAction": {
                    "key": "record-actual-client-proof",
                    "reason": "Actual-client proof is missing, stale, or failed replay.",
                    "command": ["scripts\\riftreader-chatgpt-trial-recorder.cmd", "--template", "--json"],
                },
            }
            compact_final = {
                **final_payload,
                "blockers": ["proof:replay-failed:required-field-missing:connectionMode"],
                "phase2Ready": False,
                "ciStatus": "blocked",
                "upstreamStatus": "blocked",
                "dependencyStatus": "passed",
                "environmentStatus": "passed",
                "toolSurfaceStatus": "passed",
                "publicSessionStatus": "passed",
                "proofReplayStatus": "blocked",
                "proofFreshnessStatus": "stale",
                "requiredDependencies": {"tunnel-client": "passed"},
            }

            with (
                mock.patch.object(mission, "build_mcp_workflow_state", return_value=state),
                mock.patch.object(
                    mission,
                    "current_head_ci_status",
                    return_value={"status": "blocked", "ok": False, "warnings": [], "blockers": []},
                ),
                mock.patch.object(mission, "final_readiness", return_value=final_payload),
                mock.patch.object(mission, "compact_final_readiness", return_value=compact_final),
            ):
                payload = mission.mission_control(root)

        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["recommendedNextAction"]["key"], "record-actual-client-proof")
        self.assertEqual(payload["operatorNextAction"]["key"], "record-actual-client-proof")
        self.assertEqual(payload["rankedActions"][0]["key"], "record-actual-client-proof")
        self.assertIn("proof:replay-failed:required-field-missing:connectionMode", payload["blockers"])

    def test_trial_command_displays_bounded_public_trial_command_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = mission.trial_command_payload(root)

        self.assertEqual(payload["kind"], "riftreader-mcp-mission-control-trial-command")
        self.assertIn("--chatgpt-trial-session", payload["command"])
        self.assertIn("--chatgpt-session-seconds", payload["command"])
        self.assertTrue(payload["safety"]["commandDisplayedOnly"])
        self.assertFalse(payload["safety"]["publicTunnelStarted"])

    def test_progress_marks_release_handoff_complete_from_recorded_actual_client_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            contract = root / "docs" / "workflow" / "riftreader-chatgpt-mcp-final-readiness.md"
            contract.parent.mkdir(parents=True)
            contract.write_text("# Final readiness contract\n", encoding="utf-8")
            handoff = root / "docs" / "handoffs" / "20260519-1645-mcp-final-readiness-release-handoff.md"
            handoff.parent.mkdir(parents=True)
            handoff.write_text("# Release handoff\n", encoding="utf-8")
            progress = mission.build_final_product_progress(
                root,
                {
                    "ok": True,
                    "phase2Ready": True,
                    "ciStatus": "passed",
                    "upstreamStatus": "passed",
                    "dependencyStatus": "passed",
                    "environmentStatus": "passed",
                    "toolSurfaceStatus": "passed",
                    "publicSessionStatus": "passed",
                    "proofReplayStatus": "passed",
                    "proofFreshnessStatus": "fresh",
                },
                mission.standard_commands(),
                {
                    "actual-client-proof": {
                        "ok": True,
                        "status": "passed",
                        "selfTest": False,
                        "chatGptRegistrationSucceeded": True,
                        "templateFetched": True,
                        "toolCount": mission.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
                        "toolNames": list(mission.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
                        "toolOutputSchemasPresent": True,
                        "toolOutputSchemaCount": mission.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
                        "toolOutputSchemaToolNames": list(mission.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
                        "submitPackageProposalSucceeded": True,
                        "listInboxSawInboxId": True,
                        "createPackageDraftSucceeded": True,
                        "reviewLatestPackageDraftSucceeded": True,
                        "reviewLatestPackageDraftReadOnly": True,
                        "dryRunSucceeded": True,
                        "dryRunDiffPreviewOk": True,
                        "dryRunDiffPreviewArtifactUnderPackageIntake": True,
                        "dryRunDiffPreviewBoundedBytes": True,
                        "dryRunDiffPreviewTextLength": 195,
                        "dryRunDiffPreviewTruncated": False,
                        "applyLatestPackageDraftWithoutApprovalBlocked": True,
                        "applyLatestPackageDraftWithoutApprovalBlockers": ["APPLY_APPROVAL_MISSING"],
                        "applyLatestPackageDraftWithoutApprovalApplied": False,
                    }
                },
            )

        self.assertEqual(progress["status"], "completed")
        self.assertEqual(progress["completedPhaseCount"], 8)
        self.assertEqual(progress["currentCompletedThroughPhase"], 8)
        self.assertIsNone(progress["nextPhase"])
        self.assertEqual(progress["recommendedNextAction"]["key"], "maintenance-loop")
        self.assertEqual(progress["phases"][6]["status"], "completed")
        self.assertEqual(progress["phases"][7]["status"], "completed")
        self.assertTrue(progress["actualClientProofCompleted"])
        self.assertEqual(progress["releaseHandoffPath"], "docs\\handoffs\\20260519-1645-mcp-final-readiness-release-handoff.md")

    def test_actual_client_completion_blocks_on_malformed_tool_name_lists(self) -> None:
        self.assertFalse(
            mission._actual_client_proof_completed(
                {
                    "actual-client-proof": {
                        "ok": True,
                        "status": "passed",
                        "selfTest": False,
                        "chatGptRegistrationSucceeded": True,
                        "toolCount": mission.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
                        "toolNames": ["health"] * mission.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
                        "toolOutputSchemasPresent": True,
                        "toolOutputSchemaCount": mission.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
                        "toolOutputSchemaToolNames": "health",
                    }
                }
            )
        )

    def test_actual_client_completion_requires_apply_denial_proof(self) -> None:
        proof = {
            "ok": True,
            "status": "passed",
            "selfTest": False,
            "chatGptRegistrationSucceeded": True,
            "templateFetched": True,
            "toolCount": mission.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
            "toolNames": list(mission.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
            "toolOutputSchemasPresent": True,
            "toolOutputSchemaCount": mission.EXPECTED_CHATGPT_MCP_TOOL_COUNT,
            "toolOutputSchemaToolNames": list(mission.EXPECTED_CHATGPT_MCP_TOOL_NAMES),
            "submitPackageProposalSucceeded": True,
            "listInboxSawInboxId": True,
            "createPackageDraftSucceeded": True,
            "reviewLatestPackageDraftSucceeded": True,
            "reviewLatestPackageDraftReadOnly": True,
            "dryRunSucceeded": True,
            "dryRunDiffPreviewOk": True,
            "dryRunDiffPreviewArtifactUnderPackageIntake": True,
            "dryRunDiffPreviewBoundedBytes": True,
            "dryRunDiffPreviewTextLength": 195,
            "dryRunDiffPreviewTruncated": False,
            "applyLatestPackageDraftWithoutApprovalBlocked": True,
            "applyLatestPackageDraftWithoutApprovalBlockers": ["APPLY_APPROVAL_MISSING"],
            "applyLatestPackageDraftWithoutApprovalApplied": False,
        }

        self.assertTrue(mission._actual_client_proof_completed({"actual-client-proof": proof}))
        proof["applyLatestPackageDraftWithoutApprovalBlockers"] = ["APPLY_PREFLIGHT_NOT_READY"]
        self.assertFalse(mission._actual_client_proof_completed({"actual-client-proof": proof}))

    def test_run_readiness_executes_local_only_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = mission.run_local_action(root, "mcpTrialReadiness", "run-readiness")

        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertIn("riftreader-operator-lite.cmd", payload["command"][0])
        self.assertFalse(payload["safety"]["publicTunnelStarted"])
        self.assertFalse(payload["safety"]["gitMutation"])

    def test_cli_trial_command_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = mission.main(["--repo-root", str(root), "--trial-command", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["kind"], "riftreader-mcp-mission-control-trial-command")

    def test_markdown_summary_and_checklist_are_generated_from_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            payload = mission.mission_control(root)

            summary = mission.render_summary_markdown(payload)
            checklist = mission.render_proof_checklist(payload)

        self.assertIn("RiftReader MCP Mission Control Summary", summary)
        self.assertIn("Final product progress", summary)
        self.assertIn("Current-head CI", summary)
        self.assertIn("Final readiness", summary)
        self.assertIn("Secure Tunnel client", summary)
        self.assertIn("Latest artifacts", summary)
        self.assertIn("RiftReader MCP Proof Checklist", checklist)
        self.assertIn("Local final gate", checklist)
        self.assertIn("Explicit ChatGPT Secure Tunnel proof", checklist)
        self.assertIn("riftreader-mcp-mission-control.cmd --secure-tunnel-plan --json", checklist)
        self.assertIn("riftreader-chatgpt-trial-recorder.cmd --template --json", checklist)
        self.assertIn("Confirm output schemas are present", checklist)
        self.assertIn("get_package_proposal_template", checklist)
        self.assertIn("create_package_draft_from_inbox", checklist)
        self.assertIn("apply_latest_package_draft", checklist)
        self.assertIn("APPLY_APPROVAL_MISSING", checklist)
        self.assertIn("riftreader-mcp-final.cmd --status --compact-json", checklist)
        self.assertIn("scripts\\riftreader-chatgpt-trial-recorder.cmd --record --input proof.json --json", checklist)


if __name__ == "__main__":
    unittest.main()
