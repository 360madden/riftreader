#!/usr/bin/env python3
"""No-input post-update owner/root rediscovery status and next-step helper.

This helper is deliberately candidate-only.  It consolidates the current
post-update evidence, checks whether direct coordinate candidates look like the
old owner layout, and ranks the safest next read-only root-discovery work.

It never sends input, attaches a debugger, writes target memory, updates truth,
or promotes a proof/actor chain.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import struct
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workflow_common import base_safety, repo_root as default_repo_root, utc_iso, utc_stamp, write_json  # noqa: E402


SCHEMA_VERSION = 1
DEFAULT_MODULE_SIZE = 0x5000000
DEFAULT_OWNER_WINDOW_BYTES = 0x480
DEFAULT_RIFT_LIVE_ROOT = Path(r"C:\Program Files (x86)\Glyph\Games\RIFT\Live")
OLD_OWNER_COORD_OFFSET = 0x320
OWNER_HYPOTHESIS_OFFSETS = (0x320, 0x324, 0x328, 0x300, 0x30C, 0x310, 0x314)
PROMOTED_LAYOUT_OFFSETS = ("0x300", "0x304", "0x30C", "0x310", "0x314", "0x320", "0x324", "0x328")


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


def hex_int(value: int | None) -> str | None:
    return None if value is None else f"0x{value:X}"


def safe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def load_json_object(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return data


def resolve_path(repo_root: Path, value: str | Path | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def latest_path(capture_root: Path, pattern: str) -> Path | None:
    matches = [path for path in capture_root.glob(pattern) if path.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def latest_artifact_paths(repo_root: Path) -> dict[str, str | None]:
    capture_root = repo_root / "scripts" / "captures"
    patterns = {
        "candidateReadback": "candidate-readback-currentpid-*/candidate-readback-summary.json",
        "staticReadback": "static-owner-coordinate-chain-readback-*/summary.json",
        "staticFieldMatrix": "static-field-access-matrix-*/summary.json",
        "ghidraStatic": "ghidra-static-analysis-*/summary.json",
        "pointerFamily": "pointer-family-scan-*/summary.json",
        "ownerBatch": "pointer-owner-batch-currentpid-*/summary.json",
        "rootSignatureSeed": "postupdate-root-signature-seed-currentpid-*/root-signature-seed.json",
        "rootSignatureBatch": "root-signature-batch-sweep-currentpid-*/summary.json",
        "staticAccessChain": "postupdate-static-access-chain-*/summary.json",
    }
    return {
        key: str(path.resolve()) if (path := latest_path(capture_root, pattern)) else None
        for key, pattern in patterns.items()
    }


def file_mtime_utc(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_game_epoch(rift_live_root: Path) -> dict[str, Any]:
    manifest = rift_live_root / "manifest64.txt"
    executable = rift_live_root / "rift_x64.exe"
    result: dict[str, Any] = {
        "riftLiveRoot": str(rift_live_root),
        "manifestPath": str(manifest),
        "manifestExists": manifest.is_file(),
        "manifestVersion": None,
        "manifestLastWriteTimeUtc": file_mtime_utc(manifest),
        "manifestLength": manifest.stat().st_size if manifest.exists() else None,
        "manifestRiftX64Sha1": None,
        "manifestRiftX64Size": None,
        "executablePath": str(executable),
        "executableExists": executable.is_file(),
        "executableLastWriteTimeUtc": file_mtime_utc(executable),
        "executableLength": executable.stat().st_size if executable.exists() else None,
        "candidateOnly": False,
    }
    if not manifest.is_file():
        result["status"] = "missing"
        result["blockers"] = ["manifest64-missing"]
        return result

    try:
        lines = manifest.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError as exc:
        result["status"] = "blocked"
        result["blockers"] = [f"manifest64-read-failed:{type(exc).__name__}"]
        return result

    if lines and lines[0].startswith("version "):
        result["manifestVersion"] = lines[0].split(" ", 1)[1].strip()
    for line in lines:
        if line.startswith("rift_x64.exe:"):
            parts = line.split(":")
            if len(parts) >= 3:
                result["manifestRiftX64Sha1"] = parts[1]
                result["manifestRiftX64Size"] = parse_int(parts[2])
            break
    result["status"] = "passed" if result["manifestVersion"] else "blocked"
    result["blockers"] = [] if result["manifestVersion"] else ["manifest-version-missing"]
    return result


def coordinate_from_mapping(value: Any) -> dict[str, float] | None:
    data = safe_mapping(value)
    axes: dict[str, float] = {}
    for axis in ("x", "y", "z"):
        raw = data.get(axis, data.get(axis.upper()))
        try:
            parsed = float(raw)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(parsed):
            return None
        axes[axis] = parsed
    return axes


def max_abs_delta(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    return max(abs(float(left[axis]) - float(right[axis])) for axis in ("x", "y", "z"))


def best_candidate_from_readback(candidate_readback: Mapping[str, Any]) -> dict[str, Any]:
    best = safe_mapping(candidate_readback.get("bestReadback"))
    if best:
        return best
    readbacks = [safe_mapping(item) for item in safe_list(candidate_readback.get("readbacks"))]
    return readbacks[0] if readbacks else {}


def candidate_address_from_readback(candidate_readback: Mapping[str, Any]) -> int | None:
    best = best_candidate_from_readback(candidate_readback)
    return parse_int(best.get("addressHex") or best.get("address"))


def reference_from_readback(candidate_readback: Mapping[str, Any]) -> dict[str, float] | None:
    best = best_candidate_from_readback(candidate_readback)
    return (
        coordinate_from_mapping(best.get("reference"))
        or coordinate_from_mapping(candidate_readback.get("reference"))
        or coordinate_from_mapping(best.get("memoryValue"))
    )


def read_vec3_from_bytes(data: bytes, offset: int) -> dict[str, float] | None:
    if offset < 0 or offset + 12 > len(data):
        return None
    try:
        x, y, z = struct.unpack_from("<fff", data, offset)
    except struct.error:
        return None
    values = {"x": float(x), "y": float(y), "z": float(z)}
    return values if all(math.isfinite(v) for v in values.values()) else None


def read_f32_from_bytes(data: bytes, offset: int) -> float | None:
    if offset < 0 or offset + 4 > len(data):
        return None
    try:
        value = struct.unpack_from("<f", data, offset)[0]
    except struct.error:
        return None
    return float(value) if math.isfinite(value) else None


def read_u32_from_bytes(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 4 > len(data):
        return None
    try:
        return int(struct.unpack_from("<I", data, offset)[0])
    except struct.error:
        return None


def read_i32_from_bytes(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 4 > len(data):
        return None
    try:
        return int(struct.unpack_from("<i", data, offset)[0])
    except struct.error:
        return None


def qwords_from_bytes(data: bytes, *, count: int) -> list[int]:
    values: list[int] = []
    for index in range(count):
        offset = index * 8
        if offset + 8 > len(data):
            break
        values.append(int.from_bytes(data[offset : offset + 8], "little", signed=False))
    return values


def module_pointer_offsets(data: bytes, module_base: int, module_size: int, *, limit: int = 0x90) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    module_end = module_base + module_size
    for offset in range(0, min(len(data), limit), 8):
        value = int.from_bytes(data[offset : offset + 8], "little", signed=False)
        if module_base <= value < module_end:
            results.append({"offset": hex_int(offset), "value": hex_int(value), "rva": hex_int(value - module_base)})
    return results


def plausible_world_vec3(value: dict[str, float] | None, reference: Mapping[str, float] | None = None) -> bool:
    if value is None:
        return False
    if any(abs(float(value[axis])) > 100000.0 for axis in ("x", "y", "z")):
        return False
    # Tiny denormal/zero-looking triplets are not useful world coordinates here.
    if max(abs(float(value[axis])) for axis in ("x", "y", "z")) < 1.0:
        return False
    if reference is not None:
        planar = math.hypot(float(value["x"]) - float(reference["x"]), float(value["z"]) - float(reference["z"]))
        if planar > 5000.0:
            return False
    return True


def support_fields_from_bytes(data: bytes) -> dict[str, Any]:
    return {
        "owner+0x300": read_f32_from_bytes(data, 0x300),
        "owner+0x304": read_f32_from_bytes(data, 0x304),
        "owner+0x438": read_f32_from_bytes(data, 0x438),
        "owner+0x43C_u32": read_u32_from_bytes(data, 0x43C),
        "owner+0x440_i32": read_i32_from_bytes(data, 0x440),
    }


def support_fields_sane(fields: Mapping[str, Any]) -> bool:
    float_values = [fields.get("owner+0x300"), fields.get("owner+0x304"), fields.get("owner+0x438")]
    sane_floats = [
        isinstance(value, (int, float))
        and math.isfinite(float(value))
        and abs(float(value)) < 100000.0
        for value in float_values
    ]
    integer_values = [fields.get("owner+0x43C_u32"), fields.get("owner+0x440_i32")]
    sane_ints = [isinstance(value, int) and abs(value) < 100000000 for value in integer_values]
    return sum(bool(v) for v in sane_floats + sane_ints) >= 3


def classify_owner_shape_from_bytes(
    *,
    owner_base: int,
    offset_assumption: int,
    data: bytes | None,
    module_base: int,
    module_size: int,
    reference: Mapping[str, float] | None,
    tolerance: float,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ownerHypothesisAddress": hex_int(owner_base),
        "offsetAssumption": hex_int(offset_assumption),
        "readable": data is not None,
        "score": 0,
        "classification": "unreadable",
        "promotionEligible": False,
        "candidateOnly": True,
        "reasons": [],
    }
    if data is None:
        result["reasons"].append("owner-window-unreadable")
        return result

    module_pointers = module_pointer_offsets(data, module_base, module_size)
    first_qwords = qwords_from_bytes(data[:0x90], count=0x90 // 8)
    coord_at_320 = read_vec3_from_bytes(data, OLD_OWNER_COORD_OFFSET)
    facing_at_30c = read_vec3_from_bytes(data, 0x30C)
    support = support_fields_from_bytes(data)
    coord_delta = max_abs_delta(coord_at_320, reference) if coord_at_320 and reference else None
    coord_matches = coord_delta is not None and coord_delta <= tolerance
    facing_plausible = plausible_world_vec3(facing_at_30c, reference)
    support_sane = support_fields_sane(support)

    score = 0
    reasons: list[str] = []
    if coord_matches:
        score += 50
        reasons.append(f"coord+0x320-within-tolerance:{coord_delta:.6f}")
    elif coord_at_320 and reference:
        reasons.append(f"coord+0x320-delta:{coord_delta:.6f}" if coord_delta is not None else "coord+0x320-no-reference")
    if len(module_pointers) >= 1:
        score += min(30, 10 + len(module_pointers) * 2)
        reasons.append(f"module-pointers-first0x90:{len(module_pointers)}")
    if facing_plausible:
        score += 10
        reasons.append("facing+0x30c-plausible-world-vec3")
    if support_sane and module_pointers:
        score += 10
        reasons.append("support-fields-sane")
    elif support_sane:
        reasons.append("support-fields-sane-but-untrusted-without-owner-header")

    classification = "rejected-not-owner-shaped"
    if coord_matches and not module_pointers:
        classification = "direct-coordinate-copy-not-owner-shaped"
        reasons.append("coordinate-matches-but-owner-header-lacks-module-shape")
    elif coord_matches and module_pointers and score >= 60:
        classification = "owner-shaped-candidate"
    elif module_pointers and score >= 40:
        classification = "weak-owner-shape-candidate-needs-pointer-proof"

    result.update(
        {
            "score": score,
            "classification": classification,
            "modulePointerCountFirst0x90": len(module_pointers),
            "modulePointersFirst0x90": module_pointers[:12],
            "firstQwords": [hex_int(value) for value in first_qwords],
            "reads": {
                "coordinateAt0x320": coord_at_320,
                "coordinateAt0x320MaxAbsDelta": coord_delta,
                "facingAt0x30C": facing_at_30c,
                "supportFields": support,
            },
            "reasons": reasons,
        }
    )
    return result


def rank_static_clusters(static_matrix: Mapping[str, Any]) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    offset_hits = safe_mapping(static_matrix.get("offsetHits"))
    for offset, hits in offset_hits.items():
        if offset not in PROMOTED_LAYOUT_OFFSETS:
            continue
        for hit in safe_list(hits):
            row = safe_mapping(hit)
            function_rva = row.get("linearFunctionStartRva")
            if not function_rva:
                continue
            cluster = counts.setdefault(
                str(function_rva),
                {"functionStartRva": str(function_rva), "offsets": set(), "hitCount": 0, "writeLikeCount": 0, "examples": []},
            )
            cluster["offsets"].add(str(offset))
            cluster["hitCount"] += 1
            if str(row.get("operandAccess") or "").lower() == "write":
                cluster["writeLikeCount"] += 1
            if len(cluster["examples"]) < 5:
                cluster["examples"].append(
                    {
                        "offset": offset,
                        "rva": row.get("rva"),
                        "instruction": row.get("instruction"),
                        "access": row.get("operandAccess"),
                    }
                )
    ranked: list[dict[str, Any]] = []
    for cluster in counts.values():
        offsets = sorted(cluster["offsets"], key=lambda item: parse_int(item) or 0)
        score = len(offsets) * 20 + int(cluster["hitCount"]) + int(cluster["writeLikeCount"]) * 2
        ranked.append(
            {
                "functionStartRva": cluster["functionStartRva"],
                "score": score,
                "offsets": offsets,
                "offsetCount": len(offsets),
                "hitCount": cluster["hitCount"],
                "writeLikeCount": cluster["writeLikeCount"],
                "examples": cluster["examples"],
                "candidateOnly": True,
            }
        )
    return sorted(ranked, key=lambda item: (-int(item["score"]), -int(item["offsetCount"]), str(item["functionStartRva"])))


def summarize_pointer_family(pointer_family: Mapping[str, Any]) -> dict[str, Any]:
    ranked = [safe_mapping(item) for item in safe_list(pointer_family.get("rankedTargets"))]
    module_hits = sum(int(item.get("moduleHitCount") or 0) for item in ranked)
    rift_hits = sum(int(item.get("riftModuleHitCount") or 0) for item in ranked)
    top_hits: list[dict[str, Any]] = []
    for item in ranked[:4]:
        for hit in safe_list(item.get("hits"))[:4]:
            hit_map = safe_mapping(hit)
            top_hits.append(
                {
                    "target": item.get("target"),
                    "address": hit_map.get("address"),
                    "module": hit_map.get("module"),
                    "asciiPreview": hit_map.get("asciiPreview"),
                }
            )
    return {
        "status": pointer_family.get("status"),
        "path": safe_mapping(pointer_family.get("artifacts")).get("summaryJson"),
        "moduleHitCount": module_hits,
        "riftModuleHitCount": rift_hits,
        "rankedTargetCount": len(ranked),
        "topHits": top_hits,
    }


def summarize_owner_batch(owner_batch: Mapping[str, Any]) -> dict[str, Any]:
    rows = [safe_mapping(item) for item in safe_list(owner_batch.get("rankedRows"))]
    hints = [safe_mapping(item) for item in safe_list(owner_batch.get("moduleRvaHints"))]
    return {
        "status": owner_batch.get("status"),
        "path": safe_mapping(owner_batch.get("artifacts")).get("summaryJson"),
        "inspectedOwnerCount": safe_mapping(owner_batch.get("counts")).get("inspectedOwnerCount"),
        "moduleRvaHintCount": safe_mapping(owner_batch.get("counts")).get("moduleRvaHintCount"),
        "topRows": rows[:5],
        "moduleRvaHints": hints[:8],
    }


def summarize_root_signature_seed(seed: Mapping[str, Any]) -> dict[str, Any]:
    signature = safe_mapping(seed.get("signature"))
    fields = [safe_mapping(item) for item in safe_list(signature.get("ownerModuleFields"))]
    return {
        "status": seed.get("status"),
        "path": safe_mapping(seed.get("artifacts")).get("seedJson"),
        "generatedAtUtc": seed.get("generatedAtUtc"),
        "ownerBase": signature.get("ownerBase"),
        "coordPointer": signature.get("coordPointer"),
        "coordPointerSlotOffset": signature.get("coordPointerSlotOffset"),
        "ownerModuleFieldCount": len(fields),
        "ownerModuleFields": fields[:12],
        "blockers": safe_list(seed.get("blockers")),
        "warnings": safe_list(seed.get("warnings")),
        "candidateOnly": True,
        "promotionEligible": False,
    }


def _matched_field_count(candidate: Mapping[str, Any]) -> int:
    return sum(1 for field in safe_list(candidate.get("fieldMatches")) if safe_mapping(field).get("matched"))


def _field_count(candidate: Mapping[str, Any]) -> int:
    return len(safe_list(candidate.get("fieldMatches")))


def _root_sweep_high_signal(result: Mapping[str, Any]) -> bool:
    owner = safe_mapping(result.get("topOwnerFieldCandidate"))
    parent = safe_mapping(result.get("topParentSlotCandidate"))
    reasons = {str(reason) for reason in safe_list(owner.get("scoreReasons"))}
    parent_reasons = {str(reason) for reason in safe_list(parent.get("scoreReasons"))}
    matched = _matched_field_count(owner)
    total = _field_count(owner)
    if "complete-owner-module-field-signature" in reasons:
        return True
    if matched >= 3 and total and matched / total >= 0.5:
        return True
    if "matches-known-owner" in parent_reasons and int(parent.get("score") or 0) >= 80:
        return True
    return False


def summarize_root_signature_batch(batch: Mapping[str, Any]) -> dict[str, Any]:
    results = [safe_mapping(item) for item in safe_list(batch.get("results"))]
    high_signal = [item for item in results if _root_sweep_high_signal(item)]
    top_results: list[dict[str, Any]] = []
    for item in results[:8]:
        owner = safe_mapping(item.get("topOwnerFieldCandidate"))
        parent = safe_mapping(item.get("topParentSlotCandidate"))
        top_results.append(
            {
                "rva": item.get("rva"),
                "status": item.get("status"),
                "summaryJson": item.get("summaryJson"),
                "modulePointerHitCount": safe_mapping(item.get("counts")).get("modulePointerHitCount"),
                "topOwnerScore": owner.get("score"),
                "topOwnerBase": owner.get("ownerBase"),
                "topOwnerMatchedFields": _matched_field_count(owner),
                "topOwnerFieldCount": _field_count(owner),
                "topParentScore": parent.get("score"),
                "topParentSlot": parent.get("parentSlot"),
                "topParentOwnerPointer": parent.get("ownerPointer"),
                "warningCount": len(safe_list(item.get("warnings"))),
                "highSignal": _root_sweep_high_signal(item),
            }
        )
    selected_count = int(safe_mapping(batch.get("counts")).get("selectedRvaCount") or 0)
    result_count = int(safe_mapping(batch.get("counts")).get("resultCount") or len(results))
    classification = "not-run"
    if result_count and high_signal:
        classification = "root-candidate-leads-present"
    elif result_count:
        classification = "heap-ref-storage-only-no-parent-root"
    elif selected_count == 0:
        classification = "no-rvas-selected"
    return {
        "status": batch.get("status"),
        "path": safe_mapping(batch.get("artifacts")).get("summaryJson"),
        "generatedAtUtc": batch.get("generatedAtUtc"),
        "classification": classification,
        "selectedRvaCount": selected_count,
        "resultCount": result_count,
        "commandStatuses": safe_mapping(safe_mapping(batch.get("counts")).get("commandStatuses")),
        "highSignalResultCount": len(high_signal),
        "topResults": top_results,
        "blockers": safe_list(batch.get("blockers")),
        "warnings": safe_list(batch.get("warnings")),
        "candidateOnly": True,
        "promotionEligible": False,
    }


def summarize_static_access_chain(packet: Mapping[str, Any]) -> dict[str, Any]:
    constructor = safe_mapping(packet.get("constructorEvidence"))
    roots = [safe_mapping(item) for item in safe_list(constructor.get("candidateGlobalRoots"))]
    samples = [safe_mapping(item) for item in safe_list(packet.get("liveRootSamples"))]
    breadcrumbs = [safe_mapping(item) for item in safe_list(packet.get("callBreadcrumbs"))]
    classifications = sorted({str(item.get("classification")) for item in samples if item.get("classification")})
    return {
        "status": packet.get("status"),
        "verdict": packet.get("verdict"),
        "path": safe_mapping(packet.get("artifacts")).get("summaryJson"),
        "generatedAtUtc": packet.get("generatedAtUtc"),
        "functionRva": constructor.get("functionRva"),
        "fieldWriteCount": constructor.get("fieldWriteCount"),
        "fieldOffsets": safe_list(constructor.get("fieldOffsets")),
        "candidateGlobalRoots": roots[:8],
        "liveRootClassifications": classifications,
        "liveRootSamples": samples[:8],
        "callBreadcrumbDepth": len(breadcrumbs),
        "topCallBreadcrumbs": breadcrumbs[:6],
        "candidateOnly": True,
        "promotionEligible": False,
    }


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]


def filetime_to_iso(filetime: FILETIME) -> str:
    value = (int(filetime.dwHighDateTime) << 32) + int(filetime.dwLowDateTime)
    unix_seconds = (value - 116444736000000000) / 10000000
    return datetime.fromtimestamp(unix_seconds, UTC).isoformat()


def get_process_start_utc(handle: int) -> str | None:
    if sys.platform != "win32":
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create = FILETIME()
    exit_time = FILETIME()
    kernel = FILETIME()
    user = FILETIME()
    kernel32.GetProcessTimes.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
    ]
    kernel32.GetProcessTimes.restype = ctypes.c_bool
    if not kernel32.GetProcessTimes(ctypes.c_void_p(handle), ctypes.byref(create), ctypes.byref(exit_time), ctypes.byref(kernel), ctypes.byref(user)):
        return None
    return filetime_to_iso(create)


def live_owner_hypotheses(
    *,
    pid: int,
    hwnd: str,
    expected_process_start_utc: str | None,
    module_base: int,
    module_size: int,
    candidate_address: int,
    reference: Mapping[str, float] | None,
    tolerance: float,
    owner_window_bytes: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str], list[str]]:
    from scan_current_pid_coordinate_family import close_handle, open_process, read_memory, verify_hwnd_owner  # noqa: E402

    blockers: list[str] = []
    warnings: list[str] = []
    target = {
        "pid": pid,
        "hwnd": hwnd,
        "moduleBase": hex_int(module_base),
        "moduleSize": hex_int(module_size),
        "expectedProcessStartUtc": expected_process_start_utc,
    }
    hwnd_check = verify_hwnd_owner(hwnd, pid)
    target["hwndCheck"] = hwnd_check
    if not bool(hwnd_check.get("ownerMatchesExpectedPid")):
        blockers.append("pid-hwnd-mismatch")
        return target, [], blockers, warnings

    handle = open_process(pid)
    try:
        actual_start = get_process_start_utc(handle)
        target["actualProcessStartUtc"] = actual_start
        if expected_process_start_utc and actual_start:
            # The existing repo checks use sub-second tolerant string comparison;
            # here record a warning instead of failing on formatting precision.
            expected_prefix = expected_process_start_utc.replace("Z", "+00:00")[:19]
            if not actual_start.startswith(expected_prefix):
                blockers.append("process-start-mismatch")
        hypotheses: list[dict[str, Any]] = []
        for offset in OWNER_HYPOTHESIS_OFFSETS:
            owner_base = candidate_address - offset
            data = read_memory(handle, owner_base, owner_window_bytes)
            hypotheses.append(
                classify_owner_shape_from_bytes(
                    owner_base=owner_base,
                    offset_assumption=offset,
                    data=data,
                    module_base=module_base,
                    module_size=module_size,
                    reference=reference,
                    tolerance=tolerance,
                )
            )
    finally:
        close_handle(handle)
    hypotheses.sort(key=lambda item: (-int(item.get("score") or 0), str(item.get("ownerHypothesisAddress"))))
    return target, hypotheses, blockers, warnings


def build_markdown(summary: Mapping[str, Any]) -> str:
    paths = safe_mapping(summary.get("artifactInputs"))
    stale = safe_mapping(summary.get("staleStaticRoot"))
    candidate = safe_mapping(summary.get("coordinateCandidate"))
    game_epoch = safe_mapping(summary.get("gameEpoch"))
    lines = [
        "# Post-update owner/root rediscovery",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Verdict: `{summary.get('verdict')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Game manifest version: `{game_epoch.get('manifestVersion')}`",
        f"- Coordinate candidate: `{candidate.get('addressHex')}`",
        f"- Old static root verdict: `{stale.get('verdict')}` pointer `{stale.get('rootPointer')}`",
        "",
        "## Game/update epoch",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Manifest version | `{game_epoch.get('manifestVersion')}` |",
        f"| Manifest mtime UTC | `{game_epoch.get('manifestLastWriteTimeUtc')}` |",
        f"| `rift_x64.exe` manifest SHA1 | `{game_epoch.get('manifestRiftX64Sha1')}` |",
        f"| `rift_x64.exe` manifest size | `{game_epoch.get('manifestRiftX64Size')}` |",
        f"| `rift_x64.exe` mtime UTC | `{game_epoch.get('executableLastWriteTimeUtc')}` |",
        f"| `rift_x64.exe` size | `{game_epoch.get('executableLength')}` |",
        "",
        "## Artifact inputs",
        "",
    ]
    for key, value in paths.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Owner-shape hypotheses", "", "| Rank | Address | Offset | Score | Classification | Reasons |", "|---:|---|---:|---:|---|---|"])
    for index, item in enumerate(safe_list(summary.get("ownerShapeHypotheses"))[:8], start=1):
        row = safe_mapping(item)
        reasons = "; ".join(str(reason) for reason in safe_list(row.get("reasons")))
        lines.append(
            f"| {index} | `{row.get('ownerHypothesisAddress')}` | `{row.get('offsetAssumption')}` | "
            f"`{row.get('score')}` | `{row.get('classification')}` | {reasons} |"
        )
    lines.extend(["", "## Static clusters", "", "| Rank | Function RVA | Score | Offsets |", "|---:|---|---:|---|"])
    for index, row in enumerate(safe_list(summary.get("staticFieldClusters"))[:8], start=1):
        item = safe_mapping(row)
        lines.append(f"| {index} | `{item.get('functionStartRva')}` | `{item.get('score')}` | `{', '.join(safe_list(item.get('offsets')))}` |")
    lines.extend(["", "## Owner-batch module RVA hints", "", "| Rank | RVA | Hits | Owners |", "|---:|---|---:|---|"])
    owner_batch = safe_mapping(summary.get("ownerBatch"))
    for index, row in enumerate(safe_list(owner_batch.get("moduleRvaHints"))[:8], start=1):
        item = safe_mapping(row)
        lines.append(f"| {index} | `{item.get('rva')}` | `{item.get('ownerWindowHitCount')}` | `{', '.join(safe_list(item.get('owners')))}` |")
    seed = safe_mapping(summary.get("rootSignatureSeed"))
    if seed:
        lines.extend(
            [
                "",
                "## Root-signature seed",
                "",
                "| Field | Value |",
                "|---|---|",
                f"| Status | `{seed.get('status')}` |",
                f"| Owner base | `{seed.get('ownerBase')}` |",
                f"| Coord pointer | `{seed.get('coordPointer')}` |",
                f"| Owner module fields | `{seed.get('ownerModuleFieldCount')}` |",
            ]
        )
    root_batch = safe_mapping(summary.get("rootSignatureBatch"))
    if root_batch:
        lines.extend(
            [
                "",
                "## Root-signature batch sweep evidence",
                "",
                f"- Classification: `{root_batch.get('classification')}`",
                f"- Results: `{root_batch.get('resultCount')}`",
                f"- High-signal results: `{root_batch.get('highSignalResultCount')}`",
                "",
                "| RVA | Module hits | Owner score | Matched fields | Parent score | High signal |",
                "|---|---:|---:|---:|---:|---|",
            ]
        )
        for row in safe_list(root_batch.get("topResults"))[:8]:
            item = safe_mapping(row)
            matched = item.get("topOwnerMatchedFields")
            total = item.get("topOwnerFieldCount")
            lines.append(
                f"| `{item.get('rva')}` | `{item.get('modulePointerHitCount')}` | `{item.get('topOwnerScore')}` | "
                f"`{matched}/{total}` | `{item.get('topParentScore')}` | `{str(bool(item.get('highSignal'))).lower()}` |"
            )
    static_chain = safe_mapping(summary.get("staticAccessChain"))
    if static_chain:
        lines.extend(
            [
                "",
                "## Static access-chain packet",
                "",
                f"- Verdict: `{static_chain.get('verdict')}`",
                f"- Function RVA: `{static_chain.get('functionRva')}`",
                f"- Field writes: `{static_chain.get('fieldWriteCount')}`",
                f"- Live root classifications: `{', '.join(safe_list(static_chain.get('liveRootClassifications')))}`",
                "",
                "| Root RVA | Instruction | Classification |",
                "|---|---|---|",
            ]
        )
        samples_by_root = {
            str(safe_mapping(item).get("rootRva")): safe_mapping(item)
            for item in safe_list(static_chain.get("liveRootSamples"))
        }
        for row in safe_list(static_chain.get("candidateGlobalRoots"))[:8]:
            item = safe_mapping(row)
            sample = samples_by_root.get(str(item.get("globalRva")), {})
            lines.append(f"| `{item.get('globalRva')}` | `{item.get('instruction')}` | `{sample.get('classification')}` |")
    lines.extend(["", "## Blockers"])
    for blocker in safe_list(summary.get("blockers")):
        lines.append(f"- `{blocker}`")
    lines.extend(["", "## Recommended next action"])
    lines.append(str(safe_mapping(summary.get("next")).get("recommendedAction") or ""))
    lines.extend(["", "No input, movement, debugger/CE, truth update, provider write, or promotion was performed."])
    return "\n".join(lines).rstrip() + "\n"


def build_summary(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    repo_root = Path(args.repo_root).resolve() if args.repo_root else default_repo_root()
    rift_live_root = Path(args.rift_live_root).resolve() if args.rift_live_root else DEFAULT_RIFT_LIVE_ROOT
    latest = latest_artifact_paths(repo_root)
    candidate_path = resolve_path(repo_root, args.candidate_readback_json) or (Path(latest["candidateReadback"]) if latest["candidateReadback"] else None)
    static_readback_path = resolve_path(repo_root, args.static_readback_json) or (Path(latest["staticReadback"]) if latest["staticReadback"] else None)
    static_matrix_path = resolve_path(repo_root, args.static_field_matrix_json) or (Path(latest["staticFieldMatrix"]) if latest["staticFieldMatrix"] else None)
    ghidra_path = resolve_path(repo_root, args.ghidra_static_json) or (Path(latest["ghidraStatic"]) if latest["ghidraStatic"] else None)
    owner_batch_path = resolve_path(repo_root, args.owner_batch_json) or (Path(latest["ownerBatch"]) if latest["ownerBatch"] else None)
    root_signature_seed_path = resolve_path(repo_root, args.root_signature_seed_json) or (
        Path(latest["rootSignatureSeed"]) if latest["rootSignatureSeed"] else None
    )
    root_signature_batch_path = resolve_path(repo_root, args.root_signature_batch_json) or (
        Path(latest["rootSignatureBatch"]) if latest["rootSignatureBatch"] else None
    )
    static_access_chain_path = resolve_path(repo_root, args.static_access_chain_json) or (
        Path(latest["staticAccessChain"]) if latest["staticAccessChain"] else None
    )

    candidate_readback = load_json_object(candidate_path) or {}
    static_readback = load_json_object(static_readback_path) or {}
    static_matrix = load_json_object(static_matrix_path) or {}
    ghidra_static = load_json_object(ghidra_path) or {}
    owner_batch = load_json_object(owner_batch_path) or {}
    owner_batch_pointer_family_path = resolve_path(repo_root, safe_mapping(owner_batch.get("inputs")).get("pointerFamilySummary"))
    pointer_family_path = (
        resolve_path(repo_root, args.pointer_family_json)
        or owner_batch_pointer_family_path
        or (Path(latest["pointerFamily"]) if latest["pointerFamily"] else None)
    )
    pointer_family = load_json_object(pointer_family_path) or {}
    root_signature_seed = load_json_object(root_signature_seed_path) or {}
    root_signature_batch = load_json_object(root_signature_batch_path) or {}
    static_access_chain = load_json_object(static_access_chain_path) or {}

    candidate_address = parse_int(args.candidate_address) or candidate_address_from_readback(candidate_readback)
    reference = reference_from_readback(candidate_readback)
    module_base = (
        parse_int(args.module_base)
        or parse_int(safe_mapping(static_readback.get("target")).get("moduleBase"))
        or parse_int(safe_mapping(safe_mapping(pointer_family.get("target")).get("processDetails")).get("moduleBaseAddressHex"))
        or parse_int(safe_mapping(pointer_family.get("target")).get("moduleBaseAddressHex"))
    )
    module_size = parse_int(args.module_size) or DEFAULT_MODULE_SIZE
    pid = args.pid or parse_int(candidate_readback.get("processId") or candidate_readback.get("ProcessId"))
    hwnd = args.hwnd or candidate_readback.get("targetWindowHandle") or candidate_readback.get("TargetWindowHandle")
    expected_start = args.expected_process_start_utc or safe_mapping(static_readback.get("target")).get("expectedProcessStartUtc")

    blockers: list[str] = []
    warnings: list[str] = []
    game_epoch = read_game_epoch(rift_live_root)
    if game_epoch.get("status") != "passed":
        warnings.extend(f"game-epoch:{blocker}" for blocker in safe_list(game_epoch.get("blockers")))
    if not candidate_path:
        blockers.append("candidate-readback-missing")
    if not static_readback_path:
        blockers.append("static-readback-missing")
    if not static_matrix_path:
        warnings.append("static-field-matrix-missing")
    if not root_signature_seed_path:
        warnings.append("root-signature-seed-missing")
    if not root_signature_batch_path:
        warnings.append("root-signature-batch-missing")
    if not static_access_chain_path:
        warnings.append("postupdate-static-access-chain-missing")
    if not candidate_address:
        blockers.append("coordinate-candidate-address-missing")
    if not module_base:
        blockers.append("module-base-missing")

    stale_root = {
        "status": static_readback.get("status"),
        "verdict": static_readback.get("verdict"),
        "rootRva": safe_mapping(static_readback.get("reads")).get("rootRva") or safe_mapping(static_readback.get("candidate")).get("rootRva"),
        "rootAddress": safe_mapping(static_readback.get("reads")).get("rootAddress") or safe_mapping(static_readback.get("candidate")).get("rootAddress"),
        "rootPointer": safe_mapping(static_readback.get("reads")).get("rootPointer"),
        "generatedAtUtc": static_readback.get("generatedAtUtc"),
        "path": str(static_readback_path.resolve()) if static_readback_path else None,
    }
    if stale_root.get("verdict") == "root-pointer-null":
        blockers.append("old-static-root-null")

    owner_hypotheses: list[dict[str, Any]] = []
    target: dict[str, Any] = {
        "pid": pid,
        "hwnd": hwnd,
        "moduleBase": hex_int(module_base),
        "moduleSize": hex_int(module_size),
        "liveOwnerProbe": False,
    }
    if not args.artifact_only and pid and hwnd and candidate_address and module_base:
        live_target, owner_hypotheses, live_blockers, live_warnings = live_owner_hypotheses(
            pid=int(pid),
            hwnd=str(hwnd),
            expected_process_start_utc=str(expected_start) if expected_start else None,
            module_base=int(module_base),
            module_size=int(module_size),
            candidate_address=int(candidate_address),
            reference=reference,
            tolerance=float(args.tolerance),
            owner_window_bytes=int(args.owner_window_bytes),
        )
        target.update(live_target)
        target["liveOwnerProbe"] = True
        blockers.extend(live_blockers)
        warnings.extend(live_warnings)
    elif args.artifact_only:
        warnings.append("artifact-only-live-owner-shape-not-probed")
    else:
        blockers.append("live-owner-probe-missing-required-target-fields")

    owner_candidates = [
        item
        for item in owner_hypotheses
        if item.get("classification") in {"owner-shaped-candidate", "weak-owner-shape-candidate-needs-pointer-proof"}
    ]
    direct_copy_rejections = [
        item for item in owner_hypotheses if item.get("classification") == "direct-coordinate-copy-not-owner-shaped"
    ]
    if direct_copy_rejections and not owner_candidates:
        blockers.append("direct-coordinate-candidate-not-owner-shaped")
    if not owner_candidates:
        blockers.append("no-owner-root-hypothesis-yet")

    static_clusters = rank_static_clusters(static_matrix)
    pointer_family_summary = summarize_pointer_family(pointer_family)
    owner_batch_summary = summarize_owner_batch(owner_batch)
    root_signature_seed_summary = summarize_root_signature_seed(root_signature_seed)
    root_signature_batch_summary = summarize_root_signature_batch(root_signature_batch)
    static_access_chain_summary = summarize_static_access_chain(static_access_chain)
    ghidra_summary = safe_mapping(ghidra_static.get("evidenceSummary"))
    if root_signature_batch_summary.get("classification") == "heap-ref-storage-only-no-parent-root":
        blockers.append("root-signature-sweeps-found-no-parent-root-candidate")
    if "orientation-matrix-root-not-position-root" in safe_list(static_access_chain_summary.get("liveRootClassifications")):
        warnings.append("static-access-chain-root-orientation-only-not-position")

    status = "blocked" if blockers else "candidate"
    verdict = (
        "post-update-owner-root-rediscovery-needed"
        if blockers
        else "owner-root-candidate-ready-for-read-only-pointer-proof"
    )

    safety = base_safety()
    safety.update(
        {
            "targetMemoryBytesRead": bool(target.get("liveOwnerProbe")),
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
            "githubConnectorWrites": False,
        }
    )

    top_rvas = [str(item.get("rva")) for item in safe_list(owner_batch_summary.get("moduleRvaHints"))[:3] if item.get("rva")]
    if root_signature_batch_summary.get("classification") == "heap-ref-storage-only-no-parent-root":
        if static_access_chain_path:
            recommended = (
                "Stop repeating the same module-RVA root sweeps for this epoch; they reconfirm the heap/ref-storage island but found no parent/root candidate. "
                "The static access-chain packet found rift_x64+0x335F508, but current readback classifies it as orientation/matrix rather than world position. "
                "Continue caller-chain tracing above 0x13A37D0/0x13AFAD0/0x13B5E00 and run fresh read-only scans for the higher-level object that owns the world-coordinate copy."
            )
        else:
            recommended = (
                "Stop repeating the same module-RVA root sweeps for this epoch; they reconfirm the heap/ref-storage island but found no parent/root candidate. "
                "Shift to offline/static access-chain tracing around the 0x3F8B0 layout cluster and fresh broad family/container scans if a new seed appears."
            )
    elif blockers:
        recommended = (
            "Use the owner-batch module RVA hints as read-only root-signature sweep seeds, but first build/refresh a current root-signature packet; "
            "the old static root is null and the direct coordinate candidate is not old-owner-shaped."
        )
    else:
        recommended = "Run pointer-family/root-signature sweeps against the owner-shaped candidate, then require movement/restart proof before any promotion."
    if top_rvas:
        recommended += " Top current module RVA hints: " + ", ".join(top_rvas) + "."

    output_root = resolve_path(repo_root, args.output_root) if args.output_root else repo_root / "scripts" / "captures"
    output_dir = output_root / f"postupdate-owner-root-rediscovery-{utc_stamp()}"
    summary_json = output_dir / "summary.json"
    summary_md = output_dir / "summary.md"

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-postupdate-owner-root-rediscovery",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "verdict": verdict,
        "repoRoot": str(repo_root),
        "gameEpoch": game_epoch,
        "target": target,
        "artifactInputs": {
            "candidateReadback": str(candidate_path.resolve()) if candidate_path else None,
            "staticReadback": str(static_readback_path.resolve()) if static_readback_path else None,
            "staticFieldMatrix": str(static_matrix_path.resolve()) if static_matrix_path else None,
            "ghidraStatic": str(ghidra_path.resolve()) if ghidra_path else None,
            "pointerFamily": str(pointer_family_path.resolve()) if pointer_family_path else None,
            "ownerBatch": str(owner_batch_path.resolve()) if owner_batch_path else None,
            "rootSignatureSeed": str(root_signature_seed_path.resolve()) if root_signature_seed_path else None,
            "rootSignatureBatch": str(root_signature_batch_path.resolve()) if root_signature_batch_path else None,
            "staticAccessChain": str(static_access_chain_path.resolve()) if static_access_chain_path else None,
        },
        "coordinateCandidate": {
            "addressHex": hex_int(candidate_address),
            "reference": reference,
            "candidateId": best_candidate_from_readback(candidate_readback).get("candidateId"),
            "classification": best_candidate_from_readback(candidate_readback).get("classification"),
            "truthReadiness": best_candidate_from_readback(candidate_readback).get("truthReadiness"),
        },
        "staleStaticRoot": stale_root,
        "ownerShapeHypotheses": owner_hypotheses,
        "staticFieldClusters": static_clusters[:16],
        "ghidraStatic": {
            "status": ghidra_static.get("status"),
            "generatedAtUtc": ghidra_static.get("generatedAtUtc"),
            "rootReferenceCountCaptured": ghidra_summary.get("rootReferenceCountCaptured"),
            "instructionsScanned": ghidra_summary.get("instructionsScanned"),
            "warnings": ghidra_static.get("warnings"),
        },
        "pointerFamily": pointer_family_summary,
        "ownerBatch": owner_batch_summary,
        "rootSignatureSeed": root_signature_seed_summary,
        "rootSignatureBatch": root_signature_batch_summary,
        "staticAccessChain": static_access_chain_summary,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "safety": safety,
        "next": {
            "recommendedAction": recommended,
            "topReadOnlyCommands": [
                [
                    "python",
                    "scripts\\postupdate_static_access_chain.py",
                    "--json",
                ],
                [
                    "python",
                    "scripts\\postupdate_root_signature_seed.py",
                    "--from-owner-batch-summary",
                    str(owner_batch_path) if owner_batch_path else "<owner-batch-summary>",
                    "--json",
                ],
                [
                    "python",
                    "scripts\\pointer_owner_batch_inspector.py",
                    "--from-pointer-family-summary",
                    str(pointer_family_path) if pointer_family_path else "<pointer-family-summary>",
                    "--target-pid",
                    str(pid or "<pid>"),
                    "--target-hwnd",
                    str(hwnd or "<hwnd>"),
                    "--expected-module-base",
                    hex_int(module_base) or "<module-base>",
                    "--include-module-pointers",
                    "--json",
                ],
                [
                    "python",
                    "scripts\\root_signature_batch_sweep.py",
                    "--from-owner-batch-summary",
                    str(owner_batch_path) if owner_batch_path else "<owner-batch-summary>",
                    "--root-signature-json",
                    "<current-root-signature-summary.json>",
                    "--dry-run",
                    "--json",
                ],
            ],
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
    module_base = 0x7FF700000000
    module_size = 0x500000
    reference = {"x": 10.0, "y": 20.0, "z": 30.0}

    owner = bytearray(DEFAULT_OWNER_WINDOW_BYTES)
    owner[0:8] = (module_base + 0x1234).to_bytes(8, "little")
    struct.pack_into("<fff", owner, 0x320, 10.0, 20.0, 30.0)
    struct.pack_into("<fff", owner, 0x30C, 11.0, 20.0, 31.0)
    struct.pack_into("<f", owner, 0x300, 1.0)
    struct.pack_into("<f", owner, 0x304, 2.0)
    struct.pack_into("<f", owner, 0x438, 3.0)
    shaped = classify_owner_shape_from_bytes(
        owner_base=0x20000000,
        offset_assumption=0x320,
        data=bytes(owner),
        module_base=module_base,
        module_size=module_size,
        reference=reference,
        tolerance=0.25,
    )

    direct = bytearray(DEFAULT_OWNER_WINDOW_BYTES)
    struct.pack_into("<fff", direct, 0x320, 10.0, 20.0, 30.0)
    direct_copy = classify_owner_shape_from_bytes(
        owner_base=0x30000000,
        offset_assumption=0x320,
        data=bytes(direct),
        module_base=module_base,
        module_size=module_size,
        reference=reference,
        tolerance=0.25,
    )

    matrix = {
        "offsetHits": {
            "0x320": [{"linearFunctionStartRva": "0x3F8B0", "operandAccess": "write", "instruction": "mov", "rva": "0x1"}],
            "0x324": [{"linearFunctionStartRva": "0x3F8B0", "operandAccess": "write", "instruction": "mov", "rva": "0x2"}],
            "0x30C": [{"linearFunctionStartRva": "0x3F8B0", "operandAccess": "write", "instruction": "mov", "rva": "0x3"}],
        }
    }
    clusters = rank_static_clusters(matrix)
    passed = (
        shaped["classification"] == "owner-shaped-candidate"
        and direct_copy["classification"] == "direct-coordinate-copy-not-owner-shaped"
        and clusters
        and clusters[0]["functionStartRva"] == "0x3F8B0"
    )
    return {
        "status": "passed" if passed else "failed",
        "shapedClassification": shaped["classification"],
        "directCopyClassification": direct_copy["classification"],
        "topCluster": clusters[0] if clusters else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="No-input post-update owner/root rediscovery status helper.")
    parser.add_argument("--repo-root")
    parser.add_argument("--rift-live-root", default=str(DEFAULT_RIFT_LIVE_ROOT))
    parser.add_argument("--pid", type=int)
    parser.add_argument("--hwnd")
    parser.add_argument("--expected-process-start-utc")
    parser.add_argument("--module-base")
    parser.add_argument("--module-size", default=hex(DEFAULT_MODULE_SIZE))
    parser.add_argument("--candidate-address")
    parser.add_argument("--candidate-readback-json")
    parser.add_argument("--static-readback-json")
    parser.add_argument("--static-field-matrix-json")
    parser.add_argument("--ghidra-static-json")
    parser.add_argument("--pointer-family-json")
    parser.add_argument("--owner-batch-json")
    parser.add_argument("--root-signature-seed-json")
    parser.add_argument("--root-signature-batch-json")
    parser.add_argument("--static-access-chain-json")
    parser.add_argument("--output-root")
    parser.add_argument("--owner-window-bytes", type=lambda value: int(value, 0), default=DEFAULT_OWNER_WINDOW_BYTES)
    parser.add_argument("--tolerance", type=float, default=0.25)
    parser.add_argument("--artifact-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        result = self_test()
        if args.json:
            print(json.dumps(result, separators=(",", ":")))
        else:
            print(result["status"])
        return 0 if result["status"] == "passed" else 1
    summary, exit_code = build_summary(args)
    if args.json:
        print(
            json.dumps(
                {
                    "status": summary.get("status"),
                    "verdict": summary.get("verdict"),
                    "summaryJson": safe_mapping(summary.get("artifacts")).get("summaryJson"),
                    "coordinateCandidate": summary.get("coordinateCandidate"),
                    "gameEpoch": summary.get("gameEpoch"),
                    "topOwnerHypothesis": (safe_list(summary.get("ownerShapeHypotheses")) or [None])[0],
                    "topStaticCluster": (safe_list(summary.get("staticFieldClusters")) or [None])[0],
                    "ownerBatchModuleRvaHints": safe_list(safe_mapping(summary.get("ownerBatch")).get("moduleRvaHints"))[:5],
                    "rootSignatureBatch": summary.get("rootSignatureBatch"),
                    "staticAccessChain": summary.get("staticAccessChain"),
                    "blockers": summary.get("blockers"),
                    "warnings": summary.get("warnings"),
                },
                separators=(",", ":"),
            )
        )
    else:
        print(f"{summary.get('status')}: {safe_mapping(summary.get('artifacts')).get('summaryJson')}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
