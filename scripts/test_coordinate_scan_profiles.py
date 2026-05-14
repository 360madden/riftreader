from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from rift_live_test.coordinate_scan_profiles import main, profile_commands, rank_profile_runs


class CoordinateScanProfilesTests(unittest.TestCase):
    def test_profile_commands_expand_historical_centers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ref = root / "ref.json"
            ref.write_text("{}", encoding="utf-8")
            commands = profile_commands(
                repo_root=root,
                pid=123,
                hwnd="0xABC",
                process_name="rift_x64",
                reference_file=ref,
                profiles=["historical-neighborhood"],
                centers=[(0x2000, "center")],
                historical_radius_bytes=0x100,
            )

            self.assertEqual(len(commands), 1)
            args = commands[0]["args"]
            self.assertIn("--min-address", args)
            self.assertEqual(args[args.index("--min-address") + 1], "0x1F00")
            self.assertEqual(args[args.index("--max-address") + 1], "0x2100")
            self.assertEqual(commands[0]["profile"], "historical-neighborhood")

    def test_dry_run_writes_planned_commands_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ref = root / "ref.json"
            out = root / "out"
            ref.write_text(json.dumps({"coordinate": {"x": 1, "y": 2, "z": 3}}), encoding="utf-8")

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--pid",
                    "123",
                    "--hwnd",
                    "0xABC",
                    "--reference-file",
                    str(ref),
                    "--profile",
                    "quick",
                    "--output-root",
                    str(out),
                    "--dry-run",
                    "--json",
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "blocked")
            self.assertEqual(summary["profileRuns"], [])
            self.assertTrue(summary["plannedCommands"])
            self.assertFalse(summary["safety"]["movementSent"])
            self.assertTrue((out / "summary.html").is_file())

    def test_require_displaced_pose_blocks_without_displaced_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ref = root / "ref.json"
            out = root / "out"
            ref.write_text(json.dumps({"coordinate": {"x": 1, "y": 2, "z": 3}}), encoding="utf-8")

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--pid",
                    "123",
                    "--hwnd",
                    "0xABC",
                    "--reference-file",
                    str(ref),
                    "--require-displaced-pose",
                    "--output-root",
                    str(out),
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("manual-displaced-reference-required", summary["blockers"])

    def test_latest_reference_alias_and_center_file_expand_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            captures = root / "scripts" / "captures" / "ref"
            captures.mkdir(parents=True)
            ref = captures / "rift-api-reference-currentpid-123-demo.json"
            ref.write_text(
                json.dumps({"processId": 123, "targetWindowHandle": "0xABC", "coordinate": {"x": 1, "y": 2, "z": 3}}),
                encoding="utf-8",
            )
            centers = root / "centers.json"
            centers.write_text(json.dumps({"centers": [{"label": "manual", "address": "0x5000"}]}), encoding="utf-8")
            out = root / "out"

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--pid",
                    "123",
                    "--hwnd",
                    "0xABC",
                    "--reference-file",
                    "latest",
                    "--profile",
                    "historical-neighborhood",
                    "--historical-center-file",
                    str(centers),
                    "--output-root",
                    str(out),
                    "--dry-run",
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["referenceFileResolvedFromAlias"], "latest")
            self.assertTrue(any(item.get("centerAddress") == "0x5000" for item in summary["plannedCommands"]))

    def test_update_current_truth_writes_latest_scan_profile_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            truth = root / "docs" / "recovery" / "current-truth.json"
            truth.parent.mkdir(parents=True)
            truth.write_text(json.dumps({"visualEvidenceRouting": {}}), encoding="utf-8")
            truth_md = root / "docs" / "recovery" / "current-truth.md"
            truth_md.write_text(
                "\n".join(
                    [
                        "# Current truth",
                        "",
                        "## Visual/capture proof-route policy — test",
                        "",
                        "| Field | Value |",
                        "|---|---|",
                        "| Latest route status | `reacquisition-no-current-hits` |",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            ref = root / "ref.json"
            ref.write_text(json.dumps({"coordinate": {"x": 1, "y": 2, "z": 3}}), encoding="utf-8")
            out = root / "out"

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--pid",
                    "123",
                    "--hwnd",
                    "0xABC",
                    "--reference-file",
                    str(ref),
                    "--require-displaced-pose",
                    "--output-root",
                    str(out),
                    "--update-current-truth",
                ]
            )

            self.assertEqual(code, 2)
            updated = json.loads(truth.read_text(encoding="utf-8"))
            routing = updated["visualEvidenceRouting"]
            self.assertEqual(routing["latestScanProfileRun"], "out/summary.json")
            self.assertEqual(routing["latestScanProfileHtml"], "out/summary.html")
            self.assertEqual(routing["latestManualDisplacementBlocker"], "out/summary.json")
            updated_markdown = truth_md.read_text(encoding="utf-8")
            self.assertIn("| Latest scan-profile run | `out/summary.json` |", updated_markdown)
            self.assertIn("| Latest manual displacement blocker | `out/summary.json` |", updated_markdown)

    def test_latest_displaced_alias_blocks_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ref = root / "ref.json"
            out = root / "out"
            ref.write_text(json.dumps({"processId": 123, "targetWindowHandle": "0xABC", "coordinate": {"x": 1, "y": 2, "z": 3}}), encoding="utf-8")

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--pid",
                    "123",
                    "--hwnd",
                    "0xABC",
                    "--reference-file",
                    str(ref),
                    "--displaced-reference-file",
                    "latest-displaced",
                    "--require-displaced-pose",
                    "--output-root",
                    str(out),
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("displaced-reference-latest-not-found", summary["blockers"])
            self.assertEqual(summary["displacedReferenceFileResolvedFromAlias"], "latest-displaced")

    def test_rank_profile_runs_orders_hits_then_delta(self) -> None:
        rankings = rank_profile_runs(
            [
                {
                    "profile": "quick",
                    "label": "quick",
                    "exitCode": 2,
                    "stdoutJson": {
                        "status": "blocked",
                        "scan": {"hitCount": 0, "bytesScanned": 100, "bestHit": None},
                        "artifacts": {"summaryJson": "a.json"},
                    },
                },
                {
                    "profile": "wide",
                    "label": "wide",
                    "exitCode": 0,
                    "stdoutJson": {
                        "status": "passed",
                        "scan": {"hitCount": 2, "bytesScanned": 200, "bestHit": {"maxAbsDelta": 0.2}},
                        "artifacts": {"summaryJson": "b.json"},
                    },
                },
                {
                    "profile": "historical-neighborhood",
                    "label": "center",
                    "exitCode": 0,
                    "stdoutJson": {
                        "status": "passed",
                        "scan": {"hitCount": 2, "bytesScanned": 300, "bestHit": {"maxAbsDelta": 0.1}},
                        "artifacts": {"summaryJson": "c.json"},
                    },
                },
            ],
            Path.cwd(),
        )

        self.assertEqual(rankings[0]["profile"], "historical-neighborhood")
        self.assertEqual(rankings[0]["rank"], 1)
        self.assertEqual(rankings[2]["profile"], "quick")

    def test_no_default_and_max_historical_centers_limit_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ref = root / "ref.json"
            centers = root / "centers.json"
            out = root / "out"
            ref.write_text(json.dumps({"coordinate": {"x": 1, "y": 2, "z": 3}}), encoding="utf-8")
            centers.write_text(
                json.dumps({"centers": [{"label": "one", "address": "0x1000"}, {"label": "two", "address": "0x2000"}]}),
                encoding="utf-8",
            )

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--pid",
                    "123",
                    "--hwnd",
                    "0xABC",
                    "--reference-file",
                    str(ref),
                    "--profile",
                    "historical-neighborhood-stride1",
                    "--historical-center-file",
                    str(centers),
                    "--no-default-historical-centers",
                    "--max-historical-centers",
                    "1",
                    "--output-root",
                    str(out),
                    "--dry-run",
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(len(summary["plannedCommands"]), 1)
            self.assertEqual(summary["plannedCommands"][0]["profile"], "historical-neighborhood-stride1")
            self.assertEqual(summary["plannedCommands"][0]["centerAddress"], "0x1000")
            args = summary["plannedCommands"][0]["args"]
            self.assertEqual(args[args.index("--scan-stride") + 1], "1")

    def test_displaced_reference_age_budget_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ref = root / "ref.json"
            displaced = root / "displaced.json"
            out = root / "out"
            ref.write_text(json.dumps({"coordinate": {"x": 1, "y": 2, "z": 3}}), encoding="utf-8")
            displaced.write_text(json.dumps({"poseLabel": "manual-displaced", "coordinate": {"x": 2, "y": 2, "z": 3}}), encoding="utf-8")
            os.utime(displaced, (ref.stat().st_mtime - 1000, ref.stat().st_mtime - 1000))

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--pid",
                    "123",
                    "--hwnd",
                    "0xABC",
                    "--reference-file",
                    str(ref),
                    "--displaced-reference-file",
                    str(displaced),
                    "--max-displaced-reference-age-seconds",
                    "30",
                    "--output-root",
                    str(out),
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertTrue(any(str(item).startswith("displaced-reference-age-exceeded:") for item in summary["blockers"]))
            self.assertIn("displaced-reference-older-than-baseline-reference", summary["warnings"])


if __name__ == "__main__":
    unittest.main()
