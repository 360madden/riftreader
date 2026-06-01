from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from riftreader_workflow import ghidra_static_evidence  # noqa: E402


def write(path: Path, text: str = "test\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class GhidraStaticEvidenceTests(unittest.TestCase):
    def test_plan_uses_ignored_non_dot_project_and_pointer_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "RiftReader"
            external = Path(temp_dir) / "Tools"
            root.mkdir()
            write(root / "agents.md")
            write(root / "tools/riftreader_workflow/ghidra_scripts/RiftReaderPointerEvidence.java")
            write(external / "ghidra-headless.bat")
            binary = root / "fixtures" / "rift_x64.exe"
            write(binary, "binary\n")

            plan = ghidra_static_evidence.build_plan(
                root,
                external,
                binary_path=binary,
                run_stamp="20260601-000000",
                analysis_timeout_per_file=300,
                command_timeout_seconds=900,
            )

        self.assertEqual(plan["status"], "ready")
        self.assertIn("scripts\\captures\\ghidra-static-analysis-", plan["artifactRoot"])
        self.assertIn("scripts\\captures\\ghidra-static-projects", plan["projectLocation"])
        self.assertNotIn(".riftreader-local", plan["projectLocation"])
        self.assertIn("RiftReaderPointerEvidence.java", plan["commands"]["evidence"])
        self.assertTrue(plan["pathFixups"]["projectAvoidsDotPathComponent"])
        self.assertTrue(plan["safety"]["offlineOnly"])
        self.assertFalse(plan["safety"]["x64dbgAttach"])

    def test_self_test_is_plan_only(self) -> None:
        result = ghidra_static_evidence.build_self_test(REPO_ROOT)

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "passed")
        self.assertTrue(all(item["pass"] for item in result["checks"]))


if __name__ == "__main__":
    unittest.main()
