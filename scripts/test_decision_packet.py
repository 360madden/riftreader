from __future__ import annotations

import json
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
    subprocess.run(["git", "add", "agents.md", "docs/recovery/current-truth.json", "docs/recovery/current-proof-anchor-readback.json"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class DecisionPacketTests(unittest.TestCase):
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

    def test_agent_plan_has_no_overlapping_write_paths(self) -> None:
        self.assertEqual(decision_packet.validate_agent_plan(decision_packet.build_agent_plan()), [])

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
            "blockers": ["actor-chain-candidate-only"],
        }

        markdown = decision_packet.build_markdown(packet)

        self.assertIn("# **🚦 NEXT ACTION — CONTINUE SAFELY**", markdown)
        self.assertIn("## **🔄 DO NOT STOP HERE**", markdown)


if __name__ == "__main__":
    unittest.main()
