# Compact handoff — OpenCode bridge ready, proof still stale

> Historical snapshot: this handoff was created before commit `337016a`
> (`Add adaptive OpenCode integration bridge`). Use it as the stale-proof /
> OpenCode baseline context from 2026-05-17 09:37 EDT, not as the newest
> implementation inventory. Always rerun
> `scripts\riftreader-workflow-status.cmd --compact-json` for current truth.

Created: 2026-05-17 09:37 EDT
Branch: `main`
HEAD: `c8939ec` — `Default OpenCode bridge to GPT-5.5 xhigh`
Scope: Compact resume point after OpenCode/non-Codex bridge setup and GPT-5.5 xhigh default.

## TL;DR

OpenCode is now usable as the local non-Codex execution/status bridge. Default model is `openai/gpt-5.5` with `xhigh` reasoning. The repo wrappers, docs, status packet, and package review/live observer lanes are wired and validated.

The active blocker is not OpenCode: current coordinate proof is stale. A `rift_x64` process is visible with PID `22304`, but the proof artifact points at historical PID `27552` / HWND `0x3411E2`. Movement remains blocked until safe current-target reacquisition/status refresh and same-target proof validation pass.

## Current truth snapshot

| Field | Value |
|---|---|
| Git branch | `main...origin/main` |
| Worktree before this handoff | Clean |
| HEAD | `c8939ec` — `Default OpenCode bridge to GPT-5.5 xhigh` |
| Status packet | `blocked` expected |
| OpenCode CLI | `1.15.3` |
| OpenCode model | `openai/gpt-5.5` |
| OpenCode reasoning variant | `xhigh` |
| OpenCode model visible | `true` |
| Visible process | `rift_x64` PID `22304` |
| Historical proof target | PID `27552`, HWND `0x3411E2` |
| Current proof | `blocked-target-drift` |
| Movement | Blocked |

## Safety boundary

| Boundary | Current rule |
|---|---|
| Process visibility | Not same-target proof and not movement permission. |
| Stale proof pointer | Do not use as current proof; do not use for movement. |
| Old PID/HWND | `27552` / `0x3411E2` is historical only. |
| Live input/movement | Not authorized in this lane. |
| `/reloadui` / screenshot hotkeys | Not sent. |
| CE/x64dbg | Not attached. |
| Provider repo writes | Not allowed. |
| Git mutation | Only explicit repo commit/push after validation. |

## Recent pushed commits

| Commit | Purpose |
|---|---|
| `c8939ec` | Default OpenCode bridge to GPT-5.5 xhigh. |
| `4110e3a` | Use process-aware OpenCode target wording. |
| `1e1bfdf` | Clarify live stale-target OpenCode status. |
| `a5444d0` | Document OpenCode default model fix. |
| `34fbd2e` | Fix OpenCode GPT-5.5 CLI bridge. |

## Useful commands

| Command | Use |
|---|---|
| `scripts\riftreader-workflow-status.cmd --compact-json --write` | Deterministic compact local truth for desktop ChatGPT. |
| `scripts\riftreader-opencode-sitrep.cmd` | OpenCode one-shot SITREP using GPT-5.5 xhigh. |
| `scripts\riftreader-opencode-live-observer.cmd` | No-input process/proof status observer using GPT-5.5 xhigh. |
| `scripts\riftreader-package-intake-selftest.cmd` | Safe package intake smoke test. |
| `scripts\riftreader-opencode-package-review.cmd <package>` | OpenCode package dry-run review; no apply by default. |
| `scripts\riftreader-operator-lite.cmd --self-test --json` | Headless Operator Lite validation. |

## Recommended next slice

Next safest useful work is a **no-input current-target reacquisition readiness packet**. It should answer whether current PID `22304` has enough safe current runtime/API evidence to attempt proof recovery. It must not send movement/input, attach CE/x64dbg, or promote proof.

## Ready-to-paste resume prompt

```text
Resume RiftReader OpenCode/non-Codex lane from `docs\handoffs\2026-05-17-0937-compact-opencode-bridge-ready-proof-stale.md`. Start with `scripts\riftreader-workflow-status.cmd --compact-json`. Confirm OpenCode is `openai/gpt-5.5` with `desiredVariant: xhigh`. Treat visible `rift_x64` PID `22304` as process presence only; keep historical PID `27552` / HWND `0x3411E2` stale-only and movement blocked. Continue with no-input current-target reacquisition readiness unless explicit proof recovery authorization is given.
```
