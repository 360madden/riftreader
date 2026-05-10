#!/usr/bin/env python3
# Version: riftreader-reacquire-current-pid-coordinate-candidate-v0.1.1
# Total-Character-Count: 11750
# Purpose: Reacquire current-PID coordinate candidates by capturing a fresh RRAPICOORD reference, optionally generating local RiftScan candidates, and running RiftReader readback with absolute paths only.

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_compact_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() and (candidate / "scripts").is_dir():
            return candidate
    raise RuntimeError(f"Could not find RiftReader repo root from {start}")


def resolve_powershell() -> str:
    for exe in ("pwsh", "powershell"):
        found = shutil.which(exe)
        if found:
            return found
    raise RuntimeError("Neither pwsh nor powershell was found on PATH.")


def extract_json(text: str) -> Any:
    value = text.strip()
    if not value:
        raise RuntimeError("Command produced no stdout JSON.")

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass

    starts = [idx for idx in (value.find("{"), value.find("[")) if idx >= 0]
    if not starts:
        raise RuntimeError(f"No JSON object or array found. Output preview: {value[:500]}")

    decoder = json.JSONDecoder()
    try:
        parsed, _ = decoder.raw_decode(value[min(starts):])
        return parsed
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not parse JSON. {exc}. Output preview: {value[:1000]}") from exc


def run_command(args: list[str], cwd: Path, *, allow_failure: bool = False) -> dict[str, Any]:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    envelope = {
        "args": args,
        "cwd": str(cwd),
        "exitCode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "completedAtUtc": utc_iso(),
    }
    if result.returncode != 0 and not allow_failure:
        raise RuntimeError(
            "Command failed "
            f"exit={result.returncode}: {' '.join(args)}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return envelope


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def run_git_status(repo_root: Path) -> str:
    result = run_command(["git", "--no-pager", "status", "-sb"], repo_root, allow_failure=True)
    return (result["stdout"] + result["stderr"]).strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reacquire current-PID coordinate candidate evidence using absolute paths."
    )
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--hwnd", required=True)
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--riftscan-root", default=r"C:\RIFT MODDING\Riftscan")
    parser.add_argument("--candidate-file", default=None)
    parser.add_argument("--authorize-riftscan-generation", action="store_true")
    parser.add_argument("--reference-max-age-seconds", type=int, default=180)
    parser.add_argument("--top-reference-matches", type=int, default=10)
    parser.add_argument("--top-count", type=int, default=16)
    parser.add_argument("--readback-sample-count", type=int, default=2)
    parser.add_argument("--scan-context-bytes", type=int, default=16384)
    parser.add_argument("--max-hits", type=int, default=512)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    scripts_dir = repo_root / "scripts"
    capture_script = scripts_dir / "capture-rift-api-reference-coordinate.ps1"
    readback_script = scripts_dir / "invoke-riftscan-coordinate-readback.ps1"

    if not capture_script.exists():
        raise FileNotFoundError(capture_script)
    if not readback_script.exists():
        raise FileNotFoundError(readback_script)

    if not args.candidate_file and not args.authorize_riftscan_generation:
        raise RuntimeError(
            "No --candidate-file supplied. Add --authorize-riftscan-generation to allow local RiftScan passive "
            "candidate/session/report generation, or pass --candidate-file for readback-only mode."
        )

    powershell = resolve_powershell()
    run_dir = repo_root / "scripts" / "captures" / f"reacquire-currentpid-{args.pid}-{utc_compact_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    reference_file = run_dir / f"currentpid-{args.pid}-reference.json"
    readback_raw_file = run_dir / f"currentpid-{args.pid}-riftscan-readback-raw.txt"
    summary_file = run_dir / f"currentpid-{args.pid}-candidate-readback-summary.json"
    markdown_file = run_dir / f"currentpid-{args.pid}-candidate-readback-summary.md"

    capture_cmd = [
        powershell,
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(capture_script),
        "-ProcessName",
        args.process_name,
        "-ProcessId",
        str(args.pid),
        "-TargetWindowHandle",
        args.hwnd,
        "-OutputRoot",
        str(run_dir),
        "-OutputFile",
        str(reference_file),
        "-ScanContextBytes",
        str(args.scan_context_bytes),
        "-MaxHits",
        str(args.max_hits),
        "-Json",
    ]

    capture_envelope = run_command(capture_cmd, repo_root)
    capture_json = extract_json(capture_envelope["stdout"])
    if str(capture_json.get("Status", "")).lower() != "captured":
        raise RuntimeError(f"Reference capture did not return captured status: {capture_json}")

    readback_cmd = [
        powershell,
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(readback_script),
        "-ProcessName",
        args.process_name,
        "-ProcessId",
        str(args.pid),
        "-TargetWindowHandle",
        args.hwnd,
        "-ReferenceFile",
        str(reference_file),
        "-ReferenceMaxAgeSeconds",
        str(args.reference_max_age_seconds),
        "-TopReferenceMatches",
        str(args.top_reference_matches),
        "-TopCount",
        str(args.top_count),
        "-ReadbackSampleCount",
        str(args.readback_sample_count),
        "-SkipProofAnchorCheck",
        "-Json",
    ]

    if args.candidate_file:
        readback_cmd.extend(["-CandidateFile", str(Path(args.candidate_file).resolve())])
    else:
        readback_cmd.extend(["-RiftScanRoot", str(Path(args.riftscan_root).resolve())])

    readback_envelope = run_command(readback_cmd, repo_root, allow_failure=True)
    readback_raw_file.write_text(
        "STDOUT:\n" + readback_envelope["stdout"] + "\nSTDERR:\n" + readback_envelope["stderr"],
        encoding="utf-8",
    )

    readback_json: Any | None = None
    parse_error: str | None = None
    try:
        readback_json = extract_json(readback_envelope["stdout"])
    except Exception as exc:  # noqa: BLE001
        parse_error = f"{type(exc).__name__}: {exc}"

    concise = {
        "readbackStatus": readback_json.get("Status") if isinstance(readback_json, dict) else None,
        "candidateFile": readback_json.get("CandidateFile") if isinstance(readback_json, dict) else None,
        "candidateCount": readback_json.get("CandidateCount") if isinstance(readback_json, dict) else None,
        "decodedCandidateCount": readback_json.get("DecodedCandidateCount") if isinstance(readback_json, dict) else None,
        "stableDecodedCandidateCount": readback_json.get("StableDecodedCandidateCount") if isinstance(readback_json, dict) else None,
        "referenceMatchCount": readback_json.get("ReferenceMatchCount") if isinstance(readback_json, dict) else None,
        "summaryFile": readback_json.get("SummaryFile") if isinstance(readback_json, dict) else None,
    }

    status = "passed" if readback_envelope["exitCode"] == 0 and isinstance(readback_json, dict) else "failed"
    summary = {
        "schemaVersion": 1,
        "mode": "riftreader-current-pid-coordinate-candidate-reacquire",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "repoRoot": str(repo_root),
        "processName": args.process_name,
        "processId": args.pid,
        "targetWindowHandle": args.hwnd,
        "authorization": {
            "riftscanGenerationAuthorized": bool(args.authorize_riftscan_generation),
            "candidateFileProvided": bool(args.candidate_file),
            "noCheatEngine": True,
            "movementSent": False,
            "inputSent": False,
            "githubConnectorWrites": False,
        },
        "reference": {
            "status": capture_json.get("Status"),
            "file": str(reference_file),
            "coordinate": capture_json.get("Coordinate"),
            "markerCount": capture_json.get("MarkerCount"),
            "usableMarkerCount": capture_json.get("UsableMarkerCount"),
        },
        "readback": {
            "exitCode": readback_envelope["exitCode"],
            "parseError": parse_error,
            "rawOutputFile": str(readback_raw_file),
            "json": readback_json,
        },
        "concise": concise,
        "files": {
            "runDirectory": str(run_dir),
            "referenceFile": str(reference_file),
            "readbackRawFile": str(readback_raw_file),
            "summaryFile": str(summary_file),
            "markdownFile": str(markdown_file),
        },
        "gitStatus": run_git_status(repo_root),
        "next": {
            "movementAllowed": False,
            "note": "Candidate/readback evidence is not movement permission. Proof-anchor promotion and fresh ProofOnly are still required.",
        },
    }

    write_json(summary_file, summary)
    markdown_file.write_text(
        "\n".join([
            "# Current-PID coordinate candidate reacquire summary",
            "",
            f"- Status: `{status}`",
            f"- PID/HWND: `{args.pid}` / `{args.hwnd}`",
            f"- Reference file: `{reference_file}`",
            f"- Readback raw file: `{readback_raw_file}`",
            f"- Candidate file: `{concise['candidateFile']}`",
            f"- Candidate count: `{concise['candidateCount']}`",
            f"- Reference matches: `{concise['referenceMatchCount']}`",
            "",
            "Movement remains blocked. This helper sends no input and uses no Cheat Engine.",
            "",
            "# END_OF_SCRIPT_MARKER",
            "",
        ]),
        encoding="utf-8",
    )

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print("=== CONCISE RESULT ===")
        print(json.dumps(concise, indent=2))
        print("=== FILES ===")
        print(json.dumps(summary["files"], indent=2))
        print(f"status={status}")

    return 0 if status == "passed" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)

# END_OF_SCRIPT_MARKER
