from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import postupdate_owner_root_rediscovery as helper  # noqa: E402


class PostUpdateOwnerRootRediscoveryTests(unittest.TestCase):
    def test_owner_shape_classifier_accepts_module_pointer_and_coordinate_match(self) -> None:
        module_base = 0x7FF700000000
        data = bytearray(helper.DEFAULT_OWNER_WINDOW_BYTES)
        data[0:8] = (module_base + 0x1234).to_bytes(8, "little")
        struct.pack_into("<fff", data, 0x320, 100.0, 200.0, 300.0)
        struct.pack_into("<fff", data, 0x30C, 101.0, 200.0, 301.0)
        struct.pack_into("<f", data, 0x300, 1.0)
        struct.pack_into("<f", data, 0x304, 2.0)
        struct.pack_into("<f", data, 0x438, 3.0)

        result = helper.classify_owner_shape_from_bytes(
            owner_base=0x200000000,
            offset_assumption=0x320,
            data=bytes(data),
            module_base=module_base,
            module_size=0x500000,
            reference={"x": 100.0, "y": 200.0, "z": 300.0},
            tolerance=0.25,
        )

        self.assertEqual(result["classification"], "owner-shaped-candidate")
        self.assertGreaterEqual(result["score"], 60)
        self.assertEqual(result["modulePointerCountFirst0x90"], 1)

    def test_owner_shape_classifier_rejects_direct_coordinate_copy(self) -> None:
        data = bytearray(helper.DEFAULT_OWNER_WINDOW_BYTES)
        struct.pack_into("<fff", data, 0x320, 100.0, 200.0, 300.0)

        result = helper.classify_owner_shape_from_bytes(
            owner_base=0x200000000,
            offset_assumption=0x320,
            data=bytes(data),
            module_base=0x7FF700000000,
            module_size=0x500000,
            reference={"x": 100.0, "y": 200.0, "z": 300.0},
            tolerance=0.25,
        )

        self.assertEqual(result["classification"], "direct-coordinate-copy-not-owner-shaped")
        self.assertIn("coordinate-matches-but-owner-header-lacks-module-shape", result["reasons"])

    def test_static_cluster_ranking_groups_promoted_layout_offsets(self) -> None:
        matrix = {
            "offsetHits": {
                "0x320": [
                    {"linearFunctionStartRva": "0x3F8B0", "operandAccess": "write", "instruction": "mov", "rva": "0x1"}
                ],
                "0x324": [
                    {"linearFunctionStartRva": "0x3F8B0", "operandAccess": "write", "instruction": "mov", "rva": "0x2"}
                ],
                "0x328": [
                    {"linearFunctionStartRva": "0x18BC50", "operandAccess": "read", "instruction": "lea", "rva": "0x3"}
                ],
                "0x999": [
                    {"linearFunctionStartRva": "0xBAD", "operandAccess": "write", "instruction": "mov", "rva": "0x4"}
                ],
            }
        }

        ranked = helper.rank_static_clusters(matrix)

        self.assertEqual(ranked[0]["functionStartRva"], "0x3F8B0")
        self.assertEqual(ranked[0]["offsets"], ["0x320", "0x324"])
        self.assertNotIn("0x999", ranked[0]["offsets"])

    def test_best_candidate_from_readback_uses_best_readback(self) -> None:
        readback = {
            "bestReadback": {
                "candidateId": "api-family-hit-000001",
                "addressHex": "0x1234",
                "reference": {"x": 1, "y": 2, "z": 3},
            }
        }

        self.assertEqual(helper.candidate_address_from_readback(readback), 0x1234)
        self.assertEqual(helper.reference_from_readback(readback), {"x": 1.0, "y": 2.0, "z": 3.0})

    def test_read_game_epoch_extracts_manifest_version_and_exe_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "manifest64.txt").write_text(
                "version STABLE-1-1152-a-1256395\n"
                "rift_x64.exe:a8ba8748ea752e4e5581cea34188dc702469c923:59955136\n",
                encoding="utf-8",
            )
            (root / "rift_x64.exe").write_bytes(b"fake")

            epoch = helper.read_game_epoch(root)

        self.assertEqual(epoch["status"], "passed")
        self.assertEqual(epoch["manifestVersion"], "STABLE-1-1152-a-1256395")
        self.assertEqual(epoch["manifestRiftX64Sha1"], "a8ba8748ea752e4e5581cea34188dc702469c923")
        self.assertEqual(epoch["manifestRiftX64Size"], 59955136)
        self.assertEqual(epoch["executableLength"], 4)

    def test_root_signature_batch_summary_classifies_heap_only_sweeps(self) -> None:
        batch = {
            "status": "passed",
            "counts": {"selectedRvaCount": 1, "resultCount": 1, "commandStatuses": {"completed": 1}},
            "results": [
                {
                    "rva": "0x26E5E80",
                    "status": "passed",
                    "counts": {"modulePointerHitCount": 1024},
                    "topOwnerFieldCandidate": {
                        "score": 190,
                        "ownerBase": "0x1D4BA11F480",
                        "fieldMatches": [
                            {"matched": True},
                            {"matched": True},
                            {"matched": False},
                            {"matched": False},
                        ],
                        "scoreReasons": ["matched-owner-module-fields=2/4", "matches-known-owner"],
                    },
                    "topParentSlotCandidate": {
                        "score": 15,
                        "parentSlot": "0x1D4BA093D30",
                        "ownerPointer": "0x1D4BA093D40",
                        "scoreReasons": ["owner-pointer-heap-like"],
                    },
                }
            ],
        }

        summary = helper.summarize_root_signature_batch(batch)

        self.assertEqual(summary["classification"], "heap-ref-storage-only-no-parent-root")
        self.assertEqual(summary["highSignalResultCount"], 0)
        self.assertFalse(summary["topResults"][0]["highSignal"])

    def test_root_signature_batch_summary_detects_high_signal_parent(self) -> None:
        batch = {
            "status": "passed",
            "counts": {"selectedRvaCount": 1, "resultCount": 1},
            "results": [
                {
                    "rva": "0x1",
                    "topOwnerFieldCandidate": {"fieldMatches": [{"matched": False}], "scoreReasons": []},
                    "topParentSlotCandidate": {
                        "score": 160,
                        "scoreReasons": ["matches-known-owner", "matches-known-parent-slot"],
                    },
                }
            ],
        }

        summary = helper.summarize_root_signature_batch(batch)

        self.assertEqual(summary["classification"], "root-candidate-leads-present")
        self.assertEqual(summary["highSignalResultCount"], 1)

    def test_self_test_passes(self) -> None:
        self.assertEqual(helper.self_test()["status"], "passed")


if __name__ == "__main__":
    unittest.main()
