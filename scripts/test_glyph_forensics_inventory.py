from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import glyph_forensics_inventory as glyph
from scripts import glyph_health_packet as health


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

    def test_parse_pe_metadata_marks_non_pe_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "not-pe.exe"
            path.write_bytes(b"not a portable executable")

            metadata = glyph.parse_pe_metadata(path)

        self.assertEqual(metadata["status"], "not-pe")

    def test_endpoint_inventory_skips_email_domains(self) -> None:
        endpoints = glyph.endpoint_inventory(
            [{"path": "x.cfg", "preview": "support https://support.gamigo.com user person@gmail.com encoded 40gmail.com"}]
        )
        values = {item["value"] for item in endpoints}

        self.assertIn("https://support.gamigo.com", values)
        self.assertNotIn("gmail.com", values)
        self.assertNotIn("40gmail.com", values)

    def test_selection_server_summary_detects_failed_all_addresses(self) -> None:
        timeline = {
            "latestEvents": [
                {
                    "timestamp": "INF",
                    "category": "error",
                    "message": "[ENG] Failed to connect to selection server at [144.217.46.224:6527]",
                },
                {
                    "timestamp": "WRN",
                    "category": "error",
                    "message": "[ENG] Failed to connect to selection server using any address",
                },
            ]
        }

        summary = glyph.selection_server_summary(timeline)

        self.assertEqual(summary["status"], "failed-all-addresses")
        self.assertEqual(summary["failureCount"], 2)
        self.assertEqual(summary["endpoints"][0]["endpoint"], "144.217.46.224:6527")

    def test_signature_trust_summary_counts_non_valid(self) -> None:
        summary = glyph.signature_trust_summary(
            [
                {"path": "a.exe", "signatureStatus": "Valid", "signerCertificateSubject": "CN=A"},
                {"path": "b.exe", "signatureStatus": "NotSigned", "signerCertificateSubject": None},
            ]
        )

        self.assertEqual(summary["statusCounts"]["Valid"], 1)
        self.assertEqual(summary["statusCounts"]["NotSigned"], 1)
        self.assertEqual(summary["nonValidCount"], 1)

    def test_module_origin_summary_flags_non_windows_non_glyph_modules(self) -> None:
        summary = glyph.module_origin_summary(
            [
                {
                    "pid": 10,
                    "moduleCount": 3,
                    "truncated": False,
                    "modules": [
                        {"ModuleName": "GlyphClientApp.exe", "FileName": r"C:\Program Files (x86)\Glyph\GlyphClientApp.exe"},
                        {"ModuleName": "kernel32.dll", "FileName": r"C:\Windows\System32\kernel32.dll"},
                        {"ModuleName": "odd.dll", "FileName": r"C:\Users\mrkoo\AppData\Local\Temp\odd.dll"},
                    ],
                }
            ],
            install_roots=[Path(r"C:\Program Files (x86)\Glyph")],
        )

        self.assertEqual(summary["categoryCounts"]["glyph-install"], 1)
        self.assertEqual(summary["categoryCounts"]["windows"], 1)
        self.assertEqual(summary["categoryCounts"]["temp"], 1)
        self.assertEqual(summary["nonWindowsNonGlyphCount"], 1)

    def test_health_packet_summarizes_key_fields(self) -> None:
        summary = {
            "generatedAtUtc": "2026-06-02T00:00:00Z",
            "artifacts": {"summaryMarkdown": "summary.md"},
            "processes": [{"Name": "GlyphClientApp.exe", "ProcessId": 1, "ParentProcessId": 2, "ExecutablePath": "GlyphClientApp.exe"}],
            "selectionServerSummary": {"status": "failed-all-addresses", "failureCount": 2, "endpoints": []},
            "executableTrustSummary": {"statusCounts": {"Valid": 1}},
            "dependencyTrustSummary": {"statusCounts": {"NotSigned": 1}, "nonValidCount": 1},
            "manifestInventory": [{"status": "passed", "path": "manifest64.txt", "version": "v1", "entryCount": 1}],
            "endpointInventory": [{"value": "glyph.example", "count": 3, "sources": ["a", "b"]}],
            "targetedFileInventory": [{"exists": True}],
            "dependencyMetadata": [{}],
            "logTimeline": {"eventCount": 5},
            "moduleOriginSummary": {"processCount": 1, "totalModuleCount": 3, "categoryCounts": {"windows": 2}, "nonWindowsNonGlyphCount": 0},
        }
        ghidra_summary = {
            "programName": "GlyphClientApp.exe",
            "languageId": "x86:LE:32:default",
            "compilerSpecId": "windows",
            "functionSummary": {"functionCount": 10, "instructionCount": 99},
            "interestingStringSummary": {
                "capturedStringCount": 4,
                "scannedStringDataCount": 5,
                "totalReferencesCaptured": 7,
                "categoryCounts": {"auth": 2},
                "categoryReferenceCounts": {"auth": 7},
                "topReferencedFunctionsByCategory": {
                    "auth": [{"functionName": "FUN_1", "functionEntry": "001", "count": 7}]
                },
            },
        }

        packet = health.build_health_packet(
            summary,
            summary_path=Path("summary.json"),
            endpoint_limit=1,
            ghidra_summary=ghidra_summary,
            ghidra_path=Path("ghidra.json"),
        )

        self.assertEqual(packet["network"]["selectionServerStatus"], "failed-all-addresses")
        self.assertEqual(packet["trust"]["dependencyNonValidSignatureCount"], 1)
        self.assertEqual(packet["manifests"][0]["version"], "v1")
        self.assertEqual(packet["modules"]["totalModuleCount"], 3)
        self.assertEqual(packet["staticReverseEngineering"]["totalReferencesCaptured"], 7)
        self.assertEqual(packet["staticReverseEngineering"]["topReferencedFunctionsByCategory"]["auth"][0]["functionEntry"], "001")


if __name__ == "__main__":
    unittest.main()
