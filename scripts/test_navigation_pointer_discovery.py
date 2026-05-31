#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import io
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

from riftreader_workflow import navigation_pointer_discovery as discovery  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def seed_navigation_artifacts(root: Path) -> None:
    write_json(
        root / "docs" / "recovery" / "current-truth.json",
        {
            "updatedAtUtc": "2026-05-31T14:23:12Z",
            "target": {
                "processName": "rift_x64",
                "processId": 25668,
                "targetWindowHandle": "0x320CB0",
                "processStartUtc": "2026-05-30T02:46:41Z",
                "moduleBase": "0x7FF6EE5D0000",
                "status": "current",
            },
            "staticChainStatus": {
                "status": "promoted-static-player-coordinate-resolver-current-pid-readback-and-api-now-passed",
                "promotionAllowed": True,
                "primaryCandidate": {
                    "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
                    "rootModule": "rift_x64.exe",
                    "rootRva": "0x32EBC80",
                    "ownerAddress": "0x1000",
                    "coordinateAddress": "0x1320",
                    "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
                    "latestCurrentReadbackAtUtc": "2026-05-31T14:23:12Z",
                },
                "latestApiNowValidation": {
                    "currentApiNowStatus": "passed-current-pid-25668-api-now-vs-chain-now",
                    "currentPidValidation": {"status": "passed-current-pid-25668-api-now-vs-chain-now"},
                },
            },
        },
    )
    write_json(
        root / "scripts" / "captures" / "static-owner-coordinate-chain-readback-20260531-142312-924000" / "summary.json",
        {
            "mode": "static-owner-coordinate-chain-readback",
            "status": "passed",
            "verdict": "promoted-static-coordinate-resolver-readback-passed",
            "generatedAtUtc": "2026-05-31T14:23:12Z",
            "reads": {"ownerAddress": "0x1000", "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0}},
            "analysis": {"maxPlanarDelta": 0.0},
            "safety": {"targetMemoryBytesRead": True},
        },
    )
    write_json(
        root / "scripts" / "captures" / "static-owner-nav-state-20260531-142313-000000" / "summary.json",
        {
            "kind": "static-owner-nav-state-readback",
            "status": "passed",
            "verdict": "position-and-facing-nav-state-readback-passed",
            "generatedAtUtc": "2026-05-31T14:23:13Z",
            "latestState": {
                "ownerAddress": "0x1000",
                "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
                "facingTargetCoordinate": {"x": 10.0, "y": 2.0, "z": 6.0},
                "yawDegrees": 22.5,
                "pitchDegrees": -4.0,
                "planarLookaheadDistance": 9.9,
                "turnRate0x304": 1.25,
                "turnRateClassification": "left",
                "facingTargetOffset": "0x30C",
                "turnRateOffset": "0x304",
            },
            "safety": {"targetMemoryBytesRead": True},
        },
    )
    write_json(
        root / "scripts" / "captures" / "static-owner-facing-comparison-20260531-141949-380215" / "summary.json",
        {
            "kind": "static-owner-facing-comparison",
            "status": "passed",
            "verdict": "static-owner-facing-candidates-scored",
            "generatedAtUtc": "2026-05-31T14:19:49Z",
            "comparison": {
                "ownerAddresses": ["0x1000"],
                "maxCoordinatePlanarDrift": 0.0,
                "relativeTargetCandidates": [
                    {
                        "offset": "0x30C",
                        "address": "0x130C",
                        "yawDeltasFromBaseline": {"right": 49.4, "left": -62.1},
                        "maxAbsYawDeltaDegrees": 62.1,
                    }
                ],
                "scalarCandidates": [
                    {
                        "offset": "0x304",
                        "address": "0x1304",
                        "deltasFromBaseline": {"right": -0.8, "left": 1.0},
                        "maxAbsDelta": 1.0,
                    }
                ],
            },
        },
    )
    write_json(
        root / "scripts" / "captures" / "pointer-owner-neighborhood-inspector-20260531-142006-017134" / "summary.json",
        {
            "kind": "pointer-owner-neighborhood-inspector",
            "status": "passed",
            "generatedAtUtc": "2026-05-31T14:20:06Z",
            "analysis": {"exactTargetCounts": {"0x130C": 0}, "regionMatchCount": 2, "modulePointerCount": 0},
        },
    )
    family_dir = root / "scripts" / "captures" / "family-snapshot-sequence-currentpid-25668-20260531-142159-332736"
    candidate_path = family_dir / "delta-analysis" / "candidate-vec3.json"
    write_json(
        family_dir / "summary.json",
        {
            "mode": "current-pid-family-snapshot-sequence",
            "status": "passed",
            "generatedAtUtc": "2026-05-31T14:21:59Z",
            "artifacts": {"candidateVec3Json": str(candidate_path)},
            "safety": {"movementSent": True, "inputSent": True},
            "analysis": {
                "analysis": {
                    "candidateCount": 2,
                    "familyCount": 1,
                    "bestCandidate": {
                        "candidateId": "snapshot-delta-1320-xyz",
                        "addressHex": "0x1320",
                        "segmentOffsetHex": "0x320",
                        "axisOrder": "xyz",
                        "apiDelta": {"planar": 2.0},
                        "memoryDelta": {"planar": 2.01},
                        "trackingError": {"maxAbs": 0.006},
                        "baselineMaxAbsDelta": 0.003,
                        "displacedMaxAbsDelta": 0.004,
                    },
                }
            },
        },
    )
    write_json(candidate_path, {"candidateCount": 1, "candidates": []})


class NavigationPointerDiscoveryTests(unittest.TestCase):
    def test_build_summary_indexes_promoted_and_candidate_navigation_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)

            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 14, 24, tzinfo=timezone.utc),
            )

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["kind"], "riftreader-navigation-pointer-discovery-status")
        candidates = summary["candidates"]
        self.assertFalse(candidates["promotedCoordinate"]["candidateOnly"])
        self.assertEqual(candidates["promotedCoordinate"]["coordinateOffset"], "0x320")
        self.assertTrue(candidates["candidateFacingTarget"]["candidateOnly"])
        self.assertEqual(candidates["candidateFacingTarget"]["offset"], "0x30C")
        self.assertEqual(candidates["candidateFacingTarget"]["comparisonMaxAbsYawDeltaDegrees"], 62.1)
        self.assertTrue(candidates["candidateTurnRate"]["candidateOnly"])
        self.assertEqual(candidates["coordinateDeltaCandidate"]["status"], "confirms-promoted-coordinate-offset")
        self.assertEqual(candidates["coordinateDeltaCandidate"]["trackingErrorMaxAbs"], 0.006)
        self.assertFalse(summary["safety"]["inputSent"])
        self.assertFalse(summary["safety"]["gitMutation"])
        self.assertFalse(summary["safety"]["proofPromotion"])
        self.assertTrue(summary["sourceSafety"]["familySnapshotMovementSent"])
        self.assertEqual(summary["freshness"]["status"], "fresh")
        self.assertEqual(summary["sources"]["coordinateReadback"]["freshness"]["status"], "fresh")

    def test_freshness_classifies_stale_current_readbacks_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)

            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 16, 0, tzinfo=timezone.utc),
            )

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["freshness"]["status"], "stale")
        self.assertIn("coordinateReadback", summary["freshness"]["staleSources"])
        self.assertIn("navState", summary["freshness"]["staleSources"])
        self.assertNotIn("facingComparison", summary["freshness"]["staleSources"])

    def test_next_action_prioritizes_truth_refresh_when_only_current_truth_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)
            truth_path = root / "docs" / "recovery" / "current-truth.json"
            truth = json.loads(truth_path.read_text(encoding="utf-8"))
            truth["updatedAtUtc"] = "2026-05-31T13:00:00Z"
            truth_path.write_text(json.dumps(truth), encoding="utf-8")

            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 14, 24, tzinfo=timezone.utc),
            )

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["freshness"]["staleSources"], ["currentTruth"])
        self.assertIn("current-truth refresh slice", summary["next"]["recommendedAction"])
        self.assertIn("static-root proof", summary["next"]["recommendedActions"][1])

    def test_missing_artifacts_blocks_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)

            summary = discovery.build_navigation_pointer_discovery(root)

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("navigation-pointer-evidence-missing", summary["blockers"])
        self.assertFalse(summary["safety"]["targetMemoryBytesRead"])

    def test_malformed_current_truth_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            (root / "docs" / "recovery").mkdir(parents=True)
            (root / "docs" / "recovery" / "current-truth.json").write_text("{bad", encoding="utf-8")

            summary = discovery.build_navigation_pointer_discovery(root)

        self.assertEqual(summary["status"], "failed")
        self.assertIn("current-truth-unreadable", summary["blockers"])
        self.assertTrue(any(item.startswith("current-truth-malformed") for item in summary["errors"]))

    def test_write_outputs_creates_json_and_markdown_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            seed_navigation_artifacts(root)
            summary = discovery.build_navigation_pointer_discovery(
                root,
                now=datetime(2026, 5, 31, 14, 24, tzinfo=timezone.utc),
            )

            artifacts = discovery.write_outputs(root, summary, Path(".riftreader-local") / "navigation-pointer-discovery" / "latest")

            summary_json = root / artifacts["summaryJson"]
            summary_md = root / artifacts["summaryMarkdown"]
            loaded = json.loads(summary_json.read_text(encoding="utf-8"))
            markdown = summary_md.read_text(encoding="utf-8")

        self.assertEqual(loaded["status"], "passed")
        self.assertIn("Navigation Pointer Discovery Status", markdown)
        self.assertIn("Candidate summary", markdown)
        self.assertIn("Freshness", markdown)
        self.assertIn("Recommended action list", markdown)
        self.assertIn("Next action", markdown)

    def test_main_self_test_json_passes(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = discovery.main(["--self-test", "--json"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "passed")
        self.assertFalse(payload["safety"]["proofPromotion"])


if __name__ == "__main__":
    unittest.main()
