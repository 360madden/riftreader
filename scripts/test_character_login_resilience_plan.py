from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.character_login_resilience_plan import identities_match, main
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
            "processStartUtc": "2026-05-20T11:02:20Z",
            "moduleBase": "0x7FF7B77A0000",
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
    }


class CharacterLoginResiliencePlanTests(unittest.TestCase):
    def run_plan(self, root: Path, args: list[str]) -> tuple[int, dict[str, object]]:
        out = root / "out"
        with redirect_stdout(StringIO()):
            code = main([*args, "--repo-root", str(root), "--output-root", str(out), "--json"])
        summary = json.loads((out / "character-login-resilience-plan-summary.json").read_text(encoding="utf-8"))
        return code, summary

    def test_matching_character_select_environment_plans_resilient_login(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env_path = root / "env.json"
            truth_path = root / "truth.json"
            proof_path = root / "proof.json"
            write_json(env_path, sample_environment())
            write_json(truth_path, current_truth())
            write_json(proof_path, current_proof())

            code, summary = self.run_plan(
                root,
                [
                    "--env-summary",
                    str(env_path),
                    "--current-truth",
                    str(truth_path),
                    "--current-proof",
                    str(proof_path),
                    "--target-character",
                    "ATANK",
                ],
            )

            self.assertEqual(code, 0)
            self.assertEqual(summary["status"], "planned")
            self.assertTrue(summary["readiness"]["canPlanLogin"])
            self.assertFalse(summary["readiness"]["canExecuteLiveActionsNow"])
            self.assertFalse(summary["safety"]["mouseClickSent"])
            self.assertEqual(summary["readiness"]["playButton"]["clickPoint"], [517, 343])
            states = [item["state"] for item in summary["stateMachine"]]
            self.assertIn("crash-recovery-loop", states)
            state_log = summary["stateLog"]
            self.assertEqual(state_log[0]["state"], "detect-client")
            self.assertEqual(state_log[0]["status"], "passed")
            self.assertEqual(
                next(item for item in state_log if item["state"] == "future-click-play")["status"],
                "approval-required",
            )
            state_log_path = Path(summary["artifacts"]["stateLogJsonl"])
            self.assertTrue(state_log_path.is_file())
            self.assertIn('"state": "detect-client"', state_log_path.read_text(encoding="utf-8"))

    def test_stale_environment_target_blocks_relogin_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env_path = root / "env.json"
            truth_path = root / "truth.json"
            proof_path = root / "proof.json"
            write_json(env_path, sample_environment())
            truth = current_truth()
            truth["target"]["processId"] = 77728  # type: ignore[index]
            truth["target"]["targetWindowHandle"] = "0x8E13A6"  # type: ignore[index]
            write_json(truth_path, truth)
            write_json(proof_path, current_proof())

            code, summary = self.run_plan(
                root,
                [
                    "--env-summary",
                    str(env_path),
                    "--current-truth",
                    str(truth_path),
                    "--current-proof",
                    str(proof_path),
                    "--target-character",
                    "ATANK",
                ],
            )

            self.assertEqual(code, 2)
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("environment-target-does-not-match-current-truth", summary["blockers"])
            self.assertFalse(summary["safety"]["worldEntryClicked"])

    def test_identity_match_rejects_process_epoch_drift_when_available(self) -> None:
        base = {
            "processName": "rift_x64",
            "processId": 60636,
            "windowHandle": "0xC51368",
            "processStartUtc": "2026-05-20T11:02:20.5639279Z",
            "moduleBase": "0x7FF7B77A0000",
        }
        same_epoch_with_truncated_timestamp = {
            **base,
            "processStartUtc": "2026-05-20T11:02:20Z",
            "moduleBase": "0x7ff7b77a0000",
        }
        drifted_epoch = {
            **base,
            "processStartUtc": "2026-05-20T12:02:20Z",
        }

        self.assertTrue(identities_match(base, same_epoch_with_truncated_timestamp))
        self.assertFalse(identities_match(base, drifted_epoch))

    def test_missing_environment_blocks_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            code, summary = self.run_plan(root, ["--target-character", "ATANK"])

            self.assertEqual(code, 2)
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("missing-character-select-environment-summary", summary["blockers"])
            self.assertFalse(summary["safety"]["mouseClickSent"])


if __name__ == "__main__":
    unittest.main()
