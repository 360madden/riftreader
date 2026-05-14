from __future__ import annotations

import json
import subprocess
import unittest
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT = REPO_ROOT / "tools" / "rift-window-capture" / "RiftWindowCapture.csproj"
EXE = (
    REPO_ROOT
    / "tools"
    / "rift-window-capture"
    / "bin"
    / "Debug"
    / "net10.0-windows10.0.19041.0"
    / "RiftWindowCapture.exe"
)
CAPTURES = REPO_ROOT / "scripts" / "captures"
PY_CONTROLLER = REPO_ROOT / "scripts" / "capture_rift_window.py"


def run(args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def unique_output_root(name: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return CAPTURES / f"{name}-{stamp}"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def assert_jsonl_valid(testcase: unittest.TestCase, path: Path) -> None:
    testcase.assertTrue(path.exists(), f"missing JSONL log: {path}")
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    testcase.assertGreater(len(lines), 0, f"empty JSONL log: {path}")
    for line in lines:
        testcase.assertIsInstance(json.loads(line), dict)


class RiftWindowCaptureCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        build = run(["dotnet", "build", str(PROJECT), "--nologo"], timeout=60)
        if build.returncode != 0:
            raise AssertionError(
                "dotnet build failed\nSTDOUT:\n"
                + build.stdout
                + "\nSTDERR:\n"
                + build.stderr
            )
        if not EXE.exists():
            raise AssertionError(f"expected built executable missing: {EXE}")

    def test_bad_hwnd_parse_exits_usage_64(self) -> None:
        result = run([str(EXE), "--hwnd", "not-a-handle", "--json"])
        self.assertEqual(result.returncode, 64, result.stdout + result.stderr)
        self.assertIn("--hwnd must be a positive window handle", result.stderr)

    def test_invalid_hwnd_writes_blocked_bundle_and_validates(self) -> None:
        output_root = unique_output_root("rift-window-capture-cli-test-invalid-hwnd")
        result = run([str(EXE), "--hwnd", "0x1", "--output-root", str(output_root), "--json"])
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["ok"])
        self.assertTrue(report["knownBlocker"])
        self.assertEqual(report["requestedHwnd"], "0x1")

        manifest_path = output_root / "manifest.json"
        manifest = load_json(manifest_path)
        self.assertEqual(manifest["schema"], "rift-window-capture-manifest/v1")
        self.assertEqual(manifest["status"], "blocked")
        self.assertEqual(manifest["target"]["requestedHwnd"], "0x1")
        self.assertFalse(manifest["safety"]["movementSent"])
        self.assertFalse(manifest["safety"]["inputSent"])
        self.assertTrue((output_root / "summary.md").exists())
        assert_jsonl_valid(self, output_root / "logs" / "run.jsonl")

        inspect_result = run([str(EXE), "inspect", "--manifest", str(manifest_path), "--json"])
        self.assertEqual(inspect_result.returncode, 0, inspect_result.stdout + inspect_result.stderr)
        self.assertTrue(json.loads(inspect_result.stdout)["ok"])

        validate_result = run([str(EXE), "validate", "--manifest", str(manifest_path), "--json"])
        self.assertEqual(validate_result.returncode, 0, validate_result.stdout + validate_result.stderr)
        self.assertTrue(json.loads(validate_result.stdout)["ok"])

    def test_wrapper_passes_output_root_and_exact_hwnd_safely(self) -> None:
        output_root = unique_output_root("rift-window-capture-cli-test-wrapper-invalid-hwnd")
        relative_root = output_root.relative_to(REPO_ROOT)
        result = run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(REPO_ROOT / "scripts" / "capture-rift-window-wgc.ps1"),
                "-Hwnd",
                "0x1",
                "-OutputRoot",
                str(relative_root),
                "-Json",
            ],
            timeout=60,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        manifest_path = output_root / "manifest.json"
        manifest = load_json(manifest_path)
        self.assertEqual(manifest["status"], "blocked")
        self.assertEqual(manifest["target"]["requestedHwnd"], "0x1")
        assert_jsonl_valid(self, output_root / "logs" / "run.jsonl")

    def test_benchmark_writes_summary_and_blocks_safely(self) -> None:
        output_root = unique_output_root("rift-window-capture-cli-test-benchmark-invalid-hwnd")
        result = run(
            [
                str(EXE),
                "benchmark",
                "--hwnd",
                "0x1",
                "--frames",
                "2",
                "--output-root",
                str(output_root),
                "--json",
            ]
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        benchmark = json.loads(result.stdout)
        self.assertFalse(benchmark["ok"])
        self.assertEqual(benchmark["framesRequested"], 2)
        self.assertEqual(benchmark["framesCompleted"], 1)
        self.assertTrue((output_root / "benchmark.json").exists())
        self.assertTrue((output_root / "summary.md").exists())
        self.assertEqual(load_json(output_root / "benchmark.json")["framesRequested"], 2)

    def test_python_controller_dry_run_writes_command_plan(self) -> None:
        output_root = unique_output_root("rift-window-capture-python-test-dry-run")
        result = run(
            [
                "python",
                str(PY_CONTROLLER),
                "--dry-run",
                "--output-root",
                str(output_root),
                "--hwnd",
                "0x1",
                "--json",
            ]
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["schema"], "rift-window-capture-controller/v1")
        self.assertEqual(summary["status"], "passed")
        self.assertTrue(summary["dryRun"])
        self.assertFalse(summary["commands"])
        self.assertTrue(any("--hwnd" in command for command in summary["commandPlan"] for command in command))
        self.assertTrue((output_root / "controller-summary.json").exists())
        self.assertTrue((output_root / "controller-summary.md").exists())

    def test_python_controller_self_test_observes_known_blocker(self) -> None:
        output_root = unique_output_root("rift-window-capture-python-test-self-test")
        result = run(
            [
                "python",
                str(PY_CONTROLLER),
                "--self-test",
                "--no-build",
                "--output-root",
                str(output_root),
                "--json",
            ]
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["status"], "passed")
        self.assertTrue(summary["selfTest"])
        self.assertTrue(summary["expectedBlockerObserved"])
        self.assertEqual(summary["toolReport"]["requestedHwnd"], "0x1")
        self.assertTrue(summary["toolReport"]["knownBlocker"])
        self.assertTrue((output_root / "manifest.json").exists())
        self.assertTrue((output_root / "controller-summary.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
