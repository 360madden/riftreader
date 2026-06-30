#!/usr/bin/env python3
"""Read back current-PID coordinate candidates against a fresh API reference.

This is a candidate-only safety gate.  It reads explicit vec3 addresses from a
candidate file, captures a fresh ChromaLink/RRAPI coordinate reference, and
reports whether each candidate still tracks the same coordinate family directly
or through a stable per-axis origin offset observed in the snapshot-delta run.

It sends no input, launches no debugger, uses no Cheat Engine, writes no
provider state, and does not promote movement truth.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from scan_current_pid_coordinate_family import (  # noqa: E402
    close_handle,
    extract_json,
    find_repo_root,
    format_hex,
    get_process_start_utc,
    open_process,
    process_start_matches,
    query_process_image,
    read_memory,
    resolve_powershell,
    run_command,
    verify_hwnd_owner,
)

try:
    from .workflow_common import utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution path
    from workflow_common import utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def coordinate_from_mapping(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    axes: dict[str, float] = {}
    for axis in ("x", "y", "z"):
        parsed = to_float(value.get(axis, value.get(axis.upper())))
        if parsed is None:
            return None
        axes[axis] = parsed
    return axes


def max_abs_delta(left: dict[str, float], right: dict[str, float]) -> float:
    return max(abs(float(left[axis]) - float(right[axis])) for axis in ("x", "y", "z"))


def subtract(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    return {axis: float(left[axis]) - float(right[axis]) for axis in ("x", "y", "z")}


def add(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    return {axis: float(left[axis]) + float(right[axis]) for axis in ("x", "y", "z")}


def average_offsets(offsets: list[dict[str, float]]) -> dict[str, float] | None:
    if not offsets:
        return None
    return {axis: sum(item[axis] for item in offsets) / len(offsets) for axis in ("x", "y", "z")}


def offset_spread(offsets: list[dict[str, float]]) -> dict[str, Any]:
    if not offsets:
        return {"maxAbs": None, "perAxis": {}}
    per_axis: dict[str, float] = {}
    for axis in ("x", "y", "z"):
        values = [float(item[axis]) for item in offsets]
        per_axis[axis] = max(values) - min(values)
    return {"maxAbs": max(per_axis.values()), "perAxis": per_axis}


def candidate_address(candidate: dict[str, Any]) -> int | None:
    for key in ("addressHex", "absolute_address_hex", "absoluteAddressHex", "address"):
        value = candidate.get(key)
        if value is None:
            continue
        try:
            return int(str(value), 0)
        except (TypeError, ValueError):
            continue
    return None


def candidate_id(candidate: dict[str, Any], index: int) -> str:
    for key in ("candidateId", "candidate_id", "id"):
        value = candidate.get(key)
        if value:
            return str(value)
    address = candidate_address(candidate)
    return f"candidate-{index:06d}-{format_hex(address) if address is not None else 'unknown'}"


def load_candidates(path: Path, top: int) -> list[dict[str, Any]]:
    if not path.exists():
        raise RuntimeError(f"candidate file not found: {path}")
    candidates: list[dict[str, Any]] = []
    if path.suffix.lower() == ".jsonl":
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped:
                candidates.append(json.loads(stripped))
    else:
        document = json.loads(path.read_text(encoding="utf-8"))
        raw = document.get("candidates") if isinstance(document, dict) else document
        if not isinstance(raw, list):
            raise RuntimeError(f"candidate JSON does not contain a candidate list: {path}")
        candidates = [item for item in raw if isinstance(item, dict)]
    return candidates[: max(1, int(top))]


def load_reference_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"reference file not found: {path}")
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict):
        raise RuntimeError(f"reference JSON does not contain an object: {path}")
    coord = document.get("coordinate") or document.get("Coordinate") or document
    reference = coordinate_from_mapping(coord)
    if reference is None:
        raise RuntimeError(f"reference file missing coordinate x/y/z: {path}")
    return {"coordinate": reference, "raw": document, "referenceFile": str(path.resolve())}


def snapshot_offsets(candidate: dict[str, Any]) -> list[dict[str, float]]:
    offsets: list[dict[str, float]] = []
    for prefix in ("baseline", "displaced"):
        value = coordinate_from_mapping(candidate.get(f"{prefix}Value"))
        reference = coordinate_from_mapping(candidate.get(f"{prefix}Reference"))
        if value and reference:
            offsets.append(subtract(reference, value))

    # Older candidate formats carry only one value/reference pair.
    value_preview = candidate.get("value_preview", candidate.get("valuePreview"))
    reference = coordinate_from_mapping(candidate.get("reference_coordinate", candidate.get("referenceCoordinate")))
    if isinstance(value_preview, list) and len(value_preview) >= 3 and reference:
        value = {"x": float(value_preview[0]), "y": float(value_preview[1]), "z": float(value_preview[2])}
        offsets.append(subtract(reference, value))

    return offsets


def read_vec3(handle: int, address: int) -> dict[str, float] | None:
    data = read_memory(handle, address, 12)
    if data is None or len(data) < 12:
        return None
    x, y, z = struct.unpack_from("<fff", data, 0)
    values = {"x": float(x), "y": float(y), "z": float(z)}
    if not all(math.isfinite(values[axis]) for axis in ("x", "y", "z")):
        return None
    return values


def capture_reference(repo_root: Path, run_dir: Path, pid: int, hwnd: str, process_name: str, timeout_seconds: int) -> tuple[dict[str, Any], dict[str, Any], Path]:
    ps = resolve_powershell()
    output = run_dir / "fresh-reference-coordinate.json"
    command = [
        ps,
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(repo_root / "scripts" / "capture-rift-api-reference-coordinate.ps1"),
        "-ProcessName",
        process_name,
        "-ProcessId",
        str(pid),
        "-TargetWindowHandle",
        hwnd,
        "-OutputRoot",
        str(run_dir),
        "-OutputFile",
        str(output),
        "-ScanContextBytes",
        "16384",
        "-MaxHits",
        "512",
        "-Json",
    ]
    envelope = run_command(command, repo_root, timeout_seconds=timeout_seconds)
    if envelope.get("timedOut") or envelope.get("exitCode") != 0:
        raise RuntimeError(f"reference_capture_failed: exit={envelope.get('exitCode')}; timedOut={envelope.get('timedOut')}")
    parsed = extract_json(str(envelope.get("stdout") or ""))
    coord = parsed.get("Coordinate") if isinstance(parsed, dict) else None
    reference = coordinate_from_mapping(coord)
    if reference is None:
        raise RuntimeError(f"reference_capture_missing_coordinate: {parsed}")
    return {"coordinate": reference, "raw": parsed, "referenceFile": str(output)}, envelope, output


def classify_readback(
    *,
    memory_value: dict[str, float],
    reference: dict[str, float],
    offsets: list[dict[str, float]],
    direct_tolerance: float,
    offset_tolerance: float,
) -> dict[str, Any]:
    direct_delta = max_abs_delta(memory_value, reference)
    average_offset = average_offsets(offsets)
    spread = offset_spread(offsets)
    corrected_value = add(memory_value, average_offset) if average_offset else None
    corrected_delta = max_abs_delta(corrected_value, reference) if corrected_value else None
    offset_spread_ok = bool(spread["maxAbs"] is not None and float(spread["maxAbs"]) <= offset_tolerance)
    direct_ok = direct_delta <= direct_tolerance
    corrected_ok = bool(corrected_delta is not None and corrected_delta <= direct_tolerance and offset_spread_ok)
    if direct_ok:
        classification = "direct-current-coordinate-candidate"
    elif corrected_ok:
        classification = "offset-corrected-current-coordinate-candidate"
    else:
        classification = "readback-mismatch"
    return {
        "classification": classification,
        "directMaxAbsDelta": direct_delta,
        "offsetCorrectedMaxAbsDelta": corrected_delta,
        "offsetSpread": spread,
        "averageOffset": average_offset,
        "offsetCorrectedValue": corrected_value,
        "directWithinTolerance": direct_ok,
        "offsetCorrectedWithinTolerance": corrected_ok,
    }


def route_reference_match(item: dict[str, Any]) -> dict[str, Any]:
    reference_delta = item.get("directMaxAbsDelta")
    if item.get("classification") == "offset-corrected-current-coordinate-candidate":
        reference_delta = item.get("offsetCorrectedMaxAbsDelta")
    reference_matches = item.get("classification") in {
        "direct-current-coordinate-candidate",
        "offset-corrected-current-coordinate-candidate",
    }
    spread = item.get("offsetSpread") if isinstance(item.get("offsetSpread"), dict) else {}
    return {
        "CandidateId": item.get("candidateId"),
        "CandidateAddressHex": item.get("addressHex"),
        "ReferenceMatchesReadback": reference_matches,
        "ReferenceMaxAbsDelta": reference_delta,
        "StableAcrossReadbackSamples": bool(reference_matches and item.get("snapshotOffsetCount", 0) >= 1),
        "SourcePreviewMatchesReadback": reference_matches,
        "Classification": item.get("classification"),
        "DirectMaxAbsDelta": item.get("directMaxAbsDelta"),
        "OffsetCorrectedMaxAbsDelta": item.get("offsetCorrectedMaxAbsDelta"),
        "OffsetSpreadMaxAbs": spread.get("maxAbs"),
        "TruthReadiness": item.get("truthReadiness"),
    }


def render_markdown(summary: dict[str, Any]) -> str:
    rows = []
    for item in summary.get("readbacks", [])[:10]:
        rows.append(
            "| {rank} | `{candidate}` | `{address}` | `{classification}` | {direct:.6f} | {corrected} |".format(
                rank=item.get("rank"),
                candidate=item.get("candidateId"),
                address=item.get("addressHex"),
                classification=item.get("classification"),
                direct=float(item.get("directMaxAbsDelta") or 0.0),
                corrected=(
                    f"{float(item['offsetCorrectedMaxAbsDelta']):.6f}"
                    if item.get("offsetCorrectedMaxAbsDelta") is not None
                    else ""
                ),
            )
        )
    return "\n".join(
        [
            "# Current-PID candidate readback",
            "",
            f"- Status: `{summary.get('status')}`",
            f"- PID/HWND: `{summary.get('processId')}` / `{summary.get('targetWindowHandle')}`",
            f"- Candidate file: `{summary.get('candidateFile')}`",
            f"- Fresh reference file: `{summary.get('artifacts', {}).get('referenceFile')}`",
            f"- Best classification: `{summary.get('bestReadback', {}).get('classification')}`",
            "",
            "| Rank | Candidate | Address | Classification | Direct max abs delta | Offset-corrected max abs delta |",
            "|---:|---|---|---|---:|---:|",
            *rows,
            "",
            "Candidate-only readback. No input, x64dbg, Cheat Engine, provider writes, memory writes, or proof promotion were performed.",
            "",
        ]
    )


def build_self_test() -> dict[str, Any]:
    candidate = {
        "candidateId": "synthetic",
        "addressHex": "0x1000",
        "baselineValue": {"x": 95.0, "y": 195.0, "z": 295.0},
        "baselineReference": {"x": 100.0, "y": 200.0, "z": 300.0},
        "displacedValue": {"x": 96.0, "y": 195.0, "z": 296.0},
        "displacedReference": {"x": 101.0, "y": 200.0, "z": 301.0},
    }
    offsets = snapshot_offsets(candidate)
    result = classify_readback(
        memory_value={"x": 97.0, "y": 195.0, "z": 297.0},
        reference={"x": 102.0, "y": 200.0, "z": 302.0},
        offsets=offsets,
        direct_tolerance=0.75,
        offset_tolerance=0.25,
    )
    if result["classification"] != "offset-corrected-current-coordinate-candidate":
        return {"status": "failed", "errors": [f"unexpected classification {result['classification']}"], "result": result}
    return {"status": "passed", "errors": [], "result": result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Read back explicit current-PID coord candidates against fresh API coords.")
    parser.add_argument("--pid", type=int, required=False)
    parser.add_argument("--hwnd", required=False)
    parser.add_argument("--candidate-jsonl", required=False)
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--direct-tolerance", type=float, default=0.75)
    parser.add_argument("--offset-tolerance", type=float, default=0.75)
    parser.add_argument("--reference-file", default=None)
    parser.add_argument("--reference-timeout-seconds", type=int, default=90)
    parser.add_argument("--expected-process-start-utc", default=None)
    parser.add_argument("--module-base", default=None)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    run_pid = args.pid if args.pid is not None else "selftest"
    run_dir = repo_root / "scripts" / "captures" / f"candidate-readback-currentpid-{run_pid}-{utc_stamp()}"
    summary_path = run_dir / "candidate-readback-summary.json"
    markdown_path = run_dir / "candidate-readback-summary.md"

    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-current-pid-candidate-readback",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "blockers": [],
        "warnings": [],
        "errors": [],
        "repoRoot": str(repo_root),
        "processId": args.pid,
        "ProcessId": args.pid,
        "ProcessName": args.process_name,
        "targetWindowHandle": args.hwnd,
        "TargetWindowHandle": args.hwnd,
        "candidateFile": str(Path(args.candidate_jsonl).resolve()) if args.candidate_jsonl else None,
        "SourceCandidateFile": str(Path(args.candidate_jsonl).resolve()) if args.candidate_jsonl else None,
        "MovementSent": False,
        "InputSent": False,
        "NoCheatEngine": True,
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
        },
        "readbacks": [],
        "next": {},
        "target": {
            "pid": args.pid,
            "hwnd": args.hwnd,
            "moduleBase": args.module_base,
            "expectedProcessStartUtc": args.expected_process_start_utc,
            "processIdentityVerified": False,
        },
    }
    exit_code = 1

    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        if args.self_test:
            self_test = build_self_test()
            summary["selfTest"] = self_test
            summary["status"] = self_test["status"]
            summary["warnings"].append("self-test only; no live process queried")
            exit_code = 0 if self_test["status"] == "passed" else 1
            return exit_code

        if args.pid is None or args.hwnd is None or not args.candidate_jsonl:
            raise RuntimeError("--pid, --hwnd, and --candidate-jsonl are required unless --self-test is used")

        candidates = load_candidates(Path(args.candidate_jsonl).resolve(), args.top)
        if not candidates:
            summary["status"] = "blocked"
            summary["blockers"].append("no-candidates-loaded")
            exit_code = 2
            return exit_code

        hwnd_info = verify_hwnd_owner(args.hwnd, args.pid)
        summary["target"].update(hwnd_info)
        if hwnd_info.get("blocker"):
            summary["status"] = "blocked"
            summary["blockers"].append(str(hwnd_info["blocker"]))
            exit_code = 2
            return exit_code

        identity_handle = open_process(args.pid)
        try:
            actual_start = get_process_start_utc(identity_handle)
            summary["target"]["actualProcessStartUtc"] = actual_start
            image = query_process_image(identity_handle)
            summary["target"]["processImage"] = image
            if args.expected_process_start_utc:
                if not actual_start:
                    summary["status"] = "blocked"
                    summary["blockers"].append("process-start-unavailable")
                    exit_code = 2
                    return exit_code
                if not process_start_matches(actual_start, args.expected_process_start_utc):
                    summary["status"] = "blocked"
                    summary["blockers"].append("process-start-mismatch")
                    exit_code = 2
                    return exit_code
                summary["target"]["processIdentityVerified"] = True
            else:
                summary["warnings"].append("process-start-not-bound-pass---expected-process-start-utc-for-exact-target-safety")
        finally:
            close_handle(identity_handle)

        if args.reference_file:
            reference = load_reference_file(Path(args.reference_file).resolve())
            reference_envelope = None
            reference_file = Path(str(reference["referenceFile"]))
        else:
            reference, reference_envelope, reference_file = capture_reference(
                repo_root,
                run_dir,
                args.pid,
                args.hwnd,
                args.process_name,
                args.reference_timeout_seconds,
            )
        summary["reference"] = reference["coordinate"]
        summary["artifacts"]["referenceFile"] = str(reference_file)
        if reference_envelope is None:
            summary["warnings"].append("reference-file-reused-no-fresh-reference-capture")
        else:
            summary["commandEnvelopes"] = {
                "referenceCapture": {
                    **{key: value for key, value in reference_envelope.items() if key not in {"stdout", "stderr"}},
                    "stdoutPreview": str(reference_envelope.get("stdout") or "")[:2000],
                    "stderrPreview": str(reference_envelope.get("stderr") or "")[:2000],
                }
            }

        handle = open_process(args.pid)
        try:
            actual_start = get_process_start_utc(handle)
            summary["target"]["postReferenceActualProcessStartUtc"] = actual_start
            if args.expected_process_start_utc and not process_start_matches(actual_start, args.expected_process_start_utc):
                summary["status"] = "blocked"
                summary["blockers"].append("process-start-mismatch-after-reference-capture")
                exit_code = 2
                return exit_code
            readbacks = []
            for index, candidate in enumerate(candidates, start=1):
                address = candidate_address(candidate)
                if address is None:
                    readbacks.append({"rank": index, "candidateId": candidate_id(candidate, index), "status": "skipped", "blocker": "missing-address"})
                    continue
                memory_value = read_vec3(handle, address)
                if memory_value is None:
                    readbacks.append(
                        {
                            "rank": index,
                            "candidateId": candidate_id(candidate, index),
                            "addressHex": format_hex(address),
                            "status": "blocked",
                            "blocker": "read-failed",
                        }
                    )
                    continue
                offsets = snapshot_offsets(candidate)
                classification = classify_readback(
                    memory_value=memory_value,
                    reference=reference["coordinate"],
                    offsets=offsets,
                    direct_tolerance=args.direct_tolerance,
                    offset_tolerance=args.offset_tolerance,
                )
                readbacks.append(
                    {
                        "rank": index,
                        "candidateId": candidate_id(candidate, index),
                        "address": address,
                        "addressHex": format_hex(address),
                        "memoryValue": memory_value,
                        "reference": reference["coordinate"],
                        "snapshotOffsetCount": len(offsets),
                        "status": "read",
                        **classification,
                        "truthReadiness": "candidate_only_not_movement_proof",
                    }
                )
            summary["readbacks"] = sorted(
                readbacks,
                key=lambda item: (
                    0
                    if item.get("classification") == "direct-current-coordinate-candidate"
                    else 1
                    if item.get("classification") == "offset-corrected-current-coordinate-candidate"
                    else 9,
                    float(item.get("offsetCorrectedMaxAbsDelta") if item.get("offsetCorrectedMaxAbsDelta") is not None else item.get("directMaxAbsDelta", 1e9)),
                ),
            )
            summary["safety"]["targetMemoryBytesRead"] = True
        finally:
            close_handle(handle)

        matching = [
            item
            for item in summary["readbacks"]
            if item.get("classification") in {"direct-current-coordinate-candidate", "offset-corrected-current-coordinate-candidate"}
        ]
        summary["bestReadback"] = matching[0] if matching else (summary["readbacks"][0] if summary["readbacks"] else None)
        summary["readbackCandidateCount"] = len(summary["readbacks"])
        summary["matchingCandidateCount"] = len(matching)
        summary["DecodedCandidateCount"] = len(summary["readbacks"])
        summary["StableDecodedCandidateCount"] = len(matching)
        summary["ReferenceMatchCount"] = len(matching)
        summary["BestReferenceMatches"] = [route_reference_match(item) for item in matching[:10]]
        if matching:
            summary["status"] = "passed"
            summary["next"]["recommendedAction"] = "Run another short snapshot/readback after a distinct movement vector; still do not promote until proof-chain gates pass."
            exit_code = 0
        else:
            summary["status"] = "blocked"
            summary["blockers"].append("no-current-readback-match")
            summary["next"]["recommendedAction"] = "Refresh snapshots or widen family ranges; do not x64dbg until candidate quality improves."
            exit_code = 2
        return exit_code
    except Exception as exc:  # noqa: BLE001
        summary["status"] = "failed"
        summary["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        exit_code = 1
        return exit_code
    finally:
        write_json(summary_path, summary)
        markdown_path.write_text(render_markdown(summary), encoding="utf-8")
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(
                json.dumps(
                    {
                        "status": summary.get("status"),
                        "blockers": summary.get("blockers"),
                        "matchingCandidateCount": summary.get("matchingCandidateCount"),
                        "summaryJson": str(summary_path),
                    },
                    indent=2,
                )
            )


if __name__ == "__main__":
    raise SystemExit(main())
