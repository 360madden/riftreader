from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DEFAULT_TOLERANCE = 0.25


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip(), 0)
        except ValueError:
            return None
    return None


def int_hex(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{int(value):X}"


def as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def coordinate_from_mapping(value: Any) -> dict[str, float] | None:
    if not isinstance(value, Mapping):
        return None
    result: dict[str, float] = {}
    for axis in ("x", "y", "z"):
        raw = value.get(axis, value.get(axis.upper()))
        parsed = as_float(raw)
        if parsed is None:
            return None
        result[axis] = parsed
    return result


def max_abs_delta(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    return max(abs(float(left[axis]) - float(right[axis])) for axis in ("x", "y", "z"))


def subtract(left: Mapping[str, float], right: Mapping[str, float]) -> dict[str, float]:
    return {axis: float(left[axis]) - float(right[axis]) for axis in ("x", "y", "z")}


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def readback_address(readback: Mapping[str, Any]) -> int | None:
    parsed = parse_int(readback.get("address"))
    if parsed is not None:
        return parsed
    return parse_int(readback.get("addressHex"))


def readback_matches(readback: Mapping[str, Any], tolerance: float) -> bool:
    if readback.get("directWithinTolerance") is True:
        return True
    if readback.get("offsetCorrectedWithinTolerance") is True:
        return True
    direct = as_float(readback.get("directMaxAbsDelta"))
    corrected = as_float(readback.get("offsetCorrectedMaxAbsDelta"))
    return (direct is not None and direct <= tolerance) or (corrected is not None and corrected <= tolerance)


def rank_readback(readback: Mapping[str, Any]) -> tuple[float, float, int]:
    corrected = as_float(readback.get("offsetCorrectedMaxAbsDelta"))
    direct = as_float(readback.get("directMaxAbsDelta"))
    rank = parse_int(readback.get("rank"))
    return (
        corrected if corrected is not None else math.inf,
        direct if direct is not None else math.inf,
        rank if rank is not None else 999_999,
    )


def normalize_summary(path: Path, doc: Mapping[str, Any], index: int) -> dict[str, Any]:
    reference = coordinate_from_mapping(doc.get("reference"))
    raw_readbacks = doc.get("readbacks")
    if not isinstance(raw_readbacks, list):
        raw_readbacks = []
    by_address: dict[int, Mapping[str, Any]] = {}
    for raw in raw_readbacks:
        if not isinstance(raw, Mapping):
            continue
        address = readback_address(raw)
        if address is None:
            continue
        existing = by_address.get(address)
        if existing is None or rank_readback(raw) < rank_readback(existing):
            by_address[address] = raw
    return {
        "index": index,
        "path": str(path),
        "generatedAtUtc": doc.get("generatedAtUtc"),
        "status": doc.get("status"),
        "readbackCandidateCount": doc.get("readbackCandidateCount"),
        "matchingCandidateCount": doc.get("matchingCandidateCount"),
        "reference": reference,
        "readbacksByAddress": by_address,
    }


def summarize_address(
    address: int,
    normalized: Sequence[Mapping[str, Any]],
    *,
    tolerance: float,
    stable_delta_tolerance: float,
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    for summary in normalized:
        by_address = summary.get("readbacksByAddress")
        if not isinstance(by_address, Mapping):
            continue
        readback = by_address.get(address)
        reference = summary.get("reference")
        if not isinstance(readback, Mapping):
            observations.append(
                {
                    "summaryIndex": summary.get("index"),
                    "present": False,
                    "summaryGeneratedAtUtc": summary.get("generatedAtUtc"),
                }
            )
            continue
        memory_value = coordinate_from_mapping(readback.get("memoryValue"))
        offset_corrected = coordinate_from_mapping(readback.get("offsetCorrectedValue"))
        direct_delta = as_float(readback.get("directMaxAbsDelta"))
        corrected_delta = as_float(readback.get("offsetCorrectedMaxAbsDelta"))
        observations.append(
            {
                "summaryIndex": summary.get("index"),
                "present": True,
                "summaryGeneratedAtUtc": summary.get("generatedAtUtc"),
                "rank": readback.get("rank"),
                "candidateId": readback.get("candidateId"),
                "classification": readback.get("classification"),
                "memoryValue": memory_value,
                "reference": reference,
                "offsetCorrectedValue": offset_corrected,
                "directMaxAbsDelta": direct_delta,
                "offsetCorrectedMaxAbsDelta": corrected_delta,
                "withinTolerance": readback_matches(readback, tolerance),
            }
        )

    present = [obs for obs in observations if obs.get("present")]
    match_count = sum(1 for obs in present if obs.get("withinTolerance"))
    first = present[0] if present else None
    last = present[-1] if present else None
    memory_delta_max_abs = None
    corrected_tracking_delta_error = None
    if first and last:
        first_memory = first.get("memoryValue")
        last_memory = last.get("memoryValue")
        if isinstance(first_memory, Mapping) and isinstance(last_memory, Mapping):
            memory_delta_max_abs = max_abs_delta(first_memory, last_memory)
        first_corrected = first.get("offsetCorrectedValue")
        last_corrected = last.get("offsetCorrectedValue")
        first_reference = first.get("reference")
        last_reference = last.get("reference")
        if (
            isinstance(first_corrected, Mapping)
            and isinstance(last_corrected, Mapping)
            and isinstance(first_reference, Mapping)
            and isinstance(last_reference, Mapping)
        ):
            corrected_delta = subtract(last_corrected, first_corrected)
            reference_delta = subtract(last_reference, first_reference)
            corrected_tracking_delta_error = max_abs_delta(corrected_delta, reference_delta)

    corrected_values = [
        obs.get("offsetCorrectedMaxAbsDelta")
        for obs in present
        if isinstance(obs.get("offsetCorrectedMaxAbsDelta"), (int, float))
    ]
    direct_values = [
        obs.get("directMaxAbsDelta")
        for obs in present
        if isinstance(obs.get("directMaxAbsDelta"), (int, float))
    ]
    candidate_ids = [str(obs.get("candidateId")) for obs in present if obs.get("candidateId")]
    classifications = [str(obs.get("classification")) for obs in present if obs.get("classification")]
    present_in_all = len(present) == len(normalized)
    all_match = present_in_all and match_count == len(normalized)
    if all_match and (
        corrected_tracking_delta_error is None or corrected_tracking_delta_error <= stable_delta_tolerance
    ):
        stability = "stable-repeat-match"
    elif match_count and not all_match:
        stability = "intermittent-or-dropped-match"
    elif match_count:
        stability = "repeat-match-with-drift"
    else:
        stability = "repeat-mismatch"

    return {
        "address": address,
        "addressHex": int_hex(address),
        "familyPage": int_hex(address & ~0xFFF),
        "presentCount": len(present),
        "summaryCount": len(normalized),
        "matchCount": match_count,
        "presentInAll": present_in_all,
        "allWithinTolerance": all_match,
        "stability": stability,
        "memoryDeltaMaxAbs": memory_delta_max_abs,
        "correctedTrackingDeltaError": corrected_tracking_delta_error,
        "bestOffsetCorrectedMaxAbsDelta": min(corrected_values) if corrected_values else None,
        "lastOffsetCorrectedMaxAbsDelta": corrected_values[-1] if corrected_values else None,
        "bestDirectMaxAbsDelta": min(direct_values) if direct_values else None,
        "lastDirectMaxAbsDelta": direct_values[-1] if direct_values else None,
        "candidateIds": sorted(set(candidate_ids)),
        "classifications": sorted(set(classifications)),
        "observations": observations,
    }


def summarize_families(address_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    families: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "familyPage": None,
            "addressCount": 0,
            "stableRepeatMatchCount": 0,
            "repeatMatchWithDriftCount": 0,
            "intermittentOrDroppedMatchCount": 0,
            "repeatMismatchCount": 0,
            "presentInAllCount": 0,
            "allWithinToleranceCount": 0,
            "bestStableAddress": None,
            "bestStableOffsetCorrectedMaxAbsDelta": None,
        }
    )
    for row in address_rows:
        family_page = str(row.get("familyPage"))
        family = families[family_page]
        family["familyPage"] = family_page
        family["addressCount"] += 1
        if row.get("presentInAll"):
            family["presentInAllCount"] += 1
        if row.get("allWithinTolerance"):
            family["allWithinToleranceCount"] += 1
        stability = row.get("stability")
        if stability == "stable-repeat-match":
            family["stableRepeatMatchCount"] += 1
            delta = as_float(row.get("bestOffsetCorrectedMaxAbsDelta"))
            best_delta = as_float(family.get("bestStableOffsetCorrectedMaxAbsDelta"))
            if delta is not None and (best_delta is None or delta < best_delta):
                family["bestStableOffsetCorrectedMaxAbsDelta"] = delta
                family["bestStableAddress"] = row.get("addressHex")
        elif stability == "repeat-match-with-drift":
            family["repeatMatchWithDriftCount"] += 1
        elif stability == "intermittent-or-dropped-match":
            family["intermittentOrDroppedMatchCount"] += 1
        else:
            family["repeatMismatchCount"] += 1
    return sorted(
        families.values(),
        key=lambda row: (
            -int(row.get("stableRepeatMatchCount") or 0),
            -int(row.get("allWithinToleranceCount") or 0),
            str(row.get("familyPage")),
        ),
    )


def build_summary(
    summary_paths: Sequence[Path],
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    stable_delta_tolerance: float = DEFAULT_TOLERANCE,
) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, path in enumerate(summary_paths, start=1):
        try:
            doc = load_json_object(path)
            normalized.append(normalize_summary(path.resolve(), doc, index))
        except Exception as exc:  # pragma: no cover - exercised by CLI error path
            errors.append(f"{path}:{type(exc).__name__}:{exc}")

    addresses: set[int] = set()
    for summary in normalized:
        by_address = summary.get("readbacksByAddress")
        if isinstance(by_address, Mapping):
            addresses.update(int(address) for address in by_address.keys())

    address_rows = [
        summarize_address(
            address,
            normalized,
            tolerance=tolerance,
            stable_delta_tolerance=stable_delta_tolerance,
        )
        for address in sorted(addresses)
    ]
    address_rows.sort(
        key=lambda row: (
            0 if row.get("stability") == "stable-repeat-match" else 1,
            row.get("bestOffsetCorrectedMaxAbsDelta")
            if isinstance(row.get("bestOffsetCorrectedMaxAbsDelta"), (int, float))
            else math.inf,
            row.get("address") or 0,
        )
    )
    families = summarize_families(address_rows)
    blockers: list[str] = []
    if len(normalized) < 2:
        blockers.append("need-at-least-two-readback-summaries")
    status = "passed" if not errors and not blockers else "blocked" if blockers and not errors else "failed"
    stable_count = sum(1 for row in address_rows if row.get("stability") == "stable-repeat-match")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "candidate-readback-stability",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "blockers": blockers,
        "warnings": [
            "Offline JSON comparison only; this does not promote movement truth.",
            "Stable repeat matches are candidate evidence until same-target ProofOnly passes.",
        ],
        "errors": errors,
        "summaryCount": len(normalized),
        "addressCount": len(address_rows),
        "stableRepeatMatchCount": stable_count,
        "tolerance": tolerance,
        "stableDeltaTolerance": stable_delta_tolerance,
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgLaunched": False,
            "debuggerAttached": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "providerWrites": False,
            "githubConnectorWrites": False,
        },
        "summaries": [
            {
                key: value
                for key, value in summary.items()
                if key not in {"readbacksByAddress"}
            }
            for summary in normalized
        ],
        "families": families,
        "addresses": address_rows,
        "next": {
            "recommendedAction": (
                "Use stable repeat-match rows only as candidate seeds; keep navigation blocked until a current "
                "same-target ProofOnly proof anchor is rebuilt."
            )
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Candidate readback stability",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Compared summaries: `{summary.get('summaryCount')}`",
        f"- Addresses: `{summary.get('addressCount')}`",
        f"- Stable repeat matches: `{summary.get('stableRepeatMatchCount')}`",
        "",
        "## Families",
        "",
        "| Family page | Addresses | Stable | All-match | Intermittent | Mismatch | Best stable address |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for family in summary.get("families", []):
        if not isinstance(family, Mapping):
            continue
        lines.append(
            f"| `{family.get('familyPage')}` | `{family.get('addressCount')}` | "
            f"`{family.get('stableRepeatMatchCount')}` | `{family.get('allWithinToleranceCount')}` | "
            f"`{family.get('intermittentOrDroppedMatchCount')}` | `{family.get('repeatMismatchCount')}` | "
            f"`{family.get('bestStableAddress')}` |"
        )
    lines.extend(
        [
            "",
            "## Top stable/repeat candidates",
            "",
            "| Address | Family | Stability | Matches | Best offset-corrected delta | Last offset-corrected delta | Tracking delta error |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in summary.get("addresses", [])[:25]:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"| `{row.get('addressHex')}` | `{row.get('familyPage')}` | `{row.get('stability')}` | "
            f"`{row.get('matchCount')}/{row.get('summaryCount')}` | "
            f"`{row.get('bestOffsetCorrectedMaxAbsDelta')}` | "
            f"`{row.get('lastOffsetCorrectedMaxAbsDelta')}` | "
            f"`{row.get('correctedTrackingDeltaError')}` |"
        )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        for blocker in summary.get("blockers", []):
            lines.append(f"- `{blocker}`")
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        for warning in summary.get("warnings", []):
            lines.append(f"- {warning}")
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare candidate readback summaries offline and rank repeat-stable candidate families."
    )
    parser.add_argument("summaries", nargs="*", type=Path, help="candidate-readback-summary.json paths")
    parser.add_argument("--output-root", type=Path, help="directory for summary.json and summary.md")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    parser.add_argument("--stable-delta-tolerance", type=float, default=DEFAULT_TOLERANCE)
    parser.add_argument("--json", action="store_true", help="print summary JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    repo_root = repo_root_from_module()
    output_root = args.output_root
    if output_root is None:
        output_root = repo_root / "scripts" / "captures" / f"candidate-readback-stability-{utc_stamp()}"
    summary = build_summary(
        [path.resolve() for path in args.summaries],
        tolerance=args.tolerance,
        stable_delta_tolerance=args.stable_delta_tolerance,
    )
    output_root = output_root.resolve()
    summary_json = output_root / "summary.json"
    summary_md = output_root / "summary.md"
    summary["repoRoot"] = str(repo_root)
    summary["artifacts"] = {"runDirectory": str(output_root), "summaryJson": str(summary_json), "summaryMarkdown": str(summary_md)}
    write_json(summary_json, summary)
    write_text_atomic(summary_md, render_markdown(summary))
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"status={summary.get('status')} summary={summary_json}")
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
