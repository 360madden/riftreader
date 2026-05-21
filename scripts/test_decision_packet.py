from __future__ import annotations

import contextlib
import io
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

from riftreader_workflow import decision_packet  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "riftreader-tests@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "RiftReader Tests"], cwd=root, check=True)
    write_text(root / "agents.md", "# test\n")
    write_text(root / ".gitignore", ".riftreader-local/\n")
    write_json(
        root / "docs" / "recovery" / "current-truth.json",
        {
            "target": {
                "processName": "rift_x64",
                "processId": 100,
                "targetWindowHandle": "0xABC",
                "processStartUtc": "2026-05-21T14:00:00Z",
                "moduleBase": "0x1000",
                "inWorld": True,
                "live": True,
            },
            "bestCurrentCandidate": {
                "candidateId": "api-family-hit-000001",
                "addressHex": "0x2000",
                "candidateOnly": True,
                "promotionEligible": False,
                "status": "actor-like-current-pid-candidate-only",
            },
        },
    )
    write_json(
        root / "docs" / "recovery" / "current-proof-anchor-readback.json",
        {
            "status": "current-target-proofonly-passed",
            "lastUpdatedUtc": "2026-05-21T14:01:00Z",
            "target": {
                "processName": "rift_x64",
                "processId": 100,
                "targetWindowHandle": "0xABC",
                "processStartUtc": "2026-05-21T14:00:00Z",
                "moduleBase": "0x1000",
            },
            "latestValidation": {"movementAllowed": True, "movementSent": False},
        },
    )
    subprocess.run(
        ["git", "add", "agents.md", ".gitignore", "docs/recovery/current-truth.json", "docs/recovery/current-proof-anchor-readback.json"],
        cwd=root,
        check=True,
    )
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def init_empty_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "riftreader-tests@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "RiftReader Tests"], cwd=root, check=True)
    write_text(root / "agents.md", "# test\n")
    write_text(root / ".gitignore", ".riftreader-local/\n")
    subprocess.run(["git", "add", "agents.md", ".gitignore"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class DecisionPacketTests(unittest.TestCase):
    def test_clean_repo_without_live_target_blocks_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_empty_repo(root)

            packet = decision_packet.build_decision_packet(root)

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["targetEpoch"]["status"], "absent")
        self.assertIn("target-epoch-absent", packet["blockers"])
        self.assertEqual(packet["milestoneStatus"]["state"], "blocked-safe")

    def test_target_epoch_classifies_current_match(self) -> None:
        truth = {"target": {"processId": 1, "targetWindowHandle": "0x1", "inWorld": True}}
        proof = {"status": "current-target-proofonly-passed", "target": {"processId": 1, "targetWindowHandle": "0x1"}}

        result = decision_packet.classify_target_epoch(truth, proof)

        self.assertEqual(result["status"], "current")
        self.assertEqual(result["blockers"], [])

    def test_target_epoch_detects_pid_hwnd_process_and_module_drift(self) -> None:
        truth = {
            "target": {
                "processId": 2,
                "targetWindowHandle": "0x2",
                "processStartUtc": "2026-05-21T15:00:00Z",
                "moduleBase": "0x2000",
            }
        }
        proof = {
            "status": "current-target-proofonly-passed",
            "lastUpdatedUtc": "2026-05-21T14:00:00Z",
            "target": {
                "processId": 1,
                "targetWindowHandle": "0x1",
                "processStartUtc": "2026-05-21T14:00:00Z",
                "moduleBase": "0x1000",
            },
        }

        result = decision_packet.classify_target_epoch(truth, proof)

        self.assertEqual(result["status"], "stale")
        self.assertIn("target-epoch-pid-drift", result["blockers"])
        self.assertIn("target-epoch-hwnd-drift", result["blockers"])
        self.assertIn("target-epoch-process-start-drift", result["blockers"])
        self.assertIn("target-epoch-module-base-drift", result["blockers"])
        self.assertIn("proof-older-than-process-start", result["blockers"])

    def test_target_epoch_drift_scenarios_block_individually(self) -> None:
        base_truth_target = {
            "processId": 1,
            "targetWindowHandle": "0x1",
            "processStartUtc": "2026-05-21T14:00:00Z",
            "moduleBase": "0x1000",
            "inWorld": True,
        }
        base_proof_target = {
            "processId": 1,
            "targetWindowHandle": "0x1",
            "processStartUtc": "2026-05-21T14:00:00Z",
            "moduleBase": "0x1000",
        }
        cases = [
            ("processId", 2, "target-epoch-pid-drift"),
            ("targetWindowHandle", "0x2", "target-epoch-hwnd-drift"),
            ("processStartUtc", "2026-05-21T15:00:00Z", "target-epoch-process-start-drift"),
            ("moduleBase", "0x2000", "target-epoch-module-base-drift"),
        ]
        for field, value, blocker in cases:
            with self.subTest(field=field):
                truth_target = dict(base_truth_target)
                truth_target[field] = value
                result = decision_packet.classify_target_epoch(
                    {"target": truth_target},
                    {"status": "current-target-proofonly-passed", "target": base_proof_target},
                )

                self.assertEqual(result["status"], "stale")
                self.assertIn(blocker, result["blockers"])
                self.assertEqual(
                    result["staleAddressPolicy"],
                    "absolute heap addresses are historical hints only after PID/HWND/process-start/module-base drift",
                )

    def test_process_presence_is_not_proof(self) -> None:
        result = decision_packet.classify_target_epoch({"target": {"processId": 1, "live": True}}, {})

        self.assertEqual(result["processPresence"], "not-checked-process-presence-is-not-proof")
        self.assertIn(result["status"], {"in-world-unproven", "unknown"})

    def test_actor_chain_candidate_only_blocks_promotion(self) -> None:
        result = decision_packet.summarize_truth(
            {
                "bestCurrentCandidate": {
                    "candidateId": "api-family-hit-000001",
                    "candidateOnly": True,
                    "promotionEligible": False,
                    "status": "actor-like-candidate-only",
                }
            },
            {"status": "current-target-proofonly-passed"},
        )

        actor = result["actorChain"]
        self.assertEqual(actor["status"], "candidate-only")
        self.assertFalse(actor["promotionAllowed"])
        self.assertIn("actor-chain-candidate-only", actor["blockers"])
        self.assertIn("no-static-resolver-promoted", actor["blockers"])

    def test_validation_plan_selects_decision_packet_checks_for_python_change(self) -> None:
        plan = decision_packet.build_validation_plan(
            {"changedFiles": [{"path": "tools/riftreader_workflow/decision_packet.py"}]},
            "git",
        )
        labels = {item["label"] for item in plan["commands"]}

        self.assertIn("py-compile-decision-packet", labels)
        self.assertIn("decision-packet-tests", labels)
        self.assertIn("policy-lint-changed", labels)

    def test_dirty_docs_only_lane_and_commit_plan_are_coherent(self) -> None:
        git_state = {"changedFiles": [{"path": "docs/workflow/example.md", "generated": False}], "dirty": True}

        self.assertEqual(decision_packet.classify_lane(git_state, {"status": "current"}, {}), "docs")
        commit_plan = decision_packet.build_commit_plan(git_state, [{"ok": True}])

        self.assertTrue(commit_plan["recommended"])
        self.assertEqual(commit_plan["pathCategories"], ["docs"])
        self.assertEqual(commit_plan["suggestedMessage"], "Update RiftReader workflow docs")

    def test_commit_plan_excludes_generated_and_blocks_live_truth(self) -> None:
        generated = decision_packet.build_commit_plan(
            {"changedFiles": [{"path": "scripts/captures/run/summary.json", "generated": True}]}
        )
        live_truth = decision_packet.build_commit_plan(
            {"changedFiles": [{"path": "docs/recovery/current-truth.json", "generated": False}]}
        )

        self.assertFalse(generated["recommended"])
        self.assertEqual(generated["excludedGeneratedPaths"], ["scripts/captures/run/summary.json"])
        self.assertFalse(live_truth["recommended"])
        self.assertEqual(live_truth["reason"], "live-truth-paths-require-main-agent-review")

    def test_commit_plan_blocks_mixed_docs_code_and_generated_slice(self) -> None:
        mixed = decision_packet.build_commit_plan(
            {
                "changedFiles": [
                    {"path": "docs/workflow/example.md", "generated": False},
                    {"path": "tools/riftreader_workflow/decision_packet.py", "generated": False},
                    {"path": "scripts/captures/run/summary.json", "generated": True},
                ]
            },
            [{"ok": True}],
        )

        self.assertFalse(mixed["recommended"])
        self.assertEqual(mixed["reason"], "mixed-risk-worktree-split-required")
        self.assertEqual(mixed["pathCategories"], ["code", "docs"])
        self.assertEqual(mixed["excludedGeneratedPaths"], ["scripts/captures/run/summary.json"])

    def test_clean_branch_ahead_reports_commits_before_other_safe_work(self) -> None:
        safe_next = decision_packet.build_safe_next_action(
            "unknown",
            {"status": "current"},
            {"dirty": False, "ahead": 2},
            {"actorChain": {"status": "candidate-only"}},
        )

        self.assertEqual(safe_next["key"], "report-local-commits-ahead")
        self.assertEqual(safe_next["command"], ["git", "--no-pager", "status", "--short", "--branch"])

    def test_agent_plan_has_no_overlapping_write_paths(self) -> None:
        self.assertEqual(decision_packet.validate_agent_plan(decision_packet.build_agent_plan()), [])

    def test_high_risk_approval_blocker_requires_stop_state(self) -> None:
        self.assertEqual(decision_packet.milestone_state(["debugger-required"]), "blocked-needs-approval")
        reminder = decision_packet.build_llm_reminder({"command": ["ask"]}, "blocked-needs-approval")

        self.assertIn("debugger or CE would be required", reminder["mustStopIf"])

    def test_safe_validation_exit_two_is_known_safe_blocked_not_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script = root / "safe_blocker.py"
            write_text(script, "raise SystemExit(2)\n")
            plan = {
                "commands": [
                    decision_packet.command_spec(
                        "known-safe-blocker",
                        [sys.executable, str(script)],
                        "Fixture exits 2 as a known blocker.",
                        expected=(0, 2),
                    )
                ]
            }

            results = decision_packet.run_safe_validations(root, plan)

        self.assertEqual(results[0]["exitCode"], 2)
        self.assertTrue(results[0]["ok"])
        self.assertTrue(results[0]["knownSafeBlocked"])

    def test_llm_reminder_contains_continue_and_stop_rules(self) -> None:
        reminder = decision_packet.build_llm_reminder({"command": ["python", "x.py"]}, "blocked-safe")

        self.assertIn("safe validation passed", reminder["doNotStopIf"])
        self.assertIn("debugger or CE would be required", reminder["mustStopIf"])
        self.assertEqual(reminder["continueWith"]["command"], ["python", "x.py"])

    def test_build_decision_packet_from_temp_repo_reports_candidate_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)

            packet = decision_packet.build_decision_packet(root)

        self.assertEqual(packet["kind"], "riftreader-decision-packet")
        self.assertEqual(packet["targetEpoch"]["status"], "current")
        self.assertEqual(packet["truth"]["actorChain"]["status"], "candidate-only")
        self.assertIn("actor-chain-candidate-only", packet["blockers"])
        self.assertEqual(packet["milestoneStatus"]["state"], "blocked-safe")

    def test_malformed_current_truth_fails_closed_with_structured_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            write_text(root / "docs" / "recovery" / "current-truth.json", "{not-json")

            packet = decision_packet.build_decision_packet(root)

        self.assertEqual(packet["status"], "failed")
        self.assertIn("current-truth-malformed", packet["blockers"])
        self.assertTrue(any(str(item).startswith("current-truth-malformed:") for item in packet["errors"]))
        self.assertNotEqual(packet["targetEpoch"]["status"], "current")

    def test_malformed_current_proof_fails_closed_with_structured_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            write_text(root / "docs" / "recovery" / "current-proof-anchor-readback.json", "[]")

            packet = decision_packet.build_decision_packet(root)

        self.assertEqual(packet["status"], "failed")
        self.assertIn("current-proof-malformed", packet["blockers"])
        self.assertTrue(any(str(item).startswith("current-proof-malformed:") for item in packet["errors"]))
        self.assertNotEqual(packet["targetEpoch"]["status"], "current")

    def test_cache_reuses_packet_only_when_fingerprint_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            output_dir = root / ".riftreader-local" / "decision-packet" / "latest"

            packet = decision_packet.build_decision_packet(root)
            decision_packet.write_outputs(root, packet, output_dir)
            cached = decision_packet.build_decision_packet(root, use_cache=True, cache_dir=output_dir)

        self.assertEqual(cached["cacheStatus"], "reused")
        self.assertEqual(cached["performance"]["buildMode"], "cache-reused")
        self.assertTrue(cached["performance"]["cacheReused"])
        self.assertFalse(cached["performance"]["runSafeChecks"])
        self.assertIsInstance(cached["performance"]["totalDurationSeconds"], float)
        self.assertTrue(cached["cacheSafety"]["freshFingerprintChecked"])
        self.assertEqual(cached["targetEpoch"]["status"], "current")
        self.assertIn("actor-chain-candidate-only", cached["blockers"])

    def test_corrupted_cache_is_miss_not_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            output_dir = root / ".riftreader-local" / "decision-packet" / "latest"

            packet = decision_packet.build_decision_packet(root)
            decision_packet.write_outputs(root, packet, output_dir)
            write_text(output_dir / "decision-packet.json", "{corrupt-cache")
            rebuilt = decision_packet.build_decision_packet(root, use_cache=True, cache_dir=output_dir)

        self.assertEqual(rebuilt["cacheStatus"], "miss")
        self.assertEqual(rebuilt["performance"]["buildMode"], "fresh")
        self.assertFalse(rebuilt["performance"]["cacheReused"])
        self.assertEqual(rebuilt["targetEpoch"]["status"], "current")

    def test_corrupted_fingerprint_does_not_block_output_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            output_dir = root / ".riftreader-local" / "decision-packet" / "latest"

            packet = decision_packet.build_decision_packet(root)
            decision_packet.write_outputs(root, packet, output_dir)
            write_text(output_dir / "fingerprint.json", "{corrupt-fingerprint")
            artifacts = decision_packet.write_outputs(root, packet, output_dir)

        self.assertEqual(packet["cacheStatus"], "miss")
        self.assertEqual(
            decision_packet.normalize_path(artifacts["fingerprint"]),
            "riftreader-local/decision-packet/latest/fingerprint.json",
        )

    def test_cli_use_cache_reuses_written_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            first_stdout = io.StringIO()
            cached_stdout = io.StringIO()

            with contextlib.redirect_stdout(first_stdout):
                first_exit = decision_packet.main(["--repo-root", str(root), "--write", "--compact-json"])
            with contextlib.redirect_stdout(cached_stdout):
                cached_exit = decision_packet.main(["--repo-root", str(root), "--use-cache", "--compact-json"])
            cached_payload = json.loads(cached_stdout.getvalue())

        self.assertEqual(first_exit, 2)
        self.assertEqual(cached_exit, 2)
        self.assertEqual(cached_payload["cacheStatus"], "reused")
        self.assertEqual(cached_payload["performance"]["buildMode"], "cache-reused")
        self.assertTrue(cached_payload["performance"]["cacheReused"])
        self.assertIn("actor-chain-candidate-only", cached_payload["blockers"])

    def test_cli_explain_renders_reminder_commit_and_performance_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = decision_packet.main(["--repo-root", str(root), "--explain"])
            markdown = stdout.getvalue()

        self.assertEqual(exit_code, 2)
        self.assertIn("# **🚦 NEXT ACTION — CONTINUE SAFELY**", markdown)
        self.assertIn("## Commit planner", markdown)
        self.assertIn("# **⚠️ NOT COMMIT-READY**", markdown)
        self.assertIn("## Performance", markdown)
        self.assertIn("| Build mode | `fresh` |", markdown)
        self.assertIn("actor-chain-candidate-only", markdown)

    def test_cache_miss_after_current_truth_mtime_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            output_dir = root / ".riftreader-local" / "decision-packet" / "latest"
            truth_path = root / "docs" / "recovery" / "current-truth.json"

            packet = decision_packet.build_decision_packet(root)
            decision_packet.write_outputs(root, packet, output_dir)
            old_stat = truth_path.stat()
            os.utime(truth_path, (old_stat.st_atime + 10, old_stat.st_mtime + 10))
            rebuilt = decision_packet.build_decision_packet(root, use_cache=True, cache_dir=output_dir)

        self.assertEqual(rebuilt["cacheStatus"], "miss")
        self.assertEqual(rebuilt["performance"]["buildMode"], "fresh")
        self.assertFalse(rebuilt["performance"]["cacheReused"])
        self.assertEqual(rebuilt["targetEpoch"]["status"], "current")

    def test_run_safe_checks_disables_cache_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            init_repo(root)
            output_dir = root / ".riftreader-local" / "decision-packet" / "latest"

            packet = decision_packet.build_decision_packet(root)
            decision_packet.write_outputs(root, packet, output_dir)
            rebuilt = decision_packet.build_decision_packet(root, run_safe_checks=True, use_cache=True, cache_dir=output_dir)

        self.assertNotEqual(rebuilt["cacheStatus"], "reused")
        self.assertTrue(rebuilt["cacheSafety"]["runSafeChecksDisablesCache"])
        self.assertTrue(rebuilt["performance"]["runSafeChecks"])
        self.assertGreater(rebuilt["performance"]["safeValidationCommandCount"], 0)

    def test_compact_packet_schema_preserves_llm_reminder_contract(self) -> None:
        packet = {
            "schemaVersion": 1,
            "kind": "riftreader-decision-packet",
            "status": "blocked",
            "lane": "actor-chain",
            "risk": "high",
            "targetEpoch": {"status": "stale", "blockers": ["target-epoch-pid-drift"]},
            "safeNextAction": {"key": "safe", "command": ["python", "safe.py"], "why": "fixture"},
            "llmReminder": decision_packet.build_llm_reminder({"command": ["python", "safe.py"]}, "blocked-safe"),
            "milestoneStatus": {"state": "blocked-safe"},
            "commitPlan": {"recommended": False},
            "blockers": ["target-epoch-pid-drift"],
            "warnings": [],
            "cacheStatus": "miss",
            "performance": {"buildMode": "fresh", "cacheReused": False, "totalDurationSeconds": 0.01},
        }

        compact = decision_packet.compact_decision_packet(packet)

        self.assertEqual(
            set(compact),
            {
                "schemaVersion",
                "kind",
                "status",
                "lane",
                "risk",
                "targetEpoch",
                "safeNextAction",
                "llmReminder",
                "milestoneStatus",
                "commitPlan",
                "blockers",
                "warnings",
                "cacheStatus",
                "performance",
            },
        )
        self.assertEqual(compact["llmReminder"]["banner"], "# **🚦 NEXT ACTION — CONTINUE SAFELY**")
        self.assertIn("status helper returned a known blocker", compact["llmReminder"]["doNotStopIf"])
        self.assertIn("debugger or CE would be required", compact["llmReminder"]["mustStopIf"])
        self.assertEqual(compact["performance"]["buildMode"], "fresh")

    def test_markdown_renders_big_reminder_banner(self) -> None:
        packet = {
            "status": "blocked",
            "lane": "actor-chain",
            "risk": "high",
            "targetEpoch": {"status": "current"},
            "cacheStatus": "miss",
            "safeNextAction": {"key": "actor", "command": ["python", "actor.py"], "why": "candidate only"},
            "llmReminder": decision_packet.build_llm_reminder({"command": ["python", "actor.py"]}, "blocked-safe"),
            "milestoneStatus": {"state": "blocked-safe"},
            "validationPlan": {"commands": []},
            "commitPlan": {"recommended": False, "reason": "no-stageable-tracked-paths", "explicitPaths": []},
            "performance": {
                "buildMode": "fresh",
                "cacheReused": False,
                "runSafeChecks": False,
                "safeValidationCommandCount": 0,
                "safeValidationDurationSeconds": 0,
                "totalDurationSeconds": 0.01,
            },
            "blockers": ["actor-chain-candidate-only"],
        }

        markdown = decision_packet.build_markdown(packet)

        self.assertIn("# **🚦 NEXT ACTION — CONTINUE SAFELY**", markdown)
        self.assertIn("## **🔄 DO NOT STOP HERE**", markdown)
        self.assertIn("# **⚠️ NOT COMMIT-READY**", markdown)
        self.assertIn("## Performance", markdown)
        self.assertIn("| Build mode | `fresh` |", markdown)

    def test_markdown_renders_commit_ready_explicit_paths(self) -> None:
        packet = {
            "status": "passed",
            "lane": "docs",
            "risk": "low",
            "targetEpoch": {"status": "current"},
            "cacheStatus": "miss",
            "safeNextAction": {"key": "status", "command": ["git", "status"], "why": "fixture"},
            "llmReminder": decision_packet.build_llm_reminder({"command": ["git", "status"]}, "passed"),
            "milestoneStatus": {"state": "passed"},
            "validationPlan": {"commands": []},
            "commitPlan": {
                "recommended": True,
                "validationRequired": False,
                "suggestedMessage": "Update docs",
                "explicitPaths": ["docs/workflow/example.md"],
                "excludedGeneratedPaths": ["scripts/captures/run/summary.json"],
                "stageCommandPreview": "git add docs/workflow/example.md",
            },
            "performance": {
                "buildMode": "cache-reused",
                "cacheReused": True,
                "runSafeChecks": False,
                "safeValidationCommandCount": 0,
                "safeValidationDurationSeconds": 0,
                "totalDurationSeconds": 0.02,
            },
            "blockers": [],
        }

        markdown = decision_packet.build_markdown(packet)

        self.assertIn("# **✅ COMMIT-READY — EXPLICIT PATHS ONLY**", markdown)
        self.assertIn("`git add docs/workflow/example.md`", markdown)
        self.assertIn("`docs/workflow/example.md`", markdown)
        self.assertIn("`scripts/captures/run/summary.json`", markdown)
        self.assertIn("| Build mode | `cache-reused` |", markdown)
        self.assertIn("| Cache reused | `true` |", markdown)


if __name__ == "__main__":
    unittest.main()
