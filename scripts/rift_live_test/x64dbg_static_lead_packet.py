from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic
from .x64dbg_snapshot_diff import BLOCKED_OPERATIONS


SCHEMA_VERSION = 1
DEFAULT_PROCESS_NAME = "rift_x64"


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


def load_json(path: Path) -> Mapping[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def load_candidates(candidate_doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = candidate_doc.get("candidates") or candidate_doc.get("Candidates") or []
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def candidate_address(candidate: Mapping[str, Any]) -> int | None:
    for key in ("address", "addressHex", "absoluteAddressHex", "absolute_address_hex"):
        parsed = parse_int(candidate.get(key))
        if parsed is not None:
            return parsed
    return None


def candidate_id(candidate: Mapping[str, Any], index: int) -> str:
    value = candidate.get("candidateId") or candidate.get("id") or candidate.get("candidate_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    address = candidate_address(candidate)
    return f"candidate-{index:03d}-{int_hex(address) if address is not None else 'unknown'}"


def summarize_candidates(candidate_doc: Mapping[str, Any]) -> dict[str, Any]:
    candidates = load_candidates(candidate_doc)
    summarized: list[dict[str, Any]] = []
    family_counts: dict[str, int] = {}
    for index, candidate in enumerate(candidates, start=1):
        address = candidate_address(candidate)
        family_base = candidate.get("familyBaseHex")
        if isinstance(family_base, str) and family_base:
            family_counts[family_base] = family_counts.get(family_base, 0) + 1
        summarized.append(
            {
                "rank": index,
                "candidateId": candidate_id(candidate, index),
                "address": int_hex(address),
                "addressInt": address,
                "familyBase": family_base,
                "rangeLabel": candidate.get("rangeLabel"),
                "trackingErrorMaxAbs": candidate.get("trackingError", {}).get("maxAbs")
                if isinstance(candidate.get("trackingError"), Mapping)
                else None,
                "passiveNoiseByteOverlap": candidate.get("passiveNoiseByteOverlap"),
                "offsetSpreadMaxAbs": candidate.get("offsetSpread", {}).get("maxAbs")
                if isinstance(candidate.get("offsetSpread"), Mapping)
                else None,
            }
        )
    dominant_family = None
    if family_counts:
        dominant_family = sorted(family_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    return {
        "candidateCount": len(summarized),
        "dominantFamilyBase": dominant_family,
        "candidates": summarized,
        "bestCandidate": summarized[0] if summarized else None,
    }


def summarize_readback(readback_doc: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if readback_doc is None:
        return None
    best = readback_doc.get("bestReadback") if isinstance(readback_doc.get("bestReadback"), Mapping) else None
    return {
        "status": readback_doc.get("status"),
        "generatedAtUtc": readback_doc.get("generatedAtUtc"),
        "reference": readback_doc.get("reference"),
        "matchingCandidateCount": readback_doc.get("matchingCandidateCount"),
        "readbackCandidateCount": readback_doc.get("readbackCandidateCount"),
        "best": dict(best) if best else None,
        "summaryJson": readback_doc.get("artifacts", {}).get("summaryJson")
        if isinstance(readback_doc.get("artifacts"), Mapping)
        else None,
    }


MEMORY_EXPR_RE = re.compile(r"\[(?P<expr>[^\]]+)\]")
CONSTANT_RE = re.compile(r"(?P<sign>[+-])\s*(?P<value>0x[0-9a-fA-F]+|\d+)")
REGISTER_RE = re.compile(r"\b([re]?[abcds][xip]?|r(?:[0-9]|1[0-5])[dwb]?|r[sd]i|r[bs]p|rip)\b", re.IGNORECASE)


def parse_memory_reference(op_str: str) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for match in MEMORY_EXPR_RE.finditer(op_str or ""):
        expr = match.group("expr").strip()
        registers = REGISTER_RE.findall(expr)
        constant_offset = 0
        has_constant = False
        for const_match in CONSTANT_RE.finditer(expr):
            value = int(const_match.group("value"), 0)
            if const_match.group("sign") == "-":
                value = -value
            constant_offset += value
            has_constant = True
        refs.append(
            {
                "expression": expr,
                "registers": [register.lower() for register in registers],
                "baseRegister": registers[0].lower() if registers else None,
                "constantOffset": int_hex(constant_offset) if has_constant else None,
                "constantOffsetInt": constant_offset if has_constant else None,
                "hasConstantOffset": has_constant,
            }
        )
    return refs


def extract_code_leads(disasm_doc: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if disasm_doc is None:
        return []
    rows = disasm_doc.get("rows")
    if not isinstance(rows, list):
        return []
    leads: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        instructions = row.get("instructions")
        if not isinstance(instructions, list):
            continue
        hit_instruction = None
        for instruction in instructions:
            if isinstance(instruction, Mapping) and instruction.get("isHitRip") is True:
                hit_instruction = instruction
                break
        if hit_instruction is None:
            continue
        op_str = str(hit_instruction.get("opStr") or "")
        leads.append(
            {
                "sourceLabel": row.get("label"),
                "historicalRip": row.get("historicalRip"),
                "historicalStartRva": row.get("historicalStartRva"),
                "currentStart": row.get("currentStart"),
                "currentHitRip": row.get("currentHitRip"),
                "fullCodeWindowMatch": row.get("fullMatch"),
                "matchingPrefixBytes": row.get("matchingPrefixBytes"),
                "instruction": {
                    "address": hit_instruction.get("address"),
                    "mnemonic": hit_instruction.get("mnemonic"),
                    "opStr": op_str,
                    "text": f"{hit_instruction.get('mnemonic')} {op_str}".strip(),
                },
                "memoryReferences": parse_memory_reference(op_str),
            }
        )
    return leads


def candidate_offset_alignments(candidates: list[dict[str, Any]], code_leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    addresses = [candidate for candidate in candidates if candidate.get("addressInt") is not None]
    alignments: list[dict[str, Any]] = []
    for lead in code_leads:
        for memref in lead.get("memoryReferences") or []:
            offset = memref.get("constantOffsetInt")
            if offset is None:
                continue
            for left in addresses:
                for right in addresses:
                    if left is right:
                        continue
                    left_addr = int(left["addressInt"])
                    right_addr = int(right["addressInt"])
                    if right_addr - left_addr != int(offset):
                        continue
                    alignments.append(
                        {
                            "leadInstruction": lead.get("instruction", {}).get("text"),
                            "leadCurrentHitRip": lead.get("currentHitRip"),
                            "memoryExpression": memref.get("expression"),
                            "constantOffset": memref.get("constantOffset"),
                            "fromCandidate": left.get("address"),
                            "toCandidate": right.get("address"),
                            "fromCandidateId": left.get("candidateId"),
                            "toCandidateId": right.get("candidateId"),
                            "interpretation": "candidate-address-spacing-matches-code-memory-offset; register value was not captured for current PID",
                        }
                    )
    return alignments


def make_safety() -> dict[str, Any]:
    return {
        "offlineOnly": True,
        "movementSent": False,
        "inputSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "providerWrites": False,
        "githubConnectorWrites": False,
        "x64dbgLiveAttachStarted": False,
        "x64dbgCommandsExecuted": False,
        "processAttachOrMemoryReadStarted": False,
        "nativeLiveMemoryReadStarted": False,
        "targetMemoryBytesWritten": False,
        "movementAllowed": False,
        "candidateOnly": True,
        "writeClassOperationsBlocked": True,
        "blockedOperations": list(BLOCKED_OPERATIONS),
    }


def build_work_packet(
    *,
    candidate_doc: Mapping[str, Any],
    readback_doc: Mapping[str, Any] | None,
    rva_check_doc: Mapping[str, Any] | None,
    disasm_doc: Mapping[str, Any] | None,
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    candidate_summary = summarize_candidates(candidate_doc)
    readback = summarize_readback(readback_doc)
    code_leads = extract_code_leads(disasm_doc)
    alignments = candidate_offset_alignments(candidate_summary["candidates"], code_leads)
    warnings: list[str] = []
    blockers = [
        "not-resolved-static-chain",
        "no-current-pid-register-object-pointer",
        "missing-module-rva-root-pointer",
        "not-restart-validated",
        "proofonly-not-passed",
    ]
    if not code_leads:
        blockers.append("no-code-leads")
    if not alignments:
        warnings.append("no-candidate-offset-alignment-found")
    if readback and readback.get("status") != "passed":
        warnings.append("latest-readback-not-passed")
    best_readback = readback.get("best") if readback else None
    if best_readback and best_readback.get("classification") != "offset-corrected-current-coordinate-candidate":
        warnings.append("best-readback-not-offset-corrected-current-coordinate-candidate")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "x64dbg-static-lead-work-packet",
        "generatedAtUtc": utc_iso(),
        "status": "candidate",
        "process": {
            "name": inputs.get("processName") or DEFAULT_PROCESS_NAME,
            "pid": parse_int(inputs.get("targetPid")),
            "hwnd": inputs.get("targetHwnd"),
            "startTimeUtc": inputs.get("processStartTimeUtc"),
            "moduleBase": inputs.get("moduleBase"),
        },
        "candidateFamily": candidate_summary,
        "latestReadback": readback,
        "historicalRvaCheck": {
            "status": rva_check_doc.get("status") if rva_check_doc else None,
            "generatedAtUtc": rva_check_doc.get("generatedAtUtc") if rva_check_doc else None,
            "rows": rva_check_doc.get("rows") if rva_check_doc else [],
        },
        "codeLeads": code_leads,
        "candidateOffsetAlignments": alignments,
        "blockers": blockers,
        "warnings": warnings,
        "safety": make_safety(),
        "next": {
            "recommendedAction": "Use code leads and candidate-offset alignments to search for a module/static-owner root; do not promote until restart and ProofOnly gates pass.",
        },
    }


def markdown_summary(packet: Mapping[str, Any], summary: Mapping[str, Any]) -> str:
    family = packet.get("candidateFamily") if isinstance(packet.get("candidateFamily"), Mapping) else {}
    readback = packet.get("latestReadback") if isinstance(packet.get("latestReadback"), Mapping) else {}
    best = readback.get("best") if isinstance(readback.get("best"), Mapping) else {}
    lines = [
        "# x64dbg static lead work packet",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Generated UTC: `{packet.get('generatedAtUtc')}`",
        f"- Dominant family: `{family.get('dominantFamilyBase')}`",
        f"- Best candidate: `{(family.get('bestCandidate') or {}).get('address') if isinstance(family.get('bestCandidate'), Mapping) else None}`",
        f"- Latest readback status: `{readback.get('status')}`",
        f"- Best readback classification: `{best.get('classification')}`",
        f"- Best offset-corrected delta: `{best.get('offsetCorrectedMaxAbsDelta')}`",
        "",
        "## Code leads",
        "",
        "| Hit RIP | Instruction | Memory refs | Full match |",
        "|---|---|---|---:|",
    ]
    for lead in packet.get("codeLeads") or []:
        refs = ", ".join(f"`{ref.get('expression')}`" for ref in lead.get("memoryReferences") or [])
        lines.append(
            f"| `{lead.get('currentHitRip')}` | `{lead.get('instruction', {}).get('text')}` | {refs} | "
            f"`{lead.get('fullCodeWindowMatch')}` |"
        )
    lines.extend(["", "## Candidate offset alignments", "", "| From | Offset | To | Lead |", "|---|---:|---|---|"])
    for alignment in packet.get("candidateOffsetAlignments") or []:
        lines.append(
            f"| `{alignment.get('fromCandidate')}` | `{alignment.get('constantOffset')}` | "
            f"`{alignment.get('toCandidate')}` | `{alignment.get('leadInstruction')}` |"
        )
    if packet.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in packet["blockers"])
    if packet.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{warning}`" for warning in packet["warnings"])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This packet is offline-only. It does not attach x64dbg, send input,",
            "read target memory, write target memory, or promote movement truth.",
            "",
            "## Artifacts",
            "",
            f"- Summary JSON: `{summary.get('artifacts', {}).get('summaryJson')}`",
            f"- Work packet JSON: `{summary.get('artifacts', {}).get('workPacketJson')}`",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def choose_run_dir(repo_root: Path, output_root: Path | None) -> Path:
    run_dir = output_root.resolve() if output_root else repo_root / "scripts" / "captures" / f"x64dbg-static-lead-packet-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def build_summary(
    *,
    repo_root: Path,
    run_dir: Path,
    args: argparse.Namespace,
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "x64dbg-static-lead-work-packet-summary",
        "generatedAtUtc": utc_iso(),
        "status": packet.get("status"),
        "repoRoot": str(repo_root),
        "inputs": {
            "candidateJson": str(args.candidate_json) if args.candidate_json else None,
            "readbackSummaryJson": str(args.readback_summary_json) if args.readback_summary_json else None,
            "rvaCheckSummaryJson": str(args.rva_check_summary_json) if args.rva_check_summary_json else None,
            "disasmSummaryJson": str(args.disasm_summary_json) if args.disasm_summary_json else None,
        },
        "counts": {
            "candidateCount": packet.get("candidateFamily", {}).get("candidateCount")
            if isinstance(packet.get("candidateFamily"), Mapping)
            else 0,
            "codeLeadCount": len(packet.get("codeLeads") or []),
            "candidateOffsetAlignmentCount": len(packet.get("candidateOffsetAlignments") or []),
        },
        "blockers": packet.get("blockers", []),
        "warnings": packet.get("warnings", []),
        "safety": make_safety(),
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
            "workPacketJson": str(run_dir / "static-lead-work-packet.json"),
        },
        "next": packet.get("next"),
    }


def synthetic_candidate_doc() -> dict[str, Any]:
    return {
        "candidates": [
            {
                "candidateId": "best",
                "addressHex": "0x268DF21ED30",
                "familyBaseHex": "0x268DF200000",
                "trackingError": {"maxAbs": 0.003},
                "passiveNoiseByteOverlap": 0,
            },
            {
                "candidateId": "sibling",
                "addressHex": "0x268DF21ED20",
                "familyBaseHex": "0x268DF200000",
                "trackingError": {"maxAbs": 0.003},
                "passiveNoiseByteOverlap": 0,
            },
        ]
    }


def synthetic_readback_doc() -> dict[str, Any]:
    return {
        "status": "passed",
        "generatedAtUtc": "2026-05-13T19:47:00Z",
        "matchingCandidateCount": 2,
        "readbackCandidateCount": 2,
        "bestReadback": {
            "addressHex": "0x268DF21ED30",
            "classification": "offset-corrected-current-coordinate-candidate",
            "offsetCorrectedMaxAbsDelta": 0.0037,
        },
    }


def synthetic_disasm_doc() -> dict[str, Any]:
    return {
        "rows": [
            {
                "label": "synthetic-hit",
                "historicalRip": "0x7FF7970CC2B5",
                "historicalStartRva": "0x57C2A5",
                "currentStart": "0x7FF71D30C2A5",
                "currentHitRip": "0x7FF71D30C2B5",
                "fullMatch": True,
                "matchingPrefixBytes": 96,
                "instructions": [
                    {
                        "address": "0x7FF71D30C2B5",
                        "isHitRip": True,
                        "mnemonic": "cmp",
                        "opStr": "qword ptr [rcx + 0x10], 0",
                    }
                ],
            }
        ]
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build an offline static-chain work packet from candidate family and stable x64dbg hit-RVA leads.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--candidate-json", type=Path, default=None)
    parser.add_argument("--readback-summary-json", type=Path, default=None)
    parser.add_argument("--rva-check-summary-json", type=Path, default=None)
    parser.add_argument("--disasm-summary-json", type=Path, default=None)
    parser.add_argument("--target-pid", type=int, default=None)
    parser.add_argument("--target-hwnd", default=None)
    parser.add_argument("--process-start-time-utc", default=None)
    parser.add_argument("--module-base", default=None)
    parser.add_argument("--process-name", default=DEFAULT_PROCESS_NAME)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    run_dir = choose_run_dir(repo_root, args.output_root)
    try:
        if args.self_test:
            candidate_doc = synthetic_candidate_doc()
            readback_doc = synthetic_readback_doc()
            rva_check_doc: Mapping[str, Any] | None = {"rows": [], "status": "self-test"}
            disasm_doc = synthetic_disasm_doc()
        else:
            if args.candidate_json is None:
                raise ValueError("--candidate-json is required unless --self-test is used")
            candidate_doc = load_json(args.candidate_json)
            readback_doc = load_json(args.readback_summary_json) if args.readback_summary_json else None
            rva_check_doc = load_json(args.rva_check_summary_json) if args.rva_check_summary_json else None
            disasm_doc = load_json(args.disasm_summary_json) if args.disasm_summary_json else None
        packet = build_work_packet(
            candidate_doc=candidate_doc,
            readback_doc=readback_doc,
            rva_check_doc=rva_check_doc,
            disasm_doc=disasm_doc,
            inputs={
                "processName": args.process_name,
                "targetPid": args.target_pid,
                "targetHwnd": args.target_hwnd,
                "processStartTimeUtc": args.process_start_time_utc,
                "moduleBase": args.module_base,
            },
        )
        summary = build_summary(repo_root=repo_root, run_dir=run_dir, args=args, packet=packet)
        write_json(Path(summary["artifacts"]["workPacketJson"]), packet)
        write_json(Path(summary["artifacts"]["summaryJson"]), summary)
        write_text_atomic(Path(summary["artifacts"]["summaryMarkdown"]), markdown_summary(packet, summary))
        if args.json:
            print(json.dumps({"status": summary["status"], "summaryJson": summary["artifacts"]["summaryJson"], "workPacketJson": summary["artifacts"]["workPacketJson"], "blockers": summary["blockers"], "warnings": summary["warnings"]}, separators=(",", ":")))
        else:
            print(f"status={summary['status']}")
            print(f"summaryJson={summary['artifacts']['summaryJson']}")
            print(f"workPacketJson={summary['artifacts']['workPacketJson']}")
        return 0
    except Exception as exc:  # noqa: BLE001
        summary = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "x64dbg-static-lead-work-packet-summary",
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "repoRoot": str(repo_root),
            "errors": [f"{type(exc).__name__}:{exc}"],
            "blockers": [],
            "warnings": [],
            "safety": make_safety(),
            "artifacts": {
                "runDirectory": str(run_dir),
                "summaryJson": str(run_dir / "summary.json"),
                "summaryMarkdown": str(run_dir / "summary.md"),
                "workPacketJson": str(run_dir / "static-lead-work-packet.json"),
            },
        }
        write_json(Path(summary["artifacts"]["summaryJson"]), summary)
        write_text_atomic(Path(summary["artifacts"]["summaryMarkdown"]), "# x64dbg static lead work packet\n\n- Status: `failed`\n")
        if args.json:
            print(json.dumps({"status": "failed", "summaryJson": summary["artifacts"]["summaryJson"], "errors": summary["errors"]}, separators=(",", ":")))
        else:
            print(f"status=failed\nsummaryJson={summary['artifacts']['summaryJson']}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
