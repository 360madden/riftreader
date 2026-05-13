#!/usr/bin/env python3
"""Run coordinate-family scans through a memory-region scan plan.

The batch runner is an orchestrator over
scripts/scan_current_pid_coordinate_family.py.  It sends no input, launches no
debugger, and makes no provider or Git writes.  Each child scan remains
read-only against the selected process.
"""

from __future__ import annotations

import argparse
import glob
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() and (candidate / "scripts").is_dir():
            return candidate
    raise RuntimeError(f"Could not find RiftReader repo root from {start}")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def extract_json(text: str) -> Any:
    value = (text or "").strip()
    if not value:
        raise RuntimeError("empty command output")
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass
    starts = [idx for idx in (value.find("{"), value.find("[")) if idx >= 0]
    starts = [idx for idx in starts if idx >= 0]
    if not starts:
        raise RuntimeError(f"no JSON object/array found; preview={value[:500]}")
    parsed, _ = json.JSONDecoder().raw_decode(value[min(starts) :])
    return parsed


def latest_scan_plan(repo_root: Path, pid: int) -> Path:
    pattern = str(repo_root / "scripts" / "captures" / f"memory-region-inventory-currentpid-{pid}-*" / "scan-plan.json")
    matches = [Path(p) for p in glob.glob(pattern)]
    if not matches:
        raise RuntimeError(f"no scan plan found for PID {pid}: {pattern}")
    return max(matches, key=lambda p: p.stat().st_mtime).resolve()


def load_plan(path: Path, top_count: int) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    ranges = document.get("ranges")
    if not isinstance(ranges, list):
        raise RuntimeError(f"scan plan does not contain ranges: {path}")
    return ranges[: max(1, int(top_count))]


def build_scan_command(
    repo_root: Path,
    pid: int,
    hwnd: str,
    scan_range: dict[str, Any],
    stride: int,
    tolerance: float,
    max_seconds: int,
    reference_file: Path | None,
    reference_timeout_seconds: int,
) -> list[str]:
    script = repo_root / "scripts" / "scan_current_pid_coordinate_family.py"
    args = [
        sys.executable,
        str(script),
        "--pid",
        str(pid),
        "--hwnd",
        str(hwnd),
        "--tolerance",
        str(tolerance),
        "--scan-stride",
        str(stride),
        "--min-address",
        str(scan_range["minAddressHex"]),
        "--max-address",
        str(scan_range["maxAddressHex"]),
        "--max-seconds",
        str(max_seconds),
        "--reference-timeout-seconds",
        str(reference_timeout_seconds),
        "--json",
    ]
    if reference_file is not None:
        args.extend(["--reference-file", str(reference_file)])
    return args


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


def result_from_child(scan_range: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "rank": scan_range.get("rank"),
        "minAddressHex": scan_range.get("minAddressHex"),
        "maxAddressHex": scan_range.get("maxAddressHex"),
        "spanMiB": scan_range.get("spanMiB"),
        "readableMiB": scan_range.get("readableMiB"),
        "regionCount": scan_range.get("regionCount"),
        "plannerScore": scan_range.get("plannerScore"),
        "exitCode": envelope.get("exitCode"),
        "timedOut": envelope.get("timedOut"),
        "durationSeconds": envelope.get("durationSeconds"),
        "status": "failed",
        "hitCount": None,
        "blockers": [],
        "warnings": [],
        "summaryJson": None,
        "candidateJsonl": None,
        "bestHit": None,
    }
    if envelope.get("timedOut"):
        result["blockers"].append("child_scan_timeout")
        return result
    try:
        parsed = extract_json(str(envelope.get("stdout") or ""))
        result["status"] = parsed.get("status")
        result["blockers"] = parsed.get("blockers") or []
        result["warnings"] = parsed.get("warnings") or []
        result["hitCount"] = parsed.get("scan", {}).get("hitCount")
        result["summaryJson"] = parsed.get("artifacts", {}).get("summaryJson")
        result["candidateJsonl"] = parsed.get("artifacts", {}).get("candidateJsonl")
        result["bestHit"] = parsed.get("scan", {}).get("bestHit")
    except Exception as exc:  # keep durable evidence rather than hiding parse failures.
        result["blockers"].append(f"child_output_parse_failed:{type(exc).__name__}:{exc}")
    return result


def render_markdown(summary: dict[str, Any]) -> str:
    rows = []
    for item in summary.get("rangeResults", []):
        rows.append(
            "| {rank} | `{min}`-`{max}` | {span} | `{status}` | {hits} | {seconds} |".format(
                rank=item.get("rank"),
                min=item.get("minAddressHex"),
                max=item.get("maxAddressHex"),
                span=item.get("spanMiB"),
                status=item.get("status"),
                hits=item.get("hitCount"),
                seconds=item.get("durationSeconds"),
            )
        )
    return "\n".join(
        [
            "# Current-PID coordinate scan-plan batch",
            "",
            f"- Status: `{summary.get('status')}`",
            f"- PID/HWND: `{summary.get('processId')}` / `{summary.get('targetWindowHandle')}`",
            f"- Stride: `{summary.get('scan', {}).get('stride')}`",
            f"- Ranges completed: `{summary.get('scan', {}).get('rangesCompleted')}`",
            f"- Total hits: `{summary.get('scan', {}).get('totalHits')}`",
            "",
            "| Rank | Range | Span MiB | Status | Hits | Seconds |",
            "|---:|---|---:|---|---:|---:|",
            *rows,
            "",
            "Movement remains blocked. This batch sends no input, launches no debugger, and uses no Cheat Engine.",
            "",
        ]
    )


def run_self_test(repo_root: Path) -> dict[str, Any]:
    fake = {
        "rank": 1,
        "minAddressHex": "0x1000",
        "maxAddressHex": "0x2000",
        "spanMiB": 0.004,
    }
    command = build_scan_command(repo_root, 1234, "0xABC", fake, 4, 2.0, 5, None, 5)
    errors: list[str] = []
    if "--min-address" not in command or "0x1000" not in command:
        errors.append("command missing min address")
    if "--scan-stride" not in command or "4" not in command:
        errors.append("command missing stride")
    return {"status": "passed" if not errors else "failed", "errors": errors, "command": command}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run current-PID coordinate scans through a region scan plan.")
    parser.add_argument("--pid", type=int, required=False)
    parser.add_argument("--hwnd", required=False)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--scan-plan", default=None)
    parser.add_argument("--reference-file", default=None)
    parser.add_argument("--top-count", type=int, default=20)
    parser.add_argument("--stride", type=int, choices=(1, 4), default=4)
    parser.add_argument("--tolerance", type=float, default=2.0)
    parser.add_argument("--max-seconds-per-range", type=int, default=45)
    parser.add_argument("--reference-timeout-seconds", type=int, default=45)
    parser.add_argument("--stop-on-hit", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    run_pid = args.pid if args.pid is not None else "selftest"
    run_dir = repo_root / "scripts" / "captures" / f"coordinate-scan-plan-batch-currentpid-{run_pid}-{utc_stamp()}"
    summary_path = run_dir / "summary.json"
    markdown_path = run_dir / "summary.md"
    command_log_path = run_dir / "command-envelopes.json"

    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "mode": "riftreader-current-pid-coordinate-scan-plan-batch",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "blockers": [],
        "warnings": [],
        "errors": [],
        "repoRoot": str(repo_root),
        "processId": args.pid,
        "targetWindowHandle": args.hwnd,
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgLaunched": False,
            "debuggerAttached": False,
            "githubConnectorWrites": False,
            "providerWrites": False,
        },
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(summary_path),
            "summaryMarkdown": str(markdown_path),
            "commandEnvelopesJson": str(command_log_path),
        },
        "scan": {
            "topCount": args.top_count,
            "stride": args.stride,
            "tolerance": args.tolerance,
            "maxSecondsPerRange": args.max_seconds_per_range,
            "rangesCompleted": 0,
            "totalHits": 0,
        },
        "rangeResults": [],
        "next": {},
    }

    envelopes: list[dict[str, Any]] = []
    exit_code = 1
    try:
        if args.self_test:
            self_test = run_self_test(repo_root)
            summary["selfTest"] = self_test
            summary["status"] = self_test["status"]
            if self_test["status"] == "passed":
                summary["warnings"].append("self-test only; no child scan executed")
                exit_code = 0
            else:
                summary["errors"].extend(self_test["errors"])
                exit_code = 1
            return exit_code

        if args.pid is None or args.hwnd is None:
            raise RuntimeError("--pid and --hwnd are required unless --self-test is used")

        plan_path = Path(args.scan_plan).resolve() if args.scan_plan else latest_scan_plan(repo_root, args.pid)
        reference_file = Path(args.reference_file).resolve() if args.reference_file else None
        summary["scan"]["scanPlanJson"] = str(plan_path)
        summary["scan"]["referenceFile"] = str(reference_file) if reference_file else None
        ranges = load_plan(plan_path, args.top_count)
        timeout = max(30, args.max_seconds_per_range + args.reference_timeout_seconds + 30)

        for scan_range in ranges:
            command = build_scan_command(
                repo_root=repo_root,
                pid=args.pid,
                hwnd=args.hwnd,
                scan_range=scan_range,
                stride=args.stride,
                tolerance=args.tolerance,
                max_seconds=args.max_seconds_per_range,
                reference_file=reference_file,
                reference_timeout_seconds=args.reference_timeout_seconds,
            )
            envelope = run_command(command, repo_root, timeout_seconds=timeout)
            envelopes.append(
                {
                    **{k: v for k, v in envelope.items() if k not in {"stdout", "stderr"}},
                    "stdoutPreview": str(envelope.get("stdout") or "")[:2000],
                    "stderrPreview": str(envelope.get("stderr") or "")[:2000],
                }
            )
            child = result_from_child(scan_range, envelope)
            summary["rangeResults"].append(child)
            summary["scan"]["rangesCompleted"] = int(summary["scan"]["rangesCompleted"]) + 1
            hits = int(child.get("hitCount") or 0)
            summary["scan"]["totalHits"] = int(summary["scan"]["totalHits"]) + hits

            if envelope.get("timedOut"):
                summary["warnings"].append(f"range {scan_range.get('rank')} timed out")
            elif envelope.get("exitCode") not in (0, 2):
                summary["errors"].append(
                    {
                        "rangeRank": scan_range.get("rank"),
                        "exitCode": envelope.get("exitCode"),
                        "stderrPreview": str(envelope.get("stderr") or "")[:500],
                    }
                )
                break
            if hits and args.stop_on_hit:
                summary["warnings"].append("stop-on-hit requested; remaining ranges not scanned")
                break

        total_hits = int(summary["scan"]["totalHits"])
        if summary["errors"]:
            summary["status"] = "failed"
            summary["next"]["recommendedAction"] = "Inspect failed child scan envelopes before continuing."
            exit_code = 1
        elif total_hits:
            summary["status"] = "passed"
            summary["next"]["recommendedAction"] = "Rank candidates across fresh poses; keep movement/x64dbg blocked until candidates survive validation."
            exit_code = 0
        else:
            summary["status"] = "blocked"
            summary["blockers"].append("no_xyz_triplets_found_in_scan_plan_ranges")
            summary["next"]["recommendedAction"] = "Try alternate layouts/orderings or a wider scan plan before using x64dbg."
            exit_code = 2
        return exit_code
    except Exception as exc:
        summary["status"] = "failed"
        summary["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        exit_code = 1
        return exit_code
    finally:
        write_json(command_log_path, envelopes)
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
                        "totalHits": summary.get("scan", {}).get("totalHits"),
                        "summaryJson": str(summary_path),
                    },
                    indent=2,
                )
            )


if __name__ == "__main__":
    raise SystemExit(main())
