# RiftReader ChatGPT MCP Stage 21 approved apply proof

This documentation file is intentionally small and harmless. It exists to prove that the actual non-Codex ChatGPT MCP connector can move from an inert package proposal through reviewed dry-run into an approval-token-gated `apply_latest_package_draft` call.

## Proof boundaries

| Boundary | Expected state |
|---|---|
| Package scope | Docs-only file under `docs/workflow/`. |
| Apply gate | Requires current `dryRunSummaryPath`, `dryRunDiffSha256`, and local `expectedApprovalToken`. |
| Git mutation | Not performed by `apply_latest_package_draft`; commit remains a separate gate. |
| Remote mutation | Not performed by apply. |
| Live RIFT input | Not performed. |
| CE/x64dbg | Not used. |
| Provider writes | Not performed. |

## Acceptance evidence

Stage 21 is proven only when the actual connector call to `apply_latest_package_draft` returns `applied=true`, reports the changed file path for this note, keeps `gitMutation=false`, and records no live/provider/debugger side effects.

The follow-up Stage 27 proof may commit this file only after separate validation and a current commit preflight approval token.
