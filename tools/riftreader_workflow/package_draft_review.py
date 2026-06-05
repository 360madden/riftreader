#!/usr/bin/env python3
"""Review and dry-run the newest Local Artifact Bridge package draft.

This helper stays in the non-Codex/Desktop ChatGPT workflow lane:
it reads inert drafts under .riftreader-local, and its dry-run mode invokes the
existing package intake helper without --apply.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from . import local_artifact_bridge as bridge
    from .common import find_repo_root, repo_rel as rel, run_command_envelope, safety_flags, utc_iso
except ImportError:  # pragma: no cover - supports direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow import local_artifact_bridge as bridge
    from riftreader_workflow.common import find_repo_root, repo_rel as rel, run_command_envelope, safety_flags, utc_iso


SCHEMA_VERSION = 1
DRAFT_ROOT_REL = Path(".riftreader-local") / "artifact-bridge-package-drafts"
PACKAGE_INTAKE_ROOT_REL = Path(".riftreader-local") / "package-intake"
SELF_TEST_TARGET = "docs/workflow/package-draft-review-selftest-preview.md"


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def draft_root(repo_root: Path) -> Path:
    return (repo_root / DRAFT_ROOT_REL).resolve()


def package_intake_root(repo_root: Path) -> Path:
    return (repo_root / PACKAGE_INTAKE_ROOT_REL).resolve()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json-not-object:{path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_utc_timestamp(value: Any) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def safe_resolve_repo_path(repo_root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def package_root_from_summary(repo_root: Path, draft_dir: Path, summary: dict[str, Any]) -> Path:
    package_root = safe_resolve_repo_path(repo_root, summary.get("packageRoot"))
    if package_root is None:
        package_root = (draft_dir / "package").resolve()
    return package_root


def text_says_self_test(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.lower().replace("_", "-")
    return "self-test" in normalized or "selftest" in normalized


def summary_is_self_test(summary: dict[str, Any]) -> bool:
    metadata = summary.get("messageMetadata")
    if isinstance(metadata, dict) and metadata.get("selfTest") is True:
        return True
    source = summary.get("messageSource")
    if isinstance(source, dict) and any(text_says_self_test(source.get(key)) for key in ("tool", "context")):
        return True
    validation = summary.get("validation")
    validation_package_name = validation.get("packageName") if isinstance(validation, dict) else None
    return any(
        text_says_self_test(value)
        for value in (
            summary.get("messageTitle"),
            summary.get("packageName"),
            validation_package_name,
            summary.get("inboxId"),
        )
    )


def summarize_draft(repo_root: Path, draft_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    summary_path = draft_dir / "summary.json"
    if not summary_path.is_file():
        return None, "summary-missing"
    try:
        summary = load_json(summary_path)
    except Exception as exc:  # noqa: BLE001 - preserve exact blocker for review.
        return None, f"summary-json-invalid:{type(exc).__name__}:{exc}"
    package_root = package_root_from_summary(repo_root, draft_dir, summary)
    manifest_path = safe_resolve_repo_path(repo_root, summary.get("manifestPath")) or (
        package_root / "riftreader-package-manifest.json"
    )
    root = draft_root(repo_root)
    draft_under_root = is_relative_to(draft_dir, root)
    package_under_root = is_relative_to(package_root, root)
    manifest_under_root = is_relative_to(manifest_path, root)
    blockers: list[str] = []
    if not draft_under_root:
        blockers.append("draft-root-outside-package-draft-root")
    if not package_under_root:
        blockers.append("package-root-outside-draft-root")
    if not manifest_under_root:
        blockers.append("manifest-path-outside-draft-root")
    package_root_exists = package_under_root and package_root.is_dir()
    manifest_exists = manifest_under_root and manifest_path.is_file()
    if package_under_root and not package_root_exists:
        blockers.append("package-root-missing")
    if manifest_under_root and not manifest_exists:
        blockers.append("package-manifest-missing")
    validation = summary.get("validation")
    validation_package_name = validation.get("packageName") if isinstance(validation, dict) else None
    package_name = summary.get("packageName") or validation_package_name
    self_test = summary_is_self_test(summary)
    item = {
        "draftId": draft_dir.name,
        "draftRoot": rel(repo_root, draft_dir),
        "summaryPath": rel(repo_root, summary_path),
        "packageRoot": rel(repo_root, package_root),
        "manifestPath": rel(repo_root, manifest_path),
        "generatedAtUtc": summary.get("generatedAtUtc"),
        "status": summary.get("status"),
        "ok": bool(summary.get("ok")),
        "inboxId": summary.get("inboxId"),
        "messageTitle": summary.get("messageTitle"),
        "packageName": package_name,
        "fileCount": summary.get("fileCount"),
        "validation": summary.get("validation"),
        "origin": "self-test" if self_test else "operator-proposal",
        "selfTest": self_test,
        "packageRootExists": package_root_exists,
        "manifestExists": manifest_exists,
        "underDraftRoot": draft_under_root and package_under_root and manifest_under_root,
        "reviewReady": not blockers,
        "blockers": blockers,
        "latestSortKey": [summary_path.stat().st_mtime, draft_dir.name],
        "dryRunCommand": [
            "scripts\\riftreader-package-intake.cmd",
            "--package",
            rel(repo_root, package_root),
            "--compact-json",
        ],
    }
    return item, None


def discover_package_drafts(repo_root: Path) -> dict[str, Any]:
    root = draft_root(repo_root)
    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    if root.exists() and not root.is_dir():
        warnings.append("package_draft_root_not_directory")
    if root.is_dir():
        for child in root.iterdir():
            if not child.is_dir():
                continue
            item, warning = summarize_draft(repo_root, child)
            if item is not None:
                items.append(item)
            elif warning:
                warnings.append(f"skipped:{child.name}:{warning}")
    items.sort(key=lambda item: (item["latestSortKey"][0], item["latestSortKey"][1]))
    latest = items[-1] if items else None
    latest_operator = next((item for item in reversed(items) if not item.get("selfTest")), None)
    self_test_count = sum(1 for item in items if item.get("selfTest"))
    operator_draft_count = len(items) - self_test_count
    if latest and latest.get("selfTest"):
        warnings.append("latest_draft_is_self_test")
    for item in items:
        item.pop("latestSortKey", None)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-package-draft-review-index",
        "generatedAtUtc": utc_iso(),
        "status": "ready" if latest else "blocked",
        "ok": bool(latest),
        "draftRoot": rel(repo_root, root),
        "draftRootExists": root.is_dir(),
        "count": len(items),
        "operatorDraftCount": operator_draft_count,
        "selfTestDraftCount": self_test_count,
        "latestDraftId": latest.get("draftId") if latest else None,
        "latestOperatorDraftId": latest_operator.get("draftId") if latest_operator else None,
        "latest": latest,
        "latestOperator": latest_operator,
        "items": items,
        "warnings": warnings,
        "safety": {
            **safety_flags(),
            "readOnlyReview": True,
            "dryRunOnly": True,
            "applyFlagSent": False,
            "packageDraftsLocalIgnoredOnly": True,
            "noRepoTargetWrites": True,
            "noCommandExecutionEndpoint": True,
        },
        "next": [
            "Review the newest package draft summary and manifest before any dry-run.",
            "Use --dry-run-latest only as an explicit operator action; it does not pass --apply.",
            "Apply, Git, live RIFT input, CE, x64dbg, bridge serve, and tunnel automation remain out of scope.",
        ],
    }


def latest_package_draft(repo_root: Path, *, operator_only: bool = False) -> dict[str, Any]:
    index = discover_package_drafts(repo_root)
    latest_key = "latestOperator" if operator_only else "latest"
    latest = index.get(latest_key)
    if not isinstance(latest, dict):
        code = "PACKAGE_DRAFT_OPERATOR_EMPTY" if operator_only else "PACKAGE_DRAFT_EMPTY"
        message = (
            "No operator-proposal package drafts are available under .riftreader-local."
            if operator_only
            else "No package drafts are available under .riftreader-local."
        )
        next_steps = (
            [
                "Create or export a real operator-approved package-proposal first.",
                "Self-test drafts are intentionally not selected by --latest-operator.",
                "No package intake dry-run was started.",
            ]
            if operator_only
            else [
                "Create an inert package draft with the bridge inbox package-draft command first.",
                "No package intake dry-run was started.",
            ]
        )
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-package-draft-review-latest-operator" if operator_only else "riftreader-package-draft-review-latest",
            "generatedAtUtc": utc_iso(),
            "status": "blocked",
            "ok": False,
            "code": code,
            "message": message,
            "draftRoot": index["draftRoot"],
            "operatorDraftCount": index.get("operatorDraftCount"),
            "selfTestDraftCount": index.get("selfTestDraftCount"),
            "safety": index["safety"],
            "next": next_steps,
        }
    if latest.get("blockers"):
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-package-draft-review-latest-operator" if operator_only else "riftreader-package-draft-review-latest",
            "generatedAtUtc": utc_iso(),
            "status": "blocked",
            "ok": False,
            "code": "PACKAGE_DRAFT_NOT_REVIEW_READY",
            "draft": latest,
            "safety": index["safety"],
            "next": [
                "Inspect draft.blockers, draft.summaryPath, and draft.manifestPath.",
                "No package intake dry-run was started.",
            ],
        }
    warnings = list(index.get("warnings") or [])
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-package-draft-review-latest-operator" if operator_only else "riftreader-package-draft-review-latest",
        "generatedAtUtc": utc_iso(),
        "status": "ready",
        "ok": True,
        "draft": latest,
        "latestOperatorDraftId": index.get("latestOperatorDraftId"),
        "operatorOnly": operator_only,
        "warnings": warnings,
        "safety": index["safety"],
        "next": [
            "Inspect draft.summaryPath and draft.manifestPath.",
            (
                "This command ignores self-test drafts and selects only the latest operator-proposal draft."
                if operator_only
                else "If draft.selfTest is true, use --latest-operator or the draft index before real review."
            ),
            (
                "Run --dry-run-latest-operator only after operator approval to invoke package intake dry-run."
                if operator_only
                else "Run --dry-run-latest only after operator approval to invoke package intake dry-run."
            ),
            "Use --apply only outside this helper and only after explicit approval.",
        ],
    }


def dry_run_latest_package_draft(repo_root: Path, timeout_seconds: float, *, operator_only: bool = False) -> dict[str, Any]:
    latest_payload = latest_package_draft(repo_root, operator_only=operator_only)
    if not latest_payload.get("ok"):
        latest_payload["kind"] = "riftreader-package-draft-review-dry-run"
        if operator_only:
            latest_payload["kind"] = "riftreader-package-draft-review-dry-run-latest-operator"
        return latest_payload
    draft = latest_payload["draft"]
    package_root = safe_resolve_repo_path(repo_root, draft.get("packageRoot"))
    root = draft_root(repo_root)
    blockers: list[str] = list(draft.get("blockers") or [])
    if package_root is None:
        blockers.append("package-root-missing")
    elif not is_relative_to(package_root, root):
        blockers.append("package-root-outside-draft-root")
    elif not (package_root / "riftreader-package-manifest.json").is_file():
        blockers.append("package-manifest-missing")
    if blockers:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "riftreader-package-draft-review-dry-run-latest-operator"
            if operator_only
            else "riftreader-package-draft-review-dry-run",
            "generatedAtUtc": utc_iso(),
            "status": "blocked",
            "ok": False,
            "code": "PACKAGE_DRAFT_NOT_DRY_RUN_READY",
            "blockers": blockers,
            "draft": draft,
            "safety": latest_payload["safety"],
            "next": [
                "Inspect the draft summary and manifest path before retrying.",
                "No package intake dry-run was started.",
            ],
        }

    args = [
        str(repo_root / "scripts" / "riftreader-package-intake.cmd"),
        "--package",
        str(package_root),
        "--compact-json",
    ]
    envelope = run_command_envelope(
        "latest-package-draft-intake-dry-run",
        args,
        repo_root,
        timeout_seconds=timeout_seconds,
        expected_exit_codes={0, 2},
        capture_full_output=True,
    )
    exit_code = envelope.get("exitCode")
    parsed_stdout: Any = None
    stdout = envelope.get("stdout")
    if isinstance(stdout, str) and stdout.strip():
        try:
            parsed_stdout = json.loads(stdout)
        except json.JSONDecodeError:
            parsed_stdout = None
    status = "passed" if exit_code == 0 else "blocked" if exit_code == 2 else "failed"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-package-draft-review-dry-run-latest-operator"
        if operator_only
        else "riftreader-package-draft-review-dry-run",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": exit_code == 0,
        "exitCode": exit_code,
        "draft": draft,
        "command": {
            "args": args,
            "timeoutSeconds": timeout_seconds,
            "applyFlagSent": False,
            "dryRunOnly": True,
            "operatorOnly": operator_only,
        },
        "commandEnvelope": envelope,
        "intakeCompactSummary": parsed_stdout,
        "safety": {
            **latest_payload["safety"],
            "packageIntakeInvoked": True,
            "applyFlagSent": False,
            "dryRunOnly": True,
        },
        "next": [
            "Review the package intake compact summary and diff artifact.",
            "Do not apply, stage, commit, or push unless explicitly approved in a separate step.",
        ],
    }


def resolve_intake_artifact_path(repo_root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    candidate = candidate.resolve()
    intake_root = package_intake_root(repo_root)
    if not is_relative_to(candidate, intake_root):
        return None
    return candidate


def summarize_dry_run_summary(
    repo_root: Path,
    summary_path: Path,
    *,
    package_root: Path,
    now_timestamp: float | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    intake_root = package_intake_root(repo_root)
    if not is_relative_to(summary_path, intake_root):
        return None, "APPLY_DRY_RUN_ROOT_INVALID"
    if not summary_path.is_file():
        return None, "APPLY_DRY_RUN_MISSING"
    try:
        summary = load_json(summary_path)
    except Exception as exc:  # noqa: BLE001 - preserve exact blocker for preflight.
        return None, f"APPLY_DRY_RUN_JSON_INVALID:{type(exc).__name__}"
    if summary.get("kind") != "riftreader-package-intake-summary":
        return None, "APPLY_DRY_RUN_KIND_INVALID"
    if summary.get("dryRun") is not True:
        return None, "APPLY_DRY_RUN_NOT_DRY_RUN"
    if summary.get("status") != "passed":
        return None, "APPLY_DRY_RUN_NOT_PASSED"

    summary_package_root = safe_resolve_repo_path(repo_root, summary.get("packageRoot"))
    if summary_package_root != package_root:
        return None, "APPLY_DRY_RUN_PACKAGE_ROOT_MISMATCH"

    artifacts = summary.get("artifacts") if isinstance(summary.get("artifacts"), dict) else {}
    diff_path = resolve_intake_artifact_path(repo_root, artifacts.get("diff"))
    if diff_path is None or not diff_path.is_file():
        return None, "APPLY_DRY_RUN_DIFF_MISSING"

    generated_timestamp = parse_utc_timestamp(summary.get("generatedAtUtc"))
    if generated_timestamp is None:
        generated_timestamp = summary_path.stat().st_mtime
    reference_timestamp = datetime.now(timezone.utc).timestamp() if now_timestamp is None else now_timestamp
    age_seconds = max(0.0, reference_timestamp - generated_timestamp)
    diff_sha256 = sha256_file(diff_path)
    return (
        {
            "summaryPath": rel(repo_root, summary_path),
            "diffPath": rel(repo_root, diff_path),
            "generatedAtUtc": summary.get("generatedAtUtc"),
            "ageSeconds": round(age_seconds, 3),
            "diffSha256": diff_sha256,
            "changedFiles": summary.get("changedFiles") or [],
            "changedFileCount": len(summary.get("changedFiles") or []),
        },
        None,
    )


def discover_matching_dry_runs(repo_root: Path, package_root: Path) -> list[dict[str, Any]]:
    root = package_intake_root(repo_root)
    if not root.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for summary_path in root.glob("*/package-intake-summary.json"):
        item, blocker = summarize_dry_run_summary(repo_root, summary_path.resolve(), package_root=package_root)
        if item is not None and blocker is None:
            items.append(item)
    items.sort(key=lambda item: (float(item.get("ageSeconds") or 0.0), str(item.get("summaryPath") or "")))
    return items


def apply_preflight_latest_package_draft(
    repo_root: Path,
    *,
    operator_only: bool = True,
    dry_run_summary_path: str | None = None,
    dry_run_diff_sha256: str | None = None,
    max_age_seconds: float = 86400.0,
) -> dict[str, Any]:
    latest_payload = latest_package_draft(repo_root, operator_only=operator_only)
    blockers: list[str] = []
    warnings: list[str] = []
    draft = latest_payload.get("draft") if isinstance(latest_payload.get("draft"), dict) else None
    package_root: Path | None = None
    dry_run: dict[str, Any] | None = None

    if not latest_payload.get("ok") or draft is None:
        blockers.append(str(latest_payload.get("code") or "APPLY_DRAFT_NOT_FOUND"))
    else:
        draft_dir = safe_resolve_repo_path(repo_root, draft.get("draftRoot"))
        package_root = safe_resolve_repo_path(repo_root, draft.get("packageRoot"))
        root = draft_root(repo_root)
        if draft.get("selfTest") is True:
            blockers.append("APPLY_DRAFT_SELF_TEST_BLOCKED")
        if draft_dir is None or not is_relative_to(draft_dir, root):
            blockers.append("APPLY_DRAFT_ROOT_INVALID")
        if package_root is None or not is_relative_to(package_root, root):
            blockers.append("APPLY_PACKAGE_TARGET_INVALID")
        elif not package_root.is_dir():
            blockers.append("APPLY_DRAFT_NOT_FOUND")

    if package_root is not None and not blockers:
        if dry_run_summary_path:
            summary_path = resolve_intake_artifact_path(repo_root, dry_run_summary_path)
            if summary_path is None:
                blockers.append("APPLY_DRY_RUN_ROOT_INVALID")
            else:
                dry_run, blocker = summarize_dry_run_summary(repo_root, summary_path, package_root=package_root)
                if blocker:
                    blockers.append(blocker)
        else:
            matches = discover_matching_dry_runs(repo_root, package_root)
            if matches:
                dry_run = matches[0]
            else:
                blockers.append("APPLY_DRY_RUN_MISSING")

    if dry_run is not None:
        if max_age_seconds >= 0 and float(dry_run.get("ageSeconds") or 0.0) > max_age_seconds:
            blockers.append("APPLY_DRY_RUN_STALE")
        if dry_run_diff_sha256 and dry_run.get("diffSha256") != dry_run_diff_sha256:
            blockers.append("APPLY_DRY_RUN_HASH_MISMATCH")
        if not dry_run_diff_sha256:
            warnings.append("dry_run_diff_sha256_not_supplied_for_binding")

    status = "ready" if not blockers else "blocked"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-package-draft-apply-preflight-latest-operator"
        if operator_only
        else "riftreader-package-draft-apply-preflight-latest",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "ready",
        "applyToolExposed": False,
        "operatorOnly": operator_only,
        "draft": draft,
        "dryRun": dry_run,
        "blockers": blockers,
        "warnings": warnings,
        "approvalFacts": {
            "draftId": draft.get("draftId") if draft else None,
            "dryRunSummaryPath": dry_run.get("summaryPath") if dry_run else None,
            "dryRunDiffSha256": dry_run.get("diffSha256") if dry_run else None,
            "changedFileCount": dry_run.get("changedFileCount") if dry_run else None,
        },
        "safety": {
            **safety_flags(),
            "readOnlyPreflight": True,
            "applyFlagSent": False,
            "repoSourceMutationExpected": False,
            "gitMutation": False,
            "providerWrites": False,
            "inputSent": False,
            "movementSent": False,
            "x64dbgAttach": False,
            "noCheatEngine": True,
            "mcpToolExposed": False,
        },
        "next": [
            "Review approvalFacts before any future apply approval token is generated.",
            "Do not call package intake with --apply until a separate gated helper and MCP exposure stage exist.",
            "Commit/push, shell execution, RIFT input, CE, and x64dbg remain out of scope for this preflight.",
        ],
    }


def self_test_package_proposal() -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "package-proposal",
        "title": "Package draft review self-test proposal",
        "body": "Synthetic package-proposal for Local Artifact Bridge package draft review self-test.",
        "payload": {
            "packageName": "package-draft-review-self-test",
            "files": [
                {
                    "target": SELF_TEST_TARGET,
                    "content": (
                        "# Package Draft Review Self-Test Preview\n\n"
                        "This synthetic proposal is used only for inert draft export and package-intake dry-run.\n"
                    ),
                    "encoding": "utf-8",
                }
            ],
            "checks": [],
        },
        "source": {
            "tool": "package-draft-review-self-test",
            "context": "local synthetic proposal loop; no HTTP serve/tunnel/apply/Git/RIFT activity",
        },
        "metadata": {
            "requiresHumanReview": True,
            "draftOnly": True,
            "selfTest": True,
        },
    }


def run_self_test(repo_root: Path, timeout_seconds: float) -> dict[str, Any]:
    config = bridge.make_config(
        repo_root=repo_root,
        payload_root=bridge.DEFAULT_PAYLOAD_ROOT,
        token="package-draft-review-self-test",
        port=0,
        log_requests=False,
    )
    proposal = self_test_package_proposal()
    normalized = bridge.validate_inbox_message(proposal)
    raw = bridge.json_bytes(proposal)
    stored = bridge.store_inbox_message(config, normalized, len(raw))
    draft = bridge.create_inbox_package_draft(config, str(stored.get("inboxId") or "latest"))
    latest = latest_package_draft(repo_root)
    dry_run = dry_run_latest_package_draft(repo_root, timeout_seconds=timeout_seconds) if draft.get("ok") else None

    blockers: list[str] = []
    if not stored.get("ok"):
        blockers.append("inbox-store-failed")
    if not draft.get("ok"):
        blockers.append(f"draft-export-failed:{draft.get('code') or draft.get('status')}")
    if dry_run is not None and not dry_run.get("ok"):
        blockers.append(f"dry-run-failed:{dry_run.get('code') or dry_run.get('status')}")

    status = "passed" if not blockers else "failed"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-package-draft-review-self-test",
        "generatedAtUtc": utc_iso(),
        "status": status,
        "ok": status == "passed",
        "blockers": blockers,
        "stages": {
            "inboxProposalStored": {
                "ok": bool(stored.get("ok")),
                "status": stored.get("status"),
                "duplicate": stored.get("duplicate"),
                "inboxId": stored.get("inboxId"),
                "storedUnder": stored.get("storedUnder"),
            },
            "packageDraftCreated": {
                "ok": bool(draft.get("ok")),
                "status": draft.get("status"),
                "code": draft.get("code"),
                "draftRoot": draft.get("draftRoot"),
                "packageRoot": draft.get("packageRoot"),
                "manifestPath": draft.get("manifestPath"),
                "summaryPath": draft.get("summaryPath"),
            },
            "latestDraftReview": latest,
            "latestDraftDryRun": dry_run,
        },
        "safety": {
            **safety_flags(),
            "inboxProposalStoredLocalIgnoredOnly": True,
            "packageDraftsLocalIgnoredOnly": True,
            "packageIntakeDryRunOnly": True,
            "applyFlagSent": False,
            "noRepoTargetWrites": True,
            "noCommandExecutionEndpoint": True,
            "noServerStarted": True,
            "noTunnelStarted": True,
        },
        "next": [
            "Inspect stages.latestDraftDryRun.intakeCompactSummary artifacts and diff.",
            "Do not apply, stage, commit, or push unless explicitly approved in a separate step.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review inert Local Artifact Bridge package drafts.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--index", action="store_true", help="List package drafts under .riftreader-local.")
    mode.add_argument("--latest", action="store_true", help="Print the newest package draft summary pointer.")
    mode.add_argument(
        "--latest-operator",
        action="store_true",
        help="Print the newest non-self-test operator package draft summary pointer.",
    )
    mode.add_argument(
        "--dry-run-latest",
        action="store_true",
        help="Explicitly run package intake dry-run for the newest package draft. Never passes --apply.",
    )
    mode.add_argument(
        "--dry-run-latest-operator",
        action="store_true",
        help="Explicitly run package intake dry-run for the newest operator draft. Never passes --apply.",
    )
    mode.add_argument(
        "--apply-preflight-latest-operator",
        action="store_true",
        help="Read-only future-apply preflight for the newest operator draft. Never passes --apply.",
    )
    mode.add_argument(
        "--self-test",
        action="store_true",
        help="Run a local proposal -> inbox -> draft -> dry-run self-test. Writes ignored .riftreader-local artifacts only.",
    )
    parser.add_argument("--repo-root", default=None, help="RiftReader repo root; auto-detected by default.")
    parser.add_argument("--timeout-seconds", type=float, default=180.0, help="Dry-run command timeout.")
    parser.add_argument("--dry-run-summary-path", default=None, help="Optional package-intake-summary.json to bind.")
    parser.add_argument("--dry-run-diff-sha256", default=None, help="Optional expected SHA-256 for the dry-run diff.")
    parser.add_argument("--max-age-seconds", type=float, default=86400.0, help="Maximum dry-run age for apply preflight.")
    parser.add_argument("--json", action="store_true", help="Emit JSON. Present for wrapper consistency.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    if args.index:
        payload = discover_package_drafts(repo_root)
    elif args.latest:
        payload = latest_package_draft(repo_root)
    elif args.latest_operator:
        payload = latest_package_draft(repo_root, operator_only=True)
    elif args.dry_run_latest:
        payload = dry_run_latest_package_draft(repo_root, args.timeout_seconds)
    elif args.dry_run_latest_operator:
        payload = dry_run_latest_package_draft(repo_root, args.timeout_seconds, operator_only=True)
    elif args.apply_preflight_latest_operator:
        payload = apply_preflight_latest_package_draft(
            repo_root,
            operator_only=True,
            dry_run_summary_path=args.dry_run_summary_path,
            dry_run_diff_sha256=args.dry_run_diff_sha256,
            max_age_seconds=args.max_age_seconds,
        )
    else:
        payload = run_self_test(repo_root, args.timeout_seconds)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if payload.get("ok"):
        return 0
    if payload.get("status") == "blocked":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
