#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
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
        self.assertEqual(payload["repairGuide"]["blocker"], "computer-use-native-pipe-not-confirmed")
        self.assertIn("PowerShell SendKeys", payload["repairGuide"]["doNotUseFallbacks"])

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
        self.assertEqual(payload["recommendedNextActions"][0]["key"], "maintenance-loop")

    def test_partial_observation_does_not_recommend_finished_browser_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            observation = root / readiness.OBSERVATION_ROOT / "20260608T010000Z" / "observation.json"
            observation.parent.mkdir(parents=True)
            observation.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "kind": "riftreader-desktop-control-observation",
                        "browserUse": {"dashboardSmokeOk": True},
                        "computerUse": {"nativePipeOk": False, "listAppsOk": False},
                    }
                ),
                encoding="utf-8",
            )

            payload = readiness.readiness_payload(root)

        action_keys = [item["key"] for item in payload["recommendedNextActions"]]
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["surfaces"]["browserUse"]["status"], "passed")
        self.assertEqual(payload["surfaces"]["computerUse"]["status"], "blocked")
        self.assertNotIn("browser-use-dashboard-smoke-not-confirmed", payload["blockers"])
        self.assertIn("computer-use-native-pipe-not-confirmed", payload["blockers"])
        self.assertNotIn("run-no-write-browser-dashboard-smoke", action_keys)
        self.assertIn("repair-computer-use-native-pipe", action_keys)

    def test_stale_observation_blocks_even_when_smokes_were_true(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            observation = root / readiness.OBSERVATION_ROOT / "20260101T000000Z" / "observation.json"
            observation.parent.mkdir(parents=True)
            observation.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "kind": "riftreader-desktop-control-observation",
                        "generatedAtUtc": "2026-01-01T00:00:00Z",
                        "browserUse": {"dashboardSmokeOk": True},
                        "computerUse": {"nativePipeOk": True, "listAppsOk": True},
                    }
                ),
                encoding="utf-8",
            )

            payload = readiness.readiness_payload(root)

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("desktop-control-observation-stale", payload["blockers"])
        self.assertTrue(payload["latestObservation"]["stale"])
        self.assertGreater(payload["latestObservation"]["ageSeconds"], readiness.OBSERVATION_MAX_AGE_SECONDS)

    def test_computer_readiness_requires_list_apps_after_native_pipe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            observation = root / readiness.OBSERVATION_ROOT / "20260608T011500Z" / "observation.json"
            observation.parent.mkdir(parents=True)
            observation.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "kind": "riftreader-desktop-control-observation",
                        "browserUse": {"dashboardSmokeOk": True},
                        "computerUse": {"nativePipeOk": True, "listAppsOk": False},
                    }
                ),
                encoding="utf-8",
            )

            payload = readiness.readiness_payload(root)

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["surfaces"]["browserUse"]["status"], "passed")
        self.assertEqual(payload["surfaces"]["computerUse"]["status"], "blocked")
        self.assertTrue(payload["latestObservation"]["computerUseNativePipeOk"])
        self.assertFalse(payload["latestObservation"]["computerUseListAppsOk"])
        self.assertNotIn("computer-use-native-pipe-not-confirmed", payload["blockers"])
        self.assertIn("computer-use-list-apps-not-confirmed", payload["blockers"])

    def test_record_observation_writes_ignored_local_artifact_and_updates_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            args = readiness.build_parser().parse_args(
                [
                    "--record-observation",
                    "--browser-dashboard-smoke-ok",
                    "--computer-use-stage",
                    "setup",
                    "--computer-use-error",
                    "Computer Use native pipe path is unavailable",
                ]
            )

            result = readiness.write_observation(root, args)
            observation_path = root / result["observationPath"].replace("\\", "/")
            observation_exists = observation_path.is_file()
            observation = json.loads(observation_path.read_text(encoding="utf-8"))
            payload = readiness.readiness_payload(root)

        self.assertTrue(result["ok"])
        self.assertTrue(observation_exists)
        self.assertEqual(observation["kind"], "riftreader-desktop-control-observation")
        self.assertTrue(observation["browserUse"]["dashboardSmokeOk"])
        self.assertFalse(observation["computerUse"]["nativePipeOk"])
        self.assertEqual(observation["computerUse"]["stage"], "setup")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["surfaces"]["browserUse"]["status"], "passed")
        self.assertEqual(payload["surfaces"]["computerUse"]["status"], "blocked")
        self.assertFalse(payload["latestObservation"]["stale"])
        self.assertIn("computer-use-native-pipe-not-confirmed", payload["blockers"])

    def test_observation_age_uses_file_mtime_when_generated_at_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            observation = root / readiness.OBSERVATION_ROOT / "20260608T020000Z" / "observation.json"
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
            generated_at = datetime.fromisoformat(payload["latestObservation"]["generatedAtUtc"].replace("Z", "+00:00"))

        self.assertTrue(payload["ok"])
        self.assertLess(abs((datetime.now(timezone.utc) - generated_at).total_seconds()), 60)

    def test_self_test_does_not_expose_absolute_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)

            payload = readiness.self_test(root)
            text = json.dumps(payload)

        self.assertTrue(payload["ok"])
        self.assertNotIn(str(root), text)
        self.assertFalse(payload["statusPreview"]["safety"]["desktopClicksSent"])

    def test_repair_guide_is_guide_only_and_has_record_commands(self) -> None:
        payload = readiness.repair_guide_payload()

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked-safe")
        self.assertEqual(payload["knownError"], "Computer Use native pipe path is unavailable")
        self.assertTrue(payload["safety"]["guideOnly"])
        self.assertFalse(payload["safety"]["desktopClicksSent"])
        self.assertFalse(payload["safety"]["computerUseAutomated"])
        self.assertIn("--computer-use-native-pipe-ok", payload["recordSuccessCommand"])
        self.assertIn("--computer-use-error", payload["recordBlockedCommand"])


if __name__ == "__main__":
    unittest.main()
