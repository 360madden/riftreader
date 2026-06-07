#!/usr/bin/env python3
"""Replay/revalidate saved actual ChatGPT MCP proof packets offline."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .chatgpt_trial_recorder import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES, validate_proof
    from .common import find_repo_root, repo_rel as rel, safety_flags, utc_iso
    from .mcp_workflow_state import (
        ACTUAL_CLIENT_PROOF_ROOT,
        DRAFT_ROOT,
        FRESHNESS_BUDGET_SECONDS,
        INBOX_ROOT,
        PACKAGE_INTAKE_ROOT,
        discover_actual_client_proofs,
        safe_load_json,
    )
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.chatgpt_trial_recorder import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES, validate_proof
    from riftreader_workflow.common import find_repo_root, repo_rel as rel, safety_flags, utc_iso
    from riftreader_workflow.mcp_workflow_state import (
        ACTUAL_CLIENT_PROOF_ROOT,
        DRAFT_ROOT,
        FRESHNESS_BUDGET_SECONDS,
        INBOX_ROOT,
        PACKAGE_INTAKE_ROOT,
        discover_actual_client_proofs,
        safe_load_json,
    )


DEFAULT_PROOF_FRESHNESS_BUDGET_SECONDS = FRESHNESS_BUDGET_SECONDS["actual-client-proof"]


def _age_seconds(path: Path) -> int:
    return max(0, int((datetime.now(timezone.utc) - datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)).total_seconds()))


def _resolve_latest_proof_path(repo_root: Path) -> tuple[Path | None, list[str]]:
    proof_items, warnings = discover_actual_client_proofs(repo_root)
    if not proof_items:
        return None, warnings
    latest = proof_items[-1]
    item_path = latest.get("path")
    if not isinstance(item_path, str) or not item_path:
        warnings.append("actual-client-proof-latest-path-missing")
        return None, warnings
    return repo_root / item_path.replace("\\", "/"), warnings


def _path_summary(repo_root: Path, path: Path) -> dict[str, Any]:
    return {"path": rel(repo_root, path), "exists": path.exists(), "isFile": path.is_file()}


def _dry_run_matches_draft(payload: dict[str, Any], draft_id: str) -> bool:
    for field in ("packagePath", "packageRoot"):
        value = payload.get(field)
        if isinstance(value, str) and draft_id in value.replace("/", "\\"):
            return True
    return False


def _matching_dry_run_summaries(repo_root: Path, draft_id: str) -> list[tuple[Path, dict[str, Any]]]:
    root = repo_root / PACKAGE_INTAKE_ROOT
    matches: list[tuple[Path, dict[str, Any]]] = []
    if not root.is_dir():
        return matches
    for path in root.glob("*/compact-package-intake-summary.json"):
        payload, _warning = safe_load_json(path)
        if payload is not None and _dry_run_matches_draft(payload, draft_id):
            matches.append((path, payload))
    for path in root.glob("*/package-intake-summary.json"):
        payload, _warning = safe_load_json(path)
        if payload is not None and _dry_run_matches_draft(payload, draft_id):
            matches.append((path, payload))
    matches.sort(key=lambda item: (item[0].stat().st_mtime, str(item[0])))
    return matches


def _repo_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root / value.replace("\\", "/")


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def local_artifact_consistency(
    repo_root: Path,
    proof: dict[str, Any],
    *,
    strict_missing: bool = False,
) -> dict[str, Any]:
    """Cross-check local ignored artifacts referenced by an actual-client proof."""

    warnings: list[str] = []
    blockers: list[str] = []
    inbox_id = str(proof.get("inboxId") or "")
    draft_id = str(proof.get("draftId") or "")
    checks: dict[str, Any] = {}

    def missing(kind: str, value: str, path: Path) -> None:
        message = f"{kind}-artifact-missing:{value}:{rel(repo_root, path)}"
        if strict_missing:
            blockers.append(message)
        else:
            warnings.append(message)

    if inbox_id:
        inbox_path = repo_root / INBOX_ROOT / inbox_id / "metadata.json"
        checks["inbox"] = _path_summary(repo_root, inbox_path)
        if not inbox_path.is_file():
            missing("inbox", inbox_id, inbox_path)
        else:
            metadata, warning = safe_load_json(inbox_path)
            if warning:
                blockers.append(f"inbox-artifact-json-invalid:{warning}")
            elif metadata is not None:
                checks["inbox"]["metadata"] = {
                    "inboxId": metadata.get("inboxId"),
                    "messageKind": metadata.get("messageKind"),
                    "applied": metadata.get("applied"),
                    "executed": metadata.get("executed"),
                }
                if metadata.get("inboxId") != inbox_id:
                    blockers.append(f"inbox-artifact-id-mismatch:{metadata.get('inboxId')!r}!={inbox_id!r}")
                if metadata.get("messageKind") != "package-proposal":
                    blockers.append(f"inbox-artifact-kind-not-package-proposal:{metadata.get('messageKind')!r}")
                if metadata.get("applied") is not False:
                    blockers.append(f"inbox-artifact-applied-flag-not-false:{metadata.get('applied')!r}")
                if metadata.get("executed") is not False:
                    blockers.append(f"inbox-artifact-executed-flag-not-false:{metadata.get('executed')!r}")

    if draft_id:
        draft_path = repo_root / DRAFT_ROOT / draft_id / "summary.json"
        checks["draft"] = _path_summary(repo_root, draft_path)
        if not draft_path.is_file():
            missing("draft", draft_id, draft_path)
        else:
            draft, warning = safe_load_json(draft_path)
            if warning:
                blockers.append(f"draft-artifact-json-invalid:{warning}")
            elif draft is not None:
                safety = draft.get("safety") if isinstance(draft.get("safety"), dict) else {}
                checks["draft"]["summary"] = {
                    "inboxId": draft.get("inboxId"),
                    "status": draft.get("status"),
                    "ok": draft.get("ok"),
                    "noApplyExecute": safety.get("noApplyExecute"),
                    "noRepoTargetWrites": safety.get("noRepoTargetWrites"),
                    "noGitMutation": safety.get("noGitMutation"),
                }
                if inbox_id and draft.get("inboxId") != inbox_id:
                    blockers.append(f"draft-artifact-inbox-id-mismatch:{draft.get('inboxId')!r}!={inbox_id!r}")
                if draft.get("status") != "created" or draft.get("ok") is not True:
                    blockers.append(f"draft-artifact-not-created-ok:{draft.get('status')!r}:{draft.get('ok')!r}")
                for key in ("noApplyExecute", "noRepoTargetWrites", "noGitMutation"):
                    if safety.get(key) is not True:
                        blockers.append(f"draft-artifact-safety-{key}-not-true:{safety.get(key)!r}")

    if proof.get("dryRunSucceeded") is True and draft_id:
        matches = _matching_dry_run_summaries(repo_root, draft_id)
        checks["dryRun"] = {
            "matchCount": len(matches),
            "paths": [rel(repo_root, path) for path, _payload in matches[:5]],
        }
        if not matches:
            missing("dry-run", draft_id, repo_root / PACKAGE_INTAKE_ROOT)
        else:
            latest_path, latest_payload = matches[-1]
            checks["dryRun"]["latest"] = {
                "path": rel(repo_root, latest_path),
                "status": latest_payload.get("status"),
                "dryRun": latest_payload.get("dryRun"),
                "changedFileCount": latest_payload.get("changedFileCount"),
            }
            artifacts = latest_payload.get("artifacts") if isinstance(latest_payload.get("artifacts"), dict) else {}
            diff_value = artifacts.get("diff")
            if isinstance(diff_value, str) and diff_value:
                diff_path = _repo_path(repo_root, diff_value)
                under_package_intake = _is_under(diff_path, repo_root / PACKAGE_INTAKE_ROOT)
                checks["dryRun"]["latest"]["diff"] = {
                    "path": rel(repo_root, diff_path) if under_package_intake else diff_value,
                    "exists": diff_path.is_file(),
                    "underPackageIntake": under_package_intake,
                }
                if not under_package_intake:
                    blockers.append(f"dry-run-diff-artifact-not-under-package-intake:{diff_value}")
                if proof.get("dryRunDiffPreviewOk") is True and not diff_path.is_file():
                    missing("dry-run-diff", draft_id, diff_path)
            elif proof.get("dryRunDiffPreviewOk") is True:
                blockers.append("dry-run-diff-artifact-path-missing")
            if latest_payload.get("status") != "passed" or latest_payload.get("dryRun") is not True:
                blockers.append(
                    "dry-run-artifact-not-passed-dry-run:"
                    f"{latest_payload.get('status')!r}:{latest_payload.get('dryRun')!r}:{rel(repo_root, latest_path)}"
                )

    status = "passed" if not blockers and not warnings else "warning" if not blockers else "blocked"
    return {
        "status": status,
        "ok": not blockers,
        "strictMissing": strict_missing,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }


def replay_actual_client_proof(
    repo_root: Path,
    *,
    proof_path: Path | None = None,
    freshness_budget_seconds: int = DEFAULT_PROOF_FRESHNESS_BUDGET_SECONDS,
    strict_artifacts: bool = False,
) -> dict[str, Any]:
    """Revalidate a saved ``proof.json`` without starting ChatGPT, tunnels, or servers."""

    warnings: list[str] = []
    blockers: list[str] = []
    if proof_path is None:
        proof_path, discovery_warnings = _resolve_latest_proof_path(repo_root)
        warnings.extend(discovery_warnings)
    else:
        proof_path = proof_path.resolve()

    if proof_path is None:
        blockers.append("actual-client-proof-missing")
        return {
            "schemaVersion": 1,
            "kind": "riftreader-mcp-actual-client-proof-replay",
            "generatedAtUtc": utc_iso(),
            "status": "blocked",
            "ok": False,
            "proofPath": None,
            "proofFreshness": {"status": "missing"},
            "blockers": blockers,
            "warnings": warnings,
            "safety": {
                **safety_flags(),
                "proofReplayReadOnly": True,
                "chatGptApiCalled": False,
                "publicTunnelStarted": False,
                "persistentServerStarted": False,
                "gitMutation": False,
            },
        }

    if not proof_path.is_file():
        blockers.append(f"actual-client-proof-file-missing:{proof_path}")
        age_payload = {"status": "missing"}
        payload: dict[str, Any] | None = None
    else:
        age = _age_seconds(proof_path)
        freshness_status = "fresh" if age <= freshness_budget_seconds else "stale"
        age_payload = {
            "status": freshness_status,
            "ageSeconds": age,
            "budgetSeconds": freshness_budget_seconds,
            "path": rel(repo_root, proof_path),
        }
        if freshness_status == "stale":
            warnings.append(f"actual-client-proof-age-exceeds-budget:{age}s>{freshness_budget_seconds}s:{rel(repo_root, proof_path)}")
        try:
            loaded = json.loads(proof_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - preserve malformed evidence.
            blockers.append(f"actual-client-proof-json-invalid:{type(exc).__name__}:{exc}")
            loaded = None
        payload = loaded if isinstance(loaded, dict) else None
        if loaded is not None and payload is None:
            blockers.append("actual-client-proof-json-not-object")

    proof: dict[str, Any] | None = None
    artifact_consistency: dict[str, Any] = {
        "status": "not-run",
        "ok": True,
        "blockers": [],
        "warnings": [],
        "checks": {},
    }
    if payload is not None:
        if payload.get("kind") != "riftreader-chatgpt-actual-client-proof":
            blockers.append(f"actual-client-proof-kind-mismatch:{payload.get('kind')!r}")
        if payload.get("status") != "passed" or payload.get("ok") is not True:
            blockers.append(f"actual-client-proof-record-not-passed:{payload.get('status')!r}:{payload.get('ok')!r}")
        recorded_blockers = payload.get("blockers")
        if isinstance(recorded_blockers, list) and recorded_blockers:
            blockers.append("actual-client-proof-recorded-blockers-present")
        proof_value = payload.get("proof")
        if isinstance(proof_value, dict):
            proof = proof_value
            blockers.extend(validate_proof(proof))
            artifact_consistency = local_artifact_consistency(repo_root, proof, strict_missing=strict_artifacts)
            blockers.extend(f"artifact-consistency:{blocker}" for blocker in artifact_consistency.get("blockers") or [])
            warnings.extend(f"artifact-consistency:{warning}" for warning in artifact_consistency.get("warnings") or [])
        else:
            blockers.append("actual-client-proof-payload-missing-proof-object")
        safety = payload.get("safety") if isinstance(payload.get("safety"), dict) else {}
        expected_false = {
            "chatGptApiCalled": False,
            "publicTunnelStarted": False,
            "gitMutation": False,
            "applyFlagSent": False,
        }
        for key, expected in expected_false.items():
            if key in safety and safety.get(key) is not expected:
                blockers.append(f"actual-client-proof-safety-{key}-not-{expected!r}:{safety.get(key)!r}")

    status = "passed" if not blockers else "blocked"
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-actual-client-proof-replay",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "passed",
        "proofPath": rel(repo_root, proof_path),
        "proofFreshness": age_payload,
        "proofSummary": {
            "toolCount": proof.get("toolCount") if isinstance(proof, dict) else None,
            "toolNames": proof.get("toolNames") if isinstance(proof, dict) else None,
            "toolOutputSchemasPresent": proof.get("toolOutputSchemasPresent") if isinstance(proof, dict) else None,
            "toolOutputSchemaCount": proof.get("toolOutputSchemaCount") if isinstance(proof, dict) else None,
            "toolOutputSchemaToolNames": proof.get("toolOutputSchemaToolNames") if isinstance(proof, dict) else None,
            "connectionMode": proof.get("connectionMode") if isinstance(proof, dict) else None,
            "publicMcpUrl": proof.get("publicMcpUrl") if isinstance(proof, dict) else None,
            "inboxId": proof.get("inboxId") if isinstance(proof, dict) else None,
            "draftId": proof.get("draftId") if isinstance(proof, dict) else None,
            "reviewLatestPackageDraftSucceeded": proof.get("reviewLatestPackageDraftSucceeded") if isinstance(proof, dict) else None,
            "dryRunSucceeded": proof.get("dryRunSucceeded") if isinstance(proof, dict) else None,
            "dryRunDiffPreviewOk": proof.get("dryRunDiffPreviewOk") if isinstance(proof, dict) else None,
            "dryRunDiffPreviewTextLength": proof.get("dryRunDiffPreviewTextLength") if isinstance(proof, dict) else None,
            "applyLatestPackageDraftWithoutApprovalBlocked": (
                proof.get("applyLatestPackageDraftWithoutApprovalBlocked") if isinstance(proof, dict) else None
            ),
            "applyLatestPackageDraftWithoutApprovalBlockers": (
                proof.get("applyLatestPackageDraftWithoutApprovalBlockers") if isinstance(proof, dict) else None
            ),
            "applyLatestPackageDraftWithoutApprovalApplied": (
                proof.get("applyLatestPackageDraftWithoutApprovalApplied") if isinstance(proof, dict) else None
            ),
        },
        "artifactConsistency": artifact_consistency,
        "blockers": blockers,
        "warnings": warnings,
        "safety": {
            **safety_flags(),
            "proofReplayReadOnly": True,
            "chatGptApiCalled": False,
            "publicTunnelStarted": False,
            "persistentServerStarted": False,
            "gitMutation": False,
        },
    }


def self_test() -> dict[str, Any]:
    blockers = validate_proof(
        {
            "schemaVersion": 1,
            "connectionMode": "cloudflare-named-tunnel",
            "publicMcpUrl": "https://mcp.360madden.com/mcp",
            "chatgptRegistrationSucceeded": True,
            "toolCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT,
            "toolNames": list(EXPECTED_CHATGPT_MCP_TOOL_NAMES),
            "toolOutputSchemasPresent": True,
            "toolOutputSchemaCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT,
            "toolOutputSchemaToolNames": list(EXPECTED_CHATGPT_MCP_TOOL_NAMES),
            "health": {"repoRoot": ".", "repoName": "RiftReader", "absoluteRepoRootExposed": False},
            "templateFetched": True,
            "submitPackageProposalSucceeded": True,
            "inboxId": "inbox",
            "listInboxSawInboxId": True,
            "createPackageDraftSucceeded": True,
            "draftId": "draft",
            "reviewLatestPackageDraftSucceeded": True,
            "reviewLatestPackageDraftReadOnly": True,
            "dryRunSucceeded": True,
            "dryRunDiffPreviewOk": True,
            "dryRunDiffPreviewArtifactUnderPackageIntake": True,
            "dryRunDiffPreviewBoundedBytes": True,
            "dryRunDiffPreviewTextLength": 195,
            "dryRunDiffPreviewTruncated": False,
            "applyLatestPackageDraftWithoutApprovalBlocked": True,
            "applyLatestPackageDraftWithoutApprovalBlockers": ["APPLY_APPROVAL_MISSING"],
            "applyLatestPackageDraftWithoutApprovalApplied": False,
        }
    )
    checks = [{"name": "proof-rules-accept-valid-shape", "pass": blockers == []}]
    ok = all(check["pass"] for check in checks)
    return {
        "schemaVersion": 1,
        "kind": "riftreader-mcp-proof-replay-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if ok else "failed",
        "ok": ok,
        "checks": checks,
        "safety": {
            **safety_flags(),
            "chatGptApiCalled": False,
            "publicTunnelStarted": False,
            "gitMutation": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay/revalidate a saved actual ChatGPT MCP proof packet offline.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--replay", action="store_true", help="Replay the latest or provided proof.json.")
    mode.add_argument("--self-test", action="store_true", help="Run deterministic proof rule self-test.")
    parser.add_argument("--proof-path", default=None)
    parser.add_argument("--strict-artifacts", action="store_true", help="Treat missing local inbox/draft/dry-run artifacts as blockers.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
        proof_path = Path(args.proof_path).resolve() if args.proof_path else None
        payload = self_test() if args.self_test else replay_actual_client_proof(
            repo_root,
            proof_path=proof_path,
            strict_artifacts=args.strict_artifacts,
        )
    except Exception as exc:  # noqa: BLE001 - CLI must fail closed with structured error.
        payload = {
            "schemaVersion": 1,
            "kind": "riftreader-mcp-actual-client-proof-replay",
            "generatedAtUtc": utc_iso(),
            "status": "failed",
            "ok": False,
            "blockers": [f"proof-replay-exception:{type(exc).__name__}:{exc}"],
            "warnings": [],
            "safety": safety_flags(),
        }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
