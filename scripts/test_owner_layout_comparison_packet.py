from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rift_live_test.owner_layout_comparison_packet import build_summary


class OwnerLayoutComparisonPacketTests(unittest.TestCase):
    def test_build_summary_classifies_heap_ref_as_candidate_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "docs" / "recovery").mkdir(parents=True)
            (root / "scripts" / "captures" / "family").mkdir(parents=True)

            candidate_file = root / "scripts" / "captures" / "family" / "api-family-vec3-candidates.jsonl"
            candidate_file.write_text(
                json.dumps(
                    {
                        "candidate_id": "api-family-hit-000001",
                        "absolute_address_hex": "0xABC",
                        "axis_order": "xyz",
                        "support_count": 1,
                        "best_max_abs_distance": 0.01,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            current_truth = root / "docs" / "recovery" / "current-truth.json"
            current_truth.write_text(
                json.dumps(
                    {
                        "target": {
                            "processName": "rift_x64",
                            "processId": 123,
                            "targetWindowHandle": "0x456",
                            "processStartUtc": "2026-05-27T00:00:00Z",
                            "moduleBase": "0x700000000000",
                        }
                    }
                ),
                encoding="utf-8",
            )
            pointer = root / "docs" / "recovery" / "current-proof-anchor-readback.json"
            pointer.write_text(
                json.dumps(
                    {
                        "target": {"processName": "rift_x64", "processId": 123, "targetWindowHandle": "0x456"},
                        "riftscanCandidateSource": {
                            "sourceKind": "current-proof-anchor-candidate-file",
                            "matchFile": str(candidate_file),
                            "candidateId": "api-family-hit-000001",
                            "sourceBaseAddressHex": "0xA00",
                            "sourceOffsetHex": "0xBC",
                            "sourceAbsoluteAddressHex": "0xABC",
                            "axisOrder": "xyz",
                        },
                    }
                ),
                encoding="utf-8",
            )
            pointer_family = root / "pointer-family-summary.json"
            pointer_family.write_text(
                json.dumps(
                    {
                        "status": "passed",
                        "rankedTargets": [
                            {
                                "target": "0xABC",
                                "hitCount": 1,
                                "moduleHitCount": 0,
                                "riftModuleHitCount": 0,
                                "hits": [{"address": "0x900", "regionBase": "0x800", "module": None}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            ref_storage = root / "ref-storage-summary.json"
            ref_storage.write_text(
                json.dumps(
                    {
                        "status": "passed",
                        "owner": {"address": "0x900"},
                        "analysis": {
                            "exactTargetCounts": {"0xABC": 1},
                            "modulePointerCount": 0,
                            "ownerWindowModulePointerCount": 0,
                            "regionMatchCount": 24,
                        },
                    }
                ),
                encoding="utf-8",
            )

            summary = build_summary(
                repo_root=root,
                current_truth_path=current_truth,
                current_proof_pointer_path=pointer,
                pointer_family_path=pointer_family,
                ref_storage_path=ref_storage,
            )

            self.assertEqual(summary["verdict"], "candidate-only-no-current-owner-layout-root")
            self.assertIn("module-rva-static-owner-root-absent-in-reviewed-artifacts", summary["blockers"])
            classes = {row["class"]: row for row in summary["classificationMatrix"]}
            self.assertEqual(classes["heap-local-ref-storage"]["status"], "supported")
            self.assertEqual(classes["module-rva-static-owner-root"]["status"], "absent")
            offsets = {row["relationship"]: row["offset"] for row in summary["relationshipOffsets"]}
            self.assertEqual(offsets["current-proof-source-base-to-coordinate"], "0xBC")
            self.assertEqual(offsets["current-ref-storage-to-coordinate-target"], "0x1BC")
            self.assertEqual(offsets["historical-owner-template-to-coordinate-field"], "0x320")
            self.assertFalse(summary["safety"]["targetMemoryBytesReadByThisPacket"])


if __name__ == "__main__":
    unittest.main()
