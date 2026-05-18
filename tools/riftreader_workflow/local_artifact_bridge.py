# Version: riftreader-local-artifact-bridge-v0.2.0
# Total-Character-Count: 38519
# Purpose: Tokenized local bridge for curated read-only RiftReader ChatGPT payloads plus a guarded local inbox for JSON proposals.
from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import hashlib
import http.client
import http.server
import json
import os
import pathlib
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
from typing import Any, Dict, Iterable, List, Optional, Tuple


VERSION = "riftreader-local-artifact-bridge-v0.2.0"
SCHEMA_VERSION = 1
DEFAULT_BIND_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_PAYLOAD_ROOT = pathlib.Path("artifacts") / "chatgpt-payloads"
DEFAULT_INBOX_ROOT = pathlib.Path(".riftreader-local") / "artifact-bridge-inbox"
DEFAULT_MAX_RESPONSE_BYTES = 25 * 1024 * 1024
DEFAULT_MAX_INBOX_BYTES = 1 * 1024 * 1024
DEFAULT_SHA_CHECK_LIMIT_BYTES = 1 * 1024 * 1024
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{8,256}$")
CHUNK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
INBOX_ID_PATTERN = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}(?:-[0-9]+)?$")

ALLOWED_TEXT_EXTENSIONS = {".md", ".json", ".jsonl", ".csv", ".txt"}
BLOCKED_EXTENSIONS = {
    ".bin",
    ".bin.gz",
    ".zip",
    ".7z",
    ".rar",
    ".exe",
    ".dll",
    ".ps1",
    ".cmd",
    ".bat",
}

ENDPOINTS_V1 = [
    "/<token>/",
    "/<token>/health",
    "/<token>/status.json",
    "/<token>/payloads/index.json",
    "/<token>/payloads/latest/manifest.json",
    "/<token>/payloads/latest/summary.md",
    "/<token>/payloads/latest/readme.md",
    "/<token>/payloads/latest/chunk-index.json",
    "/<token>/payloads/latest/chunks.json",
    "/<token>/payloads/latest/chunks/<chunk_id>",
]

INBOX_ENDPOINTS_V1 = [
    "POST /<token>/inbox/messages",
]

ALLOWED_INBOX_KINDS = {
    "artifact-note",
    "chatgpt-data",
    "chatgpt-instructions",
    "chatgpt-message",
    "package-proposal",
}

INBOX_ALLOWED_FIELDS = {
    "schemaVersion",
    "kind",
    "title",
    "body",
    "payload",
    "source",
    "metadata",
}

RECOMMENDED_READ_ORDER_V1 = [
    {
        "step": 1,
        "path": "/<token>/health",
        "why": "Confirm the bridge is reachable, see safety flags, and see the latest payload ID.",
    },
    {
        "step": 2,
        "path": "/<token>/payloads/latest/readme.md",
        "why": "Read the human summary before opening individual chunks.",
    },
    {
        "step": 3,
        "path": "/<token>/payloads/latest/chunks.json",
        "why": "Inspect the registered chunk IDs and descriptions.",
    },
    {
        "step": 4,
        "path": "/<token>/payloads/latest/chunks/<chunk_id>",
        "why": "Fetch only the specific registered chunks needed for the task.",
    },
]

CHATGPT_INSTRUCTIONS_V1 = [
    "Use only the tokenized bridge URLs the operator provides.",
    "Start with /<token>/health, then follow recommendedReadOrder.",
    "Do not request arbitrary local filesystem paths; only listed endpoints and registered chunk IDs are served.",
    "Use GET/HEAD only for artifact reads.",
    "If the operator asks you to send data back, use only JSON POST to /<token>/inbox/messages; it stores a local inbox proposal only.",
    "Never ask for command execution, direct repo writes, live RIFT input, CE, or x64dbg through this bridge.",
]

ERROR_NEXT_HINTS_V1 = {
    "TOKEN_REQUIRED": [
        "Use a URL shaped like /<token>/health or /<token>/.",
        "Ask the operator for the tokenized bridge URL if you only have the host/port.",
    ],
    "INVALID_TOKEN": [
        "Re-copy the exact tokenized URL from the bridge startup output.",
        "Do not guess or modify the token path segment.",
    ],
    "ENDPOINT_NOT_FOUND": [
        "Open /<token>/ to see the landing page.",
        "Open /<token>/health to see the supported endpoint list.",
    ],
    "CHUNK_NOT_FOUND": [
        "Open /<token>/payloads/latest/chunks.json and use a listed chunkId.",
        "Chunk IDs are not file paths.",
    ],
    "METHOD_NOT_ALLOWED": [
        "Use GET or HEAD for artifact read endpoints.",
        "The only POST endpoint is /<token>/inbox/messages with application/json.",
        "The bridge intentionally rejects PUT, PATCH, DELETE, and OPTIONS.",
    ],
    "INBOX_METHOD_NOT_ALLOWED": [
        "Use POST with Content-Type: application/json for /<token>/inbox/messages.",
        "Use --inbox-index --json to inspect stored inbox proposals locally.",
    ],
    "INBOX_CONTENT_TYPE_UNSUPPORTED": [
        "Retry with Content-Type: application/json.",
        "Do not send form data, multipart data, files, or binary payloads to the inbox.",
    ],
    "INBOX_LENGTH_REQUIRED": [
        "Retry with a Content-Length header.",
        "Keep the JSON body under the configured maxInboxBytes limit.",
    ],
    "INBOX_LENGTH_INVALID": [
        "Retry with a valid numeric Content-Length header.",
        "Most standard JSON POST clients set this automatically.",
    ],
    "INBOX_PAYLOAD_TOO_LARGE": [
        "Reduce the JSON body and retry.",
        "For large artifacts, create a curated payload under artifacts/chatgpt-payloads instead of posting to the inbox.",
    ],
    "INVALID_INBOX_JSON": [
        "Send a UTF-8 JSON object.",
        "Include schemaVersion, kind, title, and at least one of body or payload.",
    ],
    "INBOX_SCHEMA_INVALID": [
        "Use schemaVersion 1.",
        "Include kind, title, and at least one of body or payload.",
    ],
    "INBOX_KIND_UNSUPPORTED": [
        "Use one of the advertised acceptedKinds from /<token>/health.",
        "Use chatgpt-message for ordinary notes or package-proposal for package intake suggestions.",
    ],
    "INBOX_UNKNOWN_FIELD": [
        "Remove fields not listed in the Local Inbox v0 schema.",
        "Allowed fields are schemaVersion, kind, title, body, payload, source, and metadata.",
    ],
    "RESPONSE_TOO_LARGE": [
        "Open /<token>/payloads/latest/chunks.json and choose smaller registered chunks.",
        "Ask the operator to create a reduced text payload if the needed artifact is too large.",
    ],
    "BLOCKED_EXTENSION": [
        "Use registered text artifacts only: Markdown, JSON, JSONL, CSV, or TXT.",
        "Ask the operator to reduce binary/generated files into safe text chunks.",
    ],
    "SUMMARY_EXTENSION_BLOCKED": [
        "Ask the operator to provide the latest summary as README.md or reports/reducer-summary.md.",
    ],
}


@dataclasses.dataclass(frozen=True)
class BridgeConfig:
    repo_root: pathlib.Path
    payload_root: pathlib.Path
    inbox_root: pathlib.Path
    token: str
    bind_host: str = DEFAULT_BIND_HOST
    port: int = DEFAULT_PORT
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES
    max_inbox_bytes: int = DEFAULT_MAX_INBOX_BYTES
    sha_check_limit_bytes: int = DEFAULT_SHA_CHECK_LIMIT_BYTES
    log_requests: bool = True


class BridgeError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_repo_root(path: pathlib.Path) -> pathlib.Path:
    return path.expanduser().resolve()


def resolve_under_repo(repo_root: pathlib.Path, supplied: pathlib.Path) -> pathlib.Path:
    candidate = supplied
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    resolved = candidate.expanduser().resolve()
    if not is_relative_to(resolved, repo_root):
        raise BridgeError(400, "PAYLOAD_ROOT_OUTSIDE_REPO", "Payload root must be inside the repo root for v0.2.")
    return resolved


def resolve_inbox_root(repo_root: pathlib.Path) -> pathlib.Path:
    resolved = (repo_root / DEFAULT_INBOX_ROOT).resolve()
    if not is_relative_to(resolved, repo_root):
        raise BridgeError(400, "INBOX_ROOT_OUTSIDE_REPO", "Inbox root must stay inside the repo root.")
    local_root = (repo_root / ".riftreader-local").resolve()
    if not is_relative_to(resolved, local_root):
        raise BridgeError(400, "INBOX_ROOT_NOT_LOCAL", "Inbox root must stay under .riftreader-local.")
    return resolved


def make_config(
    repo_root: pathlib.Path,
    payload_root: pathlib.Path,
    token: str,
    bind_host: str = DEFAULT_BIND_HOST,
    port: int = DEFAULT_PORT,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    max_inbox_bytes: int = DEFAULT_MAX_INBOX_BYTES,
    log_requests: bool = True,
) -> BridgeConfig:
    repo_resolved = normalize_repo_root(repo_root)
    payload_resolved = resolve_under_repo(repo_resolved, payload_root)
    inbox_resolved = resolve_inbox_root(repo_resolved)
    token_value = generate_token() if token == "auto" else token
    validate_token(token_value)
    if bind_host != "127.0.0.1":
        raise BridgeError(400, "UNSAFE_BIND_HOST", "v0.2 only permits binding to 127.0.0.1.")
    if port < 0 or port > 65535:
        raise BridgeError(400, "INVALID_PORT", "Port must be in range 0-65535.")
    if max_response_bytes <= 0:
        raise BridgeError(400, "INVALID_RESPONSE_LIMIT", "Max response bytes must be positive.")
    if max_inbox_bytes <= 0:
        raise BridgeError(400, "INVALID_INBOX_LIMIT", "Max inbox bytes must be positive.")
    return BridgeConfig(
        repo_root=repo_resolved,
        payload_root=payload_resolved,
        inbox_root=inbox_resolved,
        token=token_value,
        bind_host=bind_host,
        port=port,
        max_response_bytes=max_response_bytes,
        max_inbox_bytes=max_inbox_bytes,
        log_requests=log_requests,
    )


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def validate_token(token: str) -> None:
    if not TOKEN_PATTERN.match(token):
        raise BridgeError(400, "INVALID_TOKEN", "Token must be URL-safe and between 8 and 256 characters.")


def is_relative_to(child: pathlib.Path, parent: pathlib.Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def repo_display_path(path: pathlib.Path, repo_root: pathlib.Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return "<outside-repo>"


def json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def inbox_storage_safety(config: BridgeConfig) -> Dict[str, Any]:
    return {
        "artifactReadGetHeadOnly": True,
        "inboxJsonPostOnly": True,
        "inboxRoot": repo_display_path(config.inbox_root, config.repo_root),
        "inboxRootUnderDotRiftReaderLocal": is_relative_to(config.inbox_root, (config.repo_root / ".riftreader-local").resolve()),
        "noCommandExecutionEndpoint": True,
        "noArbitraryFileRead": True,
        "noRepoTargetWrites": True,
        "noApplyExecute": True,
        "noLiveRiftInput": True,
        "noCheatEngine": True,
        "noX64dbg": True,
    }


def validate_inbox_text_field(value: Any, field: str, max_chars: int) -> str:
    if not isinstance(value, str):
        raise BridgeError(400, "INBOX_SCHEMA_INVALID", f"Inbox field {field} must be a string.")
    stripped = value.strip()
    if not stripped:
        raise BridgeError(400, "INBOX_SCHEMA_INVALID", f"Inbox field {field} must not be empty.")
    if len(stripped) > max_chars:
        raise BridgeError(400, "INBOX_SCHEMA_INVALID", f"Inbox field {field} exceeds {max_chars} characters.")
    if "\x00" in stripped:
        raise BridgeError(400, "INBOX_SCHEMA_INVALID", f"Inbox field {field} contains a NUL byte.")
    return stripped


def validate_inbox_message(message: Any) -> Dict[str, Any]:
    if not isinstance(message, dict):
        raise BridgeError(400, "INVALID_INBOX_JSON", "Inbox request body must be a JSON object.")
    unknown = sorted(str(key) for key in message.keys() if key not in INBOX_ALLOWED_FIELDS)
    if unknown:
        raise BridgeError(400, "INBOX_UNKNOWN_FIELD", f"Unsupported inbox fields: {', '.join(unknown)}")
    if message.get("schemaVersion") != SCHEMA_VERSION:
        raise BridgeError(400, "INBOX_SCHEMA_INVALID", "Inbox schemaVersion must be 1.")
    kind = validate_inbox_text_field(message.get("kind"), "kind", 80)
    if kind not in ALLOWED_INBOX_KINDS:
        raise BridgeError(400, "INBOX_KIND_UNSUPPORTED", f"Unsupported inbox kind: {kind}")
    title = validate_inbox_text_field(message.get("title"), "title", 160)
    body_present = "body" in message and message.get("body") is not None
    payload_present = "payload" in message and message.get("payload") is not None
    if not body_present and not payload_present:
        raise BridgeError(400, "INBOX_SCHEMA_INVALID", "Inbox message requires body or payload.")
    normalized: Dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": kind,
        "title": title,
    }
    if body_present:
        normalized["body"] = validate_inbox_text_field(message.get("body"), "body", 250_000)
    if payload_present:
        normalized["payload"] = message.get("payload")
    for optional in ("source", "metadata"):
        if optional in message and message.get(optional) is not None:
            value = message.get(optional)
            if not isinstance(value, dict):
                raise BridgeError(400, "INBOX_SCHEMA_INVALID", f"Inbox field {optional} must be an object when present.")
            normalized[optional] = value
    return normalized


def read_inbox_metadata(path: pathlib.Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        return None
    return None


def find_inbox_duplicate(config: BridgeConfig, sha256: str) -> Optional[Dict[str, Any]]:
    root = config.inbox_root
    if not root.is_dir():
        return None
    for metadata_path in sorted(root.glob("*/metadata.json")):
        metadata = read_inbox_metadata(metadata_path)
        if metadata and metadata.get("sha256") == sha256:
            return metadata
    return None


def inbox_item_dir(config: BridgeConfig, received_at: str, sha256: str) -> Tuple[str, pathlib.Path]:
    timestamp = received_at.replace("-", "").replace(":", "")
    inbox_id = f"{timestamp}-{sha256[:12]}"
    target = config.inbox_root / inbox_id
    counter = 2
    while target.exists():
        candidate_id = f"{inbox_id}-{counter}"
        candidate = config.inbox_root / candidate_id
        if not candidate.exists():
            return candidate_id, candidate
        counter += 1
    return inbox_id, target


def write_inbox_json(path: pathlib.Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def store_inbox_message(config: BridgeConfig, message: Dict[str, Any], raw_size_bytes: int) -> Dict[str, Any]:
    canonical = canonical_json_bytes(message)
    sha256 = hashlib.sha256(canonical).hexdigest()
    duplicate = find_inbox_duplicate(config, sha256)
    if duplicate:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "ok": True,
            "kind": "riftreader-local-inbox-store-result",
            "status": "duplicate",
            "duplicate": True,
            "inboxId": duplicate.get("inboxId"),
            "sha256": sha256,
            "storedUnder": duplicate.get("storedUnder"),
            "files": duplicate.get("files", {}),
            "receivedAtUtc": duplicate.get("receivedAtUtc"),
            "safety": inbox_storage_safety(config),
            "next": [
                "Use --inbox-index --json to review the existing inbox item.",
                "No repo changes were applied; duplicate detection skipped a second write.",
            ],
        }

    received_at = utc_now_iso()
    inbox_id, item_dir = inbox_item_dir(config, received_at, sha256)
    if not INBOX_ID_PATTERN.match(inbox_id):
        raise BridgeError(500, "INBOX_ID_INVALID", "Generated inbox ID failed validation.")
    item_dir.mkdir(parents=True, exist_ok=False)
    relative_dir = repo_display_path(item_dir, config.repo_root)
    message_path = item_dir / "message.json"
    metadata_path = item_dir / "metadata.json"
    stored_message = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-local-inbox-message",
        "inboxId": inbox_id,
        "receivedAtUtc": received_at,
        "message": message,
    }
    metadata = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-local-inbox-metadata",
        "inboxId": inbox_id,
        "messageKind": message["kind"],
        "title": message["title"],
        "receivedAtUtc": received_at,
        "sha256": sha256,
        "rawSizeBytes": raw_size_bytes,
        "canonicalSizeBytes": len(canonical),
        "storedUnder": relative_dir,
        "files": {
            "message": repo_display_path(message_path, config.repo_root),
            "metadata": repo_display_path(metadata_path, config.repo_root),
        },
        "applied": False,
        "executed": False,
        "duplicate": False,
    }
    write_inbox_json(message_path, stored_message)
    write_inbox_json(metadata_path, metadata)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "ok": True,
        "kind": "riftreader-local-inbox-store-result",
        "status": "stored",
        "duplicate": False,
        "inboxId": inbox_id,
        "sha256": sha256,
        "storedUnder": relative_dir,
        "files": metadata["files"],
        "receivedAtUtc": received_at,
        "safety": inbox_storage_safety(config),
        "next": [
            "Use --inbox-index --json to review stored inbox proposals.",
            "Review the saved JSON before converting anything into an explicit package or patch.",
            "No repo changes were applied; v0 only stages the proposal under .riftreader-local.",
        ],
    }


def inbox_index(config: BridgeConfig) -> Dict[str, Any]:
    root = config.inbox_root
    items: List[Dict[str, Any]] = []
    warnings: List[str] = []
    if root.is_dir():
        for metadata_path in sorted(root.glob("*/metadata.json")):
            metadata = read_inbox_metadata(metadata_path)
            if not metadata:
                warnings.append(f"invalid_metadata:{repo_display_path(metadata_path, config.repo_root)}")
                continue
            item = {
                "inboxId": metadata.get("inboxId"),
                "messageKind": metadata.get("messageKind"),
                "title": metadata.get("title"),
                "receivedAtUtc": metadata.get("receivedAtUtc"),
                "sha256": metadata.get("sha256"),
                "storedUnder": metadata.get("storedUnder"),
                "files": metadata.get("files", {}),
                "applied": bool(metadata.get("applied")),
                "executed": bool(metadata.get("executed")),
                "duplicate": bool(metadata.get("duplicate")),
            }
            items.append(item)
    items.sort(key=lambda item: (str(item.get("receivedAtUtc") or ""), str(item.get("inboxId") or "")))
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-local-artifact-bridge-inbox-index",
        "generatedAtUtc": utc_now_iso(),
        "inboxRoot": repo_display_path(root, config.repo_root),
        "exists": root.is_dir(),
        "count": len(items),
        "items": items,
        "warnings": warnings,
        "safety": inbox_storage_safety(config),
        "next": [
            "Review inbox items locally before creating any explicit patch/package.",
            "Local Inbox v0 does not apply, execute, stage, commit, push, or send RIFT input.",
        ],
    }


def safe_read_json(path: pathlib.Path, max_bytes: int = 5 * 1024 * 1024) -> Dict[str, Any]:
    if not path.exists():
        raise BridgeError(404, "MISSING_JSON", f"Required JSON file is missing: {path.name}")
    size = path.stat().st_size
    if size > max_bytes:
        raise BridgeError(413, "JSON_TOO_LARGE", f"JSON file exceeds limit: {path.name}")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise BridgeError(422, "JSON_NOT_OBJECT", f"JSON file must contain an object: {path.name}")
    return data


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_blocked_extension(path_text: str) -> bool:
    lower = path_text.lower()
    return any(lower.endswith(ext) for ext in BLOCKED_EXTENSIONS)


def is_allowed_text_extension(path_text: str) -> bool:
    if is_blocked_extension(path_text):
        return False
    suffix = pathlib.PurePosixPath(path_text).suffix.lower()
    return suffix in ALLOWED_TEXT_EXTENSIONS


def validate_payload_relative_path(path_text: Any) -> pathlib.PurePosixPath:
    if not isinstance(path_text, str) or not path_text.strip():
        raise BridgeError(400, "INVALID_CHUNK_PATH", "Chunk path must be a non-empty string.")
    raw = path_text.strip()
    if "%" in raw:
        raise BridgeError(400, "ENCODED_CHUNK_PATH_REJECTED", "Chunk paths must not be URL-encoded.")
    if "\\" in raw:
        raise BridgeError(400, "BACKSLASH_CHUNK_PATH_REJECTED", "Chunk paths must use forward slashes only.")
    if "\x00" in raw:
        raise BridgeError(400, "NUL_CHUNK_PATH_REJECTED", "Chunk path contains a NUL byte.")
    pure = pathlib.PurePosixPath(raw)
    if pure.is_absolute():
        raise BridgeError(400, "ABSOLUTE_CHUNK_PATH_REJECTED", "Absolute chunk paths are rejected.")
    if any(part in ("", ".", "..") for part in pure.parts):
        raise BridgeError(400, "TRAVERSAL_CHUNK_PATH_REJECTED", "Chunk path traversal is rejected.")
    if not is_allowed_text_extension(raw):
        raise BridgeError(415, "BLOCKED_EXTENSION", "Chunk extension is not allowed for v0.2.")
    return pure


def resolve_payload_file(payload_dir: pathlib.Path, rel_path_text: Any, config: BridgeConfig) -> pathlib.Path:
    pure = validate_payload_relative_path(rel_path_text)
    resolved = (payload_dir / pathlib.Path(*pure.parts)).resolve()
    payload_resolved = payload_dir.resolve()
    if not is_relative_to(resolved, payload_resolved):
        raise BridgeError(400, "CHUNK_ESCAPED_PAYLOAD", "Chunk file escaped the payload folder.")
    if not is_relative_to(resolved, config.payload_root.resolve()):
        raise BridgeError(400, "CHUNK_ESCAPED_ROOT", "Chunk file escaped the payload root.")
    return resolved


def validate_chunk_id(chunk_id: str) -> None:
    if not isinstance(chunk_id, str) or not chunk_id:
        raise BridgeError(400, "INVALID_CHUNK_ID", "Chunk ID is required.")
    if urllib.parse.unquote(chunk_id) != chunk_id:
        raise BridgeError(400, "ENCODED_CHUNK_ID_REJECTED", "Encoded chunk IDs are rejected.")
    if "/" in chunk_id or "\\" in chunk_id or ":" in chunk_id:
        raise BridgeError(400, "PATHLIKE_CHUNK_ID_REJECTED", "Path-like chunk IDs are rejected.")
    if ".." in chunk_id or chunk_id in {".", ".."}:
        raise BridgeError(400, "TRAVERSAL_CHUNK_ID_REJECTED", "Traversal-like chunk IDs are rejected.")
    if not CHUNK_ID_PATTERN.match(chunk_id):
        raise BridgeError(400, "INVALID_CHUNK_ID", "Chunk ID contains unsupported characters.")


def content_type_for_path(path: pathlib.Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "application/json; charset=utf-8"
    if suffix == ".jsonl":
        return "application/x-ndjson; charset=utf-8"
    if suffix == ".csv":
        return "text/csv; charset=utf-8"
    if suffix == ".md":
        return "text/markdown; charset=utf-8"
    return "text/plain; charset=utf-8"


def load_chunk_index(payload_dir: pathlib.Path) -> Dict[str, Any]:
    return safe_read_json(payload_dir / "chunk-index.json")


def chunk_entries(chunk_index: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_chunks = chunk_index.get("chunks", [])
    if not isinstance(raw_chunks, list):
        return []
    return [item for item in raw_chunks if isinstance(item, dict)]


def find_chunk(chunk_index: Dict[str, Any], chunk_id: str) -> Optional[Dict[str, Any]]:
    validate_chunk_id(chunk_id)
    for chunk in chunk_entries(chunk_index):
        if chunk.get("chunkId") == chunk_id:
            return chunk
    return None


def analyze_chunk(payload_dir: pathlib.Path, chunk: Dict[str, Any], config: BridgeConfig) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "chunkId": chunk.get("chunkId"),
        "kind": chunk.get("kind"),
        "description": chunk.get("description"),
        "path": chunk.get("path"),
        "declaredSizeBytes": chunk.get("sizeBytes"),
        "declaredSha256": chunk.get("sha256"),
        "exists": False,
        "safePath": False,
        "allowedTextExtension": False,
        "sizeStatus": "not_checked",
        "sha256Status": "not_checked",
        "serveEligible": False,
    }
    try:
        if isinstance(chunk.get("chunkId"), str):
            validate_chunk_id(chunk["chunkId"])
        path = resolve_payload_file(payload_dir, chunk.get("path"), config)
        result["safePath"] = True
        result["path"] = repo_display_path(path, config.repo_root)
        result["allowedTextExtension"] = True
        if not path.exists() or not path.is_file():
            result["sha256Status"] = "missing"
            result["sizeStatus"] = "missing"
            return result
        result["exists"] = True
        actual_size = path.stat().st_size
        result["actualSizeBytes"] = actual_size
        declared_size = chunk.get("sizeBytes")
        if isinstance(declared_size, int):
            result["sizeStatus"] = "match" if declared_size == actual_size else "mismatch"
        else:
            result["sizeStatus"] = "not_declared"
        declared_sha = chunk.get("sha256")
        if isinstance(declared_sha, str) and declared_sha:
            if actual_size <= config.sha_check_limit_bytes:
                actual_sha = sha256_file(path)
                result["actualSha256"] = actual_sha
                result["sha256Status"] = "match" if declared_sha.lower() == actual_sha.lower() else "mismatch"
            else:
                result["sha256Status"] = "not_checked_size_gt_limit"
        else:
            result["sha256Status"] = "not_declared"
        result["serveEligible"] = actual_size <= config.max_response_bytes
        if actual_size > config.max_response_bytes:
            result["serveBlockReason"] = "oversized"
        return result
    except BridgeError as exc:
        result["blockedCode"] = exc.code
        result["blockedReason"] = exc.message
        if exc.status == 415:
            result["allowedTextExtension"] = False
        result["sha256Status"] = "blocked"
        result["sizeStatus"] = "blocked"
        return result


def payload_summary_candidates(payload_dir: pathlib.Path, repo_root: pathlib.Path) -> List[str]:
    candidates = []
    for rel in ("README.md", "reports/reducer-summary.md"):
        path = (payload_dir / rel).resolve()
        if path.exists() and path.is_file():
            candidates.append(repo_display_path(path, repo_root))
    return candidates


def discover_payloads(config: BridgeConfig) -> Dict[str, Any]:
    root = config.payload_root
    payloads: List[Dict[str, Any]] = []
    warnings: List[str] = []
    if not root.exists():
        return {
            "schemaVersion": SCHEMA_VERSION,
            "payloadRoot": repo_display_path(root, config.repo_root),
            "payloadCount": 0,
            "latestPayloadId": None,
            "latestPayloadPath": None,
            "payloads": [],
            "warnings": ["payload_root_missing"],
        }
    if not root.is_dir():
        raise BridgeError(400, "PAYLOAD_ROOT_NOT_DIRECTORY", "Payload root is not a directory.")
    for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not child.is_dir():
            continue
        manifest_path = child / "manifest.json"
        chunk_index_path = child / "chunk-index.json"
        if not manifest_path.exists() or not chunk_index_path.exists():
            warnings.append(f"skipped_missing_contract:{child.name}")
            continue
        try:
            manifest = safe_read_json(manifest_path)
            chunk_index = safe_read_json(chunk_index_path)
        except BridgeError as exc:
            warnings.append(f"skipped_invalid_payload:{child.name}:{exc.code}")
            continue
        payload_id = str(manifest.get("payloadId") or manifest.get("id") or child.name)
        created_utc = str(manifest.get("createdUtc") or manifest.get("created_utc") or "")
        chunks = chunk_entries(chunk_index)
        analyzed_chunks = [analyze_chunk(child, chunk, config) for chunk in chunks]
        sha_mismatches = [
            chunk.get("chunkId") for chunk in analyzed_chunks if chunk.get("sha256Status") == "mismatch"
        ]
        size_mismatches = [
            chunk.get("chunkId") for chunk in analyzed_chunks if chunk.get("sizeStatus") == "mismatch"
        ]
        payloads.append(
            {
                "payloadId": payload_id,
                "folderName": child.name,
                "path": repo_display_path(child, config.repo_root),
                "createdUtc": created_utc,
                "manifestPath": repo_display_path(manifest_path, config.repo_root),
                "chunkIndexPath": repo_display_path(chunk_index_path, config.repo_root),
                "chunkCount": len(chunks),
                "chunks": analyzed_chunks,
                "summaryCandidates": payload_summary_candidates(child, config.repo_root),
                "sha256Mismatches": sha_mismatches,
                "sizeMismatches": size_mismatches,
                "latestSortKey": [created_utc, child.name],
            }
        )
    payloads.sort(key=lambda item: (item.get("createdUtc") or "", item.get("folderName") or ""))
    latest = payloads[-1] if payloads else None
    return {
        "schemaVersion": SCHEMA_VERSION,
        "payloadRoot": repo_display_path(root, config.repo_root),
        "payloadCount": len(payloads),
        "latestPayloadId": latest.get("payloadId") if latest else None,
        "latestPayloadPath": latest.get("path") if latest else None,
        "payloads": payloads,
        "warnings": warnings,
    }


def latest_payload_dir(config: BridgeConfig) -> pathlib.Path:
    index = discover_payloads(config)
    latest_path = index.get("latestPayloadPath")
    if not latest_path:
        raise BridgeError(404, "NO_PAYLOADS", "No valid payloads found under payload root.")
    candidate = (config.repo_root / latest_path).resolve()
    if not is_relative_to(candidate, config.payload_root):
        raise BridgeError(400, "LATEST_ESCAPED_ROOT", "Latest payload escaped payload root.")
    return candidate


def select_summary_file(payload_dir: pathlib.Path, config: BridgeConfig) -> pathlib.Path:
    for rel in ("README.md", "reports/reducer-summary.md"):
        path = (payload_dir / rel).resolve()
        if path.exists() and path.is_file() and is_relative_to(path, payload_dir.resolve()):
            if not is_allowed_text_extension(rel):
                raise BridgeError(415, "SUMMARY_EXTENSION_BLOCKED", "Summary file extension is blocked.")
            return path
    raise BridgeError(404, "SUMMARY_NOT_FOUND", "No README.md or reports/reducer-summary.md found for latest payload.")


def run_fixed_git(repo_root: pathlib.Path, args: List[str], timeout_seconds: int = 5) -> Tuple[Optional[str], Optional[str]]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            shell=False,
        )
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        return None, completed.stderr.strip() or f"git exited {completed.returncode}"
    return completed.stdout.strip(), None


def safe_repo_status(config: BridgeConfig) -> Dict[str, Any]:
    branch, branch_error = run_fixed_git(config.repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    head, head_error = run_fixed_git(config.repo_root, ["rev-parse", "HEAD"])
    status_text, status_error = run_fixed_git(config.repo_root, ["status", "--porcelain=v1"])
    dirty_paths: List[str] = []
    if status_text:
        for line in status_text.splitlines():
            if len(line) >= 4:
                path_text = line[3:]
                if " -> " in path_text:
                    path_text = path_text.split(" -> ", 1)[1]
                path_text = path_text.strip().strip('"')
                if path_text:
                    dirty_paths.append(path_text.replace("\\", "/"))
    errors = [err for err in (branch_error, head_error, status_error) if err]
    return {
        "available": not errors,
        "branch": branch if branch_error is None else None,
        "head": head if head_error is None else None,
        "dirtyPaths": sorted(dirty_paths),
        "errors": errors,
    }


def recommended_read_order() -> List[Dict[str, Any]]:
    return [dict(item) for item in RECOMMENDED_READ_ORDER_V1]


def chatgpt_instructions() -> List[str]:
    return list(CHATGPT_INSTRUCTIONS_V1)


def error_next_hints(code: str) -> List[str]:
    fallback = [
        "Open /<token>/ to see the landing page.",
        "Open /<token>/health to see supported endpoints and recommendedReadOrder.",
    ]
    return list(ERROR_NEXT_HINTS_V1.get(code, fallback))


def landing_page_markdown(config: BridgeConfig) -> str:
    index = discover_payloads(config)
    latest_payload_id = index.get("latestPayloadId") or "none"
    endpoint_lines = "\n".join(f"- `{endpoint}`" for endpoint in ENDPOINTS_V1)
    inbox_endpoint_lines = "\n".join(f"- `{endpoint}`" for endpoint in INBOX_ENDPOINTS_V1)
    read_order_lines = "\n".join(
        f"{item['step']}. `{item['path']}` - {item['why']}" for item in RECOMMENDED_READ_ORDER_V1
    )
    instruction_lines = "\n".join(f"- {item}" for item in CHATGPT_INSTRUCTIONS_V1)
    return "\n".join(
        [
            "# RiftReader Local Artifact Bridge",
            "",
            "Tokenized bridge for curated RiftReader ChatGPT payload reads plus guarded Local Inbox v0 proposals.",
            "",
            f"- Version: `{VERSION}`",
            "- Mode: `read_only_artifacts_with_guarded_local_inbox`",
            f"- Latest payload: `{latest_payload_id}`",
            f"- Payload count: `{index.get('payloadCount')}`",
            f"- Local inbox count: `{inbox_index(config).get('count')}`",
            "",
            "## Start here",
            "",
            "- `./health`",
            "- `./payloads/latest/readme.md`",
            "- `./payloads/latest/chunks.json`",
            "- `./payloads/latest/chunks/<chunk_id>`",
            "",
            "## Recommended read order",
            "",
            read_order_lines,
            "",
            "## ChatGPT instructions",
            "",
            instruction_lines,
            "",
            "## Supported endpoints",
            "",
            endpoint_lines,
            "",
            "## Local Inbox v0",
            "",
            "The inbox is optional and guarded. It accepts JSON proposals only; it does not apply or execute them.",
            "",
            inbox_endpoint_lines,
            "",
            "Stored under: `.riftreader-local/artifact-bridge-inbox/`",
            "",
            "Safety: artifact reads are GET/HEAD only; inbox writes are JSON POST only under `.riftreader-local`; no command execution, arbitrary file reads, repo target writes, live RIFT input, CE, or x64dbg.",
            "",
        ]
    )


def health_payload(config: BridgeConfig) -> Dict[str, Any]:
    index = discover_payloads(config)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "service": "riftreader-local-artifact-bridge",
        "version": VERSION,
        "mode": "read_only_artifacts_with_guarded_local_inbox",
        "ok": True,
        "timestampUtc": utc_now_iso(),
        "bindHost": config.bind_host,
        "payloadRoot": repo_display_path(config.payload_root, config.repo_root),
        "inboxRoot": repo_display_path(config.inbox_root, config.repo_root),
        "payloadCount": index.get("payloadCount"),
        "latestPayloadId": index.get("latestPayloadId"),
        "maxResponseBytes": config.max_response_bytes,
        "maxInboxBytes": config.max_inbox_bytes,
        "allowedTextExtensions": sorted(ALLOWED_TEXT_EXTENSIONS),
        "blockedExtensions": sorted(BLOCKED_EXTENSIONS),
        "endpoints": ENDPOINTS_V1,
        "inboxEndpoints": INBOX_ENDPOINTS_V1,
        "localInbox": {
            "enabled": True,
            "endpoint": "/<token>/inbox/messages",
            "acceptedKinds": sorted(ALLOWED_INBOX_KINDS),
            "allowedFields": sorted(INBOX_ALLOWED_FIELDS),
            "storageRoot": repo_display_path(config.inbox_root, config.repo_root),
            "maxBytes": config.max_inbox_bytes,
            "duplicatesDetectedBy": "sha256(canonical-json)",
            "applyExecuteInV0": False,
        },
        "recommendedReadOrder": recommended_read_order(),
        "chatgptInstructions": chatgpt_instructions(),
        "safety": inbox_storage_safety(config),
    }


def status_payload(config: BridgeConfig) -> Dict[str, Any]:
    index = discover_payloads(config)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "service": "riftreader-local-artifact-bridge",
        "version": VERSION,
        "timestampUtc": utc_now_iso(),
        "mode": "read_only_artifacts_with_guarded_local_inbox",
        "repo": safe_repo_status(config),
        "payloadRoot": repo_display_path(config.payload_root, config.repo_root),
        "inbox": {
            "root": repo_display_path(config.inbox_root, config.repo_root),
            "count": inbox_index(config).get("count"),
        },
        "latestPayloadId": index.get("latestPayloadId"),
        "latestPayloadPath": index.get("latestPayloadPath"),
        "payloadCount": index.get("payloadCount"),
        "warnings": index.get("warnings", []),
    }


def preflight_redacted_urls(config: BridgeConfig) -> Dict[str, str]:
    base = f"http://{config.bind_host}:{config.port}/<token>"
    return {
        "landing": f"{base}/",
        "health": f"{base}/health",
        "readme": f"{base}/payloads/latest/readme.md",
        "chunks": f"{base}/payloads/latest/chunks.json",
        "chunkPattern": f"{base}/payloads/latest/chunks/<chunk_id>",
        "inboxMessages": f"{base}/inbox/messages",
    }


def preflight_check(name: str, passed: bool, message: str, code: str = "") -> Dict[str, Any]:
    return {
        "name": name,
        "passed": passed,
        "code": "" if passed else code,
        "message": message,
    }


def preflight_next_actions(status: str) -> List[str]:
    if status == "passed":
        return [
            "Run the printed manual start command only when you are ready to serve locally.",
            "Give ChatGPT the redacted URL pattern with the real token from bridge startup output.",
            "Keep tunnel management manual and stop the bridge/tunnel when finished.",
        ]
    return [
        "Create or refresh a curated payload under artifacts/chatgpt-payloads.",
        "Run the preflight again before starting --serve.",
        "Use --index --json to inspect payload discovery warnings.",
        "Use --inbox-index --json to inspect guarded local inbox proposals.",
    ]


def preflight_payload(config: BridgeConfig) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    blockers: List[str] = []
    warnings: List[str] = []
    index: Dict[str, Any] = {
        "payloadCount": 0,
        "latestPayloadId": None,
        "latestPayloadPath": None,
        "payloads": [],
        "warnings": [],
    }
    latest: Dict[str, Any] | None = None

    root = config.payload_root
    root_exists = root.exists()
    root_is_dir = root.is_dir()
    checks.append(preflight_check("payload-root-exists", root_exists, "Payload root exists.", "PAYLOAD_ROOT_MISSING"))
    checks.append(
        preflight_check("payload-root-is-directory", root_is_dir, "Payload root is a directory.", "PAYLOAD_ROOT_NOT_DIRECTORY")
    )

    if not root_exists:
        blockers.append("payload_root_missing")
    elif not root_is_dir:
        blockers.append("payload_root_not_directory")
    else:
        try:
            index = discover_payloads(config)
            warnings.extend(str(item) for item in index.get("warnings", []))
        except BridgeError as exc:
            blockers.append(f"payload_discovery_failed:{exc.code}")
            warnings.append(exc.message)
        payload_count = int(index.get("payloadCount") or 0)
        checks.append(preflight_check("valid-payload-count", payload_count > 0, "At least one valid payload is discoverable.", "NO_VALID_PAYLOADS"))
        if payload_count <= 0:
            blockers.append("no_valid_payloads")
        else:
            raw_payloads = index.get("payloads") or []
            latest = raw_payloads[-1] if isinstance(raw_payloads, list) and raw_payloads else None
            latest_summary_candidates = latest.get("summaryCandidates", []) if isinstance(latest, dict) else []
            latest_chunks = latest.get("chunks", []) if isinstance(latest, dict) else []
            serve_eligible_chunks = [
                chunk for chunk in latest_chunks if isinstance(chunk, dict) and chunk.get("serveEligible")
            ]
            checks.append(
                preflight_check(
                    "latest-summary-available",
                    bool(latest_summary_candidates),
                    "Latest payload has README.md or reports/reducer-summary.md.",
                    "LATEST_SUMMARY_MISSING",
                )
            )
            checks.append(
                preflight_check(
                    "latest-has-serveable-chunks",
                    bool(serve_eligible_chunks),
                    "Latest payload has at least one serve-eligible registered text chunk.",
                    "NO_SERVEABLE_CHUNKS",
                )
            )
            if not latest_summary_candidates:
                blockers.append("latest_summary_missing")
            if not serve_eligible_chunks:
                blockers.append("no_serveable_chunks")
            if isinstance(latest, dict) and latest.get("sha256Mismatches"):
                warnings.append(f"latest_sha256_mismatches:{','.join(str(item) for item in latest['sha256Mismatches'])}")
            if isinstance(latest, dict) and latest.get("sizeMismatches"):
                warnings.append(f"latest_size_mismatches:{','.join(str(item) for item in latest['sizeMismatches'])}")

    checks.extend(
        [
            preflight_check("bind-host-loopback", config.bind_host == "127.0.0.1", "Bridge bind host is loopback only.", "UNSAFE_BIND_HOST"),
            preflight_check("token-redacted", True, "Preflight output redacts token URLs.", ""),
            preflight_check("no-server-started", True, "Preflight did not start an HTTP server or tunnel.", ""),
            preflight_check("manual-tunnel-only", True, "Tunnel management remains manual.", ""),
            preflight_check(
                "inbox-root-local-only",
                is_relative_to(config.inbox_root, (config.repo_root / ".riftreader-local").resolve()),
                "Local inbox root stays under .riftreader-local.",
                "INBOX_ROOT_NOT_LOCAL",
            ),
        ]
    )

    if any(not item["passed"] and item["code"] == "UNSAFE_BIND_HOST" for item in checks):
        blockers.append("unsafe_bind_host")
    if any(not item["passed"] and item["code"] == "INBOX_ROOT_NOT_LOCAL" for item in checks):
        blockers.append("inbox_root_not_local")
    status = "passed" if not blockers else "blocked"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "tool": VERSION,
        "kind": "riftreader-local-artifact-bridge-preflight",
        "status": status,
        "ok": status == "passed",
        "timestampUtc": utc_now_iso(),
        "mode": "read_only_artifacts_with_guarded_inbox_preflight",
        "payloadRoot": repo_display_path(config.payload_root, config.repo_root),
        "inboxRoot": repo_display_path(config.inbox_root, config.repo_root),
        "maxInboxBytes": config.max_inbox_bytes,
        "localInbox": {
            "enabled": True,
            "endpoint": "/<token>/inbox/messages",
            "acceptedKinds": sorted(ALLOWED_INBOX_KINDS),
            "storageRoot": repo_display_path(config.inbox_root, config.repo_root),
            "applyExecuteInV0": False,
        },
        "payloadRootExists": root_exists,
        "payloadRootIsDirectory": root_is_dir,
        "payloadCount": index.get("payloadCount", 0),
        "latestPayloadId": index.get("latestPayloadId"),
        "latestPayloadPath": index.get("latestPayloadPath"),
        "latestSummaryCandidates": latest.get("summaryCandidates", []) if isinstance(latest, dict) else [],
        "redactedUrls": preflight_redacted_urls(config),
        "manualStartCommand": (
            ".\\scripts\\riftreader-local-artifact-bridge.cmd --serve "
            "--payload-root artifacts\\chatgpt-payloads --port 8765 --token auto "
            "--max-response-mb 25 --max-inbox-mb 1"
        ),
        "endpoints": ENDPOINTS_V1,
        "recommendedReadOrder": recommended_read_order(),
        "chatgptInstructions": chatgpt_instructions(),
        "checks": checks,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "safety": {
            "getHeadOnly": False,
            "artifactReadGetHeadOnly": True,
            "inboxJsonPostOnly": True,
            "noServerStarted": True,
            "noTunnelStarted": True,
            "manualTunnelOnly": True,
            "tokenRedacted": True,
            "noCommandExecutionEndpoint": True,
            "noArbitraryFileRead": True,
            "noRepoTargetWrites": True,
            "inboxWritesUnderDotRiftReaderLocalOnly": True,
            "noApplyExecute": True,
            "noLiveRiftInput": True,
            "noCheatEngine": True,
            "noX64dbg": True,
        },
        "next": preflight_next_actions(status),
    }


class BridgeHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: Tuple[str, int], handler_class: type, config: BridgeConfig) -> None:
        super().__init__(server_address, handler_class)
        self.config = config


def make_handler(config: BridgeConfig) -> type:
    class LocalArtifactBridgeHandler(http.server.BaseHTTPRequestHandler):
        server_version = "RiftReaderLocalArtifactBridge/0.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        @property
        def config(self) -> BridgeConfig:
            return self.server.config  # type: ignore[attr-defined]

        def do_GET(self) -> None:
            self._handle_allowed_method(send_body=True)

        def do_HEAD(self) -> None:
            self._handle_allowed_method(send_body=False)

        def do_POST(self) -> None:
            self._handle_post_method()

        def do_PUT(self) -> None:
            self._method_not_allowed()

        def do_PATCH(self) -> None:
            self._method_not_allowed()

        def do_DELETE(self) -> None:
            self._method_not_allowed()

        def do_OPTIONS(self) -> None:
            self._method_not_allowed()

        def _method_not_allowed(self) -> None:
            sent = self._send_error(
                405,
                "METHOD_NOT_ALLOWED",
                "Only GET/HEAD artifact reads and JSON POST inbox proposals are allowed.",
                send_body=True,
            )
            self._audit(405, sent, "METHOD_NOT_ALLOWED")

        def _handle_allowed_method(self, send_body: bool) -> None:
            status = 500
            sent = 0
            reason = ""
            try:
                sent = self._route(send_body=send_body)
                status = getattr(self, "_last_status", 200)
                reason = getattr(self, "_last_reason", "")
            except BridgeError as exc:
                status = exc.status
                reason = exc.code
                sent = self._send_error(exc.status, exc.code, exc.message, send_body=send_body)
            except Exception as exc:
                status = 500
                reason = "INTERNAL_ERROR"
                sent = self._send_error(
                    500,
                    "INTERNAL_ERROR",
                    f"Internal bridge error: {type(exc).__name__}",
                    send_body=send_body,
                )
                print(traceback.format_exc(), file=sys.stderr, flush=True)
            finally:
                self._audit(status, sent, reason)

        def _handle_post_method(self) -> None:
            status = 500
            sent = 0
            reason = ""
            try:
                sent = self._route_post()
                status = getattr(self, "_last_status", 200)
                reason = getattr(self, "_last_reason", "")
            except BridgeError as exc:
                status = exc.status
                reason = exc.code
                sent = self._send_error(exc.status, exc.code, exc.message, send_body=True)
            except Exception as exc:
                status = 500
                reason = "INTERNAL_ERROR"
                sent = self._send_error(
                    500,
                    "INTERNAL_ERROR",
                    f"Internal bridge error: {type(exc).__name__}",
                    send_body=True,
                )
                print(traceback.format_exc(), file=sys.stderr, flush=True)
            finally:
                self._audit(status, sent, reason)

        def _decoded_path_parts(self) -> List[str]:
            parsed = urllib.parse.urlsplit(self.path)
            decoded_path = urllib.parse.unquote(parsed.path)
            if "\x00" in decoded_path:
                raise BridgeError(400, "NUL_PATH_REJECTED", "Request path contains a NUL byte.")
            return decoded_path.split("/")

        def _tokenized_endpoint_parts(self) -> List[str]:
            parts = self._decoded_path_parts()
            if len(parts) < 2 or not parts[1]:
                raise BridgeError(403, "TOKEN_REQUIRED", "Token path segment is required.")
            token = parts[1]
            if token != self.config.token:
                raise BridgeError(403, "INVALID_TOKEN", "Invalid token.")
            return parts[2:]

        def _route(self, send_body: bool) -> int:
            endpoint_parts = self._tokenized_endpoint_parts()
            if endpoint_parts == [] or endpoint_parts == [""]:
                return self._send_text(200, landing_page_markdown(self.config), "text/markdown; charset=utf-8", send_body)
            if endpoint_parts == ["health"]:
                return self._send_json(200, health_payload(self.config), send_body)
            if endpoint_parts == ["status.json"]:
                return self._send_json(200, status_payload(self.config), send_body)
            if endpoint_parts == ["payloads", "index.json"]:
                return self._send_json(200, discover_payloads(self.config), send_body)
            if endpoint_parts == ["payloads", "latest", "manifest.json"]:
                payload_dir = latest_payload_dir(self.config)
                return self._send_file(payload_dir / "manifest.json", send_body)
            if endpoint_parts in (["payloads", "latest", "summary.md"], ["payloads", "latest", "readme.md"]):
                payload_dir = latest_payload_dir(self.config)
                return self._send_file(select_summary_file(payload_dir, self.config), send_body)
            if endpoint_parts in (["payloads", "latest", "chunk-index.json"], ["payloads", "latest", "chunks.json"]):
                payload_dir = latest_payload_dir(self.config)
                return self._send_file(payload_dir / "chunk-index.json", send_body)
            if len(endpoint_parts) >= 4 and endpoint_parts[:3] == ["payloads", "latest", "chunks"]:
                if len(endpoint_parts) != 4:
                    raise BridgeError(400, "PATHLIKE_CHUNK_ID_REJECTED", "Chunk endpoint accepts exactly one chunk ID segment.")
                chunk_id = endpoint_parts[3]
                validate_chunk_id(chunk_id)
                payload_dir = latest_payload_dir(self.config)
                chunk_index = load_chunk_index(payload_dir)
                chunk = find_chunk(chunk_index, chunk_id)
                if not chunk:
                    raise BridgeError(404, "CHUNK_NOT_FOUND", "Chunk ID is not registered in chunk-index.json.")
                path = resolve_payload_file(payload_dir, chunk.get("path"), self.config)
                return self._send_file(path, send_body)
            if endpoint_parts == ["inbox", "messages"]:
                raise BridgeError(405, "INBOX_METHOD_NOT_ALLOWED", "Local Inbox v0 accepts POST with application/json only.")
            raise BridgeError(404, "ENDPOINT_NOT_FOUND", "Endpoint not found.")

        def _route_post(self) -> int:
            endpoint_parts = self._tokenized_endpoint_parts()
            if endpoint_parts != ["inbox", "messages"]:
                return self._send_error(
                    405,
                    "METHOD_NOT_ALLOWED",
                    "POST is only allowed for /<token>/inbox/messages.",
                    send_body=True,
                )
            payload, raw_size = self._read_json_post_body()
            message = validate_inbox_message(payload)
            result = store_inbox_message(self.config, message, raw_size)
            return self._send_json(200 if result["duplicate"] else 201, result, send_body=True)

        def _read_json_post_body(self) -> Tuple[Any, int]:
            content_type = self.headers.get("Content-Type", "")
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type != "application/json":
                raise BridgeError(
                    415,
                    "INBOX_CONTENT_TYPE_UNSUPPORTED",
                    "Local Inbox v0 accepts only Content-Type: application/json.",
                )
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise BridgeError(411, "INBOX_LENGTH_REQUIRED", "Content-Length is required for inbox POST.")
            try:
                length = int(raw_length)
            except ValueError as exc:
                raise BridgeError(400, "INBOX_LENGTH_INVALID", "Content-Length must be an integer.") from exc
            if length <= 0:
                raise BridgeError(400, "INVALID_INBOX_JSON", "Inbox JSON body must not be empty.")
            if length > self.config.max_inbox_bytes:
                raise BridgeError(
                    413,
                    "INBOX_PAYLOAD_TOO_LARGE",
                    f"Inbox JSON body exceeds maxInboxBytes ({self.config.max_inbox_bytes}).",
                )
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise BridgeError(400, "INVALID_INBOX_JSON", "Request body ended before Content-Length bytes were read.")
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise BridgeError(400, "INVALID_INBOX_JSON", "Inbox JSON body must be UTF-8.") from exc
            try:
                return json.loads(text), len(raw)
            except json.JSONDecodeError as exc:
                raise BridgeError(400, "INVALID_INBOX_JSON", f"Invalid inbox JSON: {exc.msg}") from exc

        def _send_text(self, status: int, text: str, content_type: str, send_body: bool) -> int:
            raw = text.encode("utf-8")
            if len(raw) > self.config.max_response_bytes:
                return self._send_error(413, "RESPONSE_TOO_LARGE", "Text response exceeds max response size.", send_body)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if send_body:
                self.wfile.write(raw)
                bytes_sent = len(raw)
            else:
                bytes_sent = 0
            self._last_status = status
            self._last_reason = ""
            return bytes_sent

        def _send_json(self, status: int, payload: Any, send_body: bool) -> int:
            raw = json_bytes(payload)
            if len(raw) > self.config.max_response_bytes:
                return self._send_error(413, "RESPONSE_TOO_LARGE", "JSON response exceeds max response size.", send_body)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if send_body:
                self.wfile.write(raw)
                bytes_sent = len(raw)
            else:
                bytes_sent = 0
            self._last_status = status
            self._last_reason = ""
            return bytes_sent

        def _send_file(self, path: pathlib.Path, send_body: bool) -> int:
            if not path.exists() or not path.is_file():
                raise BridgeError(404, "FILE_NOT_FOUND", "Registered file does not exist.")
            display_name = path.name
            if is_blocked_extension(display_name) or not is_allowed_text_extension(path.as_posix()):
                raise BridgeError(415, "BLOCKED_EXTENSION", "File extension is blocked by default.")
            size = path.stat().st_size
            if size > self.config.max_response_bytes:
                raise BridgeError(413, "RESPONSE_TOO_LARGE", "Registered file exceeds max response size.")
            self.send_response(200)
            self.send_header("Content-Type", content_type_for_path(path))
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            bytes_sent = 0
            if send_body:
                with path.open("rb") as handle:
                    while True:
                        block = handle.read(1024 * 1024)
                        if not block:
                            break
                        bytes_sent += len(block)
                        self.wfile.write(block)
            self._last_status = 200
            self._last_reason = ""
            return bytes_sent

        def _send_error(self, status: int, code: str, message: str, send_body: bool) -> int:
            payload = {
                "schemaVersion": SCHEMA_VERSION,
                "ok": False,
                "status": status,
                "code": code,
                "message": message,
                "next": error_next_hints(code),
                "timestampUtc": utc_now_iso(),
            }
            raw = json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            if status == 405:
                self.send_header("Allow", "GET, HEAD, POST")
            self.end_headers()
            if send_body:
                self.wfile.write(raw)
                bytes_sent = len(raw)
            else:
                bytes_sent = 0
            self._last_status = status
            self._last_reason = code
            return bytes_sent

        def _audit(self, status: int, bytes_sent: int, reason: str) -> None:
            if not self.config.log_requests:
                return
            record = {
                "timestamp_utc": utc_now_iso(),
                "client_address": self.client_address[0] if self.client_address else None,
                "method": self.command,
                "path": urllib.parse.urlsplit(self.path).path,
                "status": status,
                "bytes_sent": bytes_sent,
                "reason_if_blocked": reason if status >= 400 else "",
            }
            print(json.dumps(record, sort_keys=True), file=sys.stderr, flush=True)

    return LocalArtifactBridgeHandler


def create_http_server(config: BridgeConfig) -> BridgeHTTPServer:
    return BridgeHTTPServer((config.bind_host, config.port), make_handler(config), config)


def request_local(
    host: str,
    port: int,
    method: str,
    path: str,
    body: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[int, Dict[str, str], bytes]:
    connection = http.client.HTTPConnection(host, port, timeout=5)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        body = response.read()
        headers = {key.lower(): value for key, value in response.getheaders()}
        return response.status, headers, body
    finally:
        connection.close()


def write_json(path: pathlib.Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_fake_payload(repo_root: pathlib.Path, payload_root: pathlib.Path, payload_id: str = "fake-payload-001") -> pathlib.Path:
    payload_dir = payload_root / payload_id
    payload_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = payload_dir / "candidates" / "chain-candidates.csv"
    chunk_path.parent.mkdir(parents=True, exist_ok=True)
    chunk_text = "rank,base,offset\n1,0x1000,0x20\n"
    chunk_path.write_text(chunk_text, encoding="utf-8")
    binary_path = payload_dir / "candidates" / "raw.bin"
    binary_path.write_bytes(b"\x00\x01\x02")
    big_path = payload_dir / "reports" / "big.txt"
    big_path.parent.mkdir(parents=True, exist_ok=True)
    big_path.write_text("X" * 5000, encoding="utf-8")
    readme = payload_dir / "README.md"
    readme.write_text("# Fake Payload\n\nSelf-test payload.\n", encoding="utf-8")
    manifest = {
        "schemaVersion": 1,
        "payloadId": payload_id,
        "createdUtc": "2026-05-17T00:00:00Z",
        "description": "Fake payload for local artifact bridge self-test.",
    }
    chunks = [
        {
            "chunkId": "chain-candidates",
            "path": "candidates/chain-candidates.csv",
            "kind": "csv",
            "sizeBytes": chunk_path.stat().st_size,
            "sha256": sha256_file(chunk_path),
            "description": "Ranked static pointer-chain candidates.",
        },
        {
            "chunkId": "binary-blocked",
            "path": "candidates/raw.bin",
            "kind": "binary",
            "sizeBytes": binary_path.stat().st_size,
            "sha256": sha256_file(binary_path),
            "description": "Blocked binary test file.",
        },
        {
            "chunkId": "oversized",
            "path": "reports/big.txt",
            "kind": "txt",
            "sizeBytes": big_path.stat().st_size,
            "sha256": sha256_file(big_path),
            "description": "Oversized response test file.",
        },
    ]
    write_json(payload_dir / "manifest.json", manifest)
    write_json(payload_dir / "chunk-index.json", {"schemaVersion": 1, "payloadId": payload_id, "chunks": chunks})
    return payload_dir


def run_self_test(json_mode: bool = False) -> int:
    with tempfile.TemporaryDirectory(prefix="riftreader_bridge_selftest_") as temp_text:
        repo_root = pathlib.Path(temp_text)
        payload_root = repo_root / DEFAULT_PAYLOAD_ROOT
        build_fake_payload(repo_root, payload_root)
        config = make_config(
            repo_root=repo_root,
            payload_root=DEFAULT_PAYLOAD_ROOT,
            token="selftest-token",
            port=0,
            max_response_bytes=4096,
            log_requests=False,
        )
        server = create_http_server(config)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        checks: List[Dict[str, Any]] = []
        try:
            cases = [
                ("landing", "GET", "/selftest-token/", 200),
                ("health", "GET", "/selftest-token/health", 200),
                ("invalid_token", "GET", "/wrong-token/health", 403),
                ("unknown", "GET", "/selftest-token/not-here", 404),
                ("method_block", "POST", "/selftest-token/health", 405),
                ("readme_alias", "GET", "/selftest-token/payloads/latest/readme.md", 200),
                ("chunks_alias", "GET", "/selftest-token/payloads/latest/chunks.json", 200),
                ("chunk", "GET", "/selftest-token/payloads/latest/chunks/chain-candidates", 200),
                ("traversal", "GET", "/selftest-token/payloads/latest/chunks/..%2Fsecret", 400),
                ("binary_block", "GET", "/selftest-token/payloads/latest/chunks/binary-blocked", 415),
                ("oversized", "GET", "/selftest-token/payloads/latest/chunks/oversized", 413),
            ]
            for name, method, path, expected in cases:
                status, _headers, body = request_local(str(host), int(port), method, path)
                checks.append(
                    {
                        "name": name,
                        "method": method,
                        "path": path.replace("selftest-token", "<token>"),
                        "expectedStatus": expected,
                        "actualStatus": status,
                        "pass": status == expected,
                        "bodyBytes": len(body),
                    }
                )
            inbox_body = json_bytes(
                {
                    "schemaVersion": SCHEMA_VERSION,
                    "kind": "chatgpt-message",
                    "title": "Self-test inbox proposal",
                    "body": "Verify guarded Local Inbox v0 stores JSON only.",
                }
            )
            for name, expected in (("inbox_store", 201), ("inbox_duplicate", 200)):
                status, _headers, body = request_local(
                    str(host),
                    int(port),
                    "POST",
                    "/selftest-token/inbox/messages",
                    body=inbox_body,
                    headers={"Content-Type": "application/json"},
                )
                parsed = json.loads(body.decode("utf-8"))
                checks.append(
                    {
                        "name": name,
                        "method": "POST",
                        "path": "/<token>/inbox/messages",
                        "expectedStatus": expected,
                        "actualStatus": status,
                        "pass": status == expected and bool(parsed.get("ok")),
                        "duplicate": parsed.get("duplicate"),
                        "bodyBytes": len(body),
                    }
                )
            status, _headers, body = request_local(
                str(host),
                int(port),
                "POST",
                "/selftest-token/inbox/messages",
                body=b"{not-json",
                headers={"Content-Type": "application/json"},
            )
            checks.append(
                {
                    "name": "inbox_malformed_json",
                    "method": "POST",
                    "path": "/<token>/inbox/messages",
                    "expectedStatus": 400,
                    "actualStatus": status,
                    "pass": status == 400,
                    "bodyBytes": len(body),
                }
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "tool": VERSION,
            "selfTest": all(item["pass"] for item in checks),
            "checkCount": len(checks),
            "checks": checks,
        }
        if json_mode:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload["selfTest"] else 1


def print_index(config: BridgeConfig, json_mode: bool) -> int:
    index = discover_payloads(config)
    if json_mode:
        print(json.dumps(index, indent=2, sort_keys=True))
    else:
        print(json.dumps(index, indent=2, sort_keys=True))
    return 0


def print_inbox_index(config: BridgeConfig, json_mode: bool) -> int:
    payload = inbox_index(config)
    if json_mode:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def run_preflight(config: BridgeConfig, json_mode: bool) -> int:
    payload = preflight_payload(config)
    if json_mode:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "passed" else 2


def serve(config: BridgeConfig, json_mode: bool) -> int:
    server = create_http_server(config)
    host, port = server.server_address
    startup = {
        "schemaVersion": SCHEMA_VERSION,
        "tool": VERSION,
        "mode": "read_only_artifacts_with_guarded_local_inbox",
        "bindHost": host,
        "port": port,
        "baseUrl": f"http://{host}:{port}/<token>",
        "healthPath": f"/{config.token}/health",
        "inboxPath": f"/{config.token}/inbox/messages",
        "payloadRoot": repo_display_path(config.payload_root, config.repo_root),
        "inboxRoot": repo_display_path(config.inbox_root, config.repo_root),
        "maxResponseBytes": config.max_response_bytes,
        "maxInboxBytes": config.max_inbox_bytes,
        "note": "Token is printed locally for operator use only. Do not paste it into public logs.",
    }
    if json_mode:
        print(json.dumps(startup, indent=2, sort_keys=True), flush=True)
    else:
        print("RiftReader Local Artifact Bridge v0.2", flush=True)
        print("Mode: read_only_artifacts_with_guarded_local_inbox", flush=True)
        print(f"Bind: http://{host}:{port}", flush=True)
        print(f"Health: http://{host}:{port}/{config.token}/health", flush=True)
        print(f"Inbox: http://{host}:{port}/{config.token}/inbox/messages", flush=True)
        print(f"Payload root: {repo_display_path(config.payload_root, config.repo_root)}", flush=True)
        print(f"Inbox root: {repo_display_path(config.inbox_root, config.repo_root)}", flush=True)
        print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("", file=sys.stderr, flush=True)
    finally:
        server.server_close()
    return 0


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RiftReader local artifact bridge with guarded Local Inbox v0.")
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--serve", action="store_true", help="Start the tokenized HTTP server.")
    mode_group.add_argument("--index", action="store_true", help="Print payload index JSON.")
    mode_group.add_argument("--inbox-index", action="store_true", help="Print guarded Local Inbox v0 index JSON.")
    mode_group.add_argument("--preflight", action="store_true", help="Check payload readiness without starting a server.")
    mode_group.add_argument("--self-test", action="store_true", help="Run local fake-payload self-test.")
    parser.add_argument("--payload-root", default=str(DEFAULT_PAYLOAD_ROOT), help="Repo-relative payload root.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Local bind port.")
    parser.add_argument("--host", default=DEFAULT_BIND_HOST, help="Bind host. v0.2 permits 127.0.0.1 only.")
    parser.add_argument("--token", default="auto", help="URL path token or 'auto'.")
    parser.add_argument("--max-response-mb", type=int, default=25, help="Maximum response size in MiB.")
    parser.add_argument("--max-inbox-mb", type=int, default=1, help="Maximum inbox POST body size in MiB.")
    parser.add_argument("--json", action="store_true", help="Print clean JSON on stdout for supported modes.")
    parser.add_argument("--repo-root", default=".", help="Repo root. Defaults to current working directory.")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        return run_self_test(json_mode=args.json)
    try:
        config = make_config(
            repo_root=pathlib.Path(args.repo_root),
            payload_root=pathlib.Path(args.payload_root),
            token=args.token,
            bind_host=args.host,
            port=args.port,
            max_response_bytes=args.max_response_mb * 1024 * 1024,
            max_inbox_bytes=args.max_inbox_mb * 1024 * 1024,
            log_requests=not args.json,
        )
        if args.index:
            return print_index(config, json_mode=args.json)
        if args.inbox_index:
            return print_inbox_index(config, json_mode=args.json)
        if args.preflight:
            return run_preflight(config, json_mode=args.json)
        if args.serve:
            return serve(config, json_mode=args.json)
        raise BridgeError(400, "NO_MODE", "No mode selected.")
    except BridgeError as exc:
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "ok": False,
            "status": exc.status,
            "code": exc.code,
            "message": exc.message,
        }
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
