from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import tool_catalog  # noqa: E402


def write(path: Path, text: str = "# test\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_fake_repo(root: Path) -> tuple[Path, Path]:
    repo = root / "repo"
    external = root / "Tools"
    repo.mkdir()
    write(repo / "agents.md")
    for rel in [
        "scripts/riftreader-decision-packet.cmd",
        "scripts/riftreader-workflow-status.cmd",
        "scripts/riftreader-tool-catalog.cmd",
        "scripts/riftreader-policy-lint.cmd",
        "scripts/riftreader-sensitive-artifact-scan.cmd",
        "scripts/riftreader-live-input-surface-audit.cmd",
        "scripts/static-owner-coordinate-chain-readback.cmd",
        "scripts/static-owner-nav-now.cmd",
        "scripts/static-owner-turn-aware-route-plan.cmd",
        "scripts/static-owner-turn-forward-experiment.cmd",
        "scripts/static-owner-nav-route-step.cmd",
        "scripts/static-owner-nav-route-run.cmd",
        "scripts/riftscan_milestone_review.py",
        "tools/riftreader_workflow/opencode_bridge.py",
        "tools/RiftReader.SendInput/Program.cs",
        "tools/RiftReader.WindowTools/Program.cs",
    ]:
        write(repo / rel)
    for rel in [
        "ghidra-headless.bat",
        "ghidra_12.1_PUBLIC/ghidraRun.bat",
        "x64dbg/release/x64/x64dbg.exe",
        "x64dbg/release/x64/headless.exe",
        "SysinternalsSuite/Listdlls64.exe",
        "SysinternalsSuite/handle64.exe",
        "SysinternalsSuite/procdump64.exe",
        "SysinternalsSuite/vmmap64.exe",
    ]:
        write(external / rel, "test\n")
    return repo, external


class ToolCatalogTests(unittest.TestCase):
    def test_catalog_routes_external_tools_by_risk(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo, external = make_fake_repo(Path(temp_dir))

            catalog = tool_catalog.build_tool_catalog(repo, external)

        self.assertEqual(catalog["status"], "passed")
        self.assertIn("ghidra-headless", catalog["canonicalToolKeys"])
        self.assertIn("x64dbg-gui", catalog["gatedToolKeys"])
        self.assertIn("opencode-retired", catalog["retiredToolKeys"])
        self.assertEqual(catalog["lanes"]["ghidraStatic"]["status"], "ready")
        self.assertFalse(catalog["safety"]["inputSent"])

    def test_compact_catalog_contains_workflow_and_static_lane(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo, external = make_fake_repo(Path(temp_dir))

            compact = tool_catalog.build_compact_catalog(tool_catalog.build_tool_catalog(repo, external))

        self.assertEqual(compact["kind"], "riftreader-tool-catalog-compact")
        self.assertEqual(compact["ghidraStaticLane"]["status"], "ready")
        self.assertEqual(compact["inputSurfacePolicyCommand"], ["scripts\\riftreader-live-input-surface-audit.cmd", "--json"])
        self.assertTrue(any(item["step"] == "offline-static-first" for item in compact["recommendedWorkflow"]))
        self.assertTrue(any(item["step"] == "static-chain-readback-before-nav" for item in compact["recommendedWorkflow"]))
        self.assertIn("static-owner-coordinate-chain-readback", compact["canonicalToolKeys"])

    def test_missing_external_tools_warns_without_authorizing_debugger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo, _external = make_fake_repo(Path(temp_dir))
            missing = Path(temp_dir) / "missing-tools"

            catalog = tool_catalog.build_tool_catalog(repo, missing)

        self.assertEqual(catalog["status"], "passed-with-warnings")
        self.assertIn("external-tools-root-missing", catalog["warnings"])
        self.assertIn("x64dbg-gui", catalog["gatedToolKeys"])
        self.assertFalse(catalog["safety"]["x64dbgAttach"])

    def test_ghidra_plan_never_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo, external = make_fake_repo(Path(temp_dir))

            plan = tool_catalog.build_ghidra_static_lane(repo, external)

        self.assertEqual(plan["status"], "ready")
        self.assertFalse(plan["doesRun"])
        self.assertFalse(plan["safety"]["x64dbgAttach"])
        self.assertIn("-import", plan["commandTemplate"])

    def test_cli_self_test_and_compact_json(self) -> None:
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = tool_catalog.main(["--self-test"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])

        with tempfile.TemporaryDirectory() as temp_dir:
            repo, external = make_fake_repo(Path(temp_dir))
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = tool_catalog.main(
                    ["--repo-root", str(repo), "--external-tools-root", str(external), "--compact-json"]
                )
            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["kind"], "riftreader-tool-catalog-compact")


if __name__ == "__main__":
    unittest.main()
