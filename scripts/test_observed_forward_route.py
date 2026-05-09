from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from rift_live_test.observed_forward_route import (
    OBSERVED_FORWARD_SOURCE,
    ObservedForwardRouteError,
    ObservedForwardRouteOptions,
    build_observed_forward_route,
)


class ObservedForwardRouteTests(unittest.TestCase):
    def test_builds_route_from_proof_and_forward_series(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proof = root / "proof.json"
            series = root / "series.json"
            self._write_summary(proof, current={"x": 100.0, "y": 20.0, "z": 200.0})
            self._write_summary(
                series,
                current={"x": 101.0, "y": 20.0, "z": 200.0},
                series_delta={"deltaX": 1.0, "deltaY": 0.0, "deltaZ": 0.0, "planarDistance": 1.0},
            )

            route = build_observed_forward_route(
                ObservedForwardRouteOptions(
                    proof_summary=proof,
                    forward_series_summary=series,
                    output_file=root / "route.json",
                    distance_forward=2.0,
                )
            )

        self.assertEqual("observed-forward-smoke-route", route["provenance"]["kind"])
        self.assertEqual(OBSERVED_FORWARD_SOURCE, route["provenance"]["navigationBearingSource"])
        self.assertEqual(100.0, route["waypoints"][0]["x"])
        self.assertEqual(200.0, route["waypoints"][0]["z"])
        self.assertEqual(102.0, route["waypoints"][1]["x"])
        self.assertEqual(200.0, route["waypoints"][1]["z"])
        self.assertTrue(math.isclose(route["provenance"]["navigationBearingDegrees"], 0.0, abs_tol=0.0001))

    def test_rejects_low_signal_forward_series(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proof = root / "proof.json"
            series = root / "series.json"
            self._write_summary(proof, current={"x": 100.0, "y": 20.0, "z": 200.0})
            self._write_summary(
                series,
                current={"x": 100.01, "y": 20.0, "z": 200.0},
                series_delta={"deltaX": 0.01, "deltaY": 0.0, "deltaZ": 0.0, "planarDistance": 0.01},
            )

            with self.assertRaises(ObservedForwardRouteError):
                build_observed_forward_route(
                    ObservedForwardRouteOptions(
                        proof_summary=proof,
                        forward_series_summary=series,
                        output_file=root / "route.json",
                        min_observed_planar_distance=0.25,
                    )
                )

    @staticmethod
    def _write_summary(
        path: Path,
        *,
        current: dict[str, float],
        series_delta: dict[str, float] | None = None,
        pid: int = 49504,
        hwnd: str = "0x5121A",
    ) -> None:
        payload: dict[str, object] = {
            "status": "passed",
            "ok": True,
            "processName": "rift_x64",
            "processId": pid,
            "targetWindowHandle": hwnd,
            "movementSent": series_delta is not None,
            "noCheatEngine": True,
            "savedVariablesUsedAsLiveTruth": False,
            "currentCoordinate": {
                "x": current["x"],
                "y": current["y"],
                "z": current["z"],
                "recordedAtUtc": "2026-05-09T02:17:52.7633932Z",
            },
        }
        if series_delta is not None:
            payload["seriesCoordinateDelta"] = series_delta
        path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
