from __future__ import annotations

import argparse
import json
import math
import struct
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .current_pid_family_neighborhood_inspector import close_handle, open_process_for_read, read_memory, verify_hwnd_owner
from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1
DEFAULT_COORD_POINTER_OFFSET = 0x10
DEFAULT_INSTANCE_READ_BYTES = 0x130
DEFAULT_TYPE_QWORD_OFFSETS = [0x0, 0x8, 0xE0, 0x110]


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


def parse_labeled_address(value: str) -> dict[str, Any]:
    if ":" in value:
        address_text, label = value.split(":", 1)
    else:
        address_text, label = value, value
    address = parse_int(address_text)
    if address is None:
        raise ValueError(f"invalid address: {value}")
    return {"address": address, "addressHex": int_hex(address), "label": label.strip() or int_hex(address)}


def parse_labeled_addresses(values: Sequence[str]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for value in values:
        parsed = parse_labeled_address(value)
        result[int(parsed["address"])] = parsed
    return result


def unpack_qword(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 8 > len(data):
        return None
    return struct.unpack_from("<Q", data, offset)[0]


def unpack_vec3(data: bytes) -> dict[str, float] | None:
    if len(data) < 12:
        return None
    try:
        x, y, z = struct.unpack_from("<fff", data, 0)
    except struct.error:
        return None
    values = {"x": float(x), "y": float(y), "z": float(z)}
    if not all(math.isfinite(value) for value in values.values()):
        return None
    if max(abs(value) for value in values.values()) > 100000:
        return None
    if max(abs(value) for value in values.values()) < 1:
        return None
    return values


def extract_scan_hit_addresses(scan_doc: Mapping[str, Any], *, max_instances: int | None = None) -> list[int]:
    raw_hits = scan_doc.get("Hits")
    if not isinstance(raw_hits, list):
        return []
    addresses: list[int] = []
    seen: set[int] = set()
    for raw in raw_hits:
        if not isinstance(raw, Mapping):
            continue
        address = parse_int(raw.get("Address") or raw.get("AddressHex"))
        if address is None or address in seen:
            continue
        seen.add(address)
        addresses.append(address)
        if max_instances is not None and len(addresses) >= max_instances:
            break
    return addresses


def inspect_instance_bytes(
    *,
    data: bytes,
    owner_base: int,
    coord_pointer_offset: int,
    type_qword_offsets: Sequence[int],
    candidate_addresses: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    qwords: list[dict[str, Any]] = []
    offsets = sorted(set([coord_pointer_offset, *type_qword_offsets]))
    for offset in offsets:
        value = unpack_qword(data, offset)
        candidate = candidate_addresses.get(value or -1)
        qwords.append(
            {
                "offset": int_hex(offset),
                "address": int_hex(owner_base + offset),
                "value": int_hex(value),
                "candidate": candidate,
            }
        )
    coord_pointer = unpack_qword(data, coord_pointer_offset)
    candidate = candidate_addresses.get(coord_pointer or -1)
    return {
        "ownerBase": int_hex(owner_base),
        "coordPointerOffset": int_hex(coord_pointer_offset),
        "coordPointerStorage": int_hex(owner_base + coord_pointer_offset),
        "coordPointer": int_hex(coord_pointer),
        "coordPointerIsCandidate": candidate is not None,
        "coordPointerCandidate": candidate,
        "qwords": qwords,
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Owner type instance inspector",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated: `{summary.get('generatedAtUtc')}`",
        f"- Instance count: `{summary.get('counts', {}).get('instanceCount')}`",
        f"- Candidate owner count: `{summary.get('counts', {}).get('candidateOwnerCount')}`",
        f"- Coord-like target count: `{summary.get('counts', {}).get('coordLikeTargetCount')}`",
        "",
        "## Candidate-owning instances",
        "",
        "| Owner base | Coord storage | Coord pointer | Candidate | Vec3 |",
        "|---|---|---|---|---|",
    ]
    for instance in summary.get("candidateOwnerInstances", []):
        if not isinstance(instance, Mapping):
            continue
        candidate = instance.get("coordPointerCandidate") if isinstance(instance.get("coordPointerCandidate"), Mapping) else {}
        vec3 = instance.get("coordPointerVec3") if isinstance(instance.get("coordPointerVec3"), Mapping) else None
        vec3_text = "" if not vec3 else f"X={vec3.get('x')} Y={vec3.get('y')} Z={vec3.get('z')}"
        lines.append(
            f"| `{instance.get('ownerBase')}` | `{instance.get('coordPointerStorage')}` | "
            f"`{instance.get('coordPointer')}` | `{candidate.get('label')}` | `{vec3_text}` |"
        )
    lines.extend(
        [
            "",
            "## Low-noise type instances",
            "",
            "| Owner base | Coord pointer | Candidate? | Coord-like? |",
            "|---|---|---:|---:|",
        ]
    )
    for instance in summary.get("instances", [])[:25]:
        if not isinstance(instance, Mapping):
            continue
        lines.append(
            f"| `{instance.get('ownerBase')}` | `{instance.get('coordPointer')}` | "
            f"`{str(instance.get('coordPointerIsCandidate')).lower()}` | "
            f"`{str(bool(instance.get('coordPointerVec3'))).lower()}` |"
        )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in summary.get("blockers", []))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{warning}`" for warning in summary.get("warnings", []))
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This helper is read-only. It reads explicit instance windows and coordinate-pointer targets, sends no input, and does not promote movement truth.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect low-noise owner/type-marker instances for coord-pointer relationships.")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--hwnd", required=True)
    parser.add_argument("--type-scan-json", type=Path, required=True)
    parser.add_argument("--candidate-address", action="append", default=[])
    parser.add_argument("--coord-pointer-offset", type=lambda value: int(value, 0), default=DEFAULT_COORD_POINTER_OFFSET)
    parser.add_argument("--type-qword-offset", action="append", type=lambda value: int(value, 0), default=[])
    parser.add_argument("--instance-read-bytes", type=lambda value: int(value, 0), default=DEFAULT_INSTANCE_READ_BYTES)
    parser.add_argument("--max-instances", type=int, default=64)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = repo_root_from_module()
    run_dir = (
        args.output_root.resolve()
        if args.output_root
        else repo_root / "scripts" / "captures" / f"owner-type-instance-inspector-{utc_stamp()}"
    )
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    blockers: list[str] = []
    warnings: list[str] = []
    target = verify_hwnd_owner(args.hwnd, args.pid)
    if not target.get("isWindow"):
        blockers.append("target-window-not-found")
    if not target.get("ownerMatchesExpectedPid"):
        blockers.append("target-window-pid-mismatch")
    scan_doc = json.loads(args.type_scan_json.read_text(encoding="utf-8-sig"))
    if not isinstance(scan_doc, Mapping):
        blockers.append("type-scan-json-not-object")
        scan_doc = {}
    instance_addresses = extract_scan_hit_addresses(scan_doc, max_instances=args.max_instances)
    if not instance_addresses:
        blockers.append("type-scan-had-no-instance-hits")
    candidate_addresses = parse_labeled_addresses(args.candidate_address)
    type_qword_offsets = args.type_qword_offset or DEFAULT_TYPE_QWORD_OFFSETS
    min_read_bytes = max([args.coord_pointer_offset + 8, *(offset + 8 for offset in type_qword_offsets)])
    instance_read_bytes = max(int(args.instance_read_bytes), min_read_bytes)

    instances: list[dict[str, Any]] = []
    read_started = False
    handle: int | None = None
    if not blockers:
        handle = open_process_for_read(args.pid)
        read_started = True
        try:
            for owner_base in instance_addresses:
                try:
                    data = read_memory(handle, owner_base, instance_read_bytes)
                    instance = inspect_instance_bytes(
                        data=data,
                        owner_base=owner_base,
                        coord_pointer_offset=args.coord_pointer_offset,
                        type_qword_offsets=type_qword_offsets,
                        candidate_addresses=candidate_addresses,
                    )
                    coord_pointer = parse_int(instance.get("coordPointer"))
                    if coord_pointer:
                        try:
                            vec_data = read_memory(handle, coord_pointer, 12)
                            instance["coordPointerVec3"] = unpack_vec3(vec_data)
                        except Exception as exc:  # noqa: BLE001
                            instance["coordPointerVec3"] = None
                            instance["coordPointerReadError"] = f"{type(exc).__name__}:{exc}"
                    instances.append(instance)
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"instance-read-failed:{int_hex(owner_base)}:{type(exc).__name__}:{exc}")
        finally:
            if handle is not None:
                close_handle(handle)

    candidate_instances = [instance for instance in instances if instance.get("coordPointerIsCandidate")]
    coord_like = [instance for instance in instances if instance.get("coordPointerVec3")]
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "owner-type-instance-inspector",
        "generatedAtUtc": utc_iso(),
        "status": "blocked" if blockers else "passed",
        "repoRoot": str(repo_root),
        "target": target,
        "inputs": {
            "typeScanJson": str(args.type_scan_json.resolve()),
            "coordPointerOffset": int_hex(args.coord_pointer_offset),
            "typeQwordOffsets": [int_hex(offset) for offset in type_qword_offsets],
            "instanceReadBytes": instance_read_bytes,
            "maxInstances": args.max_instances,
            "candidateAddresses": list(candidate_addresses.values()),
        },
        "counts": {
            "instanceCount": len(instances),
            "candidateOwnerCount": len(candidate_instances),
            "coordLikeTargetCount": len(coord_like),
        },
        "candidateOwnerInstances": candidate_instances,
        "instances": instances,
        "blockers": blockers,
        "warnings": warnings,
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgLaunched": False,
            "debuggerAttached": False,
            "targetMemoryBytesRead": read_started,
            "targetMemoryBytesWritten": False,
            "providerWrites": False,
            "githubConnectorWrites": False,
            "candidateOnly": True,
            "movementProofEligible": False,
        },
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(summary_json),
            "summaryMarkdown": str(summary_md),
        },
        "next": {
            "recommendedAction": "Use candidate-owning low-noise type instances as source-chain leads only; do not promote until static/root and ProofOnly gates pass.",
        },
    }
    write_json(summary_json, summary)
    write_text_atomic(summary_md, build_markdown(summary))
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = run(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "counts": summary["counts"],
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
                    "candidateOwnerInstances": summary["candidateOwnerInstances"],
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']} summary={summary['artifacts']['summaryJson']}")
    return 0 if summary["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
