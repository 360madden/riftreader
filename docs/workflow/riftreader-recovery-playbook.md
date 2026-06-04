<!--
Version: riftreader-recovery-playbook-v0.1.0
Purpose: Structured blocker-response playbook for fast RiftReader recovery automation.
-->

# RiftReader Recovery Playbook v0.1

## Purpose

Minimize downtime by turning common blocker states into known recovery lanes.

The playbook exists so the operator, repo helpers, and LLM use the same decision map.

## Recovery lanes

| Classification | Trigger | Safe automatic actions | Approval-required actions | Do not do |
|---|---|---|---|---|
| `status-refresh-needed` | No compact status exists | Run compact status, read handoff, read git state | None | Do not run discovery/promotions first |
| `proof-reacquire-needed` | PID/HWND/proof epoch stale | Discover target, no-movement scan, write summary | Bounded movement, proof promotion, ProofOnly commit | Do not reuse old PID/HWND |
| `static-chain-repair-needed` | Proof current but static root/chain null | Static diagnostics, snapshot, handoff draft | Static promotion, current-truth apply, debugger lane | Do not rerun proof recovery |
| `stale-dashboard-or-current-truth` | Dashboard/current-truth stale | Refresh status, compare epochs | Current-truth write, navigation enable | Do not treat stale artifacts as live truth |
| `manual-review-needed` | Unknown blocker pattern | Read handoff/status/git | Depends on lane | Do not build new tools before interpretation |

## Blocker response rules

### Game restart

1. Refresh compact status.
2. If proof is stale, run proof reacquire lane.
3. After ProofOnly, return to classifier.
4. Do not apply current-truth from old PID/HWND.

### Game update

1. Freeze static promotion.
2. Run compact status.
3. Run no-input static diagnostics.
4. Compare old static root and current proof evidence.
5. Add a classifier rule only if the pattern repeats.

### Static root null

1. Confirm proof anchor is current.
2. Classify as `static-chain-repair-needed`.
3. Run diagnostics.
4. Do not rerun proof recovery unless proof becomes stale.

### Transport failure

1. Try MCP smoke/status.
2. Fallback to GitHub snapshot.
3. Fallback to compact paste.
4. Never mutate truth because transport failed.

## END_OF_SCRIPT_MARKER
