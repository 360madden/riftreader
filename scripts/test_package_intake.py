#!/usr/bin/env python3

from __future__ import annotations

import json
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import apply_package, package_manifest  # noqa: E402


def make_repo(root: Path) -> None:
    (root / ".git").mkdir()
    (root / "agents.md").write_text("# policy\n", encoding="utf-8")


def make_package(package_root: Path, target: str, content: str, *, checks: list[dict] | None = None) -> Path:
    source = package_root / "files" / "payload.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(content, encoding="utf-8")
    manifest = {
        "schemaVersion": 1,
        "packageName": "test-package",
        "files": [
            {
                "source": "files/payload.txt",
                "target": target,
                "sha256": package_manifest.sha256_file(source),
            }
        ],
        "checks": checks if checks is not None else [],
    }
    (package_root / package_manifest.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    return package_root


class PackageIntakeTests(unittest.TestCase):
    def test_validate_manifest_rejects_checksum_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            package_root = Path(temp_dir) / "package"
            root.mkdir()
            package_root.mkdir()
            make_repo(root)
            make_package(package_root, "docs/test.md", "hello")
            manifest = package_manifest.load_manifest(package_root)
            manifest["files"][0]["sha256"] = "0" * 64

            result = package_manifest.validate_manifest(package_root, root, manifest)

        self.assertTrue(any("sha256-mismatch" in item for item in result["errors"]))

    def test_validate_manifest_rejects_denied_target_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            package_root = Path(temp_dir) / "package"
            root.mkdir()
            package_root.mkdir()
            make_repo(root)
            make_package(package_root, ".git/config", "bad")

            result = package_manifest.validate_manifest(package_root, root, package_manifest.load_manifest(package_root))

        self.assertTrue(any("target-denied-prefix" in item for item in result["errors"]))

    def test_dry_run_does_not_modify_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            package_root = Path(temp_dir) / "package"
            intake_dir = root / ".riftreader-local" / "package-intake" / "test"
            root.mkdir()
            package_root.mkdir()
            make_repo(root)
            target = root / "docs" / "test.md"
            target.parent.mkdir(parents=True)
            target.write_text("old\n", encoding="utf-8")
            make_package(package_root, "docs/test.md", "new\n")
            intake_dir.mkdir(parents=True)

            summary = apply_package.build_summary(
                root,
                package_root,
                intake_dir,
                apply_requested=False,
                run_declared_checks=True,
            )

            self.assertEqual(summary["status"], "passed")
            self.assertTrue(summary["dryRun"])
            self.assertEqual(target.read_text(encoding="utf-8"), "old\n")
            self.assertIsNotNone(summary["artifacts"]["diff"])
            diff_text = (root / summary["artifacts"]["diff"]).read_text(encoding="utf-8")
            self.assertIn("-old", diff_text)
            self.assertIn("+new", diff_text)
            self.assertFalse(summary["safety"]["gitMutation"])

    def test_dry_run_runs_declared_checks_in_overlay_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            package_root = Path(temp_dir) / "package"
            intake_dir = root / ".riftreader-local" / "package-intake" / "test"
            root.mkdir()
            package_root.mkdir()
            make_repo(root)
            target = root / "docs" / "test.md"
            target.parent.mkdir(parents=True)
            target.write_text("old\n", encoding="utf-8")
            checks = [
                {
                    "name": "sees-overlay-file",
                    "args": [
                        sys.executable,
                        "-c",
                        (
                            "from pathlib import Path; "
                            "raise SystemExit("
                            "0 if Path('docs/test.md').read_text(encoding='utf-8') == 'new\\n' else 7"
                            ")"
                        ),
                    ],
                }
            ]
            make_package(package_root, "docs/test.md", "new\n", checks=checks)
            intake_dir.mkdir(parents=True)

            summary = apply_package.build_summary(
                root,
                package_root,
                intake_dir,
                apply_requested=False,
                run_declared_checks=True,
            )

            self.assertEqual(summary["status"], "passed")
            self.assertTrue(summary["dryRun"])
            self.assertEqual(target.read_text(encoding="utf-8"), "old\n")
            self.assertEqual(len(summary["declaredChecks"]), 1)
            self.assertEqual(len(summary["checks"]), 1)
            self.assertTrue(summary["checks"][0]["ok"])
            self.assertIn("dry-run-workspaces", summary["checks"][0]["cwd"])

    def test_dry_run_blocks_when_declared_check_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            package_root = Path(temp_dir) / "package"
            intake_dir = root / ".riftreader-local" / "package-intake" / "test"
            root.mkdir()
            package_root.mkdir()
            make_repo(root)
            target = root / "docs" / "test.md"
            target.parent.mkdir(parents=True)
            target.write_text("old\n", encoding="utf-8")
            checks = [{"name": "fail", "args": [sys.executable, "-c", "raise SystemExit(7)"]}]
            make_package(package_root, "docs/test.md", "new\n", checks=checks)
            intake_dir.mkdir(parents=True)

            summary = apply_package.build_summary(
                root,
                package_root,
                intake_dir,
                apply_requested=False,
                run_declared_checks=True,
            )

            self.assertEqual(summary["status"], "blocked")
            self.assertTrue(summary["dryRun"])
            self.assertEqual(target.read_text(encoding="utf-8"), "old\n")
            self.assertEqual(len(summary["checks"]), 1)
            self.assertFalse(summary["checks"][0]["ok"])
            self.assertIn("check-failed:fail:7", summary["blockers"])

    def test_compact_summary_preserves_apply_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            package_root = Path(temp_dir) / "package"
            intake_dir = root / ".riftreader-local" / "package-intake" / "test"
            root.mkdir()
            package_root.mkdir()
            make_repo(root)
            target = root / "docs" / "test.md"
            target.parent.mkdir(parents=True)
            target.write_text("old\n", encoding="utf-8")
            make_package(package_root, "docs/test.md", "new\n")
            intake_dir.mkdir(parents=True)

            summary = apply_package.build_summary(
                root,
                package_root,
                intake_dir,
                apply_requested=False,
                run_declared_checks=True,
            )
            compact = apply_package.compact_summary(summary)

            self.assertEqual(compact["kind"], "riftreader-package-intake-compact-summary")
            self.assertTrue(compact["dryRun"])
            self.assertEqual(compact["changedFiles"], ["docs/test.md"])
            self.assertIn("--apply", compact["nextRecommendedAction"])
            self.assertFalse(compact["safety"]["gitMutation"])

    def test_apply_success_writes_backup_and_diff(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            package_root = Path(temp_dir) / "package"
            intake_dir = root / ".riftreader-local" / "package-intake" / "test"
            root.mkdir()
            package_root.mkdir()
            make_repo(root)
            target = root / "docs" / "test.md"
            target.parent.mkdir(parents=True)
            target.write_text("old\n", encoding="utf-8")
            checks = [{"name": "ok", "args": [sys.executable, "-c", "print('ok')"]}]
            make_package(package_root, "docs/test.md", "new\n", checks=checks)
            intake_dir.mkdir(parents=True)

            summary = apply_package.build_summary(
                root,
                package_root,
                intake_dir,
                apply_requested=True,
                run_declared_checks=True,
            )

            self.assertEqual(summary["status"], "passed")
            self.assertEqual(target.read_text(encoding="utf-8"), "new\n")
            self.assertEqual(len(summary["backups"]), 1)
            self.assertTrue((root / summary["artifacts"]["diff"]).is_file())
            self.assertTrue(summary["checks"][0]["ok"])

    def test_compact_cli_writes_compact_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            package_root = Path(temp_dir) / "package"
            output_root = root / ".riftreader-local" / "package-intake-test"
            root.mkdir()
            package_root.mkdir()
            make_repo(root)
            make_package(package_root, "docs/test.md", "new\n")

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = apply_package.main(
                    [
                        "--repo-root",
                        str(root),
                        "--package",
                        str(package_root),
                        "--output-dir",
                        str(output_root),
                        "--compact-json",
                    ]
                )

            self.assertEqual(code, 0)
            payload = json.loads(buffer.getvalue())
            self.assertEqual(payload["kind"], "riftreader-package-intake-compact-summary")
            run_dirs = [item for item in output_root.iterdir() if item.is_dir()]
            self.assertEqual(len(run_dirs), 1)
            self.assertTrue((run_dirs[0] / "compact-package-intake-summary.json").is_file())
            self.assertTrue((run_dirs[0] / "COMPACT_PACKAGE_INTAKE.md").is_file())
            self.assertTrue((run_dirs[0] / "package.diff").is_file())

    def test_self_test_summary_does_not_write_repo_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            run_root = root / ".riftreader-local" / "package-intake-selftest" / "test"
            root.mkdir()
            make_repo(root)

            summary, intake_dir = apply_package.build_self_test_summary(root, run_root)

            self.assertEqual(summary["status"], "passed")
            self.assertTrue(summary["dryRun"])
            self.assertTrue(summary["selfTest"]["noTargetWrite"])
            self.assertFalse((root / apply_package.SELF_TEST_TARGET).exists())
            self.assertTrue((run_root / "package" / package_manifest.MANIFEST_NAME).is_file())
            self.assertTrue((root / summary["artifacts"]["diff"]).is_file())
            self.assertEqual(intake_dir, run_root / "intake")

    def test_self_test_cli_compact_json_writes_ignored_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            output_root = root / ".riftreader-local" / "package-intake-selftest"
            root.mkdir()
            make_repo(root)

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = apply_package.main(
                    [
                        "--repo-root",
                        str(root),
                        "--self-test",
                        "--output-dir",
                        str(output_root),
                        "--compact-json",
                    ]
                )

            self.assertEqual(code, 0)
            payload = json.loads(buffer.getvalue())
            self.assertEqual(payload["kind"], "riftreader-package-intake-compact-summary")
            self.assertTrue(payload["selfTest"]["noTargetWrite"])
            self.assertIn("package-intake-selftest", payload["selfTest"]["runRoot"])
            run_dirs = [item for item in output_root.iterdir() if item.is_dir()]
            self.assertEqual(len(run_dirs), 1)
            self.assertTrue((run_dirs[0] / "intake" / "compact-package-intake-summary.json").is_file())
            self.assertTrue((run_dirs[0] / "intake" / "COMPACT_PACKAGE_INTAKE.md").is_file())
            self.assertFalse((root / apply_package.SELF_TEST_TARGET).exists())

    def test_apply_rolls_back_on_failed_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            package_root = Path(temp_dir) / "package"
            intake_dir = root / ".riftreader-local" / "package-intake" / "test"
            root.mkdir()
            package_root.mkdir()
            make_repo(root)
            target = root / "docs" / "test.md"
            target.parent.mkdir(parents=True)
            target.write_text("old\n", encoding="utf-8")
            checks = [{"name": "fail", "args": [sys.executable, "-c", "raise SystemExit(7)"]}]
            make_package(package_root, "docs/test.md", "new\n", checks=checks)
            intake_dir.mkdir(parents=True)

            summary = apply_package.build_summary(
                root,
                package_root,
                intake_dir,
                apply_requested=True,
                run_declared_checks=True,
            )

            self.assertEqual(summary["status"], "blocked")
            self.assertTrue(summary["rollback"]["performed"])
            self.assertEqual(target.read_text(encoding="utf-8"), "old\n")
            self.assertIn("docs/test.md", summary["rollback"]["restored"])


if __name__ == "__main__":
    unittest.main()
