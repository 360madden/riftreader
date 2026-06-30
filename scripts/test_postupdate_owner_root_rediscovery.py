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

    def test_current_global_container_readback_schema_extracts_candidate_fields(self) -> None:
        readback = {
            "bestReadback": {
                "coordinateAddress": "0x1D4D7D4FDD8",
                "coordinate": {"x": 7256.38916015625, "y": 821.4478149414062, "z": 2990.00537109375},
            },
            "target": {
                "pid": 77152,
                "hwnd": "0x17A0DB2",
                "moduleBase": "0x7FF7211C0000",
                "expectedProcessStartUtc": "2026-06-02T15:45:29.2617327Z",
            },
        }

        self.assertEqual(helper.candidate_address_from_readback(readback), 0x1D4D7D4FDD8)
        self.assertEqual(
            helper.reference_from_readback(readback),
            {"x": 7256.38916015625, "y": 821.4478149414062, "z": 2990.00537109375},
        )
        self.assertEqual(
            helper.target_fields_from_readback(readback),
            {
                "pid": 77152,
                "hwnd": "0x17A0DB2",
                "moduleBase": "0x7FF7211C0000",
                "expectedProcessStartUtc": "2026-06-02T15:45:29.2617327Z",
            },
        )

    def test_process_start_matches_normalizes_local_and_utc_offsets(self) -> None:
        self.assertTrue(
            helper.process_start_matches(
                "2026-06-18T01:57:01.857121+00:00",
                "2026-06-17T21:57:01.8571209-04:00",
            )
        )
        self.assertFalse(
            helper.process_start_matches(
                "2026-06-18T01:57:01.857121+00:00",
                "2026-06-18T01:58:01.8571209+00:00",
            )
        )

    def test_candidate_target_mismatch_blockers_detect_stale_pid_hwnd_readback(self) -> None:
        blockers = helper.candidate_target_mismatch_blockers(
            {
                "pid": 130540,
                "hwnd": "0x9310EA",
                "expectedProcessStartUtc": "2026-06-18T06:07:51Z",
            },
            pid=148616,
            hwnd="0x618C8",
            expected_process_start_utc="2026-06-30T08:49:06.8032030-04:00",
        )

        self.assertIn("candidate-readback-pid-mismatch", blockers)
        self.assertIn("candidate-readback-hwnd-mismatch", blockers)
        self.assertIn("candidate-readback-process-start-mismatch", blockers)
        self.assertIn("candidate-readback-target-mismatch", blockers)

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

    def test_static_access_chain_summary_surfaces_orientation_root(self) -> None:
        packet = {
            "status": "blocked",
            "verdict": "static-access-chain-found-orientation-root-only",
            "artifacts": {"summaryJson": "summary.json"},
            "constructorEvidence": {
                "functionRva": "0x3F8B0",
                "fieldWriteCount": 10,
                "fieldOffsets": ["0x300", "0x320"],
                "candidateGlobalRoots": [
                    {
                        "globalRva": "0x335F508",
                        "instruction": "mov qword ptr [rip + 0x331f804], rdi",
                    }
                ],
            },
            "liveRootSamples": [
                {
                    "rootRva": "0x335F508",
                    "classification": "orientation-matrix-root-not-position-root",
                }
            ],
            "breadcrumbGlobalSamples": [
                {
                    "globalRva": "0x32DD7E8",
                    "classification": "module-vtable-global-container-no-coordinate",
                }
            ],
            "safety": {"targetMemoryBytesRead": True},
            "callBreadcrumbs": [{"depth": 0}],
        }

        summary = helper.summarize_static_access_chain(packet)

        self.assertEqual(summary["verdict"], "static-access-chain-found-orientation-root-only")
        self.assertIn("orientation-matrix-root-not-position-root", summary["liveRootClassifications"])
        self.assertIn("module-vtable-global-container-no-coordinate", summary["breadcrumbGlobalClassifications"])
        self.assertTrue(summary["targetMemoryBytesRead"])
        self.assertEqual(summary["candidateGlobalRoots"][0]["globalRva"], "0x335F508")

    def test_latest_static_access_chain_path_prefers_live_packet_over_newer_artifact_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            older_live = root / "postupdate-static-access-chain-20260602T010000Z"
            newer_artifact_only = root / "postupdate-static-access-chain-20260602T020000Z"
            older_live.mkdir()
            newer_artifact_only.mkdir()
            live_path = older_live / "summary.json"
            artifact_only_path = newer_artifact_only / "summary.json"
            live_path.write_text(
                '{"safety":{"targetMemoryBytesRead":true},"liveRootSamples":[{"classification":"orientation-matrix-root-not-position-root"}]}',
                encoding="utf-8",
            )
            artifact_only_path.write_text('{"safety":{"targetMemoryBytesRead":false}}', encoding="utf-8")

            selected = helper.latest_static_access_chain_path(root)

        self.assertEqual(selected, live_path)

    def test_global_container_readback_summary_surfaces_best_chain_and_polling(self) -> None:
        packet = {
            "status": "candidate",
            "verdict": "global-container-coordinate-chain-current-readback-passed",
            "artifacts": {"summaryJson": "summary.json"},
            "bestReadback": {
                "chain": "[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30",
                "classification": "candidate-coordinate-chain-current-readback",
                "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
                "deltaVsReference": {"maxAbsDelta": 0.004},
            },
            "polling": {
                "sampleCount": 5,
                "bestMatchingSampleCount": 5,
                "allSamplesMatchedReference": True,
                "stationaryDriftWithinLimit": True,
            },
            "safety": {"targetMemoryBytesRead": True},
        }

        summary = helper.summarize_global_container_readback(packet)

        self.assertEqual(summary["bestChain"], "[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30")
        self.assertEqual(summary["bestMaxAbsDelta"], 0.004)
        self.assertEqual(summary["polling"]["bestMatchingSampleCount"], 5)
        self.assertTrue(summary["targetMemoryBytesRead"])

    def test_self_test_passes(self) -> None:
        self.assertEqual(helper.self_test()["status"], "passed")


if __name__ == "__main__":
    unittest.main()
