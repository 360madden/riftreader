#!/usr/bin/env python3

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

from riftreader_workflow import desktop_control_queue_contract as queue_contract  # noqa: E402
from riftreader_workflow import desktop_control_readiness as readiness  # noqa: E402


def make_repo(root: Path) -> None:
    (root / ".git").mkdir()
    (root / "agents.md").write_text("# policy\n", encoding="utf-8")
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "riftreader-mcp-dashboard.cmd").write_text("@echo off\n", encoding="utf-8")
    (scripts / "riftreader-operator-lite.cmd").write_text("@echo off\n", encoding="utf-8")


class DesktopControlQueueContractTests(unittest.TestCase):
    def test_contract_is_plan_only_and_blocks_execution_until_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = queue_contract.contract_payload(root)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "passed")
        self.assertFalse(payload["execution"]["enabled"])
        self.assertFalse(payload["execution"]["executorImplemented"])
        self.assertFalse(payload["execution"]["mcpToolExposed"])
        self.assertIn("computer-use-native-pipe-not-confirmed", payload["execution"]["currentReadinessBlockers"])
        self.assertTrue(payload["execution"]["computerUseBlocked"])
        self.assertTrue(payload["safety"]["contractOnly"])
        self.assertFalse(payload["safety"]["executionEndpoint"])
        self.assertFalse(payload["safety"]["desktopClicksSent"])
        self.assertIn("desktop-click", payload["queueItemSchema"]["forbiddenActionFamilies"])
        self.assertIn("rift-movement", payload["queueItemSchema"]["forbiddenActionFamilies"])
        self.assertTrue(payload["queueDraftViewer"]["safety"]["viewerOnly"])
        self.assertFalse(payload["queueDraftViewer"]["safety"]["draftWriteEndpoint"])
        self.assertFalse(payload["queueDraftViewer"]["safety"]["executionEndpoint"])
        self.assertEqual(payload["chatGptWindowDiscovery"]["actionKey"], "chatgpt-window-discovery-no-input")
        self.assertFalse(payload["chatGptWindowDiscovery"]["ok"])

    def test_contract_reflects_passed_readiness_without_enabling_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            observation = root / readiness.OBSERVATION_ROOT / "20260608T000000Z" / "observation.json"
            observation.parent.mkdir(parents=True)
            observation.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "kind": "riftreader-desktop-control-observation",
                        "browserUse": {"dashboardSmokeOk": True},
                        "computerUse": {"nativePipeOk": True, "listAppsOk": True},
                    }
                ),
                encoding="utf-8",
            )

            payload = queue_contract.contract_payload(root)

        self.assertTrue(payload["execution"]["currentDesktopReadinessOk"])
        self.assertEqual(payload["execution"]["currentReadinessBlockers"], [])
        self.assertFalse(payload["execution"]["enabled"])
        self.assertFalse(payload["safety"]["executionEndpoint"])
        self.assertTrue(payload["chatGptWindowDiscovery"]["ok"])
        self.assertEqual(payload["chatGptWindowDiscovery"]["status"], "ready")

    def test_queue_draft_viewer_summarizes_latest_valid_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            draft_root = root / queue_contract.QUEUE_DRAFT_ROOT
            draft_root.mkdir(parents=True)
            (draft_root / "001-valid.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "kind": "riftreader-desktop-control-queue-item",
                        "queueId": "queue-test-001",
                        "actionKey": "chatgpt-window-discovery-no-input",
                        "surface": "computer-use",
                        "intent": "Discover candidate ChatGPT windows without input.",
                        "requiresHumanApproval": True,
                        "dryRunOnly": True,
                    }
                ),
                encoding="utf-8",
            )

            payload = queue_contract.queue_draft_viewer_payload(root)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["latestDraft"]["queueId"], "queue-test-001")
        self.assertTrue(payload["latestDraft"]["valid"])
        self.assertEqual(payload["latestDraft"]["blockers"], [])

    def test_queue_item_validation_rejects_execution_like_draft(self) -> None:
        blockers = queue_contract.validate_queue_item(
            {
                "schemaVersion": 1,
                "kind": "riftreader-desktop-control-queue-item",
                "queueId": "queue-test-unsafe",
                "actionKey": "desktop-click",
                "surface": "computer-use",
                "intent": "desktop-click on ChatGPT",
                "requiresHumanApproval": False,
                "dryRunOnly": False,
            }
        )

        self.assertIn("actionKey-not-allowed-before-readiness", blockers)
        self.assertIn("dryRunOnly-not-true", blockers)
        self.assertIn("requiresHumanApproval-not-true", blockers)
        self.assertIn("forbidden-action-family:desktop-click", blockers)

    def test_self_test_does_not_expose_absolute_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = queue_contract.self_test(root)

        text = json.dumps(payload)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["blockers"], [])
        self.assertNotIn(str(root), text)


if __name__ == "__main__":
    unittest.main()
