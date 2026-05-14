from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.rrapicoord_scan_diagnostics import build_summary, main


def write_scan(path: Path, *, preview: str, hit_count: int = 1) -> None:
    path.write_text(
        json.dumps(
            {
                "Mode": "read-only",
                "ProcessId": 2928,
                "ProcessName": "rift_x64",
                "SearchText": "RRAPICOORD1",
                "Encoding": "ascii",
                "ContextBytes": 512,
                "MaxHits": 64,
                "HitCount": hit_count,
                "Hits": [
                    {
                        "AddressHex": "0x1234",
                        "Encoding": "ascii",
                        "Classification": "test",
                        "Context": {
                            "AsciiPreview": preview,
                            "Utf16Preview": "",
                            "BytesHex": preview.encode("utf-8").hex(" "),
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


class RrapicoordScanDiagnosticsTests(unittest.TestCase):
    def test_usable_marker_passes_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scan = root / "scan.json"
            output = root / "out"
            write_scan(
                scan,
                preview=(
                    "RRAPICOORD1|status=pass|source=rift-api|view=Inspect.Unit.Detail(player)|"
                    "x=1.5|y=2|z=3|savedVariablesUse=none"
                ),
            )

            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--repo-root",
                        str(root),
                        "--scan-file",
                        str(scan),
                        "--output-root",
                        str(output),
                        "--target-pid",
                        "2928",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "passed")
            self.assertEqual(summary["counts"]["usableMarkerCount"], 1)
            self.assertFalse(summary["safety"]["processMemoryReadByThisHelper"])
            self.assertFalse(summary["safety"]["movementSent"])

    def test_source_text_only_blocks_with_explicit_cause(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scan = root / "scan.json"
            output = root / "out"
            write_scan(
                scan,
                preview='message = "RRAPICOORD1. did not expose live coordinates"; local RiftReaderApiProbe = {}',
            )

            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--repo-root",
                        str(root),
                        "--scan-file",
                        str(scan),
                        "--output-root",
                        str(output),
                        "--target-pid",
                        "2928",
                        "--json",
                    ]
                )

            self.assertEqual(code, 2)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("rrapicoord-no-usable-marker", summary["blockers"])
            self.assertIn("rrapicoord-source-or-error-text-only-no-pipe-marker-record", summary["inferredCauses"])
            self.assertIn("scan-is-hitting-addon-source/static/error-context", summary["inferredCauses"])

    def test_partial_starting_marker_blocks_and_counts_field_issues(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scan = root / "scan.json"
            output = root / "out"
            write_scan(scan, preview="RRAPICOORD1|status=starting|savedVariablesUse=none")

            summary = build_summary(
                type(
                    "Args",
                    (),
                    {
                        "repo_root": root,
                        "output_root": output,
                        "scan_file": [scan],
                        "latest_count": 1,
                        "target_pid": 2928,
                        "process_name": "rift_x64",
                        "max_examples": 4,
                    },
                )()
            )

            self.assertEqual(summary["status"], "blocked")
            self.assertEqual(summary["counts"]["markerLikeCount"], 1)
            self.assertEqual(summary["counts"]["usableMarkerCount"], 0)
            self.assertIn("status:starting", summary["markerIssueCounts"])
            self.assertIn("only-starting/default-marker-observed", summary["inferredCauses"])

    def test_target_mismatch_blocks_even_with_usable_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scan = root / "scan.json"
            output = root / "out"
            write_scan(
                scan,
                preview=(
                    "RRAPICOORD1|status=pass|source=rift-api|view=Inspect.Unit.Detail(player)|"
                    "x=1.5|y=2|z=3|savedVariablesUse=none"
                ),
            )

            summary = build_summary(
                type(
                    "Args",
                    (),
                    {
                        "repo_root": root,
                        "output_root": output,
                        "scan_file": [scan],
                        "latest_count": 1,
                        "target_pid": 9999,
                        "process_name": "rift_x64",
                        "max_examples": 4,
                    },
                )()
            )

            self.assertEqual(summary["status"], "blocked")
            self.assertEqual(summary["counts"]["usableMarkerCount"], 1)
            self.assertIn("scan-target-pid-mismatch:scan.json:2928!=9999", summary["blockers"])
            self.assertFalse(summary["safety"]["promotionEligible"])


if __name__ == "__main__":
    unittest.main()
