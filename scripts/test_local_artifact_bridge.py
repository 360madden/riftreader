# Version: riftreader-local-artifact-bridge-tests-v0.1.0
# Total-Character-Count: 46064
# Purpose: Unit tests for the RiftReader read-only local artifact bridge v0.1 endpoint, indexing, and blocking behavior.
from __future__ import annotations

import hashlib
import http.client
import contextlib
import io
import json
import pathlib
import shutil
import sys
import tempfile
import threading
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.riftreader_workflow import local_artifact_bridge as bridge


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class BridgeServerCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = pathlib.Path(tempfile.mkdtemp(prefix="riftreader_bridge_test_"))
        self.repo_root = self.temp_dir
        self.payload_root = self.repo_root / "artifacts" / "chatgpt-payloads"
        self.token = "test-token"
        self.payload_one = self._write_payload(
            "pointer-chain-pack-20260517-001",
            "2026-05-17T00:00:00Z",
            "rank,base,offset\n1,0x1000,0x20\n",
        )
        self.payload_two = self._write_payload(
            "pointer-chain-pack-20260517-002",
            "2026-05-17T01:00:00Z",
            "rank,base,offset\n1,0x2000,0x28\n",
        )
        self.config = bridge.make_config(
            repo_root=self.repo_root,
            payload_root=pathlib.Path("artifacts") / "chatgpt-payloads",
            token=self.token,
            port=0,
            max_response_bytes=8192,
            log_requests=False,
        )
        self.server = bridge.create_http_server(self.config)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_payload(self, payload_id: str, created_utc: str, chunk_text: str) -> pathlib.Path:
        payload_dir = self.payload_root / payload_id
        candidates = payload_dir / "candidates"
        reports = payload_dir / "reports"
        candidates.mkdir(parents=True, exist_ok=True)
        reports.mkdir(parents=True, exist_ok=True)

        chunk_path = candidates / "chain-candidates.csv"
        chunk_path.write_text(chunk_text, encoding="utf-8")
        bad_path = candidates / "raw.bin"
        bad_path.write_bytes(b"\x00\x01\x02")
        big_path = reports / "big.txt"
        big_path.write_text("Z" * 16384, encoding="utf-8")
        mismatch_path = reports / "mismatch.txt"
        mismatch_path.write_text("actual text\n", encoding="utf-8")
        readme = payload_dir / "README.md"
        readme.write_text(f"# {payload_id}\n\nsummary\n", encoding="utf-8")

        manifest = {
            "schemaVersion": 1,
            "payloadId": payload_id,
            "createdUtc": created_utc,
        }
        chunk_index = {
            "schemaVersion": 1,
            "payloadId": payload_id,
            "chunks": [
                {
                    "chunkId": "chain-candidates",
                    "path": "candidates/chain-candidates.csv",
                    "kind": "csv",
                    "sizeBytes": chunk_path.stat().st_size,
                    "sha256": hashlib.sha256(chunk_path.read_bytes()).hexdigest(),
                    "description": "Ranked candidates.",
                },
                {
                    "chunkId": "binary-blocked",
                    "path": "candidates/raw.bin",
                    "kind": "binary",
                    "sizeBytes": bad_path.stat().st_size,
                    "sha256": hashlib.sha256(bad_path.read_bytes()).hexdigest(),
                    "description": "Blocked binary.",
                },
                {
                    "chunkId": "oversized",
                    "path": "reports/big.txt",
                    "kind": "txt",
                    "sizeBytes": big_path.stat().st_size,
                    "sha256": hashlib.sha256(big_path.read_bytes()).hexdigest(),
                    "description": "Oversized text.",
                },
                {
                    "chunkId": "sha-mismatch",
                    "path": "reports/mismatch.txt",
                    "kind": "txt",
                    "sizeBytes": mismatch_path.stat().st_size,
                    "sha256": sha256_text("wrong text\n"),
                    "description": "SHA mismatch fixture.",
                },
            ],
        }
        bridge.write_json(payload_dir / "manifest.json", manifest)
        bridge.write_json(payload_dir / "chunk-index.json", chunk_index)
        return payload_dir

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        connection = http.client.HTTPConnection(str(self.host), int(self.port), timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            body = response.read()
            headers = {key.lower(): value for key, value in response.getheaders()}
            return response.status, headers, body
        finally:
            connection.close()

    def test_health_endpoint_returns_json_and_expected_schema(self) -> None:
        status, headers, body = self.request("GET", f"/{self.token}/health")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["content-type"])
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(payload["schemaVersion"], 1)
        self.assertEqual(payload["service"], "riftreader-local-artifact-bridge")
        self.assertEqual(payload["mode"], "read_only_artifacts_with_guarded_local_inbox")
        self.assertTrue(payload["ok"])
        self.assertIn("/<token>/", payload["endpoints"])
        self.assertIn("/<token>/chatgpt-handoff.json", payload["endpoints"])
        self.assertIn("/<token>/inbox/schema.json", payload["endpoints"])
        self.assertIn("/<token>/payloads/latest/readme.md", payload["endpoints"])
        self.assertIn("/<token>/payloads/latest/chunks.json", payload["endpoints"])
        self.assertIn("POST /<token>/inbox/messages", payload["inboxEndpoints"])
        self.assertEqual(payload["localInbox"]["endpoint"], "/<token>/inbox/messages")
        self.assertEqual(payload["localInbox"]["schemaEndpoint"], "/<token>/inbox/schema.json")
        self.assertEqual(payload["desktopChatgptHandoff"]["endpoint"], "/<token>/chatgpt-handoff.json")
        self.assertFalse(payload["localInbox"]["applyExecuteInV0"])
        self.assertIn("chatgpt-message", payload["localInbox"]["acceptedKinds"])
        self.assertEqual(payload["recommendedReadOrder"][0]["path"], "/<token>/health")
        self.assertTrue(any("GET/HEAD only for artifact reads" in item for item in payload["chatgptInstructions"]))
        self.assertTrue(payload["safety"]["artifactReadGetHeadOnly"])
        self.assertTrue(payload["safety"]["inboxJsonPostOnly"])

    def test_landing_page_is_markdown_and_lists_bridge_start_paths(self) -> None:
        status, headers, body = self.request("GET", f"/{self.token}/")
        self.assertEqual(status, 200)
        self.assertIn("text/markdown", headers["content-type"])
        text = body.decode("utf-8")
        self.assertIn("RiftReader Local Artifact Bridge", text)
        self.assertIn("./chatgpt-handoff.json", text)
        self.assertIn("./inbox/schema.json", text)
        self.assertIn("./payloads/latest/readme.md", text)
        self.assertIn("./payloads/latest/chunks.json", text)
        self.assertIn("artifact reads are GET/HEAD only", text)
        self.assertIn("POST /<token>/inbox/messages", text)
        self.assertIn(".riftreader-local/artifact-bridge-inbox", text)
        self.assertIn(" - Confirm the bridge is reachable", text)
        self.assertNotIn("\u2014", text)

    def test_invalid_token_returns_403(self) -> None:
        status, _headers, _body = self.request("GET", "/wrong-token/health")
        self.assertEqual(status, 403)

    def test_unknown_endpoint_returns_404(self) -> None:
        status, _headers, body = self.request("GET", f"/{self.token}/missing")
        self.assertEqual(status, 404)
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(payload["code"], "ENDPOINT_NOT_FOUND")
        self.assertTrue(any("/<token>/health" in item for item in payload["next"]))
        self.assertTrue(any("/<token>/chatgpt-handoff.json" in item for item in payload["next"]))

    def test_non_get_method_returns_405(self) -> None:
        status, _headers, body = self.request("POST", f"/{self.token}/health")
        self.assertEqual(status, 405)
        payload = json.loads(body.decode("utf-8"))
        self.assertIn("GET", " ".join(payload["next"]))
        self.assertIn("HEAD", " ".join(payload["next"]))
        self.assertIn("inbox/messages", " ".join(payload["next"]))

    def test_inbox_post_stores_json_under_local_ignored_root(self) -> None:
        message = bridge.json_bytes(
            {
                "schemaVersion": 1,
                "kind": "chatgpt-message",
                "title": "Need repo processing",
                "body": "Please inspect this proposal later.",
                "metadata": {"source": "unit-test"},
            }
        )

        status, headers, body = self.request(
            "POST",
            f"/{self.token}/inbox/messages",
            body=message,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

        self.assertEqual(status, 201)
        self.assertIn("application/json", headers["content-type"])
        payload = json.loads(body.decode("utf-8"))
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["duplicate"])
        self.assertIn(".riftreader-local/artifact-bridge-inbox", payload["storedUnder"])
        self.assertTrue(payload["safety"]["noApplyExecute"])
        message_path = self.repo_root / payload["files"]["message"]
        metadata_path = self.repo_root / payload["files"]["metadata"]
        self.assertTrue(message_path.is_file())
        self.assertTrue(metadata_path.is_file())
        self.assertTrue(str(message_path.resolve()).startswith(str((self.repo_root / ".riftreader-local").resolve())))
        stored = json.loads(message_path.read_text(encoding="utf-8"))
        self.assertEqual(stored["message"]["title"], "Need repo processing")

    def test_inbox_duplicate_detection_returns_existing_item_without_second_write(self) -> None:
        message = bridge.json_bytes(
            {
                "schemaVersion": 1,
                "kind": "chatgpt-message",
                "title": "Duplicate proposal",
                "body": "Same canonical message.",
            }
        )
        first_status, _headers, first_body = self.request(
            "POST",
            f"/{self.token}/inbox/messages",
            body=message,
            headers={"Content-Type": "application/json"},
        )
        second_status, _headers, second_body = self.request(
            "POST",
            f"/{self.token}/inbox/messages",
            body=message,
            headers={"Content-Type": "application/json"},
        )

        first = json.loads(first_body.decode("utf-8"))
        second = json.loads(second_body.decode("utf-8"))
        self.assertEqual(first_status, 201)
        self.assertEqual(second_status, 200)
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["inboxId"], second["inboxId"])
        self.assertEqual(bridge.inbox_index(self.config)["count"], 1)

    def test_inbox_read_endpoint_and_latest_cli_return_stored_message(self) -> None:
        message = bridge.json_bytes(
            {
                "schemaVersion": 1,
                "kind": "chatgpt-message",
                "title": "Readable proposal",
                "body": "Read me back without applying.",
            }
        )
        post_status, _headers, post_body = self.request(
            "POST",
            f"/{self.token}/inbox/messages",
            body=message,
            headers={"Content-Type": "application/json"},
        )
        posted = json.loads(post_body.decode("utf-8"))
        inbox_id = posted["inboxId"]

        read_status, read_headers, read_body = self.request("GET", f"/{self.token}/inbox/messages/{inbox_id}")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            latest_exit = bridge.main(
                [
                    "--repo-root",
                    str(self.repo_root),
                    "--payload-root",
                    "artifacts/chatgpt-payloads",
                    "--token",
                    self.token,
                    "--port",
                    "0",
                    "--inbox-read-latest",
                    "--json",
                ]
            )
        latest = json.loads(stdout.getvalue())

        self.assertEqual(post_status, 201)
        self.assertEqual(read_status, 200)
        self.assertIn("application/json", read_headers["content-type"])
        read_payload = json.loads(read_body.decode("utf-8"))
        self.assertEqual(read_payload["kind"], "riftreader-local-artifact-bridge-inbox-read")
        self.assertEqual(read_payload["inboxId"], inbox_id)
        self.assertEqual(read_payload["message"]["message"]["title"], "Readable proposal")
        self.assertEqual(latest_exit, 0)
        self.assertEqual(latest["inboxId"], inbox_id)
        self.assertTrue(latest["safety"]["noApplyExecute"])

    def test_inbox_read_latest_cli_blocks_when_empty(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = bridge.main(
                [
                    "--repo-root",
                    str(self.repo_root),
                    "--payload-root",
                    "artifacts/chatgpt-payloads",
                    "--token",
                    self.token,
                    "--port",
                    "0",
                    "--inbox-read-latest",
                    "--json",
                ]
            )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "INBOX_EMPTY")

    def test_inbox_rejects_malformed_json(self) -> None:
        status, _headers, body = self.request(
            "POST",
            f"/{self.token}/inbox/messages",
            body=b"{not-json",
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(status, 400)
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(payload["code"], "INVALID_INBOX_JSON")
        self.assertTrue(any("UTF-8 JSON object" in item for item in payload["next"]))

    def test_inbox_rejects_unsupported_content_type(self) -> None:
        status, _headers, body = self.request(
            "POST",
            f"/{self.token}/inbox/messages",
            body=b"schemaVersion=1",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        self.assertEqual(status, 415)
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(payload["code"], "INBOX_CONTENT_TYPE_UNSUPPORTED")

    def test_inbox_rejects_unknown_fields_and_unsupported_kind(self) -> None:
        unknown = bridge.json_bytes(
            {
                "schemaVersion": 1,
                "kind": "chatgpt-message",
                "title": "Bad field",
                "body": "No hidden fields.",
                "command": "git status",
            }
        )
        status_unknown, _headers, body_unknown = self.request(
            "POST",
            f"/{self.token}/inbox/messages",
            body=unknown,
            headers={"Content-Type": "application/json"},
        )
        bad_kind = bridge.json_bytes(
            {
                "schemaVersion": 1,
                "kind": "execute-command",
                "title": "Bad kind",
                "body": "Rejected.",
            }
        )
        status_kind, _headers, body_kind = self.request(
            "POST",
            f"/{self.token}/inbox/messages",
            body=bad_kind,
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(status_unknown, 400)
        self.assertEqual(json.loads(body_unknown.decode("utf-8"))["code"], "INBOX_UNKNOWN_FIELD")
        self.assertEqual(status_kind, 400)
        self.assertEqual(json.loads(body_kind.decode("utf-8"))["code"], "INBOX_KIND_UNSUPPORTED")

    def test_inbox_oversized_body_returns_413(self) -> None:
        config = bridge.make_config(
            repo_root=self.repo_root,
            payload_root=pathlib.Path("artifacts") / "chatgpt-payloads",
            token="small-inbox",
            port=0,
            max_response_bytes=4096,
            max_inbox_bytes=64,
            log_requests=False,
        )
        server = bridge.create_http_server(config)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            body = bridge.json_bytes(
                {
                    "schemaVersion": 1,
                    "kind": "chatgpt-message",
                    "title": "Too large",
                    "body": "X" * 200,
                }
            )
            connection = http.client.HTTPConnection(str(host), int(port), timeout=5)
            try:
                connection.request(
                    "POST",
                    "/small-inbox/inbox/messages",
                    body=body,
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                response_body = response.read()
            finally:
                connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(response.status, 413)
        self.assertEqual(json.loads(response_body.decode("utf-8"))["code"], "INBOX_PAYLOAD_TOO_LARGE")

    def test_get_to_inbox_endpoint_returns_method_hint(self) -> None:
        status, _headers, body = self.request("GET", f"/{self.token}/inbox/messages")

        self.assertEqual(status, 405)
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(payload["code"], "INBOX_METHOD_NOT_ALLOWED")
        self.assertTrue(any("application/json" in item for item in payload["next"]))

    def test_invalid_inbox_read_id_is_rejected(self) -> None:
        status, _headers, body = self.request("GET", f"/{self.token}/inbox/messages/..%2Fsecret")

        self.assertEqual(status, 400)
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(payload["code"], "INBOX_ID_INVALID")

    def test_inbox_schema_endpoint_returns_template_and_safety(self) -> None:
        status, headers, body = self.request("GET", f"/{self.token}/inbox/schema.json")

        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["content-type"])
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(payload["kind"], "riftreader-local-artifact-bridge-inbox-schema")
        self.assertEqual(payload["endpoint"], "/<token>/inbox/messages")
        self.assertIn("chatgpt-message", payload["acceptedKinds"])
        self.assertEqual(payload["template"]["schemaVersion"], 1)
        self.assertEqual(payload["template"]["kind"], "chatgpt-message")
        self.assertEqual(payload["packageProposalTemplate"]["kind"], "package-proposal")
        self.assertEqual(payload["packageProposalTemplate"]["payload"]["files"][0]["encoding"], "utf-8")
        self.assertIn("checks", payload["packageProposalTemplate"]["payload"])
        self.assertFalse(payload["applyExecuteInV0"])
        self.assertTrue(payload["safety"]["noApplyExecute"])

    def test_chatgpt_handoff_endpoint_returns_read_order_and_inbox_schema(self) -> None:
        status, headers, body = self.request("GET", f"/{self.token}/chatgpt-handoff.json")

        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["content-type"])
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(payload["kind"], "riftreader-desktop-chatgpt-handoff")
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["latestPayloadId"], "pointer-chain-pack-20260517-002")
        self.assertEqual(payload["urlPatterns"]["inboxSchema"], "/<token>/inbox/schema.json")
        self.assertEqual(payload["inboxSchema"]["template"]["kind"], "chatgpt-message")
        self.assertEqual(payload["inboxSchema"]["packageProposalTemplate"]["kind"], "package-proposal")
        self.assertIn("RiftReader Local Artifact Bridge", payload["desktopChatgptPrompt"])
        self.assertTrue(payload["safety"]["noApplyExecute"])

    def test_payload_index_generation_finds_valid_payload(self) -> None:
        index = bridge.discover_payloads(self.config)
        self.assertEqual(index["payloadCount"], 2)
        self.assertEqual(index["latestPayloadId"], "pointer-chain-pack-20260517-002")

    def test_latest_payload_selection_is_deterministic(self) -> None:
        first = bridge.discover_payloads(self.config)["latestPayloadId"]
        second = bridge.discover_payloads(self.config)["latestPayloadId"]
        self.assertEqual(first, second)
        self.assertEqual(first, "pointer-chain-pack-20260517-002")

    def test_registered_chunk_serves_expected_content(self) -> None:
        status, headers, body = self.request("GET", f"/{self.token}/payloads/latest/chunks/chain-candidates")
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["content-type"])
        self.assertIn(b"0x2000", body)

    def test_latest_readme_alias_serves_same_summary_as_summary_endpoint(self) -> None:
        status_summary, _headers_summary, body_summary = self.request("GET", f"/{self.token}/payloads/latest/summary.md")
        status_readme, headers_readme, body_readme = self.request("GET", f"/{self.token}/payloads/latest/readme.md")
        self.assertEqual(status_summary, 200)
        self.assertEqual(status_readme, 200)
        self.assertIn("text/markdown", headers_readme["content-type"])
        self.assertEqual(body_summary, body_readme)
        self.assertIn(b"pointer-chain-pack-20260517-002", body_readme)

    def test_latest_chunks_alias_serves_same_index_as_chunk_index_endpoint(self) -> None:
        status_index, _headers_index, body_index = self.request("GET", f"/{self.token}/payloads/latest/chunk-index.json")
        status_alias, headers_alias, body_alias = self.request("GET", f"/{self.token}/payloads/latest/chunks.json")
        self.assertEqual(status_index, 200)
        self.assertEqual(status_alias, 200)
        self.assertIn("application/json", headers_alias["content-type"])
        self.assertEqual(json.loads(body_index.decode("utf-8")), json.loads(body_alias.decode("utf-8")))

    def test_missing_chunk_returns_404(self) -> None:
        status, _headers, _body = self.request("GET", f"/{self.token}/payloads/latest/chunks/no-such-chunk")
        self.assertEqual(status, 404)

    def test_path_traversal_chunk_id_is_rejected(self) -> None:
        status, _headers, _body = self.request("GET", f"/{self.token}/payloads/latest/chunks/..%2Fsecret")
        self.assertEqual(status, 400)

    def test_absolute_path_like_chunk_id_is_rejected(self) -> None:
        status, _headers, _body = self.request("GET", f"/{self.token}/payloads/latest/chunks/C:%5Ctemp")
        self.assertEqual(status, 400)

    def test_binary_extension_is_blocked_by_default(self) -> None:
        status, _headers, _body = self.request("GET", f"/{self.token}/payloads/latest/chunks/binary-blocked")
        self.assertEqual(status, 415)

    def test_oversized_chunk_returns_413(self) -> None:
        status, _headers, _body = self.request("GET", f"/{self.token}/payloads/latest/chunks/oversized")
        self.assertEqual(status, 413)

    def test_sha_mismatch_is_surfaced_in_index_metadata(self) -> None:
        index = bridge.discover_payloads(self.config)
        latest = index["payloads"][-1]
        mismatched = [chunk for chunk in latest["chunks"] if chunk["chunkId"] == "sha-mismatch"]
        self.assertEqual(len(mismatched), 1)
        self.assertEqual(mismatched[0]["sha256Status"], "mismatch")

    def test_preflight_valid_payload_passes_and_redacts_token(self) -> None:
        payload = bridge.preflight_payload(self.config)

        self.assertEqual(payload["kind"], "riftreader-local-artifact-bridge-preflight")
        self.assertEqual(payload["status"], "passed")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["payloadCount"], 2)
        self.assertEqual(payload["latestPayloadId"], "pointer-chain-pack-20260517-002")
        self.assertIn("<token>", payload["redactedUrls"]["health"])
        self.assertIn("<token>", payload["redactedUrls"]["handoff"])
        self.assertIn("<token>", payload["redactedUrls"]["inboxSchema"])
        self.assertNotIn(self.token, json.dumps(payload["redactedUrls"]))
        self.assertIn("--serve", payload["manualStartCommand"])
        self.assertIn("--token auto", payload["manualStartCommand"])
        self.assertIn("--max-inbox-mb 1", payload["manualStartCommand"])
        self.assertTrue(payload["safety"]["noServerStarted"])
        self.assertTrue(payload["safety"]["tokenRedacted"])

    def test_preflight_missing_payload_root_blocks_without_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            config = bridge.make_config(
                repo_root=root,
                payload_root=pathlib.Path("artifacts") / "chatgpt-payloads",
                token="missing-token",
                port=0,
                log_requests=False,
            )

            payload = bridge.preflight_payload(config)

        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["ok"])
        self.assertIn("payload_root_missing", payload["blockers"])
        self.assertEqual(payload["payloadCount"], 0)
        self.assertTrue(payload["safety"]["noServerStarted"])

    def test_preflight_invalid_payload_contract_blocks_with_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            payload_root = root / "artifacts" / "chatgpt-payloads"
            bad_payload = payload_root / "bad-payload"
            bad_payload.mkdir(parents=True)
            bridge.write_json(bad_payload / "manifest.json", {"payloadId": "bad-payload"})
            config = bridge.make_config(
                repo_root=root,
                payload_root=pathlib.Path("artifacts") / "chatgpt-payloads",
                token="invalid-token",
                port=0,
                log_requests=False,
            )

            payload = bridge.preflight_payload(config)

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("no_valid_payloads", payload["blockers"])
        self.assertIn("skipped_missing_contract:bad-payload", payload["warnings"])

    def test_preflight_cli_json_uses_exit_2_for_blocked_first_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = bridge.main(
                    [
                        "--repo-root",
                        str(root),
                        "--payload-root",
                        "artifacts/chatgpt-payloads",
                        "--token",
                        "blocked-token",
                        "--port",
                        "0",
                        "--preflight",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("payload_root_missing", payload["blockers"])

    def test_preflight_cli_json_passes_for_valid_payload(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = bridge.main(
                [
                    "--repo-root",
                    str(self.repo_root),
                    "--payload-root",
                    "artifacts/chatgpt-payloads",
                    "--token",
                    self.token,
                    "--port",
                    "0",
                    "--preflight",
                    "--json",
                ]
            )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["latestPayloadId"], "pointer-chain-pack-20260517-002")

    def test_inbox_index_cli_json_lists_stored_items_without_applying(self) -> None:
        message = {
            "schemaVersion": 1,
            "kind": "chatgpt-message",
            "title": "CLI index item",
            "body": "Stored for index check.",
        }
        bridge.store_inbox_message(self.config, bridge.validate_inbox_message(message), len(bridge.json_bytes(message)))
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = bridge.main(
                [
                    "--repo-root",
                    str(self.repo_root),
                    "--payload-root",
                    "artifacts/chatgpt-payloads",
                    "--token",
                    self.token,
                    "--port",
                    "0",
                    "--inbox-index",
                    "--json",
                ]
            )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["kind"], "riftreader-local-artifact-bridge-inbox-index")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["title"], "CLI index item")
        self.assertFalse(payload["items"][0]["applied"])
        self.assertFalse(payload["items"][0]["executed"])
        self.assertTrue(payload["safety"]["noApplyExecute"])

    def test_inbox_package_draft_cli_creates_valid_package_without_target_write(self) -> None:
        target = self.repo_root / "docs" / "desktop-chatgpt-proposed.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("old content\n", encoding="utf-8")
        message = {
            "schemaVersion": 1,
            "kind": "package-proposal",
            "title": "Draft package proposal",
            "payload": {
                "packageName": "Desktop ChatGPT proposed patch",
                "files": [
                    {
                        "target": "docs/desktop-chatgpt-proposed.md",
                        "content": "# Proposed\n\nNew content from Desktop ChatGPT.\n",
                        "encoding": "utf-8",
                    }
                ],
                "checks": [
                    {
                        "name": "compile-bridge",
                        "args": ["python", "-m", "py_compile", "tools/riftreader_workflow/local_artifact_bridge.py"],
                        "expectedExitCodes": [0],
                        "timeoutSeconds": 120,
                    }
                ],
            },
            "source": {
                "tool": "Desktop ChatGPT",
                "context": "unit-test proposal",
            },
            "metadata": {
                "requiresHumanReview": True,
                "draftOnly": True,
            },
        }
        stored = bridge.store_inbox_message(self.config, bridge.validate_inbox_message(message), len(bridge.json_bytes(message)))
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = bridge.main(
                [
                    "--repo-root",
                    str(self.repo_root),
                    "--payload-root",
                    "artifacts/chatgpt-payloads",
                    "--token",
                    self.token,
                    "--port",
                    "0",
                    "--inbox-package-draft",
                    stored["inboxId"],
                    "--json",
                ]
            )
        payload = json.loads(stdout.getvalue())
        manifest_path = self.repo_root / payload["manifestPath"]
        summary_path = self.repo_root / payload["summaryPath"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "created")
        self.assertEqual(payload["kind"], "riftreader-local-artifact-bridge-inbox-package-draft")
        self.assertEqual(payload["inboxId"], stored["inboxId"])
        self.assertEqual(payload["packageName"], "Desktop ChatGPT proposed patch")
        self.assertEqual(payload["messageMetadata"]["requiresHumanReview"], True)
        self.assertEqual(payload["messageMetadata"]["draftOnly"], True)
        self.assertEqual(payload["messageSource"]["tool"], "Desktop ChatGPT")
        self.assertEqual(payload["fileCount"], 1)
        self.assertEqual(payload["validation"]["errors"], [])
        self.assertEqual(manifest["files"][0]["target"], "docs/desktop-chatgpt-proposed.md")
        self.assertTrue(manifest_path.is_file())
        self.assertTrue(summary_path.is_file())
        self.assertIn(".riftreader-local/artifact-bridge-package-drafts", payload["draftRoot"])
        self.assertTrue(payload["safety"]["draftUnderDotRiftReaderLocal"])
        self.assertTrue(payload["safety"]["noApplyExecute"])
        self.assertTrue(payload["safety"]["noGitMutation"])
        self.assertTrue(payload["safety"]["noRepoTargetWrites"])
        self.assertEqual(target.read_text(encoding="utf-8"), "old content\n")

    def test_inbox_package_draft_cli_without_id_uses_latest_inbox_item(self) -> None:
        message = {
            "schemaVersion": 1,
            "kind": "package-proposal",
            "title": "Latest package proposal",
            "payload": {
                "files": [
                    {
                        "target": "docs/latest-proposal.md",
                        "content": "# Latest proposal\n",
                    }
                ]
            },
        }
        stored = bridge.store_inbox_message(self.config, bridge.validate_inbox_message(message), len(bridge.json_bytes(message)))
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = bridge.main(
                [
                    "--repo-root",
                    str(self.repo_root),
                    "--payload-root",
                    "artifacts/chatgpt-payloads",
                    "--token",
                    self.token,
                    "--port",
                    "0",
                    "--inbox-package-draft",
                    "--json",
                ]
            )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "created")
        self.assertEqual(payload["inboxId"], stored["inboxId"])
        self.assertEqual(payload["validation"]["errors"], [])
        self.assertFalse((self.repo_root / "docs" / "latest-proposal.md").exists())

    def test_inbox_package_draft_cli_blocks_empty_inbox(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = bridge.main(
                [
                    "--repo-root",
                    str(self.repo_root),
                    "--payload-root",
                    "artifacts/chatgpt-payloads",
                    "--token",
                    self.token,
                    "--port",
                    "0",
                    "--inbox-package-draft",
                    "--json",
                ]
            )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["code"], "INBOX_EMPTY")
        self.assertTrue(payload["safety"]["noApplyExecute"])

    def test_inbox_package_draft_cli_rejects_non_package_proposal(self) -> None:
        message = {
            "schemaVersion": 1,
            "kind": "chatgpt-message",
            "title": "Review note",
            "body": "This is not a package proposal.",
        }
        stored = bridge.store_inbox_message(self.config, bridge.validate_inbox_message(message), len(bridge.json_bytes(message)))
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = bridge.main(
                [
                    "--repo-root",
                    str(self.repo_root),
                    "--payload-root",
                    "artifacts/chatgpt-payloads",
                    "--token",
                    self.token,
                    "--port",
                    "0",
                    "--inbox-package-draft",
                    stored["inboxId"],
                    "--json",
                ]
            )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["code"], "INBOX_PACKAGE_DRAFT_KIND_INVALID")
        self.assertEqual(payload["messageKind"], "chatgpt-message")
        self.assertTrue(payload["safety"]["noRepoTargetWrites"])

    def test_inbox_package_draft_cli_blocks_unsafe_target_with_local_summary(self) -> None:
        message = {
            "schemaVersion": 1,
            "kind": "package-proposal",
            "title": "Unsafe target proposal",
            "payload": {
                "files": [
                    {
                        "target": ".git/config",
                        "content": "[core]\nunsafe = true\n",
                    }
                ]
            },
        }
        stored = bridge.store_inbox_message(self.config, bridge.validate_inbox_message(message), len(bridge.json_bytes(message)))
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = bridge.main(
                [
                    "--repo-root",
                    str(self.repo_root),
                    "--payload-root",
                    "artifacts/chatgpt-payloads",
                    "--token",
                    self.token,
                    "--port",
                    "0",
                    "--inbox-package-draft",
                    stored["inboxId"],
                    "--json",
                ]
            )
        payload = json.loads(stdout.getvalue())
        summary_path = self.repo_root / payload["summaryPath"]
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["code"], "INBOX_PACKAGE_DRAFT_VALIDATION_FAILED")
        self.assertTrue(any("target-denied-prefix:.git/config" in item for item in payload["blockers"]))
        self.assertTrue(summary_path.is_file())
        self.assertEqual(summary["code"], "INBOX_PACKAGE_DRAFT_VALIDATION_FAILED")
        self.assertTrue(payload["safety"]["draftUnderDotRiftReaderLocal"])
        self.assertFalse((self.repo_root / ".git" / "config").exists())

    def test_chatgpt_handoff_cli_json_is_redacted_and_includes_template(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = bridge.main(
                [
                    "--repo-root",
                    str(self.repo_root),
                    "--payload-root",
                    "artifacts/chatgpt-payloads",
                    "--token",
                    self.token,
                    "--port",
                    "0",
                    "--chatgpt-handoff",
                    "--json",
                ]
            )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["kind"], "riftreader-desktop-chatgpt-handoff")
        self.assertEqual(payload["status"], "ready")
        self.assertIn("<token>", json.dumps(payload["urlPatterns"]))
        self.assertNotIn(self.token, json.dumps(payload["urlPatterns"]))
        self.assertEqual(payload["inboxSchema"]["template"]["schemaVersion"], 1)
        self.assertTrue(payload["safety"]["noCommandExecutionEndpoint"])

    def test_session_start_cli_json_is_ready_redacted_and_summarizes_inbox(self) -> None:
        message = {
            "schemaVersion": 1,
            "kind": "chatgpt-message",
            "title": "Session proposal",
            "body": "Stored for latest inbox summary.",
        }
        bridge.store_inbox_message(self.config, bridge.validate_inbox_message(message), len(bridge.json_bytes(message)))
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = bridge.main(
                [
                    "--repo-root",
                    str(self.repo_root),
                    "--payload-root",
                    "artifacts/chatgpt-payloads",
                    "--token",
                    self.token,
                    "--port",
                    "0",
                    "--session-start",
                    "--json",
                ]
            )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["kind"], "riftreader-desktop-chatgpt-session-start")
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["payload"]["latest"]["payloadId"], "pointer-chain-pack-20260517-002")
        self.assertEqual(payload["localInbox"]["count"], 1)
        self.assertEqual(payload["localInbox"]["latest"]["title"], "Session proposal")
        self.assertIn("--inbox-package-draft", payload["localInbox"]["packageDraftCommand"])
        self.assertIn("--index", payload["localInbox"]["packageDraftIndexCommand"])
        self.assertIn("riftreader-package-draft-review.cmd", payload["localInbox"]["latestPackageDraftCommand"])
        self.assertIn("--latest-operator", payload["localInbox"]["latestOperatorPackageDraftCommand"])
        self.assertIn("--dry-run-latest", payload["localInbox"]["latestPackageDraftDryRunCommand"])
        self.assertIn("--dry-run-latest-operator", payload["localInbox"]["latestOperatorPackageDraftDryRunCommand"])
        self.assertIn("--self-test", payload["localInbox"]["packageDraftSelfTestCommand"])
        self.assertIn("--proposal-loop-checks", payload["localInbox"]["proposalLoopChecksCommand"])
        self.assertIn("--trial-readiness", payload["localInbox"]["trialReadinessCommand"])
        self.assertIn("--serve", payload["operatorCommands"]["manualStart"])
        self.assertIn("--session-start", payload["operatorCommands"]["sessionStart"])
        self.assertIn("--trial-readiness", payload["operatorCommands"]["trialReadiness"])
        self.assertIn("<token>", json.dumps(payload["redactedUrls"]))
        self.assertNotIn(self.token, json.dumps(payload["redactedUrls"]))
        self.assertTrue(payload["safety"]["noServerStarted"])
        self.assertTrue(payload["safety"]["manualServeOnly"])
        self.assertIn("/chatgpt-handoff.json", payload["copyableChatgptPrompt"])

    def test_session_start_cli_json_blocks_without_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = bridge.main(
                    [
                        "--repo-root",
                        str(root),
                        "--payload-root",
                        "artifacts/chatgpt-payloads",
                        "--token",
                        "session-token",
                        "--port",
                        "0",
                        "--session-start",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn("payload_root_missing", payload["blockers"])
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["safety"]["noServerStarted"])

    def test_bootstrap_payload_cli_creates_valid_payload_and_clears_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = pathlib.Path(temp_dir)
            for rel in [
                "README.md",
                "AGENTS.md",
                "docs/workflow/non-codex-desktop-chatgpt-workflow.md",
                "docs/workflow/local-artifact-bridge.md",
                "docs/workflow/operator-lite.md",
            ]:
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(f"# {rel}\n\nBootstrap fixture.\n", encoding="utf-8")
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = bridge.main(
                    [
                        "--repo-root",
                        str(root),
                        "--payload-root",
                        "artifacts/chatgpt-payloads",
                        "--token",
                        "bootstrap-token",
                        "--port",
                        "0",
                        "--bootstrap-payload",
                        "--payload-id",
                        "desktop-chatgpt-bootstrap-test",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            config = bridge.make_config(
                repo_root=root,
                payload_root=pathlib.Path("artifacts/chatgpt-payloads"),
                token="bootstrap-token",
                port=0,
                log_requests=False,
            )
            preflight = bridge.preflight_payload(config)

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "created")
        self.assertEqual(payload["payloadId"], "desktop-chatgpt-bootstrap-test")
        self.assertEqual(payload["chunkCount"], 6)
        self.assertEqual(preflight["status"], "passed")
        self.assertEqual(preflight["latestPayloadId"], "desktop-chatgpt-bootstrap-test")

    def test_self_test_covers_http_package_proposal_to_draft_loop(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = bridge.run_self_test(json_mode=True)
        payload = json.loads(stdout.getvalue())
        checks = {item["name"]: item for item in payload["checks"]}

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["selfTest"])
        self.assertGreaterEqual(payload["checkCount"], 18)
        self.assertTrue(checks["inbox_package_proposal_store"]["pass"])
        self.assertTrue(checks["inbox_package_proposal_draft"]["pass"])
        self.assertFalse(checks["inbox_package_proposal_draft"]["targetFileCreated"])
        self.assertTrue(payload["safety"]["packageProposalHttpPostCovered"])
        self.assertTrue(payload["safety"]["packageDraftCreatedLocalIgnoredOnly"])
        self.assertFalse(payload["safety"]["packageIntakeInvoked"])
        self.assertFalse(payload["safety"]["gitMutation"])


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
