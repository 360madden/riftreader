from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.manual_displacement_capture import (
    candidate_compare_file_for,
    main,
    selected_paths_from_route,
)


class ManualDisplacementCaptureTests(unittest.TestCase):
    def _root(self) -> tempfile.TemporaryDirectory[str]:
        return tempfile.TemporaryDirectory()

    @staticmethod
    def _write_json(path: Path, payload: dict) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def test_jsonl_candidate_uses_json_sibling_for_offline_compare(self) -> None:
        with self._root() as temp:
            root = Path(temp) / "RiftReader"
            candidate_jsonl = root / "scripts" / "captures" / "candidates.jsonl"
            candidate_json = candidate_jsonl.with_suffix(".json")
            candidate_jsonl.parent.mkdir(parents=True, exist_ok=True)
            candidate_jsonl.write_text("{}\n", encoding="utf-8")
            candidate_json.write_text("[]\n", encoding="utf-8")
            readback = self._write_json(root / "readback.json", {"SourceCandidateFile": str(candidate_jsonl)})
            baseline = self._write_json(root / "baseline.json", {"status": "captured"})

            paths = selected_paths_from_route(
                root,
                {
                    "artifacts": {
                        "memoryReadback": str(readback),
                        "apiReference": str(baseline),
                    },
                    "target": {"processId": 123, "targetWindowHandle": "0xABC", "processName": "rift_x64"},
                },
            )

            self.assertEqual(paths["candidateReadbackFile"], candidate_jsonl)
            self.assertEqual(paths["candidateCompareFile"], candidate_json)
            self.assertEqual(candidate_compare_file_for(candidate_json), candidate_json)

    def test_dry_run_writes_command_plan_without_executing_children(self) -> None:
        with self._root() as temp:
            root = Path(temp) / "RiftReader"
            candidate_jsonl = root / "scripts" / "captures" / "candidates.jsonl"
            candidate_json = candidate_jsonl.with_suffix(".json")
            candidate_jsonl.parent.mkdir(parents=True, exist_ok=True)
            candidate_jsonl.write_text("{}\n", encoding="utf-8")
            candidate_json.write_text("[]\n", encoding="utf-8")
            readback = self._write_json(root / "readback.json", {"SourceCandidateFile": str(candidate_jsonl)})
            baseline = self._write_json(root / "baseline.json", {"status": "captured"})
            route = self._write_json(
                root / "route.json",
                {
                    "target": {
                        "processId": 123,
                        "targetWindowHandle": "0xABC",
                        "processName": "rift_x64",
                        "processStartUtc": "2026-05-14T00:00:00Z",
                    },
                    "artifacts": {
                        "memoryReadback": str(readback),
                        "apiReference": str(baseline),
                        "centerFiles": [],
                    },
                },
            )
            output_root = root / "scripts" / "captures" / "manual-displacement-dry-run"
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--repo-root",
                        str(root),
                        "--route-summary",
                        str(route),
                        "--output-root",
                        str(output_root),
                        "--dry-run",
                        "--json",
                    ]
                )

            summary = json.loads((output_root / "summary.json").read_text(encoding="utf-8"))
            printed = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(printed["status"], "dry-run")
            self.assertEqual(summary["status"], "dry-run")
            self.assertEqual(summary["commands"], [])
            self.assertFalse(summary["safety"]["movementSent"])
            self.assertFalse(summary["safety"]["inputSent"])
            self.assertTrue(summary["safety"]["noCheatEngine"])
            self.assertIn(str(candidate_jsonl), summary["plan"]["capture"])
            self.assertIn(str(candidate_json), summary["plan"]["comparisonTemplate"])
            self.assertIn("--max-displaced-reference-age-seconds", summary["plan"]["comparisonTemplate"])
            self.assertIn("--process-start-utc", summary["plan"]["routeTemplate"])

    def test_self_test_passes(self) -> None:
        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["--self-test"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "passed")


if __name__ == "__main__":
    unittest.main()
