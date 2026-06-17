#!/usr/bin/env python3

from __future__ import annotations

import sys
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import bounded_repo_commands as commands  # noqa: E402


class BoundedRepoCommandsTests(unittest.TestCase):
    def test_registry_lists_only_initial_safe_status_and_validation_commands(self) -> None:
        payload = commands.registry_payload()

        self.assertTrue(payload["ok"], payload.get("blockers"))
        self.assertEqual(payload["registryVersion"], commands.REGISTRY_VERSION)
        self.assertEqual(
            sorted(item["key"] for item in payload["commands"]),
            [
                "current_head_ci_status",
                "mcp_final_status",
                "mcp_server_status",
                "test_mcp_server_status",
                "validate_mcp_sdk",
            ],
        )
        self.assertFalse(payload["safety"]["mcpToolExposed"])
        self.assertFalse(payload["safety"]["commandExecuted"])

    def test_safe_command_plan_uses_fixed_argv_not_shell_string(self) -> None:
        payload = commands.plan_command("mcp_server_status")

        self.assertTrue(payload["ok"], payload.get("blockers"))
        self.assertEqual(payload["argv"], ["cmd", "/c", "scripts\\riftreader-mcp-server-status.cmd", "--json"])
        self.assertEqual(payload["expectedExitCodes"], [0, 1, 2])
        self.assertEqual(payload["cwd"], "repo-root")
        self.assertFalse(payload["shellStringAccepted"])
        self.assertTrue(payload["readOnly"])
        self.assertFalse(payload["safety"]["gitMutation"])
        self.assertFalse(payload["safety"]["providerWrites"])
        self.assertFalse(payload["safety"]["commandExecuted"])

    def test_unknown_command_key_blocks(self) -> None:
        payload = commands.plan_command("git_reset_hard")

        self.assertFalse(payload["ok"])
        self.assertIn("unknown-command-key:git_reset_hard", payload["blockers"])
        self.assertEqual(payload["argv"], [])

    def test_registry_version_mismatch_blocks(self) -> None:
        payload = commands.plan_command("mcp_server_status", expected_registry_version="old")

        self.assertFalse(payload["ok"])
        self.assertIn(f"registry-version-mismatch:old:{commands.REGISTRY_VERSION}", payload["blockers"])

    def test_unknown_parameter_blocks(self) -> None:
        payload = commands.plan_command("mcp_server_status", {"extra": "nope"})

        self.assertFalse(payload["ok"])
        self.assertIn("parameter-not-allowed:extra", payload["blockers"])

    def test_timeout_above_registry_max_blocks(self) -> None:
        payload = commands.plan_command("mcp_server_status", timeout_seconds=999)

        self.assertFalse(payload["ok"])
        self.assertIn("timeout-exceeds-registry-max:999>25.0", payload["blockers"])

    def test_destructive_argv_fragment_is_rejected_by_spec_validation(self) -> None:
        bad = commands.BoundedCommandSpec(
            key="bad_reset",
            title="Bad reset",
            description="Bad destructive command",
            risk_class="destructive",
            argv_template=("git", "reset", "--hard"),
            expected_exit_codes=(0,),
            timeout_seconds=10,
            max_stdout_bytes=1000,
            max_stderr_bytes=1000,
            safety_flags=commands.default_command_safety_flags(),
        )

        blockers = commands.validate_command_spec(bad)

        self.assertIn("forbidden-argv-fragment:git", blockers)
        self.assertIn("forbidden-argv-fragment:reset", blockers)

    def test_live_provider_and_debugger_fragments_are_rejected_by_spec_validation(self) -> None:
        cases = {
            "bad_live": ("python", "scripts\\live.py", "rift_x64", "/reloadui"),
            "bad_provider": ("python", "scripts\\provider.py", "ChromaLink"),
            "bad_debugger": ("python", "scripts\\debug.py", "x64dbg"),
        }

        for key, argv in cases.items():
            with self.subTest(key=key):
                bad = commands.BoundedCommandSpec(
                    key=key,
                    title=key,
                    description="Unsafe command",
                    risk_class="unsafe",
                    argv_template=argv,
                    expected_exit_codes=(0,),
                    timeout_seconds=10,
                    max_stdout_bytes=1000,
                    max_stderr_bytes=1000,
                    safety_flags=commands.default_command_safety_flags(),
                )

                blockers = commands.validate_command_spec(bad)

                self.assertTrue(
                    any(blocker.startswith("forbidden-argv-fragment:") for blocker in blockers),
                    blockers,
                )

    def test_cmd_c_must_target_repo_script_wrapper(self) -> None:
        bad = commands.BoundedCommandSpec(
            key="bad_cmd",
            title="Bad cmd",
            description="Bad arbitrary cmd use",
            risk_class="shell",
            argv_template=("cmd", "/c", "echo", "hello"),
            expected_exit_codes=(0,),
            timeout_seconds=10,
            max_stdout_bytes=1000,
            max_stderr_bytes=1000,
            safety_flags=commands.default_command_safety_flags(),
        )

        blockers = commands.validate_command_spec(bad)

        self.assertIn("cmd-wrapper-not-repo-script:bad_cmd", blockers)

    def test_self_test_does_not_execute_commands(self) -> None:
        payload = commands.self_test()

        self.assertTrue(payload["ok"], payload.get("blockers"))
        self.assertFalse(payload["safety"]["commandExecuted"])
        self.assertFalse(payload["safety"]["mcpToolExposed"])

    def test_run_command_executes_only_registry_argv_and_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".git").mkdir()
            (root / "agents.md").write_text("# test\n", encoding="utf-8")
            completed = subprocess.CompletedProcess(
                args=["cmd", "/c", "scripts\\riftreader-mcp-server-status.cmd", "--json"],
                returncode=0,
                stdout="{\"ok\":true}",
                stderr="",
            )
            with mock.patch.object(commands.subprocess, "run", return_value=completed) as run:
                payload = commands.run_command("mcp_server_status", repo_root=root)
            summary_path = Path(payload["summaryPath"])
            self.assertTrue(summary_path.is_file())
            self.assertTrue(summary_path.resolve().is_relative_to(root.resolve()))

        run.assert_called_once()
        called = run.call_args.kwargs
        self.assertEqual(run.call_args.args[0], ["cmd", "/c", "scripts\\riftreader-mcp-server-status.cmd", "--json"])
        self.assertEqual(called["cwd"], root.resolve())
        self.assertFalse(called["check"])
        self.assertEqual(called["stdin"], subprocess.DEVNULL)
        self.assertTrue(payload["ok"], payload.get("blockers"))
        self.assertTrue(payload["commandExecuted"])
        self.assertFalse(payload["safety"]["shellStringAccepted"])
        self.assertFalse(payload["safety"]["arbitraryCommand"])
        self.assertEqual(payload["stdoutPreview"], "{\"ok\":true}")

    def test_replay_run_summary_validates_successful_envelope_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".git").mkdir()
            (root / "agents.md").write_text("# test\n", encoding="utf-8")
            completed = subprocess.CompletedProcess(
                args=["cmd", "/c", "scripts\\riftreader-mcp-server-status.cmd", "--json"],
                returncode=0,
                stdout="{\"ok\":true,\"status\":\"passed\"}",
                stderr="",
            )
            with mock.patch.object(commands.subprocess, "run", return_value=completed):
                run_payload = commands.run_command("mcp_server_status", repo_root=root)
            with mock.patch.object(commands.subprocess, "run") as run:
                replay = commands.replay_run_summary(run_payload["summaryPath"], repo_root=root)

        run.assert_not_called()
        self.assertTrue(replay["ok"], replay.get("blockers"))
        self.assertTrue(replay["summaryEnvelopeValid"])
        self.assertEqual(replay["commandKey"], "mcp_server_status")
        self.assertEqual(replay["commandStatus"], "passed")
        self.assertTrue(replay["commandOk"])
        self.assertEqual(replay["argv"], ["cmd", "/c", "scripts\\riftreader-mcp-server-status.cmd", "--json"])
        self.assertEqual(len(replay["summarySha256"]), 64)
        self.assertFalse(replay["safety"]["commandExecuted"])
        self.assertTrue(replay["safety"]["auditReplay"])

    def test_list_run_summaries_indexes_successful_and_blocked_envelopes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".git").mkdir()
            (root / "agents.md").write_text("# test\n", encoding="utf-8")
            passed = subprocess.CompletedProcess(
                args=["cmd", "/c", "scripts\\riftreader-mcp-server-status.cmd", "--json"],
                returncode=0,
                stdout="{\"ok\":true,\"status\":\"passed\"}",
                stderr="",
            )
            blocked = subprocess.CompletedProcess(
                args=["cmd", "/c", "scripts\\riftreader-mcp-server-status.cmd", "--json"],
                returncode=1,
                stdout='{"ok":false,"status":"blocked","blockers":["runtime-stale"]}',
                stderr="",
            )
            with mock.patch.object(commands.subprocess, "run", side_effect=[passed, blocked]):
                commands.run_command("mcp_server_status", repo_root=root)
                commands.run_command("mcp_server_status", repo_root=root)
            with mock.patch.object(commands.subprocess, "run") as run:
                index = commands.list_run_summaries("mcp_server_status", repo_root=root, limit=5)

        run.assert_not_called()
        self.assertTrue(index["ok"], index.get("blockers"))
        self.assertEqual(index["runCount"], 2)
        self.assertTrue(index["runs"][0]["summaryPath"].endswith("run-summary.json"))
        self.assertEqual(
            sorted(item["commandStatus"] for item in index["runs"]),
            ["blocked", "passed"],
        )
        self.assertFalse(index["safety"]["commandExecuted"])
        self.assertTrue(index["safety"]["auditReplay"])

    def test_replay_run_summary_blocks_paths_outside_audit_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            (root / ".git").mkdir()
            (root / "agents.md").write_text("# test\n", encoding="utf-8")
            outside = Path(temp_dir) / "run-summary.json"
            outside.write_text("{}", encoding="utf-8")

            replay = commands.replay_run_summary(outside, repo_root=root)

        self.assertFalse(replay["ok"])
        self.assertFalse(replay["summaryEnvelopeValid"])
        self.assertIn("summary-path-outside-audit-root", replay["blockers"])
        self.assertFalse(replay["safety"]["commandExecuted"])

    def test_run_command_blocks_unknown_without_execution(self) -> None:
        with mock.patch.object(commands.subprocess, "run") as run:
            payload = commands.run_command("git_reset_hard")

        run.assert_not_called()
        self.assertFalse(payload["ok"])
        self.assertFalse(payload["commandExecuted"])
        self.assertIn("unknown-command-key:git_reset_hard", payload["blockers"])

    def test_run_command_propagates_blocked_json_child_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".git").mkdir()
            (root / "agents.md").write_text("# test\n", encoding="utf-8")
            completed = subprocess.CompletedProcess(
                args=["cmd", "/c", "scripts\\riftreader-mcp-server-status.cmd", "--json"],
                returncode=1,
                stdout='{"ok":false,"status":"blocked","blockers":["runtime-stale"]}',
                stderr="",
            )
            with mock.patch.object(commands.subprocess, "run", return_value=completed):
                payload = commands.run_command("mcp_server_status", repo_root=root)

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(payload["commandExecuted"])
        self.assertIn("child:runtime-stale", payload["blockers"])


if __name__ == "__main__":
    unittest.main()
