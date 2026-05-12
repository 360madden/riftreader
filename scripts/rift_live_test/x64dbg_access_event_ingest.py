from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .reports import write_json, write_text_atomic
from .x64dbg_snapshot_diff import BLOCKED_OPERATIONS, SOURCE_LINKS, int_hex


SCHEMA_VERSION = 1
DEFAULT_PROCESS_NAME = "rift_x64"
DEFAULT_WATCH_SIZE = 12
DEFAULT_AXIS_OFFSETS = {"x": "0x0", "y": "0x4", "z": "0x8"}
DEFAULT_POSE_COUNT_REQUIRED = 3


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_int_value(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip(), 0)
        except ValueError:
            return None
    return None


def normalize_hex(value: Any) -> str | None:
    parsed = parse_int_value(value)
    if parsed is not None:
        return int_hex(parsed)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def normalize_hwnd(value: Any) -> str | None:
    return normalize_hex(value)


def number_value(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def string_value(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def add_unique(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)


def make_safety() -> dict[str, Any]:
    return {
        "offlineOnly": True,
        "movementSent": False,
        "inputSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "githubConnectorWrites": False,
        "providerWrites": False,
        "codexMcpConfigured": False,
        "codexMcpServerStarted": False,
        "x64dbgLiveAttachStarted": False,
        "x64dbgCommandsExecuted": False,
        "processAttachOrMemoryReadStarted": False,
        "movementAllowed": False,
        "candidateOnly": True,
        "writeClassOperationsBlocked": True,
        "blockedOperations": list(BLOCKED_OPERATIONS),
    }


def default_artifacts(run_dir: Path) -> dict[str, str | None]:
    return {
        "runDirectory": str(run_dir),
        "summaryJson": str(run_dir / "summary.json"),
        "summaryMarkdown": str(run_dir / "summary.md"),
        "candidateJson": str(run_dir / "x64dbg-coordinate-chain-candidate.json"),
        "normalizedEventsJson": str(run_dir / "normalized-access-events.json"),
    }


def build_summary_base(
    *,
    repo_root: Path,
    run_dir: Path,
    events_json: Path | None,
    status: str,
    blockers: list[str] | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "x64dbg-access-event-ingest",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "repoRoot": str(repo_root),
        "inputs": {
            "accessEventsJson": str(events_json) if events_json else None,
        },
        "counts": {
            "eventCount": 0,
            "poseCount": 0,
            "instructionCount": 0,
            "candidateCount": 0,
        },
        "blockers": blockers or [],
        "warnings": warnings or [],
        "errors": errors or [],
        "sources": list(SOURCE_LINKS),
        "artifacts": default_artifacts(run_dir),
        "safety": make_safety(),
        "next": {
            "recommendedAction": "Provide manual x64dbg 12-byte XYZ access events, then rerun the offline ingester.",
        },
    }


def required_mapping(parent: Mapping[str, Any], key: str, hard_blockers: list[str]) -> Mapping[str, Any]:
    value = parent.get(key)
    if isinstance(value, Mapping):
        return value
    add_unique(hard_blockers, f"missing-{key}")
    return {}


def validate_process(payload: Mapping[str, Any], hard_blockers: list[str]) -> dict[str, Any]:
    raw = required_mapping(payload, "process", hard_blockers)
    pid = parse_int_value(raw.get("pid"))
    hwnd = normalize_hwnd(raw.get("hwnd"))
    start = string_value(raw.get("startTimeUtc"))
    name = string_value(raw.get("name")) or DEFAULT_PROCESS_NAME
    if pid is None or pid <= 0:
        add_unique(hard_blockers, "missing-target-pid")
    if not hwnd:
        add_unique(hard_blockers, "missing-target-hwnd")
    if not start:
        add_unique(hard_blockers, "missing-process-start-time-utc")
    return {
        "name": name,
        "pid": pid,
        "hwnd": hwnd,
        "startTimeUtc": start,
    }


def validate_watch_window(payload: Mapping[str, Any], hard_blockers: list[str]) -> dict[str, Any]:
    raw = required_mapping(payload, "watchWindow", hard_blockers)
    base = normalize_hex(raw.get("baseAddress"))
    size = parse_int_value(raw.get("sizeBytes"))
    axis_order = string_value(raw.get("axisOrder")) or "xyz"
    raw_offsets = raw.get("axisOffsets") if isinstance(raw.get("axisOffsets"), Mapping) else {}
    offsets = {
        "x": normalize_hex(raw_offsets.get("x")),
        "y": normalize_hex(raw_offsets.get("y")),
        "z": normalize_hex(raw_offsets.get("z")),
    }
    if not base:
        add_unique(hard_blockers, "missing-watch-window-base-address")
    if size is None or size < DEFAULT_WATCH_SIZE:
        add_unique(hard_blockers, "watch-size-must-cover-12-byte-xyz-triplet")
    if axis_order != "xyz":
        add_unique(hard_blockers, "unsupported-axis-order")
    if offsets != DEFAULT_AXIS_OFFSETS:
        add_unique(hard_blockers, "unexpected-axis-offsets")
    return {
        "baseAddress": base,
        "sizeBytes": size,
        "axisOrder": axis_order,
        "axisOffsets": offsets,
        "access": raw.get("access") or "access",
        "plannedOnly": False,
    }


def validate_coordinate(
    raw: Mapping[str, Any],
    *,
    prefix: str,
    hard_blockers: list[str],
) -> dict[str, Any]:
    x = number_value(raw.get("x"))
    y = number_value(raw.get("y"))
    z = number_value(raw.get("z"))
    sampled_at = string_value(raw.get("sampledAtUtc"))
    if x is None or y is None or z is None:
        add_unique(hard_blockers, f"missing-{prefix}-coordinate")
    if not sampled_at:
        add_unique(hard_blockers, f"missing-{prefix}-sampled-at-utc")
    result: dict[str, Any] = {
        "sampledAtUtc": sampled_at,
        "x": x,
        "y": y,
        "z": z,
    }
    if "kind" in raw:
        result["kind"] = raw.get("kind")
    if "source" in raw:
        result["source"] = raw.get("source")
    if "address" in raw:
        result["address"] = normalize_hex(raw.get("address"))
    if "axisOrder" in raw:
        result["axisOrder"] = raw.get("axisOrder")
    return result


def coordinate_deltas(truth: Mapping[str, Any], memory: Mapping[str, Any]) -> dict[str, float | None]:
    deltas: dict[str, float | None] = {}
    for axis in ("x", "y", "z"):
        truth_value = number_value(truth.get(axis))
        memory_value = number_value(memory.get(axis))
        deltas[axis] = None if truth_value is None or memory_value is None else abs(memory_value - truth_value)
    values = [delta for delta in deltas.values() if delta is not None]
    deltas["maxAbs"] = max(values) if values else None
    return deltas


def normalize_instruction(
    raw: Mapping[str, Any],
    *,
    event_id: str,
    event_access: str,
    hard_blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    module = string_value(raw.get("module"))
    module_base = normalize_hex(raw.get("moduleBase"))
    address = normalize_hex(raw.get("address"))
    rva = normalize_hex(raw.get("rva"))
    bytes_text = string_value(raw.get("bytes"))
    disassembly = string_value(raw.get("disassembly"))
    access = string_value(raw.get("access")) or event_access
    registers = raw.get("registers") if isinstance(raw.get("registers"), Mapping) else {}
    derived_object_pointer = normalize_hex(raw.get("derivedObjectPointer"))
    field_offset = normalize_hex(raw.get("fieldOffset"))

    for field_name, value in (
        ("module", module),
        ("moduleBase", module_base),
        ("address", address),
        ("rva", rva),
        ("bytes", bytes_text),
        ("disassembly", disassembly),
        ("access", access),
    ):
        if not value:
            add_unique(hard_blockers, f"missing-instruction-{field_name}")

    module_base_int = parse_int_value(raw.get("moduleBase"))
    address_int = parse_int_value(raw.get("address"))
    rva_int = parse_int_value(raw.get("rva"))
    if module_base_int is not None and address_int is not None and rva_int is not None:
        if address_int - module_base_int != rva_int:
            add_unique(hard_blockers, "instruction-rva-mismatch")

    if access != event_access:
        add_unique(warnings, f"instruction-access-mismatch:{event_id}")
    if not isinstance(raw.get("registers"), Mapping):
        add_unique(warnings, f"instruction-registers-missing-or-not-object:{event_id}")
    if not derived_object_pointer:
        add_unique(warnings, f"missing-derived-object-pointer:{event_id}")
    if not field_offset:
        add_unique(warnings, f"missing-field-offset:{event_id}")

    return {
        "module": module,
        "moduleBase": module_base,
        "address": address,
        "rva": rva,
        "bytes": bytes_text,
        "disassembly": disassembly,
        "access": access,
        "registers": dict(registers),
        "derivedObjectPointer": derived_object_pointer,
        "fieldOffset": field_offset,
    }


def normalize_events(
    payload: Mapping[str, Any],
    *,
    max_delta: float,
    allow_write_access_events: bool,
    hard_blockers: list[str],
    warnings: list[str],
) -> list[dict[str, Any]]:
    raw_events = payload.get("events")
    if not isinstance(raw_events, list) or not raw_events:
        add_unique(hard_blockers, "no-access-events-recorded")
        return []

    normalized: list[dict[str, Any]] = []
    seen_event_ids: set[str] = set()
    for index, raw_event in enumerate(raw_events, start=1):
        if not isinstance(raw_event, Mapping):
            add_unique(hard_blockers, "access-event-not-object")
            continue
        event_id = string_value(raw_event.get("eventId")) or f"event-{index:03d}"
        if event_id in seen_event_ids:
            add_unique(hard_blockers, "duplicate-event-id")
        seen_event_ids.add(event_id)
        pose_id = string_value(raw_event.get("poseId"))
        if not pose_id:
            add_unique(hard_blockers, "missing-pose-id")
            pose_id = f"pose-{index:03d}"
        if raw_event.get("targetStillMatched") is not True:
            add_unique(hard_blockers, "target-mismatch-in-access-event")

        access = (string_value(raw_event.get("access")) or "").lower()
        if access not in {"read", "write", "access"}:
            add_unique(hard_blockers, "unsupported-access-type")
            access = access or "unknown"
        if access == "write" and not allow_write_access_events:
            add_unique(hard_blockers, "write-access-event-present")
            add_unique(hard_blockers, "write-class-operation-present")
        elif access == "write":
            add_unique(warnings, "write-access-event-observed-candidate-only")

        truth_raw = required_mapping(raw_event, "truthSurface", hard_blockers)
        memory_raw = required_mapping(raw_event, "memoryNow", hard_blockers)
        instruction_raw = required_mapping(raw_event, "instruction", hard_blockers)
        truth = validate_coordinate(truth_raw, prefix="api", hard_blockers=hard_blockers)
        memory = validate_coordinate(memory_raw, prefix="memory", hard_blockers=hard_blockers)
        memory["address"] = normalize_hex(memory_raw.get("address"))
        if not memory.get("address"):
            add_unique(hard_blockers, "missing-memory-address")

        deltas = coordinate_deltas(truth, memory)
        max_abs = deltas.get("maxAbs")
        if max_abs is None:
            add_unique(hard_blockers, "api-now-vs-memory-now-delta-unavailable")
        elif max_abs > max_delta:
            add_unique(hard_blockers, "api-now-vs-memory-now-delta-exceeded")

        instruction = normalize_instruction(
            instruction_raw,
            event_id=event_id,
            event_access=access,
            hard_blockers=hard_blockers,
            warnings=warnings,
        )
        normalized.append(
            {
                "eventId": event_id,
                "poseId": pose_id,
                "hitAtUtc": string_value(raw_event.get("hitAtUtc")),
                "targetStillMatched": raw_event.get("targetStillMatched") is True,
                "access": access,
                "truthSurface": truth,
                "memoryNow": memory,
                "deltas": deltas,
                "instruction": instruction,
            }
        )
    return normalized


def top_level_payload_checks(payload: Mapping[str, Any], hard_blockers: list[str]) -> None:
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        add_unique(hard_blockers, "unsupported-schema-version")
    if payload.get("kind") != "x64dbg-manual-access-events":
        add_unique(hard_blockers, "unsupported-input-kind")
    if not string_value(payload.get("capturedAtUtc")):
        add_unique(hard_blockers, "missing-captured-at-utc")
    if payload.get("cheatEngineInvolved") is True:
        add_unique(hard_blockers, "cheat-engine-not-allowed-for-current-boundary")
    raw_operations = payload.get("operations")
    if isinstance(raw_operations, list):
        blocked = sorted({str(op) for op in raw_operations if str(op) in BLOCKED_OPERATIONS})
        if blocked:
            add_unique(hard_blockers, "write-class-operation-present")


def build_candidate(
    *,
    payload: Mapping[str, Any],
    process: dict[str, Any],
    watch_window: dict[str, Any],
    events: list[dict[str, Any]],
    candidate_id: str,
    pose_count_required: int,
    promotion_blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    first_event = events[0]
    first_instruction = first_event["instruction"]
    validation_raw = payload.get("validation") if isinstance(payload.get("validation"), Mapping) else {}
    pose_ids = sorted({str(event["poseId"]) for event in events})
    access_types = sorted({str(event["access"]) for event in events})

    restart_validated = validation_raw.get("restartValidated") is True
    runtime_helper_readback = validation_raw.get("runtimeHelperReadback") is True
    proof_only_passed = validation_raw.get("proofOnlyPassed") is True
    if len(pose_ids) < pose_count_required:
        add_unique(promotion_blockers, "not-multi-pose-validated")
    if not restart_validated:
        add_unique(promotion_blockers, "not-restart-validated")
    if not runtime_helper_readback:
        add_unique(promotion_blockers, "no-runtime-helper-readback")
        add_unique(promotion_blockers, "not-promoted-through-api-now-vs-chain-now")
    if not proof_only_passed:
        add_unique(promotion_blockers, "proofonly-not-passed")

    derived_chain = payload.get("derivedChain") if isinstance(payload.get("derivedChain"), Mapping) else {}
    if not derived_chain.get("rootRva") and not derived_chain.get("chainExpression"):
        add_unique(promotion_blockers, "not-module-relative-rooted")

    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "candidate",
        "tool": "x64dbg",
        "kind": "x64dbg-coordinate-chain-candidate",
        "capturedAtUtc": payload.get("capturedAtUtc"),
        "generatedAtUtc": utc_iso(),
        "candidateId": candidate_id,
        "process": process,
        "truthSurface": first_event["truthSurface"],
        "memoryNow": {
            "address": first_event["memoryNow"].get("address"),
            "axisOrder": watch_window.get("axisOrder"),
            "sampledAtUtc": first_event["memoryNow"].get("sampledAtUtc"),
            "x": first_event["memoryNow"].get("x"),
            "y": first_event["memoryNow"].get("y"),
            "z": first_event["memoryNow"].get("z"),
        },
        "watchWindow": {
            "baseAddress": watch_window.get("baseAddress"),
            "sizeBytes": watch_window.get("sizeBytes"),
            "axisOffsets": watch_window.get("axisOffsets"),
            "access": ",".join(access_types),
            "plannedOnly": False,
        },
        "observedAccessEvents": events,
        "instruction": first_instruction,
        "derivedChain": {
            "rootKind": derived_chain.get("rootKind") or "pending-module-rva-or-static-owner",
            "module": derived_chain.get("module") or first_instruction.get("module"),
            "moduleBase": derived_chain.get("moduleBase") or first_instruction.get("moduleBase"),
            "instructionRva": first_instruction.get("rva"),
            "rootRva": normalize_hex(derived_chain.get("rootRva")),
            "offsets": derived_chain.get("offsets") if isinstance(derived_chain.get("offsets"), list) else [],
            "fieldOffsets": watch_window.get("axisOffsets"),
            "chainExpression": derived_chain.get("chainExpression"),
        },
        "validation": {
            "sameTarget": all(event.get("targetStillMatched") is True for event in events),
            "apiNowVsMemoryNow": True,
            "apiNowVsChainNow": runtime_helper_readback,
            "multiPose": len(pose_ids) >= pose_count_required,
            "poseCountObserved": len(pose_ids),
            "poseCountRequired": pose_count_required,
            "restartValidated": restart_validated,
            "runtimeHelperReadback": runtime_helper_readback,
            "proofOnlyPassed": proof_only_passed,
            "movementProofEligible": False,
        },
        "blockers": promotion_blockers,
        "warnings": warnings + ["manual-x64dbg-access-event-ingest-candidate-only"],
    }


def markdown_summary(summary: dict[str, Any], candidate: dict[str, Any] | None = None) -> str:
    safety = summary["safety"]
    lines = [
        "# x64dbg access-event ingest summary",
        "",
        f"- Status: `{summary['status']}`",
        f"- Generated UTC: `{summary['generatedAtUtc']}`",
        f"- Events: `{summary['counts']['eventCount']}`",
        f"- Poses: `{summary['counts']['poseCount']}`",
        f"- Candidate count: `{summary['counts']['candidateCount']}`",
        f"- Movement allowed: `{str(safety.get('movementAllowed')).lower()}`",
        f"- x64dbg live attach started: `{str(safety.get('x64dbgLiveAttachStarted')).lower()}`",
        f"- x64dbg commands executed: `{str(safety.get('x64dbgCommandsExecuted')).lower()}`",
    ]
    if candidate:
        validation = candidate["validation"]
        lines.extend(
            [
                "",
                "## Candidate",
                "",
                f"- Candidate id: `{candidate.get('candidateId')}`",
                f"- Watch base: `{candidate.get('watchWindow', {}).get('baseAddress')}`",
                f"- Memory address: `{candidate.get('memoryNow', {}).get('address')}`",
                f"- Multi-pose: `{str(validation.get('multiPose')).lower()}` (`{validation.get('poseCountObserved')}` / `{validation.get('poseCountRequired')}`)",
                f"- Runtime helper readback: `{str(validation.get('runtimeHelperReadback')).lower()}`",
                f"- Restart validated: `{str(validation.get('restartValidated')).lower()}`",
                f"- ProofOnly passed: `{str(validation.get('proofOnlyPassed')).lower()}`",
                f"- Movement proof eligible: `{str(validation.get('movementProofEligible')).lower()}`",
            ]
        )
    if summary["blockers"]:
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if summary["warnings"]:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{warning}`" for warning in summary["warnings"])
    if summary["errors"]:
        lines.extend(["", "## Errors"])
        lines.extend(f"- `{error}`" for error in summary["errors"])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This helper ingests offline/manual x64dbg access-event JSON only. It does",
            "not attach x64dbg, read live process memory, send input, configure MCP,",
            "or promote movement/navigation truth.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def synthetic_payload() -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    for idx, coord in enumerate(
        [
            (7376.87, 863.82, 2990.35),
            (7378.42, 864.01, 2991.12),
            (7373.11, 862.44, 2988.91),
        ],
        start=1,
    ):
        x, y, z = coord
        events.append(
            {
                "eventId": f"pose-{idx:03d}-hit-001",
                "poseId": f"pose-{idx:03d}",
                "hitAtUtc": f"2026-05-12T21:00:{idx:02d}Z",
                "targetStillMatched": True,
                "access": "read",
                "truthSurface": {
                    "kind": "api-now",
                    "source": "synthetic-api-now",
                    "sampledAtUtc": f"2026-05-12T21:00:{idx:02d}Z",
                    "x": x,
                    "y": y,
                    "z": z,
                },
                "memoryNow": {
                    "address": "0x78BF4FE420",
                    "sampledAtUtc": f"2026-05-12T21:00:{idx:02d}Z",
                    "x": x + 0.01,
                    "y": y - 0.01,
                    "z": z,
                },
                "instruction": {
                    "module": "rift_x64.exe",
                    "moduleBase": "0x140000000",
                    "address": "0x141234567",
                    "rva": "0x1234567",
                    "bytes": "F30F1001",
                    "disassembly": "movss xmm0, dword ptr [rcx]",
                    "access": "read",
                    "registers": {
                        "rcx": "0x78BF4FE420",
                        "rax": "0x78BF4FE420",
                    },
                    "derivedObjectPointer": "0x78BF4FE420",
                    "fieldOffset": "0x0",
                },
            }
        )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "x64dbg-manual-access-events",
        "capturedAtUtc": "2026-05-12T21:00:00Z",
        "source": {
            "tool": "x64dbg",
            "captureMode": "manual-watchpoint",
            "operator": "synthetic-self-test",
        },
        "process": {
            "name": "rift_x64",
            "pid": 63412,
            "hwnd": "0xB70082",
            "startTimeUtc": "2026-05-12T15:53:24Z",
        },
        "watchWindow": {
            "baseAddress": "0x78BF4FE420",
            "sizeBytes": DEFAULT_WATCH_SIZE,
            "axisOrder": "xyz",
            "axisOffsets": DEFAULT_AXIS_OFFSETS,
        },
        "events": events,
    }


def ingest_payload(
    *,
    payload: Mapping[str, Any],
    repo_root: Path,
    run_dir: Path,
    events_json: Path | None,
    candidate_id: str,
    max_delta: float,
    pose_count_required: int,
    allow_write_access_events: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None, list[dict[str, Any]]]:
    hard_blockers: list[str] = []
    warnings: list[str] = []
    top_level_payload_checks(payload, hard_blockers)
    process = validate_process(payload, hard_blockers)
    watch_window = validate_watch_window(payload, hard_blockers)
    events = normalize_events(
        payload,
        max_delta=max_delta,
        allow_write_access_events=allow_write_access_events,
        hard_blockers=hard_blockers,
        warnings=warnings,
    )
    status = "blocked" if hard_blockers else "passed"
    summary = build_summary_base(
        repo_root=repo_root,
        run_dir=run_dir,
        events_json=events_json,
        status=status,
        blockers=list(hard_blockers),
        warnings=warnings,
        errors=[],
    )
    pose_count = len({event["poseId"] for event in events})
    summary["counts"] = {
        "eventCount": len(events),
        "poseCount": pose_count,
        "instructionCount": len(events),
        "candidateCount": 0,
    }
    summary["process"] = process
    summary["watchWindow"] = watch_window
    summary["validation"] = {
        "maxDelta": max_delta,
        "poseCountRequired": pose_count_required,
    }
    summary["next"]["recommendedAction"] = (
        "Fix the hard blockers before using these access events as a coordinate-chain candidate."
        if hard_blockers
        else "Use the candidate packet as evidence only; next add repo-owned chain readback and restart validation before promotion."
    )

    if hard_blockers or not events:
        return summary, None, events

    promotion_blockers: list[str] = []
    candidate = build_candidate(
        payload=payload,
        process=process,
        watch_window=watch_window,
        events=events,
        candidate_id=candidate_id,
        pose_count_required=pose_count_required,
        promotion_blockers=promotion_blockers,
        warnings=warnings,
    )
    summary["counts"]["candidateCount"] = 1
    summary["candidate"] = {
        "candidateId": candidate_id,
        "status": candidate["status"],
        "movementProofEligible": False,
        "promotionBlockers": candidate["blockers"],
    }
    summary["blockers"] = list(candidate["blockers"])
    summary["warnings"] = candidate["warnings"]
    return summary, candidate, events


def write_outputs(summary: dict[str, Any], candidate: dict[str, Any] | None, events: list[dict[str, Any]]) -> None:
    artifacts = summary["artifacts"]
    run_dir = Path(str(artifacts["runDirectory"]))
    run_dir.mkdir(parents=True, exist_ok=True)
    if candidate:
        write_json(Path(str(artifacts["candidateJson"])), candidate)
    else:
        artifacts["candidateJson"] = None
    if events:
        write_json(Path(str(artifacts["normalizedEventsJson"])), events)
    else:
        artifacts["normalizedEventsJson"] = None
    write_text_atomic(Path(str(artifacts["summaryMarkdown"])), markdown_summary(summary, candidate))
    write_json(Path(str(artifacts["summaryJson"])), summary)


def choose_run_dir(repo_root: Path, output_root: Path | None) -> Path:
    run_dir = output_root.resolve() if output_root else repo_root / "scripts" / "captures" / f"x64dbg-access-event-ingest-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def load_payload(path: Path) -> Mapping[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("input JSON must be an object")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest manual x64dbg access events into a candidate-only coordinate chain packet.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--events-json", type=Path, default=None)
    parser.add_argument("--candidate-id", default="x64dbg-access-event-candidate-000001")
    parser.add_argument("--max-delta", type=float, default=1.0)
    parser.add_argument("--pose-count-required", type=int, default=DEFAULT_POSE_COUNT_REQUIRED)
    parser.add_argument("--allow-write-access-events", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else repo_root_from_module()
    run_dir = choose_run_dir(repo_root, args.output_root)
    events_json = args.events_json.resolve() if args.events_json else None

    if args.dry_run:
        summary = build_summary_base(
            repo_root=repo_root,
            run_dir=run_dir,
            events_json=events_json,
            status="blocked",
            blockers=["dry-run-no-access-events-ingested"],
            warnings=[],
            errors=[],
        )
        write_outputs(summary, None, [])
        result_code = 2
    else:
        try:
            if args.self_test:
                payload: Mapping[str, Any] = synthetic_payload()
            elif events_json:
                payload = load_payload(events_json)
            else:
                raise ValueError("--events-json is required unless --self-test or --dry-run is used")
            summary, candidate, events = ingest_payload(
                payload=payload,
                repo_root=repo_root,
                run_dir=run_dir,
                events_json=events_json,
                candidate_id=args.candidate_id,
                max_delta=args.max_delta,
                pose_count_required=args.pose_count_required,
                allow_write_access_events=args.allow_write_access_events,
            )
            write_outputs(summary, candidate, events)
            result_code = 2 if summary["status"] == "blocked" else 0
        except Exception as exc:  # noqa: BLE001 - CLI must preserve failure details in artifact.
            summary = build_summary_base(
                repo_root=repo_root,
                run_dir=run_dir,
                events_json=events_json,
                status="failed",
                blockers=[],
                warnings=[],
                errors=[f"{type(exc).__name__}: {exc}"],
            )
            write_outputs(summary, None, [])
            result_code = 1

    if args.json:
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "summaryJson": summary["artifacts"]["summaryJson"],
                    "summaryMarkdown": summary["artifacts"]["summaryMarkdown"],
                    "candidateJson": summary["artifacts"].get("candidateJson"),
                    "blockers": summary["blockers"],
                    "warnings": summary["warnings"],
                    "errors": summary["errors"],
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"status={summary['status']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
        print(f"summaryMarkdown={summary['artifacts']['summaryMarkdown']}")
        candidate_path = summary["artifacts"].get("candidateJson")
        if candidate_path:
            print(f"candidateJson={candidate_path}")
        if summary["blockers"]:
            print("blockers=" + ";".join(summary["blockers"]))
        if summary["warnings"]:
            print("warnings=" + ";".join(summary["warnings"]))
        if summary["errors"]:
            print("errors=" + ";".join(summary["errors"]))
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
