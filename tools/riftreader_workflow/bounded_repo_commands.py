#!/usr/bin/env python3
"""Versioned allowlist registry for future bounded MCP repo commands.

Stage 33 only defines and validates deterministic command entries. It does not
execute commands and it is not an MCP tool surface.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, repo_rel, safety_flags, utc_iso, utc_stamp
except ImportError:  # pragma: no cover - direct script execution fallback.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, repo_rel, safety_flags, utc_iso, utc_stamp


SCHEMA_VERSION = 1
REGISTRY_VERSION = "bounded-repo-command-registry-v1"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_PARAMETER_VALUE_CHARS = 400
DEFAULT_OUTPUT_ROOT = Path(".riftreader-local") / "riftreader-chatgpt-mcp" / "bounded-commands"
RUN_SUMMARY_FILENAME = "run-summary.json"
MAX_AUDIT_INDEX_LIMIT = 50
MAX_AUDIT_INDEX_SCAN = 200
FORBIDDEN_ARGV_FRAGMENTS = (
    "&&",
    "|",
    ">",
    "<",
    "`",
    "powershell",
    "pwsh",
    "bash",
    " sh ",
    " git ",
    "git.exe",
    " reset",
    " clean",
    " stash",
    " checkout",
    " restore",
    " commit",
    " push",
    "--force",
    "x64dbg",
    "cheatengine",
    "cheat engine",
    "proofonly",
    "/reloadui",
    "rift_x64",
    "chromalink",
    "riftscan",
)


@dataclass(frozen=True)
class BoundedCommandSpec:
    key: str
    title: str
    description: str
    risk_class: str
    argv_template: tuple[str, ...]
    expected_exit_codes: tuple[int, ...]
    timeout_seconds: float
    max_stdout_bytes: int
    max_stderr_bytes: int
    read_only: bool = True
    requires_approval_token: bool = False
    writes_ignored_artifacts: bool = False
    forbidden_if_dirty: bool = False
    parameter_schema: dict[str, Any] | None = None
    safety_flags: dict[str, bool] | None = None

    def parameters(self) -> dict[str, Any]:
        schema = self.parameter_schema if isinstance(self.parameter_schema, dict) else {}
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        return dict(properties)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "registryVersion": REGISTRY_VERSION,
            "title": self.title,
            "description": self.description,
            "riskClass": self.risk_class,
            "readOnly": self.read_only,
            "requiresApprovalToken": self.requires_approval_token,
            "cwd": "repo-root",
            "argvTemplate": list(self.argv_template),
            "parameterSchema": normalized_parameter_schema(self.parameter_schema),
            "expectedExitCodes": list(self.expected_exit_codes),
            "timeoutSeconds": self.timeout_seconds,
            "maxStdoutBytes": self.max_stdout_bytes,
            "maxStderrBytes": self.max_stderr_bytes,
            "writesIgnoredArtifacts": self.writes_ignored_artifacts,
            "forbiddenIfDirty": self.forbidden_if_dirty,
            "safetyFlags": dict(self.safety_flags or default_command_safety_flags()),
        }


def default_command_safety_flags() -> dict[str, bool]:
    return {
        "gitMutation": False,
        "remoteMutation": False,
        "providerWrites": False,
        "inputSent": False,
        "movementSent": False,
        "reloaduiSent": False,
        "screenshotKeySent": False,
        "x64dbgAttach": False,
        "cheatEngine": False,
        "proofPromotion": False,
    }


def no_parameter_schema() -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "properties": {}}


def normalized_parameter_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    if schema is None:
        return no_parameter_schema()
    normalized = dict(schema)
    normalized.setdefault("type", "object")
    normalized.setdefault("additionalProperties", False)
    normalized.setdefault("properties", {})
    return normalized


def build_registry() -> dict[str, BoundedCommandSpec]:
    base_safety = default_command_safety_flags()
    return {
        "mcp_server_status": BoundedCommandSpec(
            key="mcp_server_status",
            title="MCP server status",
            description="Verify local ChatGPT MCP backend process, live tool surface, and source freshness.",
            risk_class="status-read",
            argv_template=("cmd", "/c", "scripts\\riftreader-mcp-server-status.cmd", "--json"),
            expected_exit_codes=(0, 1, 2),
            timeout_seconds=25.0,
            max_stdout_bytes=80_000,
            max_stderr_bytes=20_000,
            safety_flags=base_safety,
        ),
        "mcp_final_status": BoundedCommandSpec(
            key="mcp_final_status",
            title="MCP final readiness status",
            description="Run the compact read-only final-readiness gate.",
            risk_class="status-read",
            argv_template=("cmd", "/c", "scripts\\riftreader-mcp-final.cmd", "--status", "--compact-json"),
            expected_exit_codes=(0, 1, 2),
            timeout_seconds=35.0,
            max_stdout_bytes=50_000,
            max_stderr_bytes=20_000,
            safety_flags=base_safety,
        ),
        "stage38_consideration_status": BoundedCommandSpec(
            key="stage38_consideration_status",
            title="Stage 38 consideration status",
            description="Run the local-only Stage 38 consideration gate without starting live RIFT tooling.",
            risk_class="external-status-read",
            argv_template=("cmd", "/c", "scripts\\riftreader-stage38-consideration.cmd", "--status", "--compact-json"),
            expected_exit_codes=(0, 1, 2),
            timeout_seconds=45.0,
            max_stdout_bytes=80_000,
            max_stderr_bytes=20_000,
            safety_flags=base_safety,
        ),
        "stage38_approval_packet": BoundedCommandSpec(
            key="stage38_approval_packet",
            title="Stage 38 approval packet",
            description="Write a fail-closed local Stage 38 approval packet under ignored .riftreader-local artifacts.",
            risk_class="local-ignored-artifact-write",
            argv_template=("cmd", "/c", "scripts\\riftreader-stage38-consideration.cmd", "--write-approval-packet", "--json"),
            expected_exit_codes=(0, 1, 2),
            timeout_seconds=45.0,
            max_stdout_bytes=80_000,
            max_stderr_bytes=20_000,
            read_only=False,
            writes_ignored_artifacts=True,
            safety_flags=base_safety,
        ),
        "current_head_ci_status": BoundedCommandSpec(
            key="current_head_ci_status",
            title="Current HEAD CI status",
            description="Inspect current-head GitHub Actions status through the existing read-only helper.",
            risk_class="external-status-read",
            argv_template=("python", "tools\\riftreader_workflow\\mcp_ci_status.py", "--status", "--json"),
            expected_exit_codes=(0, 1, 2),
            timeout_seconds=45.0,
            max_stdout_bytes=80_000,
            max_stderr_bytes=20_000,
            safety_flags=base_safety,
        ),
        "validate_mcp_sdk": BoundedCommandSpec(
            key="validate_mcp_sdk",
            title="Validate MCP SDK metadata",
            description="Validate FastMCP tool metadata for the full profile without serving persistently.",
            risk_class="local-validation",
            argv_template=(
                "python",
                "tools\\riftreader_workflow\\riftreader_chatgpt_mcp.py",
                "--validate-sdk",
                "--tool-profile",
                "full",
                "--json",
            ),
            expected_exit_codes=(0,),
            timeout_seconds=60.0,
            max_stdout_bytes=80_000,
            max_stderr_bytes=20_000,
            safety_flags=base_safety,
        ),
        "test_mcp_server_status": BoundedCommandSpec(
            key="test_mcp_server_status",
            title="Test MCP server status helper",
            description="Run focused unit tests for MCP runtime dependency classification.",
            risk_class="local-validation",
            argv_template=("python", "-m", "unittest", "scripts.test_mcp_server_status"),
            expected_exit_codes=(0,),
            timeout_seconds=35.0,
            max_stdout_bytes=40_000,
            max_stderr_bytes=20_000,
            safety_flags=base_safety,
        ),
    }


REGISTRY = build_registry()


def command_keys() -> list[str]:
    return sorted(REGISTRY)


def command_spec(command_key: str) -> BoundedCommandSpec | None:
    return REGISTRY.get(command_key)


def _contains_forbidden_fragment(argv: tuple[str, ...]) -> list[str]:
    joined = f" {' '.join(argv)} ".lower()
    blockers: list[str] = []
    for fragment in FORBIDDEN_ARGV_FRAGMENTS:
        if fragment in joined:
            blockers.append(f"forbidden-argv-fragment:{fragment.strip()}")
    return blockers


def validate_command_spec(spec: BoundedCommandSpec) -> list[str]:
    blockers: list[str] = []
    if not spec.key or not spec.key.replace("_", "").replace("-", "").isalnum():
        blockers.append(f"invalid-command-key:{spec.key!r}")
    if not spec.argv_template:
        blockers.append(f"argv-template-empty:{spec.key}")
    if any(not isinstance(part, str) or not part for part in spec.argv_template):
        blockers.append(f"argv-token-invalid:{spec.key}")
    if any("\n" in part or "\r" in part for part in spec.argv_template):
        blockers.append(f"argv-token-newline:{spec.key}")
    if spec.argv_template[:2] == ("cmd", "/c"):
        if len(spec.argv_template) < 3 or not spec.argv_template[2].startswith("scripts\\") or not spec.argv_template[2].endswith(".cmd"):
            blockers.append(f"cmd-wrapper-not-repo-script:{spec.key}")
    elif "cmd" in spec.argv_template or "/c" in spec.argv_template:
        blockers.append(f"cmd-token-unexpected-position:{spec.key}")
    blockers.extend(_contains_forbidden_fragment(spec.argv_template))
    if spec.timeout_seconds <= 0 or spec.timeout_seconds > 120:
        blockers.append(f"timeout-out-of-range:{spec.key}:{spec.timeout_seconds}")
    if spec.max_stdout_bytes <= 0 or spec.max_stdout_bytes > 100_000:
        blockers.append(f"stdout-cap-out-of-range:{spec.key}:{spec.max_stdout_bytes}")
    if spec.max_stderr_bytes <= 0 or spec.max_stderr_bytes > 100_000:
        blockers.append(f"stderr-cap-out-of-range:{spec.key}:{spec.max_stderr_bytes}")
    schema = normalized_parameter_schema(spec.parameter_schema)
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        blockers.append(f"parameter-schema-not-closed:{spec.key}")
    safety = spec.safety_flags or {}
    for flag in ("gitMutation", "remoteMutation", "providerWrites", "inputSent", "movementSent", "x64dbgAttach"):
        if safety.get(flag) is not False:
            blockers.append(f"unsafe-safety-flag:{spec.key}:{flag}")
    return blockers


def validate_registry_integrity(registry: dict[str, BoundedCommandSpec] | None = None) -> list[str]:
    items = registry or REGISTRY
    blockers: list[str] = []
    for key, spec in items.items():
        if key != spec.key:
            blockers.append(f"registry-key-mismatch:{key}:{spec.key}")
        blockers.extend(validate_command_spec(spec))
    return blockers


def validate_parameters(spec: BoundedCommandSpec, parameters: Any) -> list[str]:
    if parameters is None:
        parameters = {}
    if not isinstance(parameters, dict):
        return ["parameters-not-object"]
    allowed = spec.parameters()
    blockers: list[str] = []
    for key, value in parameters.items():
        if key not in allowed:
            blockers.append(f"parameter-not-allowed:{key}")
        if isinstance(value, str) and len(value) > MAX_PARAMETER_VALUE_CHARS:
            blockers.append(f"parameter-value-too-long:{key}")
        if isinstance(value, str) and (".." in value or "\\" in value or "/" in value):
            blockers.append(f"parameter-path-like-value-blocked:{key}")
    return blockers


def plan_command(
    command_key: str,
    parameters: dict[str, Any] | None = None,
    *,
    expected_registry_version: str | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    spec = command_spec(command_key)
    if expected_registry_version is not None and expected_registry_version != REGISTRY_VERSION:
        blockers.append(f"registry-version-mismatch:{expected_registry_version}:{REGISTRY_VERSION}")
    if spec is None:
        blockers.append(f"unknown-command-key:{command_key}")
        return command_plan_payload(command_key, None, parameters or {}, timeout_seconds, blockers)
    blockers.extend(validate_command_spec(spec))
    blockers.extend(validate_parameters(spec, parameters or {}))
    effective_timeout = spec.timeout_seconds if timeout_seconds is None else timeout_seconds
    if effective_timeout <= 0:
        blockers.append(f"timeout-not-positive:{effective_timeout}")
    if effective_timeout > spec.timeout_seconds:
        blockers.append(f"timeout-exceeds-registry-max:{effective_timeout}>{spec.timeout_seconds}")
    return command_plan_payload(command_key, spec, parameters or {}, effective_timeout, blockers)


def command_plan_payload(
    command_key: str,
    spec: BoundedCommandSpec | None,
    parameters: dict[str, Any],
    timeout_seconds: float | None,
    blockers: list[str],
) -> dict[str, Any]:
    argv = list(spec.argv_template) if spec is not None else []
    status = "passed" if not blockers else "blocked"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-bounded-repo-command-plan",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": not blockers,
        "registryVersion": REGISTRY_VERSION,
        "commandKey": command_key,
        "parameters": parameters,
        "cwd": "repo-root",
        "argv": argv,
        "shellStringAccepted": False,
        "timeoutSeconds": timeout_seconds,
        "expectedExitCodes": list(spec.expected_exit_codes) if spec is not None else [],
        "maxStdoutBytes": spec.max_stdout_bytes if spec is not None else None,
        "maxStderrBytes": spec.max_stderr_bytes if spec is not None else None,
        "requiresApprovalToken": bool(spec.requires_approval_token) if spec is not None else None,
        "readOnly": bool(spec.read_only) if spec is not None else None,
        "writesIgnoredArtifacts": bool(spec.writes_ignored_artifacts) if spec is not None else None,
        "blockers": blockers,
        "warnings": [],
        "safety": {
            **safety_flags(),
            **(spec.safety_flags if spec is not None and spec.safety_flags is not None else default_command_safety_flags()),
            "registryOnly": True,
            "commandExecuted": False,
            "shellStringAccepted": False,
            "arbitraryCommand": False,
            "gitMutation": False,
            "providerWrites": False,
        },
    }


def _truncate_bytes(text: str | None, max_bytes: int) -> tuple[str, bool, int]:
    if not text:
        return "", False, 0
    data = text.encode("utf-8", errors="replace")
    original_bytes = len(data)
    if original_bytes <= max_bytes:
        return text, False, original_bytes
    truncated = data[:max_bytes].decode("utf-8", errors="replace")
    return truncated, True, original_bytes


def _sha256_text(text: str | None) -> str | None:
    if text is None or text == "":
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped.startswith("{"):
        return None
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _run_summary_path(repo_root: Path, command_key: str) -> Path:
    safe_key = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in command_key)
    output_dir = repo_root / DEFAULT_OUTPUT_ROOT / f"{utc_stamp()}-{safe_key}"
    suffix = 2
    while output_dir.exists():
        output_dir = repo_root / DEFAULT_OUTPUT_ROOT / f"{utc_stamp()}-{safe_key}-{suffix}"
        suffix += 1
    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir / "run-summary.json"


def run_command(
    command_key: str,
    parameters: dict[str, Any] | None = None,
    *,
    expected_registry_version: str | None = None,
    timeout_seconds: float | None = None,
    approval_token: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    plan = plan_command(
        command_key,
        parameters,
        expected_registry_version=expected_registry_version,
        timeout_seconds=timeout_seconds,
    )
    spec = command_spec(command_key)
    blockers = list(plan.get("blockers") or [])
    if spec is not None and spec.requires_approval_token and not approval_token:
        blockers.append(f"approval-token-required:{command_key}")
    if blockers or spec is None:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-bounded-repo-command-run",
            "generatedAtUtc": utc_iso(),
            "status": "blocked",
            "ok": False,
            "registryVersion": REGISTRY_VERSION,
            "commandKey": command_key,
            "parameters": parameters or {},
            "plan": plan,
            "summaryPath": None,
            "exitCode": None,
            "timedOut": False,
            "commandExecuted": False,
            "blockers": blockers,
            "warnings": [],
            "safety": {
                **safety_flags(),
                **default_command_safety_flags(),
                "mcpToolExposed": True,
                "commandExecuted": False,
                "shellStringAccepted": False,
                "arbitraryCommand": False,
                "gitMutation": False,
                "providerWrites": False,
            },
        }

    root = find_repo_root(repo_root or Path.cwd())
    argv = list(spec.argv_template)
    started_at = utc_iso()
    start = time.monotonic()
    stdout_text = ""
    stderr_text = ""
    exit_code: int | None = None
    timed_out = False
    error: str | None = None
    try:
        completed = subprocess.run(
            argv,
            cwd=root,
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=plan.get("timeoutSeconds"),
        )
        exit_code = completed.returncode
        stdout_text = completed.stdout or ""
        stderr_text = completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        error = f"TimeoutExpired:{exc}"
        stdout_text = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr_text = exc.stderr if isinstance(exc.stderr, str) else ""
    except FileNotFoundError as exc:
        error = f"FileNotFoundError:{exc}"
    except Exception as exc:  # noqa: BLE001 - command envelopes must capture unexpected local failures.
        error = f"{type(exc).__name__}:{exc}"
    ended_at = utc_iso()
    duration = round(time.monotonic() - start, 3)
    stdout_preview, stdout_truncated, stdout_bytes = _truncate_bytes(stdout_text, spec.max_stdout_bytes)
    stderr_preview, stderr_truncated, stderr_bytes = _truncate_bytes(stderr_text, spec.max_stderr_bytes)
    run_blockers: list[str] = []
    if timed_out:
        run_blockers.append(f"command-timeout:{command_key}")
    if error and not timed_out:
        run_blockers.append(f"command-error:{error.split(':', 1)[0]}")
    if exit_code is not None and exit_code not in spec.expected_exit_codes:
        run_blockers.append(f"exit-code-unexpected:{exit_code}")
    child_payload = _parse_json_object(stdout_text)
    child_status = child_payload.get("status") if isinstance(child_payload, dict) else None
    child_ok = child_payload.get("ok") if isinstance(child_payload, dict) else None
    if child_ok is False:
        child_blockers = child_payload.get("blockers") if isinstance(child_payload.get("blockers"), list) else []
        if child_blockers:
            run_blockers.extend(f"child:{blocker}" for blocker in child_blockers[:10] if isinstance(blocker, str))
        else:
            run_blockers.append(f"child-status:{child_status or 'blocked'}")
    ok = not run_blockers
    status = "passed" if ok else ("blocked" if child_ok is False or child_status == "blocked" else "failed")
    summary_path = _run_summary_path(root, command_key)
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-bounded-repo-command-run",
        "generatedAtUtc": ended_at,
        "registryVersion": REGISTRY_VERSION,
        "commandKey": command_key,
        "parameters": parameters or {},
        "status": status,
        "ok": ok,
        "plan": plan,
        "cwd": str(root),
        "argv": argv,
        "startedAtUtc": started_at,
        "endedAtUtc": ended_at,
        "durationSeconds": duration,
        "exitCode": exit_code,
        "timedOut": timed_out,
        "error": error,
        "stdoutPreview": stdout_preview,
        "stderrPreview": stderr_preview,
        "stdoutTruncated": stdout_truncated,
        "stderrTruncated": stderr_truncated,
        "stdoutBytes": stdout_bytes,
        "stderrBytes": stderr_bytes,
        "stdoutSha256": _sha256_text(stdout_text),
        "stderrSha256": _sha256_text(stderr_text),
        "childStatus": child_status,
        "childOk": child_ok,
        "summaryPath": str(summary_path),
        "summaryPathRel": repo_rel(root, summary_path),
        "commandExecuted": True,
        "blockers": run_blockers,
        "warnings": [],
        "safety": {
            **safety_flags(),
            **(spec.safety_flags or default_command_safety_flags()),
            "mcpToolExposed": True,
            "commandExecuted": True,
            "shellStringAccepted": False,
            "arbitraryCommand": False,
            "gitMutation": False,
            "providerWrites": False,
        },
    }
    summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def _resolve_repo_root(repo_root: Path | None = None) -> Path:
    return find_repo_root(repo_root or Path.cwd())


def _audit_root(repo_root: Path) -> Path:
    return repo_root / DEFAULT_OUTPUT_ROOT


def _resolve_audit_summary_path(summary_path: str | Path, repo_root: Path) -> tuple[Path | None, list[str]]:
    blockers: list[str] = []
    raw_text = str(summary_path).strip()
    if not raw_text:
        return None, ["summary-path-empty"]
    raw_path = Path(raw_text)
    candidate = raw_path if raw_path.is_absolute() else repo_root / raw_path
    resolved = candidate.resolve()
    audit_root = _audit_root(repo_root).resolve()
    try:
        resolved.relative_to(audit_root)
    except ValueError:
        blockers.append("summary-path-outside-audit-root")
    if resolved.name != RUN_SUMMARY_FILENAME:
        blockers.append(f"summary-path-not-{RUN_SUMMARY_FILENAME}")
    if not resolved.is_file():
        blockers.append("summary-path-not-found")
    return resolved, blockers


def _load_json_file(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"summary-json-invalid:{exc.__class__.__name__}"]
    except OSError as exc:
        return None, [f"summary-read-failed:{exc.__class__.__name__}"]
    if not isinstance(value, dict):
        return None, ["summary-json-not-object"]
    return value, []


def validate_run_summary_payload(payload: dict[str, Any], *, repo_root: Path | None = None) -> tuple[list[str], list[str]]:
    """Validate that a saved run summary is a bounded-command audit envelope.

    This validator checks the envelope only. A command whose child status was
    blocked is still replayable when the envelope is complete and safe.
    """

    root = _resolve_repo_root(repo_root)
    blockers: list[str] = []
    warnings: list[str] = []
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        blockers.append(f"summary-schema-version-invalid:{payload.get('schemaVersion')!r}")
    if payload.get("kind") != "riftreader-bounded-repo-command-run":
        blockers.append(f"summary-kind-invalid:{payload.get('kind')!r}")
    command_key = payload.get("commandKey")
    if not isinstance(command_key, str) or not command_key:
        blockers.append("summary-command-key-invalid")
        spec = None
    else:
        spec = command_spec(command_key)
        if spec is None:
            blockers.append(f"summary-command-key-unknown:{command_key}")
    registry_version = payload.get("registryVersion")
    if registry_version != REGISTRY_VERSION:
        warnings.append(f"summary-registry-version-differs:{registry_version}:{REGISTRY_VERSION}")
    status = payload.get("status")
    if status not in {"passed", "blocked", "failed"}:
        blockers.append(f"summary-status-invalid:{status!r}")
    if not isinstance(payload.get("ok"), bool):
        blockers.append("summary-ok-not-bool")
    argv = payload.get("argv")
    if not isinstance(argv, list) or any(not isinstance(part, str) for part in argv):
        blockers.append("summary-argv-invalid")
    elif spec is not None and registry_version == REGISTRY_VERSION and list(spec.argv_template) != argv:
        blockers.append(f"summary-argv-mismatch:{command_key}")
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        blockers.append("summary-cwd-invalid")
    elif cwd not in {"repo-root", "."}:
        try:
            if Path(cwd).resolve() != root.resolve():
                blockers.append("summary-cwd-not-repo-root")
        except OSError:
            blockers.append("summary-cwd-unresolvable")
    for key in ("generatedAtUtc", "startedAtUtc", "endedAtUtc"):
        if not isinstance(payload.get(key), str) or not payload.get(key):
            blockers.append(f"summary-{key}-invalid")
    if not isinstance(payload.get("durationSeconds"), (int, float)):
        blockers.append("summary-durationSeconds-invalid")
    exit_code = payload.get("exitCode")
    if exit_code is not None and not isinstance(exit_code, int):
        blockers.append("summary-exitCode-invalid")
    for key in ("timedOut", "stdoutTruncated", "stderrTruncated", "commandExecuted"):
        if not isinstance(payload.get(key), bool):
            blockers.append(f"summary-{key}-not-bool")
    for key in ("stdoutPreview", "stderrPreview"):
        if not isinstance(payload.get(key), str):
            blockers.append(f"summary-{key}-not-string")
    if spec is not None:
        stdout_preview = payload.get("stdoutPreview")
        stderr_preview = payload.get("stderrPreview")
        if isinstance(stdout_preview, str) and len(stdout_preview.encode("utf-8", errors="replace")) > spec.max_stdout_bytes:
            blockers.append("summary-stdoutPreview-exceeds-cap")
        if isinstance(stderr_preview, str) and len(stderr_preview.encode("utf-8", errors="replace")) > spec.max_stderr_bytes:
            blockers.append("summary-stderrPreview-exceeds-cap")
    for key in ("stdoutBytes", "stderrBytes"):
        if not isinstance(payload.get(key), int):
            blockers.append(f"summary-{key}-invalid")
    for key in ("blockers", "warnings"):
        if not isinstance(payload.get(key), list):
            blockers.append(f"summary-{key}-not-list")
    safety = payload.get("safety")
    if not isinstance(safety, dict):
        blockers.append("summary-safety-not-object")
        safety = {}
    for flag in (
        "shellStringAccepted",
        "arbitraryCommand",
        "gitMutation",
        "providerWrites",
        "inputSent",
        "movementSent",
        "reloaduiSent",
        "screenshotKeySent",
        "x64dbgAttach",
        "proofPromotion",
    ):
        if safety.get(flag) is not False:
            blockers.append(f"summary-unsafe-safety-flag:{flag}")
    if safety.get("noCheatEngine") is False:
        blockers.append("summary-unsafe-safety-flag:noCheatEngine")
    return blockers, warnings


def _audit_replay_safety() -> dict[str, bool]:
    return {
        **safety_flags(),
        **default_command_safety_flags(),
        "auditReplay": True,
        "commandExecuted": False,
        "shellStringAccepted": False,
        "arbitraryCommand": False,
        "gitMutation": False,
        "providerWrites": False,
    }


def replay_run_summary(summary_path: str | Path, *, repo_root: Path | None = None) -> dict[str, Any]:
    """Replay/inspect a saved bounded-command run summary without re-executing it."""

    root = _resolve_repo_root(repo_root)
    resolved, blockers = _resolve_audit_summary_path(summary_path, root)
    payload: dict[str, Any] | None = None
    file_sha256: str | None = None
    if resolved is not None and not blockers:
        file_sha256 = _sha256_file(resolved)
        payload, load_blockers = _load_json_file(resolved)
        blockers.extend(load_blockers)
        if payload is not None:
            validation_blockers, validation_warnings = validate_run_summary_payload(payload, repo_root=root)
            blockers.extend(validation_blockers)
            warnings = validation_warnings
        else:
            warnings = []
    else:
        warnings = []
    command_key = payload.get("commandKey") if isinstance(payload, dict) else None
    command_blockers = payload.get("blockers") if isinstance(payload, dict) and isinstance(payload.get("blockers"), list) else []
    command_warnings = payload.get("warnings") if isinstance(payload, dict) and isinstance(payload.get("warnings"), list) else []
    status = "passed" if not blockers else "blocked"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-bounded-repo-command-audit-replay",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": not blockers,
        "registryVersion": REGISTRY_VERSION,
        "summaryPath": repo_rel(root, resolved) if resolved is not None else str(summary_path),
        "summarySha256": file_sha256,
        "summaryEnvelopeValid": not blockers,
        "commandKey": command_key,
        "commandStatus": payload.get("status") if isinstance(payload, dict) else None,
        "commandOk": payload.get("ok") if isinstance(payload, dict) else None,
        "commandExecuted": bool(payload.get("commandExecuted")) if isinstance(payload, dict) else False,
        "argv": payload.get("argv") if isinstance(payload, dict) else None,
        "cwd": "repo-root" if isinstance(payload, dict) and payload.get("cwd") else None,
        "startedAtUtc": payload.get("startedAtUtc") if isinstance(payload, dict) else None,
        "endedAtUtc": payload.get("endedAtUtc") if isinstance(payload, dict) else None,
        "durationSeconds": payload.get("durationSeconds") if isinstance(payload, dict) else None,
        "exitCode": payload.get("exitCode") if isinstance(payload, dict) else None,
        "timedOut": bool(payload.get("timedOut")) if isinstance(payload, dict) else False,
        "stdoutPreview": payload.get("stdoutPreview") if isinstance(payload, dict) else None,
        "stderrPreview": payload.get("stderrPreview") if isinstance(payload, dict) else None,
        "stdoutTruncated": bool(payload.get("stdoutTruncated")) if isinstance(payload, dict) else False,
        "stderrTruncated": bool(payload.get("stderrTruncated")) if isinstance(payload, dict) else False,
        "stdoutBytes": payload.get("stdoutBytes") if isinstance(payload, dict) else None,
        "stderrBytes": payload.get("stderrBytes") if isinstance(payload, dict) else None,
        "stdoutSha256": payload.get("stdoutSha256") if isinstance(payload, dict) else None,
        "stderrSha256": payload.get("stderrSha256") if isinstance(payload, dict) else None,
        "childStatus": payload.get("childStatus") if isinstance(payload, dict) else None,
        "childOk": payload.get("childOk") if isinstance(payload, dict) else None,
        "commandBlockers": command_blockers,
        "commandWarnings": command_warnings,
        "blockers": blockers,
        "warnings": warnings,
        "safety": _audit_replay_safety(),
    }


def _compact_audit_entry(replay: dict[str, Any]) -> dict[str, Any]:
    return {
        "summaryPath": replay.get("summaryPath"),
        "summarySha256": replay.get("summarySha256"),
        "summaryEnvelopeValid": replay.get("summaryEnvelopeValid"),
        "commandKey": replay.get("commandKey"),
        "commandStatus": replay.get("commandStatus"),
        "commandOk": replay.get("commandOk"),
        "commandExecuted": replay.get("commandExecuted"),
        "exitCode": replay.get("exitCode"),
        "timedOut": replay.get("timedOut"),
        "durationSeconds": replay.get("durationSeconds"),
        "endedAtUtc": replay.get("endedAtUtc"),
        "blockers": (replay.get("blockers") or [])[:5],
        "commandBlockers": (replay.get("commandBlockers") or [])[:5],
    }


def list_run_summaries(
    command_key: str | None = None,
    *,
    limit: int = 10,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = _resolve_repo_root(repo_root)
    blockers: list[str] = []
    if limit <= 0:
        blockers.append(f"limit-not-positive:{limit}")
    if limit > MAX_AUDIT_INDEX_LIMIT:
        blockers.append(f"limit-exceeds-max:{limit}>{MAX_AUDIT_INDEX_LIMIT}")
    if command_key is not None and command_key not in REGISTRY:
        blockers.append(f"unknown-command-key:{command_key}")
    entries: list[dict[str, Any]] = []
    scanned = 0
    audit_root = _audit_root(root)
    if not blockers and audit_root.exists():
        paths = sorted(
            audit_root.glob(f"*/{RUN_SUMMARY_FILENAME}"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in paths[:MAX_AUDIT_INDEX_SCAN]:
            scanned += 1
            replay = replay_run_summary(path, repo_root=root)
            if command_key is not None and replay.get("commandKey") != command_key:
                continue
            entries.append(_compact_audit_entry(replay))
            if len(entries) >= limit:
                break
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-bounded-repo-command-audit-index",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if not blockers else "blocked",
        "ok": not blockers,
        "registryVersion": REGISTRY_VERSION,
        "auditRoot": repo_rel(root, audit_root),
        "commandKey": command_key,
        "limit": limit,
        "runCount": len(entries),
        "scannedRunCount": scanned,
        "runs": entries,
        "blockers": blockers,
        "warnings": [],
        "safety": _audit_replay_safety(),
    }


def latest_run_summary(command_key: str | None = None, *, repo_root: Path | None = None) -> dict[str, Any]:
    index = list_run_summaries(command_key, limit=1, repo_root=repo_root)
    blockers = list(index.get("blockers") or [])
    runs = index.get("runs") if isinstance(index.get("runs"), list) else []
    if not blockers and not runs:
        blockers.append("no-run-summary-found")
    if blockers:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-bounded-repo-command-audit-latest",
            "generatedAtUtc": utc_iso(),
            "status": "blocked",
            "ok": False,
            "registryVersion": REGISTRY_VERSION,
            "commandKey": command_key,
            "latestRun": None,
            "blockers": blockers,
            "warnings": list(index.get("warnings") or []),
            "safety": _audit_replay_safety(),
        }
    return replay_run_summary(runs[0]["summaryPath"], repo_root=repo_root)


def registry_payload() -> dict[str, Any]:
    blockers = validate_registry_integrity()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-bounded-repo-command-registry",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if not blockers else "blocked",
        "ok": not blockers,
        "registryVersion": REGISTRY_VERSION,
        "commandCount": len(REGISTRY),
        "commands": [REGISTRY[key].as_dict() for key in command_keys()],
        "blockers": blockers,
        "warnings": [],
        "safety": {
            **safety_flags(),
            "registryOnly": True,
            "commandExecuted": False,
            "mcpToolExposed": False,
            "shellStringAccepted": False,
            "arbitraryCommand": False,
            "gitMutation": False,
            "providerWrites": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect the bounded repo command registry without executing commands.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--plan", metavar="COMMAND_KEY")
    parser.add_argument("--run", metavar="COMMAND_KEY")
    parser.add_argument("--list-runs", action="store_true")
    parser.add_argument("--latest-run", nargs="?", const="", metavar="COMMAND_KEY")
    parser.add_argument("--replay-summary", metavar="SUMMARY_PATH")
    parser.add_argument("--audit-command-key", default=None)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--parameters-json", default="{}")
    parser.add_argument("--expected-registry-version", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=None)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def load_parameters(text: str) -> dict[str, Any]:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("parameters JSON must be an object")
    return value


def self_test() -> dict[str, Any]:
    registry = registry_payload()
    accepted = plan_command("mcp_server_status")
    unknown = plan_command("git_reset_hard")
    version_mismatch = plan_command("mcp_server_status", expected_registry_version="wrong-version")
    blockers: list[str] = []
    if not registry.get("ok"):
        blockers.append("registry-integrity-failed")
    if not accepted.get("ok"):
        blockers.append("accepted-safe-command-blocked")
    if unknown.get("ok") or "unknown-command-key:git_reset_hard" not in unknown.get("blockers", []):
        blockers.append("unknown-command-not-blocked")
    if version_mismatch.get("ok"):
        blockers.append("registry-version-mismatch-not-blocked")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-bounded-repo-command-registry-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if not blockers else "blocked",
        "ok": not blockers,
        "stages": {
            "registry": registry,
            "accepted": accepted,
            "unknown": unknown,
            "versionMismatch": version_mismatch,
        },
        "blockers": blockers,
        "safety": {
            **safety_flags(),
            "registryOnly": True,
            "commandExecuted": False,
            "mcpToolExposed": False,
            "gitMutation": False,
            "providerWrites": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root) if args.repo_root else None
    if args.repo_root:
        find_repo_root(Path(args.repo_root))
    if args.self_test:
        payload = self_test()
    elif args.replay_summary:
        payload = replay_run_summary(args.replay_summary, repo_root=repo_root)
    elif args.latest_run is not None:
        payload = latest_run_summary(args.latest_run or args.audit_command_key, repo_root=repo_root)
    elif args.list_runs:
        payload = list_run_summaries(args.audit_command_key, limit=args.limit, repo_root=repo_root)
    elif args.plan:
        payload = plan_command(
            args.plan,
            load_parameters(args.parameters_json),
            expected_registry_version=args.expected_registry_version,
            timeout_seconds=args.timeout_seconds,
        )
    elif args.run:
        payload = run_command(
            args.run,
            load_parameters(args.parameters_json),
            expected_registry_version=args.expected_registry_version,
            timeout_seconds=args.timeout_seconds,
            repo_root=repo_root,
        )
    else:
        payload = registry_payload()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
