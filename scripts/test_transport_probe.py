# Version: riftreader-transport-probe-tests-v0.1.3
# Total-Character-Count: 9000
# Purpose: Unit tests for the Python-owned RiftReader transport probe helper.
from __future__ import annotations

import json
import io
import shutil
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import redirect_stdout
from pathlib import Path

from tools.riftreader_workflow import transport_probe as probe


class TransportProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="riftreader-transport-probe-test-")
        self.repo_root = Path(self.tmp.name)
        self.payload_root = self.repo_root / "artifacts" / "chatgpt-payloads"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_create_payload_writes_contract_files(self) -> None:
        info = probe.create_payload(self.repo_root, self.payload_root, "transport-smoke-test", "nonce123")
        self.assertTrue(info.manifest_path.is_file())
        self.assertTrue(info.chunk_index_path.is_file())
        self.assertTrue(info.summary_path.is_file())
        self.assertTrue(info.ping_chunk_path.is_file())
        self.assertEqual(info.nonce, "nonce123")

    def test_load_latest_payload_is_deterministic(self) -> None:
        older = probe.create_payload(self.repo_root, self.payload_root, "transport-smoke-a", "nonceA")
        newer = probe.create_payload(self.repo_root, self.payload_root, "transport-smoke-b", "nonceB")
        loaded = probe.load_payload_info(self.payload_root, "latest")
        self.assertIn(loaded.payload_id, {older.payload_id, newer.payload_id})
        self.assertEqual(loaded.payload_id, "transport-smoke-b")

    def test_reply_template_matches_payload(self) -> None:
        info = probe.create_payload(self.repo_root, self.payload_root, "transport-smoke-test", "nonce123")
        template = probe.build_reply_template(info)
        self.assertEqual(template["payloadId"], info.payload_id)
        self.assertEqual(template["nonce"], info.nonce)
        self.assertEqual(template["observedChunkSha256"], info.ping_sha256)

    def test_verify_valid_reply_passes(self) -> None:
        info = probe.create_payload(self.repo_root, self.payload_root, "transport-smoke-test", "nonce123")
        reply = self.repo_root / "reply.json"
        reply.write_text(probe.json_dumps(probe.build_reply_template(info)), encoding="utf-8")
        result = probe.verify_reply(self.payload_root, reply, "latest")
        self.assertTrue(result["ok"])
        self.assertEqual(result["errors"], [])

    def test_verify_nonce_mismatch_fails(self) -> None:
        info = probe.create_payload(self.repo_root, self.payload_root, "transport-smoke-test", "nonce123")
        bad = probe.build_reply_template(info)
        bad["nonce"] = "wrong"
        reply = self.repo_root / "reply-bad.json"
        reply.write_text(probe.json_dumps(bad), encoding="utf-8")
        result = probe.verify_reply(self.payload_root, reply, info.payload_id)
        self.assertFalse(result["ok"])
        self.assertIn("nonce mismatch", result["errors"])

    def test_verify_sha_mismatch_fails(self) -> None:
        info = probe.create_payload(self.repo_root, self.payload_root, "transport-smoke-test", "nonce123")
        bad = probe.build_reply_template(info)
        bad["observedChunkSha256"] = "0" * 64
        reply = self.repo_root / "reply-bad-sha.json"
        reply.write_text(probe.json_dumps(bad), encoding="utf-8")
        result = probe.verify_reply(self.payload_root, reply, info.payload_id)
        self.assertFalse(result["ok"])
        self.assertIn("observedChunkSha256 mismatch", result["errors"])

    def test_bad_payload_id_rejects_traversal(self) -> None:
        with self.assertRaises(probe.TransportProbeError):
            probe.create_payload(self.repo_root, self.payload_root, "../bad", "nonce")

    def test_normalize_relative_rejects_backslash(self) -> None:
        with self.assertRaises(probe.TransportProbeError):
            probe.normalize_relative("chunks\\bad.json")

    def test_self_test_returns_zero(self) -> None:
        captured = io.StringIO()
        with redirect_stdout(captured):
            self.assertEqual(probe.main(["--json", "self-test"]), 0)
        self.assertIn("riftreader-transport-probe-v0.1.3", captured.getvalue())


    def test_local_smoke_runs_installed_bridge_in_process(self) -> None:
        bridge_source = Path(probe.__file__).with_name("local_artifact_bridge.py")
        if not bridge_source.is_file():
            self.skipTest("local_artifact_bridge.py is not installed beside transport_probe.py")
        bridge_target = self.repo_root / "tools" / "riftreader_workflow" / "local_artifact_bridge.py"
        bridge_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bridge_source, bridge_target)
        package_manifest_source = Path(probe.__file__).with_name("package_manifest.py")
        if not package_manifest_source.is_file():
            self.skipTest("package_manifest.py is not installed beside transport_probe.py")
        shutil.copy2(package_manifest_source, bridge_target.parent / "package_manifest.py")
        result = probe.run_local_bridge_smoke(
            self.repo_root,
            self.payload_root,
            payload_id="transport-smoke-local",
            nonce="nonce-local-123",
            token="transport-smoke-token",
            max_response_mb=25,
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["payloadId"], "transport-smoke-local")
        self.assertEqual(result["nonce"], "nonce-local-123")
        self.assertEqual(result["bridgeVerify"]["payloadId"], "transport-smoke-local")
        self.assertIn("<token>", result["baseUrlRedacted"])

    def test_bridge_roundtrip_writes_and_validates_reply_with_fake_server(self) -> None:
        info = probe.create_payload(self.repo_root, self.payload_root, "transport-smoke-roundtrip", "nonce-roundtrip")
        payload_dir = info.payload_dir

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
                parts = [part for part in self.path.split("/") if part]
                suffix = "/" + "/".join(parts[1:]) if len(parts) > 1 else "/"
                if suffix == "/health":
                    self._send_json({"ok": True})
                elif suffix == "/payloads/index.json":
                    self._send_json({"payloads": [{"payloadId": info.payload_id}]})
                elif suffix == "/payloads/latest/manifest.json":
                    self._send_bytes((payload_dir / "manifest.json").read_bytes(), "application/json")
                elif suffix == "/payloads/latest/summary.md":
                    self._send_bytes((payload_dir / "README.md").read_bytes(), "text/markdown")
                elif suffix == "/payloads/latest/chunk-index.json":
                    self._send_bytes((payload_dir / "chunk-index.json").read_bytes(), "application/json")
                elif suffix == "/payloads/latest/chunks/transport-ping":
                    self._send_bytes((payload_dir / "chunks" / "transport-ping.json").read_bytes(), "application/json")
                else:
                    self.send_error(404)

            def _send_json(self, value: dict) -> None:
                self._send_bytes(probe.json_dumps(value).encode("utf-8"), "application/json")

            def _send_bytes(self, body: bytes, content_type: str) -> None:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            base_url = f"http://{host}:{port}/token123"
            result = probe.run_bridge_roundtrip(
                base_url=base_url,
                repo_root=self.repo_root,
                payload_root=self.payload_root,
                payload_id=info.payload_id,
                reply_dir=".riftreader-local/transport-probe/replies",
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertTrue(result["ok"], result)
        self.assertIn("<token>", result["baseUrlRedacted"])
        self.assertTrue(Path(result["replyFile"]).is_file())
        self.assertTrue(result["replyValidation"]["ok"])
        self.assertEqual(result["reply"]["payloadId"], info.payload_id)

    def test_bridge_roundtrip_rejects_reply_dir_outside_allowed_roots(self) -> None:
        with self.assertRaises(probe.TransportProbeError):
            probe.write_automated_reply(
                self.repo_root,
                {"payloadId": "transport-smoke-test"},
                "tmp/not-allowed",
            )



if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
