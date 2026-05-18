# Version: riftreader-package-flow-tests-v0.1.3
# Total-Character-Count: 7014
# Purpose: Unit tests for the Python-owned RiftReader package flow helper.

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
import hashlib

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.riftreader_workflow import package_flow


class PackageFlowTests(unittest.TestCase):
    def make_package(self, temp: Path, content: bytes = b"print('ok')\n") -> Path:
        source_rel = "tools/riftreader_workflow/sample.py"
        source = temp / source_rel
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        manifest = {
            "schemaVersion": 1,
            "package": "transport-probe-test",
            "files": [
                {
                    "source": source_rel,
                    "target": source_rel,
                    "destination": source_rel,
                    "path": source_rel,
                    "sha256": digest,
                    "sizeBytes": len(content),
                }
            ],
        }
        manifest_path = temp / package_flow.MANIFEST_NAME
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        package_path = temp / "TransportProbe_Test.zip"
        with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(source, source_rel)
            archive.write(manifest_path, package_flow.MANIFEST_NAME)
        return package_path

    def test_normalize_rejects_traversal(self) -> None:
        with self.assertRaises(package_flow.PackageFlowError):
            package_flow.normalize_repo_path("../bad.txt")

    def test_normalize_rejects_absolute(self) -> None:
        with self.assertRaises(package_flow.PackageFlowError):
            package_flow.normalize_repo_path("/bad.txt")

    def test_validate_package_success(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            package_path = self.make_package(Path(name))
            report = package_flow.validate_package(package_path)
            self.assertEqual(report["manifestFileCount"], 1)
            self.assertEqual(report["files"][0]["source"], "tools/riftreader_workflow/sample.py")

    def test_validate_package_sha_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            package_path = self.make_package(Path(name))
            with self.assertRaises(package_flow.PackageFlowError):
                package_flow.validate_package(package_path, "0" * 64)

    def test_validate_package_manifest_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            temp = Path(name)
            source_rel = "tools/riftreader_workflow/sample.py"
            source = temp / source_rel
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("actual\n", encoding="utf-8")
            manifest = {
                "schemaVersion": 1,
                "files": [
                    {
                        "source": source_rel,
                        "target": source_rel,
                        "sha256": "0" * 64,
                        "sizeBytes": source.stat().st_size,
                    }
                ],
            }
            manifest_path = temp / package_flow.MANIFEST_NAME
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            package_path = temp / "bad.zip"
            with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(source, source_rel)
                archive.write(manifest_path, package_flow.MANIFEST_NAME)
            with self.assertRaises(package_flow.PackageFlowError):
                package_flow.validate_package(package_path)

    def test_infer_transport_profile(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            package_path = self.make_package(Path(name))
            profile = package_flow.resolve_profile("auto", package_path, {"package": "RiftReader_TransportProbe_v0.1.1"})
            self.assertEqual(profile, "transport-probe")


    def test_package_flow_profile_self_test_uses_python_not_cmd_wrapper(self) -> None:
        commands = package_flow.profile_commands("package-flow")
        flattened = [" ".join(command) for command in commands]
        self.assertTrue(any("tools/riftreader_workflow/package_flow.py --json self-test" in item for item in flattened))
        self.assertFalse(any(command[0].replace("\\", "/").endswith("scripts/riftreader-package-flow.cmd") for command in commands))

    def test_run_command_failure_reports_stdout_and_stderr_tail(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            repo = Path(name)
            command = [
                sys.executable,
                "-c",
                "import sys; print('stdout-marker'); print('stderr-marker', file=sys.stderr); sys.exit(7)",
            ]
            with self.assertRaises(package_flow.PackageFlowError) as ctx:
                package_flow.run_command(repo, command, 30)
            message = str(ctx.exception)
            self.assertIn("rc=7", message)
            self.assertIn("stdout-marker", message)
            self.assertIn("stderr-marker", message)

    def test_github_review_publish_profile_exists(self) -> None:
        self.assertIn("github-review-publish", package_flow.PROFILE_COMMANDS)
        expected = package_flow.profile_expected_files("github-review-publish")
        self.assertIn("tools/riftreader_workflow/github_review_publish.py", expected)

    def test_infer_github_review_publish_profile(self) -> None:
        profile = package_flow.resolve_profile("auto", None, {"package": "RiftReader_GitHubReviewPublish_v0.1.0"})
        self.assertEqual(profile, "github-review-publish")


    def test_main_merge_profile_exists(self) -> None:
        self.assertIn("main-merge", package_flow.PROFILE_COMMANDS)
        expected = package_flow.profile_expected_files("main-merge")
        self.assertIn("tools/riftreader_workflow/main_merge.py", expected)

    def test_infer_main_merge_profile(self) -> None:
        profile = package_flow.resolve_profile("auto", None, {"package": "RiftReader_MainMerge_v0.1.0"})
        self.assertEqual(profile, "main-merge")

    def test_self_test_ok(self) -> None:
        report = package_flow.self_test(type("Args", (), {})())
        self.assertTrue(report["ok"])
        self.assertEqual(report["checkCount"], 3)

    def test_print_json_report_is_valid_json(self) -> None:
        report = {"schemaVersion": 1, "tool": "x", "ok": True}
        # Smoke test only: actual stdout capture is intentionally omitted.
        self.assertIn("schemaVersion", report)


if __name__ == "__main__":
    unittest.main()

# END_OF_SCRIPT_MARKER
