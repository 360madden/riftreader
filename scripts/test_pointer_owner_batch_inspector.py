from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.pointer_owner_batch_inspector import (
    choose_target_window_base,
    extract_owner_probes,
    main,
    module_rva_rollup,
    score_probe_result,
    target_entries_from_pointer_summary,
)


def make_pointer_summary() -> dict:
    return {
        "status": "passed",
        "target": {"pid": 2928, "hwndHex": "0xC0994"},
        "rankedTargets": [
            {
                "target": "0x268E1130000",
                "targetLabel": "exact-reference-match-family-base-64k",
                "hits": [
                    {"address": "0x2688D990878", "regionBase": "0x2688D990000", "module": None},
                    {"address": "0x26892087DB8", "regionBase": "0x26892070000", "module": None},
                ],
            },
            {
                "target": "0x268E113FED0",
                "targetLabel": "exact-reference-match-x",
                "hits": [{"address": "0x2688D990878", "regionBase": "0x2688D990000", "module": None}],
            },
        ],
    }


class PointerOwnerBatchInspectorTests(unittest.TestCase):
    def test_extract_owner_probes_dedupes_by_hit_address(self) -> None:
        probes = extract_owner_probes(make_pointer_summary(), max_owners=8, include_module_hits=False)

        self.assertEqual([probe["ownerAddressHex"] for probe in probes], ["0x2688D990878", "0x26892087DB8"])
        self.assertEqual(probes[0]["label"], "ref-to-268E1130000-01")

    def test_choose_target_window_prefers_family_base_label(self) -> None:
        targets = target_entries_from_pointer_summary(make_pointer_summary())

        self.assertEqual(
            choose_target_window_base(targets, explicit_base=None, align_bytes=0x10000),
            0x268E1130000,
        )

    def test_score_probe_result_prefers_exact_coord_target_refs(self) -> None:
        targets = target_entries_from_pointer_summary(make_pointer_summary())
        row = {
            "status": "passed",
            "exactTargetCounts": {"0x268E1130000": 1, "0x268E113FED0": 1},
            "ownerWindowModulePointerCount": 2,
            "modulePointerCount": 6,
        }

        score, reasons = score_probe_result(row, targets)

        self.assertGreaterEqual(score, 140)
        self.assertTrue(any(reason.startswith("exact-coordinate-target-ref") for reason in reasons))

    def test_module_rva_rollup_uses_owner_window_hints_only(self) -> None:
        rows = [
            {
                "owner": "0x1000",
                "childSummary": {
                    "analysis": {
                        "ownerWindowModulePointers": [
                            {
                                "address": "0x1008",
                                "offsetFromOwner": "0x8",
                                "value": "0x700020",
                                "classification": {"modulePointer": {"rva": "0x20"}},
                            }
                        ],
                        "regionMatches": [
                            {
                                "address": "0x2000",
                                "classification": {"modulePointer": {"rva": "0x999"}},
                            }
                        ],
                    }
                },
            },
            {
                "owner": "0x1100",
                "childSummary": {
                    "analysis": {
                        "ownerWindowModulePointers": [
                            {
                                "address": "0x1108",
                                "offsetFromOwner": "0x8",
                                "value": "0x700020",
                                "classification": {"modulePointer": {"rva": "0x20"}},
                            }
                        ]
                    }
                },
            },
        ]

        rollup = module_rva_rollup(rows, top_limit=4)

        self.assertEqual(rollup[0]["rva"], "0x20")
        self.assertEqual(rollup[0]["ownerWindowHitCount"], 2)
        self.assertEqual(rollup[0]["ownerCount"], 2)

    def test_self_test_writes_summary_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output_root = Path(temp) / "batch"
            with redirect_stdout(StringIO()):
                code = main(["--self-test", "--output-root", str(output_root), "--json"])

            self.assertEqual(code, 0)
            summary = json.loads((output_root / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "passed")
            self.assertFalse(summary["safety"]["movementSent"])
            self.assertFalse(summary["safety"]["targetMemoryBytesRead"])
            self.assertEqual(summary["moduleRvaHints"][0]["rva"], "0x20")


if __name__ == "__main__":
    unittest.main()
