# 2026-04-17 actor-yaw `main` rediscovery and source-chain refresh

## Summary

Two things are true on `main` as of April 17, 2026:

1. the module-pattern source-chain rebuild is working again
2. the selector-owner debugger trace is still blocked, so the reliable live
   actor-yaw recovery path is still the focused-PostMessage screen/pin/prove
   workflow rather than the old debugger-first rebuild lane

The fresh validated actor-yaw winner for this pass was:

- source address: `0x1EC9B977D20`
- basis forward offset: `0xD4`
- proof artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\screening\aggressive\recovery-1ec9b977d20-basis-d4.20260417.json`

## Commands run

### Source-chain refresh

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-player-source-chain.ps1 -Json -RefreshCluster
```

Observed result:

- success
- `SourceObjectAddress = 0x1577AC2FB60`
- `SourceContainerLoad = 0x7FF6491C55C3`
- `SourceObjectLoad = 0x7FF6491C55C7`
- `SourceResolveTarget = 0x7FF648F1A040`
- suggested source-chain pattern scan was found again in `rift_x64.exe`

Implication:

- the source-chain artifact is no longer the blocking lane on `main`

### Selector-owner trace

```powershell
C:\RIFT MODDING\RiftReader\scripts\trace-player-selector-owner.ps1 -Json -RefreshSourceChain
```

Observed result:

- failure
- status file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.status.txt`
- stage: `debug-ready`
- error:
  - `Debugger attach did not become ready. Attempts: interface-2: debugger not ready after 10000ms; default: debugger not ready after 10000ms; interface-1: debugger not ready after 10000ms`
- attach-failure ledger was appended:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\ce-debugger-attach-failures.csv`

Implication:

- the selector-owner rebuild lane remains blocked by debugger readiness
- this should not be treated as proof that actor yaw is unavailable

## Live actor-yaw rediscovery result

### Broad-screen observation

Unpinned live rediscovery was noisy:

- an unpinned `A` proof produced a real yaw-like delta but the source drifted
- the unattended `D`-first aggressive ledger produced only
  `stable_but_nonresponsive`
- a focused `A`-first broad screen also produced only
  `stable_but_nonresponsive`

This meant the workflow needed to adapt at the **pinning step**, not by simply
searching wider.

### Winning tactic

The decisive tactic was:

1. treat the drifted-but-responsive `A` result as a real candidate family
2. pin that exact source and basis
3. prove it with opposite-direction `A` and `D`

### Timeline-backed pinned proofs

Pinned `A` proof:

- artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\stimulus-timelines\20260417-054603-a.ndjson`
- stable source:
  - `0x1EC9B977D20`
- yaw delta:
  - `121.17712256117235`
- coord drift:
  - `0.0`

Pinned `D` proof:

- artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\stimulus-timelines\20260417-054903-d.ndjson`
- stable source:
  - `0x1EC9B977D20`
- yaw delta:
  - `-123.29844314015156`
- coord drift:
  - `0.0`

Full recovery:

- artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\screening\aggressive\recovery-1ec9b977d20-basis-d4.20260417.json`
- `YawRecovered = true`
- `PitchRecovered = true`
- `IdleConsistencyPass = true`
- `A` yaw delta:
  - `123.18898014680917`
- `D` yaw delta:
  - `-120.25020207335457`
- coord drift:
  - `0.0` for both directions

## Safe interpretation

What this means:

- actor yaw is validated again on `main`
- basis family `0xD4` remains the trusted basis family
- source-chain module-pattern recovery is healthy again

What this does **not** mean:

- the debugger-backed selector-owner lane is fixed
- the stale owner-components artifact is current
- every unpinned candidate returned by the read-only pointer-hop search is
  trustworthy by itself

## Recommended operational rule

Until selector-owner trace is healthy again:

- screen actor-yaw candidates with `A` primary and `D` secondary
- if `A` produces a real yaw response but the source drifts, pin it early
- prove the pinned source with opposite-direction `A`/`D`
- do not keep broad-screening indefinitely once that pattern appears
