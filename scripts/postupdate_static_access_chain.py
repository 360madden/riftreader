#!/usr/bin/env python3
"""Candidate-only post-update static access-chain packet.

This helper turns the current offline constructor/access-cluster evidence into
a durable recovery packet.  It is designed for the post-update lane where the
old promoted static root is null:

- scan the offline ``rift_x64.exe`` for owner-layout constructor evidence;
- identify RIP-relative global stores made by that constructor;
- build direct-call breadcrumbs upward from the constructor;
- optionally read those static roots from the exact current PID/HWND target.

It never sends input, attaches a debugger, writes target memory, updates truth,
or promotes a proof/actor chain.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workflow_common import base_safety, repo_root as default_repo_root, utc_iso, utc_stamp, write_json  # noqa: E402
import postupdate_owner_root_rediscovery as rediscovery  # noqa: E402


SCHEMA_VERSION = 1
TOOL_VERSION = "riftreader-postupdate-static-access-chain-v0.1.0"
DEFAULT_RIFT_LIVE_ROOT = rediscovery.DEFAULT_RIFT_LIVE_ROOT
DEFAULT_BINARY_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe"),
    Path(r"C:\Program Files\Glyph\Games\RIFT\Live\rift_x64.exe"),
)
DEFAULT_FUNCTION_RVA = 0x3F8B0
DEFAULT_FUNCTION_BYTES = 0x700
DEFAULT_ROOT_SAMPLE_BYTES = 0x930
DEFAULT_MODULE_SIZE = rediscovery.DEFAULT_MODULE_SIZE
WORLD_SCAN_STRIDE = 4


@dataclass(frozen=True)
class SectionBlob:
    name: str
    rva: int
    data: bytes
    executable: bool

    @property
    def end_rva(self) -> int:
        return self.rva + len(self.data)


def parse_int(value: Any) -> int | None:
    return rediscovery.parse_int(value)


def hex_int(value: int | None) -> str | None:
    return rediscovery.hex_int(value)


def safe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def first_existing_binary() -> Path | None:
    for path in DEFAULT_BINARY_CANDIDATES:
        if path.is_file():
            return path
    return None


def load_json_object(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return data


def latest_path(capture_root: Path, pattern: str) -> Path | None:
    matches = [path for path in capture_root.glob(pattern) if path.is_file()]
    return max(matches, key=lambda path: path.stat().st_mtime) if matches else None


def latest_artifact_paths(repo_root: Path) -> dict[str, str | None]:
    capture_root = repo_root / "scripts" / "captures"
    patterns = {
        "candidateReadback": "candidate-readback-currentpid-*/candidate-readback-summary.json",
        "staticReadback": "static-owner-coordinate-chain-readback-*/summary.json",
        "staticFieldMatrix": "static-field-access-matrix-*/summary.json",
    }
    return {
        key: str(path.resolve()) if (path := latest_path(capture_root, pattern)) else None
        for key, pattern in patterns.items()
    }


def executable_sections(binary_path: Path) -> tuple[int, list[SectionBlob], list[str]]:
    try:
        import pefile
    except ImportError as exc:  # pragma: no cover - environment-specific.
        return 0, [], [f"dependency-missing:{exc.name}"]

    pe = pefile.PE(str(binary_path), fast_load=True)
    image_base = int(pe.OPTIONAL_HEADER.ImageBase)
    sections: list[SectionBlob] = []
    for section in pe.sections:
        characteristics = int(section.Characteristics)
        executable = bool(characteristics & 0x20000000)
        data = section.get_data()
        if not executable or not data:
            continue
        name = section.Name.rstrip(b"\x00").decode("ascii", errors="replace")
        sections.append(SectionBlob(name=name, rva=int(section.VirtualAddress), data=data, executable=executable))
    return image_base, sections, []


def section_for_rva(sections: Sequence[SectionBlob], rva: int) -> SectionBlob | None:
    for section in sections:
        if section.rva <= rva < section.end_rva:
            return section
    return None


def read_section_bytes(sections: Sequence[SectionBlob], rva: int, size: int) -> bytes:
    section = section_for_rva(sections, rva)
    if section is None:
        return b""
    offset = rva - section.rva
    return section.data[offset : offset + max(0, size)]


def direct_call_target_rva(call_rva: int, rel32: int) -> int:
    return call_rva + 5 + rel32


def find_direct_call_sites(sections: Sequence[SectionBlob], target_rva: int, *, max_sites: int = 64) -> list[dict[str, Any]]:
    """Find x86-64 near ``CALL rel32`` sites that target *target_rva*."""

    sites: list[dict[str, Any]] = []
    for section in sections:
        data = section.data
        index = 0
        while True:
            index = data.find(b"\xE8", index)
            if index < 0 or index + 5 > len(data):
                break
            rel32 = struct.unpack_from("<i", data, index + 1)[0]
            call_rva = section.rva + index
            if direct_call_target_rva(call_rva, rel32) == target_rva:
                function_start = find_function_start_by_int3(section, call_rva)
                sites.append(
                    {
                        "callRva": hex_int(call_rva),
                        "targetRva": hex_int(target_rva),
                        "containingFunctionStartRva": hex_int(function_start),
                        "section": section.name,
                    }
                )
                if len(sites) >= max_sites:
                    return sites
            index += 1
    return sites


def find_function_start_by_int3(section: SectionBlob, rva: int) -> int:
    """Approximate a function start by walking back to an INT3 padding run."""

    offset = max(0, min(len(section.data), rva - section.rva))
    for index in range(offset, max(0, offset - 0x8000), -1):
        if index >= 4 and section.data[index - 4 : index] == b"\xCC\xCC\xCC\xCC":
            start = index
            while start < len(section.data) and section.data[start] == 0xCC:
                start += 1
            return section.rva + start
    return section.rva + offset


def build_call_breadcrumbs(
    sections: Sequence[SectionBlob],
    *,
    start_rva: int,
    max_depth: int,
    max_sites_per_target: int,
) -> list[dict[str, Any]]:
    """Walk direct callers upward from a constructor target."""

    breadcrumbs: list[dict[str, Any]] = []
    current_targets = [start_rva]
    seen_targets = {start_rva}
    for depth in range(max_depth + 1):
        next_targets: list[int] = []
        for target in current_targets:
            callers = find_direct_call_sites(sections, target, max_sites=max_sites_per_target)
            breadcrumbs.append({"depth": depth, "targetRva": hex_int(target), "directCallSites": callers})
            for caller in callers:
                function_rva = parse_int(caller.get("containingFunctionStartRva"))
                if function_rva is not None and function_rva not in seen_targets:
                    seen_targets.add(function_rva)
                    next_targets.append(function_rva)
        current_targets = next_targets[:max_sites_per_target]
        if not current_targets:
            break
    return breadcrumbs


def disassemble_constructor(
    *,
    image_base: int,
    sections: Sequence[SectionBlob],
    function_rva: int,
    function_bytes: int,
    owner_offsets: set[int],
) -> dict[str, Any]:
    try:
        import capstone
        from capstone import CS_AC_READ, CS_AC_WRITE
        from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_OP_REG, X86_REG_RIP
    except ImportError as exc:  # pragma: no cover - environment-specific.
        return {"status": "blocked", "blockers": [f"dependency-missing:{exc.name}"]}

    data = read_section_bytes(sections, function_rva, function_bytes)
    if not data:
        return {"status": "blocked", "blockers": ["function-rva-not-in-executable-section"]}

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    this_registers = {"rcx"}
    field_writes: list[dict[str, Any]] = []
    global_accesses: list[dict[str, Any]] = []
    vtable_stores: list[dict[str, Any]] = []
    instruction_count = 0

    for insn in md.disasm(data, image_base + function_rva):
        instruction_count += 1
        rva = int(insn.address) - image_base
        mnemonic = str(insn.mnemonic).lower()
        operands = list(insn.operands)

        # Track simple this-pointer aliases, e.g. mov rdi, rcx.
        if mnemonic == "mov" and len(operands) == 2 and operands[0].type == X86_OP_REG and operands[1].type == X86_OP_REG:
            dst = insn.reg_name(operands[0].reg).lower()
            src = insn.reg_name(operands[1].reg).lower()
            if src in this_registers:
                this_registers.add(dst)

        if len(operands) >= 2 and operands[0].type == X86_OP_MEM:
            mem = operands[0].mem
            base_reg = insn.reg_name(mem.base).lower() if mem.base else ""
            displacement = int(mem.disp)
            if base_reg in this_registers and displacement in owner_offsets:
                field_writes.append(
                    {
                        "rva": hex_int(rva),
                        "offset": hex_int(displacement),
                        "baseReg": base_reg,
                        "instruction": f"{insn.mnemonic} {insn.op_str}".strip(),
                    }
                )
            if base_reg in this_registers and displacement == 0 and operands[1].type == X86_OP_REG:
                vtable_stores.append(
                    {
                        "rva": hex_int(rva),
                        "baseReg": base_reg,
                        "instruction": f"{insn.mnemonic} {insn.op_str}".strip(),
                    }
                )
            if mem.base == X86_REG_RIP:
                global_rva = rva + int(insn.size) + displacement
                access_bits = int(getattr(operands[0], "access", 0) or 0)
                if access_bits & CS_AC_WRITE and access_bits & CS_AC_READ:
                    access = "read-write"
                elif access_bits & CS_AC_WRITE:
                    access = "write"
                elif access_bits & CS_AC_READ:
                    access = "read"
                else:
                    # Capstone does not always mark destination access for all
                    # encodings.  Keep this explicit instead of guessing read.
                    access = "unknown-destination"
                source_reg = None
                if operands[1].type == X86_OP_REG:
                    source_reg = insn.reg_name(operands[1].reg).lower()
                global_accesses.append(
                    {
                        "rva": hex_int(rva),
                        "globalRva": hex_int(global_rva),
                        "access": access,
                        "sourceReg": source_reg,
                        "sourceIsThisAlias": source_reg in this_registers if source_reg else False,
                        "instruction": f"{insn.mnemonic} {insn.op_str}".strip(),
                    }
                )
        elif len(operands) >= 2 and operands[1].type == X86_OP_MEM:
            mem = operands[1].mem
            if mem.base == X86_REG_RIP:
                global_rva = rva + int(insn.size) + int(mem.disp)
                global_accesses.append(
                    {
                        "rva": hex_int(rva),
                        "globalRva": hex_int(global_rva),
                        "access": "read",
                        "sourceReg": None,
                        "sourceIsThisAlias": False,
                        "instruction": f"{insn.mnemonic} {insn.op_str}".strip(),
                    }
                )
        elif any(operand.type == X86_OP_IMM for operand in operands):
            continue

    candidate_global_roots = [
        item
        for item in global_accesses
        if item.get("access") in {"write", "read-write", "unknown-destination"} and item.get("sourceIsThisAlias")
    ]
    return {
        "status": "passed",
        "functionRva": hex_int(function_rva),
        "instructionCount": instruction_count,
        "thisRegisters": sorted(this_registers),
        "fieldWrites": field_writes,
        "fieldWriteCount": len(field_writes),
        "fieldOffsets": sorted({str(item["offset"]) for item in field_writes}, key=lambda value: parse_int(value) or 0),
        "globalAccesses": global_accesses,
        "candidateGlobalRoots": candidate_global_roots,
        "vtableStores": vtable_stores,
        "candidateOnly": True,
        "promotionEligible": False,
    }


def read_vec3_from_bytes(data: bytes, offset: int) -> tuple[float, float, float] | None:
    if offset < 0 or offset + 12 > len(data):
        return None
    try:
        values = struct.unpack_from("<fff", data, offset)
    except struct.error:
        return None
    return values if all(math.isfinite(value) for value in values) else None


def vec3_delta(left: Sequence[float], right: Mapping[str, float]) -> float:
    return max(abs(float(left[index]) - float(right[axis])) for index, axis in enumerate(("x", "y", "z")))


def looks_like_unit_or_matrix_vector(values: Sequence[float] | None) -> bool:
    if values is None:
        return False
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if len(finite) != 3:
        return False
    norm = math.sqrt(sum(value * value for value in finite))
    return 0.5 <= norm <= 1.5 and all(abs(value) <= 2.0 for value in finite)


def near_world_triples(data: bytes, reference: Mapping[str, float] | None, *, tolerance: float, limit: int = 12) -> list[dict[str, Any]]:
    if reference is None:
        return []
    hits: list[dict[str, Any]] = []
    for offset in range(0, max(0, len(data) - 12), WORLD_SCAN_STRIDE):
        vec = read_vec3_from_bytes(data, offset)
        if vec is None:
            continue
        delta = vec3_delta(vec, reference)
        planar = math.hypot(float(vec[0]) - float(reference["x"]), float(vec[2]) - float(reference["z"]))
        if delta <= tolerance or planar <= tolerance:
            hits.append(
                {
                    "offset": hex_int(offset),
                    "value": {"x": vec[0], "y": vec[1], "z": vec[2]},
                    "maxAbsDelta": delta,
                    "planarDelta": planar,
                }
            )
            if len(hits) >= limit:
                break
    return hits


def classify_root_sample(
    *,
    root_rva: int,
    root_pointer: int | None,
    data: bytes | None,
    module_base: int,
    module_size: int,
    reference: Mapping[str, float] | None,
    tolerance: float,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "rootRva": hex_int(root_rva),
        "rootPointer": hex_int(root_pointer),
        "readable": data is not None,
        "classification": "root-null" if not root_pointer else "unreadable",
        "candidateOnly": True,
        "promotionEligible": False,
        "reasons": [],
    }
    if not root_pointer:
        result["reasons"].append("global-root-pointer-null")
        return result
    if data is None:
        result["reasons"].append("root-object-unreadable")
        return result

    vtable = int.from_bytes(data[0:8], "little", signed=False) if len(data) >= 8 else None
    module_end = module_base + module_size
    vtable_rva = vtable - module_base if vtable is not None and module_base <= vtable < module_end else None
    coord_320 = read_vec3_from_bytes(data, 0x320)
    facing_30c = read_vec3_from_bytes(data, 0x30C)
    matrix_300 = read_vec3_from_bytes(data, 0x300)
    world_hits = near_world_triples(data, reference, tolerance=tolerance)
    coord_delta = vec3_delta(coord_320, reference) if coord_320 is not None and reference is not None else None

    result.update(
        {
            "vtable": hex_int(vtable),
            "vtableRva": hex_int(vtable_rva),
            "samples": {
                "owner+0x300": tuple(coord for coord in matrix_300) if matrix_300 is not None else None,
                "owner+0x30C": tuple(coord for coord in facing_30c) if facing_30c is not None else None,
                "owner+0x320": tuple(coord for coord in coord_320) if coord_320 is not None else None,
                "owner+0x320MaxAbsDelta": coord_delta,
            },
            "nearWorldTriples": world_hits,
        }
    )
    if world_hits:
        result["classification"] = "candidate-position-root-needs-proof"
        result["reasons"].append("world-coordinate-like-triple-found")
    elif looks_like_unit_or_matrix_vector(coord_320) or looks_like_unit_or_matrix_vector(matrix_300):
        result["classification"] = "orientation-matrix-root-not-position-root"
        result["reasons"].append("unit-or-matrix-vector-at-promoted-coordinate-offset")
        result["reasons"].append("no-world-coordinate-like-triple-in-root-object")
    elif vtable_rva is not None:
        result["classification"] = "module-vtable-root-nonposition-unclassified"
        result["reasons"].append("module-vtable-root-readable")
    else:
        result["classification"] = "heap-root-nonposition-unclassified"
        result["reasons"].append("root-readable-but-no-module-vtable-or-world-coordinate")
    return result


def live_root_samples(
    *,
    target: Mapping[str, Any],
    root_rvas: Sequence[int],
    reference: Mapping[str, float] | None,
    sample_bytes: int,
    tolerance: float,
    module_size: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str], list[str]]:
    from scan_current_pid_coordinate_family import close_handle, open_process, read_memory, verify_hwnd_owner  # noqa: E402

    blockers: list[str] = []
    warnings: list[str] = []
    pid = parse_int(target.get("pid") or target.get("processId"))
    hwnd = target.get("hwnd") or target.get("targetWindowHandle")
    module_base = parse_int(target.get("moduleBase") or target.get("moduleBaseAddressHex"))
    expected_start = target.get("expectedProcessStartUtc") or target.get("processStartUtc") or target.get("startTimeUtc")
    live_target: dict[str, Any] = {
        "pid": pid,
        "hwnd": hwnd,
        "moduleBase": hex_int(module_base),
        "expectedProcessStartUtc": expected_start,
        "liveRootRead": False,
    }
    if pid is None or not hwnd or module_base is None:
        blockers.append("target-fields-missing-for-live-root-read")
        return live_target, [], blockers, warnings

    hwnd_check = verify_hwnd_owner(str(hwnd), int(pid))
    live_target["hwndCheck"] = hwnd_check
    if not bool(hwnd_check.get("ownerMatchesExpectedPid")):
        blockers.append("pid-hwnd-mismatch")
        return live_target, [], blockers, warnings

    handle = open_process(int(pid))
    try:
        actual_start = rediscovery.get_process_start_utc(handle)
        live_target["actualProcessStartUtc"] = actual_start
        if expected_start and actual_start:
            expected_prefix = str(expected_start).replace("Z", "+00:00")[:19]
            if not actual_start.startswith(expected_prefix):
                blockers.append("process-start-mismatch")
                return live_target, [], blockers, warnings
        samples: list[dict[str, Any]] = []
        for root_rva in root_rvas:
            root_slot = int(module_base) + int(root_rva)
            root_bytes = read_memory(handle, root_slot, 8)
            root_pointer = int.from_bytes(root_bytes, "little", signed=False) if root_bytes else None
            data = read_memory(handle, root_pointer, sample_bytes) if root_pointer else None
            sample = classify_root_sample(
                root_rva=int(root_rva),
                root_pointer=root_pointer,
                data=data,
                module_base=int(module_base),
                module_size=module_size,
                reference=reference,
                tolerance=tolerance,
            )
            sample["rootSlotAddress"] = hex_int(root_slot)
            samples.append(sample)
        live_target["liveRootRead"] = True
        return live_target, samples, blockers, warnings
    finally:
        close_handle(handle)


def reference_from_candidate(candidate_readback: Mapping[str, Any]) -> dict[str, float] | None:
    return rediscovery.reference_from_readback(candidate_readback)


def target_from_artifacts(static_readback: Mapping[str, Any], candidate_readback: Mapping[str, Any]) -> dict[str, Any]:
    static_target = safe_mapping(static_readback.get("target"))
    candidate_target = {
        "pid": candidate_readback.get("processId") or candidate_readback.get("pid"),
        "hwnd": candidate_readback.get("targetWindowHandle") or candidate_readback.get("hwnd"),
    }
    merged = {**candidate_target, **static_target}
    if not merged.get("moduleBase"):
        merged["moduleBase"] = safe_mapping(safe_mapping(candidate_readback.get("target")).get("processDetails")).get("moduleBaseAddressHex")
    return merged


def build_markdown(summary: Mapping[str, Any]) -> str:
    constructor = safe_mapping(summary.get("constructorEvidence"))
    live_samples = [safe_mapping(item) for item in safe_list(summary.get("liveRootSamples"))]
    lines = [
        "# Post-update static access-chain packet",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Binary: `{summary.get('binary')}`",
        f"- Game manifest version: `{safe_mapping(summary.get('gameEpoch')).get('manifestVersion')}`",
        "",
        "## Constructor evidence",
        "",
        f"- Function RVA: `{constructor.get('functionRva')}`",
        f"- Field write count: `{constructor.get('fieldWriteCount')}`",
        f"- Field offsets: `{', '.join(safe_list(constructor.get('fieldOffsets')))}`",
        "",
        "| Root RVA | Static instruction | Live pointer | Classification | Reasons |",
        "|---|---|---|---|---|",
    ]
    samples_by_root = {str(item.get("rootRva")): item for item in live_samples}
    for root in safe_list(constructor.get("candidateGlobalRoots")):
        item = safe_mapping(root)
        sample = samples_by_root.get(str(item.get("globalRva")), {})
        reasons = "; ".join(str(reason) for reason in safe_list(sample.get("reasons")))
        lines.append(
            f"| `{item.get('globalRva')}` | `{item.get('instruction')}` | `{sample.get('rootPointer')}` | "
            f"`{sample.get('classification')}` | {reasons} |"
        )
    lines.extend(["", "## Direct-call breadcrumbs", "", "| Depth | Target RVA | Callers |", "|---:|---|---|"])
    for crumb in safe_list(summary.get("callBreadcrumbs")):
        item = safe_mapping(crumb)
        callers = ", ".join(
            f"{safe_mapping(caller).get('callRva')} in {safe_mapping(caller).get('containingFunctionStartRva')}"
            for caller in safe_list(item.get("directCallSites"))
        )
        lines.append(f"| `{item.get('depth')}` | `{item.get('targetRva')}` | `{callers}` |")
    lines.extend(["", "## Blockers"])
    for blocker in safe_list(summary.get("blockers")):
        lines.append(f"- `{blocker}`")
    lines.extend(["", "## Recommended next action"])
    lines.append(str(safe_mapping(summary.get("next")).get("recommendedAction") or ""))
    lines.extend(["", "No input, movement, debugger/CE, truth update, provider write, or promotion was performed."])
    return "\n".join(lines).rstrip() + "\n"


def build_summary(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    repo_root = Path(args.repo_root).resolve() if args.repo_root else default_repo_root()
    binary_path = Path(args.binary_path).resolve() if args.binary_path else first_existing_binary()
    output_root = Path(args.output_root).resolve() if args.output_root else repo_root / "scripts" / "captures"
    output_dir = output_root / f"postupdate-static-access-chain-{utc_stamp()}"
    summary_json = output_dir / "summary.json"
    summary_md = output_dir / "summary.md"
    blockers: list[str] = []
    warnings: list[str] = []

    if binary_path is None or not binary_path.is_file():
        blockers.append("offline-binary-missing")
        binary_path = DEFAULT_BINARY_CANDIDATES[0]

    latest = latest_artifact_paths(repo_root)
    candidate_path = Path(args.candidate_readback_json).resolve() if args.candidate_readback_json else (
        Path(latest["candidateReadback"]) if latest["candidateReadback"] else None
    )
    static_readback_path = Path(args.static_readback_json).resolve() if args.static_readback_json else (
        Path(latest["staticReadback"]) if latest["staticReadback"] else None
    )
    static_matrix_path = Path(args.static_field_matrix_json).resolve() if args.static_field_matrix_json else (
        Path(latest["staticFieldMatrix"]) if latest["staticFieldMatrix"] else None
    )

    image_base = 0
    sections: list[SectionBlob] = []
    if not blockers:
        image_base, sections, section_blockers = executable_sections(binary_path)
        blockers.extend(section_blockers)
        if not sections:
            blockers.append("offline-executable-sections-missing")

    owner_offsets = {parse_int(value) for value in args.owner_offset}
    owner_offsets = {value for value in owner_offsets if value is not None}
    constructor = (
        disassemble_constructor(
            image_base=image_base,
            sections=sections,
            function_rva=int(args.function_rva, 0),
            function_bytes=int(args.function_bytes, 0),
            owner_offsets=owner_offsets,
        )
        if not blockers
        else {"status": "blocked", "blockers": blockers}
    )
    blockers.extend(str(blocker) for blocker in safe_list(constructor.get("blockers")))
    call_breadcrumbs = (
        build_call_breadcrumbs(
            sections,
            start_rva=int(args.function_rva, 0),
            max_depth=int(args.max_call_depth),
            max_sites_per_target=int(args.max_callers_per_target),
        )
        if not blockers
        else []
    )

    candidate_readback = load_json_object(candidate_path)
    static_readback = load_json_object(static_readback_path)
    reference = reference_from_candidate(candidate_readback)
    target = target_from_artifacts(static_readback, candidate_readback)

    candidate_global_roots = [safe_mapping(item) for item in safe_list(constructor.get("candidateGlobalRoots"))]
    root_rvas = [parse_int(item.get("globalRva")) for item in candidate_global_roots]
    root_rvas = [value for value in root_rvas if value is not None]
    live_target: dict[str, Any] = {"liveRootRead": False}
    live_samples: list[dict[str, Any]] = []
    if args.artifact_only:
        warnings.append("artifact-only-live-root-read-skipped")
    elif root_rvas and not blockers:
        live_target, live_samples, live_blockers, live_warnings = live_root_samples(
            target=target,
            root_rvas=root_rvas,
            reference=reference,
            sample_bytes=int(args.root_sample_bytes, 0),
            tolerance=float(args.world_tolerance),
            module_size=int(args.module_size, 0),
        )
        blockers.extend(live_blockers)
        warnings.extend(live_warnings)
    elif not root_rvas and not blockers:
        blockers.append("constructor-global-root-store-missing")

    classifications = {str(item.get("classification")) for item in live_samples}
    if "candidate-position-root-needs-proof" in classifications:
        verdict = "static-access-chain-found-position-root-candidate-needs-proof"
        status = "candidate"
        recommended = (
            "Run no-input candidate readback against the static root candidate, then request explicit approval for movement/restart proof before any promotion."
        )
    elif "orientation-matrix-root-not-position-root" in classifications:
        verdict = "static-access-chain-found-orientation-root-only"
        status = "blocked"
        blockers.append("static-global-root-is-orientation-not-world-position")
        recommended = (
            "Keep rift_x64+0x335F508 as a candidate orientation/facing anchor, but do not use it as position. "
            "Continue offline caller-chain tracing above 0x13A37D0/0x13AFAD0/0x13B5E00 and run read-only pointer-family scans for the higher-level object that owns the current world-coordinate copy."
        )
    elif blockers:
        verdict = "static-access-chain-blocked"
        status = "blocked"
        recommended = "Fix the listed blocked-safe static/access-chain prerequisites, then rerun this helper."
    else:
        verdict = "static-access-chain-candidate-only"
        status = "candidate"
        recommended = "Review candidate global roots and run exact-target no-input readback before any movement/proof gate."

    safety = base_safety()
    safety.update(
        {
            "offlineOnly": True,
            "targetMemoryBytesRead": bool(live_target.get("liveRootRead")),
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "currentTruthUpdate": False,
            "candidateOnly": True,
        }
    )
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-postupdate-static-access-chain",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": verdict,
        "repoRoot": str(repo_root),
        "binary": str(binary_path),
        "imageBase": hex_int(image_base) if image_base else None,
        "gameEpoch": rediscovery.read_game_epoch(Path(args.rift_live_root)),
        "artifactInputs": {
            "candidateReadback": str(candidate_path) if candidate_path else None,
            "staticReadback": str(static_readback_path) if static_readback_path else None,
            "staticFieldMatrix": str(static_matrix_path) if static_matrix_path else None,
        },
        "referenceCoordinate": reference,
        "target": live_target if live_target.get("liveRootRead") else target,
        "constructorEvidence": constructor,
        "callBreadcrumbs": call_breadcrumbs,
        "liveRootSamples": live_samples,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "safety": safety,
        "next": {
            "recommendedAction": recommended,
            "requiresApprovalBefore": [
                "movement/displacement stimulus",
                "x64dbg or Cheat Engine",
                "current-truth update",
                "ProofOnly or proof promotion",
                "actor-chain promotion",
            ],
        },
        "artifacts": {
            "outputDir": str(output_dir.resolve()),
            "summaryJson": str(summary_json.resolve()),
            "summaryMarkdown": str(summary_md.resolve()),
        },
    }
    write_json(summary_json, summary)
    summary_md.parent.mkdir(parents=True, exist_ok=True)
    summary_md.write_text(build_markdown(summary), encoding="utf-8")
    return summary, 2 if status == "blocked" else 0


def self_test() -> dict[str, Any]:
    module_base = 0x700000000000
    reference = {"x": 100.0, "y": 200.0, "z": 300.0}
    position = bytearray(DEFAULT_ROOT_SAMPLE_BYTES)
    position[0:8] = (module_base + 0x1234).to_bytes(8, "little")
    struct.pack_into("<fff", position, 0x320, 100.0, 200.0, 300.0)
    position_result = classify_root_sample(
        root_rva=0x1000,
        root_pointer=0x20000000,
        data=bytes(position),
        module_base=module_base,
        module_size=0x500000,
        reference=reference,
        tolerance=0.25,
    )

    orientation = bytearray(DEFAULT_ROOT_SAMPLE_BYTES)
    orientation[0:8] = (module_base + 0x4321).to_bytes(8, "little")
    struct.pack_into("<fff", orientation, 0x300, 0.0, 0.0, 1.0)
    struct.pack_into("<fff", orientation, 0x320, 0.9, -0.2, 0.1)
    orientation_result = classify_root_sample(
        root_rva=0x2000,
        root_pointer=0x30000000,
        data=bytes(orientation),
        module_base=module_base,
        module_size=0x500000,
        reference=reference,
        tolerance=0.25,
    )

    checks = [
        {
            "name": "direct-call-target-rva",
            "pass": direct_call_target_rva(0x1000, 0x20) == 0x1025,
        },
        {
            "name": "position-root-classification",
            "pass": position_result["classification"] == "candidate-position-root-needs-proof",
        },
        {
            "name": "orientation-root-classification",
            "pass": orientation_result["classification"] == "orientation-matrix-root-not-position-root",
        },
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-postupdate-static-access-chain-self-test",
        "toolVersion": TOOL_VERSION,
        "status": "passed" if all(item["pass"] for item in checks) else "failed",
        "checks": checks,
        "positionClassification": position_result["classification"],
        "orientationClassification": orientation_result["classification"],
        "safety": {**base_safety(), "offlineOnly": True, "targetMemoryBytesRead": False},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a post-update static access-chain packet.")
    parser.add_argument("--repo-root")
    parser.add_argument("--rift-live-root", default=str(DEFAULT_RIFT_LIVE_ROOT))
    parser.add_argument("--binary-path")
    parser.add_argument("--function-rva", default=hex(DEFAULT_FUNCTION_RVA))
    parser.add_argument("--function-bytes", default=hex(DEFAULT_FUNCTION_BYTES))
    parser.add_argument(
        "--owner-offset",
        action="append",
        default=["0x300", "0x304", "0x308", "0x30C", "0x310", "0x314", "0x320", "0x324", "0x328", "0x438", "0x440"],
    )
    parser.add_argument("--candidate-readback-json")
    parser.add_argument("--static-readback-json")
    parser.add_argument("--static-field-matrix-json")
    parser.add_argument("--module-size", default=hex(DEFAULT_MODULE_SIZE))
    parser.add_argument("--root-sample-bytes", default=hex(DEFAULT_ROOT_SAMPLE_BYTES))
    parser.add_argument("--world-tolerance", type=float, default=1.0)
    parser.add_argument("--max-call-depth", type=int, default=5)
    parser.add_argument("--max-callers-per-target", type=int, default=8)
    parser.add_argument("--output-root")
    parser.add_argument("--artifact-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        payload = self_test()
        if args.json:
            print(json.dumps(payload, separators=(",", ":")))
        else:
            print(payload["status"])
        return 0 if payload["status"] == "passed" else 1

    summary, exit_code = build_summary(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary.get("status"),
                    "verdict": summary.get("verdict"),
                    "summaryJson": safe_mapping(summary.get("artifacts")).get("summaryJson"),
                    "gameEpoch": summary.get("gameEpoch"),
                    "candidateGlobalRoots": safe_list(safe_mapping(summary.get("constructorEvidence")).get("candidateGlobalRoots")),
                    "liveRootSamples": summary.get("liveRootSamples"),
                    "blockers": summary.get("blockers"),
                    "warnings": summary.get("warnings"),
                    "next": summary.get("next"),
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"{summary.get('status')}: {safe_mapping(summary.get('artifacts')).get('summaryJson')}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
