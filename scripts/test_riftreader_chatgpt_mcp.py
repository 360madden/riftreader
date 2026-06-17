#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import riftreader_chatgpt_mcp as chatgpt_mcp  # noqa: E402


class FakeTransportSecuritySettings:
    def __init__(
        self,
        *,
        enable_dns_rebinding_protection: bool,
        allowed_hosts: list[str],
        allowed_origins: list[str],
    ) -> None:
        self.enable_dns_rebinding_protection = enable_dns_rebinding_protection
        self.allowed_hosts = allowed_hosts
        self.allowed_origins = allowed_origins


class FakeProcess:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs
        self.returncode: int | None = None
        self.stdout: list[str] = []
        self.stderr: list[str] = []

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def kill(self) -> None:
        self.returncode = -9

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        if self.returncode is None:
            self.returncode = 0
        return ("", "")


def make_repo(root: Path) -> None:
    (root / ".git").mkdir()
    (root / "agents.md").write_text("# policy\n", encoding="utf-8")
    (root / "docs" / "handoffs").mkdir(parents=True)
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "riftreader-package-intake.cmd").write_text(
        "@echo off\n"
        "echo {\"status\":\"passed\",\"dryRun\":true,\"changedFileCount\":1}\n"
        "exit /b 0\n",
        encoding="utf-8",
    )


def make_tracked_context_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    files = {
        "agents.md": "# policy\n",
        "docs/HANDOFF.md": "# Handoff\n",
        "docs/workflow/intro.md": "# Intro\nneedle line\n",
        "tools/riftreader_workflow/helper.py": "VALUE = 'needle'\n",
        "scripts/run.cmd": "@echo off\nREM needle cmd\n",
        ".env": "TOKEN=needle\n",
        ".riftreader-local/local.md": "needle local\n",
    }
    for rel_path, content in files.items():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    blob = root / "data" / "blob.bin"
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(b"\x00\x01\x02")
    subprocess.run(["git", "add", "--", *files.keys(), "data/blob.bin"], cwd=root, check=True)


def make_adapter(root: Path) -> chatgpt_mcp.RiftReaderChatGptMcpAdapter:
    config = chatgpt_mcp.make_adapter_config(root)
    return chatgpt_mcp.RiftReaderChatGptMcpAdapter(config)


def package_proposal(title: str = "Test proposal", target: str = "docs/proposed.md") -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "kind": "package-proposal",
        "title": title,
        "body": "Review this inert proposal.",
        "payload": {
            "packageName": title,
            "files": [
                {
                    "target": target,
                    "content": "# Proposed\n",
                    "encoding": "utf-8",
                }
            ],
            "checks": [],
        },
        "source": {"tool": "unit-test", "context": "chatgpt-mcp"},
        "metadata": {"requiresHumanReview": True, "draftOnly": True},
    }


def make_draft(root: Path, draft_id: str, *, title: str, self_test: bool = False) -> Path:
    draft_dir = root / ".riftreader-local" / "artifact-bridge-package-drafts" / draft_id
    package_root = draft_dir / "package"
    files_dir = package_root / "files"
    files_dir.mkdir(parents=True)
    source = files_dir / "file-0001.txt"
    source.write_text("# Proposed\n", encoding="utf-8")
    manifest = {
        "schemaVersion": 1,
        "packageName": title,
        "files": [
            {
                "source": "files/file-0001.txt",
                "target": "docs/proposed.md",
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        ],
        "checks": [],
    }
    (package_root / "riftreader-package-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    summary = {
        "schemaVersion": 1,
        "ok": True,
        "status": "created",
        "kind": "riftreader-local-artifact-bridge-inbox-package-draft",
        "generatedAtUtc": "2026-05-18T18:00:00Z",
        "inboxId": draft_id,
        "messageTitle": title,
        "packageName": title,
        "messageMetadata": {"selfTest": True} if self_test else {},
        "messageSource": {"tool": "self-test" if self_test else "Desktop ChatGPT"},
        "draftRoot": str(draft_dir.relative_to(root)).replace("/", "\\"),
        "packageRoot": str(package_root.relative_to(root)).replace("/", "\\"),
        "manifestPath": str((package_root / "riftreader-package-manifest.json").relative_to(root)).replace("/", "\\"),
        "fileCount": 1,
        "validation": {"errors": [], "warnings": []},
    }
    (draft_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return draft_dir


def make_cached_dry_run(
    root: Path,
    draft_dir: Path,
    run_id: str = "20260518-180100Z",
    *,
    check_counts: dict[str, int] | None = None,
) -> Path:
    package_root = draft_dir / "package"
    intake_dir = root / ".riftreader-local" / "package-intake" / run_id
    intake_dir.mkdir(parents=True)
    counts = check_counts or {"declaredCount": 0, "runCount": 0, "failedCount": 0}
    compact = {
        "schemaVersion": 1,
        "kind": "riftreader-package-intake-compact-summary",
        "generatedAtUtc": "2026-05-18T18:01:00Z",
        "status": "passed",
        "dryRun": True,
        "packageRoot": str(package_root),
        "changedFiles": ["docs/proposed.md"],
        "changedFileCount": 1,
        "checks": counts,
        "blockers": [],
        "warnings": [],
        "errors": [],
        "artifacts": {
            "diff": str((intake_dir / "package.diff").relative_to(root)).replace("/", "\\"),
            "compactJson": str((intake_dir / "compact-package-intake-summary.json").relative_to(root)).replace("/", "\\")
        },
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgAttach": False,
            "providerWrites": False,
            "gitMutation": False,
            "savedVariablesUsedAsLiveTruth": False,
        },
    }
    path = intake_dir / "compact-package-intake-summary.json"
    path.write_text(json.dumps(compact, indent=2), encoding="utf-8")
    (intake_dir / "package.diff").write_text(
        "diff --git a/docs/proposed.md b/docs/proposed.md\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/docs/proposed.md\n"
        "@@ -0,0 +1 @@\n"
        "+# Proposed\n",
        encoding="utf-8",
    )
    os.utime(path, (1_900_000_000, 1_900_000_000))
    return path


def make_full_dry_run_summary(
    root: Path,
    draft_dir: Path,
    run_id: str = "20260518T140000Z-dry-run",
    *,
    declared_checks: list[dict[str, object]] | None = None,
    check_results: list[dict[str, object]] | None = None,
) -> tuple[Path, str]:
    package_root = draft_dir / "package"
    intake_dir = root / ".riftreader-local" / "package-intake" / run_id
    intake_dir.mkdir(parents=True)
    diff_path = intake_dir / "package.diff"
    diff_path.write_text(
        "diff --git a/docs/proposed.md b/docs/proposed.md\n"
        "--- a/docs/proposed.md\n"
        "+++ b/docs/proposed.md\n",
        encoding="utf-8",
    )
    diff_sha256 = hashlib.sha256(diff_path.read_bytes()).hexdigest()
    summary = {
        "schemaVersion": 1,
        "kind": "riftreader-package-intake-summary",
        "generatedAtUtc": "2099-01-01T00:00:00Z",
        "status": "passed",
        "dryRun": True,
        "packagePath": str(package_root),
        "packageRoot": str(package_root),
        "blockers": [],
        "warnings": [],
        "errors": [],
        "changedFiles": ["docs/proposed.md"],
        "declaredChecks": declared_checks if declared_checks is not None else [],
        "checks": check_results if check_results is not None else [],
        "artifacts": {
            "summaryJson": str((intake_dir / "package-intake-summary.json").relative_to(root)).replace("/", "\\"),
            "diff": str(diff_path.relative_to(root)).replace("/", "\\"),
        },
        "safety": {"applyFlagSent": False},
    }
    summary_path = intake_dir / "package-intake-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary_path, diff_sha256


def submit_package_proposal_input_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {"proposal": {"$ref": "#/$defs/PackageProposal"}},
        "required": ["proposal"],
        "$defs": {
            "PackageProposal": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "schemaVersion": {"const": 1},
                    "kind": {"const": "package-proposal"},
                    "title": {"type": "string"},
                    "payload": {"$ref": "#/$defs/PackageProposalPayload"},
                },
                "required": ["schemaVersion", "kind", "title", "payload"],
            },
            "PackageProposalPayload": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "packageName": {"type": "string"},
                    "files": {"type": "array", "items": {"$ref": "#/$defs/PackageProposalFile"}},
                },
                "required": ["packageName", "files"],
            },
            "PackageProposalFile": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "target": {"type": "string"},
                    "content": {"type": "string"},
                    "encoding": {"const": "utf-8"},
                },
                "required": ["target", "content"],
            },
            "PackageProposalCheck": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"args": {"type": "array", "items": {"type": "string"}}},
            },
        },
    }


def registered_tool_summary(name: str) -> dict[str, object]:
    summary: dict[str, object] = {
        "name": name,
        "descriptionStartsUseThisWhen": True,
        "annotations": chatgpt_mcp.TOOL_SPECS[name].annotation_payload(),
        "outputSchema": chatgpt_mcp.tool_output_schema(name),
    }
    if name == "submit_package_proposal":
        summary["inputSchema"] = submit_package_proposal_input_schema()
    return summary


def assert_repo_root_not_serialized(testcase: unittest.TestCase, root: Path, payload: dict[str, object]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    root_text = str(root)
    testcase.assertNotIn(root_text, serialized)
    testcase.assertNotIn(root_text.replace("\\", "\\\\"), serialized)
    testcase.assertNotIn(root_text.replace("\\", "/"), serialized)


class RiftReaderChatGptMcpTests(unittest.TestCase):
    def test_manifest_exposes_exact_safe_tool_set_with_annotations(self) -> None:
        manifest = chatgpt_mcp.tool_manifest()

        self.assertEqual([item["name"] for item in manifest["tools"]], list(chatgpt_mcp.EXPECTED_TOOL_ORDER))
        annotation_by_name = {item["name"]: item["annotations"] for item in manifest["tools"]}
        allowed_args_by_name = {item["name"]: item["allowedArgumentKeys"] for item in manifest["tools"]}
        output_schema_by_name = {item["name"]: item["outputSchema"] for item in manifest["tools"]}
        self.assertTrue(annotation_by_name["health"]["readOnlyHint"])
        self.assertTrue(annotation_by_name["get_repo_status"]["readOnlyHint"])
        self.assertTrue(annotation_by_name["get_workflow_control_summary"]["readOnlyHint"])
        self.assertTrue(annotation_by_name["get_workflow_control_plan"]["readOnlyHint"])
        self.assertTrue(annotation_by_name["repo_tree_tracked"]["readOnlyHint"])
        self.assertTrue(annotation_by_name["repo_search_tracked"]["readOnlyHint"])
        self.assertTrue(annotation_by_name["repo_read_tracked_file"]["readOnlyHint"])
        self.assertTrue(annotation_by_name["repo_read_many_tracked_files"]["readOnlyHint"])
        self.assertTrue(annotation_by_name["repo_context_pack"]["readOnlyHint"])
        self.assertFalse(annotation_by_name["submit_package_proposal"]["readOnlyHint"])
        self.assertFalse(annotation_by_name["create_package_draft_from_inbox"]["readOnlyHint"])
        self.assertFalse(annotation_by_name["dry_run_latest_package_draft"]["readOnlyHint"])
        self.assertFalse(annotation_by_name["apply_latest_package_draft"]["readOnlyHint"])
        self.assertFalse(annotation_by_name["commit_reviewed_slice"]["readOnlyHint"])
        self.assertEqual(allowed_args_by_name["health"], [])
        self.assertEqual(allowed_args_by_name["get_workflow_control_summary"], [])
        self.assertEqual(allowed_args_by_name["submit_package_proposal"], ["proposal"])
        self.assertEqual(allowed_args_by_name["create_package_draft_from_inbox"], ["inboxId"])
        self.assertEqual(allowed_args_by_name["dry_run_latest_package_draft"], ["operatorOnly", "timeoutSeconds"])
        self.assertEqual(
            allowed_args_by_name["apply_latest_package_draft"],
            ["approvalToken", "dryRunDiffSha256", "dryRunSummaryPath", "operatorOnly", "timeoutSeconds"],
        )
        self.assertEqual(
            allowed_args_by_name["commit_reviewed_slice"],
            [
                "approvalToken",
                "commitMessage",
                "expectedHead",
                "paths",
                "timeoutSeconds",
                "validationDigest",
                "validationSummaryPath",
            ],
        )
        self.assertEqual(allowed_args_by_name["repo_tree_tracked"], ["depth", "includeBlockedMeta", "limit", "prefix"])
        self.assertEqual(
            allowed_args_by_name["repo_search_tracked"],
            ["caseSensitive", "maxFileBytes", "maxMatches", "query", "regex"],
        )
        self.assertEqual(allowed_args_by_name["repo_read_tracked_file"], ["includeSha256", "maxBytes", "path"])
        self.assertEqual(
            allowed_args_by_name["repo_read_many_tracked_files"],
            ["maxFileBytes", "maxFiles", "maxTotalBytes", "paths"],
        )
        self.assertEqual(allowed_args_by_name["repo_context_pack"], ["maxFileBytes", "maxFiles", "maxTotalBytes", "packName"])
        for annotations in annotation_by_name.values():
            self.assertFalse(annotations["destructiveHint"])
            self.assertFalse(annotations["openWorldHint"])
        for name, schema in output_schema_by_name.items():
            self.assertEqual(schema["type"], "object")
            self.assertIn("schemaVersion", schema["required"])
            self.assertEqual(schema["properties"]["schemaVersion"]["const"], chatgpt_mcp.SCHEMA_VERSION)

    def test_public_read_only_manifest_exposes_only_phase0_tools(self) -> None:
        manifest = chatgpt_mcp.tool_manifest(chatgpt_mcp.TOOL_PROFILE_PUBLIC_READ_ONLY)

        names = [item["name"] for item in manifest["tools"]]
        self.assertEqual(names, list(chatgpt_mcp.PUBLIC_READ_ONLY_TOOL_ORDER))
        self.assertNotIn("submit_package_proposal", names)
        self.assertNotIn("dry_run_latest_package_draft", names)
        self.assertNotIn("apply_latest_package_draft", names)
        self.assertNotIn("commit_reviewed_slice", names)
        self.assertTrue(all(item["annotations"]["readOnlyHint"] for item in manifest["tools"]))
        self.assertFalse(manifest["safety"]["writeLikeToolsExposed"])
        self.assertEqual(chatgpt_mcp.tool_manifest()["toolProfile"], chatgpt_mcp.TOOL_PROFILE_FULL)

    def test_health_reports_no_broad_mcp_proxy_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)

            payload = adapter.call_tool("health", {})

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["repoRoot"], ".")
        self.assertEqual(payload["repoName"], root.name)
        self.assertNotIn(str(root), json.dumps(payload))
        self.assertTrue(payload["safety"]["noRiftGameMcpProxy"])
        self.assertTrue(payload["safety"]["noWindowsMcpProxy"])
        self.assertTrue(payload["safety"]["noShellExecutionEndpoint"])
        self.assertTrue(payload["safety"]["noBroadGitMutationEndpoint"])
        self.assertTrue(payload["safety"]["gitMutationEndpointLimitedToCommitReviewedSlice"])
        self.assertTrue(payload["safety"]["noRemoteGitMutationEndpoint"])
        self.assertTrue(payload["safety"]["noBranchRewriteEndpoint"])
        self.assertTrue(payload["safety"]["noDestructiveGitCleanupEndpoint"])
        self.assertTrue(payload["safety"]["auditUnderDotRiftReaderLocal"])
        self.assertFalse(payload["safety"]["absoluteRepoRootExposed"])
        self.assertEqual(payload["chatGptToolFacade"]["packageProofToolOrder"], list(chatgpt_mcp.PACKAGE_PROOF_TOOL_ORDER))
        self.assertIn("Refresh the rift-mcp app", payload["chatGptToolFacade"]["ifToolUnavailable"])

    def test_tool_result_contract_blocks_malformed_handler_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)
            with mock.patch.object(adapter, "health", return_value={"status": "passed"}):
                payload = adapter.call_tool("health", {})

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "TOOL_RESULT_CONTRACT_INVALID")
        self.assertIn("tool-result-schema-version-invalid:health:None", payload["contractBlockers"])
        self.assertIn("tool-result-kind-invalid:health:None", payload["contractBlockers"])
        self.assertIn("tool-result-ok-not-boolean:health:None", payload["contractBlockers"])

    def test_tool_result_contract_accepts_current_health_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)
            payload = adapter.call_tool("health", {})

        self.assertEqual(chatgpt_mcp.validate_tool_result_payload("health", payload), [])

    def test_latest_handoff_reads_only_allowlisted_handoff_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            older = root / "docs" / "handoffs" / "2026-05-18-older.md"
            newer = root / "docs" / "handoffs" / "2026-05-18-newer.md"
            older.write_text("# Older\n", encoding="utf-8")
            newer.write_text("# Newer\n\n## TL;DR\n\nReady.\n", encoding="utf-8")
            os.utime(older, (1_700_000_000, 1_700_000_000))
            os.utime(newer, (1_800_000_000, 1_800_000_000))
            adapter = make_adapter(root)

            payload = adapter.call_tool("get_latest_handoff", {})

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["title"], "Newer")
        self.assertEqual(payload["path"], "docs\\handoffs\\2026-05-18-newer.md")
        self.assertIn("Ready.", payload["text"])
        self.assertTrue(payload["safety"]["handoffDirAllowlisted"])

    def test_package_proposal_template_reuses_bridge_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)

            payload = adapter.call_tool("get_package_proposal_template", {})

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["template"]["kind"], "package-proposal")
        self.assertEqual(payload["inboxSchema"]["packageProposalTemplate"]["kind"], "package-proposal")

    def test_submit_package_proposal_stores_only_local_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)

            payload = adapter.call_tool("submit_package_proposal", {"proposal": package_proposal()})

            target = root / "docs" / "proposed.md"
            inbox_root = root / ".riftreader-local" / "artifact-bridge-inbox"
            audit_root = root / ".riftreader-local" / "riftreader-chatgpt-mcp" / "audit"

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["status"], "stored")
            self.assertFalse(target.exists())
            self.assertTrue(str(payload["storedUnder"]).startswith(".riftreader-local"))
            self.assertTrue(inbox_root.is_dir())
            self.assertTrue(audit_root.is_dir())
            self.assertTrue(payload["safety"]["localInboxOnly"])
            self.assertTrue(payload["safety"]["noPackageDraftCreatedBySubmit"])

    def test_submit_rejects_unsafe_package_targets_before_inbox_write(self) -> None:
        unsafe_targets = [
            "../outside.md",
            "C:\\RIFT MODDING\\RiftReader\\docs\\pwned.md",
            ".git/config",
            ".riftreader-local/pwned.md",
            "scripts/captures/pwned.md",
        ]
        for target in unsafe_targets:
            with self.subTest(target=target):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    make_repo(root)
                    adapter = make_adapter(root)

                    payload = adapter.call_tool("submit_package_proposal", {"proposal": package_proposal(target=target)})

                    self.assertFalse(payload["ok"])
                    self.assertEqual(payload["code"], "PACKAGE_PROPOSAL_FILES_INVALID")
                    self.assertTrue(payload["blockers"])
                    self.assertFalse((root / ".riftreader-local" / "artifact-bridge-inbox").exists())

    def test_submit_rejects_unsafe_package_checks_before_inbox_write(self) -> None:
        unsafe_checks = [
            ["git", "add", "."],
            ["scripts\\send-rift-key.ps1", "W"],
            ["cheatengine-exec.ps1"],
            ["C:\\RIFT MODDING\\Tools\\x64dbg\\x64dbg.exe"],
        ]
        for args in unsafe_checks:
            with self.subTest(args=args):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    make_repo(root)
                    adapter = make_adapter(root)
                    proposal = package_proposal()
                    proposal["payload"]["checks"] = [  # type: ignore[index]
                        {
                            "name": "unsafe",
                            "args": args,
                            "expectedExitCodes": [0],
                            "timeoutSeconds": 120,
                        }
                    ]

                    payload = adapter.call_tool("submit_package_proposal", {"proposal": proposal})

                    self.assertFalse(payload["ok"])
                    self.assertEqual(payload["code"], "PACKAGE_PROPOSAL_CHECKS_INVALID")
                    self.assertTrue(payload["blockers"])
                    self.assertFalse((root / ".riftreader-local" / "artifact-bridge-inbox").exists())

    def test_submit_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)
            proposal = package_proposal()
            proposal["unexpected"] = True

            payload = adapter.call_tool("submit_package_proposal", {"proposal": proposal})

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "INBOX_UNKNOWN_FIELD")

    def test_submit_rejects_non_package_message_kind(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)
            proposal = package_proposal()
            proposal["kind"] = "chatgpt-message"

            payload = adapter.call_tool("submit_package_proposal", {"proposal": proposal})

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "PACKAGE_PROPOSAL_KIND_REQUIRED")

    def test_submit_rejects_non_object_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)

            payload = adapter.call_tool("submit_package_proposal", {"proposal": "not an object"})

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "INVALID_ARGUMENT")

    def test_list_inbox_returns_metadata_after_submit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)
            adapter.call_tool("submit_package_proposal", {"proposal": package_proposal()})

            payload = adapter.call_tool("list_inbox", {})

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["inbox"]["count"], 1)
        self.assertEqual(payload["inbox"]["items"][0]["messageKind"], "package-proposal")

    def test_create_package_draft_from_inbox_requires_explicit_valid_inbox_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)

            missing = adapter.call_tool("create_package_draft_from_inbox", {})
            malformed = adapter.call_tool("create_package_draft_from_inbox", {"inboxId": "../outside"})

        self.assertFalse(missing["ok"])
        self.assertEqual(missing["code"], "INBOX_ID_REQUIRED")
        self.assertFalse(malformed["ok"])
        self.assertEqual(malformed["code"], "INBOX_ID_INVALID")

    def test_create_package_draft_from_inbox_writes_only_local_inert_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)
            submitted = adapter.call_tool("submit_package_proposal", {"proposal": package_proposal()})

            payload = adapter.call_tool("create_package_draft_from_inbox", {"inboxId": submitted["inboxId"]})

            target = root / "docs" / "proposed.md"
            draft_root = root / payload["draft"]["draftRoot"]
            summary_path = root / payload["draft"]["summaryPath"]

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["status"], "created")
            self.assertEqual(payload["inboxId"], submitted["inboxId"])
            self.assertTrue(draft_root.is_dir())
            self.assertTrue(summary_path.is_file())
            self.assertFalse(target.exists())
            self.assertTrue(payload["safety"]["localPackageDraftOnly"])
            self.assertTrue(payload["safety"]["explicitInboxIdRequired"])
            self.assertFalse(payload["safety"]["applyFlagSent"])
            self.assertFalse(payload["safety"]["gitMutation"])
            assert_repo_root_not_serialized(self, root, payload)

    def test_review_latest_package_draft_defaults_to_operator_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            operator = make_draft(root, "20260518T120000Z-aaaaaaaaaaaa", title="Operator")
            self_test = make_draft(root, "20260518T130000Z-bbbbbbbbbbbb", title="Self-test", self_test=True)
            os.utime(operator / "summary.json", (1_700_000_000, 1_700_000_000))
            os.utime(self_test / "summary.json", (1_800_000_000, 1_800_000_000))
            adapter = make_adapter(root)

            payload = adapter.call_tool("review_latest_package_draft", {})

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["operatorOnly"])
        self.assertEqual(payload["draftId"], "20260518T120000Z-aaaaaaaaaaaa")
        self.assertEqual(payload["draftReview"]["draft"]["messageTitle"], "Operator")
        self.assertFalse(payload["draftReview"]["draft"]["selfTest"])
        assert_repo_root_not_serialized(self, root, payload)

    def test_dry_run_latest_package_draft_reuses_cached_same_draft_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            draft = make_draft(root, "20260518T130000Z-bbbbbbbbbbbb", title="Dry-run")
            make_cached_dry_run(root, draft, check_counts={"declaredCount": 1, "runCount": 1, "failedCount": 0})
            adapter = make_adapter(root)
            with mock.patch.object(chatgpt_mcp.package_draft_review, "dry_run_latest_package_draft") as dry_run:
                payload = adapter.call_tool(
                    "dry_run_latest_package_draft",
                    {"operatorOnly": True, "timeoutSeconds": 30},
                )

        dry_run.assert_not_called()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["dryRunSucceeded"])
        self.assertEqual(payload["draftId"], "20260518T130000Z-bbbbbbbbbbbb")
        self.assertEqual(payload["dryRun"]["kind"], "riftreader-package-draft-review-dry-run-cached")
        self.assertEqual(payload["dryRun"]["command"]["args"][0], "cached-dry-run-artifact")
        self.assertTrue(payload["dryRun"]["safety"]["cachedDryRunArtifact"])
        self.assertTrue(payload["dryRun"]["intakeCompactSummary"]["dryRun"])
        self.assertEqual(
            payload["dryRun"]["intakeCompactSummary"]["checks"],
            {"declaredCount": 1, "runCount": 1, "failedCount": 0},
        )
        self.assertTrue(payload["dryRun"]["diffPreview"]["ok"])
        self.assertEqual(payload["dryRun"]["diffPreview"]["artifactPath"], ".riftreader-local\\package-intake\\20260518-180100Z\\package.diff")
        self.assertIn("+# Proposed", payload["dryRun"]["diffPreview"]["text"])
        self.assertFalse(payload["dryRun"]["diffPreview"]["truncated"])
        self.assertTrue(payload["dryRun"]["diffPreview"]["safety"]["diffArtifactUnderPackageIntake"])
        assert_repo_root_not_serialized(self, root, payload)

    def test_dry_run_latest_package_draft_bounds_cached_diff_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            draft = make_draft(root, "20260518T130000Z-bbbbbbbbbbbb", title="Dry-run")
            cached = make_cached_dry_run(root, draft)
            diff_path = cached.parent / "package.diff"
            diff_path.write_text("x" * (chatgpt_mcp.MAX_DRY_RUN_DIFF_PREVIEW_BYTES + 128), encoding="utf-8")
            adapter = make_adapter(root)

            payload = adapter.call_tool("dry_run_latest_package_draft", {"operatorOnly": True, "timeoutSeconds": 30})

        preview = payload["dryRun"]["diffPreview"]
        self.assertTrue(preview["ok"])
        self.assertTrue(preview["truncated"])
        self.assertEqual(len(preview["text"]), chatgpt_mcp.MAX_DRY_RUN_DIFF_PREVIEW_BYTES)
        self.assertIn("package-intake-diff-preview-truncated", preview["warnings"])
        assert_repo_root_not_serialized(self, root, payload)

    def test_dry_run_latest_package_draft_blocks_unsafe_diff_preview_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            draft = make_draft(root, "20260518T130000Z-bbbbbbbbbbbb", title="Dry-run")
            cached = make_cached_dry_run(root, draft)
            compact = json.loads(cached.read_text(encoding="utf-8"))
            compact["artifacts"]["diff"] = str(root / "outside.diff")
            cached.write_text(json.dumps(compact, indent=2), encoding="utf-8")
            adapter = make_adapter(root)

            payload = adapter.call_tool("dry_run_latest_package_draft", {"operatorOnly": True, "timeoutSeconds": 30})

        preview = payload["dryRun"]["diffPreview"]
        self.assertFalse(preview["ok"])
        self.assertEqual(preview["code"], "DIFF_ARTIFACT_OUTSIDE_PACKAGE_INTAKE")
        self.assertEqual(preview["artifactPath"], "<outside-package-intake>")
        self.assertNotIn("outside.diff", json.dumps(preview))
        assert_repo_root_not_serialized(self, root, payload)

    def test_dry_run_latest_package_draft_ignores_stale_cached_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            draft = make_draft(root, "20260518T130000Z-bbbbbbbbbbbb", title="Dry-run")
            cached = make_cached_dry_run(root, draft)
            package_file = draft / "package" / "files" / "file-0001.txt"
            package_file.write_text("# Updated after cached dry-run\n", encoding="utf-8")
            os.utime(package_file, (2_000_000_000, 2_000_000_000))
            os.utime(cached, (1_900_000_000, 1_900_000_000))
            adapter = make_adapter(root)
            with mock.patch.object(chatgpt_mcp.package_draft_review, "dry_run_latest_package_draft") as dry_run:
                dry_run.return_value = {
                    "status": "passed",
                    "ok": True,
                    "draft": {"draftId": "20260518T130000Z-bbbbbbbbbbbb"},
                    "command": {"args": ["scripts\\riftreader-package-intake.cmd"]},
                    "safety": {"applyFlagSent": False},
                }
                payload = adapter.call_tool("dry_run_latest_package_draft", {"operatorOnly": True})

        dry_run.assert_called_once()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["dryRun"]["kind"], None)
        self.assertEqual(payload["draftId"], "20260518T130000Z-bbbbbbbbbbbb")

    def test_dry_run_latest_package_draft_never_passes_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            make_draft(root, "20260518T130000Z-bbbbbbbbbbbb", title="Dry-run")
            adapter = make_adapter(root)

            payload = adapter.call_tool("dry_run_latest_package_draft", {"operatorOnly": True, "timeoutSeconds": 30})

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["safety"]["packageIntakeDryRunOnly"])
        self.assertFalse(payload["safety"]["applyFlagSent"])
        self.assertNotIn("--apply", payload["dryRun"]["command"]["args"])
        assert_repo_root_not_serialized(self, root, payload)

    def test_dry_run_blocks_apply_flag_variants_from_helper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)
            helper_payload = {
                "status": "passed",
                "ok": True,
                "command": {"args": ["scripts\\riftreader-package-intake.cmd", "--apply=true"]},
            }
            with mock.patch.object(chatgpt_mcp.package_draft_review, "dry_run_latest_package_draft", return_value=helper_payload):
                payload = adapter.call_tool("dry_run_latest_package_draft", {"operatorOnly": True})

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "DRY_RUN_APPLY_FLAG_BLOCKED")

    def test_apply_latest_package_draft_blocks_without_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)
            helper_payload = {
                "status": "blocked",
                "ok": False,
                "applied": False,
                "preflight": {"approvalFacts": {"draftId": "20260518T130000Z-bbbbbbbbbbbb"}},
                "blockers": ["APPLY_APPROVAL_MISSING"],
                "warnings": [],
                "safety": {"applyFlagSent": False, "repoSourceMutationExpected": False},
            }
            with mock.patch.object(
                chatgpt_mcp.package_draft_review,
                "apply_latest_package_draft_bridge",
                return_value=helper_payload,
            ) as apply_bridge:
                payload = adapter.call_tool(
                    "apply_latest_package_draft",
                    {
                        "operatorOnly": True,
                        "dryRunSummaryPath": ".riftreader-local/package-intake/example/package-intake-summary.json",
                        "dryRunDiffSha256": "0" * 64,
                        "timeoutSeconds": 30,
                    },
                )

        apply_bridge.assert_called_once()
        self.assertFalse(payload["ok"])
        self.assertFalse(payload["applied"])
        self.assertIn("APPLY_APPROVAL_MISSING", payload["blockers"])
        self.assertFalse(payload["safety"]["applyFlagSent"])
        self.assertFalse(payload["safety"]["repoSourceMutationExpected"])
        assert_repo_root_not_serialized(self, root, payload)

    def test_apply_latest_package_draft_surfaces_preflight_check_counts_without_applying(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            draft = make_draft(root, "20260518T130000Z-bbbbbbbbbbbb", title="Apply preflight counts")
            summary_path, diff_sha256 = make_full_dry_run_summary(
                root,
                draft,
                declared_checks=[{"name": "py-compile"}],
                check_results=[{"label": "py-compile", "ok": True, "exitCode": 0}],
            )
            adapter = make_adapter(root)
            with mock.patch.object(chatgpt_mcp.package_draft_review, "run_command_envelope") as run_command:
                payload = adapter.call_tool(
                    "apply_latest_package_draft",
                    {
                        "operatorOnly": True,
                        "dryRunSummaryPath": str(summary_path.relative_to(root)),
                        "dryRunDiffSha256": diff_sha256,
                        "timeoutSeconds": 30,
                    },
                )

        self.assertFalse(payload["ok"])
        self.assertFalse(payload["applied"])
        self.assertIn("APPLY_APPROVAL_MISSING", payload["blockers"])
        preflight = payload["applyResult"]["preflight"]
        self.assertEqual(preflight["status"], "ready")
        self.assertEqual(preflight["dryRun"]["declaredCheckCount"], 1)
        self.assertEqual(preflight["dryRun"]["runCheckCount"], 1)
        self.assertEqual(preflight["dryRun"]["failedCheckCount"], 0)
        self.assertFalse(payload["safety"]["applyFlagSent"])
        run_command.assert_not_called()
        assert_repo_root_not_serialized(self, root, payload)

    def test_apply_latest_package_draft_blocks_declared_dry_run_checks_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            draft = make_draft(root, "20260518T130000Z-bbbbbbbbbbbb", title="Skipped checks")
            summary_path, diff_sha256 = make_full_dry_run_summary(
                root,
                draft,
                declared_checks=[{"name": "py-compile"}],
                check_results=[],
            )
            adapter = make_adapter(root)
            with mock.patch.object(chatgpt_mcp.package_draft_review, "run_command_envelope") as run_command:
                payload = adapter.call_tool(
                    "apply_latest_package_draft",
                    {
                        "operatorOnly": True,
                        "dryRunSummaryPath": str(summary_path.relative_to(root)),
                        "dryRunDiffSha256": diff_sha256,
                        "timeoutSeconds": 30,
                    },
                )

        self.assertFalse(payload["ok"])
        self.assertFalse(payload["applied"])
        self.assertIn("APPLY_DRY_RUN_DECLARED_CHECKS_NOT_RUN", payload["blockers"])
        self.assertIn("APPLY_PREFLIGHT_NOT_READY", payload["blockers"])
        self.assertIn("APPLY_APPROVAL_MISSING", payload["blockers"])
        self.assertFalse(payload["safety"]["applyFlagSent"])
        run_command.assert_not_called()
        assert_repo_root_not_serialized(self, root, payload)

    def test_commit_reviewed_slice_blocks_without_approval_and_does_not_mutate_git(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)
            helper_payload = {
                "schemaVersion": 1,
                "kind": "riftreader-commit-reviewed-slice-apply",
                "status": "blocked",
                "ok": False,
                "committed": False,
                "commitHash": None,
                "preflight": {
                    "status": "ready",
                    "ok": True,
                    "expectedApprovalToken": "COMMIT-0123456789abcdef",
                },
                "blockers": ["COMMIT_APPROVAL_MISSING"],
                "warnings": [],
                "commands": [],
                "safety": {
                    "gitMutation": False,
                    "localCommitOnly": True,
                    "remoteMutation": False,
                    "branchRewrite": False,
                    "destructiveCleanup": False,
                    "explicitPathsOnly": True,
                    "stagedFiles": False,
                    "committed": False,
                    "pushed": False,
                },
            }
            with mock.patch.object(
                chatgpt_mcp.commit_reviewed_slice,
                "commit_reviewed_slice_apply",
                return_value=helper_payload,
            ) as commit_apply:
                payload = adapter.call_tool(
                    "commit_reviewed_slice",
                    {
                        "expectedHead": "a" * 40,
                        "paths": ["docs/HANDOFF.md"],
                        "commitMessage": "Update handoff",
                        "validationSummaryPath": ".riftreader-local/validation-runs/example/summary.json",
                        "validationDigest": "b" * 64,
                        "timeoutSeconds": 30,
                    },
                )

        commit_apply.assert_called_once()
        self.assertFalse(payload["ok"])
        self.assertFalse(payload["committed"])
        self.assertIn("COMMIT_APPROVAL_MISSING", payload["blockers"])
        self.assertFalse(payload["safety"]["gitMutation"])
        self.assertFalse(payload["safety"]["remoteMutation"])
        self.assertFalse(payload["safety"]["branchRewrite"])
        self.assertFalse(payload["safety"]["destructiveCleanup"])
        self.assertTrue(payload["safety"]["gitMutationEndpointLimitedToCommitReviewedSlice"])
        assert_repo_root_not_serialized(self, root, payload)

    def test_invalid_operator_only_type_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)

            payload = adapter.call_tool("review_latest_package_draft", {"operatorOnly": "false"})

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "INVALID_BOOLEAN")

    def test_boolean_timeout_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)

            payload = adapter.call_tool("dry_run_latest_package_draft", {"timeoutSeconds": True})

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "INVALID_TIMEOUT")

    def test_unknown_tool_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)

            payload = adapter.call_tool("shell", {})

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "TOOL_NOT_EXPOSED")

    def test_non_object_tool_arguments_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)

            payload = adapter.call_tool("health", ["not", "an", "object"])  # type: ignore[arg-type]

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "INVALID_ARGUMENTS")

    def test_unexpected_tool_arguments_are_blocked_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)

            payload = adapter.call_tool("health", {"ignored": True})

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "UNEXPECTED_TOOL_ARGUMENTS")
        self.assertEqual(payload["unexpectedKeys"], ["ignored"])
        self.assertEqual(payload["allowedKeys"], [])

    def test_submit_blocks_unexpected_wrapper_arguments_before_inbox_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)

            payload = adapter.call_tool(
                "submit_package_proposal",
                {"proposal": package_proposal(), "apply": True},
            )

            self.assertFalse(payload["ok"])
            self.assertEqual(payload["code"], "UNEXPECTED_TOOL_ARGUMENTS")
            self.assertIn("apply", payload["unexpectedKeys"])
            self.assertFalse((root / ".riftreader-local" / "artifact-bridge-inbox").exists())

    def test_repo_context_tools_read_only_tracked_files_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_tracked_context_repo(root)
            adapter = make_adapter(root)

            tree = adapter.call_tool("repo_tree_tracked", {"prefix": "docs", "limit": 10})
            read_one = adapter.call_tool(
                "repo_read_tracked_file",
                {"path": "docs/workflow/intro.md", "maxBytes": 4096, "includeSha256": True},
            )
            read_many = adapter.call_tool(
                "repo_read_many_tracked_files",
                {
                    "paths": ["docs/workflow/intro.md", "tools/riftreader_workflow/helper.py"],
                    "maxFileBytes": 4096,
                    "maxTotalBytes": 8192,
                },
            )
            search = adapter.call_tool("repo_search_tracked", {"query": "needle", "maxMatches": 5})
            pack = adapter.call_tool(
                "repo_context_pack",
                {"packName": "workflow-docs", "maxFiles": 2, "maxFileBytes": 4096, "maxTotalBytes": 8192},
            )
            blocked_secret = adapter.call_tool("repo_read_tracked_file", {"path": ".env"})
            blocked_local = adapter.call_tool("repo_read_tracked_file", {"path": ".riftreader-local/local.md"})
            blocked_binary = adapter.call_tool("repo_read_tracked_file", {"path": "data/blob.bin"})

        self.assertTrue(tree["ok"], tree)
        self.assertEqual(tree["kind"], "riftreader-chatgpt-mcp-repo-tree-tracked")
        self.assertLessEqual(tree["count"], 10)
        self.assertIn("docs/workflow/intro.md", {row["path"] for row in tree["files"]})
        self.assertTrue(read_one["ok"], read_one)
        self.assertEqual(read_one["kind"], "riftreader-chatgpt-mcp-repo-read-tracked-file")
        self.assertIn("needle line", read_one["content"])
        self.assertIn("sha256", read_one)
        self.assertTrue(read_one["safety"]["gitTrackedFilesOnly"])
        self.assertTrue(read_many["ok"], read_many)
        self.assertEqual(read_many["returnedCount"], 2)
        self.assertTrue(search["ok"], search)
        self.assertEqual(search["kind"], "riftreader-chatgpt-mcp-repo-search-tracked")
        self.assertGreaterEqual(search["matchCount"], 2)
        self.assertTrue(pack["ok"], pack)
        self.assertEqual(pack["packName"], "workflow-docs")
        self.assertFalse(blocked_secret["ok"])
        self.assertEqual(blocked_secret["reason"], "secret-like-name")
        self.assertFalse(blocked_local["ok"])
        self.assertEqual(blocked_local["reason"], "blocked-directory")
        self.assertFalse(blocked_binary["ok"])
        self.assertEqual(blocked_binary["reason"], "blocked-extension")

    def test_repo_context_tool_argument_caps_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_tracked_context_repo(root)
            adapter = make_adapter(root)

            too_many_tree_items = adapter.call_tool(
                "repo_tree_tracked",
                {"limit": chatgpt_mcp.MCP_REPO_TREE_MAX_LIMIT + 1},
            )
            non_list_paths = adapter.call_tool("repo_read_many_tracked_files", {"paths": "docs/workflow/intro.md"})
            too_large_read = adapter.call_tool(
                "repo_read_tracked_file",
                {"path": "docs/workflow/intro.md", "maxBytes": chatgpt_mcp.MCP_REPO_READ_FILE_MAX_BYTES + 1},
            )

        self.assertFalse(too_many_tree_items["ok"])
        self.assertEqual(too_many_tree_items["code"], "INVALID_INTEGER")
        self.assertFalse(non_list_paths["ok"])
        self.assertEqual(non_list_paths["code"], "INVALID_STRING_LIST")
        self.assertFalse(too_large_read["ok"])
        self.assertEqual(too_large_read["code"], "INVALID_INTEGER")

    def test_tool_arguments_must_be_json_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)

            payload = adapter.call_tool(
                "submit_package_proposal",
                {"proposal": {"not_json": {Path("x")}}},
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "TOOL_ARGUMENTS_NOT_JSON_SERIALIZABLE")

    def test_get_repo_status_uses_existing_status_packet_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)
            packet = {"status": "passed", "blockers": [], "warnings": [], "errors": []}
            compact = {"status": "passed", "git": {"branch": "## main", "isClean": True}}
            with mock.patch.object(chatgpt_mcp.status_packet, "build_status_packet", return_value=packet) as build:
                with mock.patch.object(chatgpt_mcp.status_packet, "compact_summary", return_value=compact):
                    payload = adapter.call_tool("get_repo_status", {})

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["compact"], compact)
        build.assert_called_once()

    def test_get_workflow_control_summary_is_tiny_transport_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)
            with (
                mock.patch.object(chatgpt_mcp.mcp_mission_control, "mission_control") as mission_control,
                mock.patch.object(chatgpt_mcp.safe_commit_packager, "safe_commit_plan") as safe_commit_plan,
            ):
                payload = adapter.call_tool("get_workflow_control_summary", {})

        minified_size = len(json.dumps(payload, separators=(",", ":")))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["controlMode"], "summary-only")
        self.assertEqual(payload["currentProduct"]["toolCount"], len(chatgpt_mcp.EXPECTED_TOOL_ORDER))
        self.assertEqual(payload["currentProduct"]["primaryProofPath"], "cloudflare-named-tunnel-server-url-no-auth")
        self.assertEqual(payload["proofRunPacket"]["serverUrl"], "https://mcp.360madden.com/mcp")
        self.assertEqual(payload["proofRunPacket"]["auth"], "No Authentication")
        self.assertEqual(payload["proofRunPacket"]["connectionMode"], "cloudflare-named-tunnel")
        self.assertIn("--proof-run-packet-md", payload["proofRunPacket"]["cli"])
        self.assertEqual(payload["responseCompaction"]["minifiedBytesTarget"], chatgpt_mcp.WORKFLOW_CONTROL_SUMMARY_MINIFIED_BYTES_TARGET)
        self.assertIn("get_workflow_control_summary", payload["safeReadSequence"])
        self.assertIn("get_workflow_control_plan", payload["transportFallback"]["ifFullPlanTimesOut"])
        self.assertEqual(
            payload["actualClientProofRecovery"]["packageProofToolOrder"],
            list(chatgpt_mcp.PACKAGE_PROOF_TOOL_ORDER),
        )
        self.assertIn("APPLY_APPROVAL_MISSING", payload["actualClientProofRecovery"]["operatorPrompt"])
        self.assertLessEqual(minified_size, chatgpt_mcp.WORKFLOW_CONTROL_SUMMARY_MINIFIED_BYTES_TARGET)
        self.assertTrue(payload["safety"]["readOnlyControlSummary"])
        self.assertFalse(payload["safety"]["gitMutation"])
        self.assertFalse(payload["safety"]["shellExecutionEndpoint"])
        mission_control.assert_not_called()
        safe_commit_plan.assert_not_called()

    def test_get_workflow_control_plan_is_plan_only_and_surfaces_safe_commit_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)
            mission_payload = {
                "status": "blocked",
                "ok": False,
                "operatorNextAction": {"key": "safe-next", "command": ["scripts\\x.cmd", "--json"]},
                "finalStatus": {"status": "blocked", "secureTunnelClient": {"status": "passed"}},
                "finalProductProgress": {"completedPhaseCount": 4, "totalPhaseCount": 8},
                "pasteSafeCommands": {
                    "manualPublicIpPlan": ["scripts\\riftreader-chatgpt-mcp.cmd", "--manual-public-ip-plan", "--json"]
                },
                "rankedActions": [{"key": "safe-next"}],
                "warnings": [],
                "blockers": [],
            }
            commit_plan = {
                "status": "ready",
                "stageablePaths": ["docs/example.md"],
                "pasteSafeGitAddCommands": ['git add -- "docs/example.md"'],
                "draftCommitMessage": "Update docs",
                "validationCommandsBeforeCommit": ["python -m unittest scripts.test_riftreader_chatgpt_mcp"],
                "containsGitAddDot": False,
                "safety": {"planOnly": True, "gitMutation": False},
            }
            with (
                mock.patch.object(chatgpt_mcp.mcp_mission_control, "mission_control", return_value=mission_payload),
                mock.patch.object(chatgpt_mcp.safe_commit_packager, "safe_commit_plan", return_value=commit_plan),
            ):
                payload = adapter.call_tool("get_workflow_control_plan", {})

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["controlMode"], "plan-only")
        self.assertIn("submit_package_proposal", payload["bidirectionalDataTransfer"]["writeToLocalInbox"])
        self.assertIn("apply_latest_package_draft", payload["bidirectionalDataTransfer"]["applyApprovedDraft"])
        self.assertIn("commit_reviewed_slice", payload["bidirectionalDataTransfer"]["commitApprovedSlice"])
        self.assertEqual(payload["safeCommitPlan"]["stageablePaths"], ["docs/example.md"])
        self.assertFalse(payload["safety"]["gitMutation"])
        self.assertFalse(payload["safety"]["shellExecutionEndpoint"])
        self.assertIn("git-push", payload["gatedActions"])
        roadmap_by_key = {item["key"]: item for item in payload["futureCapabilityRoadmap"]}
        self.assertIn("apply-package-to-repo", roadmap_by_key)
        self.assertIn("bounded-shell-command", roadmap_by_key)
        self.assertEqual(roadmap_by_key["apply-package-to-repo"]["currentStatus"], "exposed-gated")
        self.assertEqual(roadmap_by_key["push-current-branch"]["currentStatus"], "designed-not-exposed")
        self.assertIn("review_latest_package_draft", roadmap_by_key["apply-package-to-repo"]["safePrecursorTools"])
        self.assertIn("commit-local-slice", payload["gatedActions"])
        self.assertEqual(payload["futureCapabilityPolicy"]["status"], "push-design-complete-preflight-next")
        self.assertEqual(payload["fullProductStagePlan"]["stageCount"], 50)
        self.assertEqual(payload["fullProductStagePlan"]["currentStage"], 29)
        self.assertEqual(payload["fullProductStagePlan"]["nextStage"], 30)
        self.assertEqual(
            payload["fullProductStagePlan"]["planPath"],
            "docs/workflow/riftreader-chatgpt-mcp-50-stage-plan.md",
        )
        self.assertGreaterEqual(len(payload["fullProductStagePlan"]["immediateStages"]), 5)
        future_contract = payload["futureToolContracts"]["apply_latest_package_draft"]
        self.assertEqual(future_contract["status"], "exposed-gated")
        self.assertEqual(future_contract["targetToolName"], "apply_latest_package_draft")
        self.assertEqual(
            future_contract["designPath"],
            "docs/workflow/riftreader-chatgpt-mcp-apply-tool-design.md",
        )
        self.assertEqual(future_contract["currentStage"], 20)
        self.assertEqual(future_contract["preflightHelper"]["status"], "implemented-local-only")
        self.assertFalse(future_contract["preflightHelper"]["mutatesRepo"])
        self.assertFalse(future_contract["preflightHelper"]["passesApplyFlag"])
        self.assertEqual(future_contract["applyBridgeHelper"]["status"], "implemented-and-mcp-wrapped")
        self.assertTrue(future_contract["applyBridgeHelper"]["requiresApprovalToken"])
        self.assertFalse(future_contract["applyBridgeHelper"]["gitMutation"])
        self.assertTrue(future_contract["applyBridgeHelper"]["mcpToolExposed"])
        self.assertIn("dryRunDiffSha256", future_contract["argumentKeys"])
        self.assertIn("diff-hash-binding", future_contract["requiredGates"])
        self.assertIn("APPLY_DRY_RUN_HASH_MISMATCH", future_contract["failClosedBlockers"])
        self.assertEqual(future_contract["exposureStatus"], "exposed-gated")
        push_contract = payload["futureToolContracts"]["push_current_branch"]
        self.assertEqual(push_contract["status"], "designed-not-exposed")
        self.assertEqual(push_contract["targetToolName"], "push_current_branch")
        self.assertEqual(
            push_contract["designPath"],
            "docs/workflow/riftreader-chatgpt-mcp-push-tool-design.md",
        )
        self.assertEqual(push_contract["currentStage"], 28)
        self.assertEqual(push_contract["exposureStatus"], "not-exposed")
        self.assertEqual(push_contract["preflightHelper"]["status"], "planned-stage-29")
        self.assertFalse(push_contract["preflightHelper"]["mutatesRepo"])
        self.assertFalse(push_contract["preflightHelper"]["pushesRemote"])
        self.assertTrue(push_contract["pushExecutionHelper"]["requiresApprovalToken"])
        self.assertTrue(push_contract["pushExecutionHelper"]["remoteMutation"])
        self.assertFalse(push_contract["pushExecutionHelper"]["mcpToolExposed"])
        self.assertIn("expectedHead", push_contract["argumentKeys"])
        self.assertIn("no-force-push", push_contract["requiredGates"])
        self.assertIn("PUSH_APPROVAL_MISSING", push_contract["failClosedBlockers"])
        self.assertIn("apply_latest_package_draft", chatgpt_mcp.EXPECTED_TOOL_ORDER)
        self.assertIn("apply_latest_package_draft", chatgpt_mcp.TOOL_SPECS)
        self.assertNotIn("push_current_branch", chatgpt_mcp.EXPECTED_TOOL_ORDER)
        self.assertNotIn("push_current_branch", chatgpt_mcp.TOOL_SPECS)
        self.assertNotIn("run_bounded_repo_command", chatgpt_mcp.TOOL_SPECS)

    def test_get_workflow_control_plan_is_transport_sized_for_chatgpt_mcp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)
            mission_payload = {
                "status": "blocked",
                "ok": False,
                "operatorNextAction": {"key": "safe-next", "command": ["scripts\\x.cmd", "--json"]},
                "finalStatus": {
                    "status": "blocked",
                    "ok": False,
                    "secureTunnelClient": {"status": "retired", "ok": True, "blockers": []},
                    "blockers": [f"proof:large-blocker-{index}-" + ("x" * 120) for index in range(50)],
                    "warnings": [f"artifact:large-warning-{index}-" + ("y" * 120) for index in range(50)],
                    "safety": {"gitMutation": False, "providerWrites": False, "inputSent": False},
                },
                "finalProductProgress": {
                    "status": "blocked",
                    "completedPhaseCount": 4,
                    "totalPhaseCount": 8,
                    "phases": [
                        {"phase": index, "name": f"Phase {index}", "status": "pending", "evidence": "z" * 120}
                        for index in range(20)
                    ],
                },
                "pasteSafeCommands": {f"cmd-{index}": ["scripts\\x.cmd", "--json"] for index in range(20)},
                "rankedActions": [
                    {"key": f"action-{index}", "priority": "P1", "reason": "r" * 200, "command": ["scripts\\x.cmd"]}
                    for index in range(20)
                ],
                "warnings": [f"mission-warning-{index}-" + ("w" * 120) for index in range(50)],
                "blockers": [f"mission-blocker-{index}-" + ("b" * 120) for index in range(50)],
            }
            commit_plan = {
                "status": "ready",
                "stageablePaths": [f"docs/example-{index}.md" for index in range(30)],
                "pasteSafeGitAddCommands": [f'git add -- "docs/example-{index}.md"' for index in range(30)],
                "draftCommitMessage": "Update docs",
                "validationCommandsBeforeCommit": ["python -m unittest scripts.test_riftreader_chatgpt_mcp"] * 20,
                "containsGitAddDot": False,
                "safety": {"planOnly": True, "gitMutation": False},
            }
            with (
                mock.patch.object(chatgpt_mcp.mcp_mission_control, "mission_control", return_value=mission_payload),
                mock.patch.object(chatgpt_mcp.safe_commit_packager, "safe_commit_plan", return_value=commit_plan),
            ):
                payload = adapter.call_tool("get_workflow_control_plan", {})

        minified_size = len(json.dumps(payload, separators=(",", ":")))
        self.assertLessEqual(minified_size, chatgpt_mcp.WORKFLOW_CONTROL_MINIFIED_BYTES_TARGET)
        self.assertEqual(payload["responseCompaction"]["status"], "compact")
        self.assertEqual(payload["missionControl"]["blockerCount"], 50)
        self.assertNotIn("blockers", payload["missionControl"])
        self.assertLessEqual(len(payload["safeCommitPlan"]["stageablePaths"]), chatgpt_mcp.WORKFLOW_CONTROL_LIST_LIMIT)

    def test_create_fastmcp_server_registers_tools_with_annotations(self) -> None:
        class FakeAnnotations:
            def __init__(self, *, readOnlyHint: bool, destructiveHint: bool, openWorldHint: bool) -> None:  # noqa: N803
                self.readOnlyHint = readOnlyHint
                self.destructiveHint = destructiveHint
                self.openWorldHint = openWorldHint

        class FakeFastMCP:
            def __init__(self, *args: object, **kwargs: object) -> None:
                self.args = args
                self.kwargs = kwargs
                self.registrations: list[dict[str, object]] = []

            def tool(self, **kwargs: object):
                self.registrations.append(kwargs)

                def decorate(fn):
                    return fn

                return decorate

        mcp_module = types.ModuleType("mcp")
        server_module = types.ModuleType("mcp.server")
        fastmcp_module = types.ModuleType("mcp.server.fastmcp")
        transport_security_module = types.ModuleType("mcp.server.transport_security")
        types_module = types.ModuleType("mcp.types")
        fastmcp_module.FastMCP = FakeFastMCP
        transport_security_module.TransportSecuritySettings = FakeTransportSecuritySettings
        types_module.ToolAnnotations = FakeAnnotations

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)
            with mock.patch.dict(
                sys.modules,
                {
                    "mcp": mcp_module,
                    "mcp.server": server_module,
                    "mcp.server.fastmcp": fastmcp_module,
                    "mcp.server.transport_security": transport_security_module,
                    "mcp.types": types_module,
                },
            ):
                server = chatgpt_mcp.create_fastmcp_server(adapter, host="127.0.0.1", port=8770)

        self.assertEqual(server.args[0], chatgpt_mcp.SERVER_NAME)
        self.assertTrue(server.kwargs["stateless_http"])
        self.assertIsNone(server.kwargs["transport_security"])
        self.assertEqual(len(server.registrations), len(chatgpt_mcp.EXPECTED_TOOL_ORDER))
        by_name = {registration["name"]: registration for registration in server.registrations}
        self.assertTrue(by_name["health"]["annotations"].readOnlyHint)
        self.assertFalse(by_name["submit_package_proposal"]["annotations"].readOnlyHint)
        for registration in server.registrations:
            self.assertIn("Use this when", registration["description"])
            self.assertFalse(registration["annotations"].destructiveHint)
            self.assertFalse(registration["annotations"].openWorldHint)

    def test_create_fastmcp_server_configures_exact_public_allowed_host(self) -> None:
        class FakeAnnotations:
            def __init__(self, *, readOnlyHint: bool, destructiveHint: bool, openWorldHint: bool) -> None:  # noqa: N803
                self.readOnlyHint = readOnlyHint
                self.destructiveHint = destructiveHint
                self.openWorldHint = openWorldHint

        class FakeFastMCP:
            def __init__(self, *args: object, **kwargs: object) -> None:
                self.args = args
                self.kwargs = kwargs
                self.registrations: list[dict[str, object]] = []

            def tool(self, **kwargs: object):
                self.registrations.append(kwargs)

                def decorate(fn):
                    return fn

                return decorate

        mcp_module = types.ModuleType("mcp")
        server_module = types.ModuleType("mcp.server")
        fastmcp_module = types.ModuleType("mcp.server.fastmcp")
        transport_security_module = types.ModuleType("mcp.server.transport_security")
        types_module = types.ModuleType("mcp.types")
        fastmcp_module.FastMCP = FakeFastMCP
        transport_security_module.TransportSecuritySettings = FakeTransportSecuritySettings
        types_module.ToolAnnotations = FakeAnnotations

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)
            with mock.patch.dict(
                sys.modules,
                {
                    "mcp": mcp_module,
                    "mcp.server": server_module,
                    "mcp.server.fastmcp": fastmcp_module,
                    "mcp.server.transport_security": transport_security_module,
                    "mcp.types": types_module,
                },
            ):
                server = chatgpt_mcp.create_fastmcp_server(
                    adapter,
                    host="127.0.0.1",
                    port=8770,
                    allowed_hosts=["example.trycloudflare.com", "example.trycloudflare.com"],
                    allowed_origins=["https://chatgpt.com/"],
                )

        security = server.kwargs["transport_security"]
        self.assertTrue(security.enable_dns_rebinding_protection)
        self.assertIn("127.0.0.1:*", security.allowed_hosts)
        self.assertIn("example.trycloudflare.com", security.allowed_hosts)
        self.assertEqual(security.allowed_hosts.count("example.trycloudflare.com"), 1)
        self.assertIn("https://chatgpt.com", security.allowed_origins)

    def test_allowed_host_normalization_rejects_urls_paths_and_wildcards(self) -> None:
        with self.assertRaises(chatgpt_mcp.AdapterError) as url_error:
            chatgpt_mcp.normalize_allowed_hosts(["https://example.trycloudflare.com"])
        with self.assertRaises(chatgpt_mcp.AdapterError) as path_error:
            chatgpt_mcp.normalize_allowed_hosts(["example.trycloudflare.com/mcp"])
        with self.assertRaises(chatgpt_mcp.AdapterError) as wildcard_error:
            chatgpt_mcp.normalize_allowed_hosts(["*"])

        self.assertEqual(url_error.exception.code, "PUBLIC_HOST_INVALID")
        self.assertEqual(path_error.exception.code, "PUBLIC_HOST_INVALID")
        self.assertEqual(wildcard_error.exception.code, "PUBLIC_HOST_INVALID")

    def test_allowed_origin_normalization_requires_exact_origin(self) -> None:
        self.assertEqual(chatgpt_mcp.normalize_allowed_origins(["https://chatgpt.com/"]), ["https://chatgpt.com"])

        with self.assertRaises(chatgpt_mcp.AdapterError) as path_error:
            chatgpt_mcp.normalize_allowed_origins(["https://chatgpt.com/mcp"])
        with self.assertRaises(chatgpt_mcp.AdapterError) as wildcard_error:
            chatgpt_mcp.normalize_allowed_origins(["https://*.example.com"])
        with self.assertRaises(chatgpt_mcp.AdapterError) as missing_scheme_error:
            chatgpt_mcp.normalize_allowed_origins(["chatgpt.com"])

        self.assertEqual(path_error.exception.code, "PUBLIC_ORIGIN_INVALID")
        self.assertEqual(wildcard_error.exception.code, "PUBLIC_ORIGIN_INVALID")
        self.assertEqual(missing_scheme_error.exception.code, "PUBLIC_ORIGIN_INVALID")

    def test_cloudflare_smoke_parses_tunnel_url_and_verifies_client_result(self) -> None:
        text = "INF +--------------------------------------------------------------------------------------------+\nINF |  https://alpha-beta.trycloudflare.com  |"
        self.assertEqual(chatgpt_mcp.parse_cloudflare_quick_tunnel_url(text), "https://alpha-beta.trycloudflare.com")
        self.assertEqual(chatgpt_mcp.host_from_https_url("https://alpha-beta.trycloudflare.com/mcp"), "alpha-beta.trycloudflare.com")
        self.assertEqual(
            chatgpt_mcp.parse_ipv4_addresses("Addresses: 2606:4700::6810:e684 104.16.230.132 999.1.1.1 104.16.230.132"),
            ["104.16.230.132"],
        )

        client_result = {
            "responses": [
                {"request": {"method": "initialize"}, "exitCode": 0, "httpStatus": 200, "jsonParseError": None, "json": {"result": {}}},
                {"request": {"method": "tools/list"}, "exitCode": 0, "httpStatus": 200, "jsonParseError": None, "json": {"result": {}}},
                {"request": {"method": "tools/call"}, "exitCode": 0, "httpStatus": 200, "jsonParseError": None, "json": {"result": {}}},
            ],
            "toolNames": list(chatgpt_mcp.EXPECTED_TOOL_ORDER),
            "registeredTools": [registered_tool_summary(name) for name in chatgpt_mcp.EXPECTED_TOOL_ORDER],
            "healthIsError": False,
            "healthStructuredContent": {
                "service": chatgpt_mcp.SERVER_NAME,
                "toolCount": len(chatgpt_mcp.EXPECTED_TOOL_ORDER),
                "repoRoot": ".",
                "safety": {"absoluteRepoRootExposed": False},
            },
        }

        self.assertEqual(chatgpt_mcp.verify_cloudflare_smoke_client_result(client_result), [])

    def test_cloudflare_smoke_client_can_cover_apply_denial_sequence(self) -> None:
        calls: list[dict[str, object]] = []

        def tool_response(request: dict[str, object], structured: dict[str, object], *, is_error: bool = False) -> dict[str, object]:
            return {
                "request": {"id": request.get("id"), "method": request.get("method")},
                "exitCode": 0,
                "httpStatus": 200,
                "jsonParseError": None,
                "json": {"result": {"isError": is_error, "structuredContent": structured}},
            }

        def fake_curl_json_rpc_request(**kwargs: object) -> dict[str, object]:
            request = kwargs["request"]
            assert isinstance(request, dict)
            calls.append(request)
            method = request.get("method")
            params = request.get("params") if isinstance(request.get("params"), dict) else {}
            name = params.get("name")
            if method == "initialize":
                return {
                    "request": {"id": request.get("id"), "method": method},
                    "exitCode": 0,
                    "httpStatus": 200,
                    "jsonParseError": None,
                    "json": {"result": {}},
                }
            if method == "tools/list":
                tools = chatgpt_mcp.tool_manifest()["tools"]
                for tool in tools:
                    if tool["name"] == "submit_package_proposal":
                        tool["inputSchema"] = submit_package_proposal_input_schema()
                return {
                    "request": {"id": request.get("id"), "method": method},
                    "exitCode": 0,
                    "httpStatus": 200,
                    "jsonParseError": None,
                    "json": {"result": {"tools": tools}},
                }
            if name == "health":
                return tool_response(
                    request,
                    {
                        "service": chatgpt_mcp.SERVER_NAME,
                        "toolCount": len(chatgpt_mcp.EXPECTED_TOOL_ORDER),
                        "repoRoot": ".",
                        "safety": {"absoluteRepoRootExposed": False},
                    },
                )
            if name == "submit_package_proposal":
                return tool_response(request, {"ok": True, "inboxId": "inbox-1", "safety": {"noRepoTargetWrites": True}})
            if name == "list_inbox":
                return tool_response(request, {"ok": True})
            if name == "create_package_draft_from_inbox":
                return tool_response(
                    request,
                    {"ok": True, "draftId": "draft-1", "safety": {"localPackageDraftOnly": True, "applyFlagSent": False}},
                )
            if name == "review_latest_package_draft":
                return tool_response(request, {"ok": True, "draftId": "draft-1", "safety": {"readOnlyReview": True}})
            if name == "dry_run_latest_package_draft":
                return tool_response(
                    request,
                    {
                        "ok": True,
                        "draftId": "draft-1",
                        "dryRunSucceeded": True,
                        "safety": {"packageIntakeDryRunOnly": True, "applyFlagSent": False},
                        "dryRun": {
                            "diffPreview": {
                                "ok": True,
                                "text": "+# Preview\n",
                                "safety": {"diffArtifactUnderPackageIntake": True, "boundedBytes": True, "applyFlagSent": False},
                            }
                        },
                    },
                )
            if name == "apply_latest_package_draft":
                return tool_response(
                    request,
                    {
                        "ok": False,
                        "status": "blocked",
                        "applied": False,
                        "blockers": ["APPLY_APPROVAL_MISSING"],
                        "safety": {"applyFlagSent": False, "repoSourceMutationExpected": False},
                    },
                )
            raise AssertionError(f"unexpected request: {request!r}")

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            chatgpt_mcp,
            "curl_json_rpc_request",
            side_effect=fake_curl_json_rpc_request,
        ):
            payload = chatgpt_mcp.cloudflare_smoke_client_result(
                curl_executable="curl.exe",
                url="https://example.trycloudflare.com/mcp",
                timeout_seconds=5,
                temp_dir=Path(temp_dir),
                origin="https://chatgpt.com",
                include_proposal_submit=True,
            )

        tool_call_names = [
            request["params"]["name"]
            for request in calls
            if isinstance(request.get("params"), dict) and request.get("method") == "tools/call"
        ]
        self.assertEqual(
            tool_call_names,
            [
                "health",
                "submit_package_proposal",
                "list_inbox",
                "create_package_draft_from_inbox",
                "review_latest_package_draft",
                "dry_run_latest_package_draft",
                "apply_latest_package_draft",
            ],
        )
        self.assertEqual(chatgpt_mcp.verify_cloudflare_smoke_client_result(payload), [])
        self.assertFalse(payload["applyLatestPackageDraftWithoutApprovalStructuredContent"]["applied"])
        self.assertIn("APPLY_APPROVAL_MISSING", payload["applyLatestPackageDraftWithoutApprovalStructuredContent"]["blockers"])

    def test_transport_smoke_result_verifier_blocks_unredacted_health_repo_root(self) -> None:
        registered = [registered_tool_summary(name) for name in chatgpt_mcp.EXPECTED_TOOL_ORDER]
        client_result = {
            "toolNames": list(chatgpt_mcp.EXPECTED_TOOL_ORDER),
            "healthIsError": False,
            "healthStructuredContent": {
                "service": chatgpt_mcp.SERVER_NAME,
                "toolCount": len(chatgpt_mcp.EXPECTED_TOOL_ORDER),
                "repoRoot": "C:\\RIFT MODDING\\RiftReader",
                "safety": {"absoluteRepoRootExposed": True},
            },
            "registeredTools": registered,
        }

        blockers = chatgpt_mcp.verify_transport_smoke_result(client_result)

        self.assertIn("health-repo-root-not-redacted:'C:\\\\RIFT MODDING\\\\RiftReader'", blockers)
        self.assertIn("health-absolute-repo-root-exposure-flag-not-false:True", blockers)

    def test_transport_smoke_result_verifier_accepts_public_read_only_tool_profile(self) -> None:
        registered = [registered_tool_summary(name) for name in chatgpt_mcp.PUBLIC_READ_ONLY_TOOL_ORDER]
        client_result = {
            "toolNames": list(chatgpt_mcp.PUBLIC_READ_ONLY_TOOL_ORDER),
            "healthIsError": False,
            "healthStructuredContent": {
                "service": chatgpt_mcp.SERVER_NAME,
                "toolCount": len(chatgpt_mcp.PUBLIC_READ_ONLY_TOOL_ORDER),
                "toolProfile": chatgpt_mcp.TOOL_PROFILE_PUBLIC_READ_ONLY,
                "repoRoot": ".",
                "safety": {"absoluteRepoRootExposed": False},
            },
            "registeredTools": registered,
        }

        blockers = chatgpt_mcp.verify_transport_smoke_result(
            client_result,
            tool_profile=chatgpt_mcp.TOOL_PROFILE_PUBLIC_READ_ONLY,
        )

        self.assertEqual(blockers, [])

    def test_transport_smoke_result_verifier_blocks_broad_submit_schema(self) -> None:
        registered = [registered_tool_summary(name) for name in chatgpt_mcp.EXPECTED_TOOL_ORDER]
        for tool in registered:
            if tool["name"] == "submit_package_proposal":
                tool["inputSchema"] = {
                    "type": "object",
                    "properties": {"proposal": {"type": "object", "additionalProperties": True}},
                    "required": ["proposal"],
                }
        client_result = {
            "toolNames": list(chatgpt_mcp.EXPECTED_TOOL_ORDER),
            "healthIsError": False,
            "healthStructuredContent": {
                "service": chatgpt_mcp.SERVER_NAME,
                "toolCount": len(chatgpt_mcp.EXPECTED_TOOL_ORDER),
                "repoRoot": ".",
                "safety": {"absoluteRepoRootExposed": False},
            },
            "registeredTools": registered,
        }

        blockers = chatgpt_mcp.verify_transport_smoke_result(client_result)

        self.assertIn("submit-package-proposal-top-level-extra-not-forbidden", blockers)
        self.assertIn("submit-package-proposal-schema-version-not-const-1", blockers)

    def test_transport_smoke_result_verifier_blocks_missing_output_schema(self) -> None:
        registered = [registered_tool_summary(name) for name in chatgpt_mcp.EXPECTED_TOOL_ORDER]
        registered[0].pop("outputSchema")
        client_result = {
            "toolNames": list(chatgpt_mcp.EXPECTED_TOOL_ORDER),
            "healthIsError": False,
            "healthStructuredContent": {
                "service": chatgpt_mcp.SERVER_NAME,
                "toolCount": len(chatgpt_mcp.EXPECTED_TOOL_ORDER),
                "repoRoot": ".",
                "safety": {"absoluteRepoRootExposed": False},
            },
            "registeredTools": registered,
        }

        blockers = chatgpt_mcp.verify_transport_smoke_result(client_result)

        self.assertIn(f"output-schema-missing:{chatgpt_mcp.EXPECTED_TOOL_ORDER[0]}", blockers)

    def test_proposal_transport_smoke_writes_artifact_and_covers_submit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            config = chatgpt_mcp.make_adapter_config(root)
            client_result = {
                "toolNames": list(chatgpt_mcp.EXPECTED_TOOL_ORDER),
                "registeredTools": [registered_tool_summary(name) for name in chatgpt_mcp.EXPECTED_TOOL_ORDER],
                "healthIsError": False,
                "healthStructuredContent": {
                    "service": chatgpt_mcp.SERVER_NAME,
                    "toolCount": len(chatgpt_mcp.EXPECTED_TOOL_ORDER),
                    "repoRoot": ".",
                    "safety": {"absoluteRepoRootExposed": False},
                },
                "submitPackageProposalIsError": False,
                "submitPackageProposalStructuredContent": {
                    "ok": True,
                    "inboxId": "20260519T000000Z-test",
                    "safety": {"noRepoTargetWrites": True},
                },
                "listInboxAfterSubmitIsError": False,
                "listInboxAfterSubmitStructuredContent": {"ok": True},
                "createPackageDraftIsError": False,
                "createPackageDraftStructuredContent": {
                    "ok": True,
                    "draftId": "20260519T000000Z-test",
                    "safety": {"localPackageDraftOnly": True, "applyFlagSent": False},
                },
                "reviewLatestPackageDraftIsError": False,
                "reviewLatestPackageDraftStructuredContent": {
                    "ok": True,
                    "draftId": "20260519T000000Z-test",
                    "safety": {"readOnlyReview": True},
                },
                "dryRunLatestPackageDraftIsError": False,
                "dryRunLatestPackageDraftStructuredContent": {
                    "ok": True,
                    "draftId": "20260519T000000Z-test",
                    "dryRunSucceeded": True,
                    "safety": {"packageIntakeDryRunOnly": True, "applyFlagSent": False},
                    "dryRun": {
                        "diffPreview": {
                            "ok": True,
                            "status": "ready",
                            "artifactPath": ".riftreader-local\\package-intake\\20260519-000000Z\\package.diff",
                            "text": "+# Preview\n",
                            "truncated": False,
                            "maxBytes": chatgpt_mcp.MAX_DRY_RUN_DIFF_PREVIEW_BYTES,
                            "safety": {"diffArtifactUnderPackageIntake": True, "boundedBytes": True, "applyFlagSent": False},
                        }
                    },
                },
                "applyLatestPackageDraftWithoutApprovalIsError": False,
                "applyLatestPackageDraftWithoutApprovalStructuredContent": {
                    "ok": False,
                    "status": "blocked",
                    "applied": False,
                    "blockers": ["APPLY_APPROVAL_MISSING"],
                    "safety": {"applyFlagSent": False, "repoSourceMutationExpected": False},
                },
            }

            async def fake_transport_client_with_retry(*args: object, **kwargs: object) -> dict[str, object]:
                return client_result

            fake_process = FakeProcess()
            with (
                mock.patch.object(chatgpt_mcp, "ensure_mcp_sdk_available", return_value=[]),
                mock.patch.object(chatgpt_mcp, "choose_loopback_port", return_value=9770),
                mock.patch.object(chatgpt_mcp.subprocess, "Popen", return_value=fake_process),
                mock.patch.object(chatgpt_mcp, "run_transport_client_with_retry", new=fake_transport_client_with_retry),
            ):
                payload = chatgpt_mcp.run_transport_smoke_test(config, include_proposal_submit=True)
                summary_path = root / payload["artifactPaths"]["summaryJson"]
                summary_exists = summary_path.is_file()
                summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["kind"], "riftreader-chatgpt-mcp-proposal-transport-smoke")
        self.assertTrue(payload["safety"]["proposalSubmitTransportCovered"])
        self.assertTrue(payload["safety"]["proposalSubmitWritesLocalInboxOnly"])
        self.assertTrue(payload["safety"]["packageDraftCreateTransportCovered"])
        self.assertTrue(payload["safety"]["packageDraftWritesLocalOnly"])
        self.assertTrue(payload["safety"]["packageDraftReviewTransportCovered"])
        self.assertTrue(payload["safety"]["packageDraftDryRunTransportCovered"])
        self.assertTrue(payload["safety"]["packageDraftDiffPreviewTransportCovered"])
        self.assertTrue(payload["safety"]["packageDraftApplyWithoutApprovalBlocked"])
        self.assertFalse(payload["client"]["applyLatestPackageDraftWithoutApprovalStructuredContent"]["applied"])
        self.assertTrue(summary_exists)
        self.assertEqual(summary_payload["artifactPaths"], payload["artifactPaths"])

    def test_transport_client_retry_uses_smoke_budget_for_read_timeout(self) -> None:
        observed: dict[str, object] = {}

        async def fake_client_once(
            url: str,
            package_proposal: dict[str, object] | None = None,
            *,
            client_read_timeout_seconds: float,
            progress: dict[str, object] | None = None,
        ) -> dict[str, object]:
            observed["url"] = url
            observed["packageProposal"] = package_proposal
            observed["clientReadTimeoutSeconds"] = client_read_timeout_seconds
            if progress is not None:
                progress["currentStage"] = "call_tool:dry_run_latest_package_draft"
            return {"ok": True}

        fake_process = FakeProcess()
        with mock.patch.object(chatgpt_mcp, "run_transport_client_once", new=fake_client_once):
            result = asyncio.run(
                chatgpt_mcp.run_transport_client_with_retry(
                    "http://127.0.0.1:9770/mcp",
                    fake_process,
                    timeout_seconds=30.0,
                    package_proposal={"kind": "package-proposal"},
                )
            )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(observed["url"], "http://127.0.0.1:9770/mcp")
        self.assertEqual(observed["packageProposal"], {"kind": "package-proposal"})
        self.assertGreater(float(observed["clientReadTimeoutSeconds"]), 30.0)
        self.assertLessEqual(
            float(observed["clientReadTimeoutSeconds"]),
            30.0 + chatgpt_mcp.TRANSPORT_CLIENT_READ_TIMEOUT_MARGIN_SECONDS + 1.0,
        )

    def test_transport_client_retry_timeout_reports_current_stage(self) -> None:
        async def fake_client_once(
            url: str,
            package_proposal: dict[str, object] | None = None,
            *,
            client_read_timeout_seconds: float,
            progress: dict[str, object] | None = None,
        ) -> dict[str, object]:
            if progress is not None:
                progress["currentStage"] = "call_tool:dry_run_latest_package_draft"
                progress["stepTimings"] = [
                    {"stage": "initialize", "status": "passed", "durationSeconds": 0.001},
                    {"stage": "call_tool:dry_run_latest_package_draft", "status": "started"},
                ]
            await asyncio.sleep(1.0)
            return {"ok": True}

        fake_process = FakeProcess()
        with mock.patch.object(chatgpt_mcp, "run_transport_client_once", new=fake_client_once):
            with self.assertRaises(chatgpt_mcp.AdapterError) as caught:
                asyncio.run(
                    chatgpt_mcp.run_transport_client_with_retry(
                        "http://127.0.0.1:9770/mcp",
                        fake_process,
                        timeout_seconds=0.01,
                        package_proposal={"kind": "package-proposal"},
                    )
                )

        self.assertEqual(caught.exception.code, "MCP_TRANSPORT_CLIENT_TIMEOUT")
        self.assertEqual(caught.exception.extra["lastClientStage"], "call_tool:dry_run_latest_package_draft")
        self.assertIn("remaining smoke timeout", caught.exception.extra["lastClientError"])
        self.assertEqual(
            caught.exception.extra["lastClientStepTimings"][-1]["stage"],
            "call_tool:dry_run_latest_package_draft",
        )

    def test_transport_smoke_result_verifier_requires_dry_run_diff_preview(self) -> None:
        registered = [registered_tool_summary(name) for name in chatgpt_mcp.EXPECTED_TOOL_ORDER]
        client_result = {
            "toolNames": list(chatgpt_mcp.EXPECTED_TOOL_ORDER),
            "registeredTools": registered,
            "healthIsError": False,
            "healthStructuredContent": {
                "service": chatgpt_mcp.SERVER_NAME,
                "toolCount": len(chatgpt_mcp.EXPECTED_TOOL_ORDER),
                "repoRoot": ".",
                "safety": {"absoluteRepoRootExposed": False},
            },
            "submitPackageProposalIsError": False,
            "submitPackageProposalStructuredContent": {
                "ok": True,
                "inboxId": "20260519T000000Z-test",
                "safety": {"noRepoTargetWrites": True},
            },
            "listInboxAfterSubmitIsError": False,
            "listInboxAfterSubmitStructuredContent": {"ok": True},
            "createPackageDraftIsError": False,
            "createPackageDraftStructuredContent": {
                "ok": True,
                "draftId": "20260519T000000Z-test",
                "safety": {"localPackageDraftOnly": True, "applyFlagSent": False},
            },
            "reviewLatestPackageDraftIsError": False,
            "reviewLatestPackageDraftStructuredContent": {
                "ok": True,
                "draftId": "20260519T000000Z-test",
                "safety": {"readOnlyReview": True},
            },
            "dryRunLatestPackageDraftIsError": False,
            "dryRunLatestPackageDraftStructuredContent": {
                "ok": True,
                "draftId": "20260519T000000Z-test",
                "dryRunSucceeded": True,
                "safety": {"packageIntakeDryRunOnly": True, "applyFlagSent": False},
                "dryRun": {"diffPreview": {"ok": False, "code": "DIFF_ARTIFACT_MISSING", "safety": {}}},
            },
        }

        blockers = chatgpt_mcp.verify_transport_smoke_result(client_result)

        self.assertIn("dry-run-diff-preview-not-ok:DIFF_ARTIFACT_MISSING", blockers)
        self.assertIn("dry-run-diff-preview-text-missing", blockers)
        self.assertIn("dry-run-diff-preview-package-intake-flag-missing", blockers)

    def test_transport_smoke_result_verifier_requires_apply_without_approval_denial(self) -> None:
        registered = [registered_tool_summary(name) for name in chatgpt_mcp.EXPECTED_TOOL_ORDER]
        client_result = {
            "toolNames": list(chatgpt_mcp.EXPECTED_TOOL_ORDER),
            "registeredTools": registered,
            "healthIsError": False,
            "healthStructuredContent": {
                "service": chatgpt_mcp.SERVER_NAME,
                "toolCount": len(chatgpt_mcp.EXPECTED_TOOL_ORDER),
                "repoRoot": ".",
                "safety": {"absoluteRepoRootExposed": False},
            },
            "submitPackageProposalIsError": False,
            "submitPackageProposalStructuredContent": {
                "ok": True,
                "inboxId": "20260519T000000Z-test",
                "safety": {"noRepoTargetWrites": True},
            },
            "listInboxAfterSubmitIsError": False,
            "listInboxAfterSubmitStructuredContent": {"ok": True},
            "createPackageDraftIsError": False,
            "createPackageDraftStructuredContent": {
                "ok": True,
                "draftId": "20260519T000000Z-test",
                "safety": {"localPackageDraftOnly": True, "applyFlagSent": False},
            },
            "reviewLatestPackageDraftIsError": False,
            "reviewLatestPackageDraftStructuredContent": {
                "ok": True,
                "draftId": "20260519T000000Z-test",
                "safety": {"readOnlyReview": True},
            },
            "dryRunLatestPackageDraftIsError": False,
            "dryRunLatestPackageDraftStructuredContent": {
                "ok": True,
                "draftId": "20260519T000000Z-test",
                "dryRunSucceeded": True,
                "safety": {"packageIntakeDryRunOnly": True, "applyFlagSent": False},
                "dryRun": {
                    "diffPreview": {
                        "ok": True,
                        "text": "+# Preview\n",
                        "safety": {"diffArtifactUnderPackageIntake": True, "boundedBytes": True, "applyFlagSent": False},
                    }
                },
            },
            "applyLatestPackageDraftWithoutApprovalIsError": False,
            "applyLatestPackageDraftWithoutApprovalStructuredContent": {
                "ok": True,
                "status": "passed",
                "applied": True,
                "blockers": [],
                "safety": {"applyFlagSent": True, "repoSourceMutationExpected": True},
            },
        }

        blockers = chatgpt_mcp.verify_transport_smoke_result(client_result)

        self.assertIn("apply-latest-package-draft-without-approval-ok-not-false:True", blockers)
        self.assertIn("apply-latest-package-draft-without-approval-applied-not-false:True", blockers)
        self.assertIn("apply-latest-package-draft-without-approval-missing-approval-blocker", blockers)
        self.assertIn("apply-latest-package-draft-without-approval-apply-flag-not-false", blockers)

    def test_create_fastmcp_server_fails_closed_without_annotation_support(self) -> None:
        class FakeAnnotations:
            def __init__(self, *, readOnlyHint: bool, destructiveHint: bool, openWorldHint: bool) -> None:  # noqa: N803
                self.readOnlyHint = readOnlyHint
                self.destructiveHint = destructiveHint
                self.openWorldHint = openWorldHint

        class RejectingFastMCP:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def tool(self, **kwargs: object):
                if "annotations" in kwargs:
                    raise TypeError("annotations unsupported")
                raise AssertionError("registration without annotations must not be attempted")

        mcp_module = types.ModuleType("mcp")
        server_module = types.ModuleType("mcp.server")
        fastmcp_module = types.ModuleType("mcp.server.fastmcp")
        transport_security_module = types.ModuleType("mcp.server.transport_security")
        types_module = types.ModuleType("mcp.types")
        fastmcp_module.FastMCP = RejectingFastMCP
        transport_security_module.TransportSecuritySettings = FakeTransportSecuritySettings
        types_module.ToolAnnotations = FakeAnnotations

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)
            with mock.patch.dict(
                sys.modules,
                {
                    "mcp": mcp_module,
                    "mcp.server": server_module,
                    "mcp.server.fastmcp": fastmcp_module,
                    "mcp.server.transport_security": transport_security_module,
                    "mcp.types": types_module,
                },
            ):
                with self.assertRaises(chatgpt_mcp.AdapterError) as caught:
                    chatgpt_mcp.create_fastmcp_server(adapter, host="127.0.0.1", port=8770)

        self.assertEqual(caught.exception.code, "MCP_TOOL_REGISTRATION_FAILED")

    def test_validate_sdk_registration_constructs_server_without_running(self) -> None:
        class FakeAnnotations:
            def __init__(self, *, readOnlyHint: bool, destructiveHint: bool, openWorldHint: bool) -> None:  # noqa: N803
                self.readOnlyHint = readOnlyHint
                self.destructiveHint = destructiveHint
                self.openWorldHint = openWorldHint

        class FakeFastMCP:
            def __init__(self, *args: object, **kwargs: object) -> None:
                self.registrations: list[dict[str, object]] = []

            def tool(self, **kwargs: object):
                self.registrations.append(kwargs)

                def decorate(fn):
                    return fn

                return decorate

            def run(self, *args: object, **kwargs: object) -> None:
                raise AssertionError("SDK validation must not start the server")

            async def list_tools(self):
                return [
                    types.SimpleNamespace(
                        name=registration["name"],
                        description=registration["description"],
                        annotations=registration["annotations"],
                        outputSchema=chatgpt_mcp.tool_output_schema(str(registration["name"])),
                    )
                    for registration in self.registrations
                ]

        mcp_module = types.ModuleType("mcp")
        server_module = types.ModuleType("mcp.server")
        fastmcp_module = types.ModuleType("mcp.server.fastmcp")
        transport_security_module = types.ModuleType("mcp.server.transport_security")
        types_module = types.ModuleType("mcp.types")
        fastmcp_module.FastMCP = FakeFastMCP
        transport_security_module.TransportSecuritySettings = FakeTransportSecuritySettings
        types_module.ToolAnnotations = FakeAnnotations

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            config = chatgpt_mcp.make_adapter_config(root)
            with mock.patch.dict(
                sys.modules,
                {
                    "mcp": mcp_module,
                    "mcp.server": server_module,
                    "mcp.server.fastmcp": fastmcp_module,
                    "mcp.server.transport_security": transport_security_module,
                    "mcp.types": types_module,
                },
            ):
                payload = chatgpt_mcp.validate_sdk_registration(config)

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["safety"]["sdkImported"])
        self.assertFalse(payload["safety"]["serverStarted"])
        self.assertTrue(payload["safety"]["registeredToolMetadataVerified"])
        self.assertEqual(payload["toolCount"], len(chatgpt_mcp.EXPECTED_TOOL_ORDER))
        self.assertEqual([tool["name"] for tool in payload["registeredTools"]], list(chatgpt_mcp.EXPECTED_TOOL_ORDER))

    def test_validate_sdk_registration_rejects_non_localhost(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            config = chatgpt_mcp.make_adapter_config(root)

            with self.assertRaises(chatgpt_mcp.AdapterError) as caught:
                chatgpt_mcp.validate_sdk_registration(config, host="0.0.0.0")

        self.assertEqual(caught.exception.code, "UNSAFE_BIND_HOST")

    def test_validate_sdk_registration_fails_on_registered_annotation_mismatch(self) -> None:
        class FakeAnnotations:
            def __init__(self, *, readOnlyHint: bool, destructiveHint: bool, openWorldHint: bool) -> None:  # noqa: N803
                self.readOnlyHint = readOnlyHint
                self.destructiveHint = destructiveHint
                self.openWorldHint = openWorldHint

        class FakeFastMCP:
            def __init__(self, *args: object, **kwargs: object) -> None:
                self.registrations: list[dict[str, object]] = []

            def tool(self, **kwargs: object):
                self.registrations.append(kwargs)

                def decorate(fn):
                    return fn

                return decorate

            async def list_tools(self):
                tools = []
                for registration in self.registrations:
                    annotations = registration["annotations"]
                    if registration["name"] == "submit_package_proposal":
                        annotations = FakeAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
                    tools.append(
                        types.SimpleNamespace(
                            name=registration["name"],
                            description=registration["description"],
                            annotations=annotations,
                            outputSchema=chatgpt_mcp.tool_output_schema(str(registration["name"])),
                        )
                    )
                return tools

        mcp_module = types.ModuleType("mcp")
        server_module = types.ModuleType("mcp.server")
        fastmcp_module = types.ModuleType("mcp.server.fastmcp")
        transport_security_module = types.ModuleType("mcp.server.transport_security")
        types_module = types.ModuleType("mcp.types")
        fastmcp_module.FastMCP = FakeFastMCP
        transport_security_module.TransportSecuritySettings = FakeTransportSecuritySettings
        types_module.ToolAnnotations = FakeAnnotations

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            config = chatgpt_mcp.make_adapter_config(root)
            with mock.patch.dict(
                sys.modules,
                {
                    "mcp": mcp_module,
                    "mcp.server": server_module,
                    "mcp.server.fastmcp": fastmcp_module,
                    "mcp.server.transport_security": transport_security_module,
                    "mcp.types": types_module,
                },
            ):
                with self.assertRaises(chatgpt_mcp.AdapterError) as caught:
                    chatgpt_mcp.validate_sdk_registration(config)

        self.assertEqual(caught.exception.code, "MCP_SDK_REGISTRATION_MISMATCH")
        self.assertTrue(any("submit_package_proposal" in blocker for blocker in caught.exception.extra["blockers"]))

    def test_build_child_pythonpath_prefers_local_sdk_and_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            local_sdk = root / ".riftreader-local" / "mcp-sdk-validation" / "mcp"
            local_sdk.mkdir(parents=True)
            (local_sdk / "__init__.py").write_text("", encoding="utf-8")
            config = chatgpt_mcp.make_adapter_config(root)

            value = chatgpt_mcp.build_child_pythonpath(config, {"PYTHONPATH": "existing-path"})

        parts = value.split(os.pathsep)
        self.assertEqual(parts[0], str((root / ".riftreader-local" / "mcp-sdk-validation").resolve()))
        self.assertEqual(parts[1], str((root / "tools").resolve()))
        self.assertEqual(parts[2], "existing-path")

    def test_transport_smoke_result_verifier_catches_annotation_mismatch(self) -> None:
        registered = []
        for name in chatgpt_mcp.EXPECTED_TOOL_ORDER:
            annotations = chatgpt_mcp.TOOL_SPECS[name].annotation_payload()
            if name == "dry_run_latest_package_draft":
                annotations = {**annotations, "readOnlyHint": True}
            summary = registered_tool_summary(name)
            summary["annotations"] = annotations
            registered.append(summary)
        client_result = {
            "toolNames": list(chatgpt_mcp.EXPECTED_TOOL_ORDER),
            "healthIsError": False,
            "healthStructuredContent": {
                "service": chatgpt_mcp.SERVER_NAME,
                "toolCount": len(chatgpt_mcp.EXPECTED_TOOL_ORDER),
                "repoRoot": ".",
                "safety": {"absoluteRepoRootExposed": False},
            },
            "registeredTools": registered,
        }

        blockers = chatgpt_mcp.verify_transport_smoke_result(client_result)

        self.assertTrue(any("dry_run_latest_package_draft" in blocker for blocker in blockers))

    def test_trial_readiness_compacts_core_checks_and_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            config = chatgpt_mcp.make_adapter_config(root)
            with (
                mock.patch.object(
                    chatgpt_mcp,
                    "run_self_test",
                    return_value={
                        "kind": "self-test",
                        "status": "passed",
                        "ok": True,
                        "warnings": ["self-test-local-only"],
                        "stages": {"large": {"not": "included"}},
                        "artifacts": {"auditRoot": ".riftreader-local/audit"},
                    },
                ),
                mock.patch.object(
                    chatgpt_mcp,
                    "validate_sdk_registration",
                    return_value={
                        "kind": "sdk-validation",
                        "status": "passed",
                        "ok": True,
                        "toolCount": len(chatgpt_mcp.EXPECTED_TOOL_ORDER),
                        "registeredTools": [{"name": name} for name in chatgpt_mcp.EXPECTED_TOOL_ORDER],
                    },
                ),
                mock.patch.object(
                    chatgpt_mcp,
                    "run_transport_smoke_test",
                    return_value={
                        "kind": "transport-smoke",
                        "status": "passed",
                        "ok": True,
                        "client": {
                            "toolCount": len(chatgpt_mcp.EXPECTED_TOOL_ORDER),
                            "toolNames": list(chatgpt_mcp.EXPECTED_TOOL_ORDER),
                            "healthIsError": False,
                            "submitPackageProposalIsError": False,
                            "submitPackageProposalStructuredContent": {
                                "ok": True,
                                "inboxId": "20260519T000000Z-test",
                                "safety": {"noRepoTargetWrites": True},
                            },
                            "listInboxAfterSubmitIsError": False,
                            "listInboxAfterSubmitStructuredContent": {"ok": True, "count": 1},
                            "createPackageDraftIsError": False,
                            "createPackageDraftStructuredContent": {
                                "ok": True,
                                "draftId": "20260519T000000Z-test",
                                "safety": {"localPackageDraftOnly": True, "applyFlagSent": False},
                            },
                            "reviewLatestPackageDraftIsError": False,
                            "reviewLatestPackageDraftStructuredContent": {
                                "ok": True,
                                "draftId": "20260519T000000Z-test",
                                "safety": {"readOnlyReview": True},
                            },
                            "dryRunLatestPackageDraftIsError": False,
                            "dryRunLatestPackageDraftStructuredContent": {
                                "ok": True,
                                "draftId": "20260519T000000Z-test",
                                "dryRunSucceeded": True,
                                "safety": {"packageIntakeDryRunOnly": True, "applyFlagSent": False},
                                "dryRun": {
                                    "diffPreview": {
                                        "ok": True,
                                        "status": "ready",
                                        "artifactPath": ".riftreader-local\\package-intake\\20260519-000000Z\\package.diff",
                                        "text": "+# Preview\n",
                                        "truncated": False,
                                        "sizeBytes": 11,
                                        "maxBytes": chatgpt_mcp.MAX_DRY_RUN_DIFF_PREVIEW_BYTES,
                                        "safety": {
                                            "diffArtifactUnderPackageIntake": True,
                                            "boundedBytes": True,
                                            "applyFlagSent": False,
                                        },
                                    }
                                },
                            },
                            "applyLatestPackageDraftWithoutApprovalIsError": False,
                            "applyLatestPackageDraftWithoutApprovalStructuredContent": {
                                "ok": False,
                                "status": "blocked",
                                "applied": False,
                                "blockers": ["APPLY_APPROVAL_MISSING"],
                                "safety": {"applyFlagSent": False, "repoSourceMutationExpected": False},
                            },
                        },
                        "safety": {
                            "proposalSubmitTransportCovered": True,
                            "proposalSubmitWritesLocalInboxOnly": True,
                            "packageDraftCreateTransportCovered": True,
                            "packageDraftWritesLocalOnly": True,
                            "packageDraftReviewTransportCovered": True,
                            "packageDraftDryRunTransportCovered": True,
                            "packageDraftDiffPreviewTransportCovered": True,
                            "packageDraftApplyWithoutApprovalBlocked": True,
                        },
                    },
                ) as transport_mock,
                mock.patch.object(chatgpt_mcp, "resolve_curl_executable", return_value=root / "curl.exe"),
            ):
                payload = chatgpt_mcp.run_trial_readiness(config)
                summary_exists = (root / payload["artifactPaths"]["summaryJson"]).is_file()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["stages"]["self_test"]["artifacts"]["auditRoot"], ".riftreader-local/audit")
        self.assertNotIn("stages", payload["stages"]["self_test"])
        self.assertEqual(payload["stages"]["validate_sdk"]["registeredToolNames"], list(chatgpt_mcp.EXPECTED_TOOL_ORDER))
        self.assertEqual(payload["stages"]["transport_smoke"]["client"]["toolCount"], len(chatgpt_mcp.EXPECTED_TOOL_ORDER))
        self.assertFalse(payload["stages"]["transport_smoke"]["client"]["submitPackageProposalIsError"])
        self.assertTrue(payload["stages"]["transport_smoke"]["client"]["submitPackageProposal"]["noRepoTargetWrites"])
        self.assertFalse(payload["stages"]["transport_smoke"]["client"]["createPackageDraftIsError"])
        self.assertTrue(payload["stages"]["transport_smoke"]["client"]["createPackageDraft"]["localPackageDraftOnly"])
        self.assertFalse(payload["stages"]["transport_smoke"]["client"]["reviewLatestPackageDraftIsError"])
        self.assertTrue(payload["stages"]["transport_smoke"]["client"]["reviewLatestPackageDraft"]["readOnlyReview"])
        self.assertFalse(payload["stages"]["transport_smoke"]["client"]["dryRunLatestPackageDraftIsError"])
        self.assertTrue(payload["stages"]["transport_smoke"]["client"]["dryRunLatestPackageDraft"]["dryRunSucceeded"])
        self.assertTrue(payload["stages"]["transport_smoke"]["client"]["dryRunLatestPackageDraft"]["packageIntakeDryRunOnly"])
        self.assertTrue(
            payload["stages"]["transport_smoke"]["client"]["dryRunLatestPackageDraft"]["diffPreview"][
                "diffArtifactUnderPackageIntake"
            ]
        )
        self.assertEqual(payload["stages"]["transport_smoke"]["client"]["dryRunLatestPackageDraft"]["diffPreview"]["textLength"], 11)
        self.assertFalse(
            payload["stages"]["transport_smoke"]["client"]["applyLatestPackageDraftWithoutApproval"]["applied"]
        )
        self.assertIn(
            "APPLY_APPROVAL_MISSING",
            payload["stages"]["transport_smoke"]["client"]["applyLatestPackageDraftWithoutApproval"]["blockers"],
        )
        self.assertTrue(payload["stages"]["transport_smoke"]["safety"]["proposalSubmitTransportCovered"])
        self.assertTrue(payload["stages"]["transport_smoke"]["safety"]["packageDraftCreateTransportCovered"])
        self.assertTrue(payload["stages"]["transport_smoke"]["safety"]["packageDraftReviewTransportCovered"])
        self.assertTrue(payload["stages"]["transport_smoke"]["safety"]["packageDraftDryRunTransportCovered"])
        self.assertTrue(payload["stages"]["transport_smoke"]["safety"]["packageDraftDiffPreviewTransportCovered"])
        self.assertTrue(payload["stages"]["transport_smoke"]["safety"]["packageDraftApplyWithoutApprovalBlocked"])
        self.assertTrue(payload["safety"]["trialReadinessLocalOnly"])
        self.assertFalse(payload["safety"]["publicTunnelStarted"])
        self.assertTrue(summary_exists)
        self.assertTrue(transport_mock.call_args.kwargs["include_proposal_submit"])

    def test_trial_readiness_blocks_on_core_stage_failure_without_blocking_optional_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            config = chatgpt_mcp.make_adapter_config(root)
            with (
                mock.patch.object(chatgpt_mcp, "run_self_test", return_value={"status": "passed", "ok": True}),
                mock.patch.object(
                    chatgpt_mcp,
                    "validate_sdk_registration",
                    return_value={
                        "status": "failed",
                        "ok": False,
                        "code": "MCP_PYTHON_SDK_MISSING",
                        "blockers": ["MCP_PYTHON_SDK_MISSING"],
                    },
                ),
                mock.patch.object(chatgpt_mcp, "run_transport_smoke_test", return_value={"status": "passed", "ok": True}),
                mock.patch.object(chatgpt_mcp, "resolve_curl_executable", return_value=root / "curl.exe"),
            ):
                payload = chatgpt_mcp.run_trial_readiness(config)

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("validate_sdk:MCP_PYTHON_SDK_MISSING", payload["blockers"])
        self.assertIn("curl", payload["optionalDependencies"])
        self.assertNotIn("tunnelClient", payload["optionalDependencies"])
        self.assertNotIn("cloudflaredFallback", payload["optionalDependencies"])

    def test_secure_tunnel_plan_prefers_tunnel_client_without_starting_processes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            config = chatgpt_mcp.make_adapter_config(root)
            with (
                mock.patch.object(chatgpt_mcp, "resolve_tunnel_client_executable", return_value=root / "tunnel-client.exe"),
                mock.patch.object(
                    chatgpt_mcp,
                    "executable_binary_diagnostics",
                    return_value={
                        "status": "passed",
                        "ok": True,
                        "sha256": "a" * 64,
                        "versionProbe": {"ok": True, "exitCode": 0, "stdoutPreview": "0.0.0-test"},
                        "blockers": [],
                        "warnings": [],
                    },
                ),
            ):
                payload = chatgpt_mcp.build_secure_tunnel_plan(
                    config,
                    profile="riftreader-local-stdio",
                    tunnel_id="tunnel_test",
                )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["recommendedPath"], "retired-openai-secure-mcp-tunnel")
        self.assertEqual(payload["deprecatedFallback"], "none")
        self.assertIn("--transport", payload["mcpCommand"])
        self.assertIn("stdio", payload["mcpCommand"])
        self.assertIn("--mcp-command", payload["commands"]["init"])
        self.assertIn("--mcp-command", payload["commandLines"]["init"])
        self.assertEqual(payload["commands"]["init"][payload["commands"]["init"].index("--tunnel-id") + 1], "tunnel_test")
        self.assertEqual(payload["chatGptConnector"]["toolSmokeOrder"], ["health", "get_repo_status", "get_latest_handoff"])
        self.assertIn("runtimeApiKey", payload["openAiRequirements"])
        self.assertIn("connect-from-chatgpt", payload["docs"]["connectFromChatGpt"])
        self.assertEqual(payload["dependencies"]["tunnelClient"]["binaryDiagnostics"]["sha256"], "a" * 64)
        self.assertTrue(payload["secretLeakCheck"]["ok"])
        self.assertTrue(payload["safety"]["credentialPlaceholderOnly"])
        self.assertTrue(payload["safety"]["openAiSecureTunnelRetired"])
        self.assertTrue(payload["safety"]["cloudflareTunnelRetired"])

    def test_secure_tunnel_plan_blocks_on_tunnel_client_binary_diagnostics_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            config = chatgpt_mcp.make_adapter_config(root)
            with (
                mock.patch.object(chatgpt_mcp, "resolve_tunnel_client_executable", return_value=root / "tunnel-client.exe"),
                mock.patch.object(
                    chatgpt_mcp,
                    "executable_binary_diagnostics",
                    return_value={
                        "status": "blocked",
                        "ok": False,
                        "blockers": ["tunnel-client-version-probe-failed"],
                        "warnings": [],
                    },
                ),
            ):
                payload = chatgpt_mcp.build_secure_tunnel_plan(config, tunnel_id="tunnel_test")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("tunnel-client-version-probe-failed", payload["blockers"])

    def test_operator_launch_plan_reuses_existing_scripts_without_starting_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            config = chatgpt_mcp.make_adapter_config(root)
            payload = chatgpt_mcp.build_operator_launch_plan(config, session_seconds=3600)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["kind"], "riftreader-chatgpt-mcp-operator-launch-plan")
        self.assertTrue(payload["nonCodexInvariant"]["operatorOwnedRuntimeRequired"])
        self.assertFalse(payload["nonCodexInvariant"]["codexLaunchedRuntimeIsFinalProof"])
        self.assertFalse(payload["nonCodexInvariant"]["savedChatGptAppStartsLocalServer"])
        self.assertEqual(payload["existingEntrypoints"]["chatgptMcpWrapper"], "scripts\\riftreader-chatgpt-mcp.cmd")
        self.assertEqual(payload["recommendedPath"]["key"], "cloudflare-named-tunnel")
        self.assertEqual(payload["recommendedPath"]["legacyCliAlias"], "--manual-public-ip-plan")
        self.assertEqual(payload["recommendedPath"]["defaultPublicHost"], "mcp.360madden.com")
        self.assertIn("mcp.360madden.com", payload["recommendedPath"]["command"])
        self.assertFalse(payload["recommendedPath"]["startsRuntime"])
        self.assertTrue(payload["retiredPaths"]["openAiSecureMcpTunnel"]["retired"])
        self.assertTrue(payload["retiredPaths"]["openAiSecureMcpTunnel"]["notFallback"])
        self.assertTrue(payload["retiredPaths"]["cloudflareQuickTunnel"]["retired"])
        self.assertTrue(payload["retiredPaths"]["cloudflareQuickTunnel"]["notFallback"])
        self.assertTrue(payload["safety"]["planOnly"])
        self.assertFalse(payload["safety"]["publicTunnelStarted"])
        self.assertFalse(payload["safety"]["persistentServerStarted"])
        self.assertIn("health", payload["chatGptSmokeOrder"])
        self.assertTrue(any("local MCP server" in item for item in payload["prerequisiteChain"]))
        self.assertTrue(any("Cloudflare named Tunnel" in item for item in payload["prerequisiteChain"]))
        self.assertTrue(any("http://127.0.0.1:8770" in item for item in payload["prerequisiteChain"]))
        self.assertTrue(any("duplicate launcher" in item for item in payload["doNotUse"]))
        self.assertFalse(payload["safety"]["manualPublicIpPreferred"])
        self.assertTrue(payload["safety"]["cloudflareNamedTunnelPreferred"])
        self.assertTrue(payload["safety"]["openAiSecureTunnelRetired"])
        self.assertTrue(payload["safety"]["cloudflareQuickTunnelRetired"])
        self.assertTrue(payload["safety"]["caddyRouterDeprecated"])
        self.assertFalse(payload["safety"]["cloudflareTunnelRetired"])

    def test_manual_public_ip_plan_alias_emits_cloudflare_named_tunnel_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            config = chatgpt_mcp.make_adapter_config(root)
            payload = chatgpt_mcp.build_manual_public_ip_plan(config, public_mcp_host="mcp.360madden.com")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["kind"], "riftreader-chatgpt-mcp-manual-public-ip-plan")
        self.assertEqual(payload["activePath"]["key"], "cloudflare-named-tunnel")
        self.assertEqual(payload["activePath"]["legacyCliAlias"], "--manual-public-ip-plan")
        self.assertEqual(payload["activePath"]["connectionMode"], "Server URL")
        self.assertEqual(payload["activePath"]["chatGptAuthentication"], "No Authentication")
        self.assertEqual(payload["activePath"]["publicMcpUrl"], "https://mcp.360madden.com/mcp")
        self.assertEqual(payload["activePath"]["publicHostKind"], "domain-or-ddns-host")
        self.assertFalse(payload["activePath"]["operatorMustEditChatGptAppWhenIpChanges"])
        self.assertIn("--allowed-host", payload["localRuntime"]["mcpServerCommand"])
        self.assertIn("mcp.360madden.com", payload["localRuntime"]["mcpServerCommand"])
        self.assertTrue(payload["localRuntime"]["mcpServerBindsLoopbackOnly"])
        self.assertTrue(any("Cloudflare" in item for item in payload["manualNetworkChecklist"]))
        self.assertTrue(payload["retiredPaths"]["openAiSecureMcpTunnel"]["notFallback"])
        self.assertTrue(payload["retiredPaths"]["cloudflareQuickTunnel"]["notFallback"])
        self.assertTrue(payload["retiredPaths"]["caddyRouter"]["deprecated"])
        self.assertFalse(payload["safety"]["manualPublicIpPreferred"])
        self.assertTrue(payload["safety"]["cloudflareNamedTunnelPreferred"])
        self.assertTrue(payload["safety"]["openAiSecureTunnelRetired"])
        self.assertTrue(payload["safety"]["cloudflareQuickTunnelRetired"])
        self.assertTrue(payload["safety"]["caddyRouterDeprecated"])
        self.assertFalse(payload["safety"]["cloudflareTunnelRetired"])

    def test_secure_tunnel_plan_redacts_secret_like_tunnel_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            config = chatgpt_mcp.make_adapter_config(root)
            accidental_key = "sk-proj-" + ("x" * 32)
            with (
                mock.patch.object(chatgpt_mcp, "resolve_tunnel_client_executable", return_value=root / "tunnel-client.exe"),
                mock.patch.object(
                    chatgpt_mcp,
                    "executable_binary_diagnostics",
                    return_value={"status": "passed", "ok": True, "blockers": [], "warnings": []},
                ),
            ):
                payload = chatgpt_mcp.build_secure_tunnel_plan(config, tunnel_id=accidental_key)

        serialized = json.dumps(payload, sort_keys=True)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("secure-tunnel-id-looks-like-secret", payload["blockers"])
        self.assertNotIn(accidental_key, serialized)
        self.assertTrue(payload["tunnelIdInput"]["redacted"])
        self.assertEqual(payload["secretLeakCheck"]["status"], "passed")

    def test_secure_tunnel_plan_blocks_malformed_tunnel_id_without_echoing_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            config = chatgpt_mcp.make_adapter_config(root)
            malformed = "not a tunnel id"
            with (
                mock.patch.object(chatgpt_mcp, "resolve_tunnel_client_executable", return_value=root / "tunnel-client.exe"),
                mock.patch.object(
                    chatgpt_mcp,
                    "executable_binary_diagnostics",
                    return_value={"status": "passed", "ok": True, "blockers": [], "warnings": []},
                ),
            ):
                payload = chatgpt_mcp.build_secure_tunnel_plan(config, tunnel_id=malformed)

        serialized = json.dumps(payload, sort_keys=True)
        self.assertFalse(payload["ok"])
        self.assertIn("secure-tunnel-id-invalid-format", payload["blockers"])
        self.assertNotIn(malformed, serialized)
        self.assertEqual(payload["commands"]["init"][payload["commands"]["init"].index("--tunnel-id") + 1], chatgpt_mcp.SECURE_TUNNEL_ID_PLACEHOLDER)

    def test_executable_binary_diagnostics_records_hash_and_version_probe(self) -> None:
        diagnostics = chatgpt_mcp.executable_binary_diagnostics("python", Path(sys.executable), cwd=REPO_ROOT)

        self.assertEqual(diagnostics["status"], "passed")
        self.assertTrue(diagnostics["ok"])
        self.assertEqual(len(diagnostics["sha256"]), 64)
        self.assertTrue(diagnostics["versionProbe"]["ok"])

    def test_resolve_tunnel_client_checks_repo_local_adminless_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            expected = root / ".riftreader-local" / "tools" / "openai" / "tunnel-client" / "tunnel-client.exe"
            expected.parent.mkdir(parents=True)
            expected.write_text("fake tunnel-client", encoding="utf-8")

            resolved = chatgpt_mcp.resolve_tunnel_client_executable(repo_root=root)

        self.assertEqual(resolved, expected.resolve())

    def test_chatgpt_trial_session_writes_ready_and_final_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            config = chatgpt_mcp.make_adapter_config(root)
            fake_client = {
                "responses": [
                    {"request": {"method": "initialize"}, "exitCode": 0, "httpStatus": 200, "jsonParseError": None, "json": {"result": {}}},
                    {"request": {"method": "tools/list"}, "exitCode": 0, "httpStatus": 200, "jsonParseError": None, "json": {"result": {}}},
                    {"request": {"method": "tools/call"}, "exitCode": 0, "httpStatus": 200, "jsonParseError": None, "json": {"result": {}}},
                ],
                "toolNames": list(chatgpt_mcp.EXPECTED_TOOL_ORDER),
                "registeredTools": [registered_tool_summary(name) for name in chatgpt_mcp.EXPECTED_TOOL_ORDER],
                "healthIsError": False,
                "healthStructuredContent": {
                    "service": chatgpt_mcp.SERVER_NAME,
                    "toolCount": len(chatgpt_mcp.EXPECTED_TOOL_ORDER),
                    "repoRoot": ".",
                    "safety": {"absoluteRepoRootExposed": False},
                },
            }
            fake_processes = [FakeProcess(), FakeProcess()]
            with (
                mock.patch.object(chatgpt_mcp, "ensure_mcp_sdk_available", return_value=[]),
                mock.patch.object(chatgpt_mcp, "resolve_cloudflared_executable", return_value=root / "cloudflared.exe"),
                mock.patch.object(chatgpt_mcp, "resolve_curl_executable", return_value="curl.exe"),
                mock.patch.object(chatgpt_mcp, "choose_loopback_port", return_value=9777),
                mock.patch.object(chatgpt_mcp.subprocess, "Popen", side_effect=fake_processes),
                mock.patch.object(
                    chatgpt_mcp,
                    "wait_for_cloudflare_quick_tunnel_url",
                    return_value="https://example.trycloudflare.com",
                ),
                mock.patch.object(chatgpt_mcp, "resolve_ipv4_for_curl", return_value="104.16.1.1"),
                mock.patch.object(chatgpt_mcp, "cloudflare_smoke_client_result", return_value=fake_client) as cloudflare_client,
            ):
                payload = chatgpt_mcp.run_chatgpt_trial_session(config, session_seconds=0)
                ready_exists = (root / payload["artifactPaths"]["readyJson"]).is_file()
                summary_exists = (root / payload["artifactPaths"]["summaryJson"]).is_file()
                ready_payload = json.loads((root / payload["artifactPaths"]["readyJson"]).read_text(encoding="utf-8"))

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["publicMcpUrl"], "https://example.trycloudflare.com/mcp")
        self.assertEqual(payload["registration"]["authentication"], "No Authentication")
        self.assertEqual(payload["registration"]["firstToolToCall"], "health")
        self.assertTrue(payload["client"])
        self.assertTrue(ready_payload["publicDnsVerified"])
        self.assertTrue(payload["safety"]["serverStopped"])
        self.assertTrue(payload["safety"]["publicTunnelStopped"])
        self.assertTrue(ready_exists)
        self.assertTrue(summary_exists)
        self.assertTrue(cloudflare_client.call_args.kwargs["include_proposal_submit"])
        self.assertIsNone(cloudflare_client.call_args.kwargs.get("resolve_host"))
        self.assertIsNone(cloudflare_client.call_args.kwargs.get("resolve_ip"))

    def test_parser_exposes_trial_modes(self) -> None:
        help_text = chatgpt_mcp.build_parser().format_help()
        args = chatgpt_mcp.build_parser().parse_args(
            ["--chatgpt-trial-session", "--chatgpt-session-seconds", "1"]
        )
        serve_args = chatgpt_mcp.build_parser().parse_args(["--serve", "--transport", "stdio"])

        self.assertIn("--trial-readiness", help_text)
        self.assertIn("--secure-tunnel-plan", help_text)
        self.assertIn("--manual-public-ip-plan", help_text)
        self.assertIn("--operator-launch-plan", help_text)
        self.assertIn("--proposal-transport-smoke", help_text)
        self.assertIn("--chatgpt-trial-session", help_text)
        self.assertTrue(args.chatgpt_trial_session)
        self.assertEqual(args.chatgpt_session_seconds, 1)
        self.assertEqual(serve_args.transport, "stdio")

    def test_serve_adds_local_sdk_path_before_starting_stdio_server(self) -> None:
        class FakeServer:
            def __init__(self) -> None:
                self.transport: str | None = None

            def run(self, *, transport: str) -> None:
                self.transport = transport

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            fake_server = FakeServer()
            with (
                mock.patch.object(chatgpt_mcp, "ensure_mcp_sdk_available", return_value=[str(root / ".riftreader-local" / "mcp-sdk-validation")]) as ensure,
                mock.patch.object(chatgpt_mcp, "create_fastmcp_server", return_value=fake_server),
            ):
                exit_code = chatgpt_mcp.main(
                    [
                        "--serve",
                        "--transport",
                        "stdio",
                        "--repo-root",
                        str(root),
                    ]
                )

        self.assertEqual(exit_code, 0)
        ensure.assert_called_once_with(root.resolve())
        self.assertEqual(fake_server.transport, "stdio")


if __name__ == "__main__":
    unittest.main()
