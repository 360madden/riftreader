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

from riftreader_workflow import current_truth_refresh_plan as planner  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def seed_current_truth_and_dashboard(root: Path) -> tuple[Path, Path]:
    truth_path = root / "docs" / "recovery" / "current-truth.json"
    dashboard_path = root / ".riftreader-local" / "navigation-pointer-discovery" / "latest" / "summary.json"
    current_truth = {
        "schemaVersion": 1,
        "kind": "riftreader-current-truth",
        "updatedAtUtc": "2026-05-31T14:23:13Z",
        "status": "current_pid_25668_static_player_coordinate_resolver_fresh_readback_api_now_passed",
        "target": {
            "processName": "rift_x64",
            "processId": 25668,
            "targetWindowHandle": "0x320CB0",
            "processStartUtc": "2026-05-30T02:46:41Z",
            "moduleBase": "0x7FF6EE5D0000",
            "lastVerifiedUtc": "2026-05-31T14:23:12Z",
            "verificationSource": "old readback",
        },
        "liveReferenceSurface": {
            "status": "old-status",
            "source": "old source",
            "view": "old view",
            "currentCoordinateFromStaticChainCandidate": {
                "x": 1.0,
                "y": 2.0,
                "z": 3.0,
                "recordedAtUtc": "2026-05-31T14:23:12Z",
            },
            "apiNowStatus": "passed-current-pid-25668-api-now-vs-chain-now",
            "notes": ["existing note"],
        },
        "staticChainStatus": {
            "status": "old-static-status",
            "promotionAllowed": True,
            "primaryCandidate": {
                "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                "rootModule": "rift_x64.exe",
                "rootRva": "0x32EBC80",
                "ownerAddress": "0xOLD",
                "coordinateAddress": "0xOLD320",
                "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
                "latestPromotedReadbackArtifact": "C:\\old\\coordinate-summary.json",
                "latestCurrentReadbackArtifact": "C:\\old\\coordinate-summary.json",
                "latestCurrentReadbackAtUtc": "2026-05-31T14:23:12Z",
            },
        },
        "canonicalArtifacts": {
            "latestCurrentPidStaticOwnerReadback": "C:\\old\\coordinate-summary.json",
            "latestCurrentPidNavStateReadback": "C:\\old\\nav-state-summary.json",
        },
    }
    dashboard = {
        "schemaVersion": 1,
        "kind": "riftreader-navigation-pointer-discovery-status",
        "generatedAtUtc": "2026-05-31T15:19:44Z",
        "status": "passed",
        "target": {
            "processName": "rift_x64",
            "processId": 25668,
            "targetWindowHandle": "0x320CB0",
            "processStartUtc": "2026-05-30T02:46:41Z",
            "moduleBase": "0x7FF6EE5D0000",
        },
        "sources": {
            "currentTruth": {"freshness": {"status": "stale"}, "status": "loaded"},
            "coordinateReadback": {
                "status": "passed",
                "generatedAtUtc": "2026-05-31T15:19:42Z",
                "path": "scripts\\captures\\static-owner-coordinate-chain-readback-20260531-151942\\summary.json",
                "freshness": {"status": "fresh"},
            },
            "navState": {
                "status": "passed",
                "generatedAtUtc": "2026-05-31T15:19:43Z",
                "path": "scripts\\captures\\static-owner-nav-state-20260531-151943\\summary.json",
                "freshness": {"status": "fresh"},
            },
        },
        "freshness": {"status": "stale", "staleSources": ["currentTruth"]},
        "candidates": {
            "promotedCoordinate": {
                "status": "promoted-static-player-coordinate-resolver-current-pid-readback-and-api-now-passed",
                "promotionAllowed": True,
                "candidateOnly": False,
                "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                "ownerAddress": "0x1B53D7806A0",
                "coordinateAddress": "0x1B53D7809C0",
                "coordinate": {"x": 7264.431640625, "y": 821.6972045898438, "z": 3003.875732421875},
                "latestReadbackStatus": "passed",
                "latestReadbackAtUtc": "2026-05-31T15:19:42Z",
                "latestReadbackJson": "scripts\\captures\\static-owner-coordinate-chain-readback-20260531-151942\\summary.json",
            },
            "candidateFacingTarget": {
                "status": "candidate-only",
                "candidateOnly": True,
                "promotionAllowed": False,
            },
            "candidateTurnRate": {
                "status": "candidate-only",
                "candidateOnly": True,
                "promotionAllowed": False,
            },
        },
        "sourceSafety": {"familySnapshotMovementSent": True, "familySnapshotInputSent": True},
        "safety": {
            "readOnlyArtifactIndex": True,
            "movementSent": False,
            "inputSent": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "facingPromotion": False,
            "gitMutation": False,
            "providerWrites": False,
            "x64dbgAttach": False,
        },
    }
    write_json(truth_path, current_truth)
    write_json(dashboard_path, dashboard)
    return truth_path, dashboard_path


class CurrentTruthRefreshPlanTests(unittest.TestCase):
    def test_plan_builds_proposed_truth_without_mutating_tracked_truth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            truth_path, _dashboard_path = seed_current_truth_and_dashboard(root)
            original_truth = truth_path.read_text(encoding="utf-8")

            summary = planner.build_current_truth_refresh_plan(
                root,
                generated_at_utc="2026-05-31T15:20:00Z",
            )

            self.assertEqual(original_truth, truth_path.read_text(encoding="utf-8"))

        self.assertEqual("passed", summary["status"])
        self.assertGreater(summary["updateCount"], 0)
        proposed = summary["proposedCurrentTruth"]
        self.assertEqual("2026-05-31T15:20:00Z", proposed["updatedAtUtc"])
        self.assertEqual("2026-05-31T15:19:42Z", proposed["target"]["lastVerifiedUtc"])
        self.assertEqual("0x1B53D7806A0", proposed["staticChainStatus"]["primaryCandidate"]["ownerAddress"])
        self.assertTrue(
            proposed["staticChainStatus"]["primaryCandidate"]["latestCurrentReadbackArtifact"].endswith(
                "scripts\\captures\\static-owner-coordinate-chain-readback-20260531-151942\\summary.json"
            )
        )
        self.assertTrue(
            proposed["canonicalArtifacts"]["latestCurrentPidNavStateReadback"].endswith(
                "scripts\\captures\\static-owner-nav-state-20260531-151943\\summary.json"
            )
        )
        self.assertEqual(
            "2026-05-31T15:19:42Z",
            proposed["liveReferenceSurface"]["currentCoordinateFromStaticChainCandidate"]["recordedAtUtc"],
        )
        self.assertFalse(summary["safety"]["trackedTruthWritten"])
        self.assertFalse(summary["safety"]["movementSent"])
        self.assertFalse(summary["safety"]["proofPromotion"])
        self.assertIn("this planner performs no proof/facing/actor promotion", proposed["target"]["verificationSource"])

    def test_write_outputs_creates_ignored_plan_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            seed_current_truth_and_dashboard(root)
            summary = planner.build_current_truth_refresh_plan(
                root,
                generated_at_utc="2026-05-31T15:20:00Z",
            )

            artifacts = planner.write_outputs(root, summary)

            self.assertTrue((root / artifacts["summaryJson"]).is_file())
            self.assertTrue((root / artifacts["summaryMarkdown"]).is_file())
            self.assertTrue((root / artifacts["proposedCurrentTruthJson"]).is_file())
            self.assertTrue((root / artifacts["proposedCurrentTruthDiff"]).is_file())
            self.assertIn("Dry-run", (root / artifacts["summaryMarkdown"]).read_text(encoding="utf-8"))

    def test_target_mismatch_blocks_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _truth_path, dashboard_path = seed_current_truth_and_dashboard(root)
            dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
            dashboard["target"]["processId"] = 99999
            write_json(dashboard_path, dashboard)

            summary = planner.build_current_truth_refresh_plan(root)

        self.assertEqual("blocked", summary["status"])
        self.assertIn("target-identity-mismatch:processId:truth=25668;dashboard=99999", summary["blockers"])
        self.assertIsNone(summary["proposedCurrentTruth"])
        self.assertFalse(summary["safety"]["trackedTruthWritten"])

    def test_stale_readback_source_blocks_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _truth_path, dashboard_path = seed_current_truth_and_dashboard(root)
            dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
            dashboard["sources"]["coordinateReadback"]["freshness"]["status"] = "stale"
            dashboard["freshness"]["staleSources"].append("coordinateReadback")
            write_json(dashboard_path, dashboard)

            summary = planner.build_current_truth_refresh_plan(root)

        self.assertEqual("blocked", summary["status"])
        self.assertIn("coordinateReadback-not-fresh:stale", summary["blockers"])
        self.assertIn("dashboard-has-stale-readback-source", summary["blockers"])

    def test_dashboard_safety_violation_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _truth_path, dashboard_path = seed_current_truth_and_dashboard(root)
            dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
            dashboard["safety"]["proofPromotion"] = True
            write_json(dashboard_path, dashboard)

            summary = planner.build_current_truth_refresh_plan(root)

        self.assertEqual("blocked", summary["status"])
        self.assertIn("dashboard-safety-flag-true:proofPromotion", summary["blockers"])
        self.assertFalse(summary["safety"]["proofPromotion"])

    def test_malformed_dashboard_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _truth_path, dashboard_path = seed_current_truth_and_dashboard(root)
            dashboard_path.write_text("{bad", encoding="utf-8")

            summary = planner.build_current_truth_refresh_plan(root)

        self.assertEqual("failed", summary["status"])
        self.assertTrue(any(item.startswith("navigation-dashboard-load-failed:") for item in summary["errors"]))
        self.assertFalse(summary["safety"]["trackedTruthWritten"])

    def test_cli_json_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            seed_current_truth_and_dashboard(root)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = planner.main(["--repo-root", str(root), "--write", "--json"])

            payload = json.loads(stdout.getvalue())

        self.assertEqual(0, exit_code)
        self.assertEqual("passed", payload["status"])
        self.assertIn("summaryJson", payload["artifacts"])

    def test_cli_self_test_json_passes_without_repo_writes(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = planner.main(["--self-test", "--json"])

        payload = json.loads(stdout.getvalue())

        self.assertEqual(0, exit_code)
        self.assertEqual("passed", payload["status"])
        self.assertEqual("riftreader-current-truth-refresh-plan-self-test", payload["kind"])
        check_names = {item["name"] for item in payload["checks"]}
        self.assertIn("tracked-truth-unchanged", check_names)
        self.assertIn("facing-remains-candidate-only", check_names)
        self.assertFalse(payload["safety"]["trackedTruthWritten"])
        self.assertFalse(payload["safety"]["movementSent"])
        self.assertFalse(payload["safety"]["inputSent"])
        self.assertFalse(payload["safety"]["proofPromotion"])


if __name__ == "__main__":
    unittest.main()
