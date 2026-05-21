#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import opencode_bridge  # noqa: E402


SAMPLE_COMPACT = {
    "schemaVersion": 1,
    "kind": "riftreader-opencode-compact-sitrep",
    "generatedAtUtc": "2026-05-17T00:00:00Z",
    "status": "blocked",
    "git": {
        "branch": "## main...origin/main",
        "isClean": False,
        "head": {"hash": "abc1234", "subject": "Test head"},
    },
    "latestHandoff": {"path": "docs\\handoffs\\latest.md", "title": "Latest"},
    "currentProof": {
        "status": "blocked-target-drift",
        "targetPid": 27552,
        "targetHwnd": "0x3411E2",
        "staleCandidateId": "api-family-hit-000001",
        "staleAddressHex": "0x27B1ED850C0",
        "reusePolicy": "do-not-use-as-current-proof",
    },
    "liveTarget": {
        "verdict": "artifact-pid-stale",
        "livePids": [22304],
        "artifactPid": 27552,
        "artifactHwnd": "0x3411E2",
        "artifactPidStale": True,
    },
    "movementGate": {
        "allowed": False,
        "status": "blocked-no-live-target-reacquisition-required",
        "reason": "stale target",
    },
    "opencode": {
        "available": True,
        "version": "1.15.3",
        "desiredModel": "openai/gpt-5.5",
        "desiredVariant": "xhigh",
        "modelProvider": "openai",
        "modelVisible": True,
    },
    "bridgeCommands": [],
    "decisionPacket": {
        "kind": "riftreader-decision-packet",
        "status": "blocked",
        "lane": "actor-chain",
        "risk": "high",
        "targetEpoch": {"status": "current", "blockers": []},
        "safeNextAction": {
            "key": "actor-chain-no-debug-status",
            "command": ["python", ".\\scripts\\actor_chain_no_debug_status.py", "--json"],
            "why": "Actor-chain evidence is candidate-only.",
        },
        "llmReminder": {
            "banner": "# **🚦 NEXT ACTION — CONTINUE SAFELY**",
            "doNotStopIf": ["safe validation passed"],
            "mustStopIf": ["debugger or CE would be required"],
        },
        "milestoneStatus": {"state": "blocked-safe"},
        "blockers": ["actor-chain-candidate-only"],
    },
    "blockers": ["live-target-artifact-pid-stale:artifact=27552;live=22304"],
    "warnings": ["current-truth-stale-live-target-detected:artifact=27552;live=22304"],
    "errors": [],
    "nextRecommendedAction": "Keep movement blocked.",
    "safety": {"movementSent": False, "gitMutation": False},
}


class OpenCodeBridgePromptTests(unittest.TestCase):
    def test_lane_policy_marks_integration_as_scoped_tracked_edit_lane(self) -> None:
        policy = opencode_bridge.lane_policy("integration")

        self.assertEqual(policy["mode"], "opencode-integration-patch-and-test")
        self.assertEqual(policy["recommendedAgent"], "riftreader-integration")
        self.assertTrue(policy["allowsTrackedEdits"])
        self.assertIn("tools/riftreader_workflow/opencode_bridge.py", policy["allowedEditPaths"])
        self.assertIn("scripts/riftreader-opencode-*.cmd", policy["allowedEditPaths"])
        self.assertIn("scripts/test_opencode_bridge.py", policy["groundingFiles"])
        self.assertIn("docs/workflow/opencode-non-codex-bridge.md", policy["groundingFiles"])
        self.assertIn("git-mutation", policy["forbiddenActions"])
        self.assertIn("live-input", policy["forbiddenActions"])
        self.assertIn(r".riftreader-local\opencode-runs", policy["ignoredWriteRoots"])
        self.assertIn("no-further-useful-opencode-integration-improvements", policy["hardStopConditions"])
        self.assertIn("git --no-pager diff --check", policy["targetedValidation"])

    def test_lane_policy_marks_non_integration_lanes_as_read_only(self) -> None:
        for lane in ("sitrep", "live-observer", "package-review"):
            with self.subTest(lane=lane):
                policy = opencode_bridge.lane_policy(lane)
                self.assertFalse(policy["allowsTrackedEdits"])
                self.assertTrue(str(policy["recommendedAgent"]).startswith("riftreader-"))
                self.assertEqual(policy["allowedEditPaths"], [])
                self.assertEqual(policy["groundingFiles"], [])
                self.assertIn("tracked-edit-needed", policy["hardStopConditions"])
                self.assertEqual(policy["targetedValidation"], [])

    def test_adaptive_sitrep_prompt_blocks_stale_live_target_and_dirty_worktree(self) -> None:
        prompt = opencode_bridge.build_adaptive_prompt("sitrep", SAMPLE_COMPACT)

        self.assertIn("Rerun the required command sequence", prompt)
        self.assertIn("rift_x64 process is visible", prompt)
        self.assertIn("process-only context", prompt)
        self.assertIn("worktree is not clean", prompt)
        self.assertIn("Do not send live input", prompt)
        self.assertIn(".\\scripts\\riftreader-workflow-status.cmd --compact-json --write", prompt)
        self.assertIn("blocked-target-drift", prompt)
        self.assertIn("Do not edit tracked repo files", prompt)
        self.assertIn('"allowsTrackedEdits": false', prompt)

    def test_package_review_prompt_uses_exact_dry_run_package_path(self) -> None:
        package_path = r"C:\tmp\RiftReader package.zip"
        prompt = opencode_bridge.build_adaptive_prompt("package-review", SAMPLE_COMPACT, package_path=package_path)

        self.assertIn(package_path, prompt)
        self.assertIn("package review only", prompt)
        self.assertIn("--compact-json", prompt)
        self.assertIn("--apply still requires explicit operator approval", prompt)
        self.assertNotIn("--apply --json", prompt)

    def test_integration_prompt_requires_autonomous_milestone_loop_and_scope(self) -> None:
        prompt = opencode_bridge.build_adaptive_prompt("integration", SAMPLE_COMPACT)

        self.assertIn("Continue improving RiftReader OpenCode integration", prompt)
        self.assertIn("autonomous OpenCode-integration development lane", prompt)
        self.assertIn("A completed milestone is a checkpoint, not the end of the task", prompt)
        self.assertIn("immediately choose the next safe in-scope OpenCode-integration improvement", prompt)
        self.assertIn("Allowed edit scope is limited", prompt)
        self.assertIn("scripts/riftreader-opencode-*.cmd", prompt)
        self.assertIn("Tracked edits are allowed only inside the OpenCode-integration allowlist", prompt)
        self.assertIn('"allowsTrackedEdits": true', prompt)
        self.assertIn('"next-step-requires-git-mutation"', prompt)
        self.assertIn("Grounding file set", prompt)
        self.assertIn("scripts/test_opencode_bridge.py", prompt)
        self.assertIn("Do not stop for a single passing patch", prompt)
        self.assertIn("same failure pattern has repeated three times", prompt)
        self.assertIn("# ✅ OpenCode Integration Milestone Complete", prompt)
        self.assertIn("git status --short --branch", prompt)
        self.assertIn(".\\scripts\\riftreader-workflow-status.cmd --compact-json --write", prompt)

    def test_adaptive_prompt_embeds_decision_packet_contract(self) -> None:
        prompt = opencode_bridge.build_adaptive_prompt("integration", SAMPLE_COMPACT)

        self.assertIn('"decisionPacket"', prompt)
        self.assertIn('"kind": "riftreader-decision-packet"', prompt)
        self.assertIn('"safeNextAction"', prompt)
        self.assertIn('"llmReminder"', prompt)
        self.assertIn('"milestoneStatus"', prompt)
        self.assertIn("actor-chain-no-debug-status", prompt)
        self.assertIn("NEXT ACTION", prompt)
        self.assertIn("CONTINUE SAFELY", prompt)

    def test_required_commands_include_integration_preflight(self) -> None:
        self.assertEqual(
            opencode_bridge.required_commands("integration"),
            [
                r".\scripts\riftreader-workflow-status.cmd --compact-json --write",
                "git status --short --branch",
            ],
        )

    def test_opencode_run_command_uses_model_variant_and_dir(self) -> None:
        command = opencode_bridge.opencode_run_command(Path("C:/repo"), model="openai/gpt-5.5", variant="xhigh")

        self.assertIn("opencode", command)
        self.assertIn("run", command)
        self.assertIn("--dir", command)
        self.assertIn("-m", command)
        self.assertIn("openai/gpt-5.5", command)
        self.assertIn("--variant", command)
        self.assertIn("xhigh", command)
        self.assertNotIn("--agent", command)
        self.assertNotIn("hello", command)

    def test_opencode_run_command_can_select_configured_agent(self) -> None:
        command = opencode_bridge.opencode_run_command(
            Path("C:/repo"),
            model="openai/gpt-5.5",
            variant="xhigh",
            agent="riftreader-integration",
        )

        self.assertIn("--agent", command)
        self.assertIn("riftreader-integration", command)

    def test_selected_opencode_agent_prefers_explicit_value_then_environment(self) -> None:
        previous = os.environ.get("RIFTREADER_OPENCODE_AGENT")
        try:
            os.environ["RIFTREADER_OPENCODE_AGENT"] = "riftreader-live-observer"

            self.assertEqual(opencode_bridge.selected_opencode_agent(), "riftreader-live-observer")
            self.assertEqual(
                opencode_bridge.selected_opencode_agent("riftreader-integration"),
                "riftreader-integration",
            )
            self.assertIsNone(opencode_bridge.selected_opencode_agent("   "))
        finally:
            if previous is None:
                os.environ.pop("RIFTREADER_OPENCODE_AGENT", None)
            else:
                os.environ["RIFTREADER_OPENCODE_AGENT"] = previous

    def test_stdin_command_envelope_handles_unicode_prompt_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            envelope = opencode_bridge.run_command_envelope_with_input(
                "unicode-stdin",
                [sys.executable, "-c", "import sys; print(sys.stdin.read())"],
                Path(temp_dir),
                stdin_text="OpenCode prompt ✅ ⚠️",
                timeout_seconds=10.0,
            )

        self.assertTrue(envelope["ok"])
        self.assertEqual(envelope["exitCode"], 0)
        self.assertIn("OpenCode prompt", envelope["stdoutPreview"])
        self.assertIn("stdinBytes", envelope)
        self.assertEqual(envelope["stdinMode"], "prompt-via-stdin")

    def test_run_opencode_blocks_when_model_not_visible_in_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "prompt.txt").write_text("prompt", encoding="utf-8")
            summary = {
                "repoRoot": str(root),
                "promptPath": "prompt.txt",
                "compactStatus": {
                    "opencode": {
                        "available": True,
                        "desiredModel": "openai/not-visible",
                        "modelVisible": False,
                    }
                },
            }

            envelope = opencode_bridge.run_opencode(summary, timeout_seconds=1.0)

        self.assertFalse(envelope["ok"])
        self.assertIsNone(envelope["exitCode"])
        self.assertEqual(envelope["error"], "opencode-model-not-visible-preflight:openai/not-visible")
        self.assertIn("not visible during preflight", envelope["stderrPreview"])

    def test_run_opencode_streams_full_output_under_ignored_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "prompt.txt").write_text("stream prompt", encoding="utf-8")
            summary = {
                "repoRoot": str(root),
                "promptPath": "prompt.txt",
                "compactStatus": {
                    "opencode": {
                        "available": True,
                        "desiredModel": "openai/gpt-5.5",
                        "modelVisible": True,
                    }
                },
            }
            original_command = opencode_bridge.opencode_run_command
            captured_agent: dict[str, str | None] = {}

            def fake_command(repo_root: Path, model: str, variant: str, agent: str | None = None) -> list[str]:
                captured_agent["agent"] = agent
                return [
                    sys.executable,
                    "-c",
                    "import sys; prompt=sys.stdin.read(); print('stream-out:' + prompt.strip()); print('stream-err', file=sys.stderr)",
                ]

            try:
                opencode_bridge.opencode_run_command = fake_command
                envelope = opencode_bridge.run_opencode(summary, timeout_seconds=10.0, agent="riftreader-integration")
            finally:
                opencode_bridge.opencode_run_command = original_command

            artifacts = envelope["artifacts"]
            stdout_path = root / artifacts["stdout"]
            stderr_path = root / artifacts["stderr"]
            run_envelope_path = root / artifacts["runEnvelopeJson"]

            self.assertTrue(envelope["ok"])
            self.assertTrue(envelope["streaming"])
            self.assertFalse(envelope["timedOut"])
            self.assertEqual(envelope["stdinMode"], "prompt-via-stdin")
            self.assertEqual(captured_agent["agent"], "riftreader-integration")
            self.assertTrue(artifacts["outputDir"].startswith(".riftreader-local\\opencode-runs\\"))
            self.assertTrue(stdout_path.is_file())
            self.assertTrue(stderr_path.is_file())
            self.assertTrue(run_envelope_path.is_file())
            self.assertIn("stream-out:stream prompt", stdout_path.read_text(encoding="utf-8"))
            self.assertIn("stream-err", stderr_path.read_text(encoding="utf-8"))
            self.assertIn("stream-out:stream prompt", envelope["stdoutPreview"])
            self.assertIn("stream-err", envelope["stderrPreview"])

    def test_streaming_command_keyboard_interrupt_returns_clean_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original_sleep = opencode_bridge._sleep
            try:
                opencode_bridge._sleep = lambda seconds: (_ for _ in ()).throw(KeyboardInterrupt())
                envelope = opencode_bridge.run_streaming_command_with_input(
                    "interrupt-test",
                    [sys.executable, "-c", "import time; time.sleep(30)"],
                    root,
                    stdin_text="",
                    timeout_seconds=30.0,
                )
            finally:
                opencode_bridge._sleep = original_sleep

            artifacts = envelope["artifacts"]

            self.assertFalse(envelope["ok"])
            self.assertTrue(envelope["interrupted"])
            self.assertEqual(envelope["error"], "KeyboardInterrupt")
            self.assertTrue((root / artifacts["stdout"]).is_file())
            self.assertTrue((root / artifacts["stderr"]).is_file())
            self.assertTrue((root / artifacts["runEnvelopeJson"]).is_file())

    def test_streaming_command_timeout_is_not_blocked_by_large_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            envelope = opencode_bridge.run_streaming_command_with_input(
                "large-stdin-timeout-test",
                [sys.executable, "-c", "import time; time.sleep(30)"],
                root,
                stdin_text="x" * 2_000_000,
                timeout_seconds=0.2,
            )

            artifacts = envelope["artifacts"]

            self.assertFalse(envelope["ok"])
            self.assertTrue(envelope["timedOut"])
            self.assertTrue((root / artifacts["stdout"]).is_file())
            self.assertTrue((root / artifacts["stderr"]).is_file())
            self.assertTrue((root / artifacts["runEnvelopeJson"]).is_file())

    def test_build_bridge_summary_writes_prompt_under_ignored_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".git").mkdir()
            (root / "agents.md").write_text("# agents\n", encoding="utf-8")
            (root / "docs" / "handoffs").mkdir(parents=True)
            (root / "docs" / "handoffs" / "latest.md").write_text("# Handoff\n\n## TL;DR\n\nTest\n", encoding="utf-8")
            (root / "docs" / "recovery").mkdir(parents=True)
            (root / "docs" / "recovery" / "current-truth.md").write_text("# Truth\n", encoding="utf-8")
            (root / "docs" / "recovery" / "current-truth.json").write_text(
                '{"movementGate":{"allowed":false,"status":"blocked"},"currentBlockers":["blocked"]}',
                encoding="utf-8",
            )
            (root / "docs" / "recovery" / "current-proof-anchor-readback.json").write_text(
                '{"status":"blocked-target-drift"}',
                encoding="utf-8",
            )

            summary = opencode_bridge.build_bridge_summary(root, lane="sitrep", check_opencode=False)

            self.assertTrue(str(summary["promptPath"]).startswith(".riftreader-local\\opencode-prompts\\"))
            self.assertTrue((root / str(summary["promptPath"]).replace("\\", "/")).is_file())
            self.assertEqual(summary["lane"], "sitrep")
            self.assertIsNone(summary["opencodeAgent"])
            self.assertFalse(summary["lanePolicy"]["allowsTrackedEdits"])
            self.assertEqual(summary["lanePolicy"]["allowedEditPaths"], [])
            self.assertEqual(summary["lanePolicy"]["groundingFiles"], [])
            self.assertEqual(summary["decisionPacket"]["kind"], "riftreader-decision-packet")
            self.assertIn("decisionPacket", summary["compactStatus"])
            prompt_text = (root / str(summary["promptPath"]).replace("\\", "/")).read_text(encoding="utf-8")
            self.assertIn("Prefer the local decision packet embedded in the preflight snapshot", prompt_text)
            self.assertIn('"decisionPacket"', prompt_text)
            self.assertIn('"llmReminder"', prompt_text)
            self.assertFalse(summary["safety"]["movementSent"])

    def test_self_test_generates_all_lane_prompts_without_opencode_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".git").mkdir()
            (root / "agents.md").write_text("# agents\n", encoding="utf-8")
            (root / "docs" / "handoffs").mkdir(parents=True)
            (root / "docs" / "handoffs" / "latest.md").write_text("# Handoff\n\n## TL;DR\n\nTest\n", encoding="utf-8")
            (root / "docs" / "recovery").mkdir(parents=True)
            (root / "docs" / "recovery" / "current-truth.md").write_text("# Truth\n", encoding="utf-8")
            (root / "docs" / "recovery" / "current-truth.json").write_text(
                '{"movementGate":{"allowed":false,"status":"blocked"},"currentBlockers":["blocked"]}',
                encoding="utf-8",
            )
            (root / "docs" / "recovery" / "current-proof-anchor-readback.json").write_text(
                '{"status":"blocked-target-drift"}',
                encoding="utf-8",
            )

            result = opencode_bridge.build_self_test(root)

            self.assertEqual(result["status"], "passed")
            self.assertFalse(result["safety"]["movementSent"])
            lanes = {item["lane"]: item for item in result["lanes"]}
            self.assertEqual(set(lanes), {"sitrep", "live-observer", "package-review", "integration"})
            self.assertGreater(lanes["integration"]["promptBytes"], 1000)
            self.assertTrue(lanes["integration"]["lanePolicy"]["allowsTrackedEdits"])
            self.assertIn("scripts/test_opencode_bridge.py", lanes["integration"]["lanePolicy"]["groundingFiles"])
            self.assertFalse(lanes["sitrep"]["lanePolicy"]["allowsTrackedEdits"])
            self.assertTrue((root / str(lanes["integration"]["promptPath"]).replace("\\", "/")).is_file())

    def test_example_config_allows_integration_preflight_and_validation(self) -> None:
        config_text = (REPO_ROOT / ".opencode" / "opencode.example.jsonc").read_text(encoding="utf-8")

        self.assertIn('"riftreader-integration"', config_text)
        self.assertIn("generated lanePolicy as authoritative", config_text)
        self.assertIn('".\\\\scripts\\\\riftreader-workflow-status.cmd --compact-json *": "allow"', config_text)
        self.assertIn('"git status --short --branch": "allow"', config_text)
        self.assertIn(
            '"python -m unittest scripts.test_opencode_bridge scripts.test_opencode_status_packet *": "allow"',
            config_text,
        )
        self.assertIn('"git add *": "deny"', config_text)
        self.assertIn('"*send-rift-key*": "deny"', config_text)


if __name__ == "__main__":
    unittest.main()
