from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FORWARD_BEARING_KIND = "forward-key-movement-bearing"
OBSERVED_FORWARD_SOURCE = "observed-forward-vector-from-current-session-forwardseries"


@dataclass(frozen=True)
class ObservedForwardRouteOptions:
    proof_summary: Path
    forward_series_summary: Path
    output_file: Path
    distance_forward: float = 2.0
    arrival_radius: float = 0.75
    start_radius: float = 0.75
    forward_key: str = "w"
    default_pace: str = "keep"
    forward_pulse_milliseconds: int = 250
    post_pulse_sample_delay_milliseconds: int = 150
    no_progress_window_milliseconds: int = 3000
    minimum_progress_distance: float = 0.05
    wrong_way_tolerance_distance: float = 1.0
    max_travel_seconds: int = 20
    min_observed_planar_distance: float = 0.25


class ObservedForwardRouteError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            value = json.load(handle)
    except Exception as exc:  # pragma: no cover - exact parser error text varies.
        raise ObservedForwardRouteError(f"Unable to load JSON file '{path}': {exc}") from exc

    if not isinstance(value, dict):
        raise ObservedForwardRouteError(f"JSON file '{path}' did not contain an object.")
    return value


def _require_ok(summary: dict[str, Any], label: str) -> None:
    status = str(summary.get("status", "")).lower()
    if summary.get("ok") is not True or not status.startswith("passed"):
        raise ObservedForwardRouteError(
            f"{label} summary is not a passed run: status={summary.get('status')!r} ok={summary.get('ok')!r}."
        )

    if summary.get("noCheatEngine") is False:
        raise ObservedForwardRouteError(f"{label} summary does not confirm noCheatEngine=true.")

    if summary.get("savedVariablesUsedAsLiveTruth") is True:
        raise ObservedForwardRouteError(
            f"{label} summary used SavedVariables as live truth; refusing to generate a movement route."
        )


def _require_coordinate(summary: dict[str, Any], label: str) -> dict[str, float]:
    coord = summary.get("currentCoordinate")
    if not isinstance(coord, dict):
        raise ObservedForwardRouteError(f"{label} summary is missing currentCoordinate.")

    try:
        return {
            "x": float(coord["x"]),
            "y": float(coord["y"]),
            "z": float(coord["z"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise ObservedForwardRouteError(f"{label} summary currentCoordinate is incomplete or non-numeric.") from exc


def _require_matching_targets(proof: dict[str, Any], series: dict[str, Any]) -> None:
    proof_pid = proof.get("processId")
    series_pid = series.get("processId")
    if proof_pid != series_pid:
        raise ObservedForwardRouteError(f"Summary processId mismatch: proof={proof_pid!r} series={series_pid!r}.")

    proof_hwnd = str(proof.get("targetWindowHandle") or "").strip().lower()
    series_hwnd = str(series.get("targetWindowHandle") or "").strip().lower()
    if proof_hwnd and series_hwnd and proof_hwnd != series_hwnd:
        raise ObservedForwardRouteError(
            f"Summary targetWindowHandle mismatch: proof={proof.get('targetWindowHandle')!r} "
            f"series={series.get('targetWindowHandle')!r}."
        )


def _require_series_delta(series: dict[str, Any], min_observed_planar_distance: float) -> dict[str, float]:
    delta = series.get("seriesCoordinateDelta")
    if not isinstance(delta, dict):
        delta = series.get("coordinateDelta")
    if not isinstance(delta, dict):
        raise ObservedForwardRouteError("Forward-series summary is missing seriesCoordinateDelta.")

    try:
        delta_x = float(delta["deltaX"])
        delta_z = float(delta["deltaZ"])
        planar = float(delta.get("planarDistance") or math.hypot(delta_x, delta_z))
    except (KeyError, TypeError, ValueError) as exc:
        raise ObservedForwardRouteError("Forward-series coordinate delta is incomplete or non-numeric.") from exc

    if not math.isfinite(planar) or planar < min_observed_planar_distance:
        raise ObservedForwardRouteError(
            f"Observed forward planar distance {planar:.6f}m is below required "
            f"{min_observed_planar_distance:.6f}m."
        )

    if not math.isfinite(delta_x) or not math.isfinite(delta_z) or math.hypot(delta_x, delta_z) <= 0:
        raise ObservedForwardRouteError("Observed forward delta has no usable X/Z direction.")

    return {
        "deltaX": delta_x,
        "deltaY": float(delta.get("deltaY") or 0.0),
        "deltaZ": delta_z,
        "planarDistance": planar,
        "spatialDistance": float(delta.get("spatialDistance") or planar),
    }


def build_observed_forward_route(options: ObservedForwardRouteOptions) -> dict[str, Any]:
    if options.distance_forward <= 0:
        raise ObservedForwardRouteError("--distance-forward must be positive.")
    if options.arrival_radius <= 0:
        raise ObservedForwardRouteError("--arrival-radius must be positive.")
    if options.start_radius <= 0:
        raise ObservedForwardRouteError("--start-radius must be positive.")

    proof = load_json(options.proof_summary)
    series = load_json(options.forward_series_summary)
    _require_ok(proof, "ProofOnly")
    _require_ok(series, "ForwardSeries")
    _require_matching_targets(proof, series)

    start = _require_coordinate(proof, "ProofOnly")
    observed_delta = _require_series_delta(series, options.min_observed_planar_distance)
    observed_planar = math.hypot(observed_delta["deltaX"], observed_delta["deltaZ"])
    unit_x = observed_delta["deltaX"] / observed_planar
    unit_z = observed_delta["deltaZ"] / observed_planar
    destination = {
        "x": start["x"] + (unit_x * options.distance_forward),
        "y": start["y"],
        "z": start["z"] + (unit_z * options.distance_forward),
    }
    bearing_radians = math.atan2(destination["z"] - start["z"], destination["x"] - start["x"])
    bearing_degrees = math.degrees(bearing_radians)
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "schemaVersion": 1,
        "provenance": {
            "kind": "observed-forward-smoke-route",
            "generatedAtUtc": generated_at,
            "processName": proof.get("processName") or "rift_x64",
            "processId": proof.get("processId"),
            "targetWindowHandle": proof.get("targetWindowHandle"),
            "proofSummaryFile": str(options.proof_summary),
            "forwardSeriesSummaryFile": str(options.forward_series_summary),
            "proofCoordinateRecordedAtUtc": (proof.get("currentCoordinate") or {}).get("recordedAtUtc"),
            "forwardSeriesCoordinateRecordedAtUtc": (series.get("currentCoordinate") or {}).get("recordedAtUtc"),
            "navigationBearingKind": FORWARD_BEARING_KIND,
            "navigationBearingSource": OBSERVED_FORWARD_SOURCE,
            "navigationBearingDegrees": bearing_degrees,
            "distanceForward": options.distance_forward,
            "observedForwardDelta": observed_delta,
            "observedForwardUnitVector": {
                "x": unit_x,
                "z": unit_z,
            },
            "notes": [
                "Generated from current-session ProofOnly position plus observed W-key ForwardSeries displacement.",
                "This route intentionally avoids stale actor-facing truth; do not use it for auto-turn proof.",
                "Regenerate after any player movement, zone move, Rift restart, or proof-anchor refresh that changes coordinates.",
            ],
        },
        "movement": {
            "forwardKey": options.forward_key,
            "runKey": None,
            "walkKey": None,
            "defaultPace": options.default_pace,
            "forwardPulseMilliseconds": options.forward_pulse_milliseconds,
            "postPulseSampleDelayMilliseconds": options.post_pulse_sample_delay_milliseconds,
            "startRadius": options.start_radius,
            "defaultArrivalRadius": options.arrival_radius,
            "noProgressWindowMilliseconds": options.no_progress_window_milliseconds,
            "minimumProgressDistance": options.minimum_progress_distance,
            "wrongWayToleranceDistance": options.wrong_way_tolerance_distance,
            "maxTravelSeconds": options.max_travel_seconds,
        },
        "waypoints": [
            {
                "id": "smoke_start",
                "label": "Observed Forward Smoke Start",
                "x": start["x"],
                "y": start["y"],
                "z": start["z"],
                "arrivalRadius": options.arrival_radius,
                "pace": options.default_pace,
            },
            {
                "id": "smoke_destination",
                "label": "Observed Forward Smoke Destination",
                "x": destination["x"],
                "y": destination["y"],
                "z": destination["z"],
                "arrivalRadius": options.arrival_radius,
                "pace": options.default_pace,
            },
        ],
    }


def write_route(route: dict[str, Any], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(route, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a tiny waypoint smoke route from a current ProofOnly coordinate and "
            "an observed current-session ForwardSeries displacement."
        )
    )
    parser.add_argument("--proof-summary", required=True, type=Path)
    parser.add_argument("--forward-series-summary", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    parser.add_argument("--distance-forward", type=float, default=2.0)
    parser.add_argument("--arrival-radius", type=float, default=0.75)
    parser.add_argument("--start-radius", type=float, default=0.75)
    parser.add_argument("--forward-pulse-ms", type=int, default=250)
    parser.add_argument("--post-pulse-sample-delay-ms", type=int, default=150)
    parser.add_argument("--max-travel-seconds", type=int, default=20)
    parser.add_argument("--min-observed-planar-distance", type=float, default=0.25)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    options = ObservedForwardRouteOptions(
        proof_summary=args.proof_summary,
        forward_series_summary=args.forward_series_summary,
        output_file=args.output_file,
        distance_forward=args.distance_forward,
        arrival_radius=args.arrival_radius,
        start_radius=args.start_radius,
        forward_pulse_milliseconds=args.forward_pulse_ms,
        post_pulse_sample_delay_milliseconds=args.post_pulse_sample_delay_ms,
        max_travel_seconds=args.max_travel_seconds,
        min_observed_planar_distance=args.min_observed_planar_distance,
    )

    try:
        route = build_observed_forward_route(options)
        write_route(route, options.output_file)
    except ObservedForwardRouteError as exc:
        parser.error(str(exc))

    summary = {
        "status": "written",
        "outputFile": str(options.output_file),
        "processId": route["provenance"].get("processId"),
        "targetWindowHandle": route["provenance"].get("targetWindowHandle"),
        "distanceForward": route["provenance"].get("distanceForward"),
        "navigationBearingSource": route["provenance"].get("navigationBearingSource"),
    }
    print(json.dumps(summary, indent=2))
    return 0
