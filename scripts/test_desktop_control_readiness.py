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

from riftreader_workflow import desktop_control_readiness as readiness  # noqa: E402


def make_repo(root: Path) -> None:
    (root / ".git").mkdir()
    (root / "agents.md").write_text("# policy\n", encoding="utf-8")
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "riftreader-mcp-dashboard.cmd").write_text("@echo off\n", encoding="utf-8")
    (scripts / "riftreader-operator-lite.cmd").write_text("@echo off\n", encoding="utf-8")


class DesktopControlReadinessTests(unittest.TestCase):
    def test_readiness_blocks_until_browser_and_computer_observation_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = readiness.readiness_payload(root)

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("browser-use-dashboard-smoke-not-confirmed", payload["blockers"])
        self.assertIn("computer-use-native-pipe-not-confirmed", payload["blockers"])
        self.assertFalse(payload["safety"]["browserAutomated"])
        self.assertFalse(payload["safety"]["computerUseAutomated"])
        self.assertTrue(payload["surfaces"]["localDashboard"]["localhostOnly"])

    def test_readiness_passes_with_explicit_local_observation_artifact(self) -> None:
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

            payload = readiness.readiness_payload(root)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["blockers"], [])
        self.assertEqual(payload["latestObservation"]["path"], str(observation.relative_to(root)).replace("/", "\\"))

    def test_self_test_does_not_expose_absolute_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = readiness.self_test(root)
            text = json.dumps(payload)

        self.assertTrue(payload["ok"])
        self.assertNotIn(str(root), text)
        self.assertFalse(payload["statusPreview"]["safety"]["desktopClicksSent"])


if __name__ == "__main__":
    unittest.main()
