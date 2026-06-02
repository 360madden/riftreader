from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from .workflow_common import base_safety, repo_root, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution
    from workflow_common import base_safety, repo_root, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
KIND = "riftreader-glyph-forensics-inventory"
DEFAULT_TEXT_PREVIEW_BYTES = 4096
DEFAULT_MAX_FILES_PER_ROOT = 500
DEFAULT_MAX_STRING_HITS = 250
SKIP_DIRECTORY_NAMES = {
    "$recycle.bin",
    ".git",
    "cache",
    "download",
    "downloads",
    "games",
    "logs-archived",
    "patchdata",
    "temp",
    "tmp",
}

SENSITIVE_KEY_RE = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|session|cookie|auth|authorization|ticket|bearer|oauth|apikey|api_key|email|username|account)"
)
ASSIGNMENT_RE = re.compile(
    r"(?i)(?P<key>[A-Za-z0-9_.-]*(?:password|passwd|pwd|secret|token|session|cookie|auth|authorization|ticket|bearer|oauth|apikey|api_key|email|username|account)[A-Za-z0-9_.-]*)"
    r"(?P<sep>\s*[:=]\s*)"
    r"(?P<value>\"[^\"]*\"|'[^']*'|[^,\s;}\]]+)"
)
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9._~+/=-]{32,}\b")
URL_RE = re.compile(r"(?i)\bhttps?://[^\s\"'<>]+")
HOST_RE = re.compile(r"(?i)\b(?:[a-z0-9-]+\.)+(?:com|net|org|io|gg|tv|cloud|cdn|games|trionworlds)\b")
REGISTRY_RE = re.compile(r"(?i)\b(?:HKCU|HKLM|HKEY_CURRENT_USER|HKEY_LOCAL_MACHINE)\\[^\s\"']+")

TEXT_EXTENSIONS = {
    ".cfg",
    ".conf",
    ".config",
    ".ini",
    ".json",
    ".log",
    ".manifest",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

INTERESTING_EXTENSIONS = TEXT_EXTENSIONS | {
    ".dat",
    ".dll",
    ".exe",
    ".pak",
    ".patch",
    ".version",
}

REGISTRY_CANDIDATE_PATHS = (
    r"HKCU:\Software\Glyph",
    r"HKCU:\Software\Trion",
    r"HKCU:\Software\Trion Worlds",
    r"HKLM:\SOFTWARE\Glyph",
    r"HKLM:\SOFTWARE\Trion",
    r"HKLM:\SOFTWARE\Trion Worlds",
    r"HKLM:\SOFTWARE\WOW6432Node\Glyph",
    r"HKLM:\SOFTWARE\WOW6432Node\Trion",
    r"HKLM:\SOFTWARE\WOW6432Node\Trion Worlds",
)


def redact_text(text: str) -> str:
    redacted = BEARER_RE.sub("Bearer <redacted>", text)
    redacted = ASSIGNMENT_RE.sub(lambda match: f"{match.group('key')}{match.group('sep')}<redacted>", redacted)
    redacted = EMAIL_RE.sub("<redacted-email>", redacted)
    redacted = LONG_TOKEN_RE.sub(lambda m: "<redacted-long-value>" if SENSITIVE_KEY_RE.search(text[max(0, m.start() - 40) : m.start()]) else m.group(0), redacted)
    return redacted


def redact_jsonish(value: Any, *, key_hint: str = "") -> Any:
    if SENSITIVE_KEY_RE.search(key_hint):
        return "<redacted>"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_jsonish(item, key_hint=key_hint) for item in value]
    if isinstance(value, Mapping):
        return {str(key): redact_jsonish(item, key_hint=str(key)) for key, item in value.items()}
    return value


def sha256_file(path: Path, *, limit_bytes: int | None = None) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            remaining = limit_bytes
            while True:
                size = 1024 * 1024 if remaining is None else min(remaining, 1024 * 1024)
                if size <= 0:
                    break
                chunk = fh.read(size)
                if not chunk:
                    break
                h.update(chunk)
                if remaining is not None:
                    remaining -= len(chunk)
        return h.hexdigest()
    except OSError:
        return None


def file_metadata(path: Path, *, hash_file: bool = False) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError as exc:
        return {"path": str(path), "exists": False, "error": f"{type(exc).__name__}:{exc}"}
    payload: dict[str, Any] = {
        "path": str(path),
        "exists": True,
        "isFile": path.is_file(),
        "isDirectory": path.is_dir(),
        "sizeBytes": stat.st_size,
        "modifiedUtc": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        "suffix": path.suffix.lower(),
    }
    if hash_file and path.is_file():
        payload["sha256"] = sha256_file(path)
    return payload


def run_powershell_json(script: str, *, timeout_seconds: float = 20.0) -> Any:
    command = [
        "pwsh",
        "-NoProfile",
        "-Command",
        "$ErrorActionPreference='SilentlyContinue'; " + script,
    ]
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    text = (completed.stdout or "").strip()
    if not text:
        return []
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"parseError": True, "stdoutPreview": text[:2000], "stderrPreview": completed.stderr[:1000]}


def process_inventory() -> list[dict[str, Any]]:
    script = r"""
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'glyph' -or ($_.ExecutablePath -match '\\Glyph\\') } |
  Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine,CreationDate |
  ConvertTo-Json -Depth 4
"""
    data = run_powershell_json(script)
    if isinstance(data, Mapping):
        rows = [dict(data)]
    elif isinstance(data, list):
        rows = [dict(item) for item in data if isinstance(item, Mapping)]
    else:
        rows = []
    for row in rows:
        if isinstance(row.get("CommandLine"), str):
            row["CommandLine"] = redact_text(str(row["CommandLine"]))
    return rows


def debugger_indicators(pid: int) -> dict[str, Any]:
    if sys.platform != "win32":
        return {"status": "unsupported-non-windows"}
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return {"status": "open-process-failed", "lastError": ctypes.get_last_error()}
    try:
        is_debugged = ctypes.c_bool(False)
        ok = kernel32.CheckRemoteDebuggerPresent(handle, ctypes.byref(is_debugged))
        result: dict[str, Any] = {
            "status": "checked",
            "checkRemoteDebuggerPresentOk": bool(ok),
            "checkRemoteDebuggerPresent": bool(is_debugged.value) if ok else None,
        }
        for label, info_class in (
            ("processDebugPort", 7),
            ("processDebugObjectHandle", 30),
            ("processDebugFlags", 31),
        ):
            value = ctypes.c_size_t(0)
            return_length = ctypes.c_ulong(0)
            status = ntdll.NtQueryInformationProcess(
                handle,
                info_class,
                ctypes.byref(value),
                ctypes.sizeof(value),
                ctypes.byref(return_length),
            )
            result[label] = {
                "ntstatus": int(status),
                "value": int(value.value),
                "note": "debugFlags:0 can indicate debugged; debugFlags:1 usually indicates not debugged"
                if label == "processDebugFlags"
                else None,
            }
        return result
    finally:
        kernel32.CloseHandle(handle)


def likely_roots(processes: Sequence[Mapping[str, Any]]) -> list[Path]:
    roots: list[Path] = []
    for proc in processes:
        path_value = proc.get("ExecutablePath")
        if isinstance(path_value, str) and path_value:
            path = Path(path_value)
            roots.append(path.parent)
            if path.parent.name.lower() in {"x64", "x86", "bin"}:
                roots.append(path.parent.parent)
    env_candidates = [
        os.environ.get("PROGRAMDATA"),
        os.environ.get("APPDATA"),
        os.environ.get("LOCALAPPDATA"),
        str(Path.home() / "Documents"),
    ]
    for base in env_candidates:
        if not base:
            continue
        for name in ("Glyph", "Trion Worlds", "RIFT"):
            roots.append(Path(base) / name)
    roots.extend(
        [
            Path(r"C:\Program Files (x86)\Glyph"),
            Path(r"C:\Program Files\Glyph"),
            Path(r"C:\ProgramData\Glyph"),
            Path.home() / "AppData" / "Local" / "Glyph",
            Path.home() / "AppData" / "Roaming" / "Glyph",
        ]
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root).lower()
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def walk_interesting_files(root: Path, *, max_files: int) -> dict[str, Any]:
    if not root.exists():
        return {"root": str(root), "exists": False, "files": []}
    files: list[dict[str, Any]] = []
    skipped = 0
    try:
        for current_root, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name.lower() not in SKIP_DIRECTORY_NAMES]
            for filename in filenames:
                path = Path(current_root) / filename
                if len(files) >= max_files:
                    skipped += 1
                    break
                try:
                    suffix = path.suffix.lower()
                except OSError:
                    continue
                if suffix not in INTERESTING_EXTENSIONS:
                    continue
                files.append(file_metadata(path, hash_file=suffix in {".exe", ".dll"}))
            if len(files) >= max_files:
                break
    except OSError as exc:
        return {"root": str(root), "exists": True, "error": f"{type(exc).__name__}:{exc}", "files": files}
    return {"root": str(root), "exists": True, "files": files, "skippedAfterLimit": skipped}


def text_preview(path: Path, *, limit_bytes: int) -> dict[str, Any] | None:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return None
    try:
        data = path.read_bytes()[:limit_bytes]
    except OSError as exc:
        return {"path": str(path), "error": f"{type(exc).__name__}:{exc}"}
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-16", errors="replace") if data.startswith((b"\xff\xfe", b"\xfe\xff")) else data.decode("utf-8", errors="replace")
    redacted = redact_text(text)
    return {
        "path": str(path),
        "bytesRead": len(data),
        "truncated": path.stat().st_size > len(data) if path.exists() else None,
        "preview": redacted[:4000],
    }


def collect_previews(inventories: Sequence[Mapping[str, Any]], *, limit_bytes: int) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    for inventory in inventories:
        for file_info in inventory.get("files", []):
            if not isinstance(file_info, Mapping):
                continue
            path_value = file_info.get("path")
            if not isinstance(path_value, str):
                continue
            preview = text_preview(Path(path_value), limit_bytes=limit_bytes)
            if preview is not None:
                previews.append(preview)
    return previews


def signature_and_version(paths: Iterable[Path]) -> list[dict[str, Any]]:
    path_list = [str(path) for path in paths if path.exists() and path.is_file()]
    if not path_list:
        return []
    encoded = json.dumps(path_list)
    script = rf"""
$paths = ConvertFrom-Json @'
{encoded}
'@
$items = foreach ($p in $paths) {{
  $item = Get-Item -LiteralPath $p
  $sig = Get-AuthenticodeSignature -LiteralPath $p
  [PSCustomObject]@{{
    path = $p
    version = $item.VersionInfo.FileVersion
    productVersion = $item.VersionInfo.ProductVersion
    productName = $item.VersionInfo.ProductName
    companyName = $item.VersionInfo.CompanyName
    originalFilename = $item.VersionInfo.OriginalFilename
    signatureStatus = [string]$sig.Status
    signerCertificateSubject = if ($sig.SignerCertificate) {{ $sig.SignerCertificate.Subject }} else {{ $null }}
    signerCertificateThumbprint = if ($sig.SignerCertificate) {{ $sig.SignerCertificate.Thumbprint }} else {{ $null }}
  }}
}}
$items | ConvertTo-Json -Depth 5
"""
    data = run_powershell_json(script, timeout_seconds=30.0)
    if isinstance(data, Mapping):
        return [dict(data)]
    if isinstance(data, list):
        return [dict(item) for item in data if isinstance(item, Mapping)]
    return []


def module_inventory(pid: int) -> dict[str, Any]:
    script = rf"""
$p = Get-Process -Id {int(pid)}
$p.Modules |
  Select-Object ModuleName,FileName,BaseAddress,ModuleMemorySize |
  ConvertTo-Json -Depth 4
"""
    data = run_powershell_json(script, timeout_seconds=30.0)
    if isinstance(data, Mapping):
        modules = [dict(data)]
    elif isinstance(data, list):
        modules = [dict(item) for item in data if isinstance(item, Mapping)]
    else:
        modules = []
    return {"pid": int(pid), "moduleCount": len(modules), "modules": modules[:300], "truncated": len(modules) > 300}


def registry_inventory() -> list[dict[str, Any]]:
    encoded = json.dumps(list(REGISTRY_CANDIDATE_PATHS))
    script = rf"""
$seedPaths = ConvertFrom-Json @'
{encoded}
'@
$expanded = New-Object System.Collections.Generic.List[string]
foreach ($path in $seedPaths) {{
  $expanded.Add([string]$path)
  if (Test-Path -LiteralPath $path) {{
    Get-ChildItem -LiteralPath $path -ErrorAction SilentlyContinue | Select-Object -First 80 | ForEach-Object {{
      $childPath = [string]$_.PSPath
      $expanded.Add($childPath)
      Get-ChildItem -LiteralPath $childPath -ErrorAction SilentlyContinue | Select-Object -First 80 | ForEach-Object {{
        $expanded.Add([string]$_.PSPath)
      }}
    }}
  }}
}}
$items = foreach ($path in ($expanded | Select-Object -Unique)) {{
  if (-not (Test-Path -LiteralPath $path)) {{
    [PSCustomObject]@{{ path = $path; exists = $false; values = @{{}}; subKeys = @() }}
    continue
  }}
  $props = Get-ItemProperty -LiteralPath $path -ErrorAction SilentlyContinue
  $values = @{{}}
  if ($props) {{
    foreach ($prop in $props.PSObject.Properties) {{
      if ($prop.Name -notlike 'PS*') {{
        $values[$prop.Name] = $prop.Value
      }}
    }}
  }}
  $subKeys = @(Get-ChildItem -LiteralPath $path -ErrorAction SilentlyContinue | Select-Object -First 80 -ExpandProperty PSChildName)
  [PSCustomObject]@{{ path = $path; exists = $true; values = $values; subKeys = $subKeys }}
}}
$items | ConvertTo-Json -Depth 8
"""
    data = run_powershell_json(script, timeout_seconds=30.0)
    if isinstance(data, Mapping):
        rows = [dict(data)]
    elif isinstance(data, list):
        rows = [dict(item) for item in data if isinstance(item, Mapping)]
    else:
        rows = []
    return [redact_jsonish(row) for row in rows]


def extract_ascii_strings(path: Path, *, max_hits: int) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {"path": str(path), "status": "missing"}
    try:
        data = path.read_bytes()
    except OSError as exc:
        return {"path": str(path), "status": "failed", "error": f"{type(exc).__name__}:{exc}"}
    ascii_strings = re.findall(rb"[\x20-\x7e]{6,}", data)
    utf16_strings = re.findall((rb"(?:[\x20-\x7e]\x00){6,}"), data)
    decoded: list[str] = [item.decode("ascii", errors="ignore") for item in ascii_strings[:20000]]
    decoded.extend(item.decode("utf-16le", errors="ignore") for item in utf16_strings[:20000])
    interesting: list[str] = []
    seen: set[str] = set()
    for value in decoded:
        if URL_RE.search(value) or HOST_RE.search(value) or REGISTRY_RE.search(value) or any(
            term in value.lower() for term in ("glyph", "trion", "rift", "patch", "manifest", "login", "auth", "crash", "update")
        ):
            clean = redact_text(value.strip())
            if clean and clean not in seen:
                seen.add(clean)
                interesting.append(clean)
                if len(interesting) >= max_hits:
                    break
    return {
        "path": str(path),
        "status": "passed",
        "totalAsciiStringsSampled": len(ascii_strings),
        "totalUtf16StringsSampled": len(utf16_strings),
        "interestingCount": len(interesting),
        "interestingStrings": interesting,
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Glyph forensics inventory",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        "",
        "## Running processes",
        "",
    ]
    for proc in summary.get("processes", []):
        if isinstance(proc, Mapping):
            lines.append(
                f"- PID `{proc.get('ProcessId')}` `{proc.get('Name')}` path=`{proc.get('ExecutablePath')}` parent=`{proc.get('ParentProcessId')}`"
            )
    lines.extend(["", "## Executables", ""])
    for item in summary.get("executableMetadata", []):
        if isinstance(item, Mapping):
            lines.append(f"- `{item.get('path')}` sha256=`{item.get('sha256')}`")
    registry_rows = summary.get("registryInventory") if isinstance(summary.get("registryInventory"), list) else []
    existing_registry = [item for item in registry_rows if isinstance(item, Mapping) and item.get("exists")]
    lines.extend(["", "## Registry keys", ""])
    if existing_registry:
        for item in existing_registry:
            value_count = len(item.get("values", {})) if isinstance(item.get("values"), Mapping) else 0
            subkey_count = len(item.get("subKeys", [])) if isinstance(item.get("subKeys"), list) else 0
            lines.append(f"- `{item.get('path')}` values=`{value_count}` subKeys=`{subkey_count}`")
    else:
        lines.append("- none of the seeded Glyph/Trion registry keys existed")
    lines.extend(["", "## Safety", ""])
    safety = safe_mapping(summary.get("safety"))
    for key in ("debuggerAttachedByThisHelper", "processMemoryDumped", "processMemoryRead", "debuggerAttach", "tokensRedacted"):
        lines.append(f"- {key}: `{safety.get(key)}`")
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{item}`" for item in summary.get("warnings", []))
    if summary.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- `{item}`" for item in summary.get("errors", []))
    return "\n".join(lines) + "\n"


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"glyph-forensics-inventory-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    processes = process_inventory()
    glyph_processes = [proc for proc in processes if str(proc.get("Name", "")).lower().startswith("glyph")]
    roots = likely_roots(glyph_processes)
    inventories = [walk_interesting_files(root_path, max_files=int(args.max_files_per_root)) for root_path in roots]
    exe_paths: list[Path] = []
    for proc in glyph_processes:
        exe = proc.get("ExecutablePath")
        if isinstance(exe, str) and exe:
            exe_paths.append(Path(exe))
    for inventory in inventories:
        for file_info in inventory.get("files", []):
            if isinstance(file_info, Mapping) and str(file_info.get("suffix", "")).lower() == ".exe":
                exe_paths.append(Path(str(file_info.get("path"))))
    unique_exes: list[Path] = []
    seen_exes: set[str] = set()
    for path in exe_paths:
        key = str(path).lower()
        if key not in seen_exes:
            seen_exes.add(key)
            unique_exes.append(path)
    executable_metadata = [file_metadata(path, hash_file=True) for path in unique_exes]
    signatures = signature_and_version(unique_exes)
    registry = registry_inventory()
    debug_checks = []
    modules = []
    for proc in glyph_processes:
        try:
            pid = int(proc.get("ProcessId"))
        except (TypeError, ValueError):
            continue
        debug_checks.append({"pid": pid, **debugger_indicators(pid)})
        modules.append(module_inventory(pid))
    string_summaries = [extract_ascii_strings(path, max_hits=int(args.max_string_hits)) for path in unique_exes[:20]]
    previews = collect_previews(inventories, limit_bytes=int(args.text_preview_bytes))
    safety = base_safety()
    safety.update(
        {
            "readOnlyForensics": True,
            "debuggerAttachedByThisHelper": False,
            "debuggerAttach": False,
            "processMemoryDumped": False,
            "processMemoryRead": False,
            "tokensRedacted": True,
            "credentialExtractionAttempted": False,
            "x64dbgAttach": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
        }
    )
    warnings: list[str] = []
    if not glyph_processes:
        warnings.append("glyph-process-not-found")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "repoRoot": str(root),
        "input": {
            "maxFilesPerRoot": int(args.max_files_per_root),
            "textPreviewBytes": int(args.text_preview_bytes),
            "maxStringHits": int(args.max_string_hits),
        },
        "processes": processes,
        "debuggerIndicators": debug_checks,
        "moduleInventory": modules,
        "candidateRoots": [str(item) for item in roots],
        "fileInventories": inventories,
        "executableMetadata": executable_metadata,
        "signaturesAndVersions": signatures,
        "registryInventory": registry,
        "textPreviewsRedacted": previews,
        "staticStringSummaries": string_summaries,
        "warnings": warnings,
        "errors": [],
        "safety": safety,
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect safe read-only Glyph launcher forensics with redaction")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--max-files-per-root", type=int, default=DEFAULT_MAX_FILES_PER_ROOT)
    parser.add_argument("--text-preview-bytes", type=int, default=DEFAULT_TEXT_PREVIEW_BYTES)
    parser.add_argument("--max-string-hits", type=int, default=DEFAULT_MAX_STRING_HITS)
    parser.add_argument("--json", action="store_true")
    return parser


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    glyph_processes = [proc for proc in summary.get("processes", []) if isinstance(proc, Mapping) and str(proc.get("Name", "")).lower().startswith("glyph")]
    return {
        "status": summary.get("status"),
        "kind": summary.get("kind"),
        "glyphProcessCount": len(glyph_processes),
        "glyphPids": [proc.get("ProcessId") for proc in glyph_processes],
        "candidateRootCount": len(summary.get("candidateRoots", [])),
        "executableCount": len(summary.get("executableMetadata", [])),
        "registryKeyCount": len([item for item in summary.get("registryInventory", []) if isinstance(item, Mapping) and item.get("exists")]),
        "textPreviewCount": len(summary.get("textPreviewsRedacted", [])),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
        "safety": {
            key: safe_mapping(summary.get("safety")).get(key)
            for key in (
                "debuggerAttachedByThisHelper",
                "processMemoryDumped",
                "processMemoryRead",
                "tokensRedacted",
            )
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    summary = build_report(args)
    artifacts = safe_mapping(summary.get("artifacts"))
    write_json(Path(str(artifacts["summaryJson"])), summary)
    Path(str(artifacts["summaryMarkdown"])).write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(compact(summary)) if args.json else json.dumps(compact(summary), indent=2))
    return 0 if summary.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
