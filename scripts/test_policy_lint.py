# Version: riftreader-policy-lint-tests-v0.1.2
# Total-Character-Count: 4499
# Purpose: Unit tests for the Python-owned RiftReader scoped policy lint helper.

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.riftreader_workflow import policy_lint as pl

class PolicyLintTests(unittest.TestCase):
    def test_normalize_path_rejects_traversal(self) -> None:
        with self.assertRaises(pl.PolicyLintError):
            pl.normalize_repo_path("../bad")

    def test_trailing_whitespace_detection(self) -> None:
        self.assertTrue(pl.has_trailing_whitespace("x  \n"))
        self.assertFalse(pl.has_trailing_whitespace("x\n"))

    def test_git_add_dot_detection(self) -> None:
        findings = pl.lint_no_git_add_dot("scripts/bad.ps1", "git add .\n")
        self.assertEqual(findings[0].rule, "no_git_add_dot")

    def test_thin_cmd_detection(self) -> None:
        text = '@echo off\npython "tools\\riftreader_workflow\\x.py" %*\ngit status\n'
        findings = pl.lint_thin_cmd("scripts/riftreader-x.cmd", text)
        self.assertTrue(any(f.rule == "thin_cmd_wrapper" for f in findings))

    def test_library_module_not_forced_to_cli(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "tools/riftreader_workflow").mkdir(parents=True)
            rel = "tools/riftreader_workflow/common.py"
            text = "class CommonError(RuntimeError): pass\n" + ("VALUE = 1\n" * 150)
            findings = pl.lint_python_helper(rel, text, root)
            rules = {f.rule for f in findings}
            self.assertNotIn("python_main_entrypoint", rules)
            self.assertNotIn("python_argparse_cli", rules)

    def test_cli_helper_size_rules(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "tools/riftreader_workflow").mkdir(parents=True)
            rel = "tools/riftreader_workflow/bad.py"
            text = "TOOL_VERSION = 'x'\n# --json\nprint('x')\n" + ("# filler\n" * 180)
            findings = pl.lint_python_helper(rel, text, root)
            rules = {f.rule for f in findings}
            self.assertIn("python_main_entrypoint", rules)
            self.assertIn("python_error_handling", rules)

    def test_changed_scope_ignores_clean_legacy_file(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Tests"], cwd=root, check=True)
            legacy = root / "docs/workflow/legacy.md"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("legacy  \n", encoding="utf-8")
            subprocess.run(["git", "add", "docs/workflow/legacy.md"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "legacy"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            changed = root / "docs/workflow/new.md"
            changed.write_text("new\n", encoding="utf-8")
            report = pl.run_lint(root, "validate-repo", "changed", pl.DEFAULT_SCAN_ROOTS, False)
            self.assertTrue(report["ok"])
            self.assertEqual(report["checkedFiles"], 1)

    def test_self_test_ok(self) -> None:
        report = pl.command_self_test(type("Args", (), {})())
        self.assertTrue(report["ok"])
        self.assertGreaterEqual(report["checkCount"], 5)

    def test_validate_paths_missing_file_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            args = type("Args", (), {"repo_root": str(root), "paths": ["missing.py"], "roots": list(pl.DEFAULT_SCAN_ROOTS), "no_write_summary": True})()
            report = pl.command_validate_paths(args)
            self.assertFalse(report["ok"])
            self.assertEqual(report["blockerCount"], 1)

if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
