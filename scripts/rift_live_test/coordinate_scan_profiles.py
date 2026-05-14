from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ScanProfile:
    name: str
    max_seconds: int
    max_hits: int
    chunk_bytes: int
    scan_stride: int
    tolerance: float


PROFILES: dict[str, ScanProfile] = {
    "quick": ScanProfile("quick", max_seconds=20, max_hits=128, chunk_bytes=4 * 1024 * 1024, scan_stride=4, tolerance=0.25),
    "wide": ScanProfile("wide", max_seconds=75, max_hits=512, chunk_bytes=8 * 1024 * 1024, scan_stride=4, tolerance=0.25),
    "wide-stride1": ScanProfile("wide-stride1", max_seconds=75, max_hits=512, chunk_bytes=4 * 1024 * 1024, scan_stride=1, tolerance=0.25),
    "historical-neighborhood": ScanProfile(
        "historical-neighborhood",
        max_seconds=20,
        max_hits=128,
        chunk_bytes=2 * 1024 * 1024,
        scan_stride=4,
        tolerance=0.25,
    ),
}

DEFAULT_HISTORICAL_CENTERS = [
    ("0x268D5A80730", "pid2928-last-readback-reference-match"),
    ("0x268DF21ED30", "pid2928-best-focused-offset-copy-candidate"),
    ("0x268DF21ED20", "pid2928-broad-delta-offset-copy-candidate"),
    ("0x268DF200000", "pid2928-offset-copy-family-base"),
    ("0x1FF07570000", "pid60628-destination-copy-family"),
    ("0x1FF08502BC8", "pid60628-best-exact-threepose-candidate"),
    ("0x2400EA32120", "older-riftscan-first-proof-anchor"),
]


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def path_text(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def normalize_hwnd(value: str) -> str:
    text = str(value).strip()
    try:
        return f"0x{int(text, 0):X}"
    except ValueError:
        return text


def parse_center(value: str) -> tuple[int, str]:
    if "=" in value:
        label, address = value.split("=", 1)
    else:
        label, address = "manual-center", value
    return int(address, 0), label.strip() or "manual-center"


def format_hex(value: int) -> str:
    return f"0x{max(0, value):X}"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON file is not an object: {path}")
    return value


def run_command(args: list[str], cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    started = time.monotonic()
    started_at = utc_iso()
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
            "startedAtUtc": started_at,
            "completedAtUtc": utc_iso(),
            "durationSeconds": round(time.monotonic() - started, 3),
            "exitCode": proc.returncode,
            "stdoutPreview": proc.stdout[:4000],
            "stderrPreview": proc.stderr[:4000],
            "timedOut": False,
            "stdoutJson": parse_stdout_json(proc.stdout),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "args": args,
            "cwd": str(cwd),
            "startedAtUtc": started_at,
            "completedAtUtc": utc_iso(),
            "durationSeconds": round(time.monotonic() - started, 3),
            "exitCode": None,
            "stdoutPreview": (exc.stdout or "")[:4000],
            "stderrPreview": (exc.stderr or "")[:4000],
            "timedOut": True,
            "timeoutSeconds": timeout_seconds,
        }


def parse_stdout_json(text: str) -> Any | None:
    value = (text or "").strip()
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        starts = [idx for idx in (value.find("{"), value.find("[")) if idx >= 0]
        if not starts:
            return None
        try:
            parsed, _ = json.JSONDecoder().raw_decode(value[min(starts):])
            return parsed
        except json.JSONDecodeError:
            return None


def profile_commands(
    *,
    repo_root: Path,
    pid: int,
    hwnd: str,
    process_name: str,
    reference_file: Path,
    profiles: Sequence[str],
    centers: Sequence[tuple[int, str]],
    historical_radius_bytes: int,
) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    scan_script = repo_root / "scripts" / "scan_current_pid_coordinate_family.py"
    for name in profiles:
        profile = PROFILES[name]
        base_args = [
            sys.executable,
            str(scan_script),
            "--pid",
            str(pid),
            "--hwnd",
            hwnd,
            "--process-name",
            process_name,
            "--reference-file",
            str(reference_file),
            "--max-seconds",
            str(profile.max_seconds),
            "--max-hits",
            str(profile.max_hits),
            "--chunk-bytes",
            str(profile.chunk_bytes),
            "--scan-stride",
            str(profile.scan_stride),
            "--tolerance",
            str(profile.tolerance),
            "--json",
        ]
        if name == "historical-neighborhood":
            for address, label in centers:
                minimum = max(0, address - historical_radius_bytes)
                maximum = address + historical_radius_bytes
                commands.append(
                    {
                        "profile": name,
                        "label": label,
                        "centerAddress": format_hex(address),
                        "args": [
                            *base_args,
                            "--min-address",
                            format_hex(minimum),
                            "--max-address",
                            format_hex(maximum),
                        ],
                        "timeoutSeconds": profile.max_seconds + 60,
                    }
                )
        else:
            commands.append(
                {
                    "profile": name,
                    "label": name,
                    "args": base_args,
                    "timeoutSeconds": profile.max_seconds + 60,
                }
            )
    return commands


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Coordinate scan profile run",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Target: `{summary.get('processName')}` PID `{summary.get('processId')}`, HWND `{summary.get('targetWindowHandle')}`",
        f"- Reference file: `{summary.get('referenceFile')}`",
        f"- Movement sent: `{str(summary.get('safety', {}).get('movementSent')).lower()}`",
        f"- Input sent: `{str(summary.get('safety', {}).get('inputSent')).lower()}`",
        f"- No Cheat Engine: `{str(summary.get('safety', {}).get('noCheatEngine')).lower()}`",
        "",
        "## Profiles",
        "",
        "| Profile | Label | Exit | Status | Hits | Summary |",
        "|---|---|---:|---|---:|---|",
    ]
    for run in summary.get("profileRuns") or []:
        parsed = run.get("stdoutJson") if isinstance(run.get("stdoutJson"), dict) else {}
        lines.append(
            f"| `{run.get('profile')}` | `{run.get('label')}` | `{run.get('exitCode')}` | "
            f"`{parsed.get('status')}` | `{(parsed.get('scan') or {}).get('hitCount')}` | "
            f"`{(parsed.get('artifacts') or {}).get('summaryJson')}` |"
        )
    if summary.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in summary.get("blockers") or [])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{item}`" for item in summary.get("warnings") or [])
    lines.extend(["", "Movement remains blocked. This helper never sends input and never uses CE/x64dbg.", ""])
    return "\n".join(lines)


def final_status(summary: dict[str, Any]) -> tuple[str, int]:
    if summary.get("errors"):
        return "failed", 1
    if summary.get("blockers"):
        return "blocked", 2
    hits = [
        ((run.get("stdoutJson") or {}).get("scan") or {}).get("hitCount")
        for run in summary.get("profileRuns") or []
        if isinstance(run.get("stdoutJson"), dict)
    ]
    if any(isinstance(hit, int) and hit > 0 for hit in hits):
        return "passed", 0
    return "blocked", 2


def default_centers(extra_centers: Iterable[str]) -> list[tuple[int, str]]:
    centers = [(int(address, 0), label) for address, label in DEFAULT_HISTORICAL_CENTERS]
    centers.extend(parse_center(value) for value in extra_centers)
    dedup: dict[int, str] = {}
    for address, label in centers:
        dedup.setdefault(address, label)
    return [(address, label) for address, label in dedup.items()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run repeatable no-input coordinate family scan profiles.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--pid", type=int)
    parser.add_argument("--hwnd")
    parser.add_argument("--process-name", default="rift_x64")
    parser.add_argument("--reference-file", type=Path)
    parser.add_argument("--displaced-reference-file", type=Path)
    parser.add_argument("--require-displaced-pose", action="store_true")
    parser.add_argument("--profile", choices=sorted(PROFILES), action="append", default=[])
    parser.add_argument("--historical-center", action="append", default=[], help="Optional label=0xADDRESS center.")
    parser.add_argument("--historical-radius-bytes", type=lambda v: int(v, 0), default=16 * 1024 * 1024)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    run_dir = (args.output_root or repo_root / "scripts" / "captures" / f"coordinate-scan-profiles-{utc_stamp()}").resolve()
    summary_json = run_dir / "summary.json"
    summary_md = run_dir / "summary.md"
    profiles = args.profile or ["quick", "historical-neighborhood"]
    hwnd = normalize_hwnd(args.hwnd or "0x0")
    summary: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-coordinate-scan-profiles",
        "generatedAtUtc": utc_iso(),
        "status": "failed",
        "blockers": [],
        "warnings": [],
        "errors": [],
        "repoRoot": str(repo_root),
        "processName": args.process_name,
        "processId": args.pid,
        "targetWindowHandle": hwnd,
        "referenceFile": str(args.reference_file) if args.reference_file else None,
        "displacedReferenceFile": str(args.displaced_reference_file) if args.displaced_reference_file else None,
        "profiles": profiles,
        "profileRuns": [],
        "artifacts": {"summaryJson": str(summary_json), "summaryMarkdown": str(summary_md), "runDirectory": str(run_dir)},
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgAttached": False,
            "providerWrite": False,
            "githubConnectorWrites": False,
        },
    }
    try:
        if args.self_test:
            summary["status"] = "passed"
            summary["warnings"].append("self-test only; no live process scan executed")
            return_code = 0
            return return_code
        if args.pid is None:
            summary["blockers"].append("target-pid-required")
        if not args.hwnd:
            summary["blockers"].append("target-hwnd-required")
        if args.reference_file is None:
            summary["blockers"].append("reference-file-required")
        elif not args.reference_file.exists():
            summary["blockers"].append(f"reference-file-missing:{args.reference_file}")
        if args.require_displaced_pose and args.displaced_reference_file is None:
            summary["blockers"].append("manual-displaced-reference-required")
        if args.displaced_reference_file is not None and not args.displaced_reference_file.exists():
            summary["blockers"].append(f"displaced-reference-file-missing:{args.displaced_reference_file}")
        for profile in profiles:
            if profile not in PROFILES:
                summary["blockers"].append(f"unknown-profile:{profile}")
        if summary["blockers"]:
            summary["status"] = "blocked"
            return 2
        commands = profile_commands(
            repo_root=repo_root,
            pid=int(args.pid),
            hwnd=hwnd,
            process_name=args.process_name,
            reference_file=args.reference_file.resolve(),
            profiles=profiles,
            centers=default_centers(args.historical_center),
            historical_radius_bytes=args.historical_radius_bytes,
        )
        summary["plannedCommands"] = commands
        if args.dry_run:
            summary["status"] = "blocked"
            summary["warnings"].append("dry-run requested; no profile commands executed")
            return 2
        for command in commands:
            envelope = run_command(command["args"], repo_root, command["timeoutSeconds"])
            summary["profileRuns"].append({**command, **envelope})
        status, return_code = final_status(summary)
        summary["status"] = status
        if status == "blocked" and not summary["blockers"]:
            summary["blockers"].append("no-profile-found-current-coordinate-triplets")
        return return_code
    except Exception as exc:  # noqa: BLE001 - preserve durable blocker evidence.
        summary["status"] = "failed"
        summary["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        return 1
    finally:
        write_json(summary_json, summary)
        write_text_atomic(summary_md, build_markdown(summary))
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(json.dumps({"status": summary.get("status"), "summaryJson": str(summary_json)}, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
