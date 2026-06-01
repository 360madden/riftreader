#!/usr/bin/env python3
"""Run the RiftReader offline Ghidra static-evidence lane safely.

This helper owns the Windows footguns around Ghidra headless:
- batch wrappers mis-handle paths containing spaces/parentheses unless short
  paths are used;
- Ghidra project locations cannot include a path component beginning with ".";
- actual Ghidra runs should write only ignored local artifacts.

It never attaches to RIFT, reads target-process memory, sends input, writes
provider repos, mutates Git, or promotes current-truth/proof evidence.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, repo_rel, safety_flags, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, repo_rel, safety_flags, utc_iso


SCHEMA_VERSION = 1
TOOL_VERSION = "riftreader-ghidra-static-evidence-v0.1.0"
DEFAULT_EXTERNAL_TOOLS_ROOT = Path(r"C:\RIFT MODDING\Tools")
DEFAULT_BINARY_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe"),
    Path(r"C:\Program Files\Glyph\Games\RIFT\Live\rift_x64.exe"),
)
PROJECT_NAME = "riftreader-offline-static-analysis"
SCRIPT_NAME = "RiftReaderPointerEvidence.java"


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def first_existing_binary() -> Path | None:
    for path in DEFAULT_BINARY_CANDIDATES:
        if path.is_file():
            return path
    return None


def windows_short_path(path: Path) -> str:
    """Return an 8.3 path when available; fallback to the absolute path."""

    resolved = str(path.resolve())
    if sys.platform != "win32" or not path.exists():
        return resolved
    buffer = ctypes.create_unicode_buffer(4096)
    result = ctypes.windll.kernel32.GetShortPathNameW(resolved, buffer, len(buffer))  # type: ignore[attr-defined]
    return buffer.value if result else resolved


def short_repo_path(repo_root: Path, path: Path) -> str:
    repo_root = repo_root.resolve()
    path = path.resolve()
    try:
        relative = path.relative_to(repo_root)
    except ValueError:
        return windows_short_path(path)
    return str(Path(windows_short_path(repo_root)) / relative)


def run_child(command: list[str], *, cwd: Path, timeout_seconds: int, log_path: Path) -> dict[str, Any]:
    started = utc_iso()
    start = time.monotonic()
    timed_out = False
    exit_code = 1
    output = ""
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds,
            check=False,
        )
        exit_code = int(completed.returncode)
        output = completed.stdout or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        output = (exc.stdout or "") + "\nTIMEOUT\n"
    log_path.write_text(output, encoding="utf-8", errors="replace")
    return {
        "command": command,
        "cwd": str(cwd),
        "startedAtUtc": started,
        "endedAtUtc": utc_iso(),
        "durationSeconds": round(time.monotonic() - start, 3),
        "timeoutSeconds": timeout_seconds,
        "exitCode": exit_code,
        "ok": exit_code == 0 and not timed_out,
        "timedOut": timed_out,
        "log": str(log_path),
        "stdoutPreview": output[:4000],
    }


def build_plan(
    repo_root: Path,
    external_tools_root: Path,
    *,
    binary_path: Path | None,
    run_stamp: str,
    analysis_timeout_per_file: int,
    command_timeout_seconds: int,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    external_tools_root = external_tools_root.resolve()
    wrapper = external_tools_root / "ghidra-headless.bat"
    binary = (binary_path or first_existing_binary())
    artifact_root = repo_root / "scripts" / "captures" / f"ghidra-static-analysis-{run_stamp}"
    project_location = repo_root / "scripts" / "captures" / "ghidra-static-projects" / f"project-{run_stamp}"
    script_dir = repo_root / "tools" / "riftreader_workflow" / "ghidra_scripts"
    script_file = script_dir / SCRIPT_NAME
    evidence_json = artifact_root / "pointer-evidence.json"
    blockers: list[str] = []
    if not wrapper.is_file():
        blockers.append("ghidra-headless-wrapper-missing")
    if binary is None or not binary.is_file():
        blockers.append("offline-binary-missing")
    if not script_file.is_file():
        blockers.append("ghidra-pointer-evidence-script-missing")

    short_wrapper = windows_short_path(wrapper) if wrapper.exists() else str(wrapper)
    short_project = short_repo_path(repo_root, project_location)
    short_script_dir = short_repo_path(repo_root, script_dir)
    short_evidence_json = short_repo_path(repo_root, evidence_json)
    short_binary = windows_short_path(binary) if binary is not None and binary.exists() else "<offline-binary-path>"
    import_command = [
        short_wrapper,
        short_project,
        PROJECT_NAME,
        "-import",
        short_binary,
        "-analysisTimeoutPerFile",
        str(analysis_timeout_per_file),
    ]
    evidence_command = [
        short_wrapper,
        short_project,
        PROJECT_NAME,
        "-process",
        "rift_x64.exe",
        "-noanalysis",
        "-scriptPath",
        short_script_dir,
        "-postScript",
        SCRIPT_NAME,
        short_evidence_json,
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-ghidra-static-evidence-plan",
        "toolVersion": TOOL_VERSION,
        "generatedAtUtc": utc_iso(),
        "status": "blocked-safe" if blockers else "ready",
        "blockers": blockers,
        "repoRoot": str(repo_root),
        "externalToolsRoot": str(external_tools_root),
        "wrapper": str(wrapper),
        "binary": str(binary) if binary else None,
        "artifactRoot": repo_rel(repo_root, artifact_root),
        "projectLocation": repo_rel(repo_root, project_location),
        "projectName": PROJECT_NAME,
        "script": repo_rel(repo_root, script_file),
        "evidenceJson": repo_rel(repo_root, evidence_json),
        "analysisTimeoutPerFileSeconds": analysis_timeout_per_file,
        "commandTimeoutSeconds": command_timeout_seconds,
        "commands": {
            "import": import_command,
            "evidence": evidence_command,
        },
        "pathFixups": {
            "usesWindowsShortPaths": sys.platform == "win32",
            "projectAvoidsDotPathComponent": ".riftreader-local" not in str(project_location),
            "artifactRootIgnoredByGit": "scripts\\captures" in repo_rel(repo_root, artifact_root),
        },
        "safety": {
            **safety_flags(),
            "offlineOnly": True,
            "x64dbgAttach": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "proofPromotion": False,
        },
    }


def summarize_evidence(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "missing"}
    data = json.loads(path.read_text(encoding="utf-8"))
    root_refs = data.get("rootReferences") if isinstance(data.get("rootReferences"), list) else []
    offset_hits = data.get("ownerOffsetHits") if isinstance(data.get("ownerOffsetHits"), dict) else {}
    offsets: dict[str, Any] = {}
    for key, value in offset_hits.items():
        if key.startswith("_") or not isinstance(value, list):
            continue
        offsets[key] = {
            "hitCount": len(value),
            "writeLikeCount": sum(1 for item in value if isinstance(item, dict) and "write" in str(item.get("accessGuess", ""))),
            "firstHits": value[:5],
        }
    return {
        "status": "loaded",
        "programName": data.get("programName"),
        "imageBase": data.get("imageBase"),
        "rootAddress": data.get("rootAddress"),
        "rootReferenceCountCaptured": len(root_refs),
        "rootReferenceTypes": {
            item: sum(1 for ref in root_refs if isinstance(ref, dict) and ref.get("referenceType") == item)
            for item in sorted({str(ref.get("referenceType")) for ref in root_refs if isinstance(ref, dict)})
        },
        "instructionsScanned": offset_hits.get("_instructionsScanned"),
        "offsets": offsets,
    }


def build_markdown(summary: dict[str, Any]) -> str:
    evidence = summary.get("evidenceSummary") if isinstance(summary.get("evidenceSummary"), dict) else {}
    lines = [
        "# RiftReader Ghidra Static Evidence Run",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Generated UTC: `{summary.get('generatedAtUtc')}`",
        f"- Artifact root: `{summary.get('artifactRoot')}`",
        f"- Project location: `{summary.get('projectLocation')}`",
        f"- Evidence JSON: `{summary.get('evidenceJson')}`",
        "",
        "## Evidence summary",
        "",
        f"- Program: `{evidence.get('programName')}`",
        f"- Image base: `{evidence.get('imageBase')}`",
        f"- Root address: `{evidence.get('rootAddress')}`",
        f"- Root refs captured: `{evidence.get('rootReferenceCountCaptured')}`",
        f"- Instructions scanned: `{evidence.get('instructionsScanned')}`",
        "",
        "## Safety",
        "",
        "Offline Ghidra analysis only. No live input, target memory read/write, x64dbg, CE, provider writes, Git mutation, or proof/current-truth promotion.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def run_plan(repo_root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("blockers"):
        return {**plan, "kind": "riftreader-ghidra-static-evidence-run", "status": "blocked", "errors": []}
    artifact_root = repo_root / str(plan["artifactRoot"])
    project_location = repo_root / str(plan["projectLocation"])
    artifact_root.mkdir(parents=True, exist_ok=True)
    project_location.mkdir(parents=True, exist_ok=True)
    import_log = artifact_root / "analyzeHeadless.log"
    evidence_log = artifact_root / "pointer-evidence.log"
    evidence_json = repo_root / str(plan["evidenceJson"])
    import_result = run_child(
        plan["commands"]["import"],
        cwd=repo_root,
        timeout_seconds=int(plan["commandTimeoutSeconds"]),
        log_path=import_log,
    )
    warnings: list[str] = []
    if "Analysis timed out" in import_log.read_text(encoding="utf-8", errors="replace"):
        warnings.append("ghidra-analysis-timeout-project-saved")
    evidence_result = None
    if import_result["ok"]:
        evidence_result = run_child(
            plan["commands"]["evidence"],
            cwd=repo_root,
            timeout_seconds=max(600, int(plan["commandTimeoutSeconds"])),
            log_path=evidence_log,
        )
    status = "passed" if import_result["ok"] and evidence_result and evidence_result["ok"] else "failed"
    summary = {
        **plan,
        "kind": "riftreader-ghidra-static-evidence-run",
        "status": status,
        "generatedAtUtc": utc_iso(),
        "warnings": warnings,
        "errors": [],
        "commandsRun": {
            "import": import_result,
            "evidence": evidence_result,
        },
        "evidenceSummary": summarize_evidence(evidence_json),
    }
    summary_path = artifact_root / "summary.json"
    markdown_path = artifact_root / "summary.md"
    summary["summaryJson"] = repo_rel(repo_root, summary_path)
    summary["summaryMarkdown"] = repo_rel(repo_root, markdown_path)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(build_markdown(summary), encoding="utf-8")
    return summary


def build_self_test(repo_root: Path) -> dict[str, Any]:
    plan = build_plan(
        repo_root,
        DEFAULT_EXTERNAL_TOOLS_ROOT,
        binary_path=first_existing_binary(),
        run_stamp="selftest",
        analysis_timeout_per_file=1,
        command_timeout_seconds=1,
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-ghidra-static-evidence-self-test",
        "status": "passed",
        "ok": True,
        "checks": [
            {"name": "project-location-not-dot-prefixed", "pass": ".riftreader-local" not in str(plan.get("projectLocation"))},
            {"name": "uses-pointer-evidence-script", "pass": SCRIPT_NAME in plan["commands"]["evidence"]},
            {"name": "offline-safety", "pass": bool(plan["safety"]["offlineOnly"]) and not bool(plan["safety"]["x64dbgAttach"])},
        ],
        "planStatus": plan.get("status"),
        "safety": plan.get("safety"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--external-tools-root", type=Path, default=DEFAULT_EXTERNAL_TOOLS_ROOT)
    parser.add_argument("--binary-path", type=Path)
    parser.add_argument("--analysis-timeout-per-file", type=int, default=300)
    parser.add_argument("--command-timeout-seconds", type=int, default=900)
    parser.add_argument("--plan", action="store_true", help="Print a plan only; do not run Ghidra.")
    parser.add_argument("--run", action="store_true", help="Run offline Ghidra import and pointer evidence extraction.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root(Path.cwd())
    if args.self_test:
        payload = build_self_test(repo_root)
    else:
        plan = build_plan(
            repo_root,
            args.external_tools_root,
            binary_path=args.binary_path,
            run_stamp=stamp(),
            analysis_timeout_per_file=args.analysis_timeout_per_file,
            command_timeout_seconds=args.command_timeout_seconds,
        )
        payload = run_plan(repo_root, plan) if args.run else plan

    if args.json or args.plan or args.run or args.self_test:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(build_markdown(payload), end="")
    if payload.get("status") in {"blocked", "blocked-safe"}:
        return 2
    return 0 if payload.get("status") in {"ready", "passed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
