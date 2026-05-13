# Handoff: navigation-focus pivot

Generated: 2026-05-13 16:57 EDT / 2026-05-13 20:57 UTC
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

The active repo direction is now **RIFT MMO navigation** again. Do not continue
the planned full-blown reverse-engineering product build right now.

Reverse-engineering work remains valuable, but only as a **supporting recovery
lane** for navigation blockers such as stale coordinate proof, missing
actor-facing/yaw truth, turn-backend promotion, or restart-stable proof-anchor
reacquisition.

## Current state

| Area | Status |
|---|---|
| Product focus | Navigation-first. |
| Full RE product | Paused / not started as a repo milestone. |
| Current coordinate proof | Not promoted for the latest PID `2928`; candidate-only family evidence exists. |
| Movement permission | Blocked until exact-target visual gate and same-target proof gates pass. |
| Auto-turn | Still blocked until actor-facing/turn-backend truth is current and promoted. |
| Cheat Engine | Not authorized for the current lane. |
| x64dbg | Supporting/static-chain tool only; do not repeat failed attach attempts without a new tactic. |

## Working rule

Navigation work should proceed in this order:

1. read `docs/recovery/current-truth.md`;
2. prefer the latest navigation handoffs over static-chain-only handoffs when
   choosing product work;
3. revalidate live target/visual/proof state before any live input;
4. use coordinate-family/static-chain discovery only when navigation proof is
   blocked by stale or missing truth;
5. keep candidate-only evidence clearly separated from movement permission.

## Paused reverse-engineering lane

The latest static-chain/current-PID artifacts remain preserved for future use,
but they are not the next implementation direction:

| Artifact / lane | Use now |
|---|---|
| Current PID `2928` coordinate-family candidate `0x268DF200000` | Recovery seed only. |
| Best focused candidate `0x268DF21ED30` | Candidate-only; not navigation truth. |
| Static x64dbg hit RVAs | Static-chain support only if proof recovery needs it. |
| Pointer-family/owner scans | Supporting evidence only; no module/static root proven. |
| HTML static-chain report | Historical/operator summary, not product roadmap. |

## Navigation-first top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Generate an offline navigation resume status with `python .\scripts\navigation_resume_status.py --write-summary --json`. | Gives the next session a compact navigation-first gate summary without live input. |
| 2 | Refresh the live target inventory and newest navigation handoff before movement. | Avoids acting on static-chain or stale PID context. |
| 3 | Run visual gate for the exact current PID/HWND. | Live input must remain fail-closed until capture/focus is proven. |
| 4 | Rebuild or validate a current proof coordinate anchor. | Navigation needs fresh API-now vs memory-now/current-anchor agreement. |
| 5 | Run same-target `ProofOnly` immediately before movement. | Prevents stale proof reuse after restart/session drift. |
| 6 | Resume no-turn observed-forward waypoint smoke first. | It is the most recently proven navigation lane. |
| 7 | Keep route distances short and bounded while reacquiring state. | Limits risk while proving the environment and input backend. |
| 8 | Re-check native exact-HWND movement backend metadata. | Confirms the repo-owned backend is still the active movement surface. |
| 9 | Defer auto-turn until actor-facing/yaw truth is current. | Avoids using stale facing candidates for route control. |
| 10 | Use family/static-chain discovery only if proof-anchor reacquisition blocks. | Keeps reverse engineering as a navigation dependency, not a product fork. |

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. The repo focus has pivoted
back to **RIFT MMO navigation**, not a general reverse-engineering product.
Read `docs\recovery\current-truth.md`, `docs\navigation-v3-plan.md`, and this
handoff first. Treat current PID `2928` coordinate-family/static-chain evidence
as candidate-only recovery support. Before any live input, reacquire exact
PID/HWND, run the visual gate, refresh current proof/API-now vs memory-now, and
run same-target `ProofOnly`. Start with no-turn observed-forward navigation
before any auto-turn/facing work.
