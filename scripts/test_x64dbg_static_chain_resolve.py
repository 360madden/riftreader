from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.x64dbg_static_chain_resolve import main, synthetic_candidate, synthetic_memory_image, synthetic_module_map


class X64DbgStaticChainResolveTests(unittest.TestCase):
    def run_main(self, args: list[str]) -> int:
        with redirect_stdout(StringIO()):
            return main(args)

    def write_json(self, temp: str, name: str, payload: dict) -> Path:
        path = Path(temp) / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_self_test_resolves_chain_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "resolve"
            code = self.run_main(["--self-test", "--output-root", str(out), "--json"])

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            resolved = json.loads((out / "resolved-chain.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "passed")
            self.assertFalse(summary["safety"]["movementSent"])
            self.assertFalse(summary["safety"]["x64dbgLiveAttachStarted"])
            self.assertFalse(summary["safety"]["nativeLiveMemoryReadStarted"])
            self.assertTrue(resolved["validation"]["apiNowVsChainNow"])
            self.assertFalse(resolved["validation"]["movementProofEligible"])
            self.assertEqual(resolved["readback"]["baseAddress"], "0x300000030")

    def test_missing_derived_chain_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate = synthetic_candidate()
            candidate.pop("derivedChain")
            candidate_path = self.write_json(temp, "candidate.json", candidate)
            module_path = self.write_json(temp, "modules.json", synthetic_module_map())
            memory_path = self.write_json(temp, "memory.json", synthetic_memory_image())
            out = Path(temp) / "blocked"
            code = self.run_main(
                [
                    "--candidate-json",
                    str(candidate_path),
                    "--module-map-json",
                    str(module_path),
                    "--memory-image-json",
                    str(memory_path),
                    "--output-root",
                    str(out),
                    "--json",
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("missing-derived-chain", summary["blockers"])
            self.assertIn("missing-derived-chain-root-rva", summary["blockers"])

    def test_missing_current_module_base_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate_path = self.write_json(temp, "candidate.json", synthetic_candidate())
            memory_path = self.write_json(temp, "memory.json", synthetic_memory_image())
            out = Path(temp) / "blocked-module"
            code = self.run_main(
                [
                    "--candidate-json",
                    str(candidate_path),
                    "--memory-image-json",
                    str(memory_path),
                    "--output-root",
                    str(out),
                    "--json",
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("missing-current-module-base", summary["blockers"])

    def test_no_memory_image_resolves_address_only_and_blocks_readback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate_path = self.write_json(temp, "candidate.json", synthetic_candidate())
            module_path = self.write_json(temp, "modules.json", synthetic_module_map())
            out = Path(temp) / "blocked-readback"
            code = self.run_main(
                [
                    "--candidate-json",
                    str(candidate_path),
                    "--module-map-json",
                    str(module_path),
                    "--output-root",
                    str(out),
                    "--json",
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            resolved = json.loads((out / "resolved-chain.json").read_text(encoding="utf-8"))
            self.assertIn("no-readback-source", summary["blockers"])
            self.assertEqual(resolved["derivedChain"]["rootAddress"], "0x140001000")

    def test_delta_exceeded_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            memory = synthetic_memory_image()
            memory["float"]["0x300000030"] = 8000.0
            candidate_path = self.write_json(temp, "candidate.json", synthetic_candidate())
            module_path = self.write_json(temp, "modules.json", synthetic_module_map())
            memory_path = self.write_json(temp, "memory.json", memory)
            out = Path(temp) / "blocked-delta"
            code = self.run_main(
                [
                    "--candidate-json",
                    str(candidate_path),
                    "--module-map-json",
                    str(module_path),
                    "--memory-image-json",
                    str(memory_path),
                    "--output-root",
                    str(out),
                    "--json",
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("api-now-vs-chain-now-delta-exceeded", summary["blockers"])

    def test_pointer_read_failure_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            memory = synthetic_memory_image()
            memory["qword"].pop("0x200000020")
            candidate_path = self.write_json(temp, "candidate.json", synthetic_candidate())
            module_path = self.write_json(temp, "modules.json", synthetic_module_map())
            memory_path = self.write_json(temp, "memory.json", memory)
            out = Path(temp) / "blocked-pointer"
            code = self.run_main(
                [
                    "--candidate-json",
                    str(candidate_path),
                    "--module-map-json",
                    str(module_path),
                    "--memory-image-json",
                    str(memory_path),
                    "--output-root",
                    str(out),
                    "--json",
                ]
            )

            self.assertEqual(code, 2)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("pointer-chain-read-failed", summary["blockers"])

    def test_module_base_arg_can_replace_module_map(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate_path = self.write_json(temp, "candidate.json", synthetic_candidate())
            memory_path = self.write_json(temp, "memory.json", synthetic_memory_image())
            out = Path(temp) / "base-arg"
            code = self.run_main(
                [
                    "--candidate-json",
                    str(candidate_path),
                    "--module-base",
                    "0x140000000",
                    "--memory-image-json",
                    str(memory_path),
                    "--output-root",
                    str(out),
                    "--json",
                ]
            )

            self.assertEqual(code, 0)
            resolved = json.loads((out / "resolved-chain.json").read_text(encoding="utf-8"))
            self.assertEqual(resolved["derivedChain"]["currentModuleBase"], "0x140000000")


if __name__ == "__main__":
    unittest.main()
