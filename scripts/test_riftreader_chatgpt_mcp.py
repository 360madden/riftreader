#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
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


class RiftReaderChatGptMcpTests(unittest.TestCase):
    def test_manifest_exposes_exact_safe_tool_set_with_annotations(self) -> None:
        manifest = chatgpt_mcp.tool_manifest()

        self.assertEqual([item["name"] for item in manifest["tools"]], list(chatgpt_mcp.EXPECTED_TOOL_ORDER))
        annotation_by_name = {item["name"]: item["annotations"] for item in manifest["tools"]}
        self.assertTrue(annotation_by_name["health"]["readOnlyHint"])
        self.assertTrue(annotation_by_name["get_repo_status"]["readOnlyHint"])
        self.assertFalse(annotation_by_name["submit_package_proposal"]["readOnlyHint"])
        self.assertFalse(annotation_by_name["dry_run_latest_package_draft"]["readOnlyHint"])
        for annotations in annotation_by_name.values():
            self.assertFalse(annotations["destructiveHint"])
            self.assertFalse(annotations["openWorldHint"])

    def test_health_reports_no_broad_mcp_proxy_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            make_repo(root)
            adapter = make_adapter(root)

            payload = adapter.call_tool("health", {})

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["safety"]["noRiftGameMcpProxy"])
        self.assertTrue(payload["safety"]["noWindowsMcpProxy"])
        self.assertTrue(payload["safety"]["noShellExecutionEndpoint"])
        self.assertTrue(payload["safety"]["auditUnderDotRiftReaderLocal"])

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
        self.assertEqual(payload["draftReview"]["draft"]["messageTitle"], "Operator")
        self.assertFalse(payload["draftReview"]["draft"]["selfTest"])

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
            "registeredTools": [
                {
                    "name": name,
                    "descriptionStartsUseThisWhen": True,
                    "annotations": chatgpt_mcp.TOOL_SPECS[name].annotation_payload(),
                }
                for name in chatgpt_mcp.EXPECTED_TOOL_ORDER
            ],
            "healthIsError": False,
            "healthStructuredContent": {"service": chatgpt_mcp.SERVER_NAME, "toolCount": len(chatgpt_mcp.EXPECTED_TOOL_ORDER)},
        }

        self.assertEqual(chatgpt_mcp.verify_cloudflare_smoke_client_result(client_result), [])

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
            registered.append({"name": name, "descriptionStartsUseThisWhen": True, "annotations": annotations})
        client_result = {
            "toolNames": list(chatgpt_mcp.EXPECTED_TOOL_ORDER),
            "healthIsError": False,
            "healthStructuredContent": {
                "service": chatgpt_mcp.SERVER_NAME,
                "toolCount": len(chatgpt_mcp.EXPECTED_TOOL_ORDER),
            },
            "registeredTools": registered,
        }

        blockers = chatgpt_mcp.verify_transport_smoke_result(client_result)

        self.assertTrue(any("dry_run_latest_package_draft" in blocker for blocker in blockers))


if __name__ == "__main__":
    unittest.main()
