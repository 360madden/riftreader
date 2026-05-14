from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.repair_rrapicoord_addon_settings import main, parse_addon_settings, replace_or_insert_addon_setting


BASE_SETTINGS = """Addons = {
  ChromaLink = "enabled",
  ReaderBridge = "enabled",
}
SuppressedWarnings = {
}
"""


def write_settings(path: Path, text: str = BASE_SETTINGS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class RepairRrapicoordAddonSettingsTests(unittest.TestCase):
    def test_insert_missing_setting(self) -> None:
        repaired, action = replace_or_insert_addon_setting(BASE_SETTINGS)

        self.assertEqual(action, "inserted:missing->enabled")
        self.assertEqual(parse_addon_settings(repaired)["RiftReaderApiProbe"], "enabled")

    def test_update_disabled_setting(self) -> None:
        repaired, action = replace_or_insert_addon_setting(
            'Addons = {\n  RiftReaderApiProbe = "disabled",\n}\n'
        )

        self.assertEqual(action, "updated:disabled->enabled")
        self.assertEqual(parse_addon_settings(repaired)["RiftReaderApiProbe"], "enabled")

    def test_dry_run_writes_summary_without_modifying_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            addons_root = root / "Interface" / "AddOns"
            addons_root.mkdir(parents=True)
            settings = root / "Interface" / "Saved" / "rift315.1@gmail.com" / "AddonSettings.lua"
            write_settings(settings)
            output = root / "out"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--repo-root",
                        str(root),
                        "--addons-root",
                        str(addons_root),
                        "--output-root",
                        str(output),
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["verdict"], "addon-settings-repair-dry-run")
            self.assertEqual(summary["counts"]["changedCount"], 1)
            self.assertEqual(summary["counts"]["appliedCount"], 0)
            self.assertNotIn("RiftReaderApiProbe", parse_addon_settings(settings.read_text(encoding="utf-8")))
            self.assertFalse(summary["safety"]["addonSettingsWritten"])

    def test_apply_updates_latest_file_and_writes_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            addons_root = root / "Interface" / "AddOns"
            addons_root.mkdir(parents=True)
            old_settings = root / "Interface" / "Saved" / "old" / "AddonSettings.lua"
            latest_settings = root / "Interface" / "Saved" / "rift315.1@gmail.com" / "AddonSettings.lua"
            write_settings(old_settings, 'Addons = {\n}\n')
            write_settings(latest_settings)
            output = root / "out"
            backup = root / "backup"
            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--repo-root",
                        str(root),
                        "--addons-root",
                        str(addons_root),
                        "--output-root",
                        str(output),
                        "--backup-root",
                        str(backup),
                        "--apply",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["verdict"], "addon-settings-repaired")
            self.assertEqual(summary["counts"]["appliedCount"], 1)
            self.assertEqual(parse_addon_settings(latest_settings.read_text(encoding="utf-8"))["RiftReaderApiProbe"], "enabled")
            self.assertNotIn("RiftReaderApiProbe", parse_addon_settings(old_settings.read_text(encoding="utf-8")))
            self.assertTrue(any(backup.glob("*-AddonSettings.lua")))
            self.assertTrue(summary["safety"]["addonSettingsWritten"])


if __name__ == "__main__":
    unittest.main()
