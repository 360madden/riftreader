from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.root_signature_batch_sweep import (
    rank_owner_batch_hints,
    select_sweep_rvas,
    main,
)


class RootSignatureBatchSweepTests(unittest.TestCase):
    def test_rank_owner_batch_hints_prefers_repeated_owner_window_hits(self) -> None:
        owner_batch = {
            "moduleRvaHints": [
                {"rva": "0xA", "ownerWindowHitCount": 1, "ownerCount": 1},
                {"rva": "0xB", "ownerWindowHitCount": 3, "ownerCount": 2},
            ]
        }

        ranked = rank_owner_batch_hints(owner_batch)

        self.assertEqual(ranked[0]["rva"], "0xB")

    def test_rank_owner_batch_hints_skips_signature_rvas_by_default(self) -> None:
        owner_batch = {
            "moduleRvaHints": [
                {"rva": "0x26AAE70", "ownerWindowHitCount": 3, "ownerCount": 3},
                {"rva": "0x270FE10", "ownerWindowHitCount": 1, "ownerCount": 1},
            ]
        }

        ranked = rank_owner_batch_hints(owner_batch, root_signature_rvas={"0x26AAE70"})

        signature_row = next(row for row in ranked if row["rva"] == "0x26AAE70")
        self.assertIn("root-signature-field-rva", signature_row["skipReasons"])

    def test_select_sweep_rvas_skips_existing_current_target_sweeps(self) -> None:
        ranked = [
            {"rva": "0x270FE10", "score": 450, "skipReasons": []},
            {"rva": "0x2759FA8", "score": 149, "skipReasons": []},
        ]

        selected, skipped = select_sweep_rvas(
            ranked,
            existing_by_rva={"0x270FE10": [{"path": "old-summary.json"}]},
            skip_existing=True,
            max_rvas=8,
        )

        self.assertEqual([row["rva"] for row in selected], ["0x2759FA8"])
        self.assertIn("already-swept-for-current-target", skipped[0]["skipReasons"])

    def test_self_test_dry_run_writes_summary_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root_signature = Path(temp) / "root.json"
            root_signature.write_text(
                json.dumps(
                    {
                        "signature": {
                            "ownerModuleFields": [
                                {"offsetFromOwner": "0x0", "rva": "0x26AAE70"},
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            output_root = Path(temp) / "batch-sweep"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--self-test",
                        "--root-signature-json",
                        str(root_signature),
                        "--output-root",
                        str(output_root),
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            summary = json.loads((output_root / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "passed")
            self.assertEqual(summary["counts"]["selectedRvaCount"], 1)
            self.assertFalse(summary["safety"]["targetMemoryBytesRead"])
            self.assertFalse(summary["safety"]["movementSent"])
            self.assertEqual(summary["commands"][0]["status"], "planned")


if __name__ == "__main__":
    unittest.main()
