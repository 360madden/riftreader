from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from rift_live_test import postupdate_root_signature_seed as helper


class PostUpdateRootSignatureSeedTests(unittest.TestCase):
    def test_build_seed_packet_uses_top_owner_row_and_module_hints(self) -> None:
        owner_batch = {
            "target": {"pid": 77152, "hwndHex": "0x17A0DB2"},
            "rankedRows": [
                {
                    "owner": "0x1D4BA11F480",
                    "sourceTarget": "0x1D4BA11BE00",
                    "summaryJson": "neighborhood.json",
                }
            ],
            "moduleRvaHints": [
                {
                    "rva": "0x26E5E80",
                    "examples": [
                        {
                            "owner": "0x1D4BA11F480",
                            "storageAddress": "0x1D4BA11F4A0",
                            "offsetFromOwner": "0x20",
                            "value": "0x7FF7238A5E80",
                        },
                        {
                            "owner": "0xDEAD",
                            "storageAddress": "0xDEAD20",
                            "offsetFromOwner": "0x20",
                            "value": "0x7FF7238A5E80",
                        },
                    ],
                },
                {
                    "rva": "0x26E3200",
                    "examples": [
                        {
                            "owner": "0x1D4BA11F480",
                            "storageAddress": "0x1D4BA11F460",
                            "offsetFromOwner": "-0x20",
                            "value": "0x7FF7238A3200",
                        }
                    ],
                },
                {
                    "rva": "0x26E5278",
                    "examples": [
                        {
                            "owner": "0x1D4BA11F480",
                            "storageAddress": "0x1D4BA11F240",
                            "offsetFromOwner": "-0x240",
                            "value": "0x7FF7238A5278",
                        }
                    ],
                },
            ],
        }

        packet = helper.build_seed_packet(owner_batch, source_owner_batch="owner-batch.json")
        fields = packet["signature"]["ownerModuleFields"]

        self.assertEqual(packet["status"], "candidate-only")
        self.assertEqual(packet["signature"]["ownerBase"], "0x1D4BA11F480")
        self.assertEqual(packet["signature"]["coordPointer"], "0x1D4BA11BE00")
        self.assertEqual(len(fields), 3)
        self.assertNotIn("owner-module-fields-missing", packet["blockers"])
        self.assertTrue(all(field["candidateOnly"] for field in fields))

    def test_build_seed_packet_blocks_without_owner_fields(self) -> None:
        packet = helper.build_seed_packet({"rankedRows": [{"owner": "0x1000", "sourceTarget": "0x2000"}]})

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("owner-module-fields-missing", packet["blockers"])

    def test_self_test_passes(self) -> None:
        self.assertEqual(helper.self_test()["status"], "passed")

    def test_cli_writes_seed_json_without_live_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            owner_batch = Path(temp) / "owner-batch.json"
            owner_batch.write_text(
                json.dumps(
                    {
                        "target": {"pid": 1234, "hwndHex": "0xC0DE"},
                        "rankedRows": [{"owner": "0x2000", "sourceTarget": "0x5000"}],
                        "moduleRvaHints": [
                            {
                                "rva": "0x1",
                                "examples": [
                                    {"owner": "0x2000", "storageAddress": "0x2008", "offsetFromOwner": "0x8", "value": "0x700000001"}
                                ],
                            },
                            {
                                "rva": "0x2",
                                "examples": [
                                    {"owner": "0x2000", "storageAddress": "0x2010", "offsetFromOwner": "0x10", "value": "0x700000002"}
                                ],
                            },
                            {
                                "rva": "0x3",
                                "examples": [
                                    {"owner": "0x2000", "storageAddress": "0x2018", "offsetFromOwner": "0x18", "value": "0x700000003"}
                                ],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            output_root = Path(temp) / "seed"
            with redirect_stdout(StringIO()):
                code = helper.main(
                    [
                        "--from-owner-batch-summary",
                        str(owner_batch),
                        "--output-root",
                        str(output_root),
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            packet = json.loads((output_root / "root-signature-seed.json").read_text(encoding="utf-8"))
            self.assertFalse(packet["safety"]["targetMemoryBytesRead"])
            self.assertFalse(packet["safety"]["movementSent"])
            self.assertEqual(packet["signature"]["coordPointerSlotOffset"], "0x0")


if __name__ == "__main__":
    unittest.main()
