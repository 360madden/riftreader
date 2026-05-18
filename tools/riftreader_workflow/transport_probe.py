# Version: riftreader-transport-probe-v0.1.3
# Total-Character-Count: 30666
# Purpose: Python-owned safe transport smoke helper for creating bridge-readable payloads, verifying bridge reads, and validating ChatGPT reply files without adding write endpoints.
"""Safe transport smoke helper for RiftReader Local Artifact Bridge.

This helper intentionally avoids live RIFT access, process memory reads, command
execution endpoints, arbitrary file serving, and HTTP write endpoints. It creates
small synthetic payloads under a configured payload root, verifies that a local
read-only bridge can serve them, and validates a manually supplied ChatGPT reply
JSON file.
"""
from __future__ import annotations

import argparse
import importlib.util
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

VERSION = "riftreader-transport-probe-v0.1.3"
SCHEMA_VERSION = 1
DEFAULT_PAYLOAD_ROOT = Path("artifacts") / "chatgpt-payloads"
REPLY_TRANSPORT = "chatgpt-to-riftreader-smoke-v0"
PING_CHUNK_ID = "transport-ping"
ALLOWED_OUTPUT_ROOTS = (
    Path("artifacts") / "chatgpt-payloads",
    Path(".riftreader-local") / "transport-probe",
)


class TransportProbeError(RuntimeError):
    """Raised when a transport probe validation fails."""


@dataclass(frozen=True)
class PayloadInfo:
    payload_id: str
    payload_dir: Path
    nonce: str
    ping_sha256: str
    manifest_path: Path
    chunk_index_path: Path
    summary_path: Path
    ping_chunk_path: Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")


def json_dumps(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def repo_join(root: Path, relative: Path) -> Path:
    result = root
    for part in relative.parts:
        if part in ("", "."):
            continue
        result = result / part
    return result


def normalize_relative(value: str) -> Path:
    if not value or not value.strip():
        raise TransportProbeError("relative path is empty")
    if "\\" in value:
        raise TransportProbeError(f"backslash path is blocked: {value}")
    candidate = Path(value)
    if candidate.is_absolute():
        raise TransportProbeError(f"absolute path is blocked: {value}")
    if any(part == ".." for part in candidate.parts):
        raise TransportProbeError(f"path traversal is blocked: {value}")
    return candidate


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    ensure_directory(path.parent)
    path.write_text(content, encoding="utf-8", newline="\n")


def load_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TransportProbeError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TransportProbeError(f"invalid JSON in {path}: {exc}") from exc


def safe_payload_id(value: Optional[str]) -> str:
    if value is None or not value.strip():
        return f"transport-smoke-{utc_stamp()}"
    value = value.strip()
    if not all(ch.isalnum() or ch in "-_." for ch in value):
        raise TransportProbeError("payload id may only contain letters, digits, dash, underscore, or dot")
    if value in (".", "..") or ".." in value:
        raise TransportProbeError("payload id traversal is blocked")
    return value


def resolve_payload_root(repo_root: Path, payload_root: str | Path) -> Path:
    candidate = Path(payload_root)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def ensure_under(root: Path, child: Path) -> None:
    try:
        child.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise TransportProbeError(f"path escapes root: {child}") from exc


def build_ping_payload(payload_id: str, nonce: str, created_utc: str) -> Dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "tool": VERSION,
        "transport": "riftreader-to-chatgpt-smoke-v0",
        "payloadId": payload_id,
        "createdUtc": created_utc,
        "nonce": nonce,
        "message": "RiftReader transport smoke payload. Echo payloadId, nonce, and observedChunkSha256 in a reply file.",
        "replyContract": {
            "schemaVersion": SCHEMA_VERSION,
            "transport": REPLY_TRANSPORT,
            "payloadId": payload_id,
            "nonce": nonce,
            "observedChunkSha256": "<sha256 of this chunk as served through the bridge>",
        },
    }


def build_reply_template(info: PayloadInfo) -> Dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "transport": REPLY_TRANSPORT,
        "payloadId": info.payload_id,
        "nonce": info.nonce,
        "observedChunkSha256": info.ping_sha256,
        "notes": "Generated locally. ChatGPT should return the same payloadId, nonce, and observedChunkSha256 after reading the bridge-served chunk.",
    }


def create_payload(repo_root: Path, payload_root: Path, payload_id: Optional[str] = None, nonce: Optional[str] = None) -> PayloadInfo:
    payload_id = safe_payload_id(payload_id)
    nonce = nonce or hashlib.sha256(f"{payload_id}:{time.time_ns()}".encode("utf-8")).hexdigest()[:24]
    created_utc = utc_now_iso()
    payload_dir = payload_root / payload_id
    ensure_under(payload_root, payload_dir)
    ensure_directory(payload_dir)

    ping_rel = normalize_relative("chunks/transport-ping.json")
    summary_rel = normalize_relative("README.md")
    manifest_rel = normalize_relative("manifest.json")
    chunk_index_rel = normalize_relative("chunk-index.json")

    ping_data = build_ping_payload(payload_id, nonce, created_utc)
    ping_text = json_dumps(ping_data)
    ping_bytes = ping_text.encode("utf-8")
    ping_sha = sha256_bytes(ping_bytes)

    ping_path = payload_dir / ping_rel
    summary_path = payload_dir / summary_rel
    manifest_path = payload_dir / manifest_rel
    chunk_index_path = payload_dir / chunk_index_rel

    write_text(ping_path, ping_text)

    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "payloadId": payload_id,
        "createdUtc": created_utc,
        "tool": VERSION,
        "kind": "transport-smoke-test",
        "description": "Synthetic safe payload for testing RiftReader local artifact transport.",
        "files": [
            {"path": "README.md", "kind": "markdown"},
            {"path": "chunk-index.json", "kind": "json"},
            {"path": "chunks/transport-ping.json", "kind": "json", "sha256": ping_sha, "sizeBytes": len(ping_bytes)},
        ],
        "expectedReply": build_reply_template(PayloadInfo(payload_id, payload_dir, nonce, ping_sha, manifest_path, chunk_index_path, summary_path, ping_path)),
    }
    write_text(manifest_path, json_dumps(manifest))

    chunk_index = {
        "schemaVersion": SCHEMA_VERSION,
        "payloadId": payload_id,
        "createdUtc": created_utc,
        "chunks": [
            {
                "chunkId": PING_CHUNK_ID,
                "path": "chunks/transport-ping.json",
                "kind": "json",
                "sizeBytes": len(ping_bytes),
                "sha256": ping_sha,
                "description": "Transport smoke ping chunk for bridge readback and ChatGPT reply verification.",
            }
        ],
    }
    write_text(chunk_index_path, json_dumps(chunk_index))

    summary = (
        f"# RiftReader Transport Smoke Payload\n\n"
        f"Payload ID: `{payload_id}`\n\n"
        f"Nonce: `{nonce}`\n\n"
        f"Ping chunk SHA-256: `{ping_sha}`\n\n"
        f"Use the Local Artifact Bridge to read `/payloads/latest/chunks/{PING_CHUNK_ID}`, "
        f"then return a reply JSON matching `expectedReply` in `manifest.json`.\n\n"
        f"# END_OF_DOCUMENT\n"
    )
    write_text(summary_path, summary)

    return PayloadInfo(payload_id, payload_dir, nonce, ping_sha, manifest_path, chunk_index_path, summary_path, ping_path)


def find_payload_dir(payload_root: Path, payload_id: str) -> Path:
    if payload_id == "latest":
        candidates = [p for p in payload_root.iterdir() if p.is_dir() and (p / "manifest.json").is_file() and (p / "chunk-index.json").is_file()]
        if not candidates:
            raise TransportProbeError(f"no payloads found under {payload_root}")
        candidates.sort(key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)
        return candidates[0]
    safe = safe_payload_id(payload_id)
    return payload_root / safe


def load_payload_info(payload_root: Path, payload_id: str = "latest") -> PayloadInfo:
    payload_dir = find_payload_dir(payload_root, payload_id)
    manifest_path = payload_dir / "manifest.json"
    chunk_index_path = payload_dir / "chunk-index.json"
    summary_path = payload_dir / "README.md"
    manifest = load_json_file(manifest_path)
    chunk_index = load_json_file(chunk_index_path)
    chunks = chunk_index.get("chunks") or []
    ping_chunks = [chunk for chunk in chunks if chunk.get("chunkId") == PING_CHUNK_ID]
    if len(ping_chunks) != 1:
        raise TransportProbeError(f"expected exactly one {PING_CHUNK_ID} chunk in {chunk_index_path}")
    ping_rel = normalize_relative(str(ping_chunks[0].get("path") or ""))
    ping_path = payload_dir / ping_rel
    ensure_under(payload_dir, ping_path)
    ping = load_json_file(ping_path)
    nonce = str(ping.get("nonce") or "")
    if not nonce:
        raise TransportProbeError("ping chunk is missing nonce")
    payload_name = str(manifest.get("payloadId") or payload_dir.name)
    expected_sha = str(ping_chunks[0].get("sha256") or "")
    actual_sha = sha256_file(ping_path)
    if expected_sha and expected_sha != actual_sha:
        raise TransportProbeError(f"local ping chunk SHA mismatch: expected {expected_sha}, actual {actual_sha}")
    return PayloadInfo(payload_name, payload_dir, nonce, actual_sha, manifest_path, chunk_index_path, summary_path, ping_path)


def verify_reply(payload_root: Path, reply_file: Path, payload_id: str = "latest") -> Dict[str, Any]:
    info = load_payload_info(payload_root, payload_id)
    reply = load_json_file(reply_file)
    errors: List[str] = []
    if reply.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("schemaVersion mismatch")
    if reply.get("transport") != REPLY_TRANSPORT:
        errors.append("transport mismatch")
    if reply.get("payloadId") != info.payload_id:
        errors.append("payloadId mismatch")
    if reply.get("nonce") != info.nonce:
        errors.append("nonce mismatch")
    if reply.get("observedChunkSha256") != info.ping_sha256:
        errors.append("observedChunkSha256 mismatch")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "tool": VERSION,
        "ok": not errors,
        "errors": errors,
        "payloadId": info.payload_id,
        "replyFile": str(reply_file),
        "expected": build_reply_template(info),
    }


def http_get_json_or_text(url: str, expect_json: bool) -> Any:
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": VERSION})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        raise TransportProbeError(f"HTTP {exc.code} from {url}") from exc
    except urllib.error.URLError as exc:
        raise TransportProbeError(f"URL error from {url}: {exc}") from exc
    if status != 200:
        raise TransportProbeError(f"unexpected HTTP status {status} from {url}")
    text = body.decode("utf-8")
    if expect_json:
        return json.loads(text)
    return text


def make_bridge_url(base_url: str, suffix: str) -> str:
    base = base_url.rstrip("/")
    return base + suffix


def verify_bridge(base_url: str, payload_root: Path, payload_id: str = "latest") -> Dict[str, Any]:
    info = load_payload_info(payload_root, payload_id)
    checks: List[Dict[str, Any]] = []

    endpoints: Sequence[Tuple[str, bool, str]] = (
        ("/health", True, "health"),
        ("/payloads/index.json", True, "index"),
        ("/payloads/latest/manifest.json", True, "manifest"),
        ("/payloads/latest/summary.md", False, "summary"),
        ("/payloads/latest/chunk-index.json", True, "chunk_index"),
        (f"/payloads/latest/chunks/{PING_CHUNK_ID}", True, "ping_chunk"),
    )
    seen: Dict[str, Any] = {}
    for suffix, expect_json, name in endpoints:
        url = make_bridge_url(base_url, suffix)
        value = http_get_json_or_text(url, expect_json=expect_json)
        seen[name] = value
        checks.append({"name": name, "urlSuffix": suffix, "ok": True})

    errors: List[str] = []
    if seen["manifest"].get("payloadId") != info.payload_id:
        errors.append("bridge latest manifest payloadId does not match local latest payload")
    ping_text = json_dumps(seen["ping_chunk"]).encode("utf-8")
    observed_sha = sha256_bytes(ping_text)
    # Compare canonical served JSON hash first; fall back to semantic fields because bridge may preserve file bytes.
    if seen["ping_chunk"].get("payloadId") != info.payload_id:
        errors.append("bridge ping chunk payloadId mismatch")
    if seen["ping_chunk"].get("nonce") != info.nonce:
        errors.append("bridge ping chunk nonce mismatch")
    if sha256_file(info.ping_chunk_path) != info.ping_sha256:
        errors.append("local ping sha changed during bridge verification")

    return {
        "schemaVersion": SCHEMA_VERSION,
        "tool": VERSION,
        "ok": not errors,
        "errors": errors,
        "checks": checks,
        "payloadId": info.payload_id,
        "nonce": info.nonce,
        "expectedReply": build_reply_template(info),
        "note": "observedChunkSha256 in replies must use the local file SHA-256 recorded in chunk-index.json.",
    }


def redact_base_url(base_url: str) -> str:
    """Return a base URL with the token path segment redacted for safe logs."""
    parsed = urllib.parse.urlsplit(base_url.rstrip("/"))
    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        redacted_path = ""
    else:
        redacted_path = "/<token>"
        if len(path_parts) > 1:
            redacted_path += "/" + "/".join(path_parts[1:])
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, redacted_path, "", ""))


def normalize_output_relative(value: str) -> Path:
    normalized = value.replace("\\", "/")
    return normalize_relative(normalized)


def ensure_allowed_output_dir(relative_dir: Path) -> None:
    allowed = False
    for allowed_root in ALLOWED_OUTPUT_ROOTS:
        if relative_dir == allowed_root or relative_dir.is_relative_to(allowed_root):
            allowed = True
            break
    if not allowed:
        allowed_text = ", ".join(str(path).replace("\\", "/") for path in ALLOWED_OUTPUT_ROOTS)
        raise TransportProbeError(f"reply output directory is outside allowed roots: {relative_dir}; allowed: {allowed_text}")


def build_reply_from_expected(expected_reply: Mapping[str, Any], notes: Optional[str] = None) -> Dict[str, Any]:
    required = ("schemaVersion", "transport", "payloadId", "nonce", "observedChunkSha256")
    missing = [name for name in required if name not in expected_reply]
    if missing:
        raise TransportProbeError(f"expectedReply missing required keys: {', '.join(missing)}")
    return {
        "schemaVersion": expected_reply["schemaVersion"],
        "transport": expected_reply["transport"],
        "payloadId": expected_reply["payloadId"],
        "nonce": expected_reply["nonce"],
        "observedChunkSha256": expected_reply["observedChunkSha256"],
        "notes": notes or "Automated local reply generated from bridge-served expectedReply and validated by RiftReader transport_probe.",
    }


def write_automated_reply(repo_root: Path, reply: Mapping[str, Any], reply_dir: str) -> Path:
    payload_id = safe_payload_id(str(reply.get("payloadId") or ""))
    relative_dir = normalize_output_relative(reply_dir)
    ensure_allowed_output_dir(relative_dir)
    output_dir = repo_join(repo_root, relative_dir)
    ensure_under(repo_root, output_dir)
    ensure_directory(output_dir)
    reply_path = output_dir / f"chatgpt-reply-{payload_id}.json"
    write_text(reply_path, json_dumps(dict(reply)))
    return reply_path


def run_bridge_roundtrip(
    base_url: str,
    repo_root: Path,
    payload_root: Path,
    payload_id: str = "latest",
    reply_dir: str = ".riftreader-local/transport-probe/replies",
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    bridge_result = verify_bridge(base_url, payload_root, payload_id)
    checks: List[Dict[str, Any]] = [
        {"name": "verify_bridge", "pass": bool(bridge_result.get("ok"))},
    ]
    if not bridge_result.get("ok"):
        return {
            "schemaVersion": SCHEMA_VERSION,
            "tool": VERSION,
            "command": "bridge-roundtrip",
            "ok": False,
            "baseUrlRedacted": redact_base_url(base_url),
            "payloadId": bridge_result.get("payloadId"),
            "checks": checks,
            "errors": list(bridge_result.get("errors") or []),
            "bridgeVerify": bridge_result,
        }

    reply = build_reply_from_expected(bridge_result["expectedReply"], notes=notes)
    reply_file = write_automated_reply(repo_root, reply, reply_dir)
    checks.append({"name": "write_reply", "pass": reply_file.is_file()})
    reply_validation = verify_reply(payload_root, reply_file, str(bridge_result["payloadId"]))
    checks.append({"name": "verify_reply", "pass": bool(reply_validation.get("ok"))})
    errors = list(reply_validation.get("errors") or [])
    ok = all(item["pass"] for item in checks) and not errors
    return {
        "schemaVersion": SCHEMA_VERSION,
        "tool": VERSION,
        "command": "bridge-roundtrip",
        "ok": ok,
        "baseUrlRedacted": redact_base_url(base_url),
        "payloadId": bridge_result["payloadId"],
        "nonce": bridge_result["nonce"],
        "replyFile": str(reply_file),
        "reply": reply,
        "replyValidation": reply_validation,
        "bridgeVerify": bridge_result,
        "checkCount": len(checks),
        "checks": checks,
        "errors": errors,
    }


def load_local_bridge_module(repo_root: Path) -> Any:
    bridge_path = repo_root / "tools" / "riftreader_workflow" / "local_artifact_bridge.py"
    if not bridge_path.is_file():
        raise TransportProbeError(f"Local Artifact Bridge helper not found: {bridge_path}")
    spec = importlib.util.spec_from_file_location("riftreader_local_artifact_bridge_probe", bridge_path)
    if spec is None or spec.loader is None:
        raise TransportProbeError(f"could not load Local Artifact Bridge module: {bridge_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["riftreader_local_artifact_bridge_probe"] = module
    spec.loader.exec_module(module)
    return module


def run_local_bridge_smoke(
    repo_root: Path,
    payload_root: Path,
    payload_id: Optional[str] = None,
    nonce: Optional[str] = None,
    token: str = "transport-smoke-token",
    max_response_mb: int = 25,
) -> Dict[str, Any]:
    if max_response_mb <= 0:
        raise TransportProbeError("max-response-mb must be positive")
    info = create_payload(repo_root, payload_root, payload_id=payload_id, nonce=nonce)
    bridge = load_local_bridge_module(repo_root)
    config = bridge.make_config(
        repo_root=repo_root,
        payload_root=payload_root,
        token=token,
        bind_host="127.0.0.1",
        port=0,
        max_response_bytes=max_response_mb * 1024 * 1024,
        log_requests=False,
    )
    server = bridge.create_http_server(config)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base_url = f"http://{host}:{port}/{config.token}"
    try:
        last_error = None
        for _ in range(50):
            try:
                http_get_json_or_text(make_bridge_url(base_url, "/health"), expect_json=True)
                last_error = None
                break
            except TransportProbeError as exc:
                last_error = exc
                time.sleep(0.05)
        if last_error is not None:
            raise TransportProbeError(f"local bridge did not become ready: {last_error}")
        verify = verify_bridge(base_url, payload_root, info.payload_id)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    checks = [
        {"name": "create_payload", "pass": info.manifest_path.is_file() and info.chunk_index_path.is_file()},
        {"name": "start_local_bridge", "pass": True},
        {"name": "verify_bridge", "pass": bool(verify.get("ok"))},
        {"name": "stop_local_bridge", "pass": not thread.is_alive()},
    ]
    errors = list(verify.get("errors") or [])
    if thread.is_alive():
        errors.append("bridge thread did not stop within timeout")
    ok = all(item["pass"] for item in checks) and not errors
    return {
        "schemaVersion": SCHEMA_VERSION,
        "tool": VERSION,
        "ok": ok,
        "errors": errors,
        "checkCount": len(checks),
        "checks": checks,
        "payloadId": info.payload_id,
        "nonce": info.nonce,
        "baseUrlRedacted": f"http://{host}:{port}/<token>",
        "expectedReply": build_reply_template(info),
        "bridgeVerify": verify,
    }



def command_bridge_roundtrip(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    payload_root = resolve_payload_root(repo_root, args.payload_root)
    result = run_bridge_roundtrip(
        base_url=args.base_url,
        repo_root=repo_root,
        payload_root=payload_root,
        payload_id=args.payload_id,
        reply_dir=args.reply_dir,
        notes=args.notes,
    )
    emit(result, args.json)
    return 0 if result["ok"] else 2


def command_local_smoke(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    payload_root = resolve_payload_root(repo_root, args.payload_root)
    result = run_local_bridge_smoke(
        repo_root=repo_root,
        payload_root=payload_root,
        payload_id=args.payload_id,
        nonce=args.nonce,
        token=args.token,
        max_response_mb=args.max_response_mb,
    )
    emit(result, args.json)
    return 0 if result["ok"] else 2

def command_create_payload(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    payload_root = resolve_payload_root(repo_root, args.payload_root)
    info = create_payload(repo_root, payload_root, args.payload_id, args.nonce)
    result = {
        "schemaVersion": SCHEMA_VERSION,
        "tool": VERSION,
        "ok": True,
        "payloadId": info.payload_id,
        "payloadDir": str(info.payload_dir),
        "nonce": info.nonce,
        "pingChunkSha256": info.ping_sha256,
        "manifest": str(info.manifest_path),
        "chunkIndex": str(info.chunk_index_path),
        "summary": str(info.summary_path),
        "pingChunk": str(info.ping_chunk_path),
        "expectedReply": build_reply_template(info),
    }
    emit(result, args.json)
    return 0


def command_reply_template(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    payload_root = resolve_payload_root(repo_root, args.payload_root)
    info = load_payload_info(payload_root, args.payload_id)
    emit(build_reply_template(info), args.json)
    return 0


def command_verify_reply(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    payload_root = resolve_payload_root(repo_root, args.payload_root)
    result = verify_reply(payload_root, Path(args.reply_file), args.payload_id)
    emit(result, args.json)
    return 0 if result["ok"] else 2


def command_verify_bridge(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    payload_root = resolve_payload_root(repo_root, args.payload_root)
    result = verify_bridge(args.base_url, payload_root, args.payload_id)
    emit(result, args.json)
    return 0 if result["ok"] else 2


def command_self_test(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="riftreader-transport-probe-") as temp_root:
        repo_root = Path(temp_root)
        payload_root = repo_root / "artifacts" / "chatgpt-payloads"
        info = create_payload(repo_root, payload_root, payload_id="transport-smoke-self-test", nonce="selftestnonce123")
        reply_path = repo_root / "reply-good.json"
        write_text(reply_path, json_dumps(build_reply_template(info)))
        good = verify_reply(payload_root, reply_path, "latest")
        bad_path = repo_root / "reply-bad.json"
        bad = build_reply_template(info)
        bad["nonce"] = "wrong"
        write_text(bad_path, json_dumps(bad))
        bad_result = verify_reply(payload_root, bad_path, info.payload_id)
        auto_reply = build_reply_from_expected(build_reply_template(info), notes="self-test automated reply")
        auto_reply_path = write_automated_reply(repo_root, auto_reply, ".riftreader-local/transport-probe/replies")
        auto_validation = verify_reply(payload_root, auto_reply_path, info.payload_id)
        checks = [
            {"name": "create_payload", "pass": info.manifest_path.is_file() and info.chunk_index_path.is_file() and info.ping_chunk_path.is_file()},
            {"name": "reply_good", "pass": good["ok"]},
            {"name": "reply_bad_rejected", "pass": not bad_result["ok"] and "nonce mismatch" in bad_result["errors"]},
            {"name": "reply_template", "pass": build_reply_template(info)["observedChunkSha256"] == info.ping_sha256},
            {"name": "automated_reply", "pass": auto_reply_path.is_file() and auto_validation["ok"]},
        ]
        result = {"schemaVersion": SCHEMA_VERSION, "tool": VERSION, "selfTest": True, "ok": all(c["pass"] for c in checks), "checkCount": len(checks), "checks": checks}
        emit(result, args.json)
        return 0 if result["ok"] else 2


def emit(data: Any, as_json: bool) -> None:
    if as_json:
        sys.stdout.write(json_dumps(data))
        return
    if isinstance(data, Mapping):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                print(f"{key}: {json.dumps(value, sort_keys=True)}")
            else:
                print(f"{key}: {value}")
    else:
        print(data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe RiftReader transport smoke helper.")
    parser.add_argument("--repo-root", default=".", help="Repo root. Defaults to current directory.")
    parser.add_argument("--payload-root", default=str(DEFAULT_PAYLOAD_ROOT), help="Payload root relative to repo root unless absolute.")
    parser.add_argument("--json", action="store_true", help="Emit clean JSON only.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create-payload", help="Create a small bridge-readable transport smoke payload.")
    p_create.add_argument("--payload-id", default=None)
    p_create.add_argument("--nonce", default=None)
    p_create.set_defaults(func=command_create_payload)

    p_template = sub.add_parser("reply-template", help="Print the expected ChatGPT reply JSON template for a payload.")
    p_template.add_argument("--payload-id", default="latest")
    p_template.set_defaults(func=command_reply_template)

    p_verify_reply = sub.add_parser("verify-reply", help="Validate a ChatGPT reply JSON file against a local payload.")
    p_verify_reply.add_argument("--reply-file", required=True)
    p_verify_reply.add_argument("--payload-id", default="latest")
    p_verify_reply.set_defaults(func=command_verify_reply)

    p_verify_bridge = sub.add_parser("verify-bridge", help="Verify a running Local Artifact Bridge can serve the latest transport payload.")
    p_verify_bridge.add_argument("--base-url", required=True, help="Tokenized bridge base URL, e.g. http://127.0.0.1:8765/<token>")
    p_verify_bridge.add_argument("--payload-id", default="latest")
    p_verify_bridge.set_defaults(func=command_verify_bridge)

    p_round = sub.add_parser("bridge-roundtrip", aliases=["public-roundtrip"], help="Verify a bridge URL, write an automated reply JSON, and validate it locally.")
    p_round.add_argument("--base-url", required=True, help="Tokenized bridge base URL, e.g. https://example.trycloudflare.com/<token>")
    p_round.add_argument("--payload-id", default="latest")
    p_round.add_argument("--reply-dir", default=".riftreader-local/transport-probe/replies")
    p_round.add_argument("--notes", default=None)
    p_round.set_defaults(func=command_bridge_roundtrip)

    p_local = sub.add_parser("local-smoke", help="Create a payload, start the bridge in-process, verify reads, and shut it down.")
    p_local.add_argument("--payload-id", default=None)
    p_local.add_argument("--nonce", default=None)
    p_local.add_argument("--token", default="transport-smoke-token")
    p_local.add_argument("--max-response-mb", type=int, default=25)
    p_local.set_defaults(func=command_local_smoke)

    p_self = sub.add_parser("self-test", help="Run offline synthetic tests without network or live RIFT.")
    p_self.set_defaults(func=command_self_test)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except TransportProbeError as exc:
        if getattr(args, "json", False):
            emit({"schemaVersion": SCHEMA_VERSION, "tool": VERSION, "ok": False, "error": str(exc)}, True)
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
