from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rift_live_test.coordinate_scan_profiles import main, profile_commands


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


if __name__ == "__main__":
    unittest.main()
