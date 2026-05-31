#!/usr/bin/env python3
"""Capture sequential current-PID family-group snapshots for offline deltas.

Primary purpose: dump targeted family ranges across ordered poses, then run the
offline delta analyzer.  By default this helper sends no input, launches no
debugger, uses no Cheat Engine, and writes no provider state.  If
``--auto-displacement-key`` is supplied, the helper sends one bounded
exact-PID/HWND displacement through the repo-owned C# SendInput ScanCode helper
before the displaced pose and records that input in the durable command
envelopes.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import msvcrt
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from .workflow_common import utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution path
    from workflow_common import utc_iso, utc_stamp, write_json  # type: ignore

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from scan_current_pid_coordinate_family import (  # noqa: E402
    close_handle,
    enumerate_regions,
    find_repo_root,
    format_hex,
    open_process,
    query_process_image,
    read_memory,
    verify_hwnd_owner,
)


SCHEMA_VERSION = 1
DEFAULT_POSE_PLAN = "baseline-still:baseline:0,passive-still-500ms:passive:0.5,passive-still-1500ms:passive:1.5,operator-displaced-settled:displaced:0.5"
DEFAULT_REFERENCE_SOURCE = "rrapicoord"
DEFAULT_REFERENCE_TIMEOUT_SECONDS = 180
DEFAULT_CURRENT_TRUTH_JSON = Path("docs") / "recovery" / "current-truth.json"
DEFAULT_AUTO_DISPLACEMENT_INPUT_BACKEND = "csharp-scancode"
DEFAULT_PRIOR_ADDRESSES = [
    # Highest-signal May 13 PID 2928 candidate family from prior-first
    # sequential snapshots + offline delta comparison.  These are
    # candidate-only offset-coordinate copy leads, not movement proof.
    ("0x268DF21ED30", "pid2928-best-focused-offset-copy-candidate"),
    ("0x268DF21ED20", "pid2928-broad-delta-offset-copy-candidate"),
    ("0x268DF200000", "pid2928-offset-copy-family-base"),
    # Highest-signal May 13 PID 60628 candidate families.
    ("0x1FF07570000", "pid60628-destination-copy-family"),
    ("0x1FF08502BC8", "pid60628-best-exact-threepose-candidate"),
    ("0x1FF94EC0000", "pid60628-best-moving-slot-family"),
    ("0x1FF6D600020", "pid60628-source-copy-buffer"),
    ("0x1FF65FADE88", "pid60628-source-cursor-candidate"),
    ("0x1FF6D658590", "pid60628-source-family-heap-ref"),
    # Last fully proven / earlier restarted proof anchors.  These are lower
    # confidence after a new PID, but still useful as explicit prior frontiers
    # if the current process maps nearby families again.
    ("0xCC080EC30C", "pid57656-last-proof-anchor"),
    ("0x1E804B53C18", "pid30992-proof-anchor"),
    ("0x24A01358880", "pid49504-proof-anchor"),
    # Historical actor/source-chain objects: useful nearby-family priors, never
    # promotion truth for this PID by themselves.
    ("0x216F2F26020", "historical-source-object"),
    ("0x216F87CDDD0", "historical-trace-linked-source-object"),
    ("0x216FE3C6280", "historical-facing-source-object"),
]


class CommandEnvelopeError(RuntimeError):
    def __init__(self, message: str, envelope: dict[str, Any]) -> None:
        super().__init__(message)
        self.envelope = envelope


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_json(text: str) -> Any:
    value = (text or "").strip()
    if not value:
        raise RuntimeError("empty command output")
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass
    starts = [idx for idx in (value.find("{"), value.find("[")) if idx >= 0]
    if not starts:
        raise RuntimeError(f"no JSON object/array found; preview={value[:500]}")
    parsed, _ = json.JSONDecoder().raw_decode(value[min(starts) :])
    return parsed


def run_command(args: list[str], cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    started = time.monotonic()
    started_utc = utc_iso()
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "args": args,
            "cwd": str(cwd),
            "startedAtUtc": started_utc,
            "completedAtUtc": utc_iso(),
            "durationSeconds": round(time.monotonic() - started, 3),
            "exitCode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "timedOut": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "args": args,
            "cwd": str(cwd),
            "startedAtUtc": started_utc,
            "completedAtUtc": utc_iso(),
            "durationSeconds": round(time.monotonic() - started, 3),
            "exitCode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timedOut": True,
            "timeoutSeconds": timeout_seconds,
        }


def compact_envelope(envelope: dict[str, Any], stage: str) -> dict[str, Any]:
    return {
        **{k: v for k, v in envelope.items() if k not in {"stdout", "stderr"}},
        "stdoutPreview": str(envelope.get("stdout") or "")[:2000],
        "stderrPreview": str(envelope.get("stderr") or "")[:2000],
        "stage": stage,
    }


def resolve_repo_path(repo_root: Path, path_value: Path | str | None) -> Path | None:
    if path_value is None:
        return None
    path = Path(str(path_value))
    return path if path.is_absolute() else repo_root / path


def to_int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(str(value), 0)
        except (TypeError, ValueError):
            return None


def normalize_hwnd(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        return f"0x{int(str(value), 0):X}"
    except (TypeError, ValueError):
        return str(value).strip()


def normalize_hex(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        return format_hex(int(str(value), 0))
    except (TypeError, ValueError):
        return str(value).strip()


def append_if_missing(values: list[str], candidate: str) -> bool:
    if candidate in values:
        return False
    values.append(candidate)
    return True


def prior_address_value_exists(values: list[str], candidate_address: str) -> bool:
    try:
        candidate = int(str(candidate_address), 0)
    except (TypeError, ValueError):
        return False
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        if "=" in text:
            _, address_text = text.split("=", 1)
        else:
            address_text = text
        try:
            if int(address_text, 0) == candidate:
                return True
        except ValueError:
            continue
    return False


def append_prior_address_if_missing(values: list[str], label: str, candidate_address: str) -> str | None:
    if prior_address_value_exists(values, candidate_address):
        return None
    prior = f"{label}={candidate_address}"
    values.append(prior)
    return prior


def apply_current_truth_context(args: argparse.Namespace, repo_root: Path) -> dict[str, Any]:
    context: dict[str, Any] = {
        "enabled": not bool(getattr(args, "disable_current_truth", False)),
        "path": None,
        "loaded": False,
        "targetDefaultsApplied": [],
        "priorDefaultsApplied": [],
        "movementGate": None,
        "clientGeometry": None,
        "blockers": [],
        "warnings": [],
    }
    args.current_truth_context = context
    args.current_truth_blockers = context["blockers"]
    args.current_truth_warnings = context["warnings"]
    if not context["enabled"] or getattr(args, "self_test", False):
        return context

    path = resolve_repo_path(repo_root, args.current_truth_json if args.current_truth_json else DEFAULT_CURRENT_TRUTH_JSON)
    context["path"] = str(path) if path else None
    if path is None or not path.exists():
        if args.current_truth_json:
            context["blockers"].append(f"current-truth-json-not-found:{path}")
        return context

    try:
        document = load_json(path)
    except Exception as exc:  # noqa: BLE001
        context["blockers"].append(f"current-truth-json-read-failed:{type(exc).__name__}:{exc}")
        return context
    if not isinstance(document, dict):
        context["blockers"].append("current-truth-json-must-be-object")
        return context
    context["loaded"] = True

    target = document.get("target") if isinstance(document.get("target"), dict) else {}
    truth_pid = to_int_or_none(target.get("processId") or target.get("pid") or target.get("Pid"))
    truth_hwnd = normalize_hwnd(target.get("targetWindowHandle") or target.get("hwnd") or target.get("hwndHex"))
    truth_start = target.get("processStartUtc") or target.get("startTimeUtc")
    truth_module_base = normalize_hex(target.get("moduleBase") or target.get("moduleBaseAddressHex") or target.get("moduleBaseAddress"))
    client_geometry = target.get("clientGeometry") if isinstance(target.get("clientGeometry"), dict) else {}
    required_client_width = to_int_or_none(client_geometry.get("requiredClientWidth"))
    required_client_height = to_int_or_none(client_geometry.get("requiredClientHeight"))
    if required_client_width or required_client_height:
        context["clientGeometry"] = {
            "requiredClientWidth": required_client_width,
            "requiredClientHeight": required_client_height,
            "lastVerifiedAtUtc": client_geometry.get("lastVerifiedAtUtc"),
            "policy": client_geometry.get("policy"),
        }
        if getattr(args, "require_client_width", None) is None and required_client_width:
            args.require_client_width = required_client_width
            context["targetDefaultsApplied"].append("require-client-width")
        if getattr(args, "require_client_height", None) is None and required_client_height:
            args.require_client_height = required_client_height
            context["targetDefaultsApplied"].append("require-client-height")

    movement_gate = document.get("movementGate") if isinstance(document.get("movementGate"), dict) else {}
    live_input_incident = (
        movement_gate.get("liveInputIncident") if isinstance(movement_gate.get("liveInputIncident"), dict) else {}
    )
    if movement_gate:
        context["movementGate"] = {
            "allowed": movement_gate.get("allowed"),
            "status": movement_gate.get("status"),
            "reason": movement_gate.get("reason"),
            "automationMovementPaused": bool(
                movement_gate.get("automationMovementPaused") or live_input_incident.get("automationMovementPaused")
            ),
            "liveInputIncidentStatus": live_input_incident.get("status"),
        }

    if args.pid is None and truth_pid is not None:
        args.pid = truth_pid
        context["targetDefaultsApplied"].append("pid")
    elif args.pid is not None and truth_pid is not None and int(args.pid) != int(truth_pid):
        context["blockers"].append(f"current-truth-target-pid-mismatch:{args.pid}!={truth_pid}")

    if not args.hwnd and truth_hwnd:
        args.hwnd = truth_hwnd
        context["targetDefaultsApplied"].append("hwnd")
    elif args.hwnd and truth_hwnd and normalize_hwnd(args.hwnd) != truth_hwnd:
        context["blockers"].append(f"current-truth-target-hwnd-mismatch:{normalize_hwnd(args.hwnd)}!={truth_hwnd}")

    if not args.expected_start_time_utc and truth_start:
        args.expected_start_time_utc = str(truth_start)
        context["targetDefaultsApplied"].append("expected-start-time-utc")
    elif args.expected_start_time_utc and truth_start and str(args.expected_start_time_utc) != str(truth_start):
        context["blockers"].append(f"current-truth-target-start-mismatch:{args.expected_start_time_utc}!={truth_start}")

    if not args.expected_module_base and truth_module_base:
        args.expected_module_base = truth_module_base
        context["targetDefaultsApplied"].append("expected-module-base")
    elif args.expected_module_base and truth_module_base and normalize_hex(args.expected_module_base) != truth_module_base:
        context["blockers"].append(
            f"current-truth-target-module-base-mismatch:{normalize_hex(args.expected_module_base)}!={truth_module_base}"
        )

    candidate = document.get("bestCurrentCandidate") if isinstance(document.get("bestCurrentCandidate"), dict) else {}
    candidate_address = candidate.get("addressHex") or candidate.get("address") or candidate.get("absoluteAddressHex")
    if candidate_address:
        args.prior_address = list(args.prior_address or [])
        prior = append_prior_address_if_missing(args.prior_address, "currentTruth", str(candidate_address))
        if prior:
            context["priorDefaultsApplied"].append(prior)
    else:
        context["warnings"].append("current-truth-best-current-candidate-address-missing")

    latest = document.get("latestCoordinateReacquisition") if isinstance(document.get("latestCoordinateReacquisition"), dict) else {}
    duplicate_addresses = latest.get("latestDuplicateCopyRankedAddresses")
    if isinstance(duplicate_addresses, list):
        args.prior_address = list(args.prior_address or [])
        for index, address in enumerate(duplicate_addresses, start=1):
            if not address:
                continue
            prior = append_prior_address_if_missing(args.prior_address, f"duplicateCopy{index}", str(address))
            if prior:
                context["priorDefaultsApplied"].append(prior)

    return context


def current_truth_auto_displacement_blockers(args: argparse.Namespace) -> list[str]:
    context = getattr(args, "current_truth_context", None)
    if not isinstance(context, dict):
        return []
    movement_gate = context.get("movementGate")
    if not isinstance(movement_gate, dict):
        return []
    blockers: list[str] = []
    status = str(movement_gate.get("status") or "unknown")
    if movement_gate.get("allowed") is False:
        blockers.append(f"current-truth-movement-gate-blocked:{status}")
    if movement_gate.get("automationMovementPaused") is True:
        blockers.append("current-truth-automation-movement-paused")
    incident_status = movement_gate.get("liveInputIncidentStatus")
    if incident_status:
        blockers.append(f"current-truth-live-input-incident:{incident_status}")
    return blockers


def auto_displacement_backend_blockers(args: argparse.Namespace) -> list[str]:
    """Return blockers for auto-displacement backends that need explicit re-authorization."""

    if not getattr(args, "auto_displacement_key", None):
        return []
    backend = str(
        getattr(args, "auto_displacement_input_backend", DEFAULT_AUTO_DISPLACEMENT_INPUT_BACKEND)
        or DEFAULT_AUTO_DISPLACEMENT_INPUT_BACKEND
    ).strip().lower()
    if backend == DEFAULT_AUTO_DISPLACEMENT_INPUT_BACKEND:
        return []
    if backend == "window-message":
        return ["auto-displacement-window-message-backend-retired-use-csharp-scancode"]
    return [f"auto-displacement-unsupported-input-backend:{backend}"]


def inspect_client_geometry(hwnd: str) -> dict[str, int | str]:
    try:
        hwnd_int = int(str(hwnd), 0)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"invalid HWND for client geometry inspection: {hwnd}") from exc
    try:
        import ctypes
        from ctypes import wintypes
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"client geometry inspection unavailable:{type(exc).__name__}:{exc}") from exc

    rect = wintypes.RECT()
    ok = ctypes.windll.user32.GetClientRect(ctypes.c_void_p(hwnd_int), ctypes.byref(rect))
    if not ok:
        raise RuntimeError(f"GetClientRect failed for HWND {normalize_hwnd(hwnd)}")
    width = int(rect.right - rect.left)
    height = int(rect.bottom - rect.top)
    return {
        "hwnd": normalize_hwnd(hwnd) or str(hwnd),
        "left": int(rect.left),
        "top": int(rect.top),
        "right": int(rect.right),
        "bottom": int(rect.bottom),
        "width": width,
        "height": height,
    }


def required_client_geometry_blockers(args: argparse.Namespace) -> tuple[list[str], dict[str, Any] | None]:
    required_width = to_int_or_none(getattr(args, "require_client_width", None))
    required_height = to_int_or_none(getattr(args, "require_client_height", None))
    if not required_width and not required_height:
        return [], None
    if not getattr(args, "hwnd", None):
        return ["required-client-geometry-hwnd-missing"], None
    geometry = inspect_client_geometry(str(args.hwnd))
    blockers: list[str] = []
    if required_width and geometry.get("width") != required_width:
        blockers.append(f"client-width-mismatch:{geometry.get('width')}!={required_width}")
    if required_height and geometry.get("height") != required_height:
        blockers.append(f"client-height-mismatch:{geometry.get('height')}!={required_height}")
    return blockers, {
        "requiredWidth": required_width,
        "requiredHeight": required_height,
        "actual": geometry,
    }


def latest_scan_plan(repo_root: Path, pid: int) -> Path:
    matches = sorted(
        (repo_root / "scripts" / "captures").glob(f"memory-region-inventory-currentpid-{pid}-*/scan-plan.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not matches:
        raise RuntimeError(f"no memory-region scan plan found for PID {pid}")
    return matches[0].resolve()


def load_scan_ranges(path: Path, top_count: int) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    ranges = document.get("ranges")
    if not isinstance(ranges, list):
        raise RuntimeError(f"scan plan does not contain ranges: {path}")
    return ranges[: max(1, top_count)]


def range_record(
    *,
    min_address: int,
    max_address: int,
    rank: int,
    source: str,
    label: str,
    priority: int,
) -> dict[str, Any]:
    if max_address <= min_address:
        max_address = min_address + 0x1000
    return {
        "rank": rank,
        "source": source,
        "label": label,
        "priority": priority,
        "minAddress": min_address,
        "minAddressHex": format_hex(min_address),
        "maxAddress": max_address,
        "maxAddressHex": format_hex(max_address),
        "spanBytes": max_address - min_address,
        "spanMiB": round((max_address - min_address) / (1024 * 1024), 6),
    }


def page_align_down(value: int, page: int) -> int:
    return max(0, value - (value % page))


def page_align_up(value: int, page: int) -> int:
    return value if value % page == 0 else value + (page - (value % page))


def parse_prior_specs(values: list[str]) -> list[tuple[int, str]]:
    priors: list[tuple[int, str]] = []
    for index, raw in enumerate(values, start=1):
        text = str(raw).strip()
        if not text:
            continue
        if "=" in text:
            label, address_text = text.split("=", 1)
        else:
            label, address_text = f"operator-prior-{index}", text
        priors.append((int(address_text, 0), label.strip() or f"operator-prior-{index}"))
    return priors


def documented_prior_specs(disabled: bool) -> list[tuple[int, str]]:
    if disabled:
        return []
    return [(int(address, 0), label) for address, label in DEFAULT_PRIOR_ADDRESSES]


def build_prior_ranges(args: argparse.Namespace) -> list[dict[str, Any]]:
    """Build explicit prior-first family ranges.

    Prior addresses are historical/current-truth *frontiers*, not proof.  They
    are tried before generic inventory ranges because previous truth and nearby
    family groups have repeatedly been the highest-yield search area.
    """

    page = max(0x1000, int(args.prior_alignment))
    radius = max(0x1000, int(args.prior_radius))
    family_span = max(0x1000, int(args.prior_family_span))
    family_step = max(0x1000, int(args.prior_family_step))
    neighbor_count = max(0, int(args.prior_neighbor_family_count))

    # Operator/current-truth priors must outrank documented historical priors.
    # Earlier versions sorted every exact prior only by address, so low-address
    # historical anchors could crowd out the newest current-truth family when a
    # bounded run used --max-prior-ranges.  That is stale-prone and wastes the
    # highest-signal scan budget.
    raw_priors: list[tuple[int, str, int]] = []
    raw_priors.extend((address, label, 10) for address, label in documented_prior_specs(args.disable_default_priors))
    raw_priors.extend((address, label, 0) for address, label in parse_prior_specs(args.prior_address or []))
    raw_priors.extend((address, label, 0) for address, label in parse_prior_specs(args.prior_family or []))

    ranges: list[dict[str, Any]] = []
    rank = 1
    seen: set[tuple[int, int, str]] = set()
    for address, label, priority_base in raw_priors:
        exact_min = page_align_down(max(0, address - radius), page)
        exact_max = page_align_up(address + radius, page)
        key = (exact_min, exact_max, f"prior-exact:{label}")
        if key not in seen:
            ranges.append(
                range_record(
                    min_address=exact_min,
                    max_address=exact_max,
                    rank=rank,
                    source="prior-exact-window",
                    label=label,
                    priority=priority_base,
                )
            )
            rank += 1
            seen.add(key)

        family_base = page_align_down(address, family_step)
        for neighbor in range(-neighbor_count, neighbor_count + 1):
            family_min = max(0, family_base + (neighbor * family_step))
            family_max = family_min + family_span
            key = (family_min, family_max, f"prior-family:{label}:{neighbor}")
            if key in seen:
                continue
            ranges.append(
                range_record(
                    min_address=family_min,
                    max_address=family_max,
                    rank=rank,
                    source="prior-family-neighborhood",
                    label=f"{label}:neighbor{neighbor:+d}",
                    priority=priority_base + 1 + abs(neighbor),
                )
            )
            rank += 1
            seen.add(key)

    ranges.sort(key=lambda item: (int(item["priority"]), int(item["minAddress"])))
    for index, item in enumerate(ranges[: max(0, int(args.max_prior_ranges))], start=1):
        item["rank"] = index
    return ranges[: max(0, int(args.max_prior_ranges))]


def normalize_plan_range(item: dict[str, Any], rank: int) -> dict[str, Any]:
    min_address = int(str(item["minAddressHex"]), 0)
    max_address = int(str(item["maxAddressHex"]), 0)
    normalized = dict(item)
    normalized.update(
        {
            "rank": rank,
            "source": normalized.get("source") or "current-pid-scan-plan",
            "label": normalized.get("label") or f"scan-plan-rank-{item.get('rank', rank)}",
            "priority": normalized.get("priority", 1000 + rank),
            "minAddress": min_address,
            "maxAddress": max_address,
            "spanBytes": max_address - min_address,
            "spanMiB": round((max_address - min_address) / (1024 * 1024), 6),
        }
    )
    return normalized


def dedupe_and_order_ranges(prior_ranges: list[dict[str, Any]], plan_ranges: list[dict[str, Any]], max_total: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for item in [*prior_ranges, *plan_ranges]:
        key = (int(item["minAddress"]), int(item["maxAddress"]))
        if key in seen:
            continue
        selected.append(item)
        seen.add(key)
        if len(selected) >= max_total:
            break
    for index, item in enumerate(selected, start=1):
        item["rank"] = index
    return selected


def select_adaptive_scan_ranges(scan_plan: Path, args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prior_ranges = build_prior_ranges(args)
    plan_ranges = [normalize_plan_range(item, index) for index, item in enumerate(load_scan_ranges(scan_plan, args.top_count), start=1)]
    selected = dedupe_and_order_ranges(prior_ranges, plan_ranges, max_total=max(1, int(args.max_total_ranges)))
    strategy = {
        "mode": "prior-first-family-snapshot",
        "priorRangeCount": len(prior_ranges),
        "scanPlanRangeCount": len(plan_ranges),
        "selectedRangeCount": len(selected),
        "maxTotalRanges": args.max_total_ranges,
        "defaultPriorsDisabled": args.disable_default_priors,
        "priorRadius": format_hex(args.prior_radius),
        "priorFamilySpan": format_hex(args.prior_family_span),
        "priorFamilyStep": format_hex(args.prior_family_step),
        "priorNeighborFamilyCount": args.prior_neighbor_family_count,
        "selectedSourceCounts": dict(Counter(str(item.get("source")) for item in selected)),
    }
    return selected, strategy


def parse_pose_plan(value: str) -> list[dict[str, Any]]:
    poses: list[dict[str, Any]] = []
    for index, raw in enumerate(value.split(","), start=1):
        text = raw.strip()
        if not text:
            continue
        parts = text.split(":")
        if len(parts) != 3:
            raise ValueError(f"invalid pose specification {text!r}; expected label:role:settleSeconds")
        label, role, settle = parts
        role = role.strip().lower()
        if role not in {"baseline", "passive", "displaced"}:
            raise ValueError(f"invalid pose role {role!r} in {text!r}")
        poses.append({"index": index, "label": label.strip(), "role": role, "settleSeconds": float(settle)})
    if not poses:
        raise ValueError("pose plan is empty")
    if not any(pose["role"] == "baseline" for pose in poses):
        raise ValueError("pose plan must contain a baseline pose")
    return poses


def wait_for_enter_or_timeout(timeout_seconds: int) -> bool:
    if timeout_seconds <= 0:
        return False
    if not sys.stdin.isatty():
        return False
    print(f"Move the character manually, settle, then press Enter within {timeout_seconds}s...")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch in {"\r", "\n"}:
                return True
        time.sleep(0.1)
    return False


def run_auto_displacement(repo_root: Path, args: argparse.Namespace) -> tuple[bool, dict[str, Any]]:
    key = str(args.auto_displacement_key or "").strip()
    if not key:
        return False, {
            "stage": "auto-displacement",
            "exitCode": None,
            "stdout": "",
            "stderr": "auto displacement key not configured",
            "timedOut": False,
        }

    backend = str(
        getattr(args, "auto_displacement_input_backend", DEFAULT_AUTO_DISPLACEMENT_INPUT_BACKEND)
        or DEFAULT_AUTO_DISPLACEMENT_INPUT_BACKEND
    ).strip().lower()
    if backend != DEFAULT_AUTO_DISPLACEMENT_INPUT_BACKEND:
        return False, {
            "stage": "auto-displacement",
            "exitCode": None,
            "stdout": "",
            "stderr": f"unsupported auto displacement input backend: {backend}",
            "timedOut": False,
        }

    command = [
        "pwsh",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(repo_root / "scripts" / "send-rift-key-csharp.ps1"),
        "--key",
        key,
        "--hold-ms",
        str(max(1, int(args.auto_displacement_hold_ms))),
        "--process-name",
        str(args.process_name),
        "--pid",
        str(args.pid),
        "--hwnd",
        str(args.hwnd),
        "--input-mode",
        "ScanCode",
        "--json",
    ]
    envelope = run_command(command, repo_root, timeout_seconds=max(5, int(args.auto_displacement_timeout_seconds)))
    return bool(envelope.get("exitCode") == 0 and not envelope.get("timedOut")), envelope


def run_emergency_key_release(
    repo_root: Path,
    args: argparse.Namespace,
    run_dir: Path,
    *,
    stage: str,
) -> tuple[bool, dict[str, Any]]:
    command = [
        sys.executable,
        str(repo_root / "scripts" / "rift_emergency_key_release.py"),
        "--pid",
        str(args.pid),
        "--hwnd",
        str(args.hwnd),
        "--process-name",
        args.process_name,
        "--include-mouse-buttons",
        "--output-root",
        str(run_dir / "emergency-key-release"),
        "--json",
    ]
    envelope = run_command(command, repo_root, timeout_seconds=max(5, int(args.auto_displacement_timeout_seconds)))
    envelope["emergencyReleaseStage"] = stage
    return bool(envelope.get("exitCode") == 0 and not envelope.get("timedOut")), envelope


def run_preflight(repo_root: Path, args: argparse.Namespace, run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    command = [
        sys.executable,
        str(repo_root / "scripts" / "x64dbg_preflight.py"),
        "--require-exact-target",
        "--require-no-debugger-process",
        "--target-pid",
        str(args.pid),
        "--target-hwnd",
        str(args.hwnd),
        "--json",
    ]
    if args.expected_start_time_utc:
        command.extend(["--expected-start-time-utc", args.expected_start_time_utc])
    if args.expected_module_base:
        command.extend(["--expected-module-base", args.expected_module_base])
    envelope = run_command(command, repo_root, timeout_seconds=args.preflight_timeout_seconds)
    if envelope["timedOut"] or envelope["exitCode"] != 0:
        raise RuntimeError(f"preflight_failed: exit={envelope['exitCode']}; timedOut={envelope['timedOut']}; stderr={str(envelope['stderr'])[:500]}")
    parsed = extract_json(str(envelope["stdout"]))
    write_json(run_dir / "preflight-summary.json", parsed)
    return parsed, envelope


def capture_chromalink_reference(repo_root: Path, args: argparse.Namespace, pose_dir: Path) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    command = [
        sys.executable,
        str(repo_root / "scripts" / "chromalink_world_state_reference.py"),
        "--preflight-summary",
        "latest",
        "--target-pid",
        str(args.pid),
        "--target-hwnd",
        str(args.hwnd),
        "--process-name",
        args.process_name,
        "--output-root",
        str(pose_dir),
        "--json",
    ]
    envelope = run_command(command, repo_root, timeout_seconds=args.reference_timeout_seconds)
    if envelope["timedOut"] or envelope["exitCode"] != 0:
        raise CommandEnvelopeError(
            f"reference_capture_failed: source=chromalink; exit={envelope['exitCode']}; "
            f"timedOut={envelope['timedOut']}; stdout={str(envelope.get('stdout') or '')[:500]}; "
            f"stderr={str(envelope.get('stderr') or '')[:500]}",
            envelope,
        )
    parsed = extract_json(str(envelope["stdout"]))
    reference_path = Path(parsed["referenceJson"]).resolve()
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    return reference, reference_path, envelope


def capture_rrapicoord_reference(repo_root: Path, args: argparse.Namespace, pose_dir: Path) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    command = [
        "pwsh",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(repo_root / "scripts" / "capture-rift-api-reference-coordinate.ps1"),
        "-ProcessId",
        str(args.pid),
        "-TargetWindowHandle",
        str(args.hwnd),
        "-OutputRoot",
        str(pose_dir),
        "-ScanContextBytes",
        str(args.reference_scan_context_bytes),
        "-MaxHits",
        str(args.reference_max_hits),
        "-ScanAttempts",
        str(args.reference_scan_attempts),
        "-ScanRetryDelayMilliseconds",
        str(args.reference_scan_retry_delay_milliseconds),
        "-ReferenceTolerance",
        str(args.reference_tolerance),
        "-Json",
    ]
    envelope = run_command(command, repo_root, timeout_seconds=args.reference_timeout_seconds)
    parsed: dict[str, Any] | None = None
    if envelope.get("stdout"):
        try:
            parsed = extract_json(str(envelope["stdout"]))
        except Exception:
            parsed = None
    if envelope["timedOut"] or envelope["exitCode"] != 0:
        raise CommandEnvelopeError(
            "reference_capture_failed:"
            f" source=rrapicoord; exit={envelope['exitCode']}; timedOut={envelope['timedOut']}; "
            f"stdout={str(envelope.get('stdout') or '')[:500]}; stderr={str(envelope.get('stderr') or '')[:500]}",
            envelope,
        )
    if not isinstance(parsed, dict):
        raise CommandEnvelopeError("reference_capture_failed: source=rrapicoord; stdout-json-missing", envelope)
    reference_path_value = parsed.get("ReferenceFile") or parsed.get("referenceFile")
    if not reference_path_value:
        raise CommandEnvelopeError("reference_capture_failed: source=rrapicoord; reference-file-missing", envelope)
    reference_path = Path(str(reference_path_value)).resolve()
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    return reference, reference_path, envelope


def capture_reference(repo_root: Path, args: argparse.Namespace, pose_dir: Path) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    source = str(args.reference_source or DEFAULT_REFERENCE_SOURCE).strip().lower()
    if source == "chromalink":
        return capture_chromalink_reference(repo_root, args, pose_dir)
    if source == "rrapicoord":
        return capture_rrapicoord_reference(repo_root, args, pose_dir)
    raise RuntimeError(f"unsupported-reference-source:{source}")


def gzip_write(path: Path, data: bytes) -> tuple[str, int]:
    compressed = gzip.compress(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(compressed)
    return hashlib.sha256(data).hexdigest(), len(compressed)


def snapshot_pose(
    *,
    repo_root: Path,
    run_dir: Path,
    pose_spec: dict[str, Any],
    scan_ranges: list[dict[str, Any]],
    args: argparse.Namespace,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    pose_dir = run_dir / f"pose-{int(pose_spec['index']):03d}-{pose_spec['label']}"
    pose_dir.mkdir(parents=True, exist_ok=True)
    reference, reference_path, reference_envelope = capture_reference(repo_root, args, pose_dir)

    hwnd_info = verify_hwnd_owner(args.hwnd, args.pid)
    if hwnd_info.get("blocker"):
        raise RuntimeError(str(hwnd_info["blocker"]))

    handle = open_process(args.pid)
    segments: list[dict[str, Any]] = []
    warnings: list[str] = []
    total_bytes = 0
    segment_index = 0
    try:
        image = query_process_image(handle)
        for scan_range in scan_ranges:
            min_address = int(str(scan_range["minAddressHex"]), 0)
            max_address = int(str(scan_range["maxAddressHex"]), 0)
            regions = enumerate_regions(handle, min_address=min_address, max_address=max_address)
            for region in regions:
                base = int(region["base"])
                size = min(int(region["size"]), max_address - base)
                offset = 0
                while offset < size:
                    if total_bytes >= args.max_bytes_per_pose:
                        warnings.append(f"max-bytes-per-pose-reached:{args.max_bytes_per_pose}")
                        break
                    read_size = min(args.segment_bytes, size - offset, args.max_bytes_per_pose - total_bytes)
                    address = base + offset
                    data = read_memory(handle, address, read_size)
                    if data is None:
                        warnings.append(f"read-memory-failed:{format_hex(address)}:{read_size}")
                        offset += read_size
                        continue
                    segment_index += 1
                    end = address + len(data)
                    filename = f"seg-{segment_index:06d}-{address:X}-{end:X}.bin.gz"
                    segment_path = pose_dir / "segments" / filename
                    sha256, compressed_bytes = gzip_write(segment_path, data)
                    total_bytes += len(data)
                    segments.append(
                        {
                            "id": f"seg-{segment_index:06d}",
                            "path": str(segment_path.relative_to(run_dir)),
                            "compression": "gzip",
                            "sha256": sha256,
                            "base": address,
                            "baseHex": format_hex(address),
                            "end": end,
                            "endHex": format_hex(end),
                            "sizeBytes": len(data),
                            "compressedBytes": compressed_bytes,
                            "rangeRank": scan_range.get("rank"),
                            "rangeSource": scan_range.get("source"),
                            "rangeLabel": scan_range.get("label"),
                            "rangeMinHex": scan_range.get("minAddressHex"),
                            "rangeMaxHex": scan_range.get("maxAddressHex"),
                            "regionBaseHex": format_hex(base),
                        }
                    )
                    offset += read_size
                if total_bytes >= args.max_bytes_per_pose:
                    break
            if total_bytes >= args.max_bytes_per_pose:
                break
    finally:
        close_handle(handle)

    pose = {
        "index": pose_spec["index"],
        "label": pose_spec["label"],
        "role": pose_spec["role"],
        "capturedAtUtc": utc_iso(),
        "processImage": image,
        "referenceFile": str(reference_path),
        "reference": reference,
        "segments": segments,
        "segmentCount": len(segments),
        "bytesRead": total_bytes,
        "warnings": warnings,
    }
    command_envelopes = [
        compact_envelope(reference_envelope, f"reference:{pose_spec['label']}")
    ]
    write_json(pose_dir / "pose-summary.json", pose)
    return pose, command_envelopes


def render_markdown(summary: dict[str, Any], manifest: dict[str, Any]) -> str:
    rows = []
    for pose in manifest.get("poses", []):
        rows.append(
            f"| {pose.get('index')} | `{pose.get('label')}` | `{pose.get('role')}` | "
            f"{pose.get('segmentCount')} | {pose.get('bytesRead')} |"
        )
    return "\n".join(
        [
            "# Current-PID family snapshot sequence",
            "",
            f"- Status: `{summary.get('status')}`",
            f"- PID/HWND: `{summary.get('processId')}` / `{summary.get('targetWindowHandle')}`",
            f"- Reference source: `{summary.get('referenceSource')}`",
            f"- Scan plan: `{summary.get('scanPlanJson')}`",
            f"- Manifest: `{summary.get('artifacts', {}).get('manifestJson')}`",
            f"- Delta summary: `{summary.get('artifacts', {}).get('deltaSummaryJson')}`",
            "",
            "| # | Pose | Role | Segments | Bytes read |",
            "|---:|---|---|---:|---:|",
            *rows,
            "",
            "No x64dbg, Cheat Engine, provider writes, memory writes, or proof promotion are performed by this helper.",
            "Input is sent only when `--auto-displacement-key` is explicitly supplied; otherwise displaced poses require an operator Enter confirmation.",
            "",
        ]
    )


def run_analyzer(repo_root: Path, run_dir: Path, args: argparse.Namespace) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    command = [
        sys.executable,
        str(repo_root / "scripts" / "family_snapshot_delta_analyzer.py"),
        "--manifest",
        str(run_dir / "manifest.json"),
        "--output-root",
        str(run_dir / "delta-analysis"),
        "--axis-orders",
        args.axis_orders,
        "--candidate-scan-stride",
        str(args.candidate_scan_stride),
        "--json",
    ]
    envelope = run_command(command, repo_root, timeout_seconds=args.analysis_timeout_seconds)
    parsed: dict[str, Any] | None = None
    if envelope.get("stdout"):
        try:
            parsed = extract_json(str(envelope["stdout"]))
        except Exception:
            parsed = None
    return parsed, envelope


def build_self_test() -> dict[str, Any]:
    poses = parse_pose_plan(DEFAULT_POSE_PLAN)
    if len(poses) != 4:
        return {"status": "failed", "errors": ["default pose plan did not parse into 4 poses"]}
    if poses[-1]["role"] != "displaced":
        return {"status": "failed", "errors": ["default final pose is not displaced"]}
    return {"status": "passed", "errors": [], "poses": poses}


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture sequential family-group snapshots for offline delta analysis.")
    parser.add_argument("--pid", type=int, required=False)
    parser.add_argument("--hwnd", required=False)
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument(
        "--current-truth-json",
        type=Path,
        default=None,
        help=(
            "Current truth JSON used to fill missing PID/HWND/start/module fields and add the "
            "bestCurrentCandidate as the highest-priority family prior. Defaults to "
            "docs/recovery/current-truth.json when present."
        ),
    )
    parser.add_argument(
        "--disable-current-truth",
        action="store_true",
        help="Do not import target defaults or candidate priors from current-truth.json.",
    )
    parser.add_argument("--scan-plan", default=None)
    parser.add_argument("--top-count", type=int, default=20)
    parser.add_argument("--max-total-ranges", type=int, default=40)
    parser.add_argument("--max-prior-ranges", type=int, default=20)
    parser.add_argument("--disable-default-priors", action="store_true")
    parser.add_argument("--prior-address", action="append", default=[])
    parser.add_argument("--prior-family", action="append", default=[])
    parser.add_argument("--prior-radius", type=lambda value: int(value, 0), default=0x200000)
    parser.add_argument("--prior-family-span", type=lambda value: int(value, 0), default=0x1000000)
    parser.add_argument("--prior-family-step", type=lambda value: int(value, 0), default=0x1000000)
    parser.add_argument("--prior-neighbor-family-count", type=int, default=1)
    parser.add_argument("--prior-alignment", type=lambda value: int(value, 0), default=0x1000)
    parser.add_argument("--pose-plan", default=DEFAULT_POSE_PLAN)
    parser.add_argument("--expected-start-time-utc", default=None)
    parser.add_argument("--expected-module-base", default=None)
    parser.add_argument("--segment-bytes", type=int, default=4 * 1024 * 1024)
    parser.add_argument("--max-bytes-per-pose", type=int, default=512 * 1024 * 1024)
    parser.add_argument("--manual-displacement-timeout-seconds", type=int, default=120)
    parser.add_argument("--no-manual-displacement", action="store_true")
    parser.add_argument("--auto-displacement-key", default=None)
    parser.add_argument(
        "--auto-displacement-input-backend",
        choices=(DEFAULT_AUTO_DISPLACEMENT_INPUT_BACKEND, "window-message"),
        default=DEFAULT_AUTO_DISPLACEMENT_INPUT_BACKEND,
        help=(
            "Live auto-displacement backend. Default/allowed backend is repo-owned C# SendInput ScanCode. "
            "The legacy window-message value is retained only to fail closed with an explicit blocker."
        ),
    )
    parser.add_argument("--auto-displacement-hold-ms", type=int, default=1000)
    parser.add_argument("--auto-displacement-timeout-seconds", type=int, default=15)
    parser.add_argument("--require-client-width", type=int, default=None)
    parser.add_argument("--require-client-height", type=int, default=None)
    parser.add_argument(
        "--disable-emergency-key-release-guard",
        action="store_true",
        help="Disable the default keyup-only pre/post guard around auto-displacement input.",
    )
    parser.add_argument(
        "--allow-current-truth-movement-gate-override",
        action="store_true",
        help=(
            "Allow auto-displacement even when current-truth movementGate is blocked. "
            "Use only after explicit operator reauthorization and incident review."
        ),
    )
    parser.add_argument(
        "--allow-window-message-auto-displacement",
        action="store_true",
        help=(
            "Deprecated compatibility flag. The legacy WindowMessage auto-displacement backend remains retired after "
            "the live spin incident; use --auto-displacement-input-backend csharp-scancode instead."
        ),
    )
    parser.add_argument("--skip-analysis", action="store_true")
    parser.add_argument("--axis-orders", default="xyz")
    parser.add_argument("--candidate-scan-stride", type=int, choices=(1, 4), default=1)
    parser.add_argument(
        "--reference-source",
        choices=("rrapicoord", "chromalink"),
        default=DEFAULT_REFERENCE_SOURCE,
        help=(
            "Reference coordinate source captured before each pose. Default is RRAPICOORD because "
            "ChromaLink world-state can be reachable but stale."
        ),
    )
    parser.add_argument("--reference-scan-context-bytes", type=int, default=4096)
    parser.add_argument("--reference-max-hits", type=int, default=512)
    parser.add_argument("--reference-scan-attempts", type=int, default=5)
    parser.add_argument("--reference-scan-retry-delay-milliseconds", type=int, default=1500)
    parser.add_argument("--reference-tolerance", type=float, default=0.25)
    parser.add_argument("--preflight-timeout-seconds", type=int, default=30)
    parser.add_argument("--reference-timeout-seconds", type=int, default=DEFAULT_REFERENCE_TIMEOUT_SECONDS)
    parser.add_argument("--analysis-timeout-seconds", type=int, default=300)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    apply_current_truth_context(args, repo_root)
    run_pid = args.pid if args.pid is not None else "selftest"
    run_dir = args.output_root.resolve() if args.output_root else repo_root / "scripts" / "captures" / f"family-snapshot-sequence-currentpid-{run_pid}-{utc_stamp()}"
    summary_path = run_dir / "summary.json"
    markdown_path = run_dir / "summary.md"
    manifest_path = run_dir / "manifest.json"
    command_envelopes_path = run_dir / "command-envelopes.json"

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-current-pid-family-snapshot-sequence",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "blockers": [],
        "warnings": [],
        "errors": [],
        "repoRoot": str(repo_root),
        "currentTruth": getattr(args, "current_truth_context", None),
        "processId": args.pid,
        "targetWindowHandle": args.hwnd,
        "scanPlanJson": None,
        "referenceSource": args.reference_source,
        "autoDisplacementInputBackend": getattr(args, "auto_displacement_input_backend", DEFAULT_AUTO_DISPLACEMENT_INPUT_BACKEND),
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgLaunched": False,
            "debuggerAttached": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "providerWrites": False,
            "githubConnectorWrites": False,
        },
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(summary_path),
            "summaryMarkdown": str(markdown_path),
            "manifestJson": str(manifest_path),
            "commandEnvelopesJson": str(command_envelopes_path),
        },
        "next": {},
    }
    manifest: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-family-snapshot-sequence",
        "generatedAtUtc": utc_iso(),
        "repoRoot": str(repo_root),
        "currentTruth": getattr(args, "current_truth_context", None),
        "processId": args.pid,
        "targetWindowHandle": args.hwnd,
        "processName": args.process_name,
        "referenceSource": args.reference_source,
        "autoDisplacementInputBackend": getattr(args, "auto_displacement_input_backend", DEFAULT_AUTO_DISPLACEMENT_INPUT_BACKEND),
        "safety": summary["safety"].copy(),
        "poses": [],
    }
    command_envelopes: list[dict[str, Any]] = []
    exit_code = 1

    try:
        if args.self_test:
            self_test = build_self_test()
            summary["selfTest"] = self_test
            summary["status"] = self_test["status"]
            if self_test["status"] == "passed":
                summary["warnings"].append("self-test only; no live process queried")
                exit_code = 0
            else:
                summary["errors"].extend(self_test["errors"])
                exit_code = 1
            return exit_code

        summary["warnings"].extend(getattr(args, "current_truth_warnings", []) or [])
        if getattr(args, "current_truth_blockers", None):
            summary["blockers"].extend(str(blocker) for blocker in args.current_truth_blockers)
            summary["status"] = "blocked"
            summary["next"]["recommendedAction"] = (
                "Refresh current-truth, pass the matching target, or use --disable-current-truth for an explicit exploratory run."
            )
            exit_code = 2
            return exit_code

        if args.pid is None or args.hwnd is None:
            raise RuntimeError("--pid and --hwnd are required unless --self-test is used")

        poses = parse_pose_plan(args.pose_plan)
        scan_plan = Path(args.scan_plan).resolve() if args.scan_plan else latest_scan_plan(repo_root, args.pid)
        scan_ranges, range_strategy = select_adaptive_scan_ranges(scan_plan, args)
        summary["scanPlanJson"] = str(scan_plan)
        summary["rangeStrategy"] = range_strategy
        manifest["scanPlanJson"] = str(scan_plan)
        manifest["rangeStrategy"] = range_strategy
        manifest["scanRanges"] = scan_ranges
        manifest["posePlan"] = poses

        if args.plan_only:
            summary["status"] = "passed"
            summary["warnings"].append("plan-only requested; no process memory read")
            summary["next"]["recommendedAction"] = "Run without --plan-only to capture family snapshots."
            manifest["poses"] = []
            exit_code = 0
            return exit_code

        if args.auto_displacement_key:
            if getattr(args, "allow_window_message_auto_displacement", False):
                summary["warnings"].append(
                    "deprecated-window-message-auto-displacement-flag-ignored:csharp-scancode-is-the-only-allowed-diagnostic-backend"
                )
            movement_gate_blockers = current_truth_auto_displacement_blockers(args)
            if movement_gate_blockers and not args.allow_current_truth_movement_gate_override:
                summary["blockers"].extend(movement_gate_blockers)
                summary["status"] = "blocked"
                summary["next"]["recommendedAction"] = (
                    "Review and clear the current-truth movement gate before using --auto-displacement-key, "
                    "or rerun without auto-displacement for operator-managed poses."
                )
                exit_code = 2
                return exit_code
            if movement_gate_blockers and args.allow_current_truth_movement_gate_override:
                summary["warnings"].extend(f"movement-gate-override:{blocker}" for blocker in movement_gate_blockers)
            backend_blockers = auto_displacement_backend_blockers(args)
            if backend_blockers:
                summary["blockers"].extend(backend_blockers)
                summary["status"] = "blocked"
                summary["next"]["recommendedAction"] = (
                    "Use the C# SendInput ScanCode backend for bounded diagnostics only; rerun without auto-displacement "
                    "or with --auto-displacement-input-backend csharp-scancode after movement-gate reauthorization."
                )
                exit_code = 2
                return exit_code

        run_dir.mkdir(parents=True, exist_ok=True)
        preflight, preflight_envelope = run_preflight(repo_root, args, run_dir)
        command_envelopes.append(
            compact_envelope(preflight_envelope, "preflight")
        )
        manifest["preflight"] = preflight

        for pose_spec in poses:
            if pose_spec["role"] == "displaced":
                if args.auto_displacement_key:
                    geometry_blockers, geometry = required_client_geometry_blockers(args)
                    if geometry is not None:
                        summary["clientGeometryGate"] = geometry
                        manifest["clientGeometryGate"] = geometry
                    if geometry_blockers:
                        summary["blockers"].extend(geometry_blockers)
                        summary["next"]["recommendedAction"] = (
                            "Resize the exact target window to the required client geometry before auto-displacement."
                        )
                        break
                    if not args.disable_emergency_key_release_guard:
                        pre_release_ok, pre_release_envelope = run_emergency_key_release(
                            repo_root,
                            args,
                            run_dir,
                            stage="pre-auto-displacement",
                        )
                        command_envelopes.append(
                            compact_envelope(pre_release_envelope, "pre-auto-displacement-key-release")
                        )
                        if not pre_release_ok:
                            summary["blockers"].append("pre-auto-displacement-key-release-failed")
                            break
                    ok, input_envelope = run_auto_displacement(repo_root, args)
                    command_envelopes.append(
                        compact_envelope(input_envelope, "auto-displacement")
                    )
                    post_release_ok = True
                    if not args.disable_emergency_key_release_guard:
                        post_release_ok, post_release_envelope = run_emergency_key_release(
                            repo_root,
                            args,
                            run_dir,
                            stage="post-auto-displacement",
                        )
                        command_envelopes.append(
                            compact_envelope(post_release_envelope, "post-auto-displacement-key-release")
                        )
                    if not ok:
                        summary["blockers"].append("auto-displacement-input-failed")
                        break
                    if not post_release_ok:
                        summary["blockers"].append("post-auto-displacement-key-release-failed")
                        break
                    summary["safety"]["movementSent"] = True
                    summary["safety"]["inputSent"] = True
                    manifest["safety"]["movementSent"] = True
                    manifest["safety"]["inputSent"] = True
                    write_json(manifest_path, manifest)
                elif args.no_manual_displacement:
                    summary["warnings"].append("manual displacement disabled; skipping displaced pose")
                    continue
                elif not wait_for_enter_or_timeout(args.manual_displacement_timeout_seconds):
                    summary["blockers"].append("blocked-no-displaced-pose")
                    break
            if float(pose_spec["settleSeconds"]) > 0:
                time.sleep(float(pose_spec["settleSeconds"]))
            try:
                pose, envelopes = snapshot_pose(repo_root=repo_root, run_dir=run_dir, pose_spec=pose_spec, scan_ranges=scan_ranges, args=args)
            except CommandEnvelopeError as exc:
                command_envelopes.append(compact_envelope(exc.envelope, f"reference:{pose_spec['label']}"))
                raise RuntimeError(str(exc)) from exc
            manifest["poses"].append(pose)
            command_envelopes.extend(envelopes)
            summary["safety"]["targetMemoryBytesRead"] = True
            manifest["safety"]["targetMemoryBytesRead"] = True
            write_json(manifest_path, manifest)

        if not any(pose.get("role") == "displaced" for pose in manifest["poses"]):
            if "blocked-no-displaced-pose" not in summary["blockers"]:
                summary["blockers"].append("blocked-no-displaced-pose")

        if not args.skip_analysis and manifest["poses"]:
            write_json(manifest_path, manifest)
            analysis, analysis_envelope = run_analyzer(repo_root, run_dir, args)
            command_envelopes.append(
                compact_envelope(analysis_envelope, "delta-analysis")
            )
            summary["analysis"] = analysis
            summary["artifacts"]["deltaSummaryJson"] = str(run_dir / "delta-analysis" / "delta-summary.json")
            summary["artifacts"]["candidateVec3Json"] = str(run_dir / "delta-analysis" / "candidate-vec3.json")
            summary["artifacts"]["candidateVec3Jsonl"] = str(run_dir / "delta-analysis" / "candidate-vec3.jsonl")
            summary["artifacts"]["candidateFamiliesJson"] = str(run_dir / "delta-analysis" / "candidate-families.json")
            if analysis and analysis.get("status") == "passed":
                summary["status"] = "passed"
                summary["next"]["recommendedAction"] = "Run focused readback/ranking on candidate-vec3.jsonl; do not promote until proof gates pass."
                exit_code = 0
            else:
                summary["status"] = "blocked"
                if analysis:
                    for blocker in analysis.get("blockers") or []:
                        if blocker not in summary["blockers"]:
                            summary["blockers"].append(str(blocker))
                summary["next"]["recommendedAction"] = "Capture a valid displaced pose or widen family ranges before x64dbg."
                exit_code = 2
        else:
            summary["status"] = "blocked" if summary["blockers"] else "captured"
            summary["next"]["recommendedAction"] = "Run family_snapshot_delta_analyzer.py against manifest.json."
            exit_code = 2 if summary["blockers"] else 0
        return exit_code
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        exit_code = 1
        return exit_code
    finally:
        write_json(manifest_path, manifest)
        write_json(command_envelopes_path, command_envelopes)
        write_json(summary_path, summary)
        markdown_path.write_text(render_markdown(summary, manifest), encoding="utf-8")
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(
                json.dumps(
                    {
                        "status": summary.get("status"),
                        "blockers": summary.get("blockers"),
                        "summaryJson": str(summary_path),
                        "manifestJson": str(manifest_path),
                        "deltaSummaryJson": summary.get("artifacts", {}).get("deltaSummaryJson"),
                    },
                    indent=2,
                )
            )


if __name__ == "__main__":
    raise SystemExit(main())
