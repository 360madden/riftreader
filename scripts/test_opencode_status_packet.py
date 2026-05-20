#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import status_packet  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


class OpenCodeStatusPacketTests(unittest.TestCase):
    def test_opencode_version_command_uses_windows_shim_safe_form(self) -> None:
        command = status_packet.opencode_version_command()

        self.assertEqual(command[-2:], ["opencode", "--version"])
        if sys.platform == "win32":
            self.assertEqual(command[:3], ["cmd", "/d", "/c"])
        else:
            self.assertEqual(command, ["opencode", "--version"])

    def test_opencode_model_helpers_default_to_gpt55_and_parse_models(self) -> None:
        previous_model = os.environ.pop("RIFTREADER_OPENCODE_MODEL", None)
        previous_variant = os.environ.pop("RIFTREADER_OPENCODE_VARIANT", None)
        try:
            self.assertEqual(status_packet.desired_opencode_model(), "openai/gpt-5.5")
            self.assertEqual(status_packet.desired_opencode_variant(), "xhigh")
        finally:
            if previous_model is not None:
                os.environ["RIFTREADER_OPENCODE_MODEL"] = previous_model
            if previous_variant is not None:
                os.environ["RIFTREADER_OPENCODE_VARIANT"] = previous_variant
        self.assertEqual(status_packet.opencode_provider_from_model("openai/gpt-5.5"), "openai")
        self.assertIsNone(status_packet.opencode_provider_from_model("gpt-5.5"))
        self.assertEqual(
            status_packet.parse_opencode_models("\nopenai/gpt-5.4\nopenai/gpt-5.5\n\n"),
            ["openai/gpt-5.4", "openai/gpt-5.5"],
        )

    def test_opencode_model_command_uses_windows_shim_safe_form(self) -> None:
        command = status_packet.opencode_models_command("openai")

        self.assertEqual(command[-3:], ["opencode", "models", "openai"])
        if sys.platform == "win32":
            self.assertEqual(command[:3], ["cmd", "/d", "/c"])
        else:
            self.assertEqual(command, ["opencode", "models", "openai"])

    def test_find_latest_handoff_selects_newest_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            handoff_dir = root / "docs" / "handoffs"
            older = handoff_dir / "2026-05-15-old.md"
            newer = handoff_dir / "2026-05-16-new.md"
            write_text(older, "# Old handoff\n\n## TL;DR\n\nold")
            write_text(newer, "# New handoff\n\n## TL;DR\n\nnew")
            os.utime(older, (1_700_000_000, 1_700_000_000))
            os.utime(newer, (1_800_000_000, 1_800_000_000))

            latest = status_packet.find_latest_handoff(root)
            summary = status_packet.summarize_handoff(root, latest, [], [])

        self.assertEqual(latest, newer)
        self.assertEqual(summary["title"], "New handoff")
        self.assertEqual(summary["tldr"], "new")

    def test_collect_git_head_uses_checked_out_head_not_newer_side_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "riftreader-tests@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "RiftReader Tests"], cwd=root, check=True)
            write_text(root / "README.md", "main\n")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-m", "main current head"],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            subprocess.run(["git", "switch", "-c", "review/newer"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            write_text(root / "side.txt", "side\n")
            subprocess.run(["git", "add", "side.txt"], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-m", "newer side branch"],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            subprocess.run(["git", "switch", "main"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            errors: list[str] = []
            git_state = status_packet.collect_git(root, commit_count=5, ref_count=5, errors=errors)

        self.assertEqual(errors, [])
        self.assertEqual(git_state["head"]["subject"], "main current head")
        self.assertEqual(git_state["recentCommits"][0]["subject"], "main current head")
        self.assertNotIn("newer side branch", [commit["subject"] for commit in git_state["recentCommits"]])

    def test_summarize_blocked_proof_preserves_stale_anchor_boundary(self) -> None:
        proof = {
            "status": "blocked-target-drift",
            "lastUpdatedUtc": "2026-05-16T16:46:11Z",
            "target": {
                "processName": "rift_x64",
                "processId": 27552,
                "targetWindowHandle": "0x3411E2",
            },
            "latestValidation": {"status": "blocked-target-drift", "movementAllowed": False},
            "latestProofOnly": {"status": "blocked-target-drift", "movementSent": False},
            "staleProofPointer": {
                "archivedPointer": "docs\\recovery\\historical\\old.json",
                "reusePolicy": "do-not-use-as-current-proof",
                "preservedEvidence": {
                    "riftscanCandidateSource": {
                        "candidateId": "api-family-hit-000001",
                        "sourceAbsoluteAddressHex": "0x27B1ED850C0",
                        "matchFile": "candidates.jsonl",
                    }
                },
            },
        }

        summary = status_packet.summarize_current_proof(proof)

        self.assertEqual(summary["status"], "blocked-target-drift")
        self.assertFalse(summary["latestValidation"]["movementAllowed"])
        self.assertEqual(summary["staleAnchor"]["candidateId"], "api-family-hit-000001")
        self.assertEqual(summary["staleAnchor"]["addressHex"], "0x27B1ED850C0")
        self.assertEqual(summary["staleAnchor"]["reusePolicy"], "do-not-use-as-current-proof")

    def test_build_status_packet_reports_no_live_target_blocker_without_git_or_opencode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_text(root / "docs" / "handoffs" / "2026-05-16-handoff.md", "# Handoff\n\n## TL;DR\n\nblocked")
            write_text(root / "docs" / "recovery" / "current-truth.md", "# Truth\n\n## Verdict\n\nMovement is blocked.")
            write_json(
                root / "docs" / "recovery" / "current-truth.json",
                {
                    "status": "no_current_candidate_movement_blocked_reacquisition_required",
                    "updatedAtUtc": "2026-05-16T16:46:11Z",
                    "target": {"processName": "rift_x64", "processId": 27552, "targetWindowHandle": "0x3411E2"},
                    "movementGate": {
                        "allowed": False,
                        "status": "blocked-no-live-target-reacquisition-required",
                        "reason": "No live rift_x64 process is available.",
                    },
                    "currentBlockers": ["live-target-not-running:rift_x64"],
                    "nextRecommendedAction": "Load RIFT in-world before recovery.",
                },
            )
            write_json(
                root / "docs" / "recovery" / "current-proof-anchor-readback.json",
                {
                    "status": "blocked-target-drift",
                    "lastUpdatedUtc": "2026-05-16T16:46:11Z",
                    "target": {"processName": "rift_x64", "processId": 27552, "targetWindowHandle": "0x3411E2"},
                    "latestValidation": {"status": "blocked-target-drift", "movementAllowed": False},
                    "latestProofOnly": {"status": "blocked-target-drift", "movementSent": False},
                },
            )

            packet = status_packet.build_status_packet(
                root,
                run_coordinate_status=False,
                check_opencode=False,
                collect_git_state=False,
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("live-target-not-running:rift_x64", packet["blockers"])
        self.assertIn("current-proof-status:blocked-target-drift", packet["blockers"])
        self.assertIn("movement-not-allowed:blocked-no-live-target-reacquisition-required", packet["blockers"])
        self.assertFalse(packet["safety"]["movementSent"])
        self.assertFalse(packet["safety"]["gitMutation"])

    def test_build_status_packet_explains_live_artifact_pid_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_text(root / "docs" / "handoffs" / "2026-05-17-handoff.md", "# Handoff\n\n## TL;DR\n\nlive stale")
            write_text(root / "docs" / "recovery" / "current-truth.md", "# Truth\n\n## Verdict\n\nMovement is blocked.")
            write_json(
                root / "docs" / "recovery" / "current-truth.json",
                {
                    "status": "no_current_candidate_movement_blocked_reacquisition_required",
                    "updatedAtUtc": "2026-05-16T16:46:11Z",
                    "target": {"processName": "rift_x64", "processId": 27552, "targetWindowHandle": "0x3411E2"},
                    "movementGate": {"allowed": False, "status": "blocked-no-live-target-reacquisition-required"},
                    "currentBlockers": ["No live rift_x64 process was detected during offline recovery."],
                    "nextRecommendedAction": "Start/load RIFT into the character world.",
                },
            )
            write_json(
                root / "docs" / "recovery" / "current-proof-anchor-readback.json",
                {
                    "status": "blocked-target-drift",
                    "target": {"processName": "rift_x64", "processId": 27552, "targetWindowHandle": "0x3411E2"},
                    "latestValidation": {"status": "blocked-target-drift", "movementAllowed": False},
                    "latestProofOnly": {"status": "blocked-target-drift", "movementSent": False},
                },
            )
            coordinate_script = root / "scripts" / "coordinate_recovery_status.py"
            write_text(
                coordinate_script,
                "\n".join(
                    [
                        "import json, sys",
                        "print(json.dumps({",
                        "  'status': 'blocked',",
                        "  'blockers': ['artifact-target-pid-not-running:artifact=27552;live=22304'],",
                        "  'liveTarget': {",
                        "    'status': 'passed',",
                        "    'verdict': 'artifact-pid-stale',",
                        "    'artifactProcessName': 'rift_x64',",
                        "    'artifactPid': 27552,",
                        "    'artifactHwnd': '0x3411E2',",
                        "    'livePids': [22304]",
                        "  }",
                        "}))",
                        "raise SystemExit(2)",
                    ]
                ),
            )

            packet = status_packet.build_status_packet(
                root,
                run_coordinate_status=True,
                check_opencode=False,
                collect_git_state=False,
            )

        self.assertTrue(packet["liveTarget"]["artifactPidStale"])
        self.assertEqual(packet["liveTarget"]["livePids"], [22304])
        self.assertIn(
            "current-truth-stale-live-target-detected:artifact=27552;live=22304",
            packet["warnings"],
        )
        self.assertIn(
            "superseded-offline-blocker-live-target-detected:No live rift_x64 process was detected during offline recovery.",
            packet["warnings"],
        )
        self.assertNotIn("No live rift_x64 process was detected during offline recovery.", packet["blockers"])
        self.assertIn("live-target-artifact-pid-stale:artifact=27552;artifactHwnd=0x3411E2;live=22304", packet["blockers"])
        self.assertIn(
            "A rift_x64 process is visible with PID(s) [22304]",
            packet["currentTruth"]["summary"]["movementGate"]["reason"],
        )
        self.assertIn("rift_x64 process is visible with PID(s) [22304]", packet["nextRecommendedAction"])
        self.assertIn("do not reuse stale proof", packet["nextRecommendedAction"])

        compact = status_packet.compact_summary(packet)

        self.assertEqual(compact["kind"], "riftreader-local-compact-sitrep")
        self.assertEqual(compact["legacyKind"], "riftreader-opencode-compact-sitrep")
        self.assertTrue(compact["liveTarget"]["artifactPidStale"])
        self.assertIn("A rift_x64 process is visible with PID(s) [22304]", compact["movementGate"]["reason"])
        self.assertTrue(
            any("artifact-target-pid-not-running:artifact=27552;live=22304" in item for item in compact["blockers"])
        )
        self.assertFalse(any(item == "No live rift_x64 process was detected during offline recovery." for item in compact["blockers"]))

    def test_run_command_records_envelope_and_stdout_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            envelope = status_packet.run_command(
                "python-echo",
                [sys.executable, "-c", "print('ok')"],
                Path(temp_dir),
            )

        self.assertTrue(envelope["ok"])
        self.assertEqual(envelope["exitCode"], 0)
        self.assertEqual(envelope["stdoutPreview"].strip(), "ok")
        self.assertIn("durationSeconds", envelope)

    def test_compact_summary_reports_bridge_command_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_text(root / "scripts" / "riftreader-workflow-status.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-package-intake-selftest.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-local-artifact-bridge.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-family-neighborhood-analysis.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-emergency-release.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-live-input-surface-audit.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-character-select-plan.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-character-select-env-capture.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-character-login-resilience-plan.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-character-login-executor-contract.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-character-login-readiness-packet.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-character-login-crash-watch.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-character-login-screen-state.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-character-login-play-executor-gate.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-character-login-supervisor.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-launcher-inspection.cmd", "@echo off\n")
            write_text(root / "scripts" / "riftreader-sensitive-artifact-scan.cmd", "@echo off\n")
            packet = {
                "schemaVersion": 1,
                "kind": "riftreader-local-workflow-status-packet",
                "legacyKind": "riftreader-opencode-non-codex-status-packet",
                "generatedAtUtc": "2026-05-17T00:00:00Z",
                "status": "blocked",
                "repoRoot": str(root),
                "blockers": [],
                "warnings": [],
                "errors": [],
                "git": {},
                "liveTarget": {},
                "launcher": {},
                "currentProof": {"summary": {}},
                "currentTruth": {"summary": {}},
                "latestHandoff": {},
                "coordinateRecoveryStatus": {},
                "opencode": {
                    "retired": True,
                    "checked": False,
                    "desiredModel": "openai/gpt-5.5",
                    "desiredVariant": "xhigh",
                    "modelProvider": "openai",
                    "modelVisible": True,
                },
                "safety": {"movementSent": False, "gitMutation": False},
                "nextRecommendedAction": "none",
                "artifacts": {},
            }

            compact = status_packet.compact_summary(packet)

        commands = {item["key"]: item for item in compact["bridgeCommands"]}
        self.assertTrue(commands["compact-status"]["exists"])
        self.assertTrue(commands["package-intake-selftest"]["exists"])
        self.assertTrue(commands["local-artifact-bridge-selftest"]["exists"])
        self.assertIn("no persistent server", commands["local-artifact-bridge-selftest"]["safety"])
        self.assertTrue(commands["family-neighborhood-analysis"]["exists"])
        self.assertIn("no live process reads", commands["family-neighborhood-analysis"]["safety"])
        self.assertTrue(commands["emergency-release"]["exists"])
        self.assertIn("no key-down", commands["emergency-release"]["safety"])
        self.assertTrue(commands["live-input-surface-audit"]["exists"])
        self.assertIn("read-only repo scan", commands["live-input-surface-audit"]["safety"])
        self.assertTrue(commands["character-select-plan"]["exists"])
        self.assertIn("dry-run planning only", commands["character-select-plan"]["safety"])
        self.assertTrue(commands["character-select-env-capture"]["exists"])
        self.assertIn("screenshot-to-summary", commands["character-select-env-capture"]["safety"])
        self.assertTrue(commands["character-login-resilience-plan"]["exists"])
        self.assertIn("relogin planning only", commands["character-login-resilience-plan"]["safety"])
        self.assertTrue(commands["character-login-executor-contract"]["exists"])
        self.assertIn("contract validator only", commands["character-login-executor-contract"]["safety"])
        self.assertTrue(commands["character-login-readiness-packet"]["exists"])
        self.assertIn("consolidated login/relogin packet", commands["character-login-readiness-packet"]["safety"])
        self.assertTrue(commands["character-login-crash-watch"]["exists"])
        self.assertIn("crash/relogin watcher", commands["character-login-crash-watch"]["safety"])
        self.assertTrue(commands["character-login-screen-state"]["exists"])
        self.assertIn("screenshot classifier", commands["character-login-screen-state"]["safety"])
        self.assertTrue(commands["character-login-play-executor-gate"]["exists"])
        self.assertIn("Play-click gate validator", commands["character-login-play-executor-gate"]["safety"])
        self.assertTrue(commands["character-login-supervisor"]["exists"])
        self.assertIn("supervised login/relogin gate", commands["character-login-supervisor"]["safety"])
        self.assertTrue(commands["launcher-inspection"]["exists"])
        self.assertIn("read-only launcher/process/window inspection", commands["launcher-inspection"]["safety"])
        self.assertTrue(commands["sensitive-artifact-scan"]["exists"])
        self.assertIn("no secret values echoed", commands["sensitive-artifact-scan"]["safety"])
        self.assertFalse(commands["transport-probe-local-smoke"]["exists"])
        self.assertIn("no repo target writes", commands["package-intake-selftest"]["safety"])
        self.assertTrue(compact["opencode"]["retired"])
        self.assertFalse(compact["opencode"]["checked"])
        self.assertEqual(compact["opencode"]["desiredModel"], "openai/gpt-5.5")
        self.assertEqual(compact["opencode"]["desiredVariant"], "xhigh")
        self.assertTrue(compact["opencode"]["modelVisible"])

    def test_latest_launcher_inspection_is_added_to_compact_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / ".riftreader-local" / "launcher-inspection" / "run-20260520-000000-000000"
            write_json(
                run_dir / "launcher-inspection-summary.json",
                {
                    "status": "passed",
                    "generatedAtUtc": "2026-05-20T17:45:00Z",
                    "launcher": {
                        "present": True,
                        "processIds": [31812],
                        "windowState": "minimized-or-offscreen",
                        "mainWindow": {"windowHandle": "0x27017C"},
                    },
                    "game": {"present": True, "processIds": [80072]},
                    "state": {
                        "crashRecoveryState": "launcher-and-game-present",
                        "reloginState": "observe-current-game-child",
                        "automationRecommendation": "observe-process-tree-and-game-window-only",
                        "buttonAutomationPolicy": "blocked-hidden-or-minimized",
                        "riftChildOfLauncher": True,
                    },
                    "visibleStateClassifier": {"safeToAutomateButtons": False},
                    "relaunchReadiness": {"status": "not-needed-game-present"},
                    "blockers": ["launcher-button-automation-blocked-until-visible-state-classified"],
                    "warnings": ["process-command-lines-redacted-by-default"],
                },
            )
            write_text(root / ".riftreader-local" / "launcher-inspection" / "latest-run.txt", str(run_dir))

            launcher = status_packet.latest_launcher_inspection(root, [], [])
            packet = {
                "schemaVersion": 1,
                "kind": "riftreader-local-workflow-status-packet",
                "legacyKind": "riftreader-opencode-non-codex-status-packet",
                "generatedAtUtc": "2026-05-20T17:46:00Z",
                "status": "blocked",
                "repoRoot": str(root),
                "blockers": [],
                "warnings": [],
                "errors": [],
                "git": {},
                "liveTarget": {},
                "launcher": launcher,
                "currentProof": {"summary": {}},
                "currentTruth": {"summary": {}},
                "latestHandoff": {},
                "coordinateRecoveryStatus": {},
                "opencode": {},
                "safety": {"movementSent": False, "gitMutation": False},
                "nextRecommendedAction": "none",
                "artifacts": {},
            }

            compact = status_packet.compact_summary(packet)

        self.assertEqual(compact["launcher"]["status"], "passed")
        self.assertEqual(compact["launcher"]["state"], "launcher-and-game-present")
        self.assertEqual(compact["launcher"]["launcherPids"], [31812])
        self.assertEqual(compact["launcher"]["riftPids"], [80072])
        self.assertTrue(compact["launcher"]["riftChildOfLauncher"])
        self.assertEqual(compact["launcher"]["buttonAutomationPolicy"], "blocked-hidden-or-minimized")
        self.assertEqual(compact["launcher"]["relaunchReadiness"]["status"], "not-needed-game-present")
        self.assertFalse(compact["launcher"]["visibleStateClassifier"]["safeToAutomateButtons"])
        self.assertIn(compact["launcher"]["freshness"]["status"], {"fresh", "stale"})

    def test_freshness_summary_classifies_stale_artifacts(self) -> None:
        now = status_packet.datetime(2026, 5, 20, 18, 0, tzinfo=status_packet.timezone.utc)

        fresh = status_packet.freshness_summary("2026-05-20T17:59:30Z", now=now, max_age_seconds=60)
        stale = status_packet.freshness_summary("2026-05-20T17:00:00Z", now=now, max_age_seconds=60)

        self.assertEqual(fresh["status"], "fresh")
        self.assertEqual(stale["status"], "stale")
        self.assertEqual(stale["ageSeconds"], 3600)

    def test_latest_character_login_supervisor_compact_summary_omits_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / ".riftreader-local" / "character-login-supervisor" / "run-20260520-000000-000000"
            approval_token = ":".join(["ENTER-WORLD", "ATANK", "80072", "0xD10C20"])
            write_json(
                run_dir / "character-login-supervisor-summary.json",
                {
                    "status": "blocked-approval-required",
                    "generatedAtUtc": "2026-05-20T17:45:00Z",
                    "targetCharacter": "ATANK",
                    "target": {"processId": 80072, "windowHandle": "0xD10C20"},
                    "selection": {"selectedCharacter": "ATANK"},
                    "childStatuses": {"screenClassification": "character-selection-not-in-world"},
                    "supervisorDecision": {
                        "futureExecutorMayClickPlay": False,
                        "mayClickPlayInThisSupervisor": False,
                    },
                    "futureMcpActionManifest": {
                        "status": "blocked",
                        "approval": {"token": approval_token},
                    },
                    "dataBlockers": [],
                    "executionBlockers": ["explicit-world-entry-approval-token-missing-or-mismatched"],
                },
            )
            write_text(root / ".riftreader-local" / "character-login-supervisor" / "latest-run.txt", str(run_dir))

            supervisor = status_packet.latest_character_login_supervisor(root, [], [])

        self.assertEqual(supervisor["status"], "blocked-approval-required")
        self.assertEqual(supervisor["targetCharacter"], "ATANK")
        self.assertTrue(supervisor["approvalTokenRequired"])
        self.assertFalse(supervisor["approvalTokenStoredInStatus"])
        self.assertNotIn("ENTER-WORLD", json.dumps(supervisor))

    def test_write_outputs_uses_ignored_local_status_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = {
                "schemaVersion": 1,
                "kind": "riftreader-local-workflow-status-packet",
                "legacyKind": "riftreader-opencode-non-codex-status-packet",
                "generatedAtUtc": "2026-05-16T00:00:00Z",
                "status": "blocked",
                "blockers": ["live-target-not-running:rift_x64"],
                "warnings": [],
                "errors": [],
                "git": {},
                "liveTarget": {},
                "launcher": {},
                "currentProof": {"summary": {}},
                "currentTruth": {"summary": {}},
                "latestHandoff": {},
                "coordinateRecoveryStatus": {},
                "opencode": {},
                "safety": {"movementSent": False, "gitMutation": False},
                "nextRecommendedAction": "Load RIFT in-world before recovery.",
                "artifacts": {},
            }

            artifacts = status_packet.write_outputs(packet, root)

            summary_json = root / artifacts["summaryJson"]
            summary_md = root / artifacts["summaryMarkdown"]
            compact_json = root / artifacts["compactJson"]

            self.assertTrue(artifacts["summaryJson"].startswith(".riftreader-local\\workflow-status\\"))
            self.assertTrue(summary_json.is_file())
            self.assertTrue(summary_md.is_file())
            self.assertTrue(compact_json.is_file())
            self.assertTrue((root / artifacts["compactMarkdown"]).is_file())
            compact = json.loads(compact_json.read_text(encoding="utf-8"))
            self.assertEqual(compact["artifacts"]["summaryJson"], artifacts["summaryJson"])
            self.assertEqual(compact["artifacts"]["compactJson"], artifacts["compactJson"])

    def test_parser_keeps_opencode_check_off_by_default(self) -> None:
        args = status_packet.build_parser().parse_args([])

        self.assertFalse(args.check_opencode)
        self.assertFalse(args.skip_opencode_check)


if __name__ == "__main__":
    unittest.main()
