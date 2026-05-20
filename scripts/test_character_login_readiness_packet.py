from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.character_login_readiness_packet import main
from scripts.test_character_select_automation_plan import sample_environment


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def current_truth() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-current-truth",
        "updatedAtUtc": "2026-05-20T16:00:48Z",
        "target": {
            "processName": "rift_x64",
            "processId": 60636,
            "targetWindowHandle": "0xC51368",
            "processStartUtc": "2026-05-20T11:02:20.5639279Z",
            "windowTitle": "RIFT",
        },
        "movementGate": {"allowed": False, "status": "blocked-target-not-in-world"},
    }


def current_proof() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "mode": "current-proof-anchor-readback-pointer",
        "status": "blocked-target-not-in-world",
        "target": {
            "processName": "rift_x64",
            "processId": 60636,
            "targetWindowHandle": "0xC51368",
        },
        "latestValidation": {"movementAllowed": False},
    }


def resilience_plan() -> dict[str, object]:
    env = sample_environment()
    return {
        "schemaVersion": 1,
        "kind": "riftreader-character-login-resilience-plan",
        "status": "planned",
        "currentTarget": env["target"],
        "screenState": env["screenState"],
        "selection": {
            "selectedCharacter": "ATANK",
            "targetCharacter": "ATANK",
            "selectedAlready": True,
            "targetSlot": env["targets"]["selectedCharacter"],  # type: ignore[index]
            "visibleCharacters": ["SYRACUSE", "CEBU", "ATANK"],
        },
        "readiness": {
            "canPlanLogin": True,
            "canExecuteLiveActionsNow": False,
            "playButton": {"clickPoint": [517, 343], "bbox": [476, 329, 558, 357]},
        },
        "retryPolicy": {"maxReloginAttempts": 3, "backoffSeconds": [2, 5, 10]},
        "stateMachine": [{"state": "detect-client"}, {"state": "future-click-play"}],
        "stateLog": [{"state": "detect-client", "status": "passed"}],
        "safety": {"mouseClickSent": False, "movementAllowed": False},
    }


def select_plan() -> dict[str, object]:
    env = sample_environment()
    return {
        "schemaVersion": 1,
        "kind": "riftreader-character-select-automation-plan",
        "status": "planned",
        "target": env["target"],
        "screenState": env["screenState"],
        "selection": {"selectedCharacter": "ATANK", "targetCharacter": "ATANK", "selectedAlready": True},
        "safety": {"mouseClickSent": False, "worldEntryClicked": False},
    }


def executor_contract() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-character-login-executor-contract",
        "status": "blocked",
        "blockers": [
            "world-entry-not-permitted-by-source-environment",
            "explicit-world-entry-approval-token-missing-or-mismatched",
        ],
        "expectedApprovalToken": "ENTER-WORLD:ATANK:60636:0xC51368",
        "approval": {"required": True, "provided": False, "matches": False},
        "executorContract": {"mayClickPlay": False},
        "safety": {"mouseClickSent": False, "worldEntryClicked": False},
    }


class CharacterLoginReadinessPacketTests(unittest.TestCase):
    def write_fixture_files(self, root: Path) -> dict[str, Path]:
        paths = {
            "env": root / "env.json",
            "select": root / "select.json",
            "resilience": root / "resilience.json",
            "contract": root / "contract.json",
            "truth": root / "truth.json",
            "proof": root / "proof.json",
        }
        write_json(paths["env"], sample_environment())
        write_json(paths["select"], select_plan())
        write_json(paths["resilience"], resilience_plan())
        write_json(paths["contract"], executor_contract())
        write_json(paths["truth"], current_truth())
        write_json(paths["proof"], current_proof())
        return paths

    def run_packet(self, root: Path, paths: dict[str, Path], extra: list[str] | None = None) -> tuple[int, dict[str, object]]:
        out = root / "out"
        args = [
            "--repo-root",
            str(root),
            "--env-summary",
            str(paths["env"]),
            "--select-plan-summary",
            str(paths["select"]),
            "--resilience-plan-summary",
            str(paths["resilience"]),
            "--executor-contract-summary",
            str(paths["contract"]),
            "--current-truth",
            str(paths["truth"]),
            "--current-proof",
            str(paths["proof"]),
            "--output-root",
            str(out),
            "--target-character",
            "ATANK",
            "--json",
        ]
        if extra:
            args.extend(extra)
        with redirect_stdout(StringIO()):
            code = main(args)
        summary = json.loads((out / "character-login-readiness-packet-summary.json").read_text(encoding="utf-8"))
        return code, summary

    def test_packet_ready_consolidates_login_data_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_fixture_files(root)

            code, summary = self.run_packet(root, paths)

            self.assertEqual(code, 0)
            self.assertEqual(summary["status"], "packet-ready")
            self.assertEqual(summary["dataBlockers"], [])
            self.assertIn("world-entry-requires-explicit-current-run-approval", summary["executionBlockers"])
            self.assertTrue(summary["automationReadiness"]["canPlanCharacterLogin"])
            self.assertFalse(summary["automationReadiness"]["canExecuteLiveActionsNow"])
            self.assertFalse(summary["automationReadiness"]["mayClickPlayNow"])
            self.assertEqual(summary["automationReadiness"]["expectedApprovalToken"], "ENTER-WORLD:ATANK:60636:0xC51368")
            self.assertEqual(summary["playButton"]["clickPoint"], [517, 343])
            self.assertFalse(summary["safety"]["mouseClickSent"])
            self.assertFalse(summary["safety"]["movementSent"])

    def test_target_mismatch_blocks_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_fixture_files(root)
            truth = current_truth()
            truth["target"]["processId"] = 77728  # type: ignore[index]
            write_json(paths["truth"], truth)

            code, summary = self.run_packet(root, paths)

            self.assertEqual(code, 2)
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("environment-target-does-not-match-current-truth", summary["dataBlockers"])
            self.assertFalse(summary["safety"]["worldEntryClicked"])

    def test_missing_environment_blocks_without_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_fixture_files(root)
            paths["env"].unlink()

            code, summary = self.run_packet(root, paths)

            self.assertEqual(code, 2)
            self.assertIn("missing-environment-summary", summary["dataBlockers"])
            self.assertFalse(summary["safety"]["keyInputSent"])


if __name__ == "__main__":
    unittest.main()
