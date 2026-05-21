#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import operator_lite  # noqa: E402


def make_repo(root: Path) -> None:
    (root / ".git").mkdir()
    (root / "agents.md").write_text("# policy\n", encoding="utf-8")
    scripts = root / "scripts"
    scripts.mkdir()
    for name in [
        "riftreader-workflow-status.cmd",
        "riftreader-live-triage.cmd",
        "riftreader-package-intake.cmd",
        "riftreader-package-intake-selftest.cmd",
        "riftreader-local-artifact-bridge.cmd",
        "riftreader-package-draft-review.cmd",
        "riftreader-chatgpt-mcp.cmd",
        "riftreader-mcp-mission-control.cmd",
        "riftreader-mcp-artifacts.cmd",
        "riftreader-chatgpt-trial-recorder.cmd",
        "riftreader-safe-commit-packager.cmd",
        "riftreader-workflow-router.cmd",
        "riftreader-decision-packet.cmd",
    ]:
        (scripts / name).write_text("@echo off\n", encoding="utf-8")


class OperatorLiteTests(unittest.TestCase):
    def test_command_plan_contains_only_safe_default_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            plan = operator_lite.command_plan(root)

        self.assertEqual(plan["status"], "passed")
        keys = {item["key"] for item in plan["commands"]}
        self.assertEqual(
            keys,
            {
                "workflow-status",
                "compact-sitrep",
                "live-triage",
                "package-selftest",
                "bridge-selftest",
                "bridge-preflight",
                "bridge-handoff",
                "bridge-session-start",
                "bridge-bootstrap-payload",
                "bridge-index",
                "bridge-inbox-index",
                "bridge-inbox-latest",
                "bridge-inbox-package-draft",
                "package-draft-index",
                "package-draft-latest",
                "package-draft-latest-operator",
                "package-draft-dry-run-latest",
                "package-draft-dry-run-latest-operator",
                "package-draft-loop-selftest",
                "mcp-trial-readiness",
                "mcp-mission-control",
                "mcp-artifacts-latest",
                "chatgpt-trial-proof-template",
                "safe-commit-plan",
                "workflow-router-mcp",
                "decision-packet",
                "git-status",
            },
        )
        compact = next(item for item in plan["commands"] if item["key"] == "compact-sitrep")
        self.assertEqual(compact["expectedExitCodes"], [0, 2])
        self.assertIn("--compact", compact["args"])
        package_selftest = next(item for item in plan["commands"] if item["key"] == "package-selftest")
        self.assertIn("riftreader-package-intake-selftest.cmd", package_selftest["args"][0])
        bridge_selftest = next(item for item in plan["commands"] if item["key"] == "bridge-selftest")
        self.assertIn("riftreader-local-artifact-bridge.cmd", bridge_selftest["args"][0])
        self.assertIn("--self-test", bridge_selftest["args"])
        bridge_preflight = next(item for item in plan["commands"] if item["key"] == "bridge-preflight")
        self.assertIn("--preflight", bridge_preflight["args"])
        self.assertEqual(bridge_preflight["expectedExitCodes"], [0, 2])
        bridge_handoff = next(item for item in plan["commands"] if item["key"] == "bridge-handoff")
        self.assertIn("--chatgpt-handoff", bridge_handoff["args"])
        bridge_session_start = next(item for item in plan["commands"] if item["key"] == "bridge-session-start")
        self.assertIn("--session-start", bridge_session_start["args"])
        self.assertEqual(bridge_session_start["expectedExitCodes"], [0, 2])
        bridge_bootstrap = next(item for item in plan["commands"] if item["key"] == "bridge-bootstrap-payload")
        self.assertIn("--bootstrap-payload", bridge_bootstrap["args"])
        bridge_index = next(item for item in plan["commands"] if item["key"] == "bridge-index")
        self.assertIn("--index", bridge_index["args"])
        bridge_inbox_index = next(item for item in plan["commands"] if item["key"] == "bridge-inbox-index")
        self.assertIn("--inbox-index", bridge_inbox_index["args"])
        bridge_inbox_latest = next(item for item in plan["commands"] if item["key"] == "bridge-inbox-latest")
        self.assertIn("--inbox-read-latest", bridge_inbox_latest["args"])
        self.assertEqual(bridge_inbox_latest["expectedExitCodes"], [0, 2])
        bridge_package_draft = next(item for item in plan["commands"] if item["key"] == "bridge-inbox-package-draft")
        self.assertIn("--inbox-package-draft", bridge_package_draft["args"])
        self.assertEqual(bridge_package_draft["expectedExitCodes"], [0, 2])
        package_draft_index = next(item for item in plan["commands"] if item["key"] == "package-draft-index")
        self.assertIn("--index", package_draft_index["args"])
        self.assertEqual(package_draft_index["expectedExitCodes"], [0, 2])
        latest_package_draft = next(item for item in plan["commands"] if item["key"] == "package-draft-latest")
        self.assertIn("--latest", latest_package_draft["args"])
        self.assertEqual(latest_package_draft["expectedExitCodes"], [0, 2])
        latest_operator_draft = next(item for item in plan["commands"] if item["key"] == "package-draft-latest-operator")
        self.assertIn("--latest-operator", latest_operator_draft["args"])
        self.assertEqual(latest_operator_draft["expectedExitCodes"], [0, 2])
        draft_dry_run = next(item for item in plan["commands"] if item["key"] == "package-draft-dry-run-latest")
        self.assertIn("--dry-run-latest", draft_dry_run["args"])
        self.assertEqual(draft_dry_run["expectedExitCodes"], [0, 2])
        operator_draft_dry_run = next(item for item in plan["commands"] if item["key"] == "package-draft-dry-run-latest-operator")
        self.assertIn("--dry-run-latest-operator", operator_draft_dry_run["args"])
        self.assertEqual(operator_draft_dry_run["expectedExitCodes"], [0, 2])
        draft_loop_selftest = next(item for item in plan["commands"] if item["key"] == "package-draft-loop-selftest")
        self.assertIn("--self-test", draft_loop_selftest["args"])
        self.assertEqual(draft_loop_selftest["expectedExitCodes"], [0])
        mcp_trial = next(item for item in plan["commands"] if item["key"] == "mcp-trial-readiness")
        self.assertIn("riftreader-chatgpt-mcp.cmd", mcp_trial["args"][0])
        self.assertIn("--trial-readiness", mcp_trial["args"])
        self.assertEqual(mcp_trial["expectedExitCodes"], [0, 2])
        mcp_mission = next(item for item in plan["commands"] if item["key"] == "mcp-mission-control")
        self.assertIn("riftreader-mcp-mission-control.cmd", mcp_mission["args"][0])
        self.assertIn("--json", mcp_mission["args"])
        mcp_artifacts = next(item for item in plan["commands"] if item["key"] == "mcp-artifacts-latest")
        self.assertIn("riftreader-mcp-artifacts.cmd", mcp_artifacts["args"][0])
        self.assertIn("--latest", mcp_artifacts["args"])
        proof_template = next(item for item in plan["commands"] if item["key"] == "chatgpt-trial-proof-template")
        self.assertIn("riftreader-chatgpt-trial-recorder.cmd", proof_template["args"][0])
        self.assertIn("--template", proof_template["args"])
        commit_plan = next(item for item in plan["commands"] if item["key"] == "safe-commit-plan")
        self.assertIn("riftreader-safe-commit-packager.cmd", commit_plan["args"][0])
        self.assertIn("--plan", commit_plan["args"])
        router = next(item for item in plan["commands"] if item["key"] == "workflow-router-mcp")
        self.assertIn("riftreader-workflow-router.cmd", router["args"][0])
        self.assertIn("--mcp", router["args"])
        decision_packet = next(item for item in plan["commands"] if item["key"] == "decision-packet")
        self.assertIn("riftreader-decision-packet.cmd", decision_packet["args"][0])
        self.assertIn("--write", decision_packet["args"])
        self.assertIn("--compact-json", decision_packet["args"])
        self.assertEqual(decision_packet["expectedExitCodes"], [0, 2])
        self.assertIn("bridge-serve-or-tunnel", plan["disabledLiveActions"])
        self.assertFalse(plan["safety"]["movementSent"])
        self.assertFalse(plan["safety"]["gitMutation"])

    def test_denies_live_or_git_mutating_fragments(self) -> None:
        self.assertIn("send-rift-key", operator_lite.validate_safe_args(["scripts/send-rift-key.ps1"]))
        self.assertIn("git push", operator_lite.validate_safe_args(["git", "push", "origin", "main"]))
        self.assertIn("proofonly", operator_lite.validate_safe_args(["run-ProofOnly.ps1"]))
        self.assertIn("--serve", operator_lite.validate_safe_args(["scripts/riftreader-local-artifact-bridge.cmd", "--serve"]))
        self.assertIn("cloudflared", operator_lite.validate_safe_args(["cloudflared", "tunnel", "--url", "http://127.0.0.1:8765"]))

    def test_package_intake_dry_run_args_are_ask_gated_but_not_denied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            args = operator_lite.package_intake_dry_run_args(root, Path("C:/tmp/package.zip"))

        self.assertIn("--compact-json", args)
        self.assertEqual(operator_lite.validate_safe_args(args), [])

    def test_latest_report_returns_newest_local_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            older = root / ".riftreader-local" / "opencode-status" / "old" / "report.md"
            newer = root / ".riftreader-local" / "package-intake-selftest" / "new" / "summary.json"
            older.parent.mkdir(parents=True)
            newer.parent.mkdir(parents=True)
            older.write_text("old", encoding="utf-8")
            newer.write_text("{}", encoding="utf-8")
            os.utime(older, (1_700_000_000, 1_700_000_000))
            os.utime(newer, (1_800_000_000, 1_800_000_000))

            report = operator_lite.latest_report(root)

        self.assertEqual(report, newer)

    def test_bridge_status_summary_is_read_only_and_local(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = root / "artifacts" / "chatgpt-payloads" / "payload-one"
            payload.mkdir(parents=True)
            (payload / "manifest.json").write_text("{}", encoding="utf-8")
            (payload / "chunk-index.json").write_text("{}", encoding="utf-8")
            inbox = root / ".riftreader-local" / "artifact-bridge-inbox" / "20260518T120000Z-abcdef123456"
            inbox.mkdir(parents=True)
            (inbox / "metadata.json").write_text("{}", encoding="utf-8")
            package_draft = root / ".riftreader-local" / "artifact-bridge-package-drafts" / "20260518T120001Z-fedcba654321"
            package_draft.mkdir(parents=True)
            (package_draft / "summary.json").write_text("{}", encoding="utf-8")

            summary = operator_lite.bridge_status_summary(root)

        self.assertEqual(summary["mode"], "read_only_artifacts_guarded_inbox_manual_start")
        self.assertFalse(summary["serveManagedByOperatorLite"])
        self.assertFalse(summary["tunnelManagedByOperatorLite"])
        self.assertEqual(summary["payloadCount"], 1)
        self.assertEqual(summary["latestPayloadId"], "payload-one")
        self.assertEqual(summary["inboxCount"], 1)
        self.assertEqual(summary["packageDraftCount"], 1)
        self.assertTrue(summary["safety"]["guardedInboxJsonPostOnly"])
        self.assertTrue(summary["safety"]["inboxWritesLocalIgnoredOnly"])
        self.assertTrue(summary["safety"]["packageDraftsLocalIgnoredOnly"])
        self.assertTrue(summary["safety"]["noApplyExecute"])
        self.assertTrue(summary["safety"]["noRepoTargetWrites"])
        self.assertTrue(summary["safety"]["manualTunnelOnly"])

    def test_redacted_bridge_instructions_do_not_include_real_token(self) -> None:
        instructions = operator_lite.redacted_bridge_instructions(REPO_ROOT)

        self.assertIn("<token>/chatgpt-handoff.json", instructions)
        self.assertIn("<token>/health", instructions)
        self.assertIn("<token>/inbox/schema.json", instructions)
        self.assertIn("<token>/inbox/messages", instructions)
        self.assertIn("cloudflared tunnel --url http://127.0.0.1:8765", instructions)
        self.assertNotIn("token=", instructions.lower())
        self.assertNotIn("sk-", instructions.lower())

    def test_redacted_bridge_start_command_keeps_manual_serve_explicit(self) -> None:
        command = operator_lite.redacted_bridge_start_command(REPO_ROOT)

        self.assertIn("--serve", command)
        self.assertIn("--token auto", command)
        self.assertIn("--max-inbox-mb 1", command)
        self.assertIn("127.0.0.1", command)
        self.assertIn("Start any tunnel manually", command)
        self.assertNotIn("cloudflared", command.lower())
        self.assertNotIn("sk-", command.lower())

    def test_redacted_bridge_inbox_template_is_safe_json(self) -> None:
        template = operator_lite.redacted_bridge_inbox_template()
        payload = json.loads(template)

        self.assertEqual(payload["schemaVersion"], 1)
        self.assertEqual(payload["kind"], "chatgpt-message")
        self.assertTrue(payload["metadata"]["requiresHumanReview"])
        self.assertNotIn("sk-", template.lower())

    def test_redacted_bridge_package_proposal_template_is_safe_json(self) -> None:
        template = operator_lite.redacted_bridge_package_proposal_template()
        payload = json.loads(template)

        self.assertEqual(payload["schemaVersion"], 1)
        self.assertEqual(payload["kind"], "package-proposal")
        self.assertEqual(payload["payload"]["files"][0]["encoding"], "utf-8")
        self.assertEqual(payload["payload"]["checks"][0]["expectedExitCodes"], [0])
        self.assertTrue(payload["metadata"]["requiresHumanReview"])
        self.assertTrue(payload["metadata"]["draftOnly"])
        self.assertNotIn("sk-", template.lower())

    def test_redacted_bridge_chatgpt_prompt_points_to_safe_aliases(self) -> None:
        prompt = operator_lite.redacted_bridge_chatgpt_prompt(REPO_ROOT)

        self.assertIn("<token>/", prompt)
        self.assertIn("<token>/chatgpt-handoff.json", prompt)
        self.assertIn("<token>/payloads/latest/readme.md", prompt)
        self.assertIn("<token>/payloads/latest/chunks.json", prompt)
        self.assertIn("/<token>/inbox/schema.json", prompt)
        self.assertIn("GET/HEAD only for artifact reads", prompt)
        self.assertIn("/<token>/inbox/messages", prompt)
        self.assertIn("Inbox messages are proposals only", prompt)
        self.assertIn("registered chunk IDs", prompt)
        self.assertNotIn("token=", prompt.lower())
        self.assertNotIn("sk-", prompt.lower())

    def test_gui_theme_summary_has_distinct_action_groups(self) -> None:
        summary = operator_lite.gui_theme_summary()

        self.assertIn("Workflow Status & Triage", summary["sections"])
        self.assertIn("Local Artifact Bridge", summary["sections"])
        self.assertIn("bridge", summary["buttonVariants"])
        self.assertIn("warning", summary["buttonVariants"])
        self.assertIn("bridge buttons split into action and copy rows", summary["visualRules"])
        self.assertIn("Desktop ChatGPT handoff packet", summary["visualRules"])
        self.assertIn("Desktop ChatGPT session-start packet", summary["visualRules"])
        self.assertIn("guarded inbox JSON template copy", summary["visualRules"])
        self.assertIn("guarded package proposal template copy", summary["visualRules"])
        self.assertIn("guarded package draft export button", summary["visualRules"])
        self.assertIn("package draft index button", summary["visualRules"])
        self.assertIn("newest package draft summary button", summary["visualRules"])
        self.assertIn("latest operator package draft button", summary["visualRules"])
        self.assertIn("explicit latest package draft dry-run button", summary["visualRules"])
        self.assertIn("explicit latest operator draft dry-run button", summary["visualRules"])
        self.assertIn("package proposal loop self-test button", summary["visualRules"])
        self.assertIn("proposal loop checks group button", summary["visualRules"])
        self.assertIn("Desktop ChatGPT trial readiness gate button", summary["visualRules"])
        self.assertIn("ChatGPT MCP trial readiness button", summary["visualRules"])
        self.assertIn("MCP mission control button", summary["visualRules"])
        self.assertIn("latest MCP artifacts button", summary["visualRules"])
        self.assertIn("ChatGPT trial proof template button", summary["visualRules"])
        self.assertIn("safe commit plan button", summary["visualRules"])
        self.assertIn("workflow router button", summary["visualRules"])
        self.assertIn("local decision packet refresh button", summary["visualRules"])
        self.assertIn("manual bridge start command copy", summary["visualRules"])
        self.assertIn("guarded inbox index button", summary["visualRules"])
        self.assertIn("redacted ChatGPT bridge prompt copy", summary["visualRules"])
        self.assertIn("muted locked-control badges", summary["visualRules"])
        self.assertTrue(summary["palette"]["primary"].startswith("#"))
        self.assertNotEqual(summary["palette"]["primary"], summary["palette"]["bridge"])

    def test_command_plan_json_serializable(self) -> None:
        plan = operator_lite.command_plan(REPO_ROOT)
        encoded = json.dumps(plan)

        self.assertIn("riftreader-operator-lite-command-plan", encoded)

    def test_list_commands_payload_is_json_serializable_and_has_examples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = operator_lite.command_list_payload(root)
            encoded = json.dumps(payload)

        self.assertEqual(payload["kind"], "riftreader-operator-lite-command-list")
        self.assertIn("bridge-session-start", {item["key"] for item in payload["commands"]})
        self.assertIn("decision-packet", {item["key"] for item in payload["commands"]})
        self.assertEqual(payload["commandAliases"]["session-start"], "bridge-session-start")
        self.assertEqual(payload["commandAliases"]["package-draft"], "bridge-inbox-package-draft")
        self.assertEqual(payload["commandAliases"]["package-draft-index"], "package-draft-index")
        self.assertEqual(payload["commandAliases"]["latest-package-draft"], "package-draft-latest")
        self.assertEqual(payload["commandAliases"]["latest-operator-draft"], "package-draft-latest-operator")
        self.assertEqual(payload["commandAliases"]["package-draft-dry-run"], "package-draft-dry-run-latest")
        self.assertEqual(payload["commandAliases"]["operator-draft-dry-run"], "package-draft-dry-run-latest-operator")
        self.assertEqual(payload["commandAliases"]["package-draft-selftest"], "package-draft-loop-selftest")
        self.assertEqual(payload["commandAliases"]["mcp-trial"], "mcp-trial-readiness")
        self.assertEqual(payload["commandAliases"]["mcp-mission"], "mcp-mission-control")
        self.assertEqual(payload["commandAliases"]["mcp-artifacts"], "mcp-artifacts-latest")
        self.assertEqual(payload["commandAliases"]["chatgpt-trial-proof"], "chatgpt-trial-proof-template")
        self.assertEqual(payload["commandAliases"]["safe-commit-plan"], "safe-commit-plan")
        self.assertEqual(payload["commandAliases"]["workflow-router"], "workflow-router-mcp")
        self.assertEqual(payload["commandAliases"]["decision-packet"], "decision-packet")
        self.assertEqual(payload["commandAliases"]["refresh-decision-packet"], "decision-packet")
        self.assertIn("bridge-startup-checks", {item["key"] for item in payload["groups"]})
        self.assertIn("bridge-proposal-loop-checks", {item["key"] for item in payload["groups"]})
        self.assertIn("bridge-trial-readiness", {item["key"] for item in payload["groups"]})
        self.assertEqual(payload["groupAliases"]["proposal-loop"], "bridge-proposal-loop-checks")
        self.assertEqual(payload["groupAliases"]["trial-readiness"], "bridge-trial-readiness")
        self.assertIn("--run bridge-session-start", encoded)
        self.assertIn("--package-draft", encoded)
        self.assertIn("--package-draft-index", encoded)
        self.assertIn("--latest-package-draft", encoded)
        self.assertIn("--latest-operator-draft", encoded)
        self.assertIn("--package-draft-dry-run", encoded)
        self.assertIn("--operator-draft-dry-run", encoded)
        self.assertIn("--package-draft-selftest", encoded)
        self.assertIn("--mcp-trial-readiness", encoded)
        self.assertIn("--mcp-mission-control", encoded)
        self.assertIn("--mcp-artifacts", encoded)
        self.assertIn("--chatgpt-trial-proof-template", encoded)
        self.assertIn("--safe-commit-plan", encoded)
        self.assertIn("--workflow-router", encoded)
        self.assertIn("--run-all bridge-startup-checks", encoded)
        self.assertIn("--proposal-loop-checks", encoded)
        self.assertIn("--trial-readiness", encoded)
        self.assertIn("/help", encoded)

    def test_generated_command_reference_markdown_lists_safe_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            markdown = operator_lite.command_reference_markdown(root)

        self.assertIn("RiftReader Operator Lite Command Reference", markdown)
        self.assertIn("`mcp-mission-control`", markdown)
        self.assertIn("`safe-commit-plan`", markdown)
        self.assertIn("`decision-packet`", markdown)
        self.assertIn("Disabled live actions", markdown)
        self.assertIn("`bridge-serve-or-tunnel`", markdown)

    def test_run_command_key_executes_only_known_safe_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = operator_lite.run_command_key(root, "bridge-session-start")

        self.assertEqual(payload["kind"], "riftreader-operator-lite-command-run")
        self.assertEqual(payload["commandKey"], "bridge-session-start")
        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["exitCode"], 0)
        self.assertFalse(payload["safety"]["inputSent"])

    def test_run_command_key_accepts_safe_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = operator_lite.run_command_key(root, "session-start")

        self.assertEqual(payload["commandKey"], "bridge-session-start")
        self.assertEqual(payload["requestedCommandKey"], "session-start")
        self.assertEqual(payload["status"], "passed")

    def test_run_command_key_accepts_package_draft_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = operator_lite.run_command_key(root, "package-draft")

        self.assertEqual(payload["commandKey"], "bridge-inbox-package-draft")
        self.assertEqual(payload["requestedCommandKey"], "package-draft")
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["exitCode"], 0)

    def test_run_command_key_accepts_latest_package_draft_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = operator_lite.run_command_key(root, "latest-package-draft")

        self.assertEqual(payload["commandKey"], "package-draft-latest")
        self.assertEqual(payload["requestedCommandKey"], "latest-package-draft")
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["exitCode"], 0)

    def test_run_command_key_accepts_package_draft_selftest_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = operator_lite.run_command_key(root, "package-draft-selftest")

        self.assertEqual(payload["commandKey"], "package-draft-loop-selftest")
        self.assertEqual(payload["requestedCommandKey"], "package-draft-selftest")
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["exitCode"], 0)

    def test_run_command_key_accepts_mcp_trial_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = operator_lite.run_command_key(root, "mcp-trial")

        self.assertEqual(payload["commandKey"], "mcp-trial-readiness")
        self.assertEqual(payload["requestedCommandKey"], "mcp-trial")
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["exitCode"], 0)

    def test_run_command_key_accepts_mcp_helper_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            mission = operator_lite.run_command_key(root, "mcp-mission")
            artifacts = operator_lite.run_command_key(root, "mcp-artifacts")
            proof = operator_lite.run_command_key(root, "chatgpt-trial-proof")
            commit_plan = operator_lite.run_command_key(root, "safe-commit-plan")
            router = operator_lite.run_command_key(root, "workflow-router")

        self.assertEqual(mission["commandKey"], "mcp-mission-control")
        self.assertEqual(artifacts["commandKey"], "mcp-artifacts-latest")
        self.assertEqual(proof["commandKey"], "chatgpt-trial-proof-template")
        self.assertEqual(commit_plan["commandKey"], "safe-commit-plan")
        self.assertEqual(router["commandKey"], "workflow-router-mcp")
        self.assertEqual(router["exitCode"], 0)

    def test_run_command_key_unknown_command_blocks_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = operator_lite.run_command_key(root, "bridge-serve")

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["code"], "COMMAND_KEY_UNKNOWN")
        self.assertEqual(payload["exitCode"], 2)
        self.assertIn("bridge-session-start", payload["availableCommands"])

    def test_run_command_group_executes_bridge_startup_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = operator_lite.run_command_group(root, "bridge-startup-checks")

        self.assertEqual(payload["kind"], "riftreader-operator-lite-command-group-run")
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["exitCode"], 0)
        self.assertEqual([item["commandKey"] for item in payload["results"]], [
            "bridge-selftest",
            "bridge-preflight",
            "bridge-session-start",
        ])

    def test_run_command_group_executes_bridge_proposal_loop_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = operator_lite.run_command_group(root, "proposal-loop")

        self.assertEqual(payload["kind"], "riftreader-operator-lite-command-group-run")
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["exitCode"], 0)
        self.assertEqual(payload["groupKey"], "bridge-proposal-loop-checks")
        self.assertEqual(payload["requestedGroupKey"], "proposal-loop")
        self.assertEqual([item["commandKey"] for item in payload["results"]], [
            "bridge-selftest",
            "package-draft-loop-selftest",
        ])

    def test_run_command_group_executes_bridge_trial_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = operator_lite.run_command_group(root, "trial-readiness")

        self.assertEqual(payload["kind"], "riftreader-operator-lite-command-group-run")
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["exitCode"], 0)
        self.assertEqual(payload["groupKey"], "bridge-trial-readiness")
        self.assertEqual(payload["requestedGroupKey"], "trial-readiness")
        self.assertEqual(
            [item["commandKey"] for item in payload["results"]],
            [
                "bridge-selftest",
                "bridge-preflight",
                "bridge-session-start",
                "bridge-inbox-index",
                "package-draft-index",
                "package-draft-latest-operator",
            ],
        )

    def test_run_command_group_unknown_group_blocks(self) -> None:
        payload = operator_lite.run_command_group(REPO_ROOT, "serve-everything")

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["code"], "COMMAND_GROUP_UNKNOWN")
        self.assertEqual(payload["exitCode"], 2)
        self.assertIn("bridge-startup-checks", payload["availableGroups"])

    def test_cli_list_commands_json_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--list-commands", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["kind"], "riftreader-operator-lite-command-list")
        self.assertIn("bridge-session-start", {item["key"] for item in payload["commands"]})
        self.assertIn("decision-packet", {item["key"] for item in payload["commands"]})
        self.assertIn("bridge-startup-checks", {item["key"] for item in payload["groups"]})
        self.assertIn("bridge-proposal-loop-checks", {item["key"] for item in payload["groups"]})
        self.assertIn("bridge-trial-readiness", {item["key"] for item in payload["groups"]})

    def test_cli_run_json_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--run", "bridge-session-start", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["kind"], "riftreader-operator-lite-command-run")
        self.assertEqual(payload["commandKey"], "bridge-session-start")
        self.assertTrue(payload["ok"])

    def test_cli_session_start_shortcut_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--session-start", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["commandKey"], "bridge-session-start")
        self.assertTrue(payload["ok"])

    def test_cli_package_draft_shortcut_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--package-draft", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["commandKey"], "bridge-inbox-package-draft")
        self.assertTrue(payload["ok"])

    def test_cli_latest_package_draft_shortcut_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--latest-package-draft", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["commandKey"], "package-draft-latest")
        self.assertTrue(payload["ok"])

    def test_cli_package_draft_index_shortcut_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--package-draft-index", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["commandKey"], "package-draft-index")
        self.assertTrue(payload["ok"])

    def test_cli_latest_operator_draft_shortcut_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--latest-operator-draft", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["commandKey"], "package-draft-latest-operator")
        self.assertTrue(payload["ok"])

    def test_cli_package_draft_dry_run_shortcut_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--package-draft-dry-run", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["commandKey"], "package-draft-dry-run-latest")
        self.assertTrue(payload["ok"])

    def test_cli_operator_draft_dry_run_shortcut_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--operator-draft-dry-run", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["commandKey"], "package-draft-dry-run-latest-operator")
        self.assertTrue(payload["ok"])

    def test_cli_package_draft_selftest_shortcut_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--package-draft-selftest", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["commandKey"], "package-draft-loop-selftest")
        self.assertTrue(payload["ok"])

    def test_cli_mcp_trial_readiness_shortcut_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--mcp-trial-readiness", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["commandKey"], "mcp-trial-readiness")
        self.assertTrue(payload["ok"])

    def test_cli_mcp_helper_shortcut_switches(self) -> None:
        shortcuts = {
            "--mcp-mission-control": "mcp-mission-control",
            "--mcp-artifacts": "mcp-artifacts-latest",
            "--chatgpt-trial-proof-template": "chatgpt-trial-proof-template",
            "--safe-commit-plan": "safe-commit-plan",
            "--workflow-router": "workflow-router-mcp",
            "--decision-packet": "decision-packet",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            for shortcut, command_key in shortcuts.items():
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = operator_lite.main(["--repo-root", str(root), shortcut, "--json"])
                payload = json.loads(stdout.getvalue())
                self.assertEqual(exit_code, 0)
                self.assertEqual(payload["commandKey"], command_key)
                self.assertTrue(payload["ok"])

    def test_cli_decision_packet_shortcut_accepts_safe_blocked_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            (root / "scripts" / "riftreader-decision-packet.cmd").write_text("@echo off\nexit /b 2\n", encoding="utf-8")
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--decision-packet", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["commandKey"], "decision-packet")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["expectedExitCodes"], [0, 2])

    def test_cli_decision_packet_shortcut_smoke_outputs_packet_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            helper = root / "scripts" / "fake-decision-packet.py"
            helper.write_text(
                "import json, sys\n"
                "print(json.dumps({'kind':'riftreader-decision-packet','status':'blocked'}))\n"
                "raise SystemExit(2)\n",
                encoding="utf-8",
            )
            (root / "scripts" / "riftreader-decision-packet.cmd").write_text(
                '@echo off\npython "%~dp0fake-decision-packet.py" %*\nexit /b %ERRORLEVEL%\n',
                encoding="utf-8",
            )
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--decision-packet", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["commandKey"], "decision-packet")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("--write", payload["args"])
        self.assertIn("--compact-json", payload["args"])
        self.assertIn("riftreader-decision-packet", payload["stdout"])
        self.assertFalse(payload["safety"]["movementSent"])
        self.assertFalse(payload["safety"]["gitMutation"])

    def test_cli_run_alias_json_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--run", "session-start", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["commandKey"], "bridge-session-start")
        self.assertEqual(payload["requestedCommandKey"], "session-start")

    def test_cli_run_all_bridge_startup_checks_json_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--run-all", "bridge-startup-checks", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["kind"], "riftreader-operator-lite-command-group-run")
        self.assertEqual(payload["groupKey"], "bridge-startup-checks")
        self.assertEqual(len(payload["results"]), 3)

    def test_cli_proposal_loop_checks_shortcut_json_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--proposal-loop-checks", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["kind"], "riftreader-operator-lite-command-group-run")
        self.assertEqual(payload["groupKey"], "bridge-proposal-loop-checks")
        self.assertEqual(len(payload["results"]), 2)

    def test_cli_trial_readiness_shortcut_json_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--trial-readiness", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["kind"], "riftreader-operator-lite-command-group-run")
        self.assertEqual(payload["groupKey"], "bridge-trial-readiness")
        self.assertEqual(len(payload["results"]), 6)

    def test_cli_run_unknown_key_returns_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = operator_lite.main(["--repo-root", str(root), "--run", "bridge-serve", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["code"], "COMMAND_KEY_UNKNOWN")

    def test_cli_run_unknown_group_returns_exit_2(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = operator_lite.main(["--run-all", "serve-everything", "--json"])
        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["code"], "COMMAND_GROUP_UNKNOWN")

    def test_cli_blocks_conflicting_command_shortcuts(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            operator_lite.main(["--session-start", "--bridge-preflight"])

        self.assertEqual(raised.exception.code, 2)

    def test_cli_blocks_package_draft_conflicting_shortcuts(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            operator_lite.main(
                [
                    "--package-draft",
                    "--latest-inbox",
                    "--package-draft-index",
                    "--latest-package-draft",
                    "--latest-operator-draft",
                    "--operator-draft-dry-run",
                    "--package-draft-selftest",
                    "--mcp-trial-readiness",
                    "--mcp-mission-control",
                    "--mcp-artifacts",
                    "--chatgpt-trial-proof-template",
                    "--safe-commit-plan",
                    "--workflow-router",
                ]
            )

        self.assertEqual(raised.exception.code, 2)

    def test_slash_help_alias_prints_argparse_help(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit) as raised:
            operator_lite.main(["/help"])

        self.assertEqual(raised.exception.code, 0)
        help_text = stdout.getvalue()
        self.assertIn("--run", help_text)
        self.assertIn("--run-all", help_text)
        self.assertIn("--session-start", help_text)
        self.assertIn("--package-draft", help_text)
        self.assertIn("--package-draft-index", help_text)
        self.assertIn("--latest-package-draft", help_text)
        self.assertIn("--latest-operator-draft", help_text)
        self.assertIn("--package-draft-dry-run", help_text)
        self.assertIn("--operator-draft-dry-run", help_text)
        self.assertIn("--package-draft-selftest", help_text)
        self.assertIn("--mcp-trial-readiness", help_text)
        self.assertIn("--mcp-mission-control", help_text)
        self.assertIn("--mcp-artifacts", help_text)
        self.assertIn("--chatgpt-trial-proof-template", help_text)
        self.assertIn("--safe-commit-plan", help_text)
        self.assertIn("--workflow-router", help_text)
        self.assertIn("--decision-packet", help_text)
        self.assertIn("--command-reference-md", help_text)
        self.assertIn("--proposal-loop-checks", help_text)
        self.assertIn("--trial-readiness", help_text)
        self.assertIn("--list-commands", help_text)


if __name__ == "__main__":
    unittest.main()
