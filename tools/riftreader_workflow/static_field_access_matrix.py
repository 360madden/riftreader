#!/usr/bin/env python3
"""Build a fast offline field-access matrix for RiftReader owner offsets.

This is the quick static-analysis layer below Ghidra: scan executable PE
sections with Capstone, find instructions that touch known owner-relative
displacements, group them by coarse linear function windows, and rank offsets
by static evidence before any live proof is attempted.

The helper never opens or reads a live RIFT process. It reads only an offline
binary from disk and writes ignored capture artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from .common import find_repo_root, repo_rel, safety_flags, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, repo_rel, safety_flags, utc_iso


SCHEMA_VERSION = 1
TOOL_VERSION = "riftreader-static-field-access-matrix-v0.1.0"
DEFAULT_BINARY_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe"),
    Path(r"C:\Program Files\Glyph\Games\RIFT\Live\rift_x64.exe"),
)
DEFAULT_ROOT_RVA = 0x32EBC80
DEFAULT_OFFSETS = (
    0x300,
    0x304,
    0x308,
    0x30C,
    0x310,
    0x314,
    0x320,
    0x324,
    0x328,
    0x408,
    0x438,
    0x43C,
    0x440,
)
PROMOTED_COORD_OFFSETS = {0x320, 0x324, 0x328}
PROMOTED_FACING_OFFSETS = {0x30C, 0x310, 0x314}
PROMOTED_OFFSETS = PROMOTED_COORD_OFFSETS | PROMOTED_FACING_OFFSETS
DEFAULT_MAX_HITS_PER_OFFSET = 300
DEFAULT_MAX_ROOT_REFS = 300
DEFAULT_CONTEXT_BYTES = 24
DEFAULT_CHUNK_BYTES = 0x40000
DEFAULT_MAX_INSTRUCTIONS = 200_000


@dataclass(frozen=True)
class SectionBlob:
    name: str
    rva: int
    va: int
    data: bytes
    executable: bool


@dataclass(frozen=True)
class RvaWindow:
    center: int
    radius: int

    @property
    def start(self) -> int:
        return max(0, self.center - self.radius)

    @property
    def end(self) -> int:
        return self.center + self.radius


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def parse_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    text = str(value).strip()
    return int(text, 0)


def hex_int(value: int | None) -> str | None:
    if value is None:
        return None
    return f"0x{value:X}"


def first_existing_binary() -> Path | None:
    for path in DEFAULT_BINARY_CANDIDATES:
        if path.is_file():
            return path
    return None


def field_role(offset: int) -> str:
    if offset in PROMOTED_COORD_OFFSETS:
        return "promoted-coordinate"
    if offset in PROMOTED_FACING_OFFSETS:
        return "promoted-facing-yaw"
    if offset == 0x300:
        return "candidate-heading-support"
    if offset == 0x304:
        return "candidate-yaw-adjacent-not-active-turn-rate"
    if offset == 0x308:
        return "candidate-rotation-support"
    if offset == 0x408:
        return "candidate-timer-or-animation-support"
    return "candidate-owner-support"


def semantic_tags(mnemonic: str) -> list[str]:
    m = mnemonic.lower()
    tags: list[str] = []
    if m in {"movss", "movsd"}:
        tags.extend(["scalar-float", "move"])
    elif m in {"addss", "subss", "mulss", "divss", "sqrtss", "minss", "maxss"}:
        tags.extend(["scalar-float", "arithmetic"])
    elif m in {"comiss", "ucomiss"}:
        tags.extend(["scalar-float", "compare"])
    elif m in {"cvtsi2ss", "cvttss2si", "cvtss2sd", "cvtsd2ss"}:
        tags.extend(["scalar-float", "conversion"])
    elif m.startswith("movap") or m.startswith("movup"):
        tags.extend(["packed-float", "move"])
    elif m in {"cmp", "test"}:
        tags.append("integer-compare")
    elif m == "lea":
        tags.append("address-compute")
    elif m.startswith("j"):
        tags.append("branch")
    return tags


def access_label(access_bits: int) -> str:
    try:
        from capstone import CS_AC_READ, CS_AC_WRITE
    except Exception:  # pragma: no cover - import failure handled in caller.
        return "unknown"
    reads = bool(access_bits & CS_AC_READ)
    writes = bool(access_bits & CS_AC_WRITE)
    if reads and writes:
        return "read-write"
    if writes:
        return "write"
    if reads:
        return "read"
    return "unknown"


def executable_sections(pe: Any, *, include_all_sections: bool = False) -> list[SectionBlob]:
    sections: list[SectionBlob] = []
    image_base = int(pe.OPTIONAL_HEADER.ImageBase)
    for section in pe.sections:
        name = section.Name.rstrip(b"\x00").decode("ascii", errors="replace")
        characteristics = int(section.Characteristics)
        executable = bool(characteristics & 0x20000000)
        if not executable and not include_all_sections:
            continue
        data = section.get_data()
        if not data:
            continue
        rva = int(section.VirtualAddress)
        sections.append(
            SectionBlob(
                name=name,
                rva=rva,
                va=image_base + rva,
                data=data,
                executable=executable,
            )
        )
    return sections


def apply_rva_windows(section: SectionBlob, windows: list[RvaWindow]) -> list[SectionBlob]:
    if not windows:
        return [section]
    result: list[SectionBlob] = []
    section_start = section.rva
    section_end = section.rva + len(section.data)
    for index, window in enumerate(windows):
        start = max(section_start, window.start)
        end = min(section_end, window.end)
        if start >= end:
            continue
        offset = start - section.rva
        data = section.data[offset : offset + (end - start)]
        result.append(
            SectionBlob(
                name=f"{section.name}:window{index}",
                rva=start,
                va=section.va + offset,
                data=data,
                executable=section.executable,
            )
        )
    return result


def split_section(section: SectionBlob, chunk_bytes: int) -> list[SectionBlob]:
    if chunk_bytes <= 0 or len(section.data) <= chunk_bytes:
        return [section]
    chunks: list[SectionBlob] = []
    for index, start in enumerate(range(0, len(section.data), chunk_bytes)):
        data = section.data[start : start + chunk_bytes]
        chunks.append(
            SectionBlob(
                name=f"{section.name}:chunk{index}",
                rva=section.rva + start,
                va=section.va + start,
                data=data,
                executable=section.executable,
            )
        )
    return chunks


def byte_window(section: SectionBlob, address: int, size: int, context_bytes: int) -> str:
    start = max(0, address - section.va - context_bytes)
    end = min(len(section.data), address - section.va + size + context_bytes)
    return section.data[start:end].hex(" ").upper()


def memory_target_absolute(insn: Any, operand: Any) -> int | None:
    mem = operand.mem
    base_name = insn.reg_name(mem.base).lower() if mem.base else ""
    if base_name == "rip":
        return int(insn.address) + int(insn.size) + int(mem.disp)
    return None


def operand_memory_hits(
    *,
    insn: Any,
    section: SectionBlob,
    image_base: int,
    offsets: set[int],
    context_bytes: int,
    include_stack_base: bool,
) -> Iterable[dict[str, Any]]:
    from capstone.x86_const import X86_OP_MEM

    for index, operand in enumerate(insn.operands):
        if operand.type != X86_OP_MEM:
            continue
        displacement = int(operand.mem.disp)
        if displacement not in offsets:
            continue
        base_reg = insn.reg_name(operand.mem.base) if operand.mem.base else None
        if not include_stack_base and base_reg and base_reg.lower() in {"rsp", "esp"}:
            continue
        index_reg = insn.reg_name(operand.mem.index) if operand.mem.index else None
        yield {
            "offset": hex_int(displacement),
            "offsetInt": displacement,
            "role": field_role(displacement),
            "address": hex_int(int(insn.address)),
            "rva": hex_int(int(insn.address) - image_base),
            "section": section.name,
            "mnemonic": insn.mnemonic,
            "opStr": insn.op_str,
            "instruction": f"{insn.mnemonic} {insn.op_str}".strip(),
            "bytes": bytes(insn.bytes).hex(" ").upper(),
            "byteWindow": byte_window(section, int(insn.address), int(insn.size), context_bytes),
            "operandIndex": index,
            "operandAccess": access_label(int(getattr(operand, "access", 0) or 0)),
            "baseReg": base_reg,
            "indexReg": index_reg,
            "scale": int(operand.mem.scale),
            "displacement": hex_int(displacement),
            "semanticTags": semantic_tags(str(insn.mnemonic)),
        }


def root_reference_hit(*, insn: Any, image_base: int, root_va: int, root_rva: int) -> dict[str, Any] | None:
    from capstone.x86_const import X86_OP_IMM, X86_OP_MEM

    reasons: list[str] = []
    for operand in insn.operands:
        if operand.type == X86_OP_MEM and memory_target_absolute(insn, operand) == root_va:
            reasons.append("rip-relative-memory-target")
        elif operand.type == X86_OP_IMM and int(operand.imm) in {root_va, root_rva}:
            reasons.append("immediate-root-address-or-rva")
    if not reasons:
        return None
    return {
        "address": hex_int(int(insn.address)),
        "rva": hex_int(int(insn.address) - image_base),
        "mnemonic": insn.mnemonic,
        "opStr": insn.op_str,
        "instruction": f"{insn.mnemonic} {insn.op_str}".strip(),
        "bytes": bytes(insn.bytes).hex(" ").upper(),
        "reasons": reasons,
    }


def scan_binary(
    binary_path: Path,
    *,
    offsets: set[int],
    root_rva: int,
    include_all_sections: bool = False,
    max_hits_per_offset: int = DEFAULT_MAX_HITS_PER_OFFSET,
    max_root_refs: int = DEFAULT_MAX_ROOT_REFS,
    context_bytes: int = DEFAULT_CONTEXT_BYTES,
    rva_windows: list[RvaWindow] | None = None,
    include_stack_base: bool = False,
    max_instructions: int | None = None,
    chunk_bytes: int = DEFAULT_CHUNK_BYTES,
) -> dict[str, Any]:
    try:
        import capstone
        import pefile
    except ImportError as exc:
        return {
            "status": "blocked",
            "blockers": [f"dependency-missing:{exc.name}"],
            "errors": [],
        }

    pe = pefile.PE(str(binary_path), fast_load=True)
    image_base = int(pe.OPTIONAL_HEADER.ImageBase)
    root_va = image_base + root_rva
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    md.skipdata = True

    offset_hits: dict[int, list[dict[str, Any]]] = {offset: [] for offset in offsets}
    root_refs: list[dict[str, Any]] = []
    instructions_scanned = 0
    section_summaries: list[dict[str, Any]] = []
    function_start_by_section: dict[str, int] = {}
    seen_hit_keys: set[tuple[int, int, int]] = set()
    seen_root_ref_addresses: set[int] = set()

    rva_windows = rva_windows or []
    hit_limit_reached = False
    max_instruction_limit_reached = False
    for parent_section in executable_sections(pe, include_all_sections=include_all_sections):
        for bounded_section in apply_rva_windows(parent_section, rva_windows):
            for section in split_section(bounded_section, chunk_bytes):
                current_linear_function_start = section.va
                section_instruction_count = 0
                try:
                    instruction_iterable = md.disasm(section.data, section.va)
                except Exception:
                    instruction_iterable = []
                for insn in instruction_iterable:
                    instructions_scanned += 1
                    section_instruction_count += 1
                    if max_instructions is not None and instructions_scanned >= max_instructions:
                        max_instruction_limit_reached = True
                        break
                    mnemonic = str(insn.mnemonic).lower()
                    if mnemonic == ".byte":
                        continue
                    if mnemonic.startswith("ret") or mnemonic in {"int3", "ud2"}:
                        current_linear_function_start = int(insn.address) + int(insn.size)
                        continue
                    for hit in operand_memory_hits(
                        insn=insn,
                        section=section,
                        image_base=image_base,
                        offsets=offsets,
                        context_bytes=context_bytes,
                        include_stack_base=include_stack_base,
                    ):
                        offset_int = int(hit["offsetInt"])
                        hit_key = (int(insn.address), offset_int, int(hit["operandIndex"]))
                        if hit_key in seen_hit_keys or len(offset_hits[offset_int]) >= max_hits_per_offset:
                            continue
                        seen_hit_keys.add(hit_key)
                        hit["linearFunctionStart"] = hex_int(current_linear_function_start)
                        hit["linearFunctionStartRva"] = hex_int(current_linear_function_start - image_base)
                        offset_hits[offset_int].append(hit)
                    if len(root_refs) < max_root_refs:
                        root_ref = root_reference_hit(
                            insn=insn,
                            image_base=image_base,
                            root_va=root_va,
                            root_rva=root_rva,
                        )
                        if root_ref:
                            address = int(insn.address)
                            if address not in seen_root_ref_addresses:
                                seen_root_ref_addresses.add(address)
                                root_ref["section"] = section.name
                                root_ref["linearFunctionStart"] = hex_int(current_linear_function_start)
                                root_ref["linearFunctionStartRva"] = hex_int(current_linear_function_start - image_base)
                                root_refs.append(root_ref)
                    if all(len(hits) >= max_hits_per_offset for hits in offset_hits.values()) and len(root_refs) >= max_root_refs:
                        hit_limit_reached = True
                        break
                section_summaries.append(
                    {
                        "name": section.name,
                        "rva": hex_int(section.rva),
                        "va": hex_int(section.va),
                        "sizeBytes": len(section.data),
                        "executable": section.executable,
                        "instructionsScanned": section_instruction_count,
                    }
                )
                function_start_by_section[section.name] = current_linear_function_start
                if hit_limit_reached or max_instruction_limit_reached:
                    break
            if hit_limit_reached or max_instruction_limit_reached:
                break
        if hit_limit_reached or max_instruction_limit_reached:
            break

    return {
        "status": "passed",
        "binary": str(binary_path),
        "imageBase": hex_int(image_base),
        "rootRva": hex_int(root_rva),
        "rootAddress": hex_int(root_va),
        "sections": section_summaries,
        "instructionsScanned": instructions_scanned,
        "rootReferences": root_refs,
        "offsetHits": {hex_int(offset): hits for offset, hits in sorted(offset_hits.items())},
        "scanLimits": {
            "rvaWindows": [
                {"center": hex_int(window.center), "radius": hex_int(window.radius), "start": hex_int(window.start), "end": hex_int(window.end)}
                for window in rva_windows
            ],
            "includeStackBase": include_stack_base,
            "maxInstructions": max_instructions,
            "chunkBytes": chunk_bytes,
            "hitLimitReached": hit_limit_reached,
            "maxInstructionLimitReached": max_instruction_limit_reached,
        },
    }


def summarize_offsets(offset_hits: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    function_offsets: dict[str, set[int]] = defaultdict(set)
    function_hits: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for key, hits in offset_hits.items():
        if not isinstance(hits, list):
            continue
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            function_key = str(hit.get("linearFunctionStartRva") or hit.get("linearFunctionStart") or "unknown")
            offset_int = int(hit.get("offsetInt") or parse_int(key))
            function_offsets[function_key].add(offset_int)
            function_hits[function_key].append(hit)

    promoted_cluster_functions = {
        function_key
        for function_key, touched in function_offsets.items()
        if touched & PROMOTED_OFFSETS
    }

    for key, hits_value in offset_hits.items():
        hits = hits_value if isinstance(hits_value, list) else []
        offset_int = parse_int(key)
        functions = {
            str(hit.get("linearFunctionStartRva") or hit.get("linearFunctionStart") or "unknown")
            for hit in hits
            if isinstance(hit, dict)
        }
        operand_accesses = [str(hit.get("operandAccess") or "unknown") for hit in hits if isinstance(hit, dict)]
        tags = [
            str(tag)
            for hit in hits
            if isinstance(hit, dict)
            for tag in (hit.get("semanticTags") if isinstance(hit.get("semanticTags"), list) else [])
        ]
        same_promoted = sorted(functions & promoted_cluster_functions)
        write_count = sum(1 for item in operand_accesses if "write" in item)
        read_count = sum(1 for item in operand_accesses if "read" in item)
        compare_count = sum(1 for item in tags if item == "compare")
        arithmetic_count = sum(1 for item in tags if item == "arithmetic")
        scalar_float_count = sum(1 for item in tags if item == "scalar-float")
        score = 0
        if hits:
            score += min(len(hits), 20)
        score += min(len(functions), 10) * 3
        if same_promoted:
            score += min(len(same_promoted), 5) * 8
        if write_count:
            score += 18
        if read_count:
            score += 6
        if scalar_float_count:
            score += 8
        if arithmetic_count:
            score += 8
        if compare_count:
            score += 4
        if offset_int in PROMOTED_OFFSETS:
            score += 50
        if not hits:
            score -= 30
        if hits and not write_count and offset_int not in PROMOTED_OFFSETS:
            score -= 10
        if offset_int == 0x304:
            score -= 25
        if offset_int == 0x408:
            score -= 10

        if offset_int in PROMOTED_OFFSETS:
            readiness = "already-promoted-static-anchor"
        elif score >= 55:
            readiness = "candidate-static-evidence-strong-needs-runtime-proof"
        elif score >= 30:
            readiness = "candidate-static-evidence-moderate"
        elif hits:
            readiness = "candidate-static-evidence-weak"
        else:
            readiness = "blocked-no-static-field-access-hit"

        rows.append(
            {
                "offset": hex_int(offset_int),
                "role": field_role(offset_int),
                "score": score,
                "readiness": readiness,
                "hitCount": len(hits),
                "functionCount": len(functions),
                "samePromotedClusterFunctionCount": len(same_promoted),
                "samePromotedClusterFunctions": same_promoted[:12],
                "readCount": read_count,
                "writeCount": write_count,
                "scalarFloatCount": scalar_float_count,
                "arithmeticCount": arithmetic_count,
                "compareCount": compare_count,
                "firstHits": hits[:8],
                "candidateOnly": offset_int not in PROMOTED_OFFSETS,
                "promotionPerformed": False,
            }
        )
    return sorted(rows, key=lambda row: (-int(row.get("score") or 0), str(row.get("offset"))))


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# RiftReader Static Field Access Matrix",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Binary: `{summary.get('binary')}`",
        f"- Image base: `{summary.get('imageBase')}`",
        f"- Root RVA: `{summary.get('rootRva')}`",
        f"- Instructions scanned: `{summary.get('instructionsScanned')}`",
        f"- Root refs captured: `{len(summary.get('rootReferences') or [])}`",
        "",
        "## Ranked offsets",
        "",
        "| Offset | Role | Score | Readiness | Hits | Functions | Same-promoted clusters | R/W | Float ops |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary.get("rankedOffsets") or []:
        lines.append(
            "| {offset} | {role} | {score} | {readiness} | {hitCount} | {functionCount} | "
            "{samePromotedClusterFunctionCount} | {readCount}/{writeCount} | {scalarFloatCount} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "Offline binary scan only. No live input, target process memory access, x64dbg, Cheat Engine, provider writes, Git mutation, or proof/current-truth promotion.",
            "",
            "## Notes",
            "",
            "- Function grouping is a fast linear heuristic, not a Ghidra/decompiler proof.",
            "- Use this matrix to choose what deeper Ghidra/xref/decompiler analysis should inspect next.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_summary(
    repo_root: Path,
    *,
    binary_path: Path,
    offsets: set[int],
    root_rva: int,
    include_all_sections: bool,
    max_hits_per_offset: int,
    max_root_refs: int,
    context_bytes: int,
    rva_windows: list[RvaWindow],
    include_stack_base: bool,
    max_instructions: int | None,
    chunk_bytes: int,
    output_root: Path | None,
) -> dict[str, Any]:
    generated_at = utc_iso()
    artifact_root = output_root or repo_root / "scripts" / "captures" / f"static-field-access-matrix-{stamp()}"
    started = time.monotonic()
    blockers: list[str] = []
    if not binary_path.is_file():
        blockers.append("offline-binary-missing")
    if blockers:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-static-field-access-matrix",
            "toolVersion": TOOL_VERSION,
            "generatedAtUtc": generated_at,
            "status": "blocked",
            "blockers": blockers,
            "errors": [],
            "repoRoot": str(repo_root),
            "binary": str(binary_path),
            "safety": {
                **safety_flags(),
                "offlineOnly": True,
                "x64dbgAttach": False,
                "targetMemoryBytesRead": False,
                "targetMemoryBytesWritten": False,
                "proofPromotion": False,
            },
        }

    scan = scan_binary(
        binary_path,
        offsets=offsets,
        root_rva=root_rva,
        include_all_sections=include_all_sections,
        max_hits_per_offset=max_hits_per_offset,
        max_root_refs=max_root_refs,
        context_bytes=context_bytes,
        rva_windows=rva_windows,
        include_stack_base=include_stack_base,
        max_instructions=max_instructions,
        chunk_bytes=chunk_bytes,
    )
    if scan.get("status") != "passed":
        return {
            **scan,
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-static-field-access-matrix",
            "toolVersion": TOOL_VERSION,
            "generatedAtUtc": generated_at,
            "repoRoot": str(repo_root),
            "safety": {
                **safety_flags(),
                "offlineOnly": True,
                "x64dbgAttach": False,
                "targetMemoryBytesRead": False,
                "targetMemoryBytesWritten": False,
                "proofPromotion": False,
            },
        }

    ranked_offsets = summarize_offsets(scan.get("offsetHits") if isinstance(scan.get("offsetHits"), dict) else {})
    scan_limits = scan.get("scanLimits") if isinstance(scan.get("scanLimits"), dict) else {}
    warnings = [
        "fast-linear-disassembly-function-boundaries-are-heuristic",
        "candidate-only-no-proof-or-current-truth-promotion",
    ]
    recommended_actions = [
        "Use this matrix before live offset probes.",
        "Generate masked signatures for top clustered functions.",
        "Keep unpromoted offsets candidate-only until read/write semantics and runtime gates pass.",
    ]
    if scan_limits.get("maxInstructionLimitReached"):
        limit = scan_limits.get("maxInstructions")
        warnings.append(f"scan-instruction-limit-reached:{limit}")
        recommended_actions.insert(
            1,
            "Rerun with --full-scan or tighter --rva-window before treating absent hits as blockers.",
        )

    summary = {
        **scan,
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-static-field-access-matrix",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": generated_at,
        "repoRoot": str(repo_root),
        "status": "passed",
        "blockers": [],
        "warnings": warnings,
        "rankedOffsets": ranked_offsets,
        "next": {
            "recommendedAction": "Inspect top unpromoted same-promoted-cluster functions in Ghidra/decompiler, then require runtime proof gates before promotion.",
            "recommendedActions": recommended_actions,
        },
        "performance": {
            "durationSeconds": round(time.monotonic() - started, 3),
        },
        "safety": {
            **safety_flags(),
            "offlineOnly": True,
            "x64dbgAttach": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
        },
    }
    artifact_root.mkdir(parents=True, exist_ok=True)
    summary_path = artifact_root / "summary.json"
    markdown_path = artifact_root / "summary.md"
    summary["summaryJson"] = repo_rel(repo_root, summary_path)
    summary["summaryMarkdown"] = repo_rel(repo_root, markdown_path)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(build_markdown(summary), encoding="utf-8")
    return summary


def build_self_test() -> dict[str, Any]:
    fake_hits = {
        "0x300": [
            {
                "offsetInt": 0x300,
                "operandAccess": "read",
                "semanticTags": ["scalar-float", "compare"],
                "linearFunctionStartRva": "0x1000",
            }
        ],
        "0x320": [
            {
                "offsetInt": 0x320,
                "operandAccess": "read-write",
                "semanticTags": ["scalar-float", "move"],
                "linearFunctionStartRva": "0x1000",
            }
        ],
    }
    ranked = summarize_offsets(fake_hits)
    by_offset = {row["offset"]: row for row in ranked}
    checks = [
        {"name": "semantic-tags-movss", "pass": "scalar-float" in semantic_tags("movss")},
        {"name": "semantic-tags-comiss", "pass": "compare" in semantic_tags("comiss")},
        {"name": "promoted-offset-scores-above-candidate", "pass": by_offset["0x320"]["score"] > by_offset["0x300"]["score"]},
        {
            "name": "same-promoted-cluster-counts-candidate",
            "pass": by_offset["0x300"]["samePromotedClusterFunctionCount"] == 1,
        },
        {"name": "default-max-instructions-bounded", "pass": DEFAULT_MAX_INSTRUCTIONS == 200_000},
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-static-field-access-matrix-self-test",
        "toolVersion": TOOL_VERSION,
        "status": "passed" if all(item["pass"] for item in checks) else "failed",
        "checks": checks,
        "safety": {
            **safety_flags(),
            "offlineOnly": True,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
        },
    }


def parse_offsets(values: list[str] | None) -> set[int]:
    if not values:
        return set(DEFAULT_OFFSETS)
    offsets: set[int] = set()
    for value in values:
        for part in str(value).split(","):
            text = part.strip()
            if text:
                offsets.add(parse_int(text))
    return offsets


def parse_rva_windows(values: list[str] | None) -> list[RvaWindow]:
    windows: list[RvaWindow] = []
    if not values:
        return windows
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        if ":" in text:
            center_text, radius_text = text.split(":", 1)
            center = parse_int(center_text)
            radius = parse_int(radius_text)
        else:
            center = parse_int(text)
            radius = 0x800
        windows.append(RvaWindow(center=center, radius=radius))
    return windows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--binary-path", type=Path)
    parser.add_argument("--root-rva", default=hex_int(DEFAULT_ROOT_RVA))
    parser.add_argument("--offset", action="append", help="Owner-relative field offset. May be repeated or comma-separated.")
    parser.add_argument("--include-all-sections", action="store_true")
    parser.add_argument("--include-stack-base", action="store_true", help="Include RSP/ESP-based frame references; default excludes stack noise.")
    parser.add_argument("--rva-window", action="append", help="Restrict scan to RVA center:radius, e.g. 0x57A453:0x800. May be repeated.")
    parser.add_argument(
        "--max-instructions",
        type=int,
        default=DEFAULT_MAX_INSTRUCTIONS,
        help=(
            "Bound the quick default scan. Use --full-scan for complete coverage, "
            "or combine this with --rva-window for focused inspection."
        ),
    )
    parser.add_argument("--full-scan", action="store_true", help="Disable the default quick instruction limit.")
    parser.add_argument("--chunk-bytes", type=lambda value: int(str(value), 0), default=DEFAULT_CHUNK_BYTES)
    parser.add_argument("--max-hits-per-offset", type=int, default=DEFAULT_MAX_HITS_PER_OFFSET)
    parser.add_argument("--max-root-refs", type=int, default=DEFAULT_MAX_ROOT_REFS)
    parser.add_argument("--context-bytes", type=int, default=DEFAULT_CONTEXT_BYTES)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        payload = build_self_test()
    else:
        repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root(Path.cwd())
        binary = args.binary_path or first_existing_binary()
        if binary is None:
            binary = DEFAULT_BINARY_CANDIDATES[0]
        payload = build_summary(
            repo_root,
            binary_path=binary.resolve(),
            offsets=parse_offsets(args.offset),
            root_rva=parse_int(args.root_rva),
            include_all_sections=bool(args.include_all_sections),
            max_hits_per_offset=max(1, int(args.max_hits_per_offset)),
            max_root_refs=max(0, int(args.max_root_refs)),
            context_bytes=max(0, int(args.context_bytes)),
            rva_windows=parse_rva_windows(args.rva_window),
            include_stack_base=bool(args.include_stack_base),
            max_instructions=None if args.full_scan else (max(1, int(args.max_instructions)) if args.max_instructions else None),
            chunk_bytes=max(0x1000, int(args.chunk_bytes)),
            output_root=args.output_root.resolve() if args.output_root else None,
        )

    if args.json or args.self_test:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(build_markdown(payload), end="")
    if payload.get("status") in {"blocked", "blocked-safe"}:
        return 2
    return 0 if payload.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
