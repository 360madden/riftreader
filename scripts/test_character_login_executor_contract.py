from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.character_login_executor_contract import main


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def plan() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "kind": "riftreader-character-login-resilience-plan",
        "status": "planned",
        "currentTarget": {
            "processName": "rift_x64",
            "processId": 77728,
            "windowHandle": "0x8E13A6",
            "processStartUtc": "2026-05-20T15:54:23Z",
        },
        "screenState": {
            "classification": "character-selection-not-in-world",
            "worldEntryPermittedNow": True,
        },
        "selection": {
            "selectedCharacter": "ATANK",
            "targetCharacter": "ATANK",
            "selectedAlready": True,
        },
        "readiness": {
            "canPlanLogin": True,
            "canExecuteLiveActionsNow": False,
            "playButton": {"clickPoint": [517, 343], "bbox": [476, 329, 558, 357]},
        },
    }


def truth() -> dict[str, object]:
    return {
        "target": {
            "processName": "rift_x64",
            "processId": 77728,
            "targetWindowHandle": "0x8E13A6",
            "processStartUtc": "2026-05-20T15:54:23Z",
        }
    }


class CharacterLoginExecutorContractTests(unittest.TestCase):
    def run_contract(self, root: Path, extra: list[str] | None = None) -> tuple[int, dict[str, object]]:
        out = root / "out"
        args = [
            "--repo-root",
            str(root),
            "--plan-summary",
            str(root / "plan.json"),
            "--current-truth",
            str(root / "truth.json"),
            "--current-proof",
            str(root / "proof.json"),
            "--output-root",
            str(out),
            "--json",
        ]
        if extra:
            args.extend(extra)
        with redirect_stdout(StringIO()):
            code = main(args)
        summary = json.loads((out / "character-login-executor-contract-summary.json").read_text(encoding="utf-8"))
        return code, summary

    def test_blocks_without_approval_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_json(root / "plan.json", plan())
            write_json(root / "truth.json", truth())
            write_json(root / "proof.json", truth())

            code, summary = self.run_contract(root)

            self.assertEqual(code, 2)
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("explicit-world-entry-approval-token-missing-or-mismatched", summary["blockers"])
            self.assertFalse(summary["executorContract"]["mayClickPlay"])
            self.assertFalse(summary["safety"]["mouseClickSent"])

    def test_ready_for_executor_only_with_exact_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_json(root / "plan.json", plan())
            write_json(root / "truth.json", truth())
            write_json(root / "proof.json", truth())

            code, summary = self.run_contract(root, ["--approval-token", "ENTER-WORLD:ATANK:77728:0x8E13A6"])

            self.assertEqual(code, 0)
            self.assertEqual(summary["status"], "ready-for-executor")
            self.assertTrue(summary["approval"]["matches"])
            self.assertTrue(summary["executorContract"]["mayClickPlay"])
            self.assertFalse(summary["safety"]["worldEntryClicked"])

    def test_target_mismatch_blocks_even_with_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stale_plan = plan()
            stale_plan["currentTarget"]["processId"] = 60636  # type: ignore[index]
            write_json(root / "plan.json", stale_plan)
            write_json(root / "truth.json", truth())
            write_json(root / "proof.json", truth())

            code, summary = self.run_contract(root, ["--approval-token", "ENTER-WORLD:ATANK:60636:0X8E13A6"])

            self.assertEqual(code, 2)
            self.assertIn("login-plan-target-does-not-match-current-truth", summary["blockers"])
            self.assertFalse(summary["executorContract"]["mayClickPlay"])


if __name__ == "__main__":
    unittest.main()
