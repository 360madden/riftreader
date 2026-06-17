#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import mcp_server_status  # noqa: E402
from riftreader_workflow.mcp_tool_surface import EXPECTED_CHATGPT_MCP_TOOL_COUNT, EXPECTED_CHATGPT_MCP_TOOL_NAMES  # noqa: E402


def listener(command_line: str, *, pid: int = 1234) -> dict[str, object]:
    return {
        "ok": True,
        "exists": True,
        "host": "127.0.0.1",
        "port": 8770,
        "listeners": [
            {
                "localAddress": "127.0.0.1",
                "localPort": 8770,
                "state": "Listen",
                "owningProcess": pid,
                "processExists": True,
                "processName": "python.exe",
                "executablePath": r"C:\Python\python.exe",
                "commandLine": command_line,
            }
        ],
    }


def runtime_surface(tool_names: list[str] | None = None) -> dict[str, object]:
    names = tool_names or list(EXPECTED_CHATGPT_MCP_TOOL_NAMES)
    return {
        "status": "passed" if names == list(EXPECTED_CHATGPT_MCP_TOOL_NAMES) else "blocked",
        "ok": names == list(EXPECTED_CHATGPT_MCP_TOOL_NAMES),
        "expectedToolCount": EXPECTED_CHATGPT_MCP_TOOL_COUNT,
        "observedToolCount": len(names),
        "expectedToolNames": list(EXPECTED_CHATGPT_MCP_TOOL_NAMES),
        "observedToolNames": names,
        "healthToolCount": len(names),
        "healthToolNames": names,
        "blockers": [] if names == list(EXPECTED_CHATGPT_MCP_TOOL_NAMES) else [f"runtime-tool-count-not-{EXPECTED_CHATGPT_MCP_TOOL_COUNT}:{len(names)}"],
    }


def source_freshness(ok: bool = True) -> dict[str, object]:
    return {
        "status": "passed" if ok else "blocked",
        "ok": ok,
        "processStartedAtUtc": "2026-06-17T11:00:00Z",
        "latestSourcePath": "tools/riftreader_workflow/riftreader_chatgpt_mcp.py",
        "latestSourceMtimeUtc": "2026-06-17T11:05:00Z",
        "staleBySeconds": 300.0,
        "blockers": [] if ok else ["runtime-process-started-before-current-source:tools/riftreader_workflow/riftreader_chatgpt_mcp.py:300.0s"],
    }


def write_runtime_source(root: Path, *, mtime_utc: datetime) -> None:
    source = root / "tools" / "riftreader_workflow" / "riftreader_chatgpt_mcp.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# test source\n", encoding="utf-8")
    os.utime(source, (mtime_utc.timestamp(), mtime_utc.timestamp()))


class McpServerStatusTests(unittest.TestCase):
    def test_runtime_source_freshness_watches_status_helper_itself(self) -> None:
        self.assertIn(
            Path("tools/riftreader_workflow/mcp_server_status.py"),
            mcp_server_status.RUNTIME_SOURCE_PATHS,
        )

    def test_current_full_profile_server_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = mcp_server_status.build_status_payload(
                Path(temp_dir),
                listener_query=listener(
                    r'python "tools\riftreader_workflow\riftreader_chatgpt_mcp.py" --serve '
                    r"--tool-profile full --host 127.0.0.1 --port 8770 --transport streamable-http "
                    r"--allowed-host mcp.360madden.com --allowed-origin https://chatgpt.com"
                ),
                runtime_surface_probe=runtime_surface(),
                runtime_source_freshness_probe=source_freshness(),
            )

        self.assertTrue(payload["ok"])
        self.assertEqual("running-current", payload["status"])
        self.assertEqual("full", payload["selectedListener"]["classification"]["toolProfile"])
        self.assertEqual("passed", payload["runtimeSurface"]["status"])
        self.assertEqual("passed", payload["runtimeSourceFreshness"]["status"])
        self.assertEqual([], payload["blockers"])

    def test_current_command_line_with_stale_runtime_surface_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = mcp_server_status.build_status_payload(
                Path(temp_dir),
                listener_query=listener(
                    r'python "tools\riftreader_workflow\riftreader_chatgpt_mcp.py" --serve '
                    r"--tool-profile full --host 127.0.0.1 --port 8770 --transport streamable-http "
                    r"--allowed-host mcp.360madden.com --allowed-origin https://chatgpt.com"
                ),
                runtime_surface_probe=runtime_surface(list(EXPECTED_CHATGPT_MCP_TOOL_NAMES)[:-2]),
                runtime_source_freshness_probe=source_freshness(),
            )

        self.assertFalse(payload["ok"])
        self.assertEqual("running-stale-runtime", payload["status"])
        self.assertIn("current-chatgpt-mcp-server-runtime-surface-not-current", payload["blockers"])
        self.assertEqual("blocked", payload["runtimeSurface"]["status"])

    def test_current_surface_with_stale_process_start_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = mcp_server_status.build_status_payload(
                Path(temp_dir),
                listener_query=listener(
                    r'python "tools\riftreader_workflow\riftreader_chatgpt_mcp.py" --serve '
                    r"--tool-profile full --host 127.0.0.1 --port 8770 --transport streamable-http "
                    r"--allowed-host mcp.360madden.com --allowed-origin https://chatgpt.com"
                ),
                runtime_surface_probe=runtime_surface(),
                runtime_source_freshness_probe=source_freshness(False),
            )

        self.assertFalse(payload["ok"])
        self.assertEqual("running-stale-runtime", payload["status"])
        self.assertIn("current-chatgpt-mcp-server-started-before-current-source", payload["blockers"])
        self.assertEqual("blocked", payload["runtimeSourceFreshness"]["status"])

    def test_missing_listener_blocks_with_clear_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = mcp_server_status.build_status_payload(
                Path(temp_dir),
                listener_query={"ok": True, "exists": False, "listeners": []},
            )

        self.assertFalse(payload["ok"])
        self.assertEqual("not-running", payload["status"])
        self.assertIn("local-backend-not-running:127.0.0.1:8770", payload["blockers"])
        self.assertEqual("saved-chatgpt-connector-config-does-not-start-local-backend", payload["operatorRule"])

    def test_foreign_listener_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = mcp_server_status.build_status_payload(
                Path(temp_dir),
                listener_query=listener(r"C:\OtherApp\python.exe unrelated_server.py --port 8770"),
            )

        self.assertFalse(payload["ok"])
        self.assertEqual("foreign-listener", payload["status"])
        self.assertIn("local-backend-port-foreign-listener:8770", payload["blockers"])

    def test_legacy_listener_does_not_satisfy_current_chatgpt_lane(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = mcp_server_status.build_status_payload(
                Path(temp_dir),
                listener_query=listener(r"python -m tools.riftreader_mcp.http_server --repo . --json"),
            )

        self.assertFalse(payload["ok"])
        self.assertEqual("running-legacy", payload["status"])
        self.assertIn("current-chatgpt-mcp-server-not-running:legacy-server-listening", payload["blockers"])

    def test_stale_stdio_counterpart_warns_without_blocking_http_lane(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_runtime_source(root, mtime_utc=datetime(2026, 6, 17, 11, 0, tzinfo=timezone.utc))
            payload = mcp_server_status.build_status_payload(
                root,
                listener_query=listener(
                    r'python "tools\riftreader_workflow\riftreader_chatgpt_mcp.py" --serve '
                    r"--tool-profile full --host 127.0.0.1 --port 8770 --transport streamable-http "
                    r"--allowed-host mcp.360madden.com --allowed-origin https://chatgpt.com"
                ),
                runtime_surface_probe=runtime_surface(),
                runtime_source_freshness_probe=source_freshness(),
                stdio_counterpart_query={
                    "ok": True,
                    "processes": [
                        {
                            "processId": 999,
                            "parentProcessId": 100,
                            "processExists": True,
                            "processName": "python.exe",
                            "executablePath": r"C:\Python\python.exe",
                            "creationDate": "2026-06-17T10:00:00+00:00",
                            "commandLine": (
                                r'python "tools\riftreader_workflow\riftreader_chatgpt_mcp.py" '
                                r'--serve --transport stdio --repo-root "C:\RIFT MODDING\RiftReader"'
                            ),
                        }
                    ],
                },
            )

        self.assertTrue(payload["ok"])
        self.assertEqual("running-current", payload["status"])
        self.assertEqual("stale-running", payload["stdioCounterparts"]["status"])
        self.assertEqual([999], payload["stdioCounterparts"]["staleProcessIds"])
        self.assertIn("codex-stdio-counterpart-stale:999", payload["warnings"])
        by_key = {item["key"]: item for item in payload["dependencySequence"]}
        self.assertEqual("warning", by_key["codex-stdio-counterparts"]["status"])


if __name__ == "__main__":
    unittest.main()
