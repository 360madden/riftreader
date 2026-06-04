# RiftReader Operator Status Snapshot

- Generated UTC: `2026-06-04T23:32:29Z`
- Base HEAD: `8da46d91ac30ad33d9041c9a90acd7c7f303df74`

## Project Board

| Field | Value |
|---|---|
| Current lane | `static-chain-repair-needed` |
| Now | `Static-chain repair` |
| Next | `Use existing diagnostics/artifacts to identify repair target` |
| Later | `Only build a new helper if the same blocker repeats` |
| Blocked by | `static-chain-repair-needed:root-pointer-null` |

## Classifier

- Classification: `static-chain-repair-needed`
- Confidence: `high`
- Blocker: `static-chain-repair-needed:root-pointer-null`
- Reason: Proof anchor is current, but static owner root/chain is null or blocked.

## Next Recommended Action

Run or inspect static-chain repair diagnostics; do not rerun proof-anchor recovery for this state.

```text
python tools/riftreader_mcp/call_tool.py --tool riftreader.run_static_chain_diagnostics --timeout-seconds 900 --json
```

## Do Not Do

- Do not rerun proof-anchor recovery when proofAnchorCurrent is true.
- Do not apply stale current-truth/dashboard artifacts.
- Do not promote heap/current-PID-only evidence as restart-stable truth.
- Do not use CE/x64dbg unless the debugger lane is explicitly selected later.

## Raw operator-status markdown

```markdown
# RiftReader Operator Status

- Generated UTC: `2026-06-04T23:32:24Z`
- Status: `passed`

## Project Board

| Field | Value |
|---|---|
| Current lane | `static-chain-repair-needed` |
| Now | `Static-chain repair` |
| Next | `Use existing diagnostics/artifacts to identify repair target` |
| Later | `Only build a new helper if the same blocker repeats` |
| Blocked by | `static-chain-repair-needed:root-pointer-null` |

## Next Recommended Action

Run or inspect static-chain repair diagnostics; do not rerun proof-anchor recovery for this state.

```text
python tools/riftreader_mcp/call_tool.py --tool riftreader.run_static_chain_diagnostics --timeout-seconds 900 --json
```

## Do Not Do

- Do not rerun proof-anchor recovery when proofAnchorCurrent is true.
- Do not apply stale current-truth/dashboard artifacts.
- Do not promote heap/current-PID-only evidence as restart-stable truth.
- Do not use CE/x64dbg unless the debugger lane is explicitly selected later.

## END_OF_SCRIPT_MARKER
```

<!-- END_OF_SCRIPT_MARKER -->
