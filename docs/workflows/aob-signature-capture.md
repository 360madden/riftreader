# AOB Signature Capture

**What this covers:** Capturing array-of-byte (AOB) signatures for fast pointer
chain reacquisition after game updates.

**When to use:** After promoting a new root RVA, or when a signature expires.

**Time estimate:** ~5 seconds per signature.

---

## Why signatures matter

After a game update, the module base address changes and sometimes the root RVA
shifts. Without signatures, you'd need to redo the full RE pipeline (Cheat Engine
scan, pointer trace, validation). With signatures, you run one AOB scan and
the new RVA is found in seconds.

**A signature captures:**
- A unique byte pattern around a root RVA pointer
- Enough context bytes to be unique in the module (no false matches)
- Wildcards (`??`) for the pointer bytes themselves (they change per session)

---

## Capture a signature

```bash
python scripts/capture_root_signature.py \
  --rva 0x32EBC80 \
  --label root-player-owner \
  --pid <current_rift_pid> \
  --json
```

### What it does

1. Enumerates `rift_x64.exe` module base and size
2. Reads the 8-byte pointer at `moduleBase + RVA`
3. Captures ±32 bytes of context around the pointer
4. Reads the entire module bytes
5. Finds the smallest unique byte pattern in the context window
6. Writes the signature to `signatures/rift_x64/root_<label>.json`

### Output

```json
{
  "status": "passed",
  "verdict": "aob-signature-captured",
  "signaturePath": "signatures/rift_x64/root-root-player-owner.json",
  "signature": {
    "aobPattern": "48 8B 05 ?? ?? ?? ?? 48 8B 88 ...",
    "patternSize": 24,
    "rootRvaInPattern": 3,
    "moduleScanCount": 1
  },
  "ownerPointer": "0x278C3830010"
}
```

The `moduleScanCount: 1` means the pattern is **unique** in the module — no
false positives.

---

## Validate a signature

After capturing, validate it survives a restart:

```bash
# 1. Restart RIFT (or wait for next session)
# 2. Scan for the signature
dotnet run --project reader/RiftReader.Reader/RiftReader.Reader.csproj -- \
  --process-name rift_x64 \
  --scan-module-pattern "48 8B 05 ?? ?? ?? ?? 48 8B 88 ..." \
  --json

# 3. If it finds the pattern at a different RVA, the signature is still valid
# 4. Read back to verify
python scripts/static_owner_coordinate_chain_readback.py \
  --use-current-truth --json
```

---

## Signature file format

See `signatures/rift_x64/root_*.json` for examples. Each file contains:

| Field | Purpose |
|---|---|
| `schemaVersion` | Format version (currently 1) |
| `capturedAtUtc` | When the signature was captured |
| `label` | Human-readable label |
| `module` | Module name (e.g., `rift_x64.exe`) |
| `rva` | The RVA this signature finds |
| `chain` | The full chain expression |
| `whatThisFinds` | Description of what the pointer resolves to |
| `sessionContext` | PID, module base, owner pointer at capture time |
| `signature.aobPattern` | The AOB pattern with `??` wildcards |
| `signature.moduleScanCount` | Must be 1 (unique) |
| `signature.rootRvaInPattern` | Byte offset of the pointer within the pattern |
| `validation` | Validation status and instructions |

---

## When to re-capture

| Scenario | Action |
|---|---|
| Signature `moduleScanCount` > 1 after update | Pattern no longer unique. Re-capture with larger window. |
| Signature matches 0 times after update | Pattern bytes changed. Re-capture from new RE analysis. |
| New root RVA promoted | Capture signature immediately. |
| Minor patch, signature still works | Keep existing signature. |
| Expansion, entire module restructured | Re-capture ALL signatures. |

---

## Currently captured signatures

| File | RVA | Status |
|---|---|---|
| `root-root-player-owner.json` | `0x32EBC80` | To be captured |
