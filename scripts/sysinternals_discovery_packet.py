#!/usr/bin/env python3
"""Collect read-only Sysinternals evidence for RiftReader discovery.

This helper intentionally stays in the no-debug/no-input lane:
it runs read-only Sysinternals CLI tools, stores raw stdout/stderr under a
RiftReader-owned capture directory, and emits a compact JSON/Markdown packet.
It does not attach a debugger, close handles, dump memory, suspend processes,
send input, write target memory, promote proof, or mutate git state.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_TOOL_DIR = Path(r"C:\RIFT MODDING\Tools\SysinternalsSuite")
DEFAULT_CAPTURE_ROOT = Path(__file__).resolve().parent / "captures"
HEX_RE = re.compile(r"0x[0-9a-fA-F]+")


@dataclass(frozen=True)
class ToolSpec:
    key: str
    filename: str
    default_use: str
    gated: bool = False


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec("handle64", "handle64.exe", "read-only handle/debug-object evidence"),
    ToolSpec("listdlls64", "Listdlls64.exe", "read-only module inventory"),
    ToolSpec("vmmap64", "vmmap64.exe", "optional memory-map export", gated=True),
    ToolSpec("sigcheck64", "sigcheck64.exe", "read-only file metadata"),
    ToolSpec("procexp64", "procexp64.exe", "manual visual aid", gated=True),
    ToolSpec("procmon64", "Procmon64.exe", "system-wide capture", gated=True),
    ToolSpec("procdump64", "procdump64.exe", "dump creation", gated=True),
    ToolSpec("pslist64", "pslist64.exe", "read-only process listing"),
    ToolSpec("pssuspend64", "pssuspend64.exe", "process suspension", gated=True),
    ToolSpec("rammap64", "RAMMap64.exe", "manual/system-wide memory tool", gated=True),
)


def utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_root_from_file() -> Path:
    return Path(__file__).resolve().parents[1]


def safe_read_text(path: Path, limit: int = 120_000) -> str:
    data = path.read_text(encoding="utf-8", errors="replace")
    if len(data) > limit:
        return data[:limit] + "\n...[truncated]..."
    return data


def file_manifest(tool_dir: Path) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "toolDirectory": str(tool_dir),
        "tools": {},
    }
    for spec in TOOLS:
        path = tool_dir / spec.filename
        entry: dict[str, Any] = {
            "key": spec.key,
            "filename": spec.filename,
            "path": str(path),
            "exists": path.exists(),
            "defaultUse": spec.default_use,
            "gated": spec.gated,
        }
        if path.exists():
            st = path.stat()
            entry.update(
                {
                    "sizeBytes": st.st_size,
                    "mtimeUtc": datetime.fromtimestamp(st.st_mtime, timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
            )
        manifest["tools"][spec.key] = entry
    return manifest


def command_envelope(
    *,
    label: str,
    args: list[str],
    cwd: Path,
    timeout_seconds: int,
    raw_dir: Path,
) -> dict[str, Any]:
    started = utc_now_iso()
    stdout_path = raw_dir / f"{label}.stdout.txt"
    stderr_path = raw_dir / f"{label}.stderr.txt"
    env: dict[str, Any] = {
        "label": label,
        "args": args,
        "cwd": str(cwd),
        "startedAtUtc": started,
        "timeoutSeconds": timeout_seconds,
        "stdoutPath": str(stdout_path),
        "stderrPath": str(stderr_path),
    }
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
        )
        stdout_path.write_text(completed.stdout or "", encoding="utf-8")
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")
        env.update(
            {
                "exitCode": completed.returncode,
                "ok": completed.returncode == 0,
                "timedOut": False,
                "endedAtUtc": utc_now_iso(),
                "stdoutPreview": (completed.stdout or "")[:2000],
                "stderrPreview": (completed.stderr or "")[:2000],
            }
        )
    except subprocess.TimeoutExpired as exc:
        stdout_path.write_text(exc.stdout or "", encoding="utf-8", errors="replace")
        stderr_path.write_text(exc.stderr or "", encoding="utf-8", errors="replace")
        env.update(
            {
                "exitCode": None,
                "ok": False,
                "timedOut": True,
                "endedAtUtc": utc_now_iso(),
                "stdoutPreview": (exc.stdout or "")[:2000],
                "stderrPreview": (exc.stderr or "")[:2000],
            }
        )
    except Exception as exc:  # pragma: no cover - defensive envelope
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(f"{type(exc).__name__}: {exc}", encoding="utf-8")
        env.update(
            {
                "exitCode": None,
                "ok": False,
                "timedOut": False,
                "endedAtUtc": utc_now_iso(),
                "error": {"type": type(exc).__name__, "message": str(exc)},
                "stdoutPreview": "",
                "stderrPreview": f"{type(exc).__name__}: {exc}",
            }
        )
    return env


def parse_listdlls_output(text: str) -> dict[str, Any]:
    modules: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        hexes = HEX_RE.findall(stripped)
        if not hexes:
            continue
        lower = stripped.lower()
        if ".dll" not in lower and ".exe" not in lower:
            continue
        parts = stripped.split()
        path_part = next((p for p in parts if ".dll" in p.lower() or ".exe" in p.lower()), parts[-1])
        modules.append(
            {
                "line": stripped,
                "baseAddress": hexes[0],
                "pathOrName": path_part,
                "isRiftExe": "rift_x64.exe" in lower,
                "isImage": True,
            }
        )
    rift_modules = [m for m in modules if m["isRiftExe"]]
    return {
        "moduleCount": len(modules),
        "riftModuleCount": len(rift_modules),
        "riftModules": rift_modules[:8],
        "sampleModules": modules[:20],
    }


def parse_handle_output(text: str, target_pid: int | None = None) -> dict[str, Any]:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    interesting: list[str] = []
    type_counts: dict[str, int] = {}
    for line in lines:
        lower = line.lower()
        if any(token in lower for token in ("debug", "rift", "x64dbg", "process", "thread")):
            interesting.append(line)
        match = re.search(r"\b([A-Za-z]+)\s+[^:]*:", line)
        if match:
            t = match.group(1)
            type_counts[t] = type_counts.get(t, 0) + 1
    debug_lines = [line for line in interesting if "debug" in line.lower()]
    process_lines = [line for line in interesting if "process" in line.lower()]
    return {
        "lineCount": len(lines),
        "targetPid": target_pid,
        "typeCounts": dict(sorted(type_counts.items())),
        "debugLineCount": len(debug_lines),
        "processLineCount": len(process_lines),
        "interestingLines": interesting[:100],
        "debugLines": debug_lines[:100],
        "processLines": process_lines[:100],
    }


def compare_expected_module_base(parsed_listdlls: dict[str, Any], expected_module_base: str | None) -> dict[str, Any]:
    if not expected_module_base:
        return {"status": "not-checked", "reason": "expected-module-base-not-provided"}
    try:
        expected = int(expected_module_base, 16)
    except ValueError:
        return {"status": "invalid-expected-module-base", "expectedModuleBase": expected_module_base}
    observed = []
    for module in parsed_listdlls.get("riftModules", []):
        base = module.get("baseAddress")
        if not base:
            continue
        try:
            value = int(str(base), 16)
        except ValueError:
            continue
        observed.append({"baseAddress": base, "value": value})
    exact = [item for item in observed if item["value"] == expected]
    low32 = [item for item in observed if (item["value"] & 0xFFFFFFFF) == (expected & 0xFFFFFFFF)]
    if exact:
        status = "exact-match"
    elif low32:
        status = "low32-match-listdlls-address-truncated"
    elif observed:
        status = "mismatch"
    else:
        status = "no-rift-module-observed"
    return {
        "status": status,
        "expectedModuleBase": expected_module_base,
        "expectedLow32Hex": f"0x{expected & 0xFFFFFFFF:X}",
        "observedRiftBases": [item["baseAddress"] for item in observed],
    }


def build_markdown(summary: dict[str, Any]) -> str:
    artifacts = summary["artifacts"]
    tool_manifest = summary["toolManifest"]
    sys_evidence = summary["sysinternalsEvidence"]
    safety = summary["safety"]
    lines = [
        "# Sysinternals Discovery Packet",
        "",
        f"- Generated: `{summary['generatedAtUtc']}`",
        f"- Status: `{summary['status']}`",
        f"- Verdict: `{summary['verdict']}`",
        f"- Target PID: `{summary['target'].get('pid')}`",
        "",
        "## Tools",
        "",
        "| Tool | Exists | Path |",
        "|---|---:|---|",
    ]
    for key, entry in tool_manifest["tools"].items():
        lines.append(f"| `{key}` | `{entry['exists']}` | `{entry['path']}` |")
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- ListDLLs status: `{sys_evidence.get('listdlls', {}).get('status')}`",
            f"- Parsed module count: `{sys_evidence.get('listdlls', {}).get('parsed', {}).get('moduleCount')}`",
            f"- RIFT module count: `{sys_evidence.get('listdlls', {}).get('parsed', {}).get('riftModuleCount')}`",
            f"- Handle status: `{sys_evidence.get('handle', {}).get('status')}`",
            f"- Debug line count: `{sys_evidence.get('handle', {}).get('parsed', {}).get('debugLineCount')}`",
            f"- VMMap status: `{sys_evidence.get('vmmap', {}).get('status')}`",
            "",
            "## Safety",
            "",
            "| Field | Value |",
            "|---|---:|",
        ]
    )
    for key, value in safety.items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "## Blockers",
            "",
            *(f"- `{b}`" for b in summary.get("blockers", [])),
            "",
            "## Artifacts",
            "",
            f"- Summary JSON: `{artifacts['summaryJson']}`",
            f"- Raw directory: `{artifacts['rawDirectory']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def run_packet(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    repo_root = args.repo_root.resolve()
    tool_dir = args.tool_dir.resolve()
    output_root = args.output_root.resolve()
    run_dir = output_root / f"sysinternals-discovery-packet-{utc_now_compact()}"
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    tool_manifest = file_manifest(tool_dir)
    blockers: list[str] = []
    warnings: list[str] = []
    commands: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {}

    required = ("handle64", "listdlls64", "sigcheck64")
    for key in required:
        if not tool_manifest["tools"][key]["exists"]:
            blockers.append(f"sysinternals-tool-missing:{key}")

    if not blockers:
        listdlls = tool_manifest["tools"]["listdlls64"]["path"]
        listdlls_cmd = [listdlls, "-accepteula", "-nobanner", str(args.pid)]
        env = command_envelope(
            label="listdlls64",
            args=listdlls_cmd,
            cwd=repo_root,
            timeout_seconds=args.timeout_seconds,
            raw_dir=raw_dir,
        )
        commands.append(env)
        parsed = parse_listdlls_output(safe_read_text(Path(env["stdoutPath"])))
        module_base_check = compare_expected_module_base(parsed, args.expected_module_base)
        if module_base_check["status"] == "low32-match-listdlls-address-truncated":
            warnings.append("listdlls-rift-module-base-low32-match-address-truncated")
        elif module_base_check["status"] not in ("exact-match", "not-checked"):
            warnings.append(f"listdlls-rift-module-base-{module_base_check['status']}")
        if not env["ok"]:
            blockers.append("listdlls64-failed-or-blocked")
        evidence["listdlls"] = {
            "status": "passed" if env["ok"] else "blocked",
            "commandLabel": env["label"],
            "parsed": parsed,
            "moduleBaseCheck": module_base_check,
        }

        handle = tool_manifest["tools"]["handle64"]["path"]
        handle_cmd = [handle, "-accepteula", "-nobanner", "-a", "-p", str(args.pid)]
        env = command_envelope(
            label="handle64",
            args=handle_cmd,
            cwd=repo_root,
            timeout_seconds=args.timeout_seconds,
            raw_dir=raw_dir,
        )
        commands.append(env)
        parsed = parse_handle_output(safe_read_text(Path(env["stdoutPath"])), args.pid)
        if not env["ok"]:
            blockers.append("handle64-failed-or-blocked")
        evidence["handle"] = {
            "status": "passed" if env["ok"] else "blocked",
            "commandLabel": env["label"],
            "parsed": parsed,
        }

        sigcheck = tool_manifest["tools"]["sigcheck64"]["path"]
        sigcheck_cmd = [sigcheck, "-accepteula", "-nobanner", listdlls]
        env = command_envelope(
            label="sigcheck64-listdlls64",
            args=sigcheck_cmd,
            cwd=repo_root,
            timeout_seconds=args.timeout_seconds,
            raw_dir=raw_dir,
        )
        commands.append(env)
        if not env["ok"]:
            warnings.append("sigcheck64-file-metadata-failed")
        evidence["sigcheck"] = {
            "status": "passed" if env["ok"] else "warning",
            "commandLabel": env["label"],
        }

    vmmap_exists = tool_manifest["tools"]["vmmap64"]["exists"]
    if args.attempt_vmmap and vmmap_exists and not blockers:
        # VMMap CLI behavior is more interactive/version-sensitive; keep it opt-in.
        vmmap = tool_manifest["tools"]["vmmap64"]["path"]
        out_file = raw_dir / f"vmmap-{args.pid}.mmp"
        vmmap_cmd = [vmmap, "-accepteula", "-o", str(out_file), str(args.pid)]
        env = command_envelope(
            label="vmmap64",
            args=vmmap_cmd,
            cwd=repo_root,
            timeout_seconds=args.timeout_seconds,
            raw_dir=raw_dir,
        )
        commands.append(env)
        evidence["vmmap"] = {
            "status": "passed" if env["ok"] else "blocked",
            "commandLabel": env["label"],
            "outputFile": str(out_file),
        }
        if not env["ok"]:
            blockers.append("vmmap64-export-failed-or-interactive")
    else:
        evidence["vmmap"] = {
            "status": "skipped",
            "reason": "vmmap-export-is-opt-in-to-avoid-interactive-gui-or-invasive-behavior",
            "toolExists": vmmap_exists,
        }

    status = "passed" if not blockers else "blocked"
    verdict = (
        "sysinternals-readonly-evidence-collected"
        if status == "passed"
        else "sysinternals-readonly-evidence-blocked"
    )
    summary: dict[str, Any] = {
        "schemaVersion": 1,
        "mode": "sysinternals-discovery-packet",
        "generatedAtUtc": utc_now_iso(),
        "status": status,
        "verdict": verdict,
        "repoRoot": str(repo_root),
        "target": {
            "pid": args.pid,
            "hwnd": args.hwnd,
            "expectedStartTimeUtc": args.expected_start_time_utc,
            "expectedModuleBase": args.expected_module_base,
        },
        "toolManifest": tool_manifest,
        "sysinternalsEvidence": evidence,
        "commands": commands,
        "blockers": blockers,
        "warnings": warnings,
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgAttach": False,
            "debuggerAttached": False,
            "debugActiveProcessStopCalled": False,
            "handleClosed": False,
            "processSuspended": False,
            "dumpCreated": False,
            "procmonCaptureStarted": False,
            "targetMemoryBytesWritten": False,
            "providerWrites": False,
            "gitMutation": False,
            "proofPromotion": False,
            "actorChainPromotion": False,
        },
        "next": {
            "recommendedAction": "Cross-check module RVA hints against ListDLLs module inventory and root-signature sweep outputs.",
            "requiresApprovalBefore": [
                "vmmap interactive capture",
                "procdump dump creation",
                "pssuspend process mutation",
                "procmon system-wide capture",
                "x64dbg/debugger attach",
                "Cheat Engine",
                "live input or movement",
                "proof or actor-chain promotion",
            ],
        },
        "artifacts": {
            "runDirectory": str(run_dir),
            "rawDirectory": str(raw_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_dir / "summary.md").write_text(build_markdown(summary), encoding="utf-8")
    return (0 if status == "passed" else 2), summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect read-only Sysinternals discovery evidence.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_file())
    parser.add_argument("--tool-dir", type=Path, default=DEFAULT_TOOL_DIR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_CAPTURE_ROOT)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--hwnd", default=None)
    parser.add_argument("--expected-start-time-utc", default=None)
    parser.add_argument("--expected-module-base", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--attempt-vmmap", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    code, summary = run_packet(args)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"status={summary['status']}")
        print(f"summaryJson={summary['artifacts']['summaryJson']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
