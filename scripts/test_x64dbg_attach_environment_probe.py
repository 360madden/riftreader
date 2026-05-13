from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from rift_live_test.x64dbg_attach_environment_probe import (
    build_summary,
    evaluate_probe,
    plugin_paths_for_x64dbg,
)


class X64DbgAttachEnvironmentProbeTests(unittest.TestCase):
    def test_plugin_paths_are_derived_from_x64dbg_parent(self) -> None:
        paths = plugin_paths_for_x64dbg(Path(r"C:\Tools\x64dbg\release\x64\x64dbg.exe"))

        self.assertEqual(paths["plugin"], r"C:\Tools\x64dbg\release\x64\plugins\x64dbg-automate.dp64")
        self.assertEqual(paths["libzmq"], r"C:\Tools\x64dbg\release\x64\plugins\libzmq-mt-4_3_5.dll")
        self.assertEqual(paths["alternateLibzmq"], r"C:\Tools\x64dbg\release\x64\libzmq-mt-4_3_5.dll")

    def test_evaluate_probe_blocks_on_missing_required_install_parts(self) -> None:
        summary = {
            "x64dbgInstall": {
                "x64dbgFound": False,
                "pluginFound": False,
                "libzmqFound": False,
                "pythonPackageFound": False,
                "activeSessions": [],
            },
            "currentProcessToken": {"elevated": False, "seDebugPrivilegeEnabled": False},
            "targetToken": {"elevated": False},
            "targetAccessChecks": [{"label": "query-limited", "ok": True}],
            "blockers": [],
            "warnings": [],
        }

        evaluate_probe(summary, require_debug_access=False)

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("x64dbg-exe-not-found", summary["blockers"])
        self.assertIn("x64dbg-automate-plugin-not-found", summary["blockers"])
        self.assertIn("x64dbg-libzmq-not-found", summary["blockers"])
        self.assertIn("x64dbg-automate-python-package-not-found", summary["blockers"])

    def test_evaluate_probe_treats_elevation_mismatch_as_debug_access_blocker(self) -> None:
        summary = {
            "x64dbgInstall": {
                "x64dbgFound": True,
                "pluginFound": True,
                "libzmqFound": True,
                "pythonPackageFound": True,
                "activeSessions": [],
            },
            "currentProcessToken": {"elevated": False, "seDebugPrivilegeEnabled": False},
            "targetToken": {"elevated": True},
            "targetAccessChecks": [
                {"label": "query-limited", "ok": True},
                {"label": "all-access-handle-only", "ok": True},
            ],
            "blockers": [],
            "warnings": [],
        }

        evaluate_probe(summary, require_debug_access=True)

        self.assertEqual(summary["status"], "blocked")
        self.assertIn("target-elevated-but-current-process-not-elevated", summary["blockers"])

    def test_self_test_writes_summary_without_live_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = Namespace(
                repo_root=root,
                output_root=root / "probe",
                x64dbg_path=None,
                process_name="rift_x64",
                title_contains="RIFT",
                target_pid=12345,
                target_hwnd="0xABCDEF",
                expected_start_time_utc="2026-05-13T00:00:00.000000Z",
                start_time_tolerance_seconds=1.0,
                expected_module_base="0x7FF700000000",
                require_exact_target=True,
                require_no_debugger_process=True,
                include_high_access_check=True,
                require_debug_access=True,
                allow_x64dbg_launch_self_check=False,
                self_test=True,
                json=True,
            )

            summary = build_summary(args, root, args.output_root)

        self.assertEqual(summary["selectedTarget"]["pid"], 12345)
        self.assertFalse(summary["safety"]["x64dbgLaunched"])
        self.assertFalse(summary["safety"]["x64dbgLiveAttachStarted"])
        self.assertIn("self-test only; no live process inspection, x64dbg launch, attach, memory read, or input", summary["warnings"])


if __name__ == "__main__":
    unittest.main()
