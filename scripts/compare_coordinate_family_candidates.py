#!/usr/bin/env python3
# Version: riftreader-compare-coordinate-family-candidates-v0.1.0
# Total-Character-Count: 9782
# Purpose: Compare two coordinate-family candidate JSONL files to identify stable exact addresses, shared address bands, and pose displacement evidence.

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                rows.append(json.loads(text))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"{path}: JSONL parse failed at line {line_no}: {exc}") from exc
    return rows


def parse_hex(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return int(text, 0)


def hex_text(value: int | None) -> str | None:
    return None if value is None else f"0x{value:X}"


def get_address(row: dict[str, Any]) -> int | None:
    for key in ("absolute_address_hex", "AbsoluteAddressHex", "candidate_address_hex", "CandidateAddressHex", "addressHex", "AddressHex"):
        if key in row and row[key] not in (None, ""):
            return parse_hex(row[key])
    return None


def get_region_base(row: dict[str, Any]) -> int | None:
    for key in ("base_address_hex", "BaseAddressHex", "regionBaseHex", "RegionBaseHex", "region_address_hex", "RegionAddressHex"):
        if key in row and row[key] not in (None, ""):
            return parse_hex(row[key])
    return None


def get_value(row: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    preview = row.get("value_preview") or row.get("ValuePreview")
    if isinstance(preview, list) and len(preview) >= 3:
        return float(preview[0]), float(preview[1]), float(preview[2])

    x = row.get("best_memory_x", row.get("x", row.get("X")))
    y = row.get("best_memory_y", row.get("y", row.get("Y")))
    z = row.get("best_memory_z", row.get("z", row.get("Z")))
    if x is None or y is None or z is None:
        return None, None, None
    return float(x), float(y), float(z)


def coord_delta(a: tuple[float | None, float | None, float | None], b: tuple[float | None, float | None, float | None]) -> dict[str, float | None]:
    if any(value is None for value in (*a, *b)):
        return {"dx": None, "dy": None, "dz": None, "planar": None, "spatial": None, "maxAbs": None}
    dx = float(b[0]) - float(a[0])
    dy = float(b[1]) - float(a[1])
    dz = float(b[2]) - float(a[2])
    return {
        "dx": dx,
        "dy": dy,
        "dz": dz,
        "planar": math.sqrt((dx * dx) + (dz * dz)),
        "spatial": math.sqrt((dx * dx) + (dy * dy) + (dz * dz)),
        "maxAbs": max(abs(dx), abs(dy), abs(dz)),
    }


def candidate_id(row: dict[str, Any]) -> str:
    return str(row.get("candidate_id") or row.get("CandidateId") or "")


def summarize(row: dict[str, Any]) -> dict[str, Any]:
    address = get_address(row)
    region = get_region_base(row)
    value = get_value(row)
    return {
        "candidateId": candidate_id(row),
        "addressHex": hex_text(address),
        "regionBaseHex": hex_text(region),
        "pageHex": hex_text(address & ~0xFFF) if address is not None else None,
        "megapageHex": hex_text(address & ~0xFFFFF) if address is not None else None,
        "value": {"x": value[0], "y": value[1], "z": value[2]},
        "bestMaxAbsDistance": row.get("best_max_abs_distance") or row.get("BestMaxAbsDistance"),
        "classification": row.get("classification") or row.get("Classification"),
    }


def group_by(rows: list[dict[str, Any]], key_fn) -> dict[Any, list[dict[str, Any]]]:
    groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = key_fn(row)
        if key is not None:
            groups[key].append(row)
    return dict(groups)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare coordinate-family candidates from two poses.")
    parser.add_argument("--pose-a", required=True)
    parser.add_argument("--pose-b", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--markdown", default=None)
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    pose_a = Path(args.pose_a).resolve()
    pose_b = Path(args.pose_b).resolve()
    if not pose_a.exists():
        raise FileNotFoundError(pose_a)
    if not pose_b.exists():
        raise FileNotFoundError(pose_b)

    a_rows = load_jsonl(pose_a)
    b_rows = load_jsonl(pose_b)

    a_by_address = group_by(a_rows, get_address)
    b_by_address = group_by(b_rows, get_address)
    a_by_region = group_by(a_rows, get_region_base)
    b_by_region = group_by(b_rows, get_region_base)
    a_by_page = group_by(a_rows, lambda row: (get_address(row) & ~0xFFF) if get_address(row) is not None else None)
    b_by_page = group_by(b_rows, lambda row: (get_address(row) & ~0xFFF) if get_address(row) is not None else None)
    a_by_megapage = group_by(a_rows, lambda row: (get_address(row) & ~0xFFFFF) if get_address(row) is not None else None)
    b_by_megapage = group_by(b_rows, lambda row: (get_address(row) & ~0xFFFFF) if get_address(row) is not None else None)

    shared_addresses: list[dict[str, Any]] = []
    for address in sorted(set(a_by_address) & set(b_by_address)):
        a = a_by_address[address][0]
        b = b_by_address[address][0]
        shared_addresses.append({
            "addressHex": hex_text(address),
            "poseA": summarize(a),
            "poseB": summarize(b),
            "valueDeltaBMinusA": coord_delta(get_value(a), get_value(b)),
        })

    shared_regions = [
        {
            "regionBaseHex": hex_text(region),
            "poseACount": len(a_by_region[region]),
            "poseBCount": len(b_by_region[region]),
            "poseAFirst": summarize(a_by_region[region][0]),
            "poseBFirst": summarize(b_by_region[region][0]),
        }
        for region in sorted(set(a_by_region) & set(b_by_region))
    ]

    shared_pages = [
        {
            "pageHex": hex_text(page),
            "poseACount": len(a_by_page[page]),
            "poseBCount": len(b_by_page[page]),
            "poseAFirst": summarize(a_by_page[page][0]),
            "poseBFirst": summarize(b_by_page[page][0]),
        }
        for page in sorted(set(a_by_page) & set(b_by_page))
    ]

    shared_megapages = [
        {
            "megapageHex": hex_text(page),
            "poseACount": len(a_by_megapage[page]),
            "poseBCount": len(b_by_megapage[page]),
            "poseAFirst": summarize(a_by_megapage[page][0]),
            "poseBFirst": summarize(b_by_megapage[page][0]),
        }
        for page in sorted(set(a_by_megapage) & set(b_by_megapage))
    ]

    result = {
        "schemaVersion": 1,
        "mode": "riftreader-coordinate-family-candidate-comparison",
        "generatedAtUtc": utc_iso(),
        "poseAFile": str(pose_a),
        "poseBFile": str(pose_b),
        "poseACount": len(a_rows),
        "poseBCount": len(b_rows),
        "sharedAddressCount": len(shared_addresses),
        "sharedRegionCount": len(shared_regions),
        "sharedPageCount": len(shared_pages),
        "sharedMegapageCount": len(shared_megapages),
        "sharedAddresses": shared_addresses[: args.top],
        "sharedRegions": shared_regions[: args.top],
        "sharedPages": shared_pages[: args.top],
        "sharedMegapages": shared_megapages[: args.top],
        "interpretation": {
            "hasStableExactAddress": bool(shared_addresses),
            "hasSharedRegion": bool(shared_regions),
            "hasSharedMegapage": bool(shared_megapages),
            "movementAllowed": False,
            "note": "Comparison evidence only. It does not authorize movement or proof promotion by itself.",
        },
    }

    output = Path(args.output).resolve() if args.output else pose_b.parent / "family-candidate-comparison-vs-pose-a.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")

    markdown = Path(args.markdown).resolve() if args.markdown else pose_b.parent / "family-candidate-comparison-vs-pose-a.md"
    markdown.write_text(
        "\n".join([
            "# Coordinate family candidate comparison",
            "",
            f"- Pose A candidates: `{len(a_rows)}`",
            f"- Pose B candidates: `{len(b_rows)}`",
            f"- Shared exact addresses: `{len(shared_addresses)}`",
            f"- Shared region bases: `{len(shared_regions)}`",
            f"- Shared 4K pages: `{len(shared_pages)}`",
            f"- Shared 1MB address bands: `{len(shared_megapages)}`",
            "",
            "Movement remains blocked. This comparison is evidence only.",
            "",
        ]),
        encoding="utf-8",
    )

    print(json.dumps({
        "status": "passed",
        "poseACount": len(a_rows),
        "poseBCount": len(b_rows),
        "sharedAddressCount": len(shared_addresses),
        "sharedRegionCount": len(shared_regions),
        "sharedPageCount": len(shared_pages),
        "sharedMegapageCount": len(shared_megapages),
        "summaryJson": str(output),
        "summaryMarkdown": str(markdown),
        "movementAllowed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
