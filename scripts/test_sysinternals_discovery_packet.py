import unittest

from scripts.sysinternals_discovery_packet import (
    compare_expected_module_base,
    parse_handle_output,
    parse_listdlls_output,
)


class SysinternalsDiscoveryPacketTests(unittest.TestCase):
    def test_parse_listdlls_extracts_rift_module(self):
        text = """
        0x00007ff77af40000  C:\\Program Files (x86)\\Glyph\\Games\\RIFT\\Live\\rift_x64.exe
        0x00007ffb12340000  C:\\Windows\\System32\\kernel32.dll
        """
        parsed = parse_listdlls_output(text)
        self.assertEqual(parsed["moduleCount"], 2)
        self.assertEqual(parsed["riftModuleCount"], 1)
        self.assertEqual(parsed["riftModules"][0]["baseAddress"], "0x00007ff77af40000")

    def test_parse_handle_flags_debug_lines(self):
        text = """
        rift_x64.exe pid: 12148
          10: DebugObject    \\BaseNamedObjects\\ExampleDebug
          20: Process        rift_x64.exe pid: 12148
          30: File           C:\\temp\\not-interesting.txt
        """
        parsed = parse_handle_output(text, 12148)
        self.assertEqual(parsed["debugLineCount"], 1)
        self.assertEqual(parsed["processLineCount"], 1)
        self.assertIn("DebugObject", parsed["debugLines"][0])

    def test_compare_expected_module_base_detects_low32_truncation(self):
        parsed = {
            "riftModules": [
                {
                    "baseAddress": "0x000000007af40000",
                }
            ]
        }
        result = compare_expected_module_base(parsed, "0x7FF77AF40000")
        self.assertEqual(result["status"], "low32-match-listdlls-address-truncated")


if __name__ == "__main__":
    unittest.main()
