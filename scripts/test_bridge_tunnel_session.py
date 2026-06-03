# Version: riftreader-test-bridge-tunnel-session-v0.2.1
# Total-Character-Count: 1445
# Purpose: Unit tests for the RiftReader bridge_tunnel_session helper, including path-with-spaces subprocess validation.
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "riftreader_workflow"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import bridge_tunnel_session as helper  # noqa: E402


class BridgeTunnelSessionTests(unittest.TestCase):
    def test_trycloudflare_regex(self) -> None:
        text = "Visit it at: https://devices-example.trycloudflare.com"
        self.assertEqual(helper.detect_tunnel_url_from_text(text), "https://devices-example.trycloudflare.com")

    def test_netstat_parser(self) -> None:
        text = "  TCP    127.0.0.1:8765    0.0.0.0:0    LISTENING    12345"
        self.assertEqual(helper.listening_pids_from_netstat(text, 8765), [12345])

    def test_self_test_passes(self) -> None:
        self.assertEqual(helper.self_test(), 0)

    def test_synthetic_path_with_spaces(self) -> None:
        result = helper.synthetic_path_with_spaces_test()
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["scriptPathHadSpaces"])
        self.assertIn("--preflight", result["argv"])


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
