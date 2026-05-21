#!/usr/bin/env python3
"""Build a local RiftReader decision packet with safe automation reminders.

This helper is intentionally a control-plane gate, not a live-action executor:
no live input, movement, CE/x64dbg attach, provider writes, staging, committing,
pushing, branch rewrites, cleanup/delete operations, or proof promotion.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from .common import find_repo_root, preview_text, repo_rel, run_command_envelope, safety_flags, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.common import find_repo_root, preview_text, repo_rel, run_command_envelope, safety_flags, utc_iso


SCHEMA_VERSION = 1
HELPER_VERSION = "0.1.1"
DEFAULT_CURRENT_TRUTH_JSON = Path("docs") / "recovery" / "current-truth.json"
DEFAULT_CURRENT_PROOF_JSON = Path("docs") / "recovery" / "current-proof-anchor-readback.json"
DEFAULT_OUTPUT_DIR = Path(".riftreader-local") / "decision-packet" / "latest"
GENERATED_PREFIXES = (
    ".riftreader-local/",
    "scripts/captures/",
    "tools/rift-game-mcp/.runtime/",
    "artifacts/chatgpt-payloads/",
)
LIVE_TRUTH_PATHS = (
    "docs/recovery/current-truth.json",
    "docs/recovery/current-truth.md",
    "docs/recovery/current-proof-anchor-readback.json",
)
RETIRED_OPENCODE_PATH_PATTERNS = (
    ".opencode/*",
    "opencode/*",
    "docs/handoffs/*opencode*",
    "docs/workflow/*opencode*",
    "scripts/*opencode*",
    "tools/riftreader_workflow/*opencode*",
)
RETIRED_OPENCODE_POLICY = "retired-opencode-requires-explicit-reauthorization"
FORBIDDEN_ACTIONS = [
    "movement",
    "live_input",
    "target_control",
    "proofonly",
    "x64dbg_attach",
    "cheat_engine",
    "provider_write",
    "git_stage",
    "git_commit",
    "git_push",
    "branch_rewrite",
    "cleanup_delete",
    "proof_promotion",
    "actor_chain_promotion",
    "retired_opencode_work_without_explicit_reauthorization",
]
ALLOWED_ACTIONS = [
    "read_repo",
    "inspect_git",
    "read_current_truth_artifacts",
    "read_status_artifacts",
    "write_ignored_decision_packet_artifacts",
    "run_safe_validations_when_explicitly_requested",
]
MILESTONE_STATES = {
    "not-started",
    "in-progress",
    "passed",
    "blocked-safe",
    "blocked-needs-approval",
    "failed",
}


def safe_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def try_load_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return load_json_object(path), None
    except Exception as exc:  # noqa: BLE001 - helper must fail closed with structured packet errors.
        return None, f"{type(exc).__name__}: {exc}"


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def is_generated_path(path: str) -> bool:
    normalized = normalize_path(path).lower()
    return any(normalized.startswith(prefix) for prefix in GENERATED_PREFIXES)


def is_live_truth_path(path: str) -> bool:
    normalized = normalize_path(path).lower()
    return normalized in LIVE_TRUTH_PATHS


def is_retired_opencode_path(path: str) -> bool:
    normalized = normalize_path(path).lower()
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in RETIRED_OPENCODE_PATH_PATTERNS)


def retired_surface_paths(git_state: dict[str, Any]) -> list[str]:
    paths = {
        normalize_path(str(item.get("path") or ""))
        for item in safe_list(git_state.get("changedFiles"))
        if item.get("path") and is_retired_opencode_path(str(item.get("path")))
    }
    return sorted(paths)


def build_retired_surface_guardrail(git_state: dict[str, Any]) -> dict[str, Any]:
    paths = retired_surface_paths(git_state)
    if not paths:
        return {"paths": [], "blockers": [], "warnings": []}
    return {
        "paths": paths,
        "blockers": ["retired-opencode-surface-changed"],
        "warnings": [f"{RETIRED_OPENCODE_POLICY}:{path}" for path in paths],
    }


def commit_path_category(path: str) -> str:
    normalized = normalize_path(path).lower()
    if normalized.endswith(".md"):
        return "docs"
    if normalized.endswith((".py", ".cmd", ".cs", ".csproj", ".sln", ".slnx")):
        return "code"
    if normalized.endswith((".json", ".jsonc", ".toml", ".yml", ".yaml")):
        return "config"
    return "other"


def quote_stage_path(path: str) -> str:
    if not path:
        return "''"
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/\\:")
    if all(char in safe_chars for char in path):
        return path
    return "'" + path.replace("'", "''") + "'"


def parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_hwnd(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.lower()


def same_text(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return True
    return str(a).strip().lower() == str(b).strip().lower()


def target_from_document(document: dict[str, Any] | None) -> dict[str, Any]:
    target = safe_mapping(safe_mapping(document).get("target"))
    return {
        "processName": target.get("processName"),
        "pid": target.get("processId") if target.get("processId") is not None else target.get("pid"),
        "hwnd": target.get("targetWindowHandle") if target.get("targetWindowHandle") is not None else target.get("hwnd"),
        "processStartUtc": target.get("processStartUtc") or target.get("processStartTimeUtc"),
        "moduleBase": target.get("moduleBase"),
        "windowTitle": target.get("windowTitle"),
        "inWorld": target.get("inWorld"),
        "live": target.get("live"),
        "status": target.get("status"),
    }


def strip_command_output(envelope: dict[str, Any]) -> dict[str, Any]:
    result = dict(envelope)
    result.pop("stdout", None)
    result.pop("stderr", None)
    return result


def collect_git(repo_root: Path) -> dict[str, Any]:
    status_env = run_command_envelope(
        "git-status-short-branch",
        ["git", "--no-pager", "status", "--short", "--branch", "--untracked-files=all"],
        repo_root,
        timeout_seconds=20,
        expected_exit_codes={0},
        capture_full_output=True,
    )
    head_env = run_command_envelope(
        "git-head",
        ["git", "--no-pager", "log", "-1", "--format=%h%x00%s"],
        repo_root,
        timeout_seconds=20,
        expected_exit_codes={0},
        capture_full_output=True,
    )
    status_text = str(status_env.get("stdout") or "")
    branch = None
    upstream = None
    ahead = 0
    behind = 0
    changed: list[dict[str, Any]] = []
    for line in status_text.splitlines():
        if line.startswith("## "):
            branch_text = line[3:]
            branch_part = branch_text.split(" [", 1)[0]
            if "..." in branch_part:
                branch, upstream = branch_part.split("...", 1)
            else:
                branch = branch_part
            if "ahead " in branch_text:
                try:
                    ahead = int(branch_text.split("ahead ", 1)[1].split("]", 1)[0].split(",", 1)[0])
                except ValueError:
                    ahead = 0
            if "behind " in branch_text:
                try:
                    behind = int(branch_text.split("behind ", 1)[1].split("]", 1)[0].split(",", 1)[0])
                except ValueError:
                    behind = 0
            continue
        if not line:
            continue
        status_code = line[:2]
        raw_path = line[3:] if len(line) > 3 else ""
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1]
        changed.append(
            {
                "status": status_code,
                "path": raw_path,
                "generated": is_generated_path(raw_path),
                "liveTruth": is_live_truth_path(raw_path),
                "retiredSurface": is_retired_opencode_path(raw_path),
                "retiredSurfacePolicy": RETIRED_OPENCODE_POLICY if is_retired_opencode_path(raw_path) else None,
            }
        )
    head_hash = None
    head_subject = None
    if head_env.get("ok"):
        head_line = str(head_env.get("stdout") or "").strip()
        if "\x00" in head_line:
            head_hash, head_subject = head_line.split("\x00", 1)
    return {
        "branch": branch,
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "dirty": bool(changed),
        "changedFiles": changed,
        "head": {"hash": head_hash, "subject": head_subject},
        "commands": [strip_command_output(status_env), strip_command_output(head_env)],
    }


def classify_target_epoch(truth: dict[str, Any] | None, proof: dict[str, Any] | None) -> dict[str, Any]:
    truth = safe_mapping(truth)
    proof = safe_mapping(proof)
    truth_target = target_from_document(truth)
    proof_target = target_from_document(proof)
    blockers: list[str] = []
    warnings: list[str] = []
    stale_fields: list[str] = []
    proof_status = proof.get("status")
    target_status_text = " ".join(str(item or "") for item in (truth_target.get("status"), truth.get("status"))).lower()

    if not truth_target.get("pid") and not proof_target.get("pid"):
        status = "absent"
        blockers.append("target-epoch-absent")
    elif not truth_target.get("pid") and proof_target.get("pid"):
        status = "in-world-unproven"
        blockers.append("current-truth-target-missing")
    elif "character" in target_status_text and "select" in target_status_text:
        status = "character-select"
        blockers.append("target-at-character-select-movement-blocked")
    else:
        comparisons = (
            ("pid", truth_target.get("pid"), proof_target.get("pid"), "target-epoch-pid-drift"),
            ("hwnd", normalize_hwnd(truth_target.get("hwnd")), normalize_hwnd(proof_target.get("hwnd")), "target-epoch-hwnd-drift"),
            (
                "processStartUtc",
                truth_target.get("processStartUtc"),
                proof_target.get("processStartUtc"),
                "target-epoch-process-start-drift",
            ),
            ("moduleBase", truth_target.get("moduleBase"), proof_target.get("moduleBase"), "target-epoch-module-base-drift"),
        )
        for field, truth_value, proof_value, blocker in comparisons:
            if truth_value is not None and proof_value is not None and not same_text(truth_value, proof_value):
                stale_fields.append(field)
                blockers.append(blocker)
        proof_updated = parse_iso(proof.get("lastUpdatedUtc") or proof.get("updatedAtUtc"))
        process_start = parse_iso(truth_target.get("processStartUtc"))
        if proof_updated and process_start and proof_updated < process_start:
            stale_fields.append("proofLastUpdatedUtc")
            blockers.append("proof-older-than-process-start")
        if stale_fields or str(proof_status or "").startswith("blocked-target-drift"):
            status = "stale"
        elif proof_status in {"current-target-proofonly-passed", "passed-proof-only", "valid", "passed"}:
            status = "current" if truth_target.get("inWorld") is not False else "in-world-unproven"
            if status == "in-world-unproven":
                blockers.append("target-not-confirmed-in-world")
        elif truth_target.get("live"):
            status = "in-world-unproven"
            blockers.append("current-proof-not-confirmed")
        else:
            status = "unknown"
            warnings.append("target-epoch-could-not-be-proven-current")

    return {
        "status": status,
        "target": truth_target,
        "proofTarget": proof_target,
        "proofStatus": proof_status,
        "staleFields": stale_fields,
        "blockers": sorted(set(blockers)),
        "warnings": warnings,
        "processPresence": "not-checked-process-presence-is-not-proof",
        "staleAddressPolicy": "absolute heap addresses are historical hints only after PID/HWND/process-start/module-base drift",
    }


def summarize_truth(truth: dict[str, Any] | None, proof: dict[str, Any] | None) -> dict[str, Any]:
    truth = safe_mapping(truth)
    proof = safe_mapping(proof)
    best_candidate = safe_mapping(truth.get("bestCurrentCandidate"))
    static_status = safe_mapping(truth.get("staticChainStatus"))
    proof_latest_validation = safe_mapping(proof.get("latestValidation"))
    proof_latest_proofonly = safe_mapping(proof.get("latestProofOnly"))
    candidate_only = bool(best_candidate.get("candidateOnly") or "candidate" in str(best_candidate.get("status") or "").lower())
    promotion_allowed = bool(best_candidate.get("promotionEligible") or static_status.get("promotionAllowed"))
    actor_blockers = [str(item) for item in safe_list(static_status.get("blockers"))]
    if candidate_only:
        actor_blockers.append("actor-chain-candidate-only")
    if best_candidate and not promotion_allowed:
        actor_blockers.append("no-static-resolver-promoted")
    actor_status = "unknown"
    if promotion_allowed:
        actor_status = "promoted"
    elif best_candidate:
        actor_status = "candidate-only" if candidate_only else "blocked"
    return {
        "proofAnchor": {
            "status": proof.get("status"),
            "movementAllowed": proof_latest_validation.get("movementAllowed"),
            "movementSent": proof_latest_validation.get("movementSent") or proof_latest_proofonly.get("movementSent"),
            "candidateAddressHex": safe_mapping(proof.get("riftscanCandidateSource")).get("sourceAbsoluteAddressHex"),
            "candidateOnly": False,
        },
        "actorChain": {
            "status": actor_status,
            "candidateId": best_candidate.get("candidateId"),
            "addressHex": best_candidate.get("addressHex"),
            "promotionAllowed": promotion_allowed,
            "candidateOnly": candidate_only,
            "blockers": sorted(set(actor_blockers)),
            "reusePolicy": best_candidate.get("reusePolicy"),
        },
    }


def classify_lane(git_state: dict[str, Any], target_epoch: dict[str, Any], truth_summary: dict[str, Any]) -> str:
    paths = [normalize_path(str(item.get("path") or "")).lower() for item in safe_list(git_state.get("changedFiles"))]
    if any("package" in path for path in paths):
        return "package"
    if any("mcp" in path or "chatgpt" in path for path in paths):
        return "mcp"
    if any("actor_chain" in path or "current-truth" in path or "current-proof" in path for path in paths):
        return "actor-chain"
    if paths and all(path.endswith(".md") for path in paths):
        return "docs"
    if target_epoch.get("status") == "stale":
        return "proof-recovery"
    if safe_mapping(truth_summary.get("actorChain")).get("status") in {"candidate-only", "blocked"}:
        return "actor-chain"
    if git_state.get("dirty"):
        return "git"
    return "unknown"


def classify_risk(lane: str, git_state: dict[str, Any], target_epoch: dict[str, Any]) -> str:
    paths = [normalize_path(str(item.get("path") or "")).lower() for item in safe_list(git_state.get("changedFiles"))]
    if target_epoch.get("status") == "stale":
        return "high"
    if lane in {"actor-chain", "proof-recovery"}:
        return "high"
    if any(path.endswith(".py") or path.endswith(".cmd") for path in paths):
        return "medium"
    if lane == "docs":
        return "low"
    if lane in {"mcp", "package", "git"}:
        return "medium"
    return "low"


def command_spec(label: str, command: list[str], why: str, *, expected: Iterable[int] = (0,), timeout: float = 120.0) -> dict[str, Any]:
    return {
        "label": label,
        "command": command,
        "expectedExitCodes": list(expected),
        "timeoutSeconds": timeout,
        "safe": True,
        "mutatesTrackedFiles": False,
        "why": why,
    }


def build_validation_plan(git_state: dict[str, Any], lane: str) -> dict[str, Any]:
    changed_items = [safe_mapping(item) for item in safe_list(git_state.get("changedFiles"))]
    paths = [normalize_path(str(item.get("path") or "")) for item in changed_items]
    lower_paths = [path.lower() for path in paths]
    retired_paths = retired_surface_paths(git_state)
    changed_python_paths = [
        normalize_path(str(item.get("path") or ""))
        for item in changed_items
        if normalize_path(str(item.get("path") or "")).lower().endswith(".py") and "D" not in str(item.get("status") or "")
    ]
    commands: list[dict[str, Any]] = [
        command_spec("diff-check", ["git", "--no-pager", "diff", "--check"], "Check whitespace/errors in current diff."),
        command_spec(
            "policy-lint-changed",
            ["python", "tools\\riftreader_workflow\\policy_lint.py", "--json", "validate-repo", "--scope", "changed", "--no-write-summary"],
            "Run changed-scope policy lint without writing tracked summaries.",
        ),
    ]
    if any(path.endswith(".py") for path in lower_paths) or any("decision_packet" in path for path in lower_paths):
        compile_paths = list(changed_python_paths)
        if any("decision_packet" in path for path in lower_paths):
            compile_paths.extend(["tools/riftreader_workflow/decision_packet.py", "scripts/test_decision_packet.py"])
        compile_paths = list(dict.fromkeys(compile_paths)) or ["tools/riftreader_workflow/decision_packet.py", "scripts/test_decision_packet.py"]
        commands.append(
            command_spec(
                "py-compile-decision-packet",
                ["python", "-m", "py_compile", *compile_paths],
                "Compile changed Python files and decision packet tests when relevant.",
            )
        )
    if any("decision_packet" in path or "riftreader-decision-packet" in path for path in lower_paths) or not paths:
        commands.append(
            command_spec(
                "decision-packet-tests",
                ["python", "-m", "unittest", "scripts.test_decision_packet"],
                "Run focused decision packet unit tests.",
            )
        )
        commands.append(
            command_spec(
                "decision-packet-self-test",
                ["python", "tools/riftreader_workflow/decision_packet.py", "--self-test", "--json"],
                "Run fixture-only decision packet self-test.",
            )
        )
    if lane == "actor-chain" or any("actor_chain" in path for path in lower_paths):
        commands.append(
            command_spec(
                "actor-chain-status-tests",
                ["python", "-m", "unittest", "scripts.test_actor_chain_no_debug_status"],
                "Validate actor-chain no-debug status helper behavior.",
            )
        )
    if not retired_paths and any("opencode_bridge" in path or "test_opencode" in path for path in lower_paths):
        commands.append(
            command_spec(
                "opencode-bridge-tests",
                ["python", "-m", "unittest", "scripts.test_opencode_bridge", "scripts.test_opencode_status_packet"],
                "Validate OpenCode prompt/status integration.",
            )
        )
    if any(
        path in {
            "agents.md",
            "docs/workflow/codex-agent-routing-policy.md",
            "docs/workflow/local-decision-control-plane-plan.md",
            "scripts/test_retired_surface_policy.py",
        }
        for path in lower_paths
    ):
        commands.append(
            command_spec(
                "retired-surface-policy-tests",
                ["python", "-m", "unittest", "scripts.test_retired_surface_policy"],
                "Validate retired OpenCode surface policy remains durable in primary docs.",
            )
        )
    if any("operator_lite" in path or "test_operator_lite" in path for path in lower_paths):
        commands.append(
            command_spec(
                "operator-lite-tests",
                ["python", "-m", "unittest", "scripts.test_operator_lite"],
                "Validate Operator Lite safe command registry.",
                timeout=180,
            )
        )
    return {
        "mode": "recommend-only unless --run-safe-checks is supplied",
        "commands": commands,
        "allCommandsClassifiedSafe": all(item.get("safe") and not item.get("mutatesTrackedFiles") for item in commands),
    }


def build_commit_plan(git_state: dict[str, Any], validation_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    changed = safe_list(git_state.get("changedFiles"))
    explicit_paths = [str(item.get("path")) for item in changed if item.get("path") and not item.get("generated")]
    excluded_generated = [str(item.get("path")) for item in changed if item.get("path") and item.get("generated")]
    live_truth_paths = [path for path in explicit_paths if is_live_truth_path(path)]
    retired_paths = retired_surface_paths(git_state)
    failed_validation = [item for item in validation_results or [] if item.get("ok") is not True]
    categories = sorted({commit_path_category(path) for path in explicit_paths})
    if not explicit_paths:
        return {
            "recommended": False,
            "reason": "no-stageable-tracked-paths",
            "explicitPaths": [],
            "excludedGeneratedPaths": excluded_generated,
            "validationRequired": False,
            "stageCommand": None,
            "stageCommandPreview": None,
        }
    if live_truth_paths:
        return {
            "recommended": False,
            "reason": "live-truth-paths-require-main-agent-review",
            "explicitPaths": explicit_paths,
            "excludedGeneratedPaths": excluded_generated,
            "validationRequired": True,
            "stageCommand": None,
            "stageCommandPreview": None,
        }
    if retired_paths:
        return {
            "recommended": False,
            "reason": "retired-opencode-surface-requires-explicit-reauthorization",
            "explicitPaths": explicit_paths,
            "excludedGeneratedPaths": excluded_generated,
            "retiredSurfacePaths": retired_paths,
            "validationRequired": True,
            "stageCommand": None,
            "stageCommandPreview": None,
        }
    if len(categories) > 1:
        return {
            "recommended": False,
            "reason": "mixed-risk-worktree-split-required",
            "explicitPaths": explicit_paths,
            "excludedGeneratedPaths": excluded_generated,
            "pathCategories": categories,
            "validationRequired": True,
            "stageCommand": None,
            "stageCommandPreview": None,
        }
    if failed_validation:
        return {
            "recommended": False,
            "reason": "validation-not-passed",
            "explicitPaths": explicit_paths,
            "excludedGeneratedPaths": excluded_generated,
            "validationRequired": True,
            "stageCommand": None,
            "stageCommandPreview": None,
        }
    if any("decision" in path for path in explicit_paths):
        suggested = "Update local decision control plane"
    elif categories == ["docs"]:
        suggested = "Update RiftReader workflow docs"
    elif categories == ["code"]:
        suggested = "Update RiftReader workflow helpers"
    elif categories == ["config"]:
        suggested = "Update RiftReader workflow configuration"
    else:
        suggested = "Update RiftReader workflow files"
    return {
        "recommended": True,
        "reason": "coherent-explicit-path-slice" if validation_results else "validation-required-before-commit",
        "suggestedMessage": suggested,
        "explicitPaths": explicit_paths,
        "excludedGeneratedPaths": excluded_generated,
        "pathCategories": categories,
        "validationRequired": not bool(validation_results),
        "stageCommand": ["git", "add", "--", *explicit_paths],
        "stageCommandPreview": "git add -- " + " ".join(quote_stage_path(path) for path in explicit_paths),
    }


def build_agent_plan() -> list[dict[str, Any]]:
    return [
        {
            "name": "core-helper",
            "authority": "write",
            "ownedPaths": ["tools/riftreader_workflow/decision_packet.py"],
            "forbiddenPaths": ["scripts/test_decision_packet.py", "docs/**"],
            "risk": "medium",
            "validation": ["python -m py_compile tools/riftreader_workflow/decision_packet.py"],
        },
        {
            "name": "tests",
            "authority": "write",
            "ownedPaths": ["scripts/test_decision_packet.py"],
            "forbiddenPaths": ["tools/riftreader_workflow/decision_packet.py"],
            "risk": "low",
            "validation": ["python -m unittest scripts.test_decision_packet"],
        },
        {
            "name": "docs",
            "authority": "write",
            "ownedPaths": ["docs/workflow/local-decision-control-plane-plan.md"],
            "forbiddenPaths": ["tools/**", "scripts/**"],
            "risk": "low",
            "validation": ["git --no-pager diff --check"],
        },
    ]


def validate_agent_plan(agent_plan: list[dict[str, Any]]) -> list[str]:
    owners: dict[str, str] = {}
    errors: list[str] = []
    required_fields = ("name", "authority", "ownedPaths", "forbiddenPaths", "risk", "validation")
    valid_authorities = {"read", "write"}
    valid_risks = {"low", "medium", "high"}
    for item in agent_plan:
        name = str(item.get("name") or "unnamed-agent")
        for field in required_fields:
            if field not in item:
                errors.append(f"agent-plan-missing-field:{name}:{field}")
        authority = str(item.get("authority") or "").strip().lower()
        if authority not in valid_authorities:
            errors.append(f"agent-plan-invalid-authority:{name}:{authority or 'missing'}")
        risk = str(item.get("risk") or "").strip().lower()
        if risk not in valid_risks:
            errors.append(f"agent-plan-invalid-risk:{name}:{risk or 'missing'}")
        owned_paths = [normalize_path(str(path)) for path in safe_list(item.get("ownedPaths")) if str(path).strip()]
        if not owned_paths:
            errors.append(f"agent-plan-empty-owned-paths:{name}")
        if not safe_list(item.get("validation")):
            errors.append(f"agent-plan-empty-validation:{name}")
        forbidden_patterns = [normalize_path(str(pattern)) for pattern in safe_list(item.get("forbiddenPaths"))]
        for normalized_path in owned_paths:
            if normalized_path in owners:
                errors.append(f"agent-plan-overlapping-owned-path:{normalized_path}:{owners[normalized_path]}:{name}")
            for pattern in forbidden_patterns:
                if fnmatch.fnmatch(normalized_path, pattern):
                    errors.append(f"agent-plan-owned-path-forbidden:{normalized_path}:{name}:{pattern}")
            owners[normalized_path] = name
    return errors


def build_safe_next_action(lane: str, target_epoch: dict[str, Any], git_state: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    retired_paths = retired_surface_paths(git_state)
    if retired_paths:
        return {
            "key": "retired-opencode-surface-review",
            "command": ["git", "--no-pager", "diff", "--", *retired_paths],
            "why": "Retired OpenCode surfaces changed; inspect/revert or get explicit reauthorization before validation, staging, or commit.",
        }
    if target_epoch.get("status") == "stale":
        return {
            "key": "refresh-coordinate-recovery-status",
            "command": ["python", ".\\scripts\\coordinate_recovery_status.py", "--json"],
            "why": "Target epoch drift blocks proof reuse; refresh safe current-target status before any live/proof work.",
        }
    if git_state.get("dirty"):
        return {
            "key": "run-safe-decision-checks",
            "command": ["python", "tools\\riftreader_workflow\\decision_packet.py", "--run-safe-checks", "--json"],
            "why": "Dirty worktree exists; run only safe validations before commit planning.",
        }
    if int(git_state.get("ahead") or 0) > 0:
        return {
            "key": "report-local-commits-ahead",
            "command": ["git", "--no-pager", "status", "--short", "--branch"],
            "why": "Branch is ahead of origin; report local commits and wait for explicit push approval.",
        }
    actor = safe_mapping(truth.get("actorChain"))
    if actor.get("status") == "candidate-only":
        return {
            "key": "actor-chain-no-debug-status",
            "command": ["python", ".\\scripts\\actor_chain_no_debug_status.py", "--json"],
            "why": "Actor-chain evidence is candidate-only; keep using the no-debug status gate.",
        }
    return {
        "key": "compact-workflow-status",
        "command": [".\\scripts\\riftreader-workflow-status.cmd", "--compact-json"],
        "why": "Refresh compact local truth before choosing another lane.",
    }


def build_post_validation_next_action(run_safe_checks: bool, commit_plan: dict[str, Any]) -> dict[str, Any] | None:
    if not run_safe_checks or commit_plan.get("recommended") is not True:
        return None
    return {
        "key": "commit-ready-explicit-paths",
        "command": ["git", "--no-pager", "status", "--short", "--branch"],
        "why": "Safe validations passed and commitPlan is explicit-path ready; review status plus commitPlan.stageCommandPreview instead of rerunning validations.",
    }


def milestone_state(blockers: list[str], validation_results: list[dict[str, Any]] | None = None) -> str:
    if validation_results and any(item.get("ok") is not True for item in validation_results):
        return "failed"
    approval_tokens = (
        "requires-approval",
        "live-input-required",
        "debugger-required",
        "cheat-engine-required",
        "provider-write-required",
        "proof-promotion-requested",
        "actor-chain-promotion-requested",
    )
    approval_blockers = [item for item in blockers if any(token in item for token in approval_tokens)]
    if approval_blockers:
        return "blocked-needs-approval"
    if blockers:
        return "blocked-safe"
    return "passed"


def build_llm_reminder(safe_next_action: dict[str, Any], state: str) -> dict[str, Any]:
    return {
        "banner": "# **🚦 NEXT ACTION — CONTINUE SAFELY**",
        "state": state,
        "doNotStopIf": [
            "safe validation passed",
            "status helper returned a known blocker",
            "worktree is clean but ahead of origin",
            "generated ignored artifacts were written",
        ],
        "mustStopIf": [
            "live input would be required",
            "debugger or CE would be required",
            "provider write would be required",
            "proof or actor-chain promotion would be claimed",
            "retired OpenCode surface work would proceed without explicit reauthorization",
            "Git mutation is requested but scope is mixed or unvalidated",
        ],
        "continueWith": safe_next_action,
    }


def build_fingerprint(repo_root: Path, git_state: dict[str, Any], truth_path: Path, proof_path: Path) -> dict[str, Any]:
    def stat(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"path": repo_rel(repo_root, path), "exists": False}
        info = path.stat()
        return {"path": repo_rel(repo_root, path), "exists": True, "mtimeNs": info.st_mtime_ns, "sizeBytes": info.st_size}

    def changed_stat(item: dict[str, Any]) -> dict[str, Any]:
        path_text = str(item.get("path") or "")
        path = repo_root / path_text
        return {
            "path": path_text,
            "status": item.get("status"),
            "generated": bool(item.get("generated")),
            "liveTruth": bool(item.get("liveTruth")),
            "retiredSurface": bool(item.get("retiredSurface")),
            "file": stat(path),
        }

    return {
        "helperVersion": HELPER_VERSION,
        "gitHead": safe_mapping(git_state.get("head")).get("hash"),
        "changedFiles": [changed_stat(safe_mapping(item)) for item in safe_list(git_state.get("changedFiles"))],
        "currentTruth": stat(truth_path),
        "currentProof": stat(proof_path),
    }


def resolve_output_dir(repo_root: Path, output_dir: Path) -> Path:
    return output_dir if output_dir.is_absolute() else repo_root / output_dir


def load_cached_packet(repo_root: Path, output_dir: Path, fingerprint: dict[str, Any]) -> dict[str, Any] | None:
    output_dir = resolve_output_dir(repo_root, output_dir)
    packet_path = output_dir / "decision-packet.json"
    fingerprint_path = output_dir / "fingerprint.json"
    if not packet_path.is_file() or not fingerprint_path.is_file():
        return None
    cached_fingerprint, fingerprint_error = try_load_json_object(fingerprint_path)
    if fingerprint_error:
        return None
    if cached_fingerprint != fingerprint:
        return None
    packet, packet_error = try_load_json_object(packet_path)
    if packet_error:
        return None
    if not packet:
        return None
    if packet.get("schemaVersion") != SCHEMA_VERSION or packet.get("helperVersion") != HELPER_VERSION:
        return None
    packet["cacheStatus"] = "reused"
    packet["cacheCheckedAtUtc"] = utc_iso()
    packet["cacheSafety"] = {
        "freshFingerprintChecked": True,
        "reusedOnlyWhenFingerprintMatched": True,
        "runSafeChecksDisablesCache": True,
        "fingerprintInputs": [
            "helperVersion",
            "gitHead",
            "changedFiles.path",
            "changedFiles.status",
            "changedFiles.file.mtimeNs",
            "changedFiles.file.sizeBytes",
            "currentTruth.mtimeNs",
            "currentTruth.sizeBytes",
            "currentProof.mtimeNs",
            "currentProof.sizeBytes",
        ],
        "doesNotAuthorizeLiveInput": True,
        "doesNotAuthorizeProofPromotion": True,
    }
    return packet


def run_safe_validations(repo_root: Path, validation_plan: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in safe_list(validation_plan.get("commands")):
        if not item.get("safe") or item.get("mutatesTrackedFiles"):
            results.append({"label": item.get("label"), "ok": False, "blocked": True, "error": "unsafe-validation-command"})
            continue
        expected = {int(code) for code in item.get("expectedExitCodes") or [0]}
        envelope = run_command_envelope(
            str(item.get("label") or "validation"),
            [str(part) for part in item.get("command") or []],
            repo_root,
            timeout_seconds=float(item.get("timeoutSeconds") or 120.0),
            expected_exit_codes=expected,
        )
        envelope["expectedExitCodes"] = sorted(expected)
        envelope["knownSafeBlocked"] = envelope.get("exitCode") == 2 and 2 in expected
        envelope["nextIfPassed"] = "continue-to-next-safe-milestone"
        envelope["nextIfBlockedOrFailed"] = "diagnose-this-command-before-broadening-scope"
        results.append(envelope)
    return results


def build_decision_packet(
    repo_root: Path,
    *,
    run_safe_checks: bool = False,
    truth_json: Path | None = None,
    proof_json: Path | None = None,
    use_cache: bool = False,
    cache_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    build_started = time.monotonic()
    truth_path = repo_root / (truth_json or DEFAULT_CURRENT_TRUTH_JSON)
    proof_path = repo_root / (proof_json or DEFAULT_CURRENT_PROOF_JSON)
    warnings: list[str] = []
    errors: list[str] = []
    git_state = collect_git(repo_root)
    fingerprint = build_fingerprint(repo_root, git_state, truth_path, proof_path)
    if use_cache and not run_safe_checks:
        cached = load_cached_packet(repo_root, cache_dir, fingerprint)
        if cached is not None:
            cached["performance"] = {
                **safe_mapping(cached.get("performance")),
                "buildMode": "cache-reused",
                "cacheReused": True,
                "runSafeChecks": False,
                "totalDurationSeconds": round(time.monotonic() - build_started, 3),
            }
            return cached
    truth, truth_error = try_load_json_object(truth_path)
    proof, proof_error = try_load_json_object(proof_path)
    malformed_blockers: list[str] = []
    if truth_error:
        errors.append(f"current-truth-malformed:{repo_rel(repo_root, truth_path)}:{preview_text(truth_error)}")
        malformed_blockers.append("current-truth-malformed")
    if proof_error:
        errors.append(f"current-proof-malformed:{repo_rel(repo_root, proof_path)}:{preview_text(proof_error)}")
        malformed_blockers.append("current-proof-malformed")
    if truth is None:
        if not truth_error:
            warnings.append(f"current-truth-missing:{repo_rel(repo_root, truth_path)}")
    if proof is None:
        if not proof_error:
            warnings.append(f"current-proof-missing:{repo_rel(repo_root, proof_path)}")
    target_epoch = classify_target_epoch(truth, proof)
    retired_guardrail = build_retired_surface_guardrail(git_state)
    warnings.extend(str(item) for item in retired_guardrail.get("warnings") or [])
    if malformed_blockers:
        target_epoch = {
            **target_epoch,
            "status": "invalid-artifact",
            "blockers": sorted(set(safe_list(target_epoch.get("blockers")) + malformed_blockers)),
            "proofUseAllowed": False,
        }
    truth_summary = summarize_truth(truth, proof)
    lane = classify_lane(git_state, target_epoch, truth_summary)
    risk = classify_risk(lane, git_state, target_epoch)
    blockers: list[str] = []
    blockers.extend(malformed_blockers)
    blockers.extend(str(item) for item in retired_guardrail.get("blockers") or [])
    blockers.extend(str(item) for item in target_epoch.get("blockers") or [])
    blockers.extend(str(item) for item in safe_mapping(truth_summary.get("actorChain")).get("blockers") or [] if lane == "actor-chain")
    agent_plan = build_agent_plan()
    errors.extend(validate_agent_plan(agent_plan))
    validation_plan = build_validation_plan(git_state, lane)
    validation_results = run_safe_validations(repo_root, validation_plan) if run_safe_checks else []
    validation_duration = round(sum(float(item.get("durationSeconds") or 0.0) for item in validation_results), 3)
    if validation_results and any(item.get("ok") is not True for item in validation_results):
        blockers.append("safe-validation-failed")
    state = milestone_state(sorted(set(blockers)), validation_results)
    commit_plan = build_commit_plan(git_state, validation_results if run_safe_checks else None)
    safe_next_action = build_post_validation_next_action(run_safe_checks, commit_plan) or build_safe_next_action(
        lane, target_epoch, git_state, truth_summary
    )
    status = "failed" if errors or state == "failed" else ("blocked" if blockers else "passed")
    packet = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-decision-packet",
        "helperVersion": HELPER_VERSION,
        "generatedAtUtc": utc_iso(),
        "status": status,
        "lane": lane,
        "risk": risk,
        "repoRoot": str(repo_root),
        "repo": git_state,
        "targetEpoch": target_epoch,
        "truth": truth_summary,
        "allowedActions": list(ALLOWED_ACTIONS),
        "forbiddenActions": list(FORBIDDEN_ACTIONS),
        "safeNextAction": safe_next_action,
        "automationPlan": {
            "level": "validation-runner" if run_safe_checks else "packet-only",
            "runSafeChecksRequested": run_safe_checks,
            "safeChecksRun": bool(validation_results),
            "forbiddenAutomation": list(FORBIDDEN_ACTIONS),
            "allowedAutomation": list(ALLOWED_ACTIONS),
        },
        "validationPlan": validation_plan,
        "validationResults": validation_results,
        "commitPlan": commit_plan,
        "agentPlan": agent_plan,
        "llmReminder": build_llm_reminder(safe_next_action, state),
        "milestoneStatus": {
            "state": state,
            "validStates": sorted(MILESTONE_STATES),
            "banner": milestone_banner(state),
            "nextCommand": safe_next_action.get("command"),
        },
        "fingerprint": fingerprint,
        "cacheStatus": "miss" if use_cache else "not-checked",
        "performance": {
            "buildMode": "fresh",
            "cacheReused": False,
            "runSafeChecks": run_safe_checks,
            "safeValidationCommandCount": len(validation_results),
            "safeValidationDurationSeconds": validation_duration,
            "totalDurationSeconds": None,
        },
        "cacheSafety": {
            "freshFingerprintChecked": True,
            "reusedOnlyWhenFingerprintMatched": True,
            "runSafeChecksDisablesCache": True,
            "doesNotAuthorizeLiveInput": True,
            "doesNotAuthorizeProofPromotion": True,
        },
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings + [str(item) for item in target_epoch.get("warnings") or []])),
        "errors": errors,
        "safety": {
            **safety_flags(),
            "readOnlyDecisionPacket": True,
            "runSafeChecksRequested": run_safe_checks,
            "gitMutation": False,
            "providerWrites": False,
            "proofPromotion": False,
        },
    }
    packet["performance"]["totalDurationSeconds"] = round(time.monotonic() - build_started, 3)
    return packet


def milestone_banner(state: str) -> str:
    if state == "passed":
        return "# **🚦 MILESTONE — ✅ DONE, CONTINUE SAFELY**"
    if state == "blocked-safe":
        return "# **🚦 MILESTONE — ⚠️ BLOCKED SAFE, RUN SAFE DIAGNOSTIC**"
    if state == "blocked-needs-approval":
        return "# **🚦 MILESTONE — 🛑 APPROVAL REQUIRED**"
    if state == "failed":
        return "# **🚦 MILESTONE — ❌ FAILED, DIAGNOSE NARROWLY**"
    return "# **🚦 MILESTONE — 🔄 CONTINUING**"


def compact_decision_packet(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": packet.get("schemaVersion"),
        "kind": packet.get("kind"),
        "status": packet.get("status"),
        "lane": packet.get("lane"),
        "risk": packet.get("risk"),
        "targetEpoch": {
            "status": safe_mapping(packet.get("targetEpoch")).get("status"),
            "blockers": safe_mapping(packet.get("targetEpoch")).get("blockers"),
        },
        "safeNextAction": packet.get("safeNextAction"),
        "llmReminder": packet.get("llmReminder"),
        "milestoneStatus": packet.get("milestoneStatus"),
        "commitPlan": packet.get("commitPlan"),
        "agentPlan": packet.get("agentPlan"),
        "blockers": packet.get("blockers"),
        "warnings": packet.get("warnings"),
        "cacheStatus": packet.get("cacheStatus"),
        "performance": packet.get("performance"),
    }


def format_command(command: Any) -> str:
    if not isinstance(command, list):
        return ""
    return " ".join(str(part) for part in command)


def build_markdown(packet: dict[str, Any]) -> str:
    reminder = safe_mapping(packet.get("llmReminder"))
    safe_next = safe_mapping(packet.get("safeNextAction"))
    commit_plan = safe_mapping(packet.get("commitPlan"))
    lines = [
        "# RiftReader Decision Packet",
        "",
        str(reminder.get("banner") or "# **🚦 NEXT ACTION — CONTINUE SAFELY**"),
        "## **🔄 DO NOT STOP HERE**",
        "Run the listed safe command unless a hard stop condition is present.",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Status | `{packet.get('status')}` |",
        f"| Lane | `{packet.get('lane')}` |",
        f"| Risk | `{packet.get('risk')}` |",
        f"| Milestone state | `{safe_mapping(packet.get('milestoneStatus')).get('state')}` |",
        f"| Target epoch | `{safe_mapping(packet.get('targetEpoch')).get('status')}` |",
        f"| Cache | `{packet.get('cacheStatus')}` |",
        "",
        "## Safe next action",
        "",
        f"- Key: `{safe_next.get('key')}`",
        f"- Command: `{format_command(safe_next.get('command'))}`",
        f"- Why: {safe_next.get('why')}",
    ]
    lines.extend(["", "## Commit planner", ""])
    if commit_plan.get("recommended") and not commit_plan.get("validationRequired"):
        lines.append("# **✅ COMMIT-READY — EXPLICIT PATHS ONLY**")
        if commit_plan.get("suggestedMessage"):
            lines.append(f"- Suggested message: `{commit_plan.get('suggestedMessage')}`")
        if commit_plan.get("stageCommandPreview"):
            lines.append(f"- Stage preview: `{commit_plan.get('stageCommandPreview')}`")
        if commit_plan.get("stageCommand"):
            lines.append(f"- Stage command args: `{json.dumps(commit_plan.get('stageCommand'))}`")
    else:
        lines.append("# **⚠️ NOT COMMIT-READY**")
        if commit_plan.get("reason"):
            lines.append(f"- Reason: `{commit_plan.get('reason')}`")
        if commit_plan.get("validationRequired"):
            lines.append("- Validation required before staging.")
    explicit_paths = [str(item) for item in commit_plan.get("explicitPaths") or []]
    excluded_paths = [str(item) for item in commit_plan.get("excludedGeneratedPaths") or []]
    if explicit_paths:
        lines.extend(["", "### Explicit paths"])
        lines.extend(f"- `{path}`" for path in explicit_paths)
    if excluded_paths:
        lines.extend(["", "### Excluded generated paths"])
        lines.extend(f"- `{path}`" for path in excluded_paths)
    performance = safe_mapping(packet.get("performance"))
    if performance:
        lines.extend(
            [
                "",
                "## Performance",
                "",
                "| Field | Value |",
                "|---|---|",
                f"| Build mode | `{performance.get('buildMode')}` |",
                f"| Cache reused | `{str(bool(performance.get('cacheReused'))).lower()}` |",
                f"| Run safe checks | `{str(bool(performance.get('runSafeChecks'))).lower()}` |",
                f"| Safe validation commands | `{performance.get('safeValidationCommandCount')}` |",
                f"| Safe validation duration seconds | `{performance.get('safeValidationDurationSeconds')}` |",
                f"| Total duration seconds | `{performance.get('totalDurationSeconds')}` |",
            ]
        )
    if packet.get("blockers"):
        lines.extend(["", "## Blockers"])
        lines.extend(f"- `{item}`" for item in packet.get("blockers") or [])
    if packet.get("warnings"):
        lines.extend(["", "## Warnings"])
        lines.extend(f"- `{item}`" for item in packet.get("warnings") or [])
    lines.extend(["", "## LLM reminders", "", "### Do not stop if"])
    lines.extend(f"- {item}" for item in reminder.get("doNotStopIf") or [])
    lines.extend(["", "### Must stop if"])
    lines.extend(f"- {item}" for item in reminder.get("mustStopIf") or [])
    lines.extend(["", "## Validation plan", "", "| Label | Command |", "|---|---|"])
    for command in safe_mapping(packet.get("validationPlan")).get("commands") or []:
        lines.append(f"| `{command.get('label')}` | `{format_command(command.get('command'))}` |")
    if packet.get("validationResults"):
        lines.extend(["", "## Validation results", "", "| Label | Exit | OK |", "|---|---:|---:|"])
        for result in packet.get("validationResults") or []:
            lines.append(f"| `{result.get('label')}` | `{result.get('exitCode')}` | `{str(result.get('ok')).lower()}` |")
    lines.extend(["", "## Safety", "", "No live input, movement, x64dbg, CE, provider writes, Git mutation, or proof promotion is performed by this helper."])
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(repo_root: Path, packet: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir = resolve_output_dir(repo_root, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fingerprint_path = output_dir / "fingerprint.json"
    old_fingerprint = None
    if fingerprint_path.exists():
        old_fingerprint, _fingerprint_error = try_load_json_object(fingerprint_path)
    write_cache_status = "hit" if old_fingerprint == packet.get("fingerprint") else "miss"
    packet["cacheStatus"] = "reused" if packet.get("cacheStatus") == "reused" and write_cache_status == "hit" else write_cache_status
    json_path = output_dir / "decision-packet.json"
    compact_path = output_dir / "decision-packet-compact.json"
    markdown_path = output_dir / "decision-packet.md"
    fingerprint_path.write_text(json.dumps(packet.get("fingerprint"), indent=2), encoding="utf-8")
    artifacts = {
        "outputDir": repo_rel(repo_root, output_dir),
        "summaryJson": repo_rel(repo_root, json_path),
        "compactJson": repo_rel(repo_root, compact_path),
        "summaryMarkdown": repo_rel(repo_root, markdown_path),
        "fingerprint": repo_rel(repo_root, fingerprint_path),
    }
    packet["artifacts"] = artifacts
    json_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    compact_path.write_text(json.dumps(compact_decision_packet(packet), indent=2), encoding="utf-8")
    markdown_path.write_text(build_markdown(packet), encoding="utf-8")
    return artifacts


def build_self_test(repo_root: Path) -> dict[str, Any]:
    clean_git = {"dirty": False, "ahead": 1, "behind": 0, "changedFiles": [], "head": {"hash": "abc123"}}
    proof = {"status": "current-target-proofonly-passed", "target": {"processId": 1, "targetWindowHandle": "0x1"}}
    truth = {
        "target": {"processId": 1, "targetWindowHandle": "0x1", "inWorld": True, "live": True},
        "bestCurrentCandidate": {"candidateOnly": True, "promotionEligible": False, "candidateId": "c1"},
    }
    current = classify_target_epoch(truth, proof)
    stale = classify_target_epoch({"target": {"processId": 2, "targetWindowHandle": "0x1"}}, proof)
    agent_errors = validate_agent_plan(build_agent_plan())
    checks = [
        {"name": "current-target-classifies-current", "pass": current.get("status") == "current"},
        {"name": "pid-drift-classifies-stale", "pass": stale.get("status") == "stale" and "target-epoch-pid-drift" in stale.get("blockers", [])},
        {"name": "agent-plan-no-overlap", "pass": not agent_errors},
        {"name": "commit-plan-ahead-clean-not-recommended", "pass": build_commit_plan(clean_git).get("recommended") is False},
        {"name": "retired-opencode-path-detected", "pass": is_retired_opencode_path("tools/riftreader_workflow/opencode_bridge.py")},
    ]
    ok = all(check["pass"] for check in checks)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-decision-packet-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if ok else "failed",
        "ok": ok,
        "checks": checks,
        "safety": {**safety_flags(), "readOnlyDecisionPacket": True, "gitMutation": False},
    }


def build_schema_contract() -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-decision-packet-schema-contract",
        "helperVersion": HELPER_VERSION,
        "requiredTopLevelFields": [
            "schemaVersion",
            "kind",
            "helperVersion",
            "generatedAtUtc",
            "status",
            "lane",
            "risk",
            "repoRoot",
            "repo",
            "targetEpoch",
            "truth",
            "allowedActions",
            "forbiddenActions",
            "safeNextAction",
            "automationPlan",
            "validationPlan",
            "validationResults",
            "commitPlan",
            "agentPlan",
            "llmReminder",
            "milestoneStatus",
            "fingerprint",
            "cacheStatus",
            "performance",
            "cacheSafety",
            "blockers",
            "warnings",
            "errors",
            "safety",
        ],
        "statusValues": ["passed", "blocked", "failed"],
        "milestoneStates": sorted(MILESTONE_STATES),
        "commitPlanFields": [
            "recommended",
            "reason",
            "suggestedMessage",
            "explicitPaths",
            "excludedGeneratedPaths",
            "retiredSurfacePaths",
            "pathCategories",
            "validationRequired",
            "stageCommand",
            "stageCommandPreview",
        ],
        "safeNextActionFields": ["key", "command", "why"],
        "agentPlanFields": ["name", "authority", "ownedPaths", "forbiddenPaths", "risk", "validation"],
        "agentPlanAuthorityValues": ["read", "write"],
        "agentPlanRiskValues": ["low", "medium", "high"],
        "llmReminderFields": ["banner", "state", "doNotStopIf", "mustStopIf", "continueWith"],
        "safety": safety_flags(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--json", action="store_true", help="Print full JSON decision packet.")
    parser.add_argument("--compact-json", action="store_true", help="Print compact JSON decision packet.")
    parser.add_argument("--write", action="store_true", help="Write ignored packet artifacts under .riftreader-local.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-safe-checks", action="store_true", help="Run only packet-approved safe validations.")
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Reuse ignored packet artifacts only when the fresh fingerprint exactly matches; disabled for --run-safe-checks.",
    )
    parser.add_argument("--self-test", action="store_true", help="Run fixture-only self-test.")
    parser.add_argument("--schema-json", action="store_true", help="Print the static decision packet schema contract.")
    parser.add_argument("--explain", action="store_true", help="Print Markdown explanation.")
    parser.add_argument("--lane", default=None, help="Override lane label after packet construction.")
    parser.add_argument("--agent-plan", action="store_true", help="Print only the agent plan JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve() if args.repo_root else find_repo_root(Path.cwd())
    if args.self_test:
        result = build_self_test(repo_root)
        if args.json or args.compact_json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(f"Status: {result.get('status')}")
        return 0 if result.get("ok") else 1
    if args.schema_json:
        print(json.dumps(build_schema_contract(), indent=2, sort_keys=True))
        return 0
    try:
        packet = build_decision_packet(
            repo_root,
            run_safe_checks=args.run_safe_checks,
            use_cache=args.use_cache,
            cache_dir=args.output_dir,
        )
        if args.lane:
            packet["lane"] = args.lane
        if args.write:
            write_outputs(repo_root, packet, args.output_dir)
        if args.agent_plan:
            print(json.dumps({"agentPlan": packet.get("agentPlan"), "llmReminder": packet.get("llmReminder")}, indent=2))
        elif args.compact_json:
            print(json.dumps(compact_decision_packet(packet), indent=2))
        elif args.json:
            print(json.dumps(packet, indent=2))
        elif args.explain:
            print(build_markdown(packet), end="")
        else:
            next_action = safe_mapping(packet.get("safeNextAction"))
            print(str(safe_mapping(packet.get("milestoneStatus")).get("banner")))
            print(f"Status: {packet.get('status')} Lane: {packet.get('lane')} Risk: {packet.get('risk')}")
            print("Next: " + format_command(next_action.get("command")))
            if packet.get("blockers"):
                print("Blockers: " + ", ".join(packet.get("blockers") or []))
    except Exception as exc:  # noqa: BLE001 - CLI must fail closed with diagnostic JSON when requested.
        error = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-decision-packet-error",
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "error": f"{type(exc).__name__}:{exc}",
            "preview": preview_text(str(exc)),
            "safety": {**safety_flags(), "gitMutation": False, "providerWrites": False},
        }
        if args.json or args.compact_json:
            print(json.dumps(error, indent=2), file=sys.stderr)
        else:
            print(error["error"], file=sys.stderr)
        return 1
    if packet.get("status") == "failed":
        return 1
    if packet.get("status") == "blocked":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
