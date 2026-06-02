from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import glyph_forensics_inventory as glyph


class GlyphForensicsInventoryTests(unittest.TestCase):
    def test_redact_text_masks_sensitive_assignments_and_email(self) -> None:
        text = 'email="person@example.com"\ntoken=abcdef0123456789\nnormal=value\nAuthorization: Bearer abcdef0123456789'

        redacted = glyph.redact_text(text)

        self.assertNotIn("person@example.com", redacted)
        self.assertNotIn("abcdef0123456789", redacted)
        self.assertIn("normal=value", redacted)
        self.assertIn("email=<redacted>", redacted)
        self.assertIn("token=<redacted>", redacted)

    def test_extract_ascii_strings_finds_urls_without_sensitive_dump(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "GlyphClientApp.exe"
            path.write_bytes(
                b"\x00\x01https://glyph.example.com/patch\x00"
                b"Authorization: Bearer abcdef0123456789\x00"
                b"HKEY_CURRENT_USER\\Software\\Glyph\x00"
            )

            result = glyph.extract_ascii_strings(path, max_hits=10)

        self.assertEqual(result["status"], "passed")
        joined = "\n".join(result["interestingStrings"])
        self.assertIn("https://glyph.example.com/patch", joined)
        self.assertIn("HKEY_CURRENT_USER\\Software\\Glyph", joined)
        self.assertNotIn("abcdef0123456789", joined)

    def test_file_metadata_hashes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.exe"
            path.write_bytes(b"abc")

            metadata = glyph.file_metadata(path, hash_file=True)

        self.assertTrue(metadata["exists"])
        self.assertEqual(metadata["sha256"], "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


if __name__ == "__main__":
    unittest.main()
