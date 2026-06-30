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
DEFAULT_BREADCRUMB_FUNCTION_BYTES = 0x180
DEFAULT_ROOT_SAMPLE_BYTES = 0x930
DEFAULT_GLOBAL_SAMPLE_BYTES = 0x1000
DEFAULT_CHILD_SAMPLE_BYTES = 0x800
DEFAULT_MODULE_SIZE = rediscovery.DEFAULT_MODULE_SIZE
WORLD_SCAN_STRIDE = 4
GLOBAL_COORDINATE_LEAD_CLASSIFICATIONS = {
    "direct-coordinate-pointer-global-needs-proof",
    "global-object-world-coordinate-hit-needs-proof",
    "global-object-points-to-coordinate-candidate",
    "global-container-child-coordinate-lead",
}


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


def capstone_memory_access_label(access_bits: int) -> str:
    try:
        from capstone import CS_AC_READ, CS_AC_WRITE
    except ImportError:  # pragma: no cover - caller imports capstone first.
        return "unknown"
    if access_bits & CS_AC_WRITE and access_bits & CS_AC_READ:
        return "read-write"
    if access_bits & CS_AC_WRITE:
        return "write"
    if access_bits & CS_AC_READ:
        return "read"
    return "unknown"


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
                access = capstone_memory_access_label(int(getattr(operands[0], "access", 0) or 0))
                if access == "unknown":
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


def unique_breadcrumb_function_rvas(call_breadcrumbs: Sequence[Mapping[str, Any]], *, limit: int) -> list[int]:
    values: list[int] = []
    seen: set[int] = set()
    for crumb in call_breadcrumbs:
        target = parse_int(safe_mapping(crumb).get("targetRva"))
        if target is not None and target not in seen:
            seen.add(target)
            values.append(target)
        for caller in safe_list(safe_mapping(crumb).get("directCallSites")):
            function_rva = parse_int(safe_mapping(caller).get("containingFunctionStartRva"))
            if function_rva is not None and function_rva not in seen:
                seen.add(function_rva)
                values.append(function_rva)
        if len(values) >= limit:
            break
    return values[:limit]


def summarize_function_window(
    *,
    image_base: int,
    sections: Sequence[SectionBlob],
    function_rva: int,
    function_bytes: int,
    max_rows: int = 48,
) -> dict[str, Any]:
    """Summarize one breadcrumb function without requiring Ghidra."""

    try:
        import capstone
        from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_OP_REG, X86_REG_RIP
    except ImportError as exc:  # pragma: no cover - environment-specific.
        return {"status": "blocked", "functionRva": hex_int(function_rva), "blockers": [f"dependency-missing:{exc.name}"]}

    data = read_section_bytes(sections, function_rva, function_bytes)
    if not data:
        return {"status": "blocked", "functionRva": hex_int(function_rva), "blockers": ["function-rva-not-in-executable-section"]}

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    this_registers = {"rcx"}
    rip_accesses: list[dict[str, Any]] = []
    this_field_accesses: list[dict[str, Any]] = []
    direct_calls: list[dict[str, Any]] = []
    instruction_count = 0

    for insn in md.disasm(data, image_base + function_rva):
        rva = int(insn.address) - image_base
        if rva != function_rva and str(insn.mnemonic).lower() == "int3":
            break
        instruction_count += 1
        mnemonic = str(insn.mnemonic).lower()
        operands = list(insn.operands)
        instruction = f"{insn.mnemonic} {insn.op_str}".strip()

        if mnemonic == "mov" and len(operands) == 2 and operands[0].type == X86_OP_REG and operands[1].type == X86_OP_REG:
            dst = insn.reg_name(operands[0].reg).lower()
            src = insn.reg_name(operands[1].reg).lower()
            if src in this_registers:
                this_registers.add(dst)

        if mnemonic == "call" and operands and operands[0].type == X86_OP_IMM and len(direct_calls) < max_rows:
            direct_calls.append({"rva": hex_int(rva), "targetRva": hex_int(int(operands[0].imm) - image_base), "instruction": instruction})

        for index, operand in enumerate(operands):
            if operand.type != X86_OP_MEM:
                continue
            access = capstone_memory_access_label(int(getattr(operand, "access", 0) or 0))
            mem = operand.mem
            base_reg = insn.reg_name(mem.base).lower() if mem.base else ""
            displacement = int(mem.disp)
            if mem.base == X86_REG_RIP and len(rip_accesses) < max_rows:
                rip_accesses.append(
                    {
                        "rva": hex_int(rva),
                        "globalRva": hex_int(rva + int(insn.size) + displacement),
                        "access": access,
                        "operandIndex": index,
                        "instruction": instruction,
                    }
                )
            elif base_reg in this_registers and displacement and len(this_field_accesses) < max_rows:
                this_field_accesses.append(
                    {
                        "rva": hex_int(rva),
                        "offset": hex_int(displacement),
                        "baseReg": base_reg,
                        "access": access,
                        "instruction": instruction,
                    }
                )

    return {
        "status": "passed",
        "functionRva": hex_int(function_rva),
        "instructionCount": instruction_count,
        "thisRegisters": sorted(this_registers),
        "ripRelativeAccesses": rip_accesses,
        "thisFieldAccesses": this_field_accesses,
        "directCalls": direct_calls,
        "candidateOnly": True,
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


def qword_hits(data: bytes, target_value: int, *, limit: int = 16) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for offset in range(0, max(0, len(data) - 8 + 1), 8):
        value = int.from_bytes(data[offset : offset + 8], "little", signed=False)
        if value == target_value:
            hits.append({"offset": hex_int(offset), "value": hex_int(value)})
            if len(hits) >= limit:
                break
    return hits


def plausible_pointer(value: int, module_base: int, module_size: int) -> bool:
    if value < 0x10000:
        return False
    if module_base <= value < module_base + module_size:
        return False
    # User-mode canonical x64 pointers normally have high bits either clear or
    # sign-extended.  Reject obvious packed/text/scalar noise without assuming a
    # specific heap range.
    return value < 0x0000800000000000


def child_pointer_samples(
    *,
    handle: int,
    data: bytes,
    module_base: int,
    module_size: int,
    reference: Mapping[str, float] | None,
    coordinate_candidate: int | None,
    child_sample_bytes: int,
    tolerance: float,
    max_child_pointers: int,
) -> list[dict[str, Any]]:
    from scan_current_pid_coordinate_family import read_memory  # noqa: E402

    samples: list[dict[str, Any]] = []
    seen: set[int] = set()
    for offset in range(0, max(0, len(data) - 8 + 1), 8):
        value = int.from_bytes(data[offset : offset + 8], "little", signed=False)
        if value in seen or not plausible_pointer(value, module_base, module_size):
            continue
        seen.add(value)
        child_data = read_memory(handle, value, child_sample_bytes)
        if child_data is None:
            continue
        world_hits = near_world_triples(child_data, reference, tolerance=tolerance, limit=4)
        coordinate_pointer_hits = qword_hits(child_data, coordinate_candidate, limit=4) if coordinate_candidate is not None else []
        if not world_hits and not coordinate_pointer_hits:
            continue
        samples.append(
            {
                "parentOffset": hex_int(offset),
                "childPointer": hex_int(value),
                "nearWorldTriples": world_hits,
                "coordinatePointerHits": coordinate_pointer_hits,
            }
        )
        if len(samples) >= max_child_pointers:
            break
    return samples


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


def is_rip_relative_global_slot_access(access: Mapping[str, Any]) -> bool:
    instruction = str(access.get("instruction") or "").strip().lower()
    if not instruction:
        return False
    # ``lea reg, [rip+...]`` computes a module address constant.  It is not a
    # qword global slot; reading the pointed-to module bytes as a heap pointer
    # just creates noisy string/code interpretations.
    if instruction.startswith("lea "):
        return False
    return "ptr [rip" in instruction


def collect_breadcrumb_global_rvas(
    constructor: Mapping[str, Any],
    function_summaries: Sequence[Mapping[str, Any]],
    *,
    max_globals: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()

    for root in safe_list(safe_mapping(constructor).get("candidateGlobalRoots")):
        item = safe_mapping(root)
        global_rva = parse_int(item.get("globalRva"))
        if global_rva is None or global_rva in seen:
            continue
        seen.add(global_rva)
        rows.append(
            {
                "globalRva": hex_int(global_rva),
                "source": "constructor-candidate-global-root",
                "sourceFunctionRva": safe_mapping(constructor).get("functionRva"),
                "sourceInstructionRva": item.get("rva"),
                "instruction": item.get("instruction"),
                "access": item.get("access"),
            }
        )

    for function in function_summaries:
        function_map = safe_mapping(function)
        for access in safe_list(function_map.get("ripRelativeAccesses")):
            item = safe_mapping(access)
            if not is_rip_relative_global_slot_access(item):
                continue
            global_rva = parse_int(item.get("globalRva"))
            if global_rva is None or global_rva in seen:
                continue
            seen.add(global_rva)
            rows.append(
                {
                    "globalRva": hex_int(global_rva),
                    "source": "breadcrumb-rip-relative-access",
                    "sourceFunctionRva": function_map.get("functionRva"),
                    "sourceInstructionRva": item.get("rva"),
                    "instruction": item.get("instruction"),
                    "access": item.get("access"),
                }
            )
            if len(rows) >= max_globals:
                return rows
    return rows[:max_globals]


def classify_global_container_sample(
    *,
    global_rva: int,
    global_value: int | None,
    data: bytes | None,
    module_base: int,
    module_size: int,
    reference: Mapping[str, float] | None,
    coordinate_candidate: int | None,
    child_samples: Sequence[Mapping[str, Any]],
    tolerance: float,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "globalRva": hex_int(global_rva),
        "globalValue": hex_int(global_value),
        "readable": data is not None,
        "classification": "global-null-or-scalar",
        "candidateOnly": True,
        "promotionEligible": False,
        "reasons": [],
    }
    if not global_value:
        result["reasons"].append("global-qword-null-or-unreadable")
        return result
    if coordinate_candidate is not None and global_value == coordinate_candidate:
        result["classification"] = "direct-coordinate-pointer-global-needs-proof"
        result["reasons"].append("global-qword-equals-coordinate-candidate")
        return result
    if data is None:
        result["classification"] = "global-pointer-unreadable"
        result["reasons"].append("global-qword-target-unreadable")
        return result

    vtable = int.from_bytes(data[0:8], "little", signed=False) if len(data) >= 8 else None
    vtable_rva = vtable - module_base if vtable is not None and module_base <= vtable < module_base + module_size else None
    world_hits = near_world_triples(data, reference, tolerance=tolerance)
    coordinate_pointer_hits = qword_hits(data, coordinate_candidate) if coordinate_candidate is not None else []
    result.update(
        {
            "vtable": hex_int(vtable),
            "vtableRva": hex_int(vtable_rva),
            "nearWorldTriples": world_hits,
            "coordinatePointerHits": coordinate_pointer_hits,
            "childPointerSamples": [dict(item) for item in child_samples],
        }
    )
    if world_hits:
        result["classification"] = "global-object-world-coordinate-hit-needs-proof"
        result["reasons"].append("world-coordinate-like-triple-found-in-global-object")
    elif coordinate_pointer_hits:
        result["classification"] = "global-object-points-to-coordinate-candidate"
        result["reasons"].append("coordinate-candidate-pointer-found-in-global-object")
    elif child_samples:
        result["classification"] = "global-container-child-coordinate-lead"
        result["reasons"].append("child-pointer-near-coordinate-or-coordinate-pointer-hit")
    elif vtable_rva is not None:
        result["classification"] = "module-vtable-global-container-no-coordinate"
        result["reasons"].append("module-vtable-readable-no-coordinate-lead")
    else:
        result["classification"] = "heap-global-container-no-coordinate"
        result["reasons"].append("heap-readable-no-coordinate-lead")
    return result


def live_breadcrumb_global_samples(
    *,
    target: Mapping[str, Any],
    globals_to_sample: Sequence[Mapping[str, Any]],
    reference: Mapping[str, float] | None,
    coordinate_candidate: int | None,
    sample_bytes: int,
    child_sample_bytes: int,
    tolerance: float,
    module_size: int,
    max_child_pointers: int,
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
        "liveBreadcrumbGlobalRead": False,
    }
    if pid is None or not hwnd or module_base is None:
        blockers.append("target-fields-missing-for-live-breadcrumb-global-read")
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
            if not rediscovery.process_start_matches(actual_start, expected_start):
                blockers.append("process-start-mismatch")
                return live_target, [], blockers, warnings
        samples: list[dict[str, Any]] = []
        for item in globals_to_sample:
            row = safe_mapping(item)
            global_rva = parse_int(row.get("globalRva"))
            if global_rva is None:
                continue
            slot = int(module_base) + global_rva
            slot_bytes = read_memory(handle, slot, 8)
            global_value = int.from_bytes(slot_bytes, "little", signed=False) if slot_bytes else None
            data = read_memory(handle, global_value, sample_bytes) if global_value and plausible_pointer(global_value, int(module_base), module_size) else None
            children = (
                child_pointer_samples(
                    handle=handle,
                    data=data,
                    module_base=int(module_base),
                    module_size=module_size,
                    reference=reference,
                    coordinate_candidate=coordinate_candidate,
                    child_sample_bytes=child_sample_bytes,
                    tolerance=tolerance,
                    max_child_pointers=max_child_pointers,
                )
                if data is not None and max_child_pointers > 0
                else []
            )
            sample = classify_global_container_sample(
                global_rva=global_rva,
                global_value=global_value,
                data=data,
                module_base=int(module_base),
                module_size=module_size,
                reference=reference,
                coordinate_candidate=coordinate_candidate,
                child_samples=children,
                tolerance=tolerance,
            )
            sample.update(
                {
                    "globalSlotAddress": hex_int(slot),
                    "source": row.get("source"),
                    "sourceFunctionRva": row.get("sourceFunctionRva"),
                    "sourceInstructionRva": row.get("sourceInstructionRva"),
                    "sourceInstruction": row.get("instruction"),
                    "sourceAccess": row.get("access"),
                }
            )
            samples.append(sample)
        live_target["liveBreadcrumbGlobalRead"] = True
        return live_target, samples, blockers, warnings
    finally:
        close_handle(handle)


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
            if not rediscovery.process_start_matches(actual_start, expected_start):
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
    candidate_target = rediscovery.target_fields_from_readback(candidate_readback)
    merged = {**static_target, **candidate_target}
    if not merged.get("moduleBase"):
        merged["moduleBase"] = safe_mapping(safe_mapping(candidate_readback.get("target")).get("processDetails")).get("moduleBaseAddressHex")
    return merged


def target_with_overrides(
    target: Mapping[str, Any],
    *,
    pid: Any = None,
    hwnd: Any = None,
    module_base: Any = None,
    expected_process_start_utc: Any = None,
) -> dict[str, Any]:
    merged = dict(target)
    if pid not in (None, ""):
        merged["pid"] = parse_int(pid) or pid
    if hwnd not in (None, ""):
        merged["hwnd"] = hwnd
    if module_base not in (None, ""):
        merged["moduleBase"] = module_base
    if expected_process_start_utc not in (None, ""):
        merged["expectedProcessStartUtc"] = expected_process_start_utc
    return merged


def build_markdown(summary: Mapping[str, Any]) -> str:
    constructor = safe_mapping(summary.get("constructorEvidence"))
    live_samples = [safe_mapping(item) for item in safe_list(summary.get("liveRootSamples"))]
    breadcrumb_global_samples = [safe_mapping(item) for item in safe_list(summary.get("breadcrumbGlobalSamples"))]
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
    function_summaries = [safe_mapping(item) for item in safe_list(summary.get("breadcrumbFunctionSummaries"))]
    if function_summaries:
        lines.extend(
            [
                "",
                "## Breadcrumb function RIP-relative globals",
                "",
                "| Function RVA | Global RVA | Access | Instruction |",
                "|---|---|---|---|",
            ]
        )
        row_count = 0
        for function in function_summaries:
            for access in safe_list(function.get("ripRelativeAccesses")):
                item = safe_mapping(access)
                lines.append(
                    f"| `{function.get('functionRva')}` | `{item.get('globalRva')}` | `{item.get('access')}` | `{item.get('instruction')}` |"
                )
                row_count += 1
                if row_count >= 20:
                    break
            if row_count >= 20:
                break
    if breadcrumb_global_samples:
        lines.extend(
            [
                "",
                "## Breadcrumb global live samples",
                "",
                "| Global RVA | Source function | Live pointer | Classification | Reasons |",
                "|---|---|---|---|---|",
            ]
        )
        for sample in breadcrumb_global_samples[:20]:
            reasons = "; ".join(str(reason) for reason in safe_list(sample.get("reasons")))
            lines.append(
                f"| `{sample.get('globalRva')}` | `{sample.get('sourceFunctionRva')}` | `{sample.get('globalValue')}` | "
                f"`{sample.get('classification')}` | {reasons} |"
            )
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
    breadcrumb_function_summaries = []
    if not args.no_function_summaries and call_breadcrumbs and not blockers:
        breadcrumb_function_summaries = [
            summarize_function_window(
                image_base=image_base,
                sections=sections,
                function_rva=function_rva,
                function_bytes=int(args.breadcrumb_function_bytes, 0),
            )
            for function_rva in unique_breadcrumb_function_rvas(call_breadcrumbs, limit=int(args.max_function_summaries))
        ]
    breadcrumb_globals_to_sample = (
        collect_breadcrumb_global_rvas(
            constructor,
            breadcrumb_function_summaries,
            max_globals=int(args.max_breadcrumb_globals),
        )
        if not blockers
        else []
    )

    candidate_readback = load_json_object(candidate_path)
    static_readback = load_json_object(static_readback_path)
    reference = reference_from_candidate(candidate_readback)
    coordinate_candidate = parse_int(args.coordinate_candidate_address) or rediscovery.candidate_address_from_readback(candidate_readback)
    target = target_with_overrides(
        target_from_artifacts(static_readback, candidate_readback),
        pid=args.pid,
        hwnd=args.hwnd,
        module_base=args.module_base,
        expected_process_start_utc=args.expected_process_start_utc,
    )

    candidate_global_roots = [safe_mapping(item) for item in safe_list(constructor.get("candidateGlobalRoots"))]
    root_rvas = [parse_int(item.get("globalRva")) for item in candidate_global_roots]
    root_rvas = [value for value in root_rvas if value is not None]
    live_target: dict[str, Any] = {"liveRootRead": False}
    live_samples: list[dict[str, Any]] = []
    breadcrumb_global_target: dict[str, Any] = {"liveBreadcrumbGlobalRead": False}
    breadcrumb_global_samples: list[dict[str, Any]] = []
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

    if args.artifact_only:
        warnings.append("artifact-only-breadcrumb-global-read-skipped")
    elif breadcrumb_globals_to_sample and not any(blocker in blockers for blocker in ("pid-hwnd-mismatch", "process-start-mismatch")):
        (
            breadcrumb_global_target,
            breadcrumb_global_samples,
            breadcrumb_blockers,
            breadcrumb_warnings,
        ) = live_breadcrumb_global_samples(
            target=target,
            globals_to_sample=breadcrumb_globals_to_sample,
            reference=reference,
            coordinate_candidate=coordinate_candidate,
            sample_bytes=int(args.global_sample_bytes, 0),
            child_sample_bytes=int(args.child_sample_bytes, 0),
            tolerance=float(args.world_tolerance),
            module_size=int(args.module_size, 0),
            max_child_pointers=int(args.max_child_pointers),
        )
        blockers.extend(breadcrumb_blockers)
        warnings.extend(breadcrumb_warnings)
    elif not breadcrumb_globals_to_sample and not blockers:
        warnings.append("breadcrumb-rip-relative-globals-missing")

    classifications = {str(item.get("classification")) for item in live_samples}
    breadcrumb_classifications = {str(item.get("classification")) for item in breadcrumb_global_samples}
    if "candidate-position-root-needs-proof" in classifications:
        verdict = "static-access-chain-found-position-root-candidate-needs-proof"
        status = "candidate"
        recommended = (
            "Run no-input candidate readback against the static root candidate, then request explicit approval for movement/restart proof before any promotion."
        )
    elif breadcrumb_classifications & GLOBAL_COORDINATE_LEAD_CLASSIFICATIONS:
        verdict = "static-global-container-coordinate-lead-needs-proof"
        status = "candidate"
        recommended = (
            "Treat the breadcrumb global/container hit as candidate-only. Run exact-target no-input readback against the listed global/child pointer lead, "
            "then request explicit approval for movement/restart proof before promotion."
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
    target_memory_read = bool(live_target.get("liveRootRead")) or bool(breadcrumb_global_target.get("liveBreadcrumbGlobalRead"))
    safety.update(
        {
            "offlineOnly": True,
            "targetMemoryBytesRead": target_memory_read,
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "currentTruthUpdate": False,
            "candidateOnly": True,
        }
    )
    target_summary = dict(target)
    if live_target.get("liveRootRead"):
        target_summary.update(live_target)
    if breadcrumb_global_target.get("liveBreadcrumbGlobalRead"):
        target_summary.update(breadcrumb_global_target)
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
        "coordinateCandidateAddress": hex_int(coordinate_candidate),
        "target": target_summary,
        "constructorEvidence": constructor,
        "callBreadcrumbs": call_breadcrumbs,
        "breadcrumbFunctionSummaries": breadcrumb_function_summaries,
        "breadcrumbGlobalsToSample": breadcrumb_globals_to_sample,
        "liveRootSamples": live_samples,
        "breadcrumbGlobalSamples": breadcrumb_global_samples,
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

    child_coordinate_hit = classify_global_container_sample(
        global_rva=0x32DD7E8,
        global_value=0x40000000,
        data=b"\x00" * 64,
        module_base=module_base,
        module_size=0x500000,
        reference=reference,
        coordinate_candidate=0x50000000,
        child_samples=[
            {
                "parentOffset": "0x20",
                "childPointer": "0x50000000",
                "nearWorldTriples": [{"offset": "0x0"}],
                "coordinatePointerHits": [],
            }
        ],
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
        {
            "name": "global-container-child-coordinate-lead",
            "pass": child_coordinate_hit["classification"] == "global-container-child-coordinate-lead",
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
        "globalContainerClassification": child_coordinate_hit["classification"],
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
    parser.add_argument("--pid")
    parser.add_argument("--hwnd")
    parser.add_argument("--module-base")
    parser.add_argument("--expected-process-start-utc")
    parser.add_argument("--module-size", default=hex(DEFAULT_MODULE_SIZE))
    parser.add_argument("--root-sample-bytes", default=hex(DEFAULT_ROOT_SAMPLE_BYTES))
    parser.add_argument("--global-sample-bytes", default=hex(DEFAULT_GLOBAL_SAMPLE_BYTES))
    parser.add_argument("--child-sample-bytes", default=hex(DEFAULT_CHILD_SAMPLE_BYTES))
    parser.add_argument("--world-tolerance", type=float, default=1.0)
    parser.add_argument("--coordinate-candidate-address")
    parser.add_argument("--max-call-depth", type=int, default=5)
    parser.add_argument("--max-callers-per-target", type=int, default=8)
    parser.add_argument("--breadcrumb-function-bytes", default=hex(DEFAULT_BREADCRUMB_FUNCTION_BYTES))
    parser.add_argument("--max-function-summaries", type=int, default=20)
    parser.add_argument("--max-breadcrumb-globals", type=int, default=48)
    parser.add_argument("--max-child-pointers", type=int, default=24)
    parser.add_argument("--no-function-summaries", action="store_true")
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
                    "coordinateCandidateAddress": summary.get("coordinateCandidateAddress"),
                    "candidateGlobalRoots": safe_list(safe_mapping(summary.get("constructorEvidence")).get("candidateGlobalRoots")),
                    "breadcrumbFunctionSummaries": safe_list(summary.get("breadcrumbFunctionSummaries"))[:8],
                    "breadcrumbGlobalsToSample": safe_list(summary.get("breadcrumbGlobalsToSample"))[:12],
                    "liveRootSamples": summary.get("liveRootSamples"),
                    "breadcrumbGlobalSamples": safe_list(summary.get("breadcrumbGlobalSamples"))[:12],
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
