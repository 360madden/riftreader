from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.rrapicoord_addon_state_diagnostics import build_summary, main


MAIN_LUA = """
RiftReaderApiProbe_Live = RiftReaderApiProbe_Live or "RRAPICOORD1|status=starting|savedVariablesUse=none"
local function refreshLiveApiCoord(force) return force end
local function formatLivePayload()
  return table.concat({"RRAPICOORD1", "schema=1", "source=rift-api", "view=Inspect.Unit.Detail(player)", "savedVariablesUse=none"}, "|")
end
table.insert(Command.Slash.Register("rap"), { function() end, "RiftReaderApiProbe", "RiftReaderApiProbe slash command" })
table.insert(Event.Addon.Startup.End, { function() refreshLiveApiCoord(true) end, "RiftReaderApiProbe", "startup" })
table.insert(Event.System.Update.Begin, { function() refreshLiveApiCoord(false) end, "RiftReaderApiProbe", "update" })
"""

TOC = """
Identifier = "RiftReaderApiProbe"
Description = "Live coordinates without SavedVariables."
RunOnStartup = {
  "main.lua",
}
"""


def write_addon(root: Path, *, mutate_main: bool = False) -> Path:
    addon = root / "RiftReaderApiProbe"
    addon.mkdir(parents=True)
    (addon / "main.lua").write_text(MAIN_LUA + ("-- changed\n" if mutate_main else ""), encoding="utf-8")
    (addon / "RiftAddon.toc").write_text(TOC, encoding="utf-8")
    (addon / "README.md").write_text("# test\n", encoding="utf-8")
    return addon


def write_scan_diagnostic(path: Path, *, usable: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "passed" if usable else "blocked",
                "verdict": "rrapicoord-usable-marker-present" if usable else "blocked-rrapicoord-no-usable-marker",
                "generatedAtUtc": "2999-01-01T00:00:00Z",
                "counts": {
                    "scanFileCount": 1,
                    "loadedHitCount": 1,
                    "rrapicoordTextHitCount": 1,
                    "markerLikeCount": usable,
                    "usableMarkerCount": usable,
                    "sourceTextHitCount": 1 if not usable else 0,
                },
                "inferredCauses": ["scan-is-hitting-addon-source/static/error-context"] if not usable else [],
                "blockers": ["rrapicoord-no-usable-marker"] if not usable else [],
            }
        ),
        encoding="utf-8",
    )


def write_addon_settings(path: Path, *, status: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = ['  ChromaLink = "enabled",']
    if status is not None:
        entries.append(f'  RiftReaderApiProbe = "{status}",')
    path.write_text("Addons = {\n" + "\n".join(entries) + "\n}\n", encoding="utf-8")


class RrapicoordAddonStateDiagnosticsTests(unittest.TestCase):
    def test_matching_install_but_no_live_marker_blocks_with_runtime_cause(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            addons_root = root / "addons"
            write_addon(repo / "addon")
            write_addon(addons_root)
            write_addon_settings(root / "Saved" / "account" / "AddonSettings.lua", status="enabled")
            scan = root / "scan" / "summary.json"
            output = root / "out"
            write_scan_diagnostic(scan, usable=0)

            with redirect_stdout(StringIO()):
                code = main(
                    [
                        "--repo-root",
                        str(repo),
                        "--addons-root",
                        str(addons_root),
                        "--rrapicoord-scan-diagnostic",
                        str(scan),
                        "--output-root",
                        str(output),
                        "--json",
                    ]
                )

            self.assertEqual(code, 2)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "blocked")
            self.assertIn("current-scan-has-no-usable-rrapicoord-live-marker", summary["blockers"])
            self.assertIn("installed-source-is-present-but-runtime-live-marker-is-not-observed", summary["inferredCauses"])
            self.assertTrue(summary["installedCopies"][0]["requiredFilesMatchRepo"])
            self.assertTrue(summary["addonSettings"][0]["addonEnabled"])
            self.assertFalse(summary["safety"]["addonFilesWritten"])
            self.assertFalse(summary["safety"]["inputSent"])

    def test_mismatched_install_blocks_even_with_live_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            addons_root = root / "addons"
            write_addon(repo / "addon")
            write_addon(addons_root, mutate_main=True)
            write_addon_settings(root / "Saved" / "account" / "AddonSettings.lua", status="enabled")
            scan = root / "scan" / "summary.json"
            output = root / "out"
            write_scan_diagnostic(scan, usable=1)

            summary = build_summary(
                type(
                    "Args",
                    (),
                    {
                        "repo_root": repo,
                        "output_root": output,
                        "addons_root": [addons_root],
                        "rrapicoord_scan_diagnostic": scan,
                        "target_pid": None,
                        "process_name": "rift_x64",
                        "json": False,
                    },
                )()
            )

            self.assertEqual(summary["status"], "blocked")
            self.assertIn("installed-addon-not-found-or-does-not-match-repo", summary["blockers"])
            self.assertFalse(summary["installedCopies"][0]["requiredFilesMatchRepo"])

    def test_missing_addon_settings_entry_blocks_as_not_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            addons_root = root / "addons"
            write_addon(repo / "addon")
            write_addon(addons_root)
            write_addon_settings(root / "Saved" / "account" / "AddonSettings.lua", status=None)
            scan = root / "scan" / "summary.json"
            output = root / "out"
            write_scan_diagnostic(scan, usable=0)

            summary = build_summary(
                type(
                    "Args",
                    (),
                    {
                        "repo_root": repo,
                        "output_root": output,
                        "addons_root": [addons_root],
                        "rrapicoord_scan_diagnostic": scan,
                        "target_pid": None,
                        "process_name": "rift_x64",
                        "json": False,
                    },
                )()
            )

            self.assertEqual(summary["status"], "blocked")
            self.assertIn("addon-installed-but-not-enabled-in-account-addon-settings", summary["inferredCauses"])
            self.assertTrue(any(str(blocker).startswith("addon-settings-not-enabled:RiftReaderApiProbe") for blocker in summary["blockers"]))
            self.assertEqual(summary["addonSettings"][0]["addonStatus"], "missing")

    def test_matching_install_and_live_marker_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            addons_root = root / "addons"
            write_addon(repo / "addon")
            write_addon(addons_root)
            write_addon_settings(root / "Saved" / "account" / "AddonSettings.lua", status="enabled")
            scan = root / "scan" / "summary.json"
            output = root / "out"
            write_scan_diagnostic(scan, usable=1)

            summary = build_summary(
                type(
                    "Args",
                    (),
                    {
                        "repo_root": repo,
                        "output_root": output,
                        "addons_root": [addons_root],
                        "rrapicoord_scan_diagnostic": scan,
                        "target_pid": None,
                        "process_name": "rift_x64",
                        "json": False,
                    },
                )()
            )

            self.assertEqual(summary["status"], "passed")
            self.assertEqual(summary["verdict"], "addon-installed-and-live-marker-observed")


if __name__ == "__main__":
    unittest.main()
