from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def safe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text, 0)
    except ValueError:
        return None


def int_hex(value: int | None) -> str | None:
    return None if value is None else f"0x{value:X}"


def signed_hex(value: int | None) -> str | None:
    if value is None:
        return None
    return f"-0x{-value:X}" if value < 0 else f"0x{value:X}"


def normalize_hex(value: Any) -> str | None:
    return int_hex(parse_int(value))


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def infer_coord_pointer(row: Mapping[str, Any]) -> str | None:
    direct = normalize_hex(row.get("sourceTarget") or row.get("sourceTargetLabel"))
    if direct:
        return direct
    exact_counts = safe_mapping(row.get("exactTargetCounts"))
    for key, count in exact_counts.items():
        if int(count or 0) > 0:
            parsed = normalize_hex(key)
            if parsed:
                return parsed
    return None


def select_owner_row(owner_batch: Mapping[str, Any], explicit_owner: str | None = None) -> dict[str, Any]:
    wanted_owner = normalize_hex(explicit_owner) if explicit_owner else None
    rows = [safe_mapping(row) for row in safe_list(owner_batch.get("rankedRows"))]
    if wanted_owner:
        for row in rows:
            if normalize_hex(row.get("owner")) == wanted_owner:
                return row
        return {"owner": wanted_owner}
    return rows[0] if rows else {}


def owner_module_fields(owner_batch: Mapping[str, Any], owner_hex: str | None) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None, str | None]] = set()
    for hint in safe_list(owner_batch.get("moduleRvaHints")):
        hint_map = safe_mapping(hint)
        for example in safe_list(hint_map.get("examples")):
            example_map = safe_mapping(example)
            if owner_hex and normalize_hex(example_map.get("owner")) != owner_hex:
                continue
            storage = normalize_hex(example_map.get("storageAddress"))
            offset = signed_hex(parse_int(example_map.get("offsetFromOwner")))
            rva = normalize_hex(example_map.get("rva") or hint_map.get("rva"))
            value = normalize_hex(example_map.get("value"))
            key = (offset, rva, storage)
            if key in seen:
                continue
            seen.add(key)
            fields.append(
                {
                    "offsetFromOwner": offset,
                    "rva": rva,
                    "absoluteValue": value,
                    "sourceStorageAddress": storage,
                    "candidateOnly": True,
                }
            )
    return sorted(fields, key=lambda item: (parse_int(item.get("offsetFromOwner")) or 0, str(item.get("rva"))))


def build_seed_packet(
    owner_batch: Mapping[str, Any],
    *,
    source_owner_batch: str | None = None,
    explicit_owner: str | None = None,
) -> dict[str, Any]:
    row = select_owner_row(owner_batch, explicit_owner)
    owner_hex = normalize_hex(row.get("owner") or explicit_owner)
    coord_pointer = infer_coord_pointer(row)
    fields = owner_module_fields(owner_batch, owner_hex)
    blockers: list[str] = []
    warnings: list[str] = []
    if not owner_hex:
        blockers.append("owner-base-missing")
    if not coord_pointer:
        blockers.append("coord-pointer-missing")
    if not fields:
        blockers.append("owner-module-fields-missing")
    if len(fields) < 3:
        warnings.append(f"weak-owner-module-field-count:{len(fields)}")

    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "postupdate-root-signature-seed",
        "generatedAtUtc": utc_iso(),
        "status": "blocked" if blockers else "candidate-only",
        "sourceOwnerBatch": source_owner_batch,
        "sourceNeighborhood": row.get("summaryJson"),
        "target": owner_batch.get("target"),
        "signature": {
            "ownerBase": owner_hex,
            "coordPointer": coord_pointer,
            "coordPointerSlotOffset": "0x0",
            "ownerModuleFields": fields,
        },
        "rootSearch": {},
        "blockers": blockers or ["candidate-only-ref-storage-not-promoted-owner-root"],
        "warnings": warnings,
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "x64dbgAttached": False,
            "debuggerAttached": False,
            "noCheatEngine": True,
            "providerWrites": False,
            "proofPromoted": False,
            "candidateOnly": True,
        },
        "next": {
            "recommendedAction": "Use only as a current-PID module-hint seed for read-only sweeps; do not promote.",
        },
    }


def build_markdown(packet: Mapping[str, Any], *, seed_path: Path) -> str:
    signature = safe_mapping(packet.get("signature"))
    lines = [
        "# Post-update root-signature seed",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Generated UTC: `{packet.get('generatedAtUtc')}`",
        f"- Seed JSON: `{seed_path}`",
        f"- Owner base: `{signature.get('ownerBase')}`",
        f"- Coord pointer: `{signature.get('coordPointer')}`",
        f"- Owner module fields: `{len(safe_list(signature.get('ownerModuleFields')))}`",
        "",
        "## Safety",
        "",
        "Candidate-only artifact generation from an owner-batch summary. No live input, movement, debugger/CE, process-memory reads, target-memory writes, provider writes, or proof promotion.",
    ]
    if packet.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in safe_list(packet.get("blockers")))
    if packet.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{warning}`" for warning in safe_list(packet.get("warnings")))
    return "\n".join(lines).rstrip() + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    owner_batch_path = args.from_owner_batch_summary.resolve()
    owner_batch = load_json_object(owner_batch_path)
    packet = build_seed_packet(
        owner_batch,
        source_owner_batch=str(owner_batch_path),
        explicit_owner=args.owner,
    )
    target = safe_mapping(owner_batch.get("target"))
    pid = parse_int(target.get("pid"))
    run_dir = (
        args.output_root.resolve()
        if args.output_root
        else repo_root
        / "scripts"
        / "captures"
        / f"postupdate-root-signature-seed-currentpid-{pid or 'unknown'}-{utc_stamp()}"
    )
    seed_json = run_dir / "root-signature-seed.json"
    summary_md = run_dir / "summary.md"
    packet["artifacts"] = {
        "runDirectory": str(run_dir),
        "seedJson": str(seed_json),
        "summaryMarkdown": str(summary_md),
    }
    write_json(seed_json, packet)
    write_text_atomic(summary_md, build_markdown(packet, seed_path=seed_json))
    return packet


def self_test() -> dict[str, Any]:
    owner_batch = {
        "target": {"pid": 1234, "hwndHex": "0xC0DE"},
        "rankedRows": [
            {
                "owner": "0x2000",
                "sourceTarget": "0x5000",
                "summaryJson": "owner-neighborhood.json",
                "exactTargetCounts": {"0x5000": 1},
            }
        ],
        "moduleRvaHints": [
            {
                "rva": "0x26E5E80",
                "examples": [
                    {"owner": "0x2000", "storageAddress": "0x2020", "offsetFromOwner": "0x20", "value": "0x700026E5E80"}
                ],
            },
            {
                "rva": "0x26E3200",
                "examples": [
                    {"owner": "0x2000", "storageAddress": "0x1FE0", "offsetFromOwner": "-0x20", "value": "0x700026E3200"}
                ],
            },
            {
                "rva": "0x26E5278",
                "examples": [
                    {"owner": "0x2000", "storageAddress": "0x1DC0", "offsetFromOwner": "-0x240", "value": "0x700026E5278"}
                ],
            },
        ],
    }
    packet = build_seed_packet(owner_batch, source_owner_batch="synthetic.json")
    passed = (
        packet["status"] == "candidate-only"
        and safe_mapping(packet["signature"]).get("ownerBase") == "0x2000"
        and len(safe_list(safe_mapping(packet["signature"]).get("ownerModuleFields"))) == 3
    )
    return {"status": "passed" if passed else "failed", "packet": packet}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a candidate-only post-update root-signature seed from an owner-batch summary.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--from-owner-batch-summary", type=Path, required=False)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--owner", default=None)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        result = self_test()
        if args.json:
            print(json.dumps({"status": result["status"]}, separators=(",", ":")))
        else:
            print(result["status"])
        return 0 if result["status"] == "passed" else 1
    if not args.from_owner_batch_summary:
        raise SystemExit("--from-owner-batch-summary is required unless --self-test is used")
    packet = run(args)
    if args.json:
        signature = safe_mapping(packet.get("signature"))
        print(
            json.dumps(
                {
                    "status": packet.get("status"),
                    "seedJson": safe_mapping(packet.get("artifacts")).get("seedJson"),
                    "summaryMarkdown": safe_mapping(packet.get("artifacts")).get("summaryMarkdown"),
                    "ownerBase": signature.get("ownerBase"),
                    "coordPointer": signature.get("coordPointer"),
                    "ownerModuleFieldCount": len(safe_list(signature.get("ownerModuleFields"))),
                    "blockers": packet.get("blockers"),
                    "warnings": packet.get("warnings"),
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={packet.get('status')}")
        print(f"seedJson={safe_mapping(packet.get('artifacts')).get('seedJson')}")
    return 2 if packet.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
