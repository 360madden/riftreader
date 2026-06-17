#!/usr/bin/env python3
"""Versioned allowlist registry for future bounded MCP repo commands.

Stage 33 only defines and validates deterministic command entries. It does not
execute commands and it is not an MCP tool surface.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .common import find_repo_root, safety_flags, utc_iso
except ImportError:  # pragma: no cover - direct script execution fallback.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, safety_flags, utc_iso


SCHEMA_VERSION = 1
REGISTRY_VERSION = "bounded-repo-command-registry-v1"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_PARAMETER_VALUE_CHARS = 400
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
            expected_exit_codes=(0, 2),
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
    if args.repo_root:
        find_repo_root(Path(args.repo_root))
    if args.self_test:
        payload = self_test()
    elif args.plan:
        payload = plan_command(
            args.plan,
            load_parameters(args.parameters_json),
            expected_registry_version=args.expected_registry_version,
            timeout_seconds=args.timeout_seconds,
        )
    else:
        payload = registry_payload()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
