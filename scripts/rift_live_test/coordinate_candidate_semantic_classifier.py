from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .parent_slot_neighborhood_summary import safe_list, safe_mapping
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DEFAULT_AXIS_TOLERANCE = 0.25
DEFAULT_STABLE_OFFSET_RANGE = 0.1


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def norm_hex(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return f"0x{value:X}"
    text = str(value).strip()
    if not text:
        return None
    try:
        return f"0x{int(text, 0):X}"
    except ValueError:
        return text.upper().replace("0X", "0x", 1)


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def coordinate_from_reference(reference: Mapping[str, Any]) -> dict[str, float | None]:
    coordinate = safe_mapping(reference.get("Coordinate") or reference.get("coordinate"))
    return {
        "x": as_float(coordinate.get("X", coordinate.get("x"))),
        "y": as_float(coordinate.get("Y", coordinate.get("y"))),
        "z": as_float(coordinate.get("Z", coordinate.get("z"))),
    }


def coordinate_from_match(match: Mapping[str, Any]) -> dict[str, float | None]:
    sample = safe_mapping(match.get("FirstDecodedSample") or match.get("firstDecodedSample"))
    return {
        "x": as_float(sample.get("X", sample.get("x"))),
        "y": as_float(sample.get("Y", sample.get("y"))),
        "z": as_float(sample.get("Z", sample.get("z"))),
    }


def pose_candidate_samples(
    pose_summary: Mapping[str, Any],
    *,
    candidate_id: str | None,
    candidate_address: str | None,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    normalized_address = norm_hex(candidate_address)
    for pose in safe_list(pose_summary.get("poseResults")):
        pose_map = safe_mapping(pose)
        api = coordinate_from_reference(safe_mapping(pose_map.get("reference")))
        if None in api.values():
            continue
        for raw_match in safe_list(pose_map.get("referenceMatches")):
            match = safe_mapping(raw_match)
            match_id = str(match.get("CandidateId") or match.get("candidateId") or "")
            match_address = norm_hex(match.get("CandidateAddressHex") or match.get("candidateAddressHex"))
            if candidate_id and match_id != candidate_id:
                continue
            if normalized_address and match_address != normalized_address:
                continue
            memory = coordinate_from_match(match)
            if None in memory.values():
                continue
            delta = {
                axis: float(memory[axis]) - float(api[axis])  # type: ignore[arg-type]
                for axis in ("x", "y", "z")
            }
            samples.append(
                {
                    "poseIndex": pose_map.get("poseIndex"),
                    "poseName": pose_map.get("poseName"),
                    "candidateId": match_id or None,
                    "candidateAddress": match_address,
                    "api": api,
                    "memory": memory,
                    "delta": delta,
                    "referenceMaxAbsDelta": match.get("ReferenceMaxAbsDelta"),
                    "stableAcrossReadbackSamples": match.get("StableAcrossReadbackSamples"),
                }
            )
            break
    return samples


def axis_range(samples: list[dict[str, Any]], axis: str) -> float | None:
    values = [as_float(safe_mapping(sample.get("delta")).get(axis)) for sample in samples]
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return max(clean) - min(clean)


def displacement_between(first: Mapping[str, Any], other: Mapping[str, Any]) -> float:
    a = safe_mapping(first.get("api"))
    b = safe_mapping(other.get("api"))
    ax = as_float(a.get("x"))
    az = as_float(a.get("z"))
    bx = as_float(b.get("x"))
    bz = as_float(b.get("z"))
    if None in (ax, az, bx, bz):
        return 0.0
    return math.hypot(float(bx) - float(ax), float(bz) - float(az))


def tracking_summary(
    samples: list[dict[str, Any]],
    *,
    axis_tolerance: float = DEFAULT_AXIS_TOLERANCE,
    stable_offset_range: float = DEFAULT_STABLE_OFFSET_RANGE,
) -> dict[str, Any]:
    if not samples:
        return {
            "sampleCount": 0,
            "xTracksApi": False,
            "yTracksApi": False,
            "zTracksApi": False,
            "stableYOffset": False,
            "classificationHint": "no-pose-samples",
        }
    x_abs = [abs(float(safe_mapping(sample.get("delta")).get("x"))) for sample in samples]
    y_abs = [abs(float(safe_mapping(sample.get("delta")).get("y"))) for sample in samples]
    z_abs = [abs(float(safe_mapping(sample.get("delta")).get("z"))) for sample in samples]
    y_range = axis_range(samples, "y")
    max_displacement = max(displacement_between(samples[0], sample) for sample in samples)
    x_tracks = max(x_abs) <= axis_tolerance
    y_tracks = max(y_abs) <= axis_tolerance
    z_tracks = max(z_abs) <= axis_tolerance
    stable_y = y_range is not None and y_range <= stable_offset_range and not y_tracks
    return {
        "sampleCount": len(samples),
        "xTracksApi": x_tracks,
        "yTracksApi": y_tracks,
        "zTracksApi": z_tracks,
        "stableYOffset": stable_y,
        "yOffsetRange": y_range,
        "meanYOffset": sum(float(safe_mapping(sample.get("delta")).get("y")) for sample in samples) / len(samples),
        "maxAbsDeltaByAxis": {"x": max(x_abs), "y": max(y_abs), "z": max(z_abs)},
        "maxApiPlanarDisplacement": max_displacement,
        "classificationHint": "xz-tracks-stable-y-offset" if x_tracks and z_tracks and stable_y else "direct-or-weak-tracking",
    }


def collect_context_text(*documents: Mapping[str, Any]) -> str:
    chunks: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key in {"asciiPreview", "preview", "kind", "familyKey", "scoreReasons", "warnings"}:
                    chunks.append(str(child))
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for document in documents:
        walk(document)
    return "\n".join(chunks).lower()


def root_signature_summary(root_sweep: Mapping[str, Any]) -> dict[str, Any]:
    top = safe_mapping(root_sweep.get("topOwnerFieldCandidate"))
    field_matches = safe_list(top.get("fieldMatches"))
    matched = [safe_mapping(field) for field in field_matches if safe_mapping(field).get("matched") is True]
    score_reasons = [str(reason) for reason in safe_list(top.get("scoreReasons"))]
    return {
        "topOwnerScore": top.get("score"),
        "matchedFieldCount": len(matched),
        "fieldCount": len(field_matches),
        "completeOwnerModuleFieldSignature": "complete-owner-module-field-signature" in score_reasons,
        "matchesKnownOwner": "matches-known-owner" in score_reasons,
        "matchesKnownCoordPointer": "matches-known-coord-pointer" in score_reasons,
        "ownerBase": top.get("ownerBase"),
        "coordPointerStorage": top.get("coordPointerStorage"),
        "coordPointerSlotOffset": top.get("coordPointerSlotOffset"),
    }


def classify_candidate(
    *,
    tracking: Mapping[str, Any],
    root_signature: Mapping[str, Any],
    context_text: str,
) -> tuple[str, list[str], bool]:
    reasons: list[str] = []
    promotion_eligible = False
    normalized_context = context_text.lower()
    if "playerposition" in normalized_context or "player position" in normalized_context:
        reasons.append("context-contains-playerPosition")
        return "api-buffer-coordinate-source", reasons, promotion_eligible
    if bool(root_signature.get("completeOwnerModuleFieldSignature")) and int(root_signature.get("matchedFieldCount") or 0) >= 4:
        reasons.append("complete-owner-module-field-signature")
        if bool(tracking.get("xTracksApi")) and bool(tracking.get("zTracksApi")) and bool(tracking.get("stableYOffset")):
            reasons.append("x-z-track-api-with-stable-y-offset")
            return "actor-like-offset-coordinate-candidate", reasons, promotion_eligible
        if bool(tracking.get("xTracksApi")) and bool(tracking.get("yTracksApi")) and bool(tracking.get("zTracksApi")):
            reasons.append("direct-xyz-api-tracking")
            return "actor-like-direct-coordinate-candidate", reasons, promotion_eligible
        return "actor-like-structural-candidate", reasons, promotion_eligible
    if bool(tracking.get("xTracksApi")) and bool(tracking.get("yTracksApi")) and bool(tracking.get("zTracksApi")):
        reasons.append("direct-xyz-api-tracking-without-structural-root")
        return "coordinate-copy-candidate", reasons, promotion_eligible
    reasons.append("insufficient-structural-or-tracking-evidence")
    return "candidate-only-unknown", reasons, promotion_eligible


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    pose_summary = load_json_object(args.pose_summary) if args.pose_summary else {}
    neighborhood = load_json_object(args.neighborhood_summary) if args.neighborhood_summary else {}
    root_sweep = load_json_object(args.root_sweep_summary) if args.root_sweep_summary else {}
    family_classifier = load_json_object(args.family_classifier_summary) if args.family_classifier_summary else {}
    samples = pose_candidate_samples(
        pose_summary,
        candidate_id=args.candidate_id,
        candidate_address=args.candidate_address,
    )
    tracking = tracking_summary(
        samples,
        axis_tolerance=float(args.axis_tolerance),
        stable_offset_range=float(args.stable_offset_range),
    )
    root_info = root_signature_summary(root_sweep)
    context_text = collect_context_text(neighborhood, root_sweep, family_classifier)
    classification, reasons, promotion_eligible = classify_candidate(
        tracking=tracking,
        root_signature=root_info,
        context_text=context_text,
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "coordinate-candidate-semantic-classifier",
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "candidate": {
            "candidateId": args.candidate_id,
            "candidateAddress": norm_hex(args.candidate_address),
            "classification": classification,
            "classificationReasons": reasons,
            "candidateOnly": True,
            "promotionEligible": promotion_eligible,
        },
        "tracking": tracking,
        "poseSamples": samples,
        "rootSignature": root_info,
        "inputs": {
            "poseSummary": str(args.pose_summary) if args.pose_summary else None,
            "neighborhoodSummary": str(args.neighborhood_summary) if args.neighborhood_summary else None,
            "rootSweepSummary": str(args.root_sweep_summary) if args.root_sweep_summary else None,
            "familyClassifierSummary": str(args.family_classifier_summary) if args.family_classifier_summary else None,
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgAttached": False,
            "targetMemoryWritten": False,
            "providerWrites": False,
            "gitMutation": False,
        },
        "next": {
            "recommendedAction": "Keep actor-like offset candidates out of promotion until a static/root chain and semantic Y-offset contract are proven."
        },
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    candidate = safe_mapping(summary.get("candidate"))
    tracking = safe_mapping(summary.get("tracking"))
    root = safe_mapping(summary.get("rootSignature"))
    lines = [
        "# Coordinate candidate semantic classifier",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Candidate: `{candidate.get('candidateId')}` / `{candidate.get('candidateAddress')}`",
        f"- Classification: `{candidate.get('classification')}`",
        f"- Promotion eligible: `{str(candidate.get('promotionEligible')).lower()}`",
        "",
        "## Evidence",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Pose sample count | `{tracking.get('sampleCount')}` |",
        f"| X tracks API | `{tracking.get('xTracksApi')}` |",
        f"| Y tracks API | `{tracking.get('yTracksApi')}` |",
        f"| Z tracks API | `{tracking.get('zTracksApi')}` |",
        f"| Stable Y offset | `{tracking.get('stableYOffset')}` |",
        f"| Mean Y offset | `{tracking.get('meanYOffset')}` |",
        f"| Max API planar displacement | `{tracking.get('maxApiPlanarDisplacement')}` |",
        f"| Matched owner fields | `{root.get('matchedFieldCount')}/{root.get('fieldCount')}` |",
        f"| Complete owner signature | `{root.get('completeOwnerModuleFieldSignature')}` |",
        "",
        "## Safety",
        "",
        "Read-only artifact classifier. It sends no input, attaches no debugger, writes no target memory, and does not promote coordinate truth.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-id")
    parser.add_argument("--candidate-address")
    parser.add_argument("--pose-summary", type=Path)
    parser.add_argument("--neighborhood-summary", type=Path)
    parser.add_argument("--root-sweep-summary", type=Path)
    parser.add_argument("--family-classifier-summary", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--axis-tolerance", type=float, default=DEFAULT_AXIS_TOLERANCE)
    parser.add_argument("--stable-offset-range", type=float, default=DEFAULT_STABLE_OFFSET_RANGE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo_root = repo_root_from_module()
    output_root = args.output_root or repo_root / "scripts" / "captures" / f"coordinate-candidate-semantic-classifier-{utc_stamp()}"
    output_root.mkdir(parents=True, exist_ok=True)
    summary = build_summary(args)
    artifacts = {
        "runDirectory": str(output_root),
        "summaryJson": str(output_root / "summary.json"),
        "summaryMarkdown": str(output_root / "summary.md"),
    }
    summary["artifacts"] = artifacts
    write_json(output_root / "summary.json", summary)
    write_text_atomic(output_root / "summary.md", build_markdown(summary))
    result = {
        "status": summary["status"],
        "classification": safe_mapping(summary.get("candidate")).get("classification"),
        "promotionEligible": safe_mapping(summary.get("candidate")).get("promotionEligible"),
        "summaryJson": artifacts["summaryJson"],
        "summaryMarkdown": artifacts["summaryMarkdown"],
    }
    print(json.dumps(result if args.json else summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
