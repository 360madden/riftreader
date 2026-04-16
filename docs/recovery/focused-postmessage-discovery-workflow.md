# Focused PostMessage Discovery Workflow

Use this as the **backup detailed workflow** for fast live recovery and
discovery when a feature depends on controlled Rift input plus live memory
readback.

Machine-readable companion:

- `C:\RIFT MODDING\RiftReader\docs\recovery\focused-postmessage-discovery-prompt.json`

This workflow was the one that recovered actor yaw quickly on
`codex/actor-yaw-pitch` after slower earlier passes failed.

Primary lesson:

- the bottleneck was not just candidate search
- the bottleneck was the **workflow harness**
- once focus, delivery mode, timing, and evidence isolation were corrected, the
  real candidate surfaced and validated quickly

## When to use this workflow

Use this workflow when all of the following are true:

1. the target feature needs live in-game input to reveal a memory signal
2. the feature can be measured by before/after memory captures
3. the game may be running on Desktop 2 or another isolated desktop
4. screenshot-based UI checks are weak or non-authoritative for that topology
5. you need a results-first discovery ladder, not a slow manual probe loop

Examples:

- actor yaw / pitch
- camera yaw / pitch / zoom
- other turn/look/orbit driven features
- input-correlated state changes where readback is memory-first

## Core principles

### 1. Focus first, then PostMessage

For this workflow, the trusted live-input path is:

1. focus Rift
2. verify Rift actually became foreground
3. send gameplay input via `PostMessage`

Do **not** treat these as equivalent:

- background `PostMessage`
- foreground `SendInput`
- focused `PostMessage`

Only the third path is the trusted branch default for this workflow.

### 1b. Mouse input is a separate lane

Do not overgeneralize the focused-`PostMessage` keyboard win to RMB / drag /
wheel style input.

For mouse/camera work:

1. bind the Rift process and a real main window handle
2. focus Rift
3. verify Rift is actually foreground
4. only then send mouse input

If any of those fail:

- stop
- require operator intervention
- do not try to salvage the pass with a background `PostMessage` fallback

The focused-`PostMessage` rule is for keyboard/chat delivery. Mouse delivery is
only trusted when window acquisition and focus are already clean.

### 2. Desktop-2 screen pixels are not authority

If Rift is isolated on Desktop 2:

- memory reads may still be good
- focused key delivery may still be good
- pixel capture / screenshot UI gates may be misleading

Therefore:

- trust memory deltas first
- use screenshot safety gates only when the desktop is actually visible

### 3. Isolate aggressive evidence

Do not mix aggressive discovery with clean historical evidence.

Always use dedicated aggressive artifacts so broad noisy passes do not poison:

- trusted candidate ledgers
- clean history files
- handoff evidence

### 4. Broad screen first, pin second

Do not start with long bespoke one-offs.

Preferred order:

1. broad candidate screen
2. paired opposite-direction preflight
3. pin best candidates
4. full recovery only on the best few

### 5. Remove human pacing from AI-driven recovery

If the AI is driving a multi-step recovery sequence, repeated operator warning
countdowns can create false idle drift between phases.

For AI-driven runs:

- use the external operator warning once if needed
- suppress repeated script-side warning delays inside the sequence

This was the key reason the winning actor-yaw source initially failed as
`idle_drift` and then passed once the warning delay was removed.

### 6. Unattended wrappers should degrade, not abort

If the only failure is the ReaderBridge refresh lane, the unattended workflow
should retry the screen without forced refresh instead of aborting the entire
discovery pass.

Likewise, once a full recovery proves a winner, the unattended workflow should
stop immediately instead of continuing to spray more live inputs across lower
value candidates.

### 7. Frame results by purpose, harness, and signal

When documenting a live pass, always state the purpose of the run before the
raw result.

Use this reporting structure:

1. `Purpose`
   - procedure validation
   - discovery pass
   - pinned proof pass
   - regression retest
2. `Harness status`
   - whether the mechanism itself worked
3. `Signal status`
   - whether the target regions/candidates produced useful evidence
4. `Safe interpretation`
   - what the result means
   - what it does **not** mean
5. `Next decision`
   - what should happen next

Example:

- purpose: procedure validation pass
- harness status: success
- signal status: empty
- safe interpretation: the RMB test procedure worked, but the sampled regions
  did not surface a camera-bearing signal; do not classify that as a mouse
  harness failure
- next decision: keep the harness and revisit the candidate regions later

This matters because vague wording like "the pass did not surface candidates"
can be misread as a harness failure and drive the wrong follow-up repair.

## Required preconditions

Before any live discovery run:

1. Rift is running
2. the correct Rift window is available
3. if Rift is on Desktop 2, it can still be manually activated there
4. the reader baseline is healthy enough to read:
   - player current
   - coord anchor
   - target live feature readback path

If the game window is missing, crashed, or cannot take focus:

- stop immediately
- do not fall through to `SendInput`
- require operator intervention

## Step 0: verify the surviving read baselines

Run these first after an update or before a new recovery campaign:

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --readerbridge-snapshot --json
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-current --json
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-coord-anchor --json
```

If these are broken, fix the reader baseline first.

## Step 1: use aggressive artifact isolation

Use dedicated files like:

- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-ledger.aggressive.ndjson`
- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-screen.aggressive.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-screen-history.aggressive.ndjson`
- `C:\RIFT MODDING\RiftReader\scripts\captures\post-update-triage-bundle.aggressive.json`

If adapting this workflow for another feature, create the same split:

- clean outputs
- aggressive outputs

## Step 2: use focused live input, not generic live input

Canonical live-input helper:

- `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1 -RequireTargetFocus`

Rules:

- if focus verification fails, stop
- do not silently fall back to `SendInput`
- do not treat a failed background path as proof the candidate is dead

## Step 3: use a paired opposite-direction preflight

For any rotational feature, use a paired preflight:

- one direction
- then the opposite direction

For actor yaw on this branch, the working pair was:

- `D`
- `A`

Why:

- a single stimulus can still catch noise
- a paired preflight gives stronger evidence:
  - stable source
  - opposite-sign deltas
  - bounded idle drift between the two preflights

## Step 4: broad screen command pattern

Preferred orchestrator:

- `C:\RIFT MODDING\RiftReader\scripts\screen-actor-orientation-candidates.ps1`

Desktop-2 aggressive pattern:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\screen-actor-orientation-candidates.ps1" `
  -ProcessName "rift_x64" `
  -MaxHits 16 `
  -DualKeyPreflight `
  -PreflightKey "D" `
  -SecondaryPreflightKey "A" `
  -RetestLedgerRejected `
  -FullRecoveryLimit 4 `
  -MinimumYawResponseDegrees 0.5 `
  -MaxCoordDrift 0.35 `
  -MaxInterPreflightIdleDriftDegrees 8 `
  -RequireTargetFocus `
  -SkipUiClearCheck `
  -SkipLiveInputWarning `
  -RefreshReaderBridge `
  -LedgerFile "C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-ledger.aggressive.ndjson" `
  -HistoryFile "C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-screen-history.aggressive.ndjson" `
  -RecoveryOutputDirectory "C:\RIFT MODDING\RiftReader\scripts\captures\screening\aggressive" `
  -OutputFile "C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-screen.aggressive.json"
```

Preferred unattended wrapper:

- `C:\RIFT MODDING\RiftReader\scripts\run-aggressive-actor-yaw-discovery.ps1`

Unattended expectations:

- stop on first proven yaw winner
- retry without `RefreshReaderBridge` if the refresh lane is the only failing layer

These unattended expectations were live-validated on April 15, 2026:

- the wrapper recovered yaw successfully after a forced-refresh failure
- the wrapper retried without refresh
- the wrapper stopped immediately after the first validated winner

## Step 5: how to interpret a broad screen

When a candidate appears:

### Good signs

- source stable before/after stimulus
- coord drift near zero
- clear nonzero yaw delta
- opposite-sign dual-key preflight deltas
- bounded inter-preflight idle drift

### Bad signs

- source drift
- high coord drift
- same-direction paired responses
- only tiny deltas
- strong deltas plus huge no-input drift

Important:

- a candidate that fails only on idle consistency may still be real
- inspect whether the workflow timing itself introduced that drift

## Step 6: pin the best candidates early

Once a candidate shows strong preflight signal, pin it immediately.

Do not keep treating it like a generic screen candidate.

Pinned recovery pattern:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\recover-actor-orientation.ps1" `
  -Json `
  -PinnedSourceAddress "<source>" `
  -PinnedBasisForwardOffset "<basis>" `
  -RequireTargetFocus `
  -SkipUiClearCheck `
  -SkipLiveInputWarning `
  -OrientationCandidateLedgerFile "C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-ledger.aggressive.ndjson" `
  -OutputFile "C:\RIFT MODDING\RiftReader\scripts\captures\screening\aggressive\recovery-<token>.json"
```

## Step 7: treat warning-countdown-induced drift as workflow contamination

If a strong pinned candidate fails with:

- `idle_drift`

check whether:

- repeated live warning countdowns
- operator pauses
- extra focus delays
- refresh delays

were inserted between:

- baseline and first stimulus
- first stimulus and second stimulus

If yes, rerun the same candidate with warning delays removed before rejecting it.

This was the decisive correction in the successful actor-yaw recovery.

## Step 8: only then escalate to triage/watch-region narrowing

If broad screen plus pinned recovery still does not yield a winner:

1. run post-update triage
2. sample watch regions
3. only then consider widening the finder or using heavier manual reintegration

Pattern:

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --post-update-triage --recovery-bundle-file C:\RIFT MODDING\RiftReader\scripts\captures\post-update-triage-bundle.aggressive.json --max-hits 24 --json

dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --sample-triage-watch-regions --recovery-bundle-file C:\RIFT MODDING\RiftReader\scripts\captures\post-update-triage-bundle.aggressive.json --max-hits 24 --json
```

## Step 9: promote winners quickly

Once a candidate is proven:

1. save the winning artifact
2. add a dated analysis report
3. update `current-truth.md`
4. record the exact source address and basis offset
5. preserve the failed-first-pass artifact if it explains a workflow lesson

## The actor-yaw example this workflow recovered

Proven winning actor-yaw source:

- source address: `0x245D78DCB50`
- basis forward offset: `0xD4`

Successful proof artifact:

- `C:\RIFT MODDING\RiftReader\scripts\captures\screening\aggressive\recovery-245d78dcb50-basis-d4.manual.nowarning.json`

Important lesson from that recovery:

- the correct candidate was found early
- it initially failed because of workflow timing
- it passed once the repeated warning delay was removed

## Reusable checklist for future feature discovery

Use this exact checklist when adapting the workflow to other live features:

1. verify baseline reader health
2. isolate aggressive artifacts
3. determine trusted input delivery for the feature
4. enforce focus if Rift needs it
5. skip non-authoritative screen gates for hidden-desktop runs
6. use paired opposite-direction or paired contrast stimuli
7. broad screen first
8. pin strong candidates early
9. remove human pacing from AI-driven sequences
10. only then escalate to triage or deeper manual work
11. promote winners into truth immediately

## Do not repeat these mistakes

- do not assume background delivery is always enough
- do not assume `SendInput` is equivalent to focused `PostMessage`
- do not trust hidden-desktop screenshot gates as authority
- do not reject a strong candidate before checking whether the workflow timing caused the failure
- do not mix aggressive noisy evidence into the clean ledger
- do not keep broad-screening indefinitely once a strong pinned candidate appears

## Related references

- `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
- `C:\RIFT MODDING\RiftReader\docs\recovery\rebuild-runbook.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-15-actor-yaw-focused-postmessage-recovery.md`
- `C:\RIFT MODDING\RiftReader\docs\input-safety.md`
