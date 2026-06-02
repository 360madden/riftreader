from __future__ import annotations

import unittest

from scripts import navigation_consumer_state as consumer


def promoted_truth() -> dict:
    return {
        "target": {
            "processName": "rift_x64",
            "processId": 12664,
            "targetWindowHandle": "0x205146C",
            "processStartUtc": "2026-06-01T17:19:45.159353Z",
            "moduleBase": "0x7FF6EE5D0000",
        },
        "navigationControlChains": {
            "position": {
                "state": "promoted",
                "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
            },
            "facingYaw": {
                "state": "promoted",
                "chain": "[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314",
            },
        },
    }


def nav_result() -> dict:
    return {
        "ok": True,
        "status": "passed",
        "verdict": "promoted-static-coordinate-resolver-readback-passed",
        "yawDegrees": 69.5,
        "pitchDegrees": -6.0,
        "turnRate0x304": 0.35,
        "turnRateClassification": "left",
        "playerCoordinate": {"x": 7256.4, "y": 821.4, "z": 2989.2},
        "facingTargetCoordinate": {"x": 7259.9, "y": 820.3, "z": 2998.5},
        "planarLookaheadDistance": 9.9,
        "rawJson": {
            "generatedAtUtc": "2026-06-02T05:38:35Z",
            "status": "passed",
            "verdict": "position-and-facing-nav-state-readback-passed",
            "target": {
                "processName": "rift_x64",
                "processId": 12664,
                "targetWindowHandle": "0x205146C",
                "expectedProcessStartUtc": "2026-06-01T17:19:45.159353Z",
                "moduleBase": "0x7FF6EE5D0000",
                "moduleBaseCheck": {"status": "passed"},
            },
            "reads": {
                "ownerAddress": "0x1E067A80010",
                "coordinate": {"x": 7256.4, "y": 821.4, "z": 2989.2},
                "navState": {
                    "coordinate": {"x": 7256.4, "y": 821.4, "z": 2989.2},
                    "facingTargetCoordinate": {"x": 7259.9, "y": 820.3, "z": 2998.5},
                    "catalogSupportFields": {"owner+0x438": {"state": "candidate"}},
                },
            },
            "artifacts": {"summaryJson": "scripts/captures/readback/summary.json"},
            "safety": {"targetMemoryBytesRead": True},
            "warnings": ["proof-anchor-comparison-not-requested"],
        },
    }


class NavigationConsumerStateTests(unittest.TestCase):
    def test_build_consumer_state_passes_with_promoted_position_and_yaw(self) -> None:
        summary = consumer.build_consumer_state(
            nav_result=nav_result(),
            current_truth=promoted_truth(),
            generated_at_utc="2026-06-02T05:39:00Z",
        )

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["navigation"]["position"]["state"], "promoted")
        self.assertEqual(summary["navigation"]["orientation"]["state"], "promoted")
        self.assertEqual(summary["navigation"]["orientation"]["yawDegrees"], 69.5)
        self.assertFalse(summary["navigation"]["routeControl"]["authorized"])
        self.assertFalse(summary["navigation"]["diagnostics"]["turnRate0x304"]["controlAllowed"])
        self.assertIn("turn-rate-0x304-is-diagnostic-only-not-control", summary["warnings"])
        self.assertIn("reject-status-other-than-passed", summary["consumerContract"]["requiredConsumerChecks"])
        self.assertFalse(summary["safety"]["movementSent"])
        self.assertFalse(summary["safety"]["targetMemoryBytesWritten"])

    def test_build_consumer_state_blocks_when_yaw_missing(self) -> None:
        result = nav_result()
        result["yawDegrees"] = None

        summary = consumer.build_consumer_state(nav_result=result, current_truth=promoted_truth())

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("yaw-degrees-missing", summary["blockers"])

    def test_build_consumer_state_blocks_when_readback_not_ok(self) -> None:
        result = nav_result()
        result["ok"] = False
        result["status"] = "blocked"

        summary = consumer.build_consumer_state(nav_result=result, current_truth=promoted_truth())

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("nav-state-readback-not-ok:blocked", summary["blockers"])

    def test_build_consumer_state_accepts_compact_readback_shape(self) -> None:
        result = nav_result()
        result["playerCoordinate"] = None
        result["rawJson"] = {
            "status": "passed",
            "verdict": "promoted-static-coordinate-resolver-readback-passed",
            "coordinate": {"x": 1.0, "y": 2.0, "z": 3.0},
            "summaryJson": "scripts/captures/latest/summary.json",
            "summaryMarkdown": "scripts/captures/latest/summary.md",
            "moduleBaseCheck": {"status": "passed"},
            "navState": {
                "catalogSupportFields": {"owner+0x438": {"state": "candidate"}},
            },
        }

        summary = consumer.build_consumer_state(nav_result=result, current_truth=promoted_truth())

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["navigation"]["position"]["coordinate"], {"x": 1.0, "y": 2.0, "z": 3.0})
        self.assertEqual(summary["navigation"]["diagnostics"]["supportFields"]["owner+0x438"]["state"], "candidate")
        self.assertEqual(summary["sourceArtifacts"]["readbackSummaryJson"], "scripts/captures/latest/summary.json")


if __name__ == "__main__":
    unittest.main()
