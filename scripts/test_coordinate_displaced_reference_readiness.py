from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from rift_live_test.coordinate_displaced_reference_readiness import main


class CoordinateDisplacedReferenceReadinessTests(unittest.TestCase):
    def _write_reference(
        self,
        path: Path,
        *,
        x: float,
        y: float,
        z: float,
        pid: int = 123,
        hwnd: str = "0xABC",
        pose_label: str | None = None,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "processId": pid,
            "targetWindowHandle": hwnd,
            "coordinate": {"x": x, "y": y, "z": z},
        }
        if pose_label:
            document["poseLabel"] = pose_label
        path.write_text(json.dumps(document), encoding="utf-8")

    def test_blocks_when_latest_displaced_reference_is_too_old(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            captures = root / "scripts" / "captures" / "age-test"
            baseline = captures / "rift-api-reference-currentpid-123-baseline.json"
            displaced = captures / "rift-api-reference-currentpid-123-operator-displaced.json"
            out = root / "out"
            self._write_reference(baseline, x=1, y=2, z=3)
            self._write_reference(displaced, x=3, y=2, z=3, pose_label="operator-displaced")
            os.utime(displaced, (baseline.stat().st_mtime - 1000, baseline.stat().st_mtime - 1000))

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--pid",
                    "123",
                    "--hwnd",
                    "0xABC",
                    "--api-reference",
                    str(baseline),
                    "--displaced-api-reference",
                    "latest-displaced",
                    "--max-age-delta-seconds",
                    "30",
                    "--output-root",
                    str(out),
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "blocked")
            self.assertTrue(any(str(item).startswith("displaced-reference-age-exceeded:") for item in summary["blockers"]))
            self.assertFalse(summary["safety"]["movementSent"])
            self.assertFalse(summary["safety"]["inputSent"])
            self.assertTrue(summary["safety"]["noCheatEngine"])

    def test_passes_when_references_are_fresh_and_displaced_enough(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            captures = root / "scripts" / "captures" / "fresh-two-pose"
            baseline = captures / "rift-api-reference-currentpid-123-baseline.json"
            displaced = captures / "rift-api-reference-currentpid-123-operator-displaced.json"
            out = root / "out"
            self._write_reference(baseline, x=1, y=2, z=3)
            self._write_reference(displaced, x=3, y=2, z=3, pose_label="operator-displaced")

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--pid",
                    "123",
                    "--hwnd",
                    "0xABC",
                    "--api-reference",
                    str(baseline),
                    "--displaced-api-reference",
                    "latest-displaced",
                    "--min-planar-displacement",
                    "1",
                    "--output-root",
                    str(out),
                ]
            )

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "passed")
            self.assertEqual(summary["delta"]["planarDistance"], 2.0)
            self.assertEqual(summary["displacedReferenceResolvedFromAlias"], "latest-displaced")

    def test_latest_baseline_alias_skips_marked_displaced_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            captures = root / "scripts" / "captures" / "latest-alias"
            baseline = captures / "rift-api-reference-currentpid-123-baseline.json"
            displaced = captures / "rift-api-reference-currentpid-123-manual-displaced.json"
            out = root / "out"
            self._write_reference(baseline, x=1, y=2, z=3)
            self._write_reference(displaced, x=3, y=2, z=3, pose_label="manual-displaced")
            os.utime(displaced, (baseline.stat().st_mtime + 10, baseline.stat().st_mtime + 10))

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--pid",
                    "123",
                    "--hwnd",
                    "0xABC",
                    "--api-reference",
                    "latest",
                    "--displaced-api-reference",
                    "latest-displaced",
                    "--max-age-delta-seconds",
                    "30",
                    "--output-root",
                    str(out),
                ]
            )

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["baselineReference"]["path"], "scripts/captures/latest-alias/rift-api-reference-currentpid-123-baseline.json")
            self.assertEqual(summary["displacedReference"]["path"], "scripts/captures/latest-alias/rift-api-reference-currentpid-123-manual-displaced.json")

    def test_update_current_truth_records_readiness_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            captures = root / "scripts" / "captures" / "current-truth-two-pose"
            baseline = captures / "rift-api-reference-currentpid-123-baseline.json"
            displaced = captures / "rift-api-reference-currentpid-123-operator-displaced.json"
            out = root / "out"
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
                        "| Latest route status | `blocked` |",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            self._write_reference(baseline, x=1, y=2, z=3)
            self._write_reference(displaced, x=3, y=2, z=3, pose_label="operator-displaced")

            code = main(
                [
                    "--repo-root",
                    str(root),
                    "--pid",
                    "123",
                    "--hwnd",
                    "0xABC",
                    "--api-reference",
                    str(baseline),
                    "--displaced-api-reference",
                    "latest-displaced",
                    "--output-root",
                    str(out),
                    "--update-current-truth",
                ]
            )

            self.assertEqual(code, 0)
            routing = json.loads(truth.read_text(encoding="utf-8"))["visualEvidenceRouting"]
            self.assertEqual(routing["latestDisplacedReferenceReadiness"], "out/summary.json")
            self.assertEqual(routing["latestDisplacedReferenceReadinessHtml"], "out/summary.html")
            self.assertEqual(routing["latestDisplacedReferenceReadinessStatus"], "passed")
            self.assertEqual(routing["latestDisplacedReferencePlanarDistance"], 2.0)
            markdown = truth_md.read_text(encoding="utf-8")
            self.assertIn("| Latest displaced-reference readiness | `out/summary.json` |", markdown)
            self.assertIn("| Latest displaced-reference readiness status | `passed` |", markdown)


if __name__ == "__main__":
    unittest.main()
