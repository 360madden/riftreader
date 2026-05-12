#!/usr/bin/env python3
# Version: riftreader-drive-outbox-export-tests-v0.2.0
# Total-Character-Count: 4731
# Purpose: Test RiftReader Drive outbox export helper path safety, file classification, dry-run manifest generation, and export behavior.

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import riftreader_drive_outbox_export as helper


class DriveOutboxExportTests(unittest.TestCase):
    def test_decide_file_includes_small_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / ".git").mkdir()
            file_path = root / "status.json"
            file_path.write_text('{"ok": true}\n', encoding="utf-8")

            decision = helper.decide_file(file_path, root, 5_000_000)

            self.assertTrue(decision.include)
            self.assertEqual(decision.relative_path, "status.json")
            self.assertIsNotNone(decision.sha256)

    def test_decide_file_rejects_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / ".git").mkdir()
            file_path = root / "bad.json"
            file_path.write_bytes(b"abc\x00def")

            decision = helper.decide_file(file_path, root, 5_000_000)

            self.assertFalse(decision.include)
            self.assertEqual(decision.reason, "binary_like_null_byte")

    def test_decide_file_rejects_zip_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / ".git").mkdir()
            file_path = root / "patch.zip"
            file_path.write_text("not really zip", encoding="utf-8")

            decision = helper.decide_file(file_path, root, 5_000_000)

            self.assertFalse(decision.include)
            self.assertEqual(decision.reason, "blocked_extension:.zip")

    def test_decide_file_rejects_secret_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / ".git").mkdir()
            file_path = root / "secret.txt"
            file_path.write_text("token ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaa\n", encoding="utf-8")

            decision = helper.decide_file(file_path, root, 5_000_000)

            self.assertFalse(decision.include)
            self.assertEqual(decision.reason, "secret_pattern:github_token")

    def test_export_dry_run_writes_no_drive_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            drive = Path(tmp) / "drive" / "RiftReader"
            repo.mkdir()
            drive.mkdir(parents=True)
            (repo / ".git").mkdir()
            source = repo / "docs" / "status.md"
            source.parent.mkdir()
            source.write_text("# status\n", encoding="utf-8")

            code = helper.main([
                "--repo-root", str(repo),
                "--drive-root", str(drive),
                "--source", "docs/status.md",
                "--dry-run",
                "--json",
            ])

            self.assertEqual(code, 0)
            self.assertFalse((drive / "outbox").exists())

    def test_export_copies_file_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            drive = Path(tmp) / "drive" / "RiftReader"
            repo.mkdir()
            drive.mkdir(parents=True)
            (repo / ".git").mkdir()
            source = repo / "docs" / "status.md"
            source.parent.mkdir()
            source.write_text("# status\n", encoding="utf-8")

            with patch("riftreader_drive_outbox_export.utc_stamp", return_value="20260512T000000Z"):
                code = helper.main([
                    "--repo-root", str(repo),
                    "--drive-root", str(drive),
                    "--source", "docs/status.md",
                    "--label", "unit-test",
                    "--json",
                ])

            self.assertEqual(code, 0)
            manifest = drive / "outbox" / "run-summaries" / "export-unit-test-20260512T000000Z" / "DRIVE_EXPORT_MANIFEST.json"
            self.assertTrue(manifest.exists())
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(data["counts"]["included"], 1)
            copied = manifest.parent / "files" / "docs" / "status.md"
            self.assertTrue(copied.exists())


if __name__ == "__main__":
    unittest.main()

# End of script.
