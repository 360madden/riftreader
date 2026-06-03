#!/usr/bin/env python3
# Version: riftreader-chatgpt-snapshot-publisher-v0.1.0
# Total-Character-Count: 0000026963
# Purpose: Capture curated RiftReader Local Artifact Bridge endpoints from localhost, write redacted ChatGPT snapshot files, and optionally publish only those snapshot files to a dedicated GitHub transport branch.
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

VERSION = "riftreader-chatgpt-snapshot-publisher-v0.1.0"
DEFAULT_REPO_ROOT = Path(r"C:\RIFT MODDING\RiftReader")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_TOKEN_URL_FILE = Path(".riftreader-local") / "bridge-one-tab" / "COPY_THIS_CHATGPT_URL.txt"
DEFAULT_SNAPSHOT_MD = Path("handoffs") / "current" / "RIFTREADER_CHATGPT_SNAPSHOT.md"
DEFAULT_SNAPSHOT_JSON = Path("handoffs") / "current" / "RIFTREADER_CHATGPT_SNAPSHOT.json"
DEFAULT_SNAPSHOT_BRANCH = "chatgpt/snapshot"
DEFAULT_MAX_KB = 768
DEFAULT_CHUNKS = ("desktop-chatgpt-workflow", "local-artifact-bridge-docs", "repo-status")
TRYCLOUDFLARE_RE = re.compile(r"https://[A-Za-z0-9-]+\.trycloudflare\.com(?:/[A-Za-z0-9._~%-]+)?")
CHUNK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
ENDPOINTS_FIXED = (
    ("chatgpt_handoff", "/chatgpt-handoff.json"),
    ("health", "/health"),
    ("readme", "/payloads/latest/readme.md"),
    ("chunks", "/payloads/latest/chunks.json"),
)


class SnapshotError(RuntimeError):
    """Raised for deterministic operator-facing snapshot failures."""


@dataclasses.dataclass(frozen=True)
class BridgeSource:
    host: str
    port: int
    token: str
    public_url: str | None = None

    @property
    def local_base(self) -> str:
        return f"http://{self.host}:{self.port}/{self.token}"

    @property
    def redacted_local_base(self) -> str:
        return f"http://{self.host}:{self.port}/<redacted-token>"


@dataclasses.dataclass
class EndpointCapture:
    name: str
    path: str
    status: str
    sha256: str | None
    size_bytes: int
    content: str
    error: str | None = None

    def to_json(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise SnapshotError(f"Failed to read {path}: {type(exc).__name__}: {exc}") from exc


def ensure_repo_root(repo_root: Path) -> Path:
    repo_root = repo_root.expanduser().resolve()
    if not repo_root.exists():
        raise SnapshotError(f"Repo root does not exist: {repo_root}")
    if not (repo_root / ".git").exists():
        raise SnapshotError(f"Repo root is not a Git worktree: {repo_root}")
    return repo_root


def normalize_endpoint_path(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    if "\\" in path or ".." in path:
        raise SnapshotError(f"Unsafe endpoint path rejected: {path!r}")
    return path


def validate_chunk_id(chunk_id: str) -> str:
    if not CHUNK_ID_RE.fullmatch(chunk_id):
        raise SnapshotError(f"Unsafe chunk id rejected: {chunk_id!r}")
    if any(part in chunk_id for part in ("..", ":", "/", "\\")):
        raise SnapshotError(f"Path-like chunk id rejected: {chunk_id!r}")
    return chunk_id


def validate_branch_name(branch: str) -> str:
    if not BRANCH_RE.fullmatch(branch):
        raise SnapshotError(f"Unsafe snapshot branch rejected: {branch!r}")
    if branch.startswith(("/", ".")) or branch.endswith(("/", ".")):
        raise SnapshotError(f"Unsafe snapshot branch rejected: {branch!r}")
    if ".." in branch or "//" in branch or "@{" in branch or "\\" in branch:
        raise SnapshotError(f"Unsafe snapshot branch rejected: {branch!r}")
    return branch


def token_from_url(url: str) -> tuple[str, str | None]:
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise SnapshotError(f"Unsupported URL scheme for bridge URL: {parsed.scheme!r}")
    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if not parts:
        raise SnapshotError("Bridge URL did not contain a token path segment.")
    token = parts[0]
    if not re.fullmatch(r"[A-Za-z0-9._~-]{12,256}", token):
        raise SnapshotError("Bridge token path segment is malformed or too short.")
    public_base = f"{parsed.scheme}://{parsed.netloc}/{token}"
    return token, public_base


def discover_source(args: argparse.Namespace, repo_root: Path) -> BridgeSource:
    token = args.token
    public_url = None

    source_url = args.url or os.environ.get("RIFTREADER_BRIDGE_URL")
    if source_url:
        token, public_url = token_from_url(source_url)

    if not token:
        url_file = repo_root / args.url_file
        deadline = time.monotonic() + max(0, args.wait_url_file_seconds)
        while True:
            text = safe_read_text(url_file)
            if text:
                token, public_url = token_from_url(text.splitlines()[0].strip())
                break
            if args.wait_url_file_seconds <= 0 or time.monotonic() >= deadline:
                break
            time.sleep(0.5)

    if not token:
        raise SnapshotError(
            "No bridge token found. Provide --url, --token, RIFTREADER_BRIDGE_URL, "
            f"or create {args.url_file} by running the bridge/tunnel session."
        )

    return BridgeSource(host=args.host, port=args.port, token=token, public_url=public_url)


def redact_text(text: str, source: BridgeSource) -> str:
    redacted = text.replace(source.token, "<redacted-token>")
    if source.public_url:
        redacted = redacted.replace(source.public_url, "https://<trycloudflare-url>/<redacted-token>")
    redacted = TRYCLOUDFLARE_RE.sub("https://<trycloudflare-url>/<redacted-token>", redacted)
    return redacted


def fetch_bridge_text(source: BridgeSource, endpoint_path: str, timeout: float) -> str:
    endpoint_path = normalize_endpoint_path(endpoint_path)
    url = f"{source.local_base}{endpoint_path}"
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": VERSION})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise SnapshotError(f"HTTP {exc.code} while fetching {endpoint_path}: {body[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise SnapshotError(f"Failed to fetch {endpoint_path}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise SnapshotError(f"Timed out while fetching {endpoint_path}") from exc
    return raw.decode("utf-8", errors="replace")


def capture_endpoint(source: BridgeSource, name: str, endpoint_path: str, timeout: float) -> EndpointCapture:
    try:
        text = fetch_bridge_text(source, endpoint_path, timeout)
        text = redact_text(text, source)
        return EndpointCapture(
            name=name,
            path=endpoint_path,
            status="ok",
            sha256=sha256_text(text),
            size_bytes=len(text.encode("utf-8")),
            content=text,
        )
    except SnapshotError as exc:
        return EndpointCapture(
            name=name,
            path=endpoint_path,
            status="error",
            sha256=None,
            size_bytes=0,
            content="",
            error=str(exc),
        )


def parse_json_capture(capture: EndpointCapture) -> Any:
    if capture.status != "ok":
        raise SnapshotError(f"Required endpoint failed: {capture.name}: {capture.error}")
    try:
        return json.loads(capture.content)
    except json.JSONDecodeError as exc:
        raise SnapshotError(f"Endpoint {capture.name} did not return valid JSON: {exc}") from exc


def select_chunk_ids(chunks_json: dict[str, Any], requested: Sequence[str], include_repo_readme: bool) -> list[str]:
    chunks = chunks_json.get("chunks")
    if not isinstance(chunks, list):
        raise SnapshotError("chunks.json is missing a chunks array.")
    available = {str(item.get("chunkId")): item for item in chunks if isinstance(item, dict) and item.get("chunkId")}
    selected: list[str] = []
    desired: list[str] = list(DEFAULT_CHUNKS)
    if include_repo_readme:
        desired.append("repo-readme")
    desired.extend(requested)
    for chunk_id in desired:
        chunk_id = validate_chunk_id(chunk_id)
        if chunk_id in available and chunk_id not in selected:
            selected.append(chunk_id)
    if not selected:
        raise SnapshotError("No requested/default chunks were available in chunks.json.")
    return selected


def capture_snapshot(source: BridgeSource, requested_chunks: Sequence[str], include_repo_readme: bool, timeout: float) -> dict[str, Any]:
    captures: dict[str, EndpointCapture] = {}
    for name, path in ENDPOINTS_FIXED:
        captures[name] = capture_endpoint(source, name, path, timeout)

    chunks_json = parse_json_capture(captures["chunks"])
    selected_ids = select_chunk_ids(chunks_json, requested_chunks, include_repo_readme)

    chunk_captures: dict[str, EndpointCapture] = {}
    for chunk_id in selected_ids:
        endpoint = f"/payloads/latest/chunks/{chunk_id}"
        chunk_captures[chunk_id] = capture_endpoint(source, f"chunk:{chunk_id}", endpoint, timeout)
        if chunk_captures[chunk_id].status != "ok":
            raise SnapshotError(f"Required chunk failed: {chunk_id}: {chunk_captures[chunk_id].error}")

    handoff = parse_json_capture(captures["chatgpt_handoff"])
    health = parse_json_capture(captures["health"])

    return {
        "schemaVersion": 1,
        "kind": "riftreader-chatgpt-bridge-snapshot",
        "tool": VERSION,
        "generatedAtUtc": utc_now(),
        "source": {
            "mode": "localhost-bridge-capture",
            "localBaseRedacted": source.redacted_local_base,
            "publicUrlRedacted": "https://<trycloudflare-url>/<redacted-token>" if source.public_url else None,
        },
        "handoffSummary": {
            "ok": handoff.get("ok"),
            "status": handoff.get("status"),
            "tool": handoff.get("tool"),
            "latestPayloadId": handoff.get("latestPayloadId"),
            "payloadCount": handoff.get("payloadCount"),
            "recommendedReadOrder": handoff.get("recommendedReadOrder", []),
            "warnings": handoff.get("warnings", []),
            "blockers": handoff.get("blockers", []),
        },
        "healthSummary": {
            "ok": health.get("ok"),
            "status": health.get("status"),
            "version": health.get("version") or health.get("tool"),
            "mode": health.get("mode"),
            "latestPayloadId": health.get("latestPayloadId"),
            "payloadCount": health.get("payloadCount"),
            "warnings": health.get("warnings", []),
            "blockers": health.get("blockers", []),
        },
        "endpoints": {name: cap.to_json() for name, cap in captures.items()},
        "selectedChunkIds": selected_ids,
        "chunks": {chunk_id: cap.to_json() for chunk_id, cap in chunk_captures.items()},
    }


def fence_for_kind(name: str) -> str:
    if name.endswith(".json") or name == "repo-status":
        return "json"
    return "markdown"


def render_markdown(snapshot: dict[str, Any]) -> str:
    handoff = snapshot["handoffSummary"]
    health = snapshot["healthSummary"]
    lines: list[str] = []
    lines.append("# RiftReader ChatGPT Bridge Snapshot")
    lines.append("")
    lines.append(f"Generated UTC: `{snapshot['generatedAtUtc']}`")
    lines.append(f"Tool: `{snapshot['tool']}`")
    lines.append("")
    lines.append("## Status")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| Handoff OK | `{handoff.get('ok')}` |")
    lines.append(f"| Handoff status | `{handoff.get('status')}` |")
    lines.append(f"| Health OK | `{health.get('ok')}` |")
    lines.append(f"| Latest payload | `{handoff.get('latestPayloadId') or health.get('latestPayloadId')}` |")
    lines.append(f"| Payload count | `{handoff.get('payloadCount') or health.get('payloadCount')}` |")
    lines.append(f"| Selected chunks | `{', '.join(snapshot['selectedChunkIds'])}` |")
    lines.append("")
    lines.append("## Endpoint capture")
    lines.append("")
    lines.append("| Endpoint | Status | Bytes | SHA256 |")
    lines.append("|---|---:|---:|---|")
    for cap in snapshot["endpoints"].values():
        lines.append(f"| `{cap['path']}` | `{cap['status']}` | `{cap['size_bytes']}` | `{cap.get('sha256') or ''}` |")
    for cap in snapshot["chunks"].values():
        lines.append(f"| `{cap['path']}` | `{cap['status']}` | `{cap['size_bytes']}` | `{cap.get('sha256') or ''}` |")
    lines.append("")
    lines.append("## Latest payload README")
    lines.append("")
    lines.append("```markdown")
    lines.append(snapshot["endpoints"]["readme"]["content"].rstrip())
    lines.append("```")
    lines.append("")
    lines.append("## chunks.json")
    lines.append("")
    lines.append("```json")
    lines.append(snapshot["endpoints"]["chunks"]["content"].rstrip())
    lines.append("```")
    for chunk_id in snapshot["selectedChunkIds"]:
        cap = snapshot["chunks"][chunk_id]
        lines.append("")
        lines.append(f"## Chunk: `{chunk_id}`")
        lines.append("")
        lines.append(f"Source endpoint: `{cap['path']}`")
        lines.append("")
        lines.append(f"```{fence_for_kind(chunk_id)}")
        lines.append(cap["content"].rstrip())
        lines.append("```")
    lines.append("")
    lines.append("<!-- END_OF_SCRIPT_MARKER -->")
    return "\n".join(lines) + "\n"


def enforce_size(markdown_text: str, json_text: str, max_kb: int) -> None:
    total = len(markdown_text.encode("utf-8")) + len(json_text.encode("utf-8"))
    limit = max_kb * 1024
    if total > limit:
        raise SnapshotError(f"Snapshot too large: {total} bytes > {limit} bytes. Increase --max-kb or reduce selected chunks.")


def write_snapshot_files(repo_root: Path, snapshot: dict[str, Any], max_kb: int) -> dict[str, Any]:
    md_rel = DEFAULT_SNAPSHOT_MD
    json_rel = DEFAULT_SNAPSHOT_JSON
    md_text = render_markdown(snapshot)
    json_text = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"
    enforce_size(md_text, json_text, max_kb)
    for rel, text in ((md_rel, md_text), (json_rel, json_text)):
        target = repo_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    return {
        "markdownPath": md_rel.as_posix(),
        "jsonPath": json_rel.as_posix(),
        "markdownBytes": len(md_text.encode("utf-8")),
        "jsonBytes": len(json_text.encode("utf-8")),
        "markdownSha256": sha256_text(md_text),
        "jsonSha256": sha256_text(json_text),
    }


def run_git(repo_root: Path, args: Sequence[str], *, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if check and result.returncode != 0:
        raise SnapshotError(
            "git command failed: "
            + json.dumps(
                {
                    "args": ["git", *args],
                    "returncode": result.returncode,
                    "stdoutTail": result.stdout[-4000:],
                    "stderrTail": result.stderr[-4000:],
                },
                indent=2,
            )
        )
    return result


def publish_snapshot_branch(repo_root: Path, snapshot: dict[str, Any], branch: str, max_kb: int) -> dict[str, Any]:
    branch = validate_branch_name(branch)
    head = run_git(repo_root, ["rev-parse", "HEAD"]).stdout.strip()
    origin_url = run_git(repo_root, ["remote", "get-url", "origin"]).stdout.strip()
    temp_parent = Path(tempfile.mkdtemp(prefix="riftreader-snapshot-worktree-"))
    worktree = temp_parent / "worktree"
    expected = sorted([DEFAULT_SNAPSHOT_MD.as_posix(), DEFAULT_SNAPSHOT_JSON.as_posix()])
    try:
        run_git(repo_root, ["worktree", "add", "--detach", str(worktree), head], timeout=180)
        run_git(worktree, ["checkout", "-B", branch], timeout=120)
        file_summary = write_snapshot_files(worktree, snapshot, max_kb)
        run_git(worktree, ["add", "--", *expected], timeout=120)
        staged = sorted(run_git(worktree, ["diff", "--cached", "--name-only"]).stdout.splitlines())
        if staged != expected:
            raise SnapshotError(f"Staged path mismatch. Expected {expected}; got {staged}")
        changed = run_git(worktree, ["diff", "--cached", "--quiet"], check=False)
        committed = False
        if changed.returncode == 1:
            run_git(worktree, ["commit", "-m", "Publish ChatGPT bridge snapshot"], timeout=180)
            committed = True
        elif changed.returncode != 0:
            raise SnapshotError(f"git diff --cached --quiet failed: {changed.stderr}")
        commit_sha = run_git(worktree, ["rev-parse", "HEAD"]).stdout.strip()
        run_git(worktree, ["push", "--force-with-lease", "origin", f"HEAD:refs/heads/{branch}"], timeout=240)
        return {
            "branch": branch,
            "commitSha": commit_sha,
            "baseHead": head,
            "originUrl": origin_url,
            "committed": committed,
            "pushed": True,
            "files": file_summary,
        }
    finally:
        with contextlib.suppress(Exception):
            run_git(repo_root, ["worktree", "remove", "--force", str(worktree)], timeout=120, check=False)
        shutil.rmtree(temp_parent, ignore_errors=True)


def status_line(label: str, value: str) -> None:
    print(f"{label:<28} {value}", flush=True)


def run_capture(args: argparse.Namespace) -> int:
    repo_root = ensure_repo_root(Path(args.repo))
    source = discover_source(args, repo_root)
    snapshot = capture_snapshot(source, args.chunk, args.include_repo_readme, args.timeout)
    result: dict[str, Any] = {
        "ok": True,
        "version": VERSION,
        "generatedAtUtc": snapshot["generatedAtUtc"],
        "selectedChunkIds": snapshot["selectedChunkIds"],
        "source": snapshot["source"],
    }
    if args.write:
        result["write"] = write_snapshot_files(repo_root, snapshot, args.max_kb)
    if args.push:
        result["push"] = publish_snapshot_branch(repo_root, snapshot, args.snapshot_branch, args.max_kb)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Version: {VERSION}")
        status_line("Repo", str(repo_root))
        status_line("Bridge source", source.redacted_local_base)
        status_line("Selected chunks", ", ".join(snapshot["selectedChunkIds"]))
        if "write" in result:
            status_line("Snapshot markdown", result["write"]["markdownPath"])
            status_line("Snapshot json", result["write"]["jsonPath"])
        if "push" in result:
            status_line("Snapshot branch", result["push"]["branch"])
            status_line("Snapshot commit", result["push"]["commitSha"])
            status_line("Pushed", str(result["push"]["pushed"]))
        print("DONE: ChatGPT bridge snapshot capture complete.")
    return 0


class _FakeBridgeHandler(http.server.BaseHTTPRequestHandler):
    token = "0123456789abcdef0123456789abcdef"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send(self, status: int, body: str, content_type: str = "text/plain; charset=utf-8") -> None:
        raw = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        prefix = f"/{self.token}"
        if not self.path.startswith(prefix):
            self._send(403, '{"ok": false, "error": "bad token"}', "application/json")
            return
        path = self.path[len(prefix):] or "/"
        chunks = {
            "chunks": [
                {"chunkId": "desktop-chatgpt-workflow", "path": "chunks/workflow.md", "kind": "markdown", "sizeBytes": 12},
                {"chunkId": "local-artifact-bridge-docs", "path": "chunks/bridge.md", "kind": "markdown", "sizeBytes": 12},
                {"chunkId": "repo-status", "path": "chunks/repo-status.json", "kind": "json", "sizeBytes": 12},
            ],
            "payloadId": "fake-payload",
            "schemaVersion": 1,
        }
        if path == "/chatgpt-handoff.json":
            self._send(200, json.dumps({"ok": True, "status": "ready", "tool": "fake", "latestPayloadId": "fake-payload", "payloadCount": 1}), "application/json")
        elif path == "/health":
            self._send(200, json.dumps({"ok": True, "status": "ready", "version": "fake", "latestPayloadId": "fake-payload", "payloadCount": 1}), "application/json")
        elif path == "/payloads/latest/readme.md":
            self._send(200, "# Fake README\n\nToken 0123456789abcdef0123456789abcdef should be redacted.\n", "text/markdown")
        elif path == "/payloads/latest/chunks.json":
            self._send(200, json.dumps(chunks, indent=2), "application/json")
        elif path == "/payloads/latest/chunks/desktop-chatgpt-workflow":
            self._send(200, "# Workflow\n\nLocal Python helpers.\n", "text/markdown")
        elif path == "/payloads/latest/chunks/local-artifact-bridge-docs":
            self._send(200, "# Bridge Docs\n\nRead-only artifact bridge.\n", "text/markdown")
        elif path == "/payloads/latest/chunks/repo-status":
            self._send(200, '{"branch": "main", "dirtyPaths": []}\n', "application/json")
        else:
            self._send(404, '{"ok": false, "error": "not found"}', "application/json")


def run_self_test() -> int:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _FakeBridgeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with tempfile.TemporaryDirectory(prefix="riftreader-snapshot-selftest-") as tmp:
        repo = Path(tmp)
        (repo / ".git").mkdir()
        args = argparse.Namespace(
            repo=str(repo),
            token=_FakeBridgeHandler.token,
            url=None,
            url_file=DEFAULT_TOKEN_URL_FILE,
            wait_url_file_seconds=0,
            host="127.0.0.1",
            port=server.server_port,
            timeout=5.0,
            chunk=[],
            include_repo_readme=False,
            write=True,
            push=False,
            snapshot_branch=DEFAULT_SNAPSHOT_BRANCH,
            max_kb=128,
            json=True,
        )
        source = discover_source(args, repo)
        snapshot = capture_snapshot(source, [], False, 5.0)
        summary = write_snapshot_files(repo, snapshot, 128)
        md_text = (repo / DEFAULT_SNAPSHOT_MD).read_text(encoding="utf-8")
        json.loads((repo / DEFAULT_SNAPSHOT_JSON).read_text(encoding="utf-8"))
        assert "0123456789abcdef0123456789abcdef" not in md_text
        assert "<redacted-token>" in md_text
        assert summary["markdownBytes"] > 100
    server.shutdown()
    server.server_close()
    print(json.dumps({"ok": True, "version": VERSION, "selfTest": "passed"}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture RiftReader bridge data into a GitHub-readable ChatGPT snapshot.")
    parser.add_argument("--repo", default=str(DEFAULT_REPO_ROOT), help="RiftReader repo root.")
    parser.add_argument("--url", help="Tokenized bridge URL, public or local. The token is extracted and redacted.")
    parser.add_argument("--token", help="Bridge token. Prefer --url or URL file when available.")
    parser.add_argument("--url-file", type=Path, default=DEFAULT_TOKEN_URL_FILE, help="Repo-relative file containing the tokenized bridge URL.")
    parser.add_argument("--wait-url-file-seconds", type=int, default=0, help="Wait for the URL file to appear before failing.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Local bridge host. Must normally be 127.0.0.1.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Local bridge port.")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP fetch timeout in seconds.")
    parser.add_argument("--chunk", action="append", default=[], help="Additional registered chunk ID to include. May be repeated.")
    parser.add_argument("--include-repo-readme", action="store_true", help="Include repo-readme if present and size budget allows.")
    parser.add_argument("--max-kb", type=int, default=DEFAULT_MAX_KB, help="Maximum combined Markdown+JSON snapshot size in KiB.")
    parser.add_argument("--snapshot-branch", default=DEFAULT_SNAPSHOT_BRANCH, help="Transport branch used only with --push.")
    parser.add_argument("--capture", action="store_true", help="Capture bridge endpoints. Required unless --self-test is used.")
    parser.add_argument("--write", action="store_true", help="Write snapshot files under handoffs/current.")
    parser.add_argument("--push", action="store_true", help="Publish snapshot files to the snapshot branch using a temporary git worktree.")
    parser.add_argument("--json", action="store_true", help="Print clean JSON summary.")
    parser.add_argument("--self-test", action="store_true", help="Run synthetic localhost bridge self-test.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.self_test:
            return run_self_test()
        if not args.capture:
            parser.print_help()
            return 2
        return run_capture(args)
    except SnapshotError as exc:
        if args.json:
            print(json.dumps({"ok": False, "version": VERSION, "error": str(exc)}, indent=2, sort_keys=True))
        else:
            print(f"FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
