from __future__ import annotations

import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "promote-current-pid-proof-anchor-from-batch.ps1"


def extract_here_string_assignment(text: str, variable_name: str) -> str:
    marker = f"${variable_name} = @\""
    start = text.index(marker) + len(marker)
    end = text.index('\n"@', start)
    return text[start:end]


class PromoteCurrentPidProofAnchorFromBatchTests(unittest.TestCase):
    def test_encoded_child_commands_use_splatted_parameters(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8-sig")

        promote_command = extract_here_string_assignment(text, "PromoteCommand")
        assert_command = extract_here_string_assignment(text, "AssertCommand")

        self.assertIn("$PromoteParams = @{", promote_command)
        self.assertIn("@PromoteParams", promote_command)
        self.assertIn("ReadbackSummaryFile = $ReadbackArrayLiteral", promote_command)
        self.assertIn("CandidateId =", promote_command)
        self.assertIn("ProcessId = $RiftPid", promote_command)
        self.assertIn("TargetWindowHandle =", promote_command)

        self.assertIn("$AssertParams = @{", assert_command)
        self.assertIn("@AssertParams", assert_command)
        self.assertIn("ProofCoordAnchorFile =", assert_command)
        self.assertIn("ReadbackSampleCount = 4", assert_command)
        self.assertIn("ReadbackIntervalMilliseconds = 100", assert_command)

    def test_encoded_child_commands_do_not_depend_on_line_continuations(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8-sig")

        for variable_name in ("PromoteCommand", "AssertCommand"):
            command = extract_here_string_assignment(text, variable_name)
            continuation_lines = [line for line in command.splitlines() if line.rstrip().endswith("`")]
            self.assertEqual(
                continuation_lines,
                [],
                f"{variable_name} must not use trailing PowerShell line continuations inside encoded command text",
            )


if __name__ == "__main__":
    unittest.main()
