# AOB Signature Registry

This directory stores **array-of-byte (AOB) signatures** for key static addresses
in the RIFT client. When the game updates and module addresses shift, these
signatures let the reader reacquire critical RVAs in seconds instead of hours.

## What an AOB signature captures

For each promoted RVA, we store:
1. **The byte pattern** — 16-32 unique bytes around the root pointer
2. **The RVA** — where the pattern was captured relative to module base
3. **The field layout** — what offsets exist relative to the dereferenced pointer
4. **Uniqueness proof** — scan results confirming the pattern is unique in the module

## Directory layout

```
signatures/
├── README.md                  ← this file
├── rift_x64/                  ← per-module directory
│   ├── root_0x32EBC80.json    ← root RVA for player owner pointer
│   └── ...                     ← future signatures (target, health, etc.)
└── scripts/
    └── capture_root_signature.py  ← capture tool (in scripts/ dir)
```

## How to capture a new signature

```bash
python scripts/capture_root_signature.py --rva 0x32EBC80 --label root-player-owner --pid <pid> --json
```

This reads ±32 bytes around the root pointer, scans for the unique AOB pattern
in the module, and writes the signature to `signatures/rift_x64/`.

## How to use signatures during reacquisition

After a game update:

```bash
# 1. Scan for the known root pattern
dotnet run --project reader/RiftReader.Reader -- --process-name rift_x64 --scan-module-pattern "<aa bb ?? cc>" --json

# 2. The new RVA is reported. Update current-truth.json.

# 3. Read back the chain to verify
python scripts/static_owner_coordinate_chain_readback.py --use-current-truth --json
```

## Signature rotation policy

| Event | Action |
|---|---|
| Minor patch (byte shift < 4 bytes) | Signature likely still works. Re-verify uniqueness. |
| Major patch (function rewrites) | Re-capture signature. Old signature is historical. |
| Expansion (object layout changes) | Re-capture all signatures + re-validate owner layout. |

Old signatures move to `signatures/rift_x64/historical/` with a timestamp prefix.

## Currently captured signatures

| Signature file | RVA | What it finds | Captured |
|---|---|---|---|
| `root_0x32EBC80.json` | `0x32EBC80` | Player owner pointer root | Pending |
