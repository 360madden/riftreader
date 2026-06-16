#!/usr/bin/env python3
# Version: riftreader-tracked-repo-context-v0.1.1
# Total-Character-Count: 0000025980
# Purpose: Read and search only bounded git-tracked text files for RiftReader context tools.

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
TOOL_VERSION = "riftreader-tracked-repo-context-v0.1.1"
DEFAULT_MAX_FILE_BYTES = 1_048_576
DEFAULT_MAX_TOTAL_BYTES = 2_097_152
DEFAULT_MAX_MATCHES = 50
DEFAULT_MAX_TREE_ITEMS = 5000

ALLOWED_TEXT_SUFFIXES = {
    "",
    ".ahk",
    ".bat",
    ".cfg",
    ".cmd",
    ".cs",
    ".csv",
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    ".html",
    ".ini",
    ".json",
    ".jsonl",
    ".lua",
    ".md",
    ".ps1",
    ".psm1",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".xml",
    ".xaml",
    ".yaml",
    ".yml",
}
ALLOWED_TEXT_NAMES = {
    "dockerfile",
    "license",
    "makefile",
    "notice",
    "readme",
}
BLOCKED_SUFFIXES = {
    ".7z",
    ".bin",
    ".bmp",
    ".db",
    ".der",
    ".dll",
    ".dmp",
    ".dump",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".npy",
    ".p12",
    ".p7b",
    ".pcap",
    ".pdf",
    ".pfx",
    ".pickle",
    ".pkl",
    ".png",
    ".pyc",
    ".rar",
    ".sqlite",
    ".webp",
    ".zip",
}
SECRET_SUFFIXES = {
    ".crt",
    ".key",
    ".pem",
}
SECRET_NAMES = {
    ".env",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "known_hosts",
}
BLOCKED_PARTS = {
    ".git",
    ".riftreader-local",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}


@dataclass(frozen=True)
class PathPolicy:
    path: str
    allowed: bool
    reason: str | None = None


class ContextError(RuntimeError):
    def __init__(self, reason: str, message: str | None = None) -> None:
        super().__init__(message or reason)
        self.reason = reason


def _json_base(kind: str) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": kind,
        "toolVersion": TOOL_VERSION,
    }


def _safe_error(kind: str, reason: str, message: str | None = None) -> dict[str, Any]:
    data = _json_base(kind)
    data.update({"ok": False, "status": "blocked", "reason": reason})
    if message:
        data["message"] = message
    return data


def _run_git(repo_root: Path | None, args: list[str], timeout_seconds: float = 30.0) -> subprocess.CompletedProcess[bytes]:
    if not args or args[0].startswith("-"):
        raise ContextError("invalid-git-args")
    cwd = str(repo_root) if repo_root is not None else None
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            shell=False,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise ContextError("git-not-found", "git executable was not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise ContextError("git-timeout", f"git command timed out after {timeout_seconds}s") from exc


def _decode_stdout(proc: subprocess.CompletedProcess[bytes]) -> str:
    return proc.stdout.decode("utf-8", errors="replace")


def find_repo_root(start: str | Path | None = None) -> Path:
    start_path = Path(start) if start is not None else Path.cwd()
    proc = _run_git(start_path, ["rev-parse", "--show-toplevel"])
    if proc.returncode != 0:
        raise ContextError("not-a-git-repo", proc.stderr.decode("utf-8", errors="replace").strip())
    root = _decode_stdout(proc).strip()
    if not root:
        raise ContextError("empty-repo-root")
    return Path(root).resolve()


def repo_head_summary(repo_root: Path) -> dict[str, Any]:
    branch_proc = _run_git(repo_root, ["branch", "--show-current"])
    head_proc = _run_git(repo_root, ["rev-parse", "--short", "HEAD"])
    return {
        "branch": _decode_stdout(branch_proc).strip() if branch_proc.returncode == 0 else None,
        "head": _decode_stdout(head_proc).strip() if head_proc.returncode == 0 else None,
    }


def normalize_repo_path(raw_path: str) -> str:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ContextError("empty-path")
    decoded = urllib.parse.unquote(raw_path.strip())
    if "\x00" in decoded:
        raise ContextError("nul-byte-path")
    if "\\" in decoded:
        raise ContextError("backslash-path")
    if decoded.startswith("/") or decoded.startswith("~"):
        raise ContextError("absolute-path")
    if re.match(r"^[A-Za-z]:", decoded):
        raise ContextError("absolute-path")
    cleaned = decoded[2:] if decoded.startswith("./") else decoded
    parts = [part for part in cleaned.split("/") if part not in ("", ".")]
    if not parts:
        raise ContextError("empty-path")
    if any(part == ".." for part in parts):
        raise ContextError("path-traversal")
    return "/".join(parts)


def path_policy(path: str) -> PathPolicy:
    try:
        normalized = normalize_repo_path(path)
    except ContextError as exc:
        return PathPolicy(path=path, allowed=False, reason=exc.reason)
    parts = normalized.split("/")
    lower_parts = [part.lower() for part in parts]
    name = lower_parts[-1]
    suffix = Path(name).suffix.lower()
    if any(part in BLOCKED_PARTS for part in lower_parts):
        return PathPolicy(normalized, False, "blocked-directory")
    if name in SECRET_NAMES or name.startswith(".env."):
        return PathPolicy(normalized, False, "secret-like-name")
    if suffix in SECRET_SUFFIXES:
        return PathPolicy(normalized, False, "secret-like-extension")
    if any("secret" in part or "credential" in part for part in lower_parts):
        return PathPolicy(normalized, False, "secret-like-path")
    if suffix in BLOCKED_SUFFIXES:
        return PathPolicy(normalized, False, "blocked-extension")
    if suffix not in ALLOWED_TEXT_SUFFIXES and name not in ALLOWED_TEXT_NAMES:
        return PathPolicy(normalized, False, "unsupported-extension")
    return PathPolicy(normalized, True)


def list_git_tracked_paths(repo_root: Path) -> list[str]:
    proc = _run_git(repo_root, ["ls-files", "-z"])
    if proc.returncode != 0:
        raise ContextError("git-ls-files-failed", proc.stderr.decode("utf-8", errors="replace").strip())
    paths = []
    for raw in proc.stdout.split(b"\x00"):
        if not raw:
            continue
        text = raw.decode("utf-8", errors="replace").replace("\\", "/")
        if text:
            paths.append(text)
    return sorted(set(paths))


def tracked_path_set(repo_root: Path) -> set[str]:
    return set(list_git_tracked_paths(repo_root))


def _file_size(repo_root: Path, rel_path: str) -> int | None:
    try:
        return (repo_root / rel_path).stat().st_size
    except OSError:
        return None


def _read_text(repo_root: Path, rel_path: str, max_bytes: int) -> tuple[str, int, str | None]:
    file_path = repo_root / rel_path
    size = file_path.stat().st_size
    if size > max_bytes:
        raise ContextError("file-too-large", f"{rel_path} is {size} bytes, limit is {max_bytes}")
    data = file_path.read_bytes()
    if b"\x00" in data[:4096]:
        raise ContextError("binary-content")
    try:
        return data.decode("utf-8"), size, None
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace"), size, "utf-8-replacement"


def _make_record(repo_root: Path, rel_path: str) -> dict[str, Any]:
    policy = path_policy(rel_path)
    size = _file_size(repo_root, policy.path if policy.allowed else rel_path)
    record = {
        "path": policy.path,
        "allowed": policy.allowed,
        "sizeBytes": size,
    }
    if policy.reason:
        record["reason"] = policy.reason
    return record


def repo_tree_tracked(
    repo_root: str | Path | None = None,
    prefix: str | None = None,
    depth: int | None = None,
    limit: int = DEFAULT_MAX_TREE_ITEMS,
    include_blocked_meta: bool = False,
) -> dict[str, Any]:
    kind = "riftreader-repo-tree-tracked"
    try:
        root = find_repo_root(repo_root)
        prefix_norm = normalize_repo_path(prefix) if prefix else None
        rows: list[dict[str, Any]] = []
        blocked_count = 0
        omitted_count = 0
        for rel_path in list_git_tracked_paths(root):
            policy = path_policy(rel_path)
            if prefix_norm and not policy.path.startswith(prefix_norm.rstrip("/") + "/") and policy.path != prefix_norm:
                continue
            if depth is not None:
                base_depth = len(prefix_norm.split("/")) if prefix_norm else 0
                if len(policy.path.split("/")) - base_depth > depth:
                    continue
            if not policy.allowed:
                blocked_count += 1
                if include_blocked_meta and len(rows) < limit:
                    rows.append({"path": policy.path, "allowed": False, "reason": policy.reason})
                continue
            if len(rows) >= limit:
                omitted_count += 1
                continue
            rows.append(_make_record(root, policy.path))
        result = _json_base(kind)
        result.update(
            {
                "ok": True,
                "status": "passed",
                "repo": repo_head_summary(root),
                "prefix": prefix_norm,
                "depth": depth,
                "count": len(rows),
                "blockedCount": blocked_count,
                "omittedCount": omitted_count,
                "files": rows,
            }
        )
        return result
    except ContextError as exc:
        return _safe_error(kind, exc.reason, str(exc))


def repo_read_tracked_file(
    path: str,
    repo_root: str | Path | None = None,
    max_bytes: int = DEFAULT_MAX_FILE_BYTES,
    include_sha256: bool = False,
) -> dict[str, Any]:
    kind = "riftreader-repo-read-tracked-file"
    try:
        root = find_repo_root(repo_root)
        rel_path = normalize_repo_path(path)
        if rel_path not in tracked_path_set(root):
            raise ContextError("not-git-tracked")
        policy = path_policy(rel_path)
        if not policy.allowed:
            raise ContextError(policy.reason or "path-blocked")
        text, size, decode_warning = _read_text(root, rel_path, max_bytes=max_bytes)
        result = _json_base(kind)
        result.update(
            {
                "ok": True,
                "status": "passed",
                "path": rel_path,
                "sizeBytes": size,
                "content": text,
            }
        )
        if include_sha256:
            result["sha256"] = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
        if decode_warning:
            result["warnings"] = [decode_warning]
        return result
    except ContextError as exc:
        result = _safe_error(kind, exc.reason, str(exc))
        result["path"] = path
        return result
    except OSError as exc:
        result = _safe_error(kind, "file-read-error", str(exc))
        result["path"] = path
        return result


def repo_read_many_tracked_files(
    paths: Iterable[str],
    repo_root: str | Path | None = None,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    max_files: int = 20,
) -> dict[str, Any]:
    kind = "riftreader-repo-read-many-tracked-files"
    items: list[dict[str, Any]] = []
    total_bytes = 0
    path_list = list(paths)
    for index, path in enumerate(path_list):
        if index >= max_files:
            items.append(_safe_error("riftreader-repo-read-many-item", "max-files-exceeded", path))
            break
        remaining = max(0, max_total_bytes - total_bytes)
        if remaining <= 0:
            items.append(_safe_error("riftreader-repo-read-many-item", "max-total-bytes-exceeded", path))
            break
        item = repo_read_tracked_file(path, repo_root=repo_root, max_bytes=min(max_file_bytes, remaining))
        if item.get("ok"):
            total_bytes += int(item.get("sizeBytes") or 0)
        items.append(item)
    result = _json_base(kind)
    result.update(
        {
            "ok": all(bool(item.get("ok")) for item in items),
            "status": "passed" if all(bool(item.get("ok")) for item in items) else "partial",
            "requestedCount": len(path_list),
            "returnedCount": len(items),
            "totalBytes": total_bytes,
            "files": items,
        }
    )
    return result


def _iter_searchable_files(repo_root: Path, max_file_bytes: int) -> Iterable[str]:
    for rel_path in list_git_tracked_paths(repo_root):
        policy = path_policy(rel_path)
        if not policy.allowed:
            continue
        size = _file_size(repo_root, policy.path)
        if size is None or size > max_file_bytes:
            continue
        yield policy.path


def _make_snippet(line: str, needle_start: int, needle_end: int, radius: int = 90) -> str:
    start = max(0, needle_start - radius)
    end = min(len(line), needle_end + radius)
    prefix = "…" if start else ""
    suffix = "…" if end < len(line) else ""
    return prefix + line[start:end].rstrip("\r\n") + suffix


def repo_search_tracked(
    query: str,
    repo_root: str | Path | None = None,
    case_sensitive: bool = False,
    regex: bool = False,
    max_matches: int = DEFAULT_MAX_MATCHES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> dict[str, Any]:
    kind = "riftreader-repo-search-tracked"
    try:
        if not isinstance(query, str) or not query.strip():
            raise ContextError("empty-query")
        if len(query) > 500:
            raise ContextError("query-too-large")
        root = find_repo_root(repo_root)
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(query if regex else re.escape(query), flags)
        matches: list[dict[str, Any]] = []
        scanned_files = 0
        for rel_path in _iter_searchable_files(root, max_file_bytes=max_file_bytes):
            if len(matches) >= max_matches:
                break
            try:
                text, size, _decode_warning = _read_text(root, rel_path, max_bytes=max_file_bytes)
            except ContextError:
                continue
            scanned_files += 1
            for line_no, line in enumerate(text.splitlines(keepends=True), start=1):
                for match in pattern.finditer(line):
                    matches.append(
                        {
                            "path": rel_path,
                            "line": line_no,
                            "sizeBytes": size,
                            "snippet": _make_snippet(line, match.start(), match.end()),
                        }
                    )
                    if len(matches) >= max_matches:
                        break
                if len(matches) >= max_matches:
                    break
        result = _json_base(kind)
        result.update(
            {
                "ok": True,
                "status": "passed",
                "query": query,
                "regex": regex,
                "caseSensitive": case_sensitive,
                "scannedFiles": scanned_files,
                "matchCount": len(matches),
                "maxMatches": max_matches,
                "matches": matches,
            }
        )
        return result
    except re.error as exc:
        return _safe_error(kind, "invalid-regex", str(exc))
    except ContextError as exc:
        return _safe_error(kind, exc.reason, str(exc))


PACK_PATTERNS: dict[str, list[str]] = {
    "mcp-adapter": [
        "START_RIFTREADER_CHATGPT_MCP.cmd",
        "tools/riftreader_workflow/riftreader_chatgpt_mcp.py",
        "scripts/test_riftreader_chatgpt_mcp.py",
        "docs/workflow/riftreader-chatgpt-mcp.md",
    ],
    "git-state": [
        "tools/riftreader_workflow/git_state_reader.py",
        "scripts/test_git_state_reader.py",
        "docs/workflow/*git*state*.md",
        "docs/handoffs/*phase1b*git*state*.md",
    ],
    "package-flow": [
        "tools/riftreader_workflow/*package*.py",
        "tools/riftreader_workflow/*artifact*bridge*.py",
        "scripts/*package*.cmd",
        "scripts/*artifact*bridge*.cmd",
        "scripts/test_*package*.py",
        "scripts/test_*artifact*bridge*.py",
        "docs/workflow/*package*.md",
        "docs/workflow/*artifact*bridge*.md",
    ],
    "workflow-docs": [
        "docs/HANDOFF.md",
        "docs/workflow/riftreader-chatgpt-mcp-50-stage-plan.md",
        "docs/workflow/riftreader-chatgpt-mcp.md",
        "docs/handoffs/*.md",
        "docs/workflow/*.md",
    ],
}


def _handoff_sort_key(path: str) -> tuple[int, int, int, int, int, str]:
    """Sort handoff filenames by their leading date/time, newest first."""

    name = Path(path).name
    match = re.match(
        r"^(?P<year>\d{4})-?(?P<month>\d{2})-?(?P<day>\d{2})(?:[-T]?(?P<hour>\d{2})(?P<minute>\d{2})?)?",
        name,
    )
    if not match:
        return (0, 0, 0, 0, 0, path)
    groups = match.groupdict()
    return (
        int(groups["year"]),
        int(groups["month"]),
        int(groups["day"]),
        int(groups.get("hour") or 0),
        int(groups.get("minute") or 0),
        path,
    )


def _sort_pack_matches(pack_name: str, pattern: str, paths: list[str]) -> list[str]:
    if pack_name == "workflow-docs" and pattern == "docs/handoffs/*.md":
        return sorted(paths, key=_handoff_sort_key, reverse=True)
    return sorted(paths)


def _select_pack_paths(repo_root: Path, pack_name: str, limit: int) -> tuple[list[str], list[str]]:
    tracked = list_git_tracked_paths(repo_root)
    patterns = PACK_PATTERNS.get(pack_name)
    if patterns is None:
        raise ContextError("unknown-context-pack")
    selected: list[str] = []
    selected_set: set[str] = set()
    missing: list[str] = []

    def append_once(path: str) -> None:
        if path in selected_set:
            return
        selected.append(path)
        selected_set.add(path)

    for pattern in patterns:
        if any(ch in pattern for ch in "*?["):
            found = [path for path in tracked if fnmatch.fnmatch(path, pattern)]
            for path in _sort_pack_matches(pack_name, pattern, found):
                append_once(path)
            if not found:
                missing.append(pattern)
        elif pattern in tracked:
            append_once(pattern)
        else:
            missing.append(pattern)
    return selected[:limit], missing


def repo_context_pack(
    pack_name: str,
    repo_root: str | Path | None = None,
    max_files: int = 12,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> dict[str, Any]:
    kind = "riftreader-repo-context-pack"
    try:
        root = find_repo_root(repo_root)
        paths, missing = _select_pack_paths(root, pack_name, limit=max_files)
        files = repo_read_many_tracked_files(
            paths,
            repo_root=root,
            max_files=max_files,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
        )
        result = _json_base(kind)
        result.update(
            {
                "ok": bool(files.get("ok")),
                "status": "passed" if files.get("ok") else "partial",
                "packName": pack_name,
                "availablePacks": sorted(PACK_PATTERNS),
                "selectedPaths": paths,
                "missingPatterns": missing,
                "files": files.get("files", []),
            }
        )
        return result
    except ContextError as exc:
        result = _safe_error(kind, exc.reason, str(exc))
        result["availablePacks"] = sorted(PACK_PATTERNS)
        return result


def run_self_test() -> dict[str, Any]:
    kind = "riftreader-repo-context-self-test"
    with tempfile.TemporaryDirectory(prefix="riftreader-tracked-context-") as temp_dir:
        root = Path(temp_dir)
        (root / "docs" / "workflow").mkdir(parents=True)
        (root / "tools" / "riftreader_workflow").mkdir(parents=True)
        (root / "scripts").mkdir(parents=True)
        (root / "data").mkdir(parents=True)
        (root / ".riftreader-local").mkdir(parents=True)
        (root / "docs" / "workflow" / "demo.md").write_text("Needle demo document\n", encoding="utf-8")
        (root / "tools" / "riftreader_workflow" / "helper.py").write_text("print('needle')\n", encoding="utf-8")
        (root / "scripts" / "run.cmd").write_text("@echo off\nREM needle\n", encoding="utf-8")
        (root / "data" / "payload.bin").write_bytes(b"\x00\x01\x02")
        (root / ".env").write_text("TOKEN=needle\n", encoding="utf-8")
        (root / ".riftreader-local" / "local.md").write_text("needle local\n", encoding="utf-8")
        _run_git(root, ["init"])
        _run_git(root, ["add", "docs/workflow/demo.md", "tools/riftreader_workflow/helper.py", "scripts/run.cmd", "data/payload.bin", ".env", ".riftreader-local/local.md"])
        tree = repo_tree_tracked(repo_root=root)
        read_ok = repo_read_tracked_file("docs/workflow/demo.md", repo_root=root)
        search = repo_search_tracked("needle", repo_root=root)
        blocked_secret = repo_read_tracked_file(".env", repo_root=root)
        blocked_binary = repo_read_tracked_file("data/payload.bin", repo_root=root)
        blocked_local = repo_read_tracked_file(".riftreader-local/local.md", repo_root=root)
        checks = {
            "tree_ok": tree.get("ok") is True and any(row.get("path") == "docs/workflow/demo.md" for row in tree.get("files", [])),
            "read_ok": read_ok.get("ok") is True and "Needle" in read_ok.get("content", ""),
            "search_ok": search.get("ok") is True and search.get("matchCount", 0) >= 3,
            "secret_blocked": blocked_secret.get("ok") is False and blocked_secret.get("reason") == "secret-like-name",
            "binary_blocked": blocked_binary.get("ok") is False and blocked_binary.get("reason") == "blocked-extension",
            "local_blocked": blocked_local.get("ok") is False and blocked_local.get("reason") == "blocked-directory",
        }
        result = _json_base(kind)
        result.update({"ok": all(checks.values()), "status": "passed" if all(checks.values()) else "failed", "checks": checks})
        return result


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read/search bounded git-tracked RiftReader repo context.")
    parser.add_argument("--repo-root", default=None, help="Optional repo root or child path. Defaults to current directory.")
    parser.add_argument("--json", action="store_true", help="Print clean JSON output. Human output is not implemented; JSON is always printed.")
    sub = parser.add_subparsers(dest="command", required=True)

    tree = sub.add_parser("tree", help="List allowed git-tracked text paths.")
    tree.add_argument("--prefix", default=None)
    tree.add_argument("--depth", type=int, default=None)
    tree.add_argument("--limit", type=int, default=DEFAULT_MAX_TREE_ITEMS)
    tree.add_argument("--include-blocked-meta", action="store_true")

    search = sub.add_parser("search", help="Search allowed git-tracked text paths.")
    search.add_argument("query")
    search.add_argument("--case-sensitive", action="store_true")
    search.add_argument("--regex", action="store_true")
    search.add_argument("--max-matches", type=int, default=DEFAULT_MAX_MATCHES)
    search.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)

    read = sub.add_parser("read", help="Read one allowed git-tracked text file.")
    read.add_argument("path")
    read.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    read.add_argument("--sha256", action="store_true")

    many = sub.add_parser("read-many", help="Read multiple allowed git-tracked text files.")
    many.add_argument("paths", nargs="+")
    many.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    many.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    many.add_argument("--max-files", type=int, default=20)

    pack = sub.add_parser("context-pack", help="Read a predefined context pack.")
    pack.add_argument("pack_name")
    pack.add_argument("--max-files", type=int, default=12)
    pack.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    pack.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)

    sub.add_parser("self-test", help="Run a synthetic temp-repo self-test.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parsed_argv = list(sys.argv[1:] if argv is None else argv)
    # Allow --json and --repo-root before or after the subcommand so PowerShell snippets stay ergonomic.
    repo_root_override: str | None = None
    clean_argv: list[str] = []
    index = 0
    while index < len(parsed_argv):
        item = parsed_argv[index]
        if item == "--json":
            index += 1
            continue
        if item == "--repo-root" and index + 1 < len(parsed_argv):
            repo_root_override = parsed_argv[index + 1]
            index += 2
            continue
        if item.startswith("--repo-root="):
            repo_root_override = item.split("=", 1)[1]
            index += 1
            continue
        clean_argv.append(item)
        index += 1
    parser = build_arg_parser()
    args = parser.parse_args(clean_argv)
    if repo_root_override is not None:
        args.repo_root = repo_root_override
    if args.command == "tree":
        data = repo_tree_tracked(args.repo_root, prefix=args.prefix, depth=args.depth, limit=args.limit, include_blocked_meta=args.include_blocked_meta)
    elif args.command == "search":
        data = repo_search_tracked(args.query, repo_root=args.repo_root, case_sensitive=args.case_sensitive, regex=args.regex, max_matches=args.max_matches, max_file_bytes=args.max_file_bytes)
    elif args.command == "read":
        data = repo_read_tracked_file(args.path, repo_root=args.repo_root, max_bytes=args.max_bytes, include_sha256=args.sha256)
    elif args.command == "read-many":
        data = repo_read_many_tracked_files(args.paths, repo_root=args.repo_root, max_file_bytes=args.max_file_bytes, max_total_bytes=args.max_total_bytes, max_files=args.max_files)
    elif args.command == "context-pack":
        data = repo_context_pack(args.pack_name, repo_root=args.repo_root, max_files=args.max_files, max_file_bytes=args.max_file_bytes, max_total_bytes=args.max_total_bytes)
    elif args.command == "self-test":
        data = run_self_test()
    else:
        parser.error(f"unknown command: {args.command}")
    _print_json(data)
    return 0 if data.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
