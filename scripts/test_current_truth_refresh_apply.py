#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import current_truth_refresh_apply as apply_helper  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def base_safety(**overrides: object) -> dict:
    safety = {
        "movementSent": False,
        "inputSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "x64dbgAttach": False,
        "providerWrites": False,
        "gitMutation": False,
        "applyFlagSent": False,
        "savedVariablesUsedAsLiveTruth": False,
        "dryRunOnly": True,
        "trackedTruthWritten": False,
        "targetMemoryBytesRead": False,
        "targetMemoryBytesWritten": False,
        "proofPromotion": False,
        "actorChainPromotion": False,
        "facingPromotion": False,
    }
    safety.update(overrides)
    return safety


def seed_apply_fixture(root: Path, *, unsafe_plan: bool = False) -> tuple[Path, Path, Path]:
    target = {
        "processName": "rift_x64",
        "processId": 41808,
        "targetWindowHandle": "0x2B0A26",
        "processStartUtc": "2026-06-01T01:50:50.903773Z",
        "moduleBase": "0x7FF6EE5D0000",
    }
    current_truth_path = root / "docs" / "recovery" / "current-truth.json"
    proposed_path = root / ".riftreader-local" / "current-truth-refresh-plan" / "latest" / "proposed-current-truth.json"
    plan_path = root / ".riftreader-local" / "current-truth-refresh-plan" / "latest" / "summary.json"
    current_truth = {
        "schemaVersion": 1,
        "kind": "riftreader-current-truth",
        "updatedAtUtc": "2026-06-01T04:00:00Z",
        "target": target,
        "staticChainStatus": {},
        "movementGate": {"allowed": True},
    }
    proposed = {
        **current_truth,
        "updatedAtUtc": "2026-06-01T05:00:00Z",
        "liveReferenceSurface": {
            "view": "Current target has a proposed tracked-truth refresh from static-chain readback; no proof promotion or live input is performed.",
            "warnings": [
                "Dry-run current-truth refresh plan generated 2026-06-01T05:00:00Z; applying tracked truth remains a separate gate."
            ],
            "notes": [
                "Dry-run current-truth refresh plan generated 2026-06-01T05:00:00Z; applying tracked truth remains a separate gate."
            ],
        },
        "currentWarnings": [
            "Dry-run current-truth refresh plan generated 2026-06-01T05:00:00Z; applying tracked truth remains a separate gate."
        ],
        "staticChainStatus": {
            "latestApiNowValidation": {
                "status": "passed-current-pid-41808-api-now-vs-chain-now",
            }
        },
        "movementGate": {"allowed": True, "status": "allowed-with-current-pid-exact-target-fresh-static-readback-and-api-now-validation"},
    }
    plan = {
        "schemaVersion": 1,
        "kind": "riftreader-current-truth-refresh-plan",
        "generatedAtUtc": "2026-06-01T05:00:00Z",
        "status": "passed",
        "verdict": "dry-run-current-truth-refresh-plan-ready",
        "target": target,
        "updates": [{"path": "/updatedAtUtc"}],
        "blockers": [],
        "warnings": [],
        "errors": [],
        "safety": base_safety(inputSent=unsafe_plan),
        "artifacts": {
            "proposedCurrentTruthJson": str(proposed_path),
        },
    }
    write_json(current_truth_path, current_truth)
    write_json(proposed_path, proposed)
    write_json(plan_path, plan)
    return current_truth_path, proposed_path, plan_path


class CurrentTruthRefreshApplyTests(unittest.TestCase):
    def test_dry_run_validates_without_writing_tracked_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            current_truth_path, _, plan_path = seed_apply_fixture(root)
            before = current_truth_path.read_text(encoding="utf-8")
            args = type(
                "Args",
                (),
                {
                    "summary_json": plan_path,
                    "proposed_current_truth_json": None,
                    "current_truth_json": current_truth_path,
                    "output_dir": root / ".riftreader-local" / "apply",
                    "apply": False,
                },
            )()

            summary, exit_code = apply_helper.build_summary(args, root)
            after = current_truth_path.read_text(encoding="utf-8")

        self.assertEqual(0, exit_code)
        self.assertEqual("passed", summary["status"])
        self.assertEqual("current-truth-refresh-apply-dry-run-ready", summary["verdict"])
        self.assertEqual(before, after)
        self.assertFalse(summary["safety"]["applyFlagSent"])
        self.assertFalse(summary["safety"]["trackedTruthWritten"])

    def test_apply_writes_proposed_truth_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            current_truth_path, _, plan_path = seed_apply_fixture(root)
            args = type(
                "Args",
                (),
                {
                    "summary_json": plan_path,
                    "proposed_current_truth_json": None,
                    "current_truth_json": current_truth_path,
                    "output_dir": root / ".riftreader-local" / "apply",
                    "apply": True,
                },
            )()

            summary, exit_code = apply_helper.build_summary(args, root)
            applied = json.loads(current_truth_path.read_text(encoding="utf-8"))
            backup_exists = (root / ".riftreader-local" / "apply" / "current-truth-before-apply.json").is_file()

        self.assertEqual(0, exit_code)
        self.assertEqual("passed", summary["status"])
        self.assertEqual("current-truth-refresh-applied", summary["verdict"])
        self.assertEqual("2026-06-01T05:00:00Z", applied["updatedAtUtc"])
        self.assertIn("applied tracked-truth refresh", applied["liveReferenceSurface"]["view"])
        self.assertTrue(any("Tracked current-truth refresh applied" in item for item in applied["liveReferenceSurface"]["warnings"]))
        self.assertTrue(any("Tracked current-truth refresh applied" in item for item in applied["liveReferenceSurface"]["notes"]))
        self.assertTrue(any("Tracked current-truth refresh applied" in item for item in applied["currentWarnings"]))
        self.assertIn("appliedPayloadSha256", summary["hashes"])
        self.assertTrue(summary["safety"]["applyFlagSent"])
        self.assertTrue(summary["safety"]["trackedTruthWritten"])
        self.assertTrue(backup_exists)

    def test_apply_blocks_if_plan_safety_sent_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            current_truth_path, _, plan_path = seed_apply_fixture(root, unsafe_plan=True)
            args = type(
                "Args",
                (),
                {
                    "summary_json": plan_path,
                    "proposed_current_truth_json": None,
                    "current_truth_json": current_truth_path,
                    "output_dir": root / ".riftreader-local" / "apply",
                    "apply": True,
                },
            )()

            summary, exit_code = apply_helper.build_summary(args, root)

        self.assertEqual(2, exit_code)
        self.assertEqual("blocked", summary["status"])
        self.assertIn("plan-forbidden-safety-flag:inputSent", summary["blockers"])
        self.assertFalse(summary["safety"]["trackedTruthWritten"])

    def test_main_json_dry_run_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            (root / ".git").mkdir()
            (root / "agents.md").write_text("# test\n", encoding="utf-8")
            current_truth_path, _, plan_path = seed_apply_fixture(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = apply_helper.main(
                    [
                        "--repo-root",
                        str(root),
                        "--summary-json",
                        str(plan_path),
                        "--current-truth-json",
                        str(current_truth_path),
                        "--output-dir",
                        str(root / ".riftreader-local" / "apply"),
                        "--json",
                    ]
                )

            payload = json.loads(stdout.getvalue())

        self.assertEqual(0, exit_code)
        self.assertEqual("passed", payload["status"])
        self.assertFalse(payload["safety"]["trackedTruthWritten"])


if __name__ == "__main__":
    unittest.main()
