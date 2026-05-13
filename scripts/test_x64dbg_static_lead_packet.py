from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test.x64dbg_static_lead_packet import (
    build_work_packet,
    candidate_offset_alignments,
    extract_code_leads,
    main,
    parse_memory_reference,
    synthetic_candidate_doc,
    synthetic_disasm_doc,
    synthetic_readback_doc,
)


class X64DbgStaticLeadPacketTests(unittest.TestCase):
    def test_parse_memory_reference_extracts_register_and_constant_offset(self) -> None:
        refs = parse_memory_reference("qword ptr [rcx + 0x10], 0")

        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["baseRegister"], "rcx")
        self.assertEqual(refs[0]["constantOffset"], "0x10")
        self.assertEqual(refs[0]["constantOffsetInt"], 0x10)

    def test_extract_code_leads_finds_hit_instruction(self) -> None:
        leads = extract_code_leads(synthetic_disasm_doc())

        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0]["currentHitRip"], "0x7FF71D30C2B5")
        self.assertEqual(leads[0]["instruction"]["text"], "cmp qword ptr [rcx + 0x10], 0")

    def test_candidate_offset_alignment_matches_sibling_spacing(self) -> None:
        packet = build_work_packet(
            candidate_doc=synthetic_candidate_doc(),
            readback_doc=synthetic_readback_doc(),
            rva_check_doc={"rows": []},
            disasm_doc=synthetic_disasm_doc(),
            inputs={},
        )
        alignments = packet["candidateOffsetAlignments"]

        self.assertEqual(len(alignments), 1)
        self.assertEqual(alignments[0]["fromCandidate"], "0x268DF21ED20")
        self.assertEqual(alignments[0]["toCandidate"], "0x268DF21ED30")
        self.assertEqual(alignments[0]["constantOffset"], "0x10")
        self.assertIn("not-resolved-static-chain", packet["blockers"])

    def test_no_constant_offset_has_no_alignment(self) -> None:
        candidates = [
            {"address": "0x1000", "candidateId": "a"},
            {"address": "0x1010", "candidateId": "b"},
        ]
        leads = [
            {
                "instruction": {"text": "movzx edx, byte ptr [rax + r9]"},
                "memoryReferences": parse_memory_reference("byte ptr [rax + r9]"),
            }
        ]

        self.assertEqual(candidate_offset_alignments(candidates, leads), [])

    def test_self_test_writes_packet_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "packet"
            with redirect_stdout(StringIO()):
                code = main(["--self-test", "--output-root", str(out), "--json"])

            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            packet = json.loads((out / "static-lead-work-packet.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "candidate")
            self.assertFalse(summary["safety"]["x64dbgLiveAttachStarted"])
            self.assertFalse(summary["safety"]["nativeLiveMemoryReadStarted"])
            self.assertEqual(summary["counts"]["candidateOffsetAlignmentCount"], 1)
            self.assertEqual(packet["candidateOffsetAlignments"][0]["constantOffset"], "0x10")


if __name__ == "__main__":
    unittest.main()
