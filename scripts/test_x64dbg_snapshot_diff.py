from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.x64dbg_snapshot_diff import (
    BLOCKED_OPERATIONS,
    build_synthetic_snapshots,
    diff_snapshots,
    main,
)


class X64DbgSnapshotDiffTests(unittest.TestCase):
    def test_diff_detects_synthetic_register_and_memory_changes(self) -> None:
        before, after = build_synthetic_snapshots()
        diff = diff_snapshots(before, after)

        self.assertIn("registers", diff["changedSections"])
        self.assertIn("memoryReads", diff["changedSections"])
        self.assertGreaterEqual(diff["counts"]["registerChanges"], 1)
        self.assertEqual(diff["counts"]["memoryReadChanges"], 1)

    def test_self_test_writes_summary_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "self-test"
            with redirect_stdout(StringIO()):
                code = main(["--self-test", "--output-root", str(out), "--json"])

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "passed")
            self.assertTrue(summary["safety"]["offlineOnly"])
            self.assertFalse(summary["safety"]["movementSent"])
            self.assertFalse(summary["safety"]["codexMcpConfigured"])
            self.assertFalse(summary["safety"]["x64dbgLiveAttachStarted"])
            self.assertTrue((out / "snapshot-before.json").is_file())
            self.assertTrue((out / "snapshot-after.json").is_file())
            self.assertTrue((out / "snapshot-diff.json").is_file())
            self.assertTrue((out / "summary.md").is_file())

    def test_connect_session_blocks_without_required_target_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "blocked"
            with redirect_stdout(StringIO()):
                code = main(["--connect-session", "12345", "--output-root", str(out), "--json"])

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("missing-process-name", summary["blockers"])
            self.assertIn("missing-target-pid", summary["blockers"])
            self.assertIn("missing-target-hwnd", summary["blockers"])
            self.assertIn("missing-process-start-time-utc", summary["blockers"])

    def test_rift_connect_session_requires_live_debugger_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "rift-blocked"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--connect-session",
                        "12345",
                        "--process-name",
                        "rift_x64",
                        "--target-pid",
                        "999",
                        "--target-hwnd",
                        "0x123",
                        "--process-start-time-utc",
                        "2026-05-12T00:00:00Z",
                        "--output-root",
                        str(out),
                        "--json",
                    ]
                )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("rift-live-debugger-not-authorized-current-turn", summary["blockers"])

    def test_blocked_operations_include_write_and_execution_classes(self) -> None:
        blocked = set(BLOCKED_OPERATIONS)

        self.assertIn("write_memory", blocked)
        self.assertIn("assemble_at", blocked)
        self.assertIn("set_reg", blocked)
        self.assertIn("go", blocked)
        self.assertIn("cmd_sync", blocked)
        self.assertIn("start_session_attach", blocked)


if __name__ == "__main__":
    unittest.main()
