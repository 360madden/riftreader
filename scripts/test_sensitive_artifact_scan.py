from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from rift_live_test.sensitive_artifact_scan import build_scan_summary, scan_text


def args(**overrides: object) -> argparse.Namespace:
    defaults = {
        "path": [],
        "staged": False,
        "working": True,
        "write": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class SensitiveArtifactScanTests(unittest.TestCase):
    def test_scan_text_reports_without_line_preview(self) -> None:
        secret = "REAL" + "SECRET123"
        auth_value = "abc" + "123456789"
        line = "rift_x64.exe -k " + secret + " --auth" + "api=" + auth_value + "\n"
        findings = scan_text("sample.txt", line)

        self.assertEqual(len(findings), 2)
        self.assertFalse(findings[0]["linePreviewStored"])
        self.assertNotIn("REALSECRET123", str(findings))
        self.assertNotIn("abc123456789", str(findings))

    def test_scan_text_allows_redacted_placeholders(self) -> None:
        findings = scan_text("sample.txt", "rift_x64.exe -k <redacted> --authapi=<redacted> --token=$TOKEN\n")

        self.assertEqual(findings, [])

    def test_explicit_path_scan_writes_ignored_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "safe.txt").write_text("GlyphClientApp.exe -hidden\n", encoding="utf-8")
            summary = build_scan_summary(root, args(path=["safe.txt"], write=True), output_root=root / ".out")

            self.assertEqual(summary["status"], "passed")
            self.assertFalse(summary["containsSensitiveData"])
            self.assertTrue((root / summary["artifacts"]["summaryJson"]).is_file())


if __name__ == "__main__":
    unittest.main()
