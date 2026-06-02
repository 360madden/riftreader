from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import glyph_forensics_inventory as glyph
from scripts import glyph_health_packet as health
from scripts import glyph_static_focus as focus


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

    def test_config_inventory_parses_xml_and_key_value_with_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml_path = root / "GlyphClient.xml"
            cfg_path = root / "GlyphClient.cfg"
            xml_path.write_text(
                '<Glyph><Auth url="https://auth.example.test" token="secret-token-value" />'
                "<Token>tinyxmlsecret</Token><Patch>http://patch.example.test/live</Patch></Glyph>",
                encoding="utf-8",
            )
            cfg_path.write_text("language=en\nemail=user@example.test\nAuthCode=tinycfgsecret\nlastGame=RIFT\n", encoding="utf-8")

            inventory = glyph.config_inventory(
                [
                    {"path": str(xml_path), "exists": True, "isFile": True, "suffix": ".xml"},
                    {"path": str(cfg_path), "exists": True, "isFile": True, "suffix": ".cfg"},
                ],
                limit_bytes=4096,
                max_items=20,
            )

        self.assertEqual(inventory["fileCount"], 2)
        self.assertEqual(inventory["parserCounts"]["xml"], 1)
        self.assertEqual(inventory["parserCounts"]["line-key-value"], 1)
        rendered = json.dumps(inventory)
        self.assertIn("https://auth.example.test", rendered)
        self.assertNotIn("secret-token-value", rendered)
        self.assertNotIn("tinyxmlsecret", rendered)
        self.assertNotIn("tinycfgsecret", rendered)
        self.assertNotIn("user@example.test", rendered)

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

    def test_log_timeline_summarizes_http_version_and_selection_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "GlyphClient.0.log"
            log_path.write_text(
                "\n".join(
                    [
                        "[2026-06-02T00:00:01Z] Starting task 1 of type GetVersions",
                        "[2026-06-02T00:00:02Z] Received header HTTP 200 from http://patch.example.test/live.txt",
                        "[2026-06-02T00:00:03Z] Successfully downloaded version",
                        "[INF] [ENG] Failed to connect to selection server at [144.217.46.224:6527]",
                        "[WRN] [ENG] Failed to connect to selection server using any address",
                        "[2026-06-02T00:00:04Z] maintenance RSS returned 404 from http://news.example.test/rss.xml",
                    ]
                ),
                encoding="utf-8",
            )

            timeline = glyph.log_timeline([log_path], max_events=10)

        network = timeline["networkSummary"]
        self.assertEqual(network["httpStatusCodeCounts"]["200"], 1)
        self.assertEqual(network["httpStatusCodeCounts"]["404"], 1)
        self.assertEqual(network["taskTypeCounts"]["GetVersions"], 1)
        self.assertGreaterEqual(network["versionEventCount"], 2)
        self.assertEqual(network["selectionEventCount"], 2)
        self.assertEqual(network["maintenanceEventCount"], 1)

    def test_static_focus_groups_strings_by_category_and_function(self) -> None:
        ghidra_summary = {
            "programName": "GlyphClientApp.exe",
            "languageId": "x86:LE:32:default",
            "compilerSpecId": "windows",
            "functionSummary": {"functionCount": 2, "instructionCount": 20},
            "interestingStringSummary": {
                "capturedStringCount": 2,
                "totalReferencesCaptured": 2,
                "categoryReferenceCounts": {"auth": 2},
                "topReferencedFunctionsByCategory": {
                    "auth": [{"functionName": "FUN_AUTH", "functionEntry": "00401000", "count": 2}]
                },
            },
            "interestingStrings": [
                {
                    "address": "00500000",
                    "categories": ["auth", "endpoint"],
                    "value": "https://auth.example.test/login token=secret",
                    "references": [{"from": "00401010", "type": "DATA", "functionEntry": "00401000"}],
                },
                {
                    "address": "00500020",
                    "categories": ["auth"],
                    "value": "AuthCode=tinysecret",
                    "references": [{"from": "00401020", "type": "DATA", "functionEntry": "00401000"}],
                },
            ],
        }

        report = focus.build_focus_report(
            ghidra_summary,
            ghidra_path=Path("ghidra.json"),
            category_limit=1,
            function_limit=1,
            strings_per_function=5,
        )

        auth_function = report["categories"][0]["functions"][0]
        rendered = json.dumps(report)
        self.assertEqual(auth_function["observedReferenceCount"], 2)
        self.assertIn("https://auth.example.test/login", rendered)
        self.assertNotIn("secret", rendered)
        self.assertEqual(report["endpointMentions"][0]["value"], "https://auth.example.test/login")

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
        inventories = [
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
        ]
        summary = glyph.module_origin_summary(inventories, install_roots=[Path(r"C:\Program Files (x86)\Glyph")])

        self.assertEqual(summary["categoryCounts"]["glyph-install"], 1)
        self.assertEqual(summary["categoryCounts"]["windows"], 1)
        self.assertEqual(summary["categoryCounts"]["temp"], 1)
        self.assertEqual(summary["nonWindowsNonGlyphCount"], 1)
        self.assertEqual(len(glyph.unique_loaded_module_paths(inventories)), 3)

    def test_loaded_module_trust_summary_counts_non_valid_by_origin(self) -> None:
        paths = [
            Path(r"C:\Program Files (x86)\Glyph\GlyphClientApp.exe"),
            Path(r"C:\Windows\System32\kernel32.dll"),
            Path(r"C:\Users\mrkoo\AppData\Local\Temp\odd.dll"),
        ]

        summary = glyph.loaded_module_trust_summary(
            paths,
            [
                {"path": str(paths[0]), "signatureStatus": "Valid"},
                {"path": str(paths[1]), "signatureStatus": "Valid"},
                {"path": str(paths[2]), "signatureStatus": "NotSigned"},
            ],
            install_roots=[Path(r"C:\Program Files (x86)\Glyph")],
        )

        self.assertEqual(summary["signatureCheckedCount"], 3)
        self.assertEqual(summary["statusCounts"]["Valid"], 2)
        self.assertEqual(summary["statusCounts"]["NotSigned"], 1)
        self.assertEqual(summary["nonWindowsNonGlyphNonValidCount"], 1)

    def test_health_packet_summarizes_key_fields(self) -> None:
        summary = {
            "generatedAtUtc": "2026-06-02T00:00:00Z",
            "artifacts": {"summaryMarkdown": "summary.md"},
            "processes": [{"Name": "GlyphClientApp.exe", "ProcessId": 1, "ParentProcessId": 2, "ExecutablePath": "GlyphClientApp.exe"}],
            "selectionServerSummary": {"status": "failed-all-addresses", "failureCount": 2, "endpoints": []},
            "executableTrustSummary": {"statusCounts": {"Valid": 1}},
            "dependencyTrustSummary": {"statusCounts": {"NotSigned": 1}, "nonValidCount": 1},
            "configInventory": {
                "fileCount": 2,
                "parserCounts": {"xml": 1, "line-key-value": 1},
                "statusCounts": {"passed": 2},
                "endpointReferenceCount": 3,
                "files": [{"path": "GlyphClient.xml", "parser": "xml", "status": "passed", "rootTag": "Glyph", "endpoints": []}],
            },
            "manifestInventory": [{"status": "passed", "path": "manifest64.txt", "version": "v1", "entryCount": 1}],
            "endpointInventory": [{"value": "glyph.example", "count": 3, "sources": ["a", "b"]}],
            "targetedFileInventory": [{"exists": True}],
            "dependencyMetadata": [{}],
            "logTimeline": {
                "eventCount": 5,
                "categoryCounts": {"download": 1},
                "networkSummary": {
                    "httpEventCount": 1,
                    "versionEventCount": 1,
                    "maintenanceEventCount": 0,
                    "selectionEventCount": 1,
                    "httpStatusCodeCounts": {"200": 1},
                    "httpHostCounts": {"patch.example": 1},
                    "taskTypeCounts": {"GetVersions": 1},
                    "latestHttpEvents": [],
                    "latestVersionEvents": [],
                    "latestMaintenanceEvents": [],
                    "latestSelectionEvents": [],
                },
            },
            "moduleOriginSummary": {"processCount": 1, "totalModuleCount": 3, "categoryCounts": {"windows": 2}, "nonWindowsNonGlyphCount": 0},
            "loadedModuleTrustSummary": {
                "signatureCheckedCount": 3,
                "statusCounts": {"Valid": 3},
                "categoryStatusCounts": {"windows": {"Valid": 3}},
                "nonValidCount": 0,
                "glyphInstallNonValidCount": 0,
                "nonWindowsNonGlyphNonValidCount": 0,
                "nonWindowsNonGlyphNonValidModules": [],
            },
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
        self.assertEqual(packet["logs"]["httpStatusCodeCounts"]["200"], 1)
        self.assertEqual(packet["logs"]["taskTypeCounts"]["GetVersions"], 1)
        self.assertEqual(packet["trust"]["dependencyNonValidSignatureCount"], 1)
        self.assertEqual(packet["config"]["fileCount"], 2)
        self.assertEqual(packet["config"]["parserCounts"]["xml"], 1)
        self.assertEqual(packet["manifests"][0]["version"], "v1")
        self.assertEqual(packet["modules"]["totalModuleCount"], 3)
        self.assertEqual(packet["modules"]["signatureStatusCounts"]["Valid"], 3)
        self.assertEqual(packet["staticReverseEngineering"]["totalReferencesCaptured"], 7)
        self.assertEqual(packet["staticReverseEngineering"]["topReferencedFunctionsByCategory"]["auth"][0]["functionEntry"], "001")


if __name__ == "__main__":
    unittest.main()
