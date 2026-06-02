from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import postupdate_global_container_coordinate_readback as helper  # noqa: E402


class PostUpdateGlobalContainerCoordinateReadbackTests(unittest.TestCase):
    def test_extract_candidate_paths_from_static_access_chain_packet(self) -> None:
        packet = {
            "breadcrumbGlobalSamples": [
                {
                    "globalRva": "0x32DD7E8",
                    "classification": "global-container-child-coordinate-lead",
                    "sourceFunctionRva": "0xC38390",
                    "sourceInstructionRva": "0xC3843B",
                    "sourceInstruction": "mov rbx, qword ptr [rip + 0x26a53a6]",
                    "childPointerSamples": [
                        {
                            "parentOffset": "0x80",
                            "nearWorldTriples": [
                                {"offset": "0x1C", "maxAbsDelta": 0.3},
                                {"offset": "0x28", "maxAbsDelta": 0.004},
                            ],
                        }
                    ],
                }
            ]
        }

        paths = helper.extract_candidate_paths(packet)

        self.assertEqual(len(paths), 2)
        self.assertEqual(paths[0]["globalRva"], "0x32DD7E8")
        self.assertEqual(paths[0]["parentOffset"], "0x80")
        self.assertEqual(paths[0]["chain"], "[[rift_x64+0x32DD7E8]+0x80]+0x1C/+0x20/+0x24")
        self.assertEqual(paths[1]["chain"], "[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30")

    def test_classify_coordinate_read_detects_current_match(self) -> None:
        classification = helper.classify_coordinate_read(
            {"x": 7256.38916015625, "y": 821.4478149414062, "z": 2990.00537109375},
            {"x": 7256.3896, "y": 821.45, "z": 2990.01},
            0.01,
        )

        self.assertEqual(classification, "candidate-coordinate-chain-current-readback")

    def test_best_read_prefers_low_delta_match(self) -> None:
        best = helper.best_read(
            [
                {
                    "classification": "candidate-chain-readback-mismatch",
                    "deltaVsReference": {"maxAbsDelta": 100.0},
                },
                {
                    "classification": "candidate-coordinate-chain-current-readback",
                    "deltaVsReference": {"maxAbsDelta": 0.004},
                    "chain": "good",
                },
            ]
        )

        self.assertEqual(best["chain"], "good")

    def test_polling_analysis_detects_stationary_candidate(self) -> None:
        analysis = helper.polling_analysis(
            [
                {
                    "sampleIndex": 0,
                    "classification": "candidate-coordinate-chain-current-readback",
                    "coordinate": {"x": 100.0, "y": 5.0, "z": 200.0},
                    "deltaVsReference": {"maxAbsDelta": 0.01},
                },
                {
                    "sampleIndex": 1,
                    "classification": "candidate-coordinate-chain-current-readback",
                    "coordinate": {"x": 100.1, "y": 5.0, "z": 200.1},
                    "deltaVsReference": {"maxAbsDelta": 0.02},
                },
            ],
            max_stationary_planar_drift=0.5,
        )

        self.assertEqual(analysis["sampleCount"], 2)
        self.assertTrue(analysis["allSamplesMatchedReference"])
        self.assertTrue(analysis["stationaryDriftWithinLimit"])

    def test_self_test_passes(self) -> None:
        self.assertEqual(helper.self_test()["status"], "passed")


if __name__ == "__main__":
    unittest.main()
