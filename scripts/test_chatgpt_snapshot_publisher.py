# Version: riftreader-test-chatgpt-snapshot-publisher-v0.1.0
# Total-Character-Count: 0000005612
# Purpose: Unit tests for the RiftReader ChatGPT snapshot publisher helper.
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.riftreader_workflow import chatgpt_snapshot_publisher as publisher  # noqa: E402


class SnapshotPublisherTests(unittest.TestCase):
    def test_token_from_url(self) -> None:
        token, public = publisher.token_from_url("https://example.trycloudflare.com/abcdef1234567890/chatgpt-handoff.json")
        self.assertEqual(token, "abcdef1234567890")
        self.assertEqual(public, "https://example.trycloudflare.com/abcdef1234567890")

    def test_validate_chunk_id_rejects_path_like(self) -> None:
        for bad in ("../secret", "C:\\temp", "bad/id", "bad:id", ""):
            with self.subTest(bad=bad):
                with self.assertRaises(publisher.SnapshotError):
                    publisher.validate_chunk_id(bad)

    def test_validate_chunk_id_accepts_known_safe_id(self) -> None:
        self.assertEqual(publisher.validate_chunk_id("desktop-chatgpt-workflow"), "desktop-chatgpt-workflow")

    def test_validate_branch_name_rejects_unsafe(self) -> None:
        for bad in ("../main", "/main", "chatgpt//snapshot", "bad@{branch}", "bad\\branch"):
            with self.subTest(bad=bad):
                with self.assertRaises(publisher.SnapshotError):
                    publisher.validate_branch_name(bad)

    def test_redact_text_removes_token_and_trycloudflare_url(self) -> None:
        source = publisher.BridgeSource(
            host="127.0.0.1",
            port=8765,
            token="abcdef1234567890",
            public_url="https://name.trycloudflare.com/abcdef1234567890",
        )
        text = "https://name.trycloudflare.com/abcdef1234567890/health token=abcdef1234567890"
        redacted = publisher.redact_text(text, source)
        self.assertNotIn("abcdef1234567890", redacted)
        self.assertIn("<redacted-token>", redacted)

    def test_select_chunk_ids_defaults(self) -> None:
        chunks_json = {
            "chunks": [
                {"chunkId": "repo-readme"},
                {"chunkId": "desktop-chatgpt-workflow"},
                {"chunkId": "local-artifact-bridge-docs"},
                {"chunkId": "repo-status"},
            ]
        }
        selected = publisher.select_chunk_ids(chunks_json, [], False)
        self.assertEqual(selected, ["desktop-chatgpt-workflow", "local-artifact-bridge-docs", "repo-status"])

    def test_render_and_size_limit(self) -> None:
        snapshot = {
            "schemaVersion": 1,
            "kind": "riftreader-chatgpt-bridge-snapshot",
            "tool": publisher.VERSION,
            "generatedAtUtc": "2026-06-03T00:00:00Z",
            "source": {"mode": "test"},
            "handoffSummary": {"ok": True, "status": "ready", "latestPayloadId": "p", "payloadCount": 1},
            "healthSummary": {"ok": True, "status": "ready", "latestPayloadId": "p", "payloadCount": 1},
            "endpoints": {
                "readme": {"path": "/readme", "status": "ok", "size_bytes": 5, "sha256": "x", "content": "# Readme\n"},
                "chunks": {"path": "/chunks", "status": "ok", "size_bytes": 2, "sha256": "y", "content": "{}"},
            },
            "selectedChunkIds": ["repo-status"],
            "chunks": {
                "repo-status": {"path": "/chunk", "status": "ok", "size_bytes": 2, "sha256": "z", "content": "{}"}
            },
        }
        md = publisher.render_markdown(snapshot)
        self.assertIn("RiftReader ChatGPT Bridge Snapshot", md)
        publisher.enforce_size(md, json.dumps(snapshot), 64)
        with self.assertRaises(publisher.SnapshotError):
            publisher.enforce_size(md * 100, json.dumps(snapshot), 1)

    def test_self_test_passes(self) -> None:
        self.assertEqual(publisher.run_self_test(), 0)

    def test_write_snapshot_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            snapshot = {
                "schemaVersion": 1,
                "kind": "riftreader-chatgpt-bridge-snapshot",
                "tool": publisher.VERSION,
                "generatedAtUtc": "2026-06-03T00:00:00Z",
                "source": {"mode": "test"},
                "handoffSummary": {"ok": True, "status": "ready", "latestPayloadId": "p", "payloadCount": 1},
                "healthSummary": {"ok": True, "status": "ready", "latestPayloadId": "p", "payloadCount": 1},
                "endpoints": {
                    "readme": {"path": "/readme", "status": "ok", "size_bytes": 5, "sha256": "x", "content": "# Readme\n"},
                    "chunks": {"path": "/chunks", "status": "ok", "size_bytes": 2, "sha256": "y", "content": "{}"},
                },
                "selectedChunkIds": ["repo-status"],
                "chunks": {
                    "repo-status": {"path": "/chunk", "status": "ok", "size_bytes": 2, "sha256": "z", "content": "{}"}
                },
            }
            summary = publisher.write_snapshot_files(repo, snapshot, 64)
            self.assertTrue((repo / publisher.DEFAULT_SNAPSHOT_MD).exists())
            self.assertTrue((repo / publisher.DEFAULT_SNAPSHOT_JSON).exists())
            self.assertGreater(summary["markdownBytes"], 0)


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
