#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
import unittest
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
            self.assertFalse(summary["safety"]["gitMutation"])

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
