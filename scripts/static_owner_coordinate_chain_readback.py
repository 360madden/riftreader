#!/usr/bin/env python3
"""Read or poll the promoted static owner-coordinate resolver.

Resolver chain:
    [rift_x64 + 0x32EBC80] + 0x320/+0x324/+0x328

This helper is read-only. It can produce a one-shot readback or a short
navigation-grade polling baseline with timestamps, deltas, speed, jump/stale
checks, and exact HWND/PID checks around each read. It does not send input,
attach a debugger, use Cheat Engine, write target memory, or promote facing / a
full actor chain.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import struct
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rift_live_test.current_pid_family_neighborhood_inspector import close_handle, open_process_for_read, read_memory, verify_hwnd_owner
from workflow_common import load_json_object, repo_root, safe_mapping, utc_iso, utc_stamp

DEFAULT_ROOT_RVA = 0x32EBC80
DEFAULT_COORD_OFFSET = 0x320
DEFAULT_MAX_PLANAR_JUMP_PER_SAMPLE = 25.0
DEFAULT_MAX_SAMPLE_GAP_SECONDS = 2.0
DEFAULT_MAX_STATIONARY_PLANAR_DRIFT = 0.5
DEFAULT_TURN_RATE_THRESHOLD = 0.35
DEFAULT_FACING_TARGET_ZERO_EPSILON = 0.001
FILETIME_UNIX_EPOCH_100NS = 116444736000000000


def int_hex(value: int | None) -> str | None:
    return None if value is None else f"0x{int(value):X}"


def qword(data: bytes, offset: int = 0) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def triplet(data: bytes, offset: int = 0) -> dict[str, float]:
    x, y, z = struct.unpack_from("<fff", data, offset)
    return {"x": float(x), "y": float(y), "z": float(z)}


def triplet_is_zero(vec: dict[str, float], *, epsilon: float = DEFAULT_FACING_TARGET_ZERO_EPSILON) -> bool:
    """Check whether a coordinate triplet is effectively the zero vector."""
    return abs(vec["x"]) < epsilon and abs(vec["y"]) < epsilon and abs(vec["z"]) < epsilon


def unpack_float_safe(data: bytes, offset: int) -> float | None:
    """Unpack a single float, returning None if non-finite or out of bounds."""
    try:
        value = struct.unpack_from("<f", data, offset)[0]
    except (struct.error, IndexError):
        return None
    if not math.isfinite(value) or abs(value) >= 1_000_000:
        return None
    return float(value)



def nav_state_from_owner_bytes(
    data: bytes,
    *,
    owner_address: int,
    coord_offset: int = DEFAULT_COORD_OFFSET,
) -> dict[str, Any]:
    """Extract full navigation state from owner window bytes.

    Reads position at coord_offset, facing target at coord_offset - 0x14
    (i.e. 0x30C when coord_offset is 0x320), and turn rate at
    coord_offset - 0x1C (i.e. 0x304).  Computes yaw via atan2 from the
    vector between position and facing target.

    This is a read-only derivation; it does not promote facing or grant
    navigation control authority.

    Returns a dict with "navStateError" if the data is unreadable
    (e.g. non-finite coordinates or offset underrun).
    """
    if coord_offset < 0x1C:
        return {"navStateError": "coord-offset-too-small-for-nav-derivation", "coordOffset": int_hex(coord_offset)}
    position = triplet(data, coord_offset)
    if not all(math.isfinite(v) for v in position.values()):
        return {"navStateError": "non-finite-position-coordinate", "coordinate": position}
    facing_offset = coord_offset - 0x14
    turn_rate_offset = coord_offset - 0x1C
    facing_target = triplet(data, facing_offset)
    if not all(math.isfinite(v) for v in facing_target.values()):
        return {"navStateError": "non-finite-facing-target-coordinate", "facingTargetCoordinate": facing_target}
    if triplet_is_zero(facing_target):
        return {"navStateError": "facing-target-zero-vector", "facingTargetCoordinate": facing_target}

    dx = facing_target["x"] - position["x"]
    dy = facing_target["y"] - position["y"]
    dz = facing_target["z"] - position["z"]
    planar = math.hypot(dx, dz)
    distance = math.sqrt((dx * dx) + (dy * dy) + (dz * dz))

    yaw = math.degrees(math.atan2(dz, dx))
    pitch = math.degrees(math.atan2(dy, planar)) if planar else 0.0

    turn_rate = unpack_float_safe(data, turn_rate_offset)
    turn_direction = "unknown"
    turning = False
    if turn_rate is not None:
        if turn_rate > DEFAULT_TURN_RATE_THRESHOLD:
            turn_direction = "left"
            turning = True
        elif turn_rate < -DEFAULT_TURN_RATE_THRESHOLD:
            turn_direction = "right"
            turning = True
        else:
            turn_direction = "stationary"

    return {
        "ownerAddress": int_hex(owner_address),
        "coordinate": position,
        "facingTargetCoordinate": facing_target,
        "facingVector": {"x": dx, "y": dy, "z": dz},
        "yawDegrees": yaw,
        "pitchDegrees": pitch,
        "planarLookaheadDistance": planar,
        "lookaheadDistance3d": distance,
        "turnRate0x304": turn_rate,
        "turnRateClassification": turn_direction,
        "turnRateTurning": turning,
        "positionOffset": int_hex(coord_offset),
        "facingTargetOffset": int_hex(facing_offset),
        "turnRateOffset": int_hex(turn_rate_offset),
    }


def first_nonempty(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("th32ModuleID", ctypes.c_uint32),
        ("th32ProcessID", ctypes.c_uint32),
        ("GlblcntUsage", ctypes.c_uint32),
        ("ProccntUsage", ctypes.c_uint32),
        ("modBaseAddr", ctypes.c_void_p),
        ("modBaseSize", ctypes.c_uint32),
        ("hModule", ctypes.c_void_p),
        ("szModule", ctypes.c_char * 256),
        ("szExePath", ctypes.c_char * 260),
    ]


def get_live_module_base(pid: int, module_name: str = "rift_x64.exe") -> int | None:
    """Enumerate modules in the target process and return the base address
    of the named module, or None if not found or enumeration failed.

    Uses CreateToolhelp32Snapshot + Module32First/Module32Next.
    This is read-only — no debugger attach, no target memory write.
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    TH32CS_SNAPMODULE = 0x00000008
    h_snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, ctypes.c_uint32(pid))
    if h_snap == -1 or h_snap is None:
        return None
    try:
        me = MODULEENTRY32()
        me.dwSize = ctypes.sizeof(MODULEENTRY32)
        if not kernel32.Module32First(h_snap, ctypes.byref(me)):
            return None
        target_lower = module_name.lower()
        while True:
            name = me.szModule.decode("utf-8", errors="replace")
            if name.lower() == target_lower:
                base = me.modBaseAddr
                return int(base) if base is not None else None
            if not kernel32.Module32Next(h_snap, ctypes.byref(me)):
                break
        return None
    finally:
        kernel32.CloseHandle(h_snap)


def filetime_to_datetime(value: FILETIME) -> datetime:
    raw = (int(value.dwHighDateTime) << 32) + int(value.dwLowDateTime)
    unix_seconds = (raw - FILETIME_UNIX_EPOCH_100NS) / 10_000_000
    return datetime.fromtimestamp(unix_seconds, UTC)


def get_process_creation_time_utc(handle: int) -> str:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetProcessTimes.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
    ]
    kernel32.GetProcessTimes.restype = ctypes.c_bool
    created = FILETIME()
    exited = FILETIME()
    kernel = FILETIME()
    user = FILETIME()
    ok = bool(kernel32.GetProcessTimes(ctypes.c_void_p(handle), ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)))
    if not ok:
        raise RuntimeError(f"GetProcessTimes failed:{ctypes.get_last_error()}")
    return filetime_to_datetime(created).isoformat()


def parse_utc_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if "." in text:
        prefix, suffix = text.split(".", 1)
        tz = ""
        if "+" in suffix:
            frac, tz = suffix.split("+", 1)
            tz = "+" + tz
        elif "-" in suffix:
            frac, tz = suffix.split("-", 1)
            tz = "-" + tz
        else:
            frac = suffix
        if len(frac) > 6:
            text = f"{prefix}.{frac[:6]}{tz}"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def process_start_check(actual_utc: str, expected_utc: Any, *, tolerance_seconds: float) -> dict[str, Any]:
    actual = parse_utc_datetime(actual_utc)
    expected = parse_utc_datetime(expected_utc)
    if expected is None:
        return {
            "status": "not-requested",
            "actualProcessStartUtc": actual_utc,
            "expectedProcessStartUtc": expected_utc,
            "matchesExpected": None,
        }
    if actual is None:
        return {
            "status": "actual-unparseable",
            "actualProcessStartUtc": actual_utc,
            "expectedProcessStartUtc": expected_utc,
            "matchesExpected": False,
        }
    delta = abs((actual - expected).total_seconds())
    return {
        "status": "passed" if delta <= tolerance_seconds else "mismatch",
        "actualProcessStartUtc": actual_utc,
        "expectedProcessStartUtc": expected_utc,
        "deltaSeconds": delta,
        "toleranceSeconds": tolerance_seconds,
        "matchesExpected": delta <= tolerance_seconds,
    }


def load_current_truth_defaults(root: Path, truth_json: str) -> dict[str, Any]:
    truth_path = Path(truth_json)
    if not truth_path.is_absolute():
        truth_path = root / truth_path
    truth = load_json_object(truth_path)
    target = safe_mapping(truth.get("target"))
    static_status = safe_mapping(truth.get("staticChainStatus"))
    primary = safe_mapping(static_status.get("primaryCandidate"))
    best = safe_mapping(truth.get("bestCurrentCandidate"))
    return {
        "path": str(truth_path),
        "processName": first_nonempty(target.get("processName"), "rift_x64"),
        "pid": first_nonempty(target.get("processId"), target.get("pid")),
        "hwnd": first_nonempty(target.get("targetWindowHandle"), target.get("hwnd")),
        "processStartUtc": target.get("processStartUtc"),
        "moduleBase": target.get("moduleBase"),
        "rootRva": first_nonempty(primary.get("rootRva"), best.get("rootRva")),
        "coordOffset": first_nonempty(primary.get("coordinateOffset"), best.get("coordinateOffset"), hex(DEFAULT_COORD_OFFSET)),
        "staticResolverStatus": static_status.get("status"),
        "promotionAllowed": bool(static_status.get("promotionAllowed")),
        "chain": first_nonempty(primary.get("chain"), best.get("chain"), "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328"),
    }


def coordinate_delta(left: Mapping[str, float], right: Mapping[str, float]) -> dict[str, float]:
    dx = float(right["x"]) - float(left["x"])
    dy = float(right["y"]) - float(left["y"])
    dz = float(right["z"]) - float(left["z"])
    return {
        "x": dx,
        "y": dy,
        "z": dz,
        "planarXz": math.hypot(dx, dz),
        "distance3d": math.sqrt((dx * dx) + (dy * dy) + (dz * dz)),
    }


def build_poll_analysis(
    samples: list[Mapping[str, Any]],
    *,
    max_planar_jump_per_sample: float,
    max_sample_gap_seconds: float,
    expect_stationary: bool,
    max_stationary_planar_drift: float,
) -> dict[str, Any]:
    transitions: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    max_planar_delta = 0.0
    max_distance3d = 0.0
    max_speed_planar = 0.0
    owner_changed_count = 0
    jump_count = 0
    stale_gap_count = 0

    for index in range(1, len(samples)):
        previous = safe_mapping(samples[index - 1])
        current = safe_mapping(samples[index])
        previous_coord = safe_mapping(previous.get("coordinate"))
        current_coord = safe_mapping(current.get("coordinate"))
        elapsed_delta = None
        if previous.get("elapsedSeconds") is not None and current.get("elapsedSeconds") is not None:
            elapsed_delta = float(current["elapsedSeconds"]) - float(previous["elapsedSeconds"])
        owner_changed = bool(previous.get("ownerAddress") != current.get("ownerAddress"))
        if owner_changed:
            owner_changed_count += 1
        transition: dict[str, Any] = {
            "fromSample": previous.get("sampleIndex"),
            "toSample": current.get("sampleIndex"),
            "elapsedSeconds": elapsed_delta,
            "ownerChanged": owner_changed,
            "ownerAddressBefore": previous.get("ownerAddress"),
            "ownerAddressAfter": current.get("ownerAddress"),
        }
        if previous_coord and current_coord:
            delta = coordinate_delta(previous_coord, current_coord)
            speed_planar = delta["planarXz"] / elapsed_delta if elapsed_delta and elapsed_delta > 0 else None
            max_planar_delta = max(max_planar_delta, delta["planarXz"])
            max_distance3d = max(max_distance3d, delta["distance3d"])
            if speed_planar is not None:
                max_speed_planar = max(max_speed_planar, speed_planar)
            transition.update({"delta": delta, "speedPlanarPerSecond": speed_planar})
            if delta["planarXz"] > max_planar_jump_per_sample:
                jump_count += 1
                transition["jumpExceeded"] = True
        if elapsed_delta is not None and elapsed_delta > max_sample_gap_seconds:
            stale_gap_count += 1
            transition["sampleGapExceeded"] = True
        transitions.append(transition)

    if owner_changed_count:
        blockers.append(f"owner-address-changed-during-poll:{owner_changed_count}")
    if jump_count:
        blockers.append(f"coordinate-jump-threshold-exceeded:{jump_count}")
    if stale_gap_count:
        blockers.append(f"sample-gap-threshold-exceeded:{stale_gap_count}")
    if expect_stationary and max_planar_delta > max_stationary_planar_drift:
        blockers.append(f"stationary-baseline-drift-too-large:{max_planar_delta:.6f}>{max_stationary_planar_drift:.6f}")
    if len(samples) < 2:
        warnings.append("single-sample-readback-no-polling-deltas")

    return {
        "sampleCount": len(samples),
        "transitionCount": len(transitions),
        "maxPlanarDelta": max_planar_delta,
        "maxDistance3d": max_distance3d,
        "maxSpeedPlanarPerSecond": max_speed_planar,
        "ownerChangedCount": owner_changed_count,
        "jumpCount": jump_count,
        "staleGapCount": stale_gap_count,
        "expectStationary": expect_stationary,
        "maxStationaryPlanarDrift": max_stationary_planar_drift,
        "transitions": transitions,
        "blockers": blockers,
        "warnings": warnings,
    }


def read_chain_sample(
    *,
    handle: int,
    module_base: int,
    root_address: int,
    coord_offset: int,
    expected_anchor: int | None,
    include_nav_state: bool = False,
) -> dict[str, Any]:
    owner_address = qword(read_memory(handle, root_address, 8))
    owner_window = read_memory(handle, owner_address, max(0x380, coord_offset + 12))
    coordinate = triplet(owner_window, coord_offset)
    owner_vtable = qword(owner_window, 0)
    reads: dict[str, Any] = {
        "ownerAddress": int_hex(owner_address),
        "ownerVtable": int_hex(owner_vtable),
        "ownerVtableRva": int_hex(owner_vtable - module_base) if module_base <= owner_vtable < module_base + 0x4000000 else None,
        "coordinate": coordinate,
        "ownerPreviewQwords": [int_hex(qword(owner_window, off)) for off in range(0, 0x90, 8)],
    }
    if expected_anchor is not None:
        proof = triplet(read_memory(handle, expected_anchor, 12))
        reads["expectedProofAnchorCoordinate"] = proof
        reads["deltasVsExpectedProofAnchor"] = {axis: abs(coordinate[axis] - proof[axis]) for axis in ("x", "y", "z")}
    if include_nav_state:
        reads["navState"] = nav_state_from_owner_bytes(owner_window, owner_address=owner_address, coord_offset=coord_offset)
    return reads


def build_markdown(summary: dict[str, Any]) -> str:
    reads = summary.get("reads") if isinstance(summary.get("reads"), dict) else {}
    nav_state = safe_mapping(reads.get("navState"))
    polling = safe_mapping(summary.get("polling"))
    analysis = safe_mapping(summary.get("analysis"))
    safety = safe_mapping(summary.get("safety"))
    lines = [
        "# Static owner-coordinate resolver readback",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        f"Verdict: `{summary.get('verdict')}`",
        "",
        "## Chain",
        "",
        "`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`",
        "",
        "## Latest result",
        "",
        f"- Owner address: `{reads.get('ownerAddress')}`",
        f"- Owner vtable: `{reads.get('ownerVtable')}`",
        f"- Coordinate: `{reads.get('coordinate')}`",
        f"- Proof-anchor deltas: `{reads.get('deltasVsExpectedProofAnchor')}`",
    ]
    if nav_state:
        if nav_state.get("navStateError"):
            lines.extend([
                "",
                "## Navigation state (derivation failed)",
                "",
                f"- Error: `{nav_state['navStateError']}`",
            ])
        else:
            lines.extend([
                "",
                "## Navigation state (derived from owner window)",
                "",
                f"- Yaw: `{nav_state.get('yawDegrees')}` deg",
                f"- Pitch: `{nav_state.get('pitchDegrees')}` deg",
                f"- Facing target: `{nav_state.get('facingTargetCoordinate')}`",
                f"- Facing vector: `{nav_state.get('facingVector')}`",
                f"- Planar lookahead: `{nav_state.get('planarLookaheadDistance')}`",
                f"- Turn rate (0x304): `{nav_state.get('turnRate0x304')}`",
                f"- Turn classification: `{nav_state.get('turnRateClassification')}`",
                "",
                "Candidate readback only — not promoted facing/navigation control.",
            ])
    lines.extend([
        "",
        "## Polling analysis",
        "",
        f"- Samples: `{analysis.get('sampleCount')}` requested `{polling.get('requestedSampleCount')}`",
        f"- Interval seconds: `{polling.get('intervalSeconds')}`",
        f"- Max planar delta: `{analysis.get('maxPlanarDelta')}`",
        f"- Max planar speed/s: `{analysis.get('maxSpeedPlanarPerSecond')}`",
        f"- Owner changed count: `{analysis.get('ownerChangedCount')}`",
        f"- Jump count: `{analysis.get('jumpCount')}`",
        f"- Stale gap count: `{analysis.get('staleGapCount')}`",
    ])
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{blocker}`" for blocker in summary.get("blockers", []))
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{warning}`" for warning in summary.get("warnings", []))
    lines.extend(
        [
            "",
            "## Safety",
            "",
            f"- Movement sent: `{str(safety.get('movementSent')).lower()}`",
            f"- Input sent: `{str(safety.get('inputSent')).lower()}`",
            f"- Cheat Engine used: `{str(not safety.get('noCheatEngine')).lower()}`",
            f"- Target memory written: `{str(safety.get('targetMemoryBytesWritten')).lower()}`",
            "",
            "Readback/polling only. This does not promote facing, full actor/stat chain, ProofOnly, or movement control.",
        ]
    )
    return "\n".join(lines) + "\n"


def apply_current_truth_defaults(args: argparse.Namespace, root: Path) -> dict[str, Any] | None:
    if not args.use_current_truth:
        return None
    defaults = load_current_truth_defaults(root, args.current_truth_json)
    if args.process_name == "rift_x64" and defaults.get("processName"):
        args.process_name = str(defaults["processName"]).removesuffix(".exe")
    if args.pid is None and defaults.get("pid") is not None:
        args.pid = int(defaults["pid"])
    if not args.hwnd and defaults.get("hwnd"):
        args.hwnd = str(defaults["hwnd"])
    if not args.module_base and defaults.get("moduleBase"):
        args.module_base = str(defaults["moduleBase"])
    if not args.expected_process_start_utc and defaults.get("processStartUtc"):
        args.expected_process_start_utc = str(defaults["processStartUtc"])
    if args.root_rva == hex(DEFAULT_ROOT_RVA) and defaults.get("rootRva"):
        args.root_rva = str(defaults["rootRva"])
    if args.coord_offset == hex(DEFAULT_COORD_OFFSET) and defaults.get("coordOffset"):
        args.coord_offset = str(defaults["coordOffset"])
    return defaults


def validate_args(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if args.pid is None:
        errors.append("pid-required")
    if not args.hwnd:
        errors.append("hwnd-required")
    if not args.module_base:
        errors.append("module-base-required")
    if args.samples < 1:
        errors.append("samples-must-be-positive")
    if args.interval_seconds < 0:
        errors.append("interval-seconds-must-be-nonnegative")
    if args.max_planar_jump_per_sample < 0:
        errors.append("max-planar-jump-per-sample-must-be-nonnegative")
    if args.max_sample_gap_seconds <= 0:
        errors.append("max-sample-gap-seconds-must-be-positive")
    if args.max_stationary_planar_drift < 0:
        errors.append("max-stationary-planar-drift-must-be-nonnegative")
    if args.process_start_tolerance_seconds < 0:
        errors.append("process-start-tolerance-seconds-must-be-nonnegative")
    return errors


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    current_truth_defaults = apply_current_truth_defaults(args, root)
    argument_errors = validate_args(args)
    out_dir = (Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures") / f"static-owner-coordinate-chain-readback-{utc_stamp()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    if argument_errors:
        return {
            "schemaVersion": 2,
            "mode": "static-owner-coordinate-resolver-readback",
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "verdict": "invalid-arguments",
            "target": {},
            "candidate": {},
            "reads": {},
            "samples": [],
            "analysis": {},
            "blockers": [],
            "warnings": [],
            "errors": argument_errors,
            "safety": base_safety(),
            "artifacts": {"outputDir": str(out_dir), "summaryJson": str(out_dir / "summary.json"), "summaryMarkdown": str(out_dir / "summary.md")},
        }

    module_base = int(args.module_base, 0)
    root_rva = int(args.root_rva, 0)
    coord_offset = int(args.coord_offset, 0)
    expected_anchor = int(args.expected_proof_anchor, 0) if args.expected_proof_anchor else None
    root_address = module_base + root_rva
    summary: dict[str, Any] = {
        "schemaVersion": 2,
        "mode": "static-owner-coordinate-resolver-readback",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "verdict": None,
        "target": {
            "processName": args.process_name,
            "processId": int(args.pid),
            "targetWindowHandle": args.hwnd,
            "expectedProcessStartUtc": args.expected_process_start_utc,
            "moduleBase": int_hex(module_base),
            "currentTruthPath": current_truth_defaults.get("path") if current_truth_defaults else None,
        },
        "candidate": {
            "rootModule": "rift_x64.exe",
            "rootRva": int_hex(root_rva),
            "rootAddress": int_hex(root_address),
            "coordinateOffset": int_hex(coord_offset),
            "chain": "[rift_x64+0x32EBC80]+0x320/+0x324/+0x328",
            "historicalTemplateMatch": "owner+0x320/+0x324/+0x328",
            "expectedProofAnchor": int_hex(expected_anchor),
            "currentTruthStaticResolverStatus": current_truth_defaults.get("staticResolverStatus") if current_truth_defaults else None,
            "currentTruthPromotionAllowed": current_truth_defaults.get("promotionAllowed") if current_truth_defaults else None,
        },
        "polling": {
            "requestedSampleCount": int(args.samples),
            "intervalSeconds": float(args.interval_seconds),
            "maxPlanarJumpPerSample": float(args.max_planar_jump_per_sample),
            "maxSampleGapSeconds": float(args.max_sample_gap_seconds),
            "expectStationary": bool(args.expect_stationary),
            "maxStationaryPlanarDrift": float(args.max_stationary_planar_drift),
            "exactHwndPidCheckPerSample": True,
        },
        "reads": {},
        "samples": [],
        "analysis": {},
        "blockers": [],
        "warnings": [],
        "errors": [],
        "safety": base_safety(),
        "artifacts": {"outputDir": str(out_dir), "summaryJson": str(out_dir / "summary.json"), "summaryMarkdown": str(out_dir / "summary.md")},
    }
    hwnd_check = verify_hwnd_owner(args.hwnd, int(args.pid))
    summary["target"]["hwndCheck"] = hwnd_check
    if not hwnd_check.get("ownerMatchesExpectedPid"):
        summary["status"] = "blocked"
        summary["verdict"] = "target-hwnd-pid-mismatch"
        summary["blockers"].append("target-hwnd-pid-mismatch")
        return summary

    handle = open_process_for_read(int(args.pid))
    start = time.perf_counter()
    try:
        actual_process_start_utc = get_process_creation_time_utc(handle)
        summary["target"]["actualProcessStartUtc"] = actual_process_start_utc
        summary["target"]["processStartCheck"] = process_start_check(
            actual_process_start_utc,
            args.expected_process_start_utc,
            tolerance_seconds=float(args.process_start_tolerance_seconds),
        )
        if summary["target"]["processStartCheck"].get("matchesExpected") is False:
            summary["status"] = "blocked"
            summary["verdict"] = "target-process-start-mismatch"
            summary["blockers"].append("target-process-start-mismatch")
            return summary

        # Module base freshness gate — prevent silent garbage reads from stale config.
        live_base = get_live_module_base(int(args.pid), f"{args.process_name}.exe")
        summary["target"]["moduleBaseCheck"] = {
            "liveModuleBase": int_hex(live_base),
            "storedModuleBase": int_hex(module_base),
        }
        if live_base is None:
            summary["target"]["moduleBaseCheck"]["status"] = "failed-enumeration"
            summary["status"] = "blocked"
            summary["verdict"] = "module-base-enumeration-failed"
            summary["blockers"].append("module-base-enumeration-failed")
            return summary
        if live_base != module_base:
            summary["target"]["moduleBaseCheck"]["status"] = "mismatch"
            summary["target"]["moduleBaseCheck"]["delta"] = int_hex(live_base - module_base)
            summary["status"] = "blocked"
            summary["verdict"] = "module-base-mismatch"
            summary["blockers"].append(f"module-base-mismatch:live={int_hex(live_base)}-stored={int_hex(module_base)}")
            return summary
        summary["target"]["moduleBaseCheck"]["status"] = "passed"

        for sample_index in range(int(args.samples)):
            sample_check = verify_hwnd_owner(args.hwnd, int(args.pid))
            sample: dict[str, Any] = {
                "sampleIndex": sample_index,
                "sampledAtUtc": utc_iso(),
                "elapsedSeconds": time.perf_counter() - start,
                "hwndCheck": sample_check,
            }
            if not sample_check.get("ownerMatchesExpectedPid"):
                sample["status"] = "blocked"
                sample["blocker"] = "target-hwnd-pid-mismatch-during-poll"
                summary["samples"].append(sample)
                summary["blockers"].append("target-hwnd-pid-mismatch-during-poll")
                break
            reads = read_chain_sample(
                handle=handle,
                module_base=module_base,
                root_address=root_address,
                coord_offset=coord_offset,
                expected_anchor=expected_anchor,
                include_nav_state=bool(args.nav_state),
            )
            sample.update(
                {
                    "status": "passed",
                    "ownerAddress": reads.get("ownerAddress"),
                    "ownerVtable": reads.get("ownerVtable"),
                    "ownerVtableRva": reads.get("ownerVtableRva"),
                    "coordinate": reads.get("coordinate"),
                    "deltasVsExpectedProofAnchor": reads.get("deltasVsExpectedProofAnchor"),
                }
            )
            summary["reads"] = reads
            summary["samples"].append(sample)
            if sample_index < int(args.samples) - 1 and args.interval_seconds > 0:
                time.sleep(float(args.interval_seconds))
        summary["analysis"] = build_poll_analysis(
            summary["samples"],
            max_planar_jump_per_sample=float(args.max_planar_jump_per_sample),
            max_sample_gap_seconds=float(args.max_sample_gap_seconds),
            expect_stationary=bool(args.expect_stationary),
            max_stationary_planar_drift=float(args.max_stationary_planar_drift),
        )
        summary["blockers"].extend(summary["analysis"].get("blockers", []))
        summary["warnings"].extend(summary["analysis"].get("warnings", []))
        if expected_anchor is None:
            summary["warnings"].append("proof-anchor-comparison-not-requested")
        if bool(args.nav_state):
            nav_error = safe_mapping(summary.get("reads", {}).get("navState", {})).get("navStateError")
            if nav_error:
                summary["warnings"].append(f"nav-state-derivation-error:{nav_error}")
        max_delta = max(summary.get("reads", {}).get("deltasVsExpectedProofAnchor", {"x": 0, "y": 0, "z": 0}).values())
        if summary["blockers"]:
            summary["status"] = "blocked"
            summary["verdict"] = "resolver-polling-safety-gate-blocked"
        elif expected_anchor is None or max_delta <= float(args.tolerance):
            summary["status"] = "passed"
            summary["verdict"] = "promoted-static-coordinate-resolver-readback-passed"
            summary["classification"] = "static-coordinate-resolver-current-position-source"
            summary["warnings"].append("readback-only-not-facing-or-actor-stat-promotion")
        else:
            summary["status"] = "blocked"
            summary["verdict"] = "coordinate-mismatch-vs-expected-proof-anchor"
            summary["blockers"].append("coordinate-mismatch-vs-expected-proof-anchor")
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["verdict"] = "readback-error"
        summary["errors"].append(f"{type(exc).__name__}:{exc}")
    finally:
        close_handle(handle)
    summary["warnings"] = sorted(set(summary["warnings"]))
    summary["blockers"] = sorted(set(summary["blockers"]))
    return summary


def base_safety() -> dict[str, Any]:
    return {
        "movementSent": False,
        "inputSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "noCheatEngine": True,
        "x64dbgAttach": False,
        "debuggerAttached": False,
        "debugActiveProcessStopCalled": False,
        "targetMemoryBytesRead": True,
        "targetMemoryBytesWritten": False,
        "providerWrites": False,
        "gitMutation": False,
        "proofPromotion": False,
        "actorChainPromotion": False,
        "facingPromotion": False,
    }


def build_compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    reads = safe_mapping(summary.get("reads"))
    nav_state = safe_mapping(reads.get("navState"))
    analysis = safe_mapping(summary.get("analysis"))
    target = safe_mapping(summary.get("target"))
    module_base_check = safe_mapping(target.get("moduleBaseCheck"))
    compact: dict[str, Any] = {
        "status": summary.get("status"),
        "verdict": summary.get("verdict"),
        "classification": summary.get("classification"),
        "ownerAddress": reads.get("ownerAddress"),
        "coordinate": reads.get("coordinate"),
        "sampleCount": analysis.get("sampleCount"),
        "maxPlanarDelta": analysis.get("maxPlanarDelta"),
        "maxSpeedPlanarPerSecond": analysis.get("maxSpeedPlanarPerSecond"),
        "ownerChangedCount": analysis.get("ownerChangedCount"),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
    }
    if module_base_check:
        compact["moduleBaseCheck"] = module_base_check
    if nav_state:
        if nav_state.get("navStateError"):
            compact["navState"] = {
                "navStateError": nav_state["navStateError"],
                "navStateCandidateOnly": True,
                "actionableForNavigation": False,
            }
        else:
            compact["navState"] = {
                "yawDegrees": nav_state.get("yawDegrees"),
                "pitchDegrees": nav_state.get("pitchDegrees"),
                "facingTargetCoordinate": nav_state.get("facingTargetCoordinate"),
                "planarLookaheadDistance": nav_state.get("planarLookaheadDistance"),
                "turnRate0x304": nav_state.get("turnRate0x304"),
                "turnRateClassification": nav_state.get("turnRateClassification"),
                "navStateCandidateOnly": True,
                "actionableForNavigation": False,
            }
    return compact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read or poll the promoted static owner-coordinate resolver")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--use-current-truth", action="store_true", help="Populate PID/HWND/module-base/root settings from docs/recovery/current-truth.json.")
    parser.add_argument("--current-truth-json", default="docs/recovery/current-truth.json")
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--hwnd")
    parser.add_argument("--module-base")
    parser.add_argument("--expected-process-start-utc")
    parser.add_argument("--process-start-tolerance-seconds", type=float, default=2.0)
    parser.add_argument("--root-rva", default=hex(DEFAULT_ROOT_RVA))
    parser.add_argument("--coord-offset", default=hex(DEFAULT_COORD_OFFSET))
    parser.add_argument("--expected-proof-anchor", default=None, help="Optional historical/proof anchor to compare against. Omit for promoted resolver position reads.")
    parser.add_argument("--tolerance", type=float, default=0.01)
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--interval-seconds", type=float, default=0.2)
    parser.add_argument("--max-planar-jump-per-sample", type=float, default=DEFAULT_MAX_PLANAR_JUMP_PER_SAMPLE)
    parser.add_argument("--max-sample-gap-seconds", type=float, default=DEFAULT_MAX_SAMPLE_GAP_SECONDS)
    parser.add_argument("--expect-stationary", action="store_true", help="Block if the no-input baseline drifts more than --max-stationary-planar-drift.")
    parser.add_argument("--max-stationary-planar-drift", type=float, default=DEFAULT_MAX_STATIONARY_PLANAR_DRIFT)
    parser.add_argument("--nav-state", action="store_true", help="Also read facing target (+0x30C), turn rate (+0x304), and compute yaw from the same owner window.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    summary = run(args)
    artifacts = safe_mapping(summary["artifacts"])
    Path(str(artifacts["summaryJson"])).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    Path(str(artifacts["summaryMarkdown"])).write_text(build_markdown(summary), encoding="utf-8")
    compact = build_compact(summary)
    print(json.dumps(compact) if args.json else json.dumps(compact, indent=2))
    return 0 if summary.get("status") == "passed" else 2 if summary.get("status") == "blocked" else 1


if __name__ == "__main__":
    sys.exit(main())
