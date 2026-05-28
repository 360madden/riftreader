import unittest

from scripts.static_owner_facing_discovery import compare_snapshots, normalize_degrees


def snapshot(label, yaw, scalar, coord_x=0.0):
    return {
        "status": "passed",
        "label": label,
        "owner": {"ownerAddress": "0x1000"},
        "coordinate": {"x": coord_x, "y": 0.0, "z": 0.0},
        "floatSamples": [
            {"offset": "0x10", "address": "0x1010", "value": scalar},
            {"offset": "0x320", "address": "0x1320", "value": coord_x},
        ],
        "vectorSamples": [
            {"offset": "0xD4", "address": "0x10D4", "length": 1.0, "yawDegrees": yaw, "pitchDegrees": 0.0},
        ],
        "relativeTargetSamples": [
            {
                "offset": "0x30C",
                "address": "0x130C",
                "targetCoordinate": {"x": coord_x + 10.0, "y": 0.0, "z": 0.0},
                "direction": {"x": 10.0, "y": 0.0, "z": 0.0},
                "planarDistance": 10.0,
                "yawDegrees": yaw,
                "pitchDegrees": 0.0,
            },
        ],
    }


class StaticOwnerFacingDiscoveryTests(unittest.TestCase):
    def test_normalize_degrees_short_delta(self):
        self.assertAlmostEqual(normalize_degrees(358.0), -2.0)
        self.assertAlmostEqual(normalize_degrees(-358.0), 2.0)

    def test_compare_scores_vector_and_scalar_candidates(self):
        result = compare_snapshots(
            [snapshot("baseline", 10.0, 1.0), snapshot("after-right", 25.0, 1.5), snapshot("after-left", 5.0, 1.1)],
            min_scalar_delta=0.001,
            min_yaw_delta_degrees=1.0,
            max_coordinate_planar_drift=0.5,
        )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["vectorCandidateCount"], 1)
        self.assertEqual(result["vectorCandidates"][0]["offset"], "0xD4")
        self.assertEqual(result["relativeTargetCandidateCount"], 1)
        self.assertEqual(result["relativeTargetCandidates"][0]["offset"], "0x30C")
        self.assertEqual(result["scalarCandidateCount"], 1)
        self.assertEqual(result["scalarCandidates"][0]["offset"], "0x10")

    def test_compare_warns_on_coordinate_drift(self):
        result = compare_snapshots(
            [snapshot("baseline", 10.0, 1.0, 0.0), snapshot("after-right", 20.0, 1.2, 2.0)],
            min_scalar_delta=0.001,
            min_yaw_delta_degrees=1.0,
            max_coordinate_planar_drift=0.5,
        )

        self.assertTrue(any(item.startswith("coordinate-drift-during-facing-capture") for item in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
