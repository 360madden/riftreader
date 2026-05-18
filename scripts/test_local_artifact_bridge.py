# Version: riftreader-local-artifact-bridge-tests-v0.1.0
# Total-Character-Count: 8828
# Purpose: Unit tests for the RiftReader read-only local artifact bridge v0.1 endpoint, indexing, and blocking behavior.
from __future__ import annotations

import hashlib
import http.client
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
            max_response_bytes=1024,
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
        big_path.write_text("Z" * 2048, encoding="utf-8")
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

    def request(self, method: str, path: str) -> tuple[int, dict[str, str], bytes]:
        connection = http.client.HTTPConnection(str(self.host), int(self.port), timeout=5)
        try:
            connection.request(method, path)
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
        self.assertEqual(payload["mode"], "read_only")
        self.assertTrue(payload["ok"])

    def test_invalid_token_returns_403(self) -> None:
        status, _headers, _body = self.request("GET", "/wrong-token/health")
        self.assertEqual(status, 403)

    def test_unknown_endpoint_returns_404(self) -> None:
        status, _headers, _body = self.request("GET", f"/{self.token}/missing")
        self.assertEqual(status, 404)

    def test_non_get_method_returns_405(self) -> None:
        status, _headers, _body = self.request("POST", f"/{self.token}/health")
        self.assertEqual(status, 405)

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


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
