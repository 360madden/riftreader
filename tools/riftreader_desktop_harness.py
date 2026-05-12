#!/usr/bin/env python3
# Version: riftreader-desktop-harness-v0.1.0
# Total-Character-Count: 14944
# Purpose: Provide a local Desktop ChatGPT-centered RiftReader harness that reuses the Drive inbox helper for status, prompt, and package artifacts without live RIFT operations.
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

VERSION = "riftreader-desktop-harness-v0.1.0"
PURPOSE = "Desktop ChatGPT-centered RiftReader harness for Drive-backed status, prompt, and package artifacts."
DEFAULT_REPO_ROOT = r"C:\RIFT MODDING\RiftReader"
DEFAULT_DRIVE_ROOT = r"G:\My Drive\RiftReader"
REMOTE_NAME = "origin"
REMOTE_REF = "refs/heads/main"

REPO_DOC_ALLOWLIST = (
    "docs/RIFTREADER_DRIVE_INBOX_WORKFLOW.md",
    "docs/RIFTREADER_DRIVE_INBOX_CONTRACT.json",
    "docs/RIFTREADER_DESKTOP_CHATGPT_HARNESS.md",
    "docs/RIFTREADER_DESKTOP_HARNESS_CONTRACT.json",
)

DRIVE_ARTIFACT_RELATIVE_PATHS = (
    "status/RIFTREADER_DRIVE_INBOX_STATUS.json",
    "status/RIFTREADER_DRIVE_INBOX_STATUS.md",
    "status/RIFTREADER_CURRENT_STATUS.json",
    "status/RIFTREADER_CURRENT_STATUS.md",
    "handoffs/current/RIFTREADER_CURRENT_HANDOFF.json",
    "handoffs/current/RIFTREADER_CURRENT_HANDOFF.md",
)


def utc_now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def iso_utc() -> str:
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: Dict[str, Any]) -> None:
    write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_checked(args: List[str], cwd: Optional[Path] = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=str(cwd) if cwd is not None else None,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "command failed: {cmd}\nexit={code}\nstdout={stdout}\nstderr={stderr}".format(
                cmd=" ".join(args),
                code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        )
    return completed


def git_stdout(repo_root: Path, args: List[str]) -> str:
    return run_checked(["git", *args], cwd=repo_root).stdout.strip()


def git_lines(repo_root: Path, args: List[str]) -> List[str]:
    text = git_stdout(repo_root, args)
    if not text:
        return []
    return text.splitlines()


def porcelain_path(line: str) -> str:
    if len(line) < 4:
        return line
    path = line[3:]
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path.replace("\\", "/")


def is_known_proof_residue(line: str) -> bool:
    code = line[:2]
    path = porcelain_path(line)
    if code == " M" and path == "docs/recovery/current-proof-anchor-readback.json":
        return True
    if code == "??" and path.startswith("docs/recovery/historical/current-proof-anchor-readback-") and path.endswith(".json"):
        return True
    return False


def repo_status(repo_root: Path) -> Dict[str, Any]:
    branch = git_stdout(repo_root, ["branch", "--show-current"])
    head = git_stdout(repo_root, ["rev-parse", "HEAD"])
    head_short = git_stdout(repo_root, ["rev-parse", "--short", "HEAD"])
    remote_line = git_stdout(repo_root, ["ls-remote", REMOTE_NAME, REMOTE_REF])
    remote_sha = remote_line.split()[0] if remote_line else ""
    status_lines = git_lines(repo_root, ["status", "--porcelain=v1", "--untracked-files=all"])
    proof_residue = [line for line in status_lines if is_known_proof_residue(line)]
    unexpected = [line for line in status_lines if not is_known_proof_residue(line)]
    if not status_lines:
        classification = "clean"
    elif unexpected:
        classification = "dirty-unexpected"
    else:
        classification = "dirty-known-proof-residue-only"
    return {
        "root": str(repo_root),
        "branch": branch,
        "head": head,
        "head_short": head_short,
        "remote": REMOTE_NAME,
        "remote_ref": REMOTE_REF,
        "remote_sha": remote_sha,
        "local_equals_remote": head == remote_sha,
        "status_lines": status_lines,
        "known_proof_residue": proof_residue,
        "unexpected_status_lines": unexpected,
        "classification": classification,
    }


def run_drive_inbox_status(repo_root: Path, drive_root: Path, write_status: bool) -> Dict[str, Any]:
    helper = repo_root / "tools" / "riftreader_drive_inbox.py"
    if not helper.is_file():
        return {"ok": False, "code": "MISSING_DRIVE_INBOX_HELPER", "path": str(helper)}
    args = [sys.executable, str(helper), "status", "--drive-root", str(drive_root), "--json"]
    if write_status:
        args.append("--write-status")
    completed = run_checked(args, cwd=repo_root)
    if completed.stderr.strip():
        raise RuntimeError("Drive inbox helper produced stderr in JSON mode: " + completed.stderr)
    return json.loads(completed.stdout)


def markdown_status(data: Dict[str, Any]) -> str:
    repo = data.get("repo", {})
    drive = data.get("drive_inbox", {})
    lines = [
        "# RiftReader Desktop Harness Status",
        "",
        f"- Version: `{VERSION}`",
        f"- Created UTC: `{data.get('created_utc')}`",
        f"- OK: `{data.get('ok')}`",
        f"- Code: `{data.get('code')}`",
        f"- Current lane: `drive-integration`",
        f"- Repo root: `{repo.get('root')}`",
        f"- Branch: `{repo.get('branch')}`",
        f"- HEAD: `{repo.get('head')}`",
        f"- Origin/main: `{repo.get('remote_sha')}`",
        f"- Repo classification: `{repo.get('classification')}`",
        f"- Drive root: `{data.get('drive_root')}`",
        f"- Drive inbox status: `{drive.get('code')}`",
        "",
        "## Known proof-anchor residue",
        "",
    ]
    residue = repo.get("known_proof_residue", [])
    if residue:
        lines.extend(f"- `{line}`" for line in residue)
    else:
        lines.append("None.")
    lines.extend([
        "",
        "## Lane rule",
        "",
        "Drive integration only. Do not run ProofOnly, Stage 1 promotion, movement, visual gates, or live RIFT input from this harness.",
        "",
    ])
    return "\n".join(lines)


def build_status(args: argparse.Namespace) -> Dict[str, Any]:
    repo_root = Path(args.repo_root)
    drive_root = Path(args.drive_root)
    status = {
        "ok": True,
        "code": "STATUS_COMPLETE",
        "version": VERSION,
        "purpose": PURPOSE,
        "created_utc": iso_utc(),
        "current_lane": "drive-integration",
        "repo_root": str(repo_root),
        "drive_root": str(drive_root),
        "live_rift_operations": "disabled",
    }
    status["repo"] = repo_status(repo_root)
    status["drive_inbox"] = run_drive_inbox_status(repo_root, drive_root, bool(args.write_status))
    if not status["repo"]["local_equals_remote"]:
        status["ok"] = False
        status["code"] = "LOCAL_REMOTE_MISMATCH"
    elif status["repo"]["unexpected_status_lines"]:
        status["ok"] = False
        status["code"] = "UNEXPECTED_REPO_DIRTY_FILES"
    elif not status["drive_inbox"].get("ok"):
        status["ok"] = False
        status["code"] = "DRIVE_INBOX_STATUS_NOT_OK"
    if args.write_status:
        status_json = drive_root / "status" / "RIFTREADER_DESKTOP_HARNESS_STATUS.json"
        status_md = drive_root / "status" / "RIFTREADER_DESKTOP_HARNESS_STATUS.md"
        write_json(status_json, status)
        write_text(status_md, markdown_status(status))
        status["status_json_path"] = str(status_json)
        status["status_md_path"] = str(status_md)
    return status


def build_prompt_text(status: Dict[str, Any], task: str) -> str:
    repo = status.get("repo", {})
    drive = status.get("drive_inbox", {})
    return "\n".join([
        "# RiftReader Desktop ChatGPT Prompt",
        "",
        "Use this prompt in ChatGPT Desktop when continuing RiftReader Drive integration.",
        "",
        "## Current lane",
        "",
        "Drive integration only.",
        "",
        "## Verified state",
        "",
        f"- Repo root: `{repo.get('root')}`",
        f"- Branch: `{repo.get('branch')}`",
        f"- HEAD: `{repo.get('head')}`",
        f"- Origin/main: `{repo.get('remote_sha')}`",
        f"- Repo classification: `{repo.get('classification')}`",
        f"- Drive root: `{status.get('drive_root')}`",
        f"- Drive inbox status: `{drive.get('code')}`",
        "",
        "## Known exclusions",
        "",
        "The repo may contain stale proof-anchor residue. Do not stage, reset, delete, or commit it while the Drive integration lane is selected.",
        "",
        "## Task",
        "",
        task,
        "",
        "## Hard rules",
        "",
        "- Do not run ProofOnly or Stage 1 promotion.",
        "- Do not send movement or live input.",
        "- Do not use stale PID/HWND values.",
        "- Use explicit git allowlists only.",
        "- Keep Drive as artifact transport/archive/status, not source of truth.",
        "",
    ])


def cmd_status(args: argparse.Namespace) -> Dict[str, Any]:
    return build_status(args)


def cmd_prompt(args: argparse.Namespace) -> Dict[str, Any]:
    status = build_status(args)
    task = args.task or "Continue RiftReader Drive integration and propose the next minimal allowlisted repo patch."
    prompt_text = build_prompt_text(status, task)
    drive_root = Path(args.drive_root)
    prompt_path = drive_root / "inbox" / "prompts" / f"{stamp()}_riftreader_desktop_chatgpt_prompt.md"
    write_text(prompt_path, prompt_text)
    result = {
        "ok": bool(status.get("ok")),
        "code": "PROMPT_WRITTEN" if status.get("ok") else "PROMPT_WRITTEN_WITH_STATUS_WARNINGS",
        "version": VERSION,
        "created_utc": iso_utc(),
        "prompt_path": str(prompt_path),
        "status": status,
    }
    if args.write_status:
        summary_path = drive_root / "status" / f"{stamp()}_RIFTREADER_DESKTOP_PROMPT_SUMMARY.json"
        write_json(summary_path, result)
        result["summary_json_path"] = str(summary_path)
    return result


def zip_add_if_exists(zf: zipfile.ZipFile, source: Path, arcname: str) -> bool:
    if source.is_file():
        zf.write(source, arcname)
        return True
    return False


def cmd_package(args: argparse.Namespace) -> Dict[str, Any]:
    status = build_status(args)
    repo_root = Path(args.repo_root)
    drive_root = Path(args.drive_root)
    package_dir = drive_root / "inbox" / "packages"
    manifest_dir = drive_root / "inbox" / "manifests"
    package_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = package_dir / f"{stamp()}_riftreader_desktop_harness_status_package.zip"
    included: List[str] = []
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        status_text = json.dumps(status, indent=2, sort_keys=True) + "\n"
        zf.writestr("status/riftreader_desktop_harness_status.json", status_text)
        included.append("status/riftreader_desktop_harness_status.json")
        zf.writestr("status/riftreader_desktop_harness_status.md", markdown_status(status))
        included.append("status/riftreader_desktop_harness_status.md")
        for rel in REPO_DOC_ALLOWLIST:
            if zip_add_if_exists(zf, repo_root / rel, f"repo/{rel}"):
                included.append(f"repo/{rel}")
        for rel in DRIVE_ARTIFACT_RELATIVE_PATHS:
            if zip_add_if_exists(zf, drive_root / rel, f"drive/{rel}"):
                included.append(f"drive/{rel}")
    manifest = {
        "ok": bool(status.get("ok")),
        "code": "PACKAGE_WRITTEN" if status.get("ok") else "PACKAGE_WRITTEN_WITH_STATUS_WARNINGS",
        "version": VERSION,
        "created_utc": iso_utc(),
        "package_path": str(zip_path),
        "package_sha256": sha256_file(zip_path),
        "included": included,
        "status": status,
    }
    manifest_path = manifest_dir / f"{zip_path.stem}.manifest.json"
    write_json(manifest_path, manifest)
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def emit(data: Dict[str, Any], json_mode: bool) -> None:
    if json_mode:
        sys.stdout.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
        return
    print(f"RiftReader Desktop Harness {VERSION}")
    print(f"OK   : {data.get('ok')}")
    print(f"Code : {data.get('code')}")
    for key in ("status_json_path", "status_md_path", "prompt_path", "package_path", "manifest_path"):
        if data.get(key):
            print(f"{key}: {data.get(key)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=PURPOSE)
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "prompt", "package"):
        p = sub.add_parser(name)
        p.add_argument("--repo-root", default=DEFAULT_REPO_ROOT)
        p.add_argument("--drive-root", default=DEFAULT_DRIVE_ROOT)
        p.add_argument("--json", action="store_true")
        p.add_argument("--write-status", action="store_true")
        if name == "prompt":
            p.add_argument("--task", default="")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    json_mode = bool(getattr(args, "json", False))
    try:
        if args.command == "status":
            data = cmd_status(args)
        elif args.command == "prompt":
            data = cmd_prompt(args)
        elif args.command == "package":
            data = cmd_package(args)
        else:
            data = {"ok": False, "code": "UNKNOWN_COMMAND", "command": args.command}
        emit(data, json_mode)
        return 0 if data.get("ok") else 1
    except Exception as exc:
        data = {
            "ok": False,
            "code": "UNHANDLED_EXCEPTION",
            "version": VERSION,
            "created_utc": iso_utc(),
            "error": str(exc),
            "exception_type": type(exc).__name__,
        }
        emit(data, json_mode)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
