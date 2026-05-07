# Current Truth

_Last updated: May 7, 2026 07:17 EDT / 11:17 UTC (live `rift_x64` PID `47560`, HWND `0x2122E`). Latest live movement truth is now the first gated-wrapper `W` 250 ms forward smoke. The wrapper preflight was green and sent one exact-target pulse; its internal post-readback failed closed only because the proof anchor crossed the 60-second age gate during postcheck. A no-input post-pulse reference/readback was immediately captured, re-promoted, and the hard current-readback gate returned `MovementAllowed=true`. The wrapper was then hardened with a pre-input proof-age-budget guard._

## Current status

| Area | Status |
|---|---|
| Live target from latest smoke | `rift_x64` PID `47560`, HWND `0x2122E`; MCP binding confirmed exact window, focused foreground target before input |
| Current coordinate proof | **green after first gated-wrapper pulse post-recovery**; post-readback `Status=valid`, `MovementAllowed=true` at `2026-05-07T11:17:40.5792893+00:00` |
| Latest hard post-smoke readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260507-071736.json` |
| Current coordinate | `X=7437.916015625`, `Y=885.2205810546875`, `Z=3049.859130859375` at `2026-05-07T11:17:40.4096580Z` |
| Latest proof anchor | `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json` generated `2026-05-07T11:17:32.0507730+00:00` |
| Latest proof method | `no-ce-riftscan-reference-multisample`, canonical source kind `riftscan-reference-validated-candidate` |
| Proof candidate | `rift-addon-coordinate-candidate-000001` at `0x2400EA32120`, source base `0x2400E970000`, source offset `0xC2120`, proof region `0x2400EA320E0`, proof offset `64` |
| Latest promotion evidence | 2 poses (`older still -> post-wrapper fresh current`); reference planar displacement `4.534089553592799`; max candidate/reference delta error `0.003989062500295404` |
| Latest reference kind | `rift-api-unit-payload-companion` from read-only wide-context memory scan; `SavedVariablesUsedAsLiveTruth=false`; reference/readback max delta `0.00398437500007276` |
| Current-readback quality | `ReadbackIntegrityStatus=ok`, samples `3`, failures `0`, stable delta `0.0` |
| Latest active input | first gated-wrapper exact-target `W` pulse for `250 ms`; baseline screenshot `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-071621-832.png`; frame-change screenshot `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-071648-391.png`; final screenshot `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-071653-129.png` |
| Latest movement proof delta | `dX=0.06640625`, `dY=0.0`, `dZ=-0.3388671875`, planar `0.3453125552354311`, spatial `0.3453125552354311` |
| Wrapper internal postcheck | `blocked-post-readback` because `proof_anchor_age_out_of_range_seconds:61.302`; post-pulse recovery re-promotion/readback was green |
| RiftScan source | `C:\RIFT MODDING\Riftscan\sessions\codex-current-coord-region-passive-20260506-230940` / `C:\RIFT MODDING\Riftscan\reports\generated\codex-current-coord-region-passive-20260506-230940-addon-coordinate-matches.json` |
| RiftScan match quality | `candidate_count=1`, `support_count=3`, `best_max_abs_distance=0`, exact match to no-CE RiftReader readback seed |
| Cheat Engine | **not used**; CE / CE Lua / debugger / watchpoints remain forbidden unless explicitly reauthorized |
| SavedVariables as live truth | **not used**; SavedVariables remain post-save snapshots only |
| Movement gate | **satisfied at latest post-recovery validation** by `satisfied_by_current_process_proof_anchor_current_readback`; because the age gate is intentionally short, rerun the hardened wrapper dry-run or hard preflight immediately before any future live input |
| Gated forward-smoke wrapper | `C:\RIFT MODDING\RiftReader\scripts\invoke-gated-forward-smoke.ps1` now includes `MinimumPostReadbackAgeBudgetSeconds` to block before input when too little proof age remains for post-readback |
| Movement/input operational state | Active input resumed only after hard gate passed; one wrapper-mediated exact-target `W` 250 ms pulse has now been proved, and future small forward pulses should use only the hardened wrapper |
| Latest tracked pointer | `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` |
| Latest handoff | `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-06-233226-riftscan-first-proof-anchor-resume-handoff.md` |

## May 7 continuation: first gated-wrapper forward smoke passed after post-recovery

The wrapper path was tested live after a fresh no-CE proof refresh:

| Fact | Value |
|---|---|
| Pre-wrapper proof refresh reference | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-wrapper-refresh-before-live-20260507-111447\current-api-reference-wide-context.json` |
| Pre-wrapper pose summary | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-wrapper-refresh-before-live-20260507-111447\riftscan-proof-current-before-gated-wrapper-20260507-111520\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-20260507-071521.json` |
| Pre-wrapper proof anchor generated | `2026-05-07T11:15:39.9032533+00:00` |
| Wrapper dry-run | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-forward-smoke-currentpid-47560-summary-20260507-111556.json`, `Status=dry-run-valid` |
| Baseline screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-071621-832.png` |
| Wrapper live summary | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-forward-smoke-currentpid-47560-summary-20260507-111630.json` |
| Input sent | exact-target `W`, `250 ms`, `post-rift-key.ps1 -RequireTargetForeground`; `SendInput` failed and AutoHotkey fallback reported success |
| Frame change | `true`, change percent `13.7569`; screenshot `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-071648-391.png` |
| Final screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-071653-129.png` |
| Wrapper postcheck status | `blocked-post-readback` only because the proof-anchor age was `61.302s`, just past the 60-second gate |
| Post-pulse recovery reference | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-wrapper-post-pulse-recovery-20260507-111705\post-wrapper-api-reference-wide-context.json` |
| Post-pulse recovery pose | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-wrapper-post-pulse-recovery-20260507-111705\riftscan-proof-post-gated-wrapper-pulse-20260507-111713\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-20260507-071714.json` |
| Post-pulse proof anchor generated | `2026-05-07T11:17:32.0507730+00:00` |
| Post-pulse hard readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260507-071736.json`, `Status=valid`, `MovementAllowed=true` |
| Coordinate delta | `dX=0.06640625`, `dY=0.0`, `dZ=-0.3388671875`, planar `0.3453125552354311` |
| Wrapper hardening | `MinimumPostReadbackAgeBudgetSeconds` added so future runs block before input if not enough proof-age budget remains |

Operational interpretation:

- The first wrapper-mediated `W` pulse did move the proof coordinate and visual frame.
- The wrapper's original postcheck failed for timing, not coordinate/proof quality; the post-pulse no-input recovery proved the current coordinate again.
- The code is now safer than the run just performed: it refuses to send if the proof anchor is too close to age expiry for the postcheck.
- No Cheat Engine path and no SavedVariables live truth were used.

## Historical May 7 continuation: third repeat forward smoke passed

This continuation again failed closed first because the prior proof anchor had aged past the 60-second gate. A default 512-byte `RRAPICOORD1` scan had live API context but not the companion unit-detail `x/y/z` payload. A read-only unit-payload scan confirmed the live `Atank` payload was present, then a wider 4096-byte `RRAPICOORD1` context scan captured the companion payload through the helper fallback. The proof anchor was re-promoted, the hard gate passed, and only then was the third `W` pulse sent.

Refresh and pre-smoke artifacts:

- expired preflight summary: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260507-065223.json`
- failed default context scan: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-proof-pose-current-refresh-before-third-smoke-20260507-105238\rift-api-reference-scan-currentpid-47560-20260507-105259-attempt3.json`
- unit-payload inspection scan: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-proof-pose-current-refresh-before-third-smoke-20260507-105238\rift-api-unit-payload-scan-currentpid-47560-name-atank.json`
- fresh wide-context reference: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-proof-pose-current-refresh-before-third-smoke-20260507-105238\pose-current-refresh-before-third-smoke-api-reference-wide-context.json`
- fresh wide-context scan: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-proof-pose-current-refresh-before-third-smoke-20260507-105238\rift-api-reference-scan-currentpid-47560-20260507-105404.json`
- fresh recovered-reference pose summary: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-proof-pose-current-third-smoke-reference-recovered-20260507-105424\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-20260507-065425.json`
- refreshed proof anchor: `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json`
- pre-smoke hard gate summary: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260507-065446.json`
- pre-smoke proof-anchor preflight file: `C:\RIFT MODDING\RiftReader\scripts\captures\assert-current-proof-coord-anchor-currentpid-47560-readback-preflight-20260507-065446.json`

Third forward smoke artifacts:

- baseline screenshot: `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-065509-596.png`
- frame-change screenshot: `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-065517-786.png`
- final screenshot: `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260507-065522-118.png`
- post-smoke hard gate summary: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260507-065532.json`
- post-smoke proof-anchor preflight file: `C:\RIFT MODDING\RiftReader\scripts\captures\assert-current-proof-coord-anchor-currentpid-47560-readback-preflight-20260507-065532.json`
- post-smoke watchset file: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-watchset-20260507-065532.json`
- post-smoke readback session: `C:\RIFT MODDING\RiftReader\scripts\sessions\proof-anchor-currentpid-47560-readback-20260507-065532`

Promotion facts:

| Fact | Value |
|---|---|
| Candidate | `rift-addon-coordinate-candidate-000001` |
| Candidate address | `0x2400EA32120` |
| Region address / offset | `0x2400EA320E0` / `64` |
| Pose count | `2` |
| Reference planar displacement | `3.8614090795978067` |
| Max candidate/reference delta error | `0.0028953125001862645` |
| Proof method | `no-ce-riftscan-reference-multisample` |
| Reference kind | `rift-api-unit-payload-companion` |
| No CE | `true` |
| Movement sent during promotion/preflight | `false` |

Third forward smoke proof facts:

| Fact | Value |
|---|---|
| Input | exact-target `W`, `250 ms`, `window-message` backend |
| Pre-smoke coordinate | `X=7437.787109375`, `Y=885.2205810546875`, `Z=3050.5166015625` at `2026-05-07T10:54:50.5192134Z` |
| Post-smoke coordinate | `X=7437.849609375`, `Y=885.2205810546875`, `Z=3050.197998046875` at `2026-05-07T10:55:36.6703454Z` |
| Delta | `dX=0.0625`, `dY=0.0`, `dZ=-0.318603515625` |
| Planar movement | `0.3246759155967834` |
| Three-pulse planar series movement | `0.9529119785083983` |
| Post-smoke status | `valid` |
| Post-smoke MovementAllowed | `true` |
| Post-smoke read failures | `0` |
| Stable across post-smoke samples | `true` |
| Frame change | `true`, change percent `8.7708` |

Operational interpretation:

- This is a **current-session, exact PID/HWND, no-CE** coordinate proof and three-pulse active forward-smoke proof.
- Three tiny active `W` pulses have now produced measurable proof-coordinate deltas and the proof anchor remained valid afterward.
- The companion-payload reference fallback is bounded to scans that also contain live Rift API probe context; it is not a SavedVariables path.
- The proof anchor is age-gated; before any further live input, rerun:

  ```powershell
  .\scripts\invoke-gated-forward-smoke.ps1 `
    -ProcessId 47560 `
    -TargetWindowHandle 0x2122E `
    -HoldMilliseconds 250 `
    -PulseCount 1 `
    -Json
  ```

- The gated wrapper performs the hard current-readback preflight before input
  and the hard current-readback postcheck after each pulse. Use `-DryRun` to run
  its no-input gate path only.

## May 7 continuation: gated wrapper added after live proof

After the third live smoke, the ad hoc exact-target key-posting flow was
captured as a narrow fail-closed wrapper:

| Item | Value |
|---|---|
| Wrapper | `C:\RIFT MODDING\RiftReader\scripts\invoke-gated-forward-smoke.ps1` |
| Regression | `C:\RIFT MODDING\RiftReader\scripts\test-invoke-gated-forward-smoke.ps1` |
| Default input | exactly one `W` pulse, `250 ms` |
| Safety caps | `HoldMilliseconds <= 1000`; `PulseCount <= 3` |
| Required target | exact `ProcessId` and `TargetWindowHandle` |
| Pre-input gate | `assert-current-proof-coord-anchor-readback.ps1` must return `Status=valid` and `MovementAllowed=true` |
| Post-input gate | same current-readback gate must remain green after each pulse |
| Age-budget gate | `MinimumPostReadbackAgeBudgetSeconds=15` by default; the wrapper blocks before input if the proof anchor is too close to expiry for a post-readback check |
| Default input backend | `post-rift-key.ps1 -RequireTargetForeground` |
| No-input mode | `-DryRun` |
| Live no-input dry run | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-forward-smoke-currentpid-47560-summary-20260507-111124.json` |
| Dry-run result | `blocked-preflight`; `MovementAttempted=false`; `MovementSent=false`; issue `proof_anchor_age_out_of_range_seconds:1006.028` |
| Live input through wrapper | first run sent one `W` 250 ms pulse: `C:\RIFT MODDING\RiftReader\scripts\captures\gated-forward-smoke-currentpid-47560-summary-20260507-111630.json`; postcheck timed out on age, then post-recovery validation passed |
| CE / SavedVariables | no CE path; SavedVariables are not used as live truth |

## Historical May 6/7 RiftScan-first no-CE forward movement proof

The resumed lane now follows the user-corrected workflow: use RiftScan for candidate acquisition, then let RiftReader import/read back/promote only fresh candidates. The older `api-probe-triplet-000007` wording is superseded by the RiftScan candidate below.

1. Re-bound exact live target: PID `47560`, HWND `0x2122E`.
2. Seeded RiftScan with a same-session no-CE RiftReader readback coordinate, then captured the containing memory region read-only:
   - RiftScan session: `C:\RIFT MODDING\Riftscan\sessions\codex-current-coord-region-passive-20260506-230940`
   - RiftScan match file: `C:\RIFT MODDING\Riftscan\reports\generated\codex-current-coord-region-passive-20260506-230940-addon-coordinate-matches.json`
   - candidate: `rift-addon-coordinate-candidate-000001`
   - absolute address: `0x2400EA32120`
   - source base/offset: `0x2400E970000 + 0xC2120`
   - support: `3` snapshots; `best_max_abs_distance=0`
3. Imported the fresh RiftScan match into RiftReader and validated readback at pose A:
   - summary: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-pivot-candidate-readback-20260506-231205\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-ui-reference.json`
   - reference/readback max delta: `0.0365722656251819`
4. Captured pose B after a bounded `1000 ms W` pulse used for candidate proof displacement:
   - summary: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-pivot-pose-b-readback-20260506-231548\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-ui-reference.json`
   - reference/readback max delta: `0.021484375`
5. Promoted the fresh no-CE proof anchor from poses A/B and validated the default current-readback gate:
   - first promotion time: `2026-05-07T03:20:26.3697670Z`
   - validation summary: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-232031.json`
   - status: `valid`; movement gate: `satisfied_by_current_process_proof_anchor_current_readback`
6. Ran a proof-gated forward smoke (`1000 ms W`) after the valid preflight:
   - baseline screenshot: `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260506-232057-700.png`
   - changed screenshot: `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260506-232107-504.png`
   - final screenshot: `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260506-232110-751.png`
   - pre-readback: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-232031.json`
   - post-readback: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-232117.json`
   - coordinate delta: `dX=0.23681640625`, `dY=0`, `dZ=-1.21630859375`, planar `1.2391483387792066`
7. Captured pose C after the proof-gated pulse and re-promoted the anchor from poses B/C:
   - pose C reference: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-pivot-pose-c-readback-20260506-232117\pose-c-ui-marker-reference.json`
   - pose C summary: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-pivot-pose-c-readback-20260506-232117\riftscan-riftreader-currentpid-47560-readback-wrapper-summary-20260506-232223.json`
   - final proof anchor generated: `2026-05-07T03:22:38.8570044Z`
   - max reference planar displacement: `1.2165525060594347`
   - max candidate/reference delta error: `0.0368164062501819`
8. Verified the current proof-anchor readback gate again:
   - summary: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-232245.json`
   - status: `valid`; `MovementAllowed=true`; `ProofAnchorMaxAgeSeconds=60`
   - current coordinate: `X=7437.0498046875`, `Y=885.2205810546875`, `Z=3054.30517578125`

Operational interpretation:

- The latest recorded proof was movement-grade for the exact live PID/HWND during its proof-anchor age window.
- Do not reuse it after process restart, HWND change, or proof-anchor age expiry; rerun target discovery and preflight.
- The current proof source is a no-CE RiftScan/RiftReader validated candidate, not a CE coord-trace source.
- SavedVariables were not used as live truth.
- CE remains out of bounds unless explicitly reauthorized.

## Historical April 30 status snapshot

| Area | Status |
|---|---|
| Client executable | changed by the April 28, 2026 update; current `rift_x64.exe` SHA256 is `33B35F2DC17BD9AF1CC2186DF2B62ED5232D77630BDB3C00895FD84C464BF3EC`, size `59918272`, LastWrite `2026-04-28 14:05:32 -04:00` |
| Low-level reader | working against current live PID `32468` |
| ReaderBridge snapshot/export | available; export matched Atank at Sanctum Watch during April 30 recovery |
| Player current read | working for read-only context; current `SelectionSource=cached-anchor` / heuristic lineage remains exploration-only, not movement proof |
| Proof coord anchor cache | stale after Rift restart; post-restart proof-anchor rebuild failed and must be rerun/fixed before movement |
| Proof coord source | not proof-grade after restart; `read-player-current` matches ReaderBridge but is heuristic/cached-anchor only, latest read address `0x2C9ABD62850` |
| Proof polling watchset | stale after restart; no post-restart required `coord-trace-coords` watchset has been promoted |
| Source-chain/accessor-family coord recovery | historical for the pre-restart session; not re-promoted after PID `32468` restart |
| CE Lua server/bootstrap | available during this pass; `cheatengine-exec.ps1 -Code 'return 123'` returned `123` |
| Telemetry preflight | mixed after restart: memory-facing is valid from `0x2C9A013A490 @ +0xD4`, but memory coords are not proof-grade; effective position falls back to addon |
| Actor yaw / pitch truth | re-found after restart via source `0x2C9A013A490`; forward basis `+0xD4/+0xD8/+0xDC`; duplicate row not yet proven in this session |
| `--read-player-orientation` reader mode | live mode works when called with explicit `--pid 32468`; artifact-only/no-PID mode remains historical-only |
| Actor-facing provenance | April 30 post-restart exact PID/HWND D/A validation confirmed behavior-backed yaw on `0x2C9A013A490 @ +0xD4`; durable owner/source recovery remains unresolved |
| Navigation preflight (`--read-navigation-current`) | blocked for movement-grade proof after restart until coord anchor/watchset is rebuilt; facing source alone is available |
| Auto-turn preflight | historical for pre-restart session; not rerun after restart because coord proof is blocked |
| Active movement (`--navigate-waypoints`) | historical for pre-restart session; active movement is currently blocked until post-restart coord proof/watchset is green |
| Navigation v3 active route gate | implementation exists, but April 23 active movement proofs are historical after this update; live route-chain promotion remains pending |
| ReaderBridge orientation probe | still not treated as a usable direct yaw/pitch source |
| Camera yaw / pitch / distance on `main` | stale / unverified after the update |
| Authoritative camera controller | not yet isolated |

## April 30 post-restart yaw recheck

After the Rift client restart, the previous current actor-truth packet became
stale because PID `41220` no longer exists. The new live target is PID `32468`,
HWND `0x15908B2`, process start `2026-04-30T16:03:29.7977969Z`.

Current post-restart yaw/facing truth:

- source object: `0x2C9A013A490`
- forward basis: `+0xD4/+0xD8/+0xDC`
- yaw formula: `atan2(forwardZ, forwardX)`
- proof artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-yaw-recheck-after-restart-20260430-121848\manual-yaw-basis-confirmation-after-restart.json`
- compact restart packet:
  - `C:\RIFT MODDING\RiftReader\docs\recovery\current-actor-yaw-restart-check.json`

Behavior proof:

- exact target: PID `32468`, HWND `0x15908B2`
- `D` yaw delta: about `-128.309°`
- `A` yaw delta: about `+127.864°`
- coordinate drift during both turn checks: `0.0`

Operational interpretation:

- yaw/facing is current for this restarted session
- the previous `0x216F2F26020 @ +0x60/+0x94` lead is historical/stale after
  restart
- the coord-source-minus-`0x48` plus `+0x60/+0x94` pattern did not survive this
  restart as the yaw source
- movement-grade coord proof is still blocked: proof coord anchor reacquisition
  armed debug-register access watchpoints but received no verified hits against
  explicit current coord candidates
- bounded neighborhood recovery captured the current yaw object and coord-like
  candidates, but exact ReaderBridge-coordinate triplets remained in
  heuristic/current-candidate lineage only; see
  `C:\RIFT MODDING\RiftReader\docs\recovery\current-coord-proof-blocker.json`
- active movement must stay blocked until a post-restart `coord-trace-coords`
  watchset is rebuilt and validated
## April 30 actor-yaw recovery truth

April 30, 2026 live recovery supersedes conflicting April 28 session-bound
addresses below. The older April 28 sections are retained as historical proof
context.

Compact machine-readable truth packet:

- `C:\RIFT MODDING\RiftReader\docs\recovery\current-actor-truth.json`
- validation guard:
  - `C:\RIFT MODDING\RiftReader\scripts\validate-current-actor-truth.ps1`

Current live target:

- process: `rift_x64`
- PID: `41220`
- HWND: `0xBD0D94`
- character/location: `Atank` / `Sanctum Watch`

Current proof-grade coord source:

- source object: `0x216F2F26020`
- canonical coord triplet: `0x216F2F26068`
- source coord offset: `+0x48`
- proof-anchor refresh artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\proof-coord-anchor-refresh.json`
- post-active proof-anchor refresh artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\proof-coord-anchor-after-active-forward-smoke.json`
- proof polling watchset artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\proof-polling-watchset-after-yaw-promotion.json`
- post-active proof polling watchset artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\proof-polling-watchset-after-active-forward-smoke.json`
- current default watchset:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\proof-polling-watchset.json`
- required watchset region:
  - `coord-trace-coords` at `0x216F2F26068`, length `12`
- match: `CoordMatchesWithinTolerance=true`
- deltas vs ReaderBridge at refresh:
  - `DeltaX = -0.0043945312`
  - `DeltaY = -0.0009765625`
  - `DeltaZ = 0.0014648438`

Current behavior-backed actor-facing/yaw source:

- source object: `0x216F2F26020`
- primary forward basis: `+0x60/+0x64/+0x68`
- duplicate forward basis: `+0x94/+0x98/+0x9C`
- primary/duplicate agreement after promotion:
  - duplicate delta magnitude: `0.000003339988166361308`
  - duplicate agreement: `true`
- canonical formulas:
  - yaw = `atan2(forwardZ, forwardX)`
  - pitch = `atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))`

Live exact-window D/A validation:

- validation artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\actor-yaw-candidate-test-da-ahk-700ms.json`
- candidate screen:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\actor-yaw-validation-candidate-screen.json`
- input: exact target AutoHotkey `d` then `a`, `700 ms` holds
- foreground guard: target remained `0xBD0D94` / PID `41220`
- primary basis response:
  - forward yaw delta: about `-129.553°`
  - reverse yaw delta: about `+129.603°`
  - player coord drift: `0.0`
- duplicate basis response:
  - forward yaw delta: about `-129.554°`
  - reverse yaw delta: about `+129.604°`
  - player coord drift: `0.0`
- top pointer-hop candidates were nonresponsive except weak rank 9
  `0x216A250A590 @ +0xD4`, which moved only about `+3.650°/-2.916°`;
  it is not preferred over the owner/source coord object.

Promotion and validation after updating
`C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json`:

- `--read-player-orientation --pid 41220` resolved
  `0x216F2F26020 @ +0x60/+0x94`
- telemetry preflight is green:
  - memory coords valid: `true`
  - facing valid: `true`
  - effective position source: `memory`
  - effective facing source: `memory-facing`
- `--read-navigation-current` is green:
  - current address: `0x216F2F26068`
  - facing status: `available`
  - facing source: `behavior-backed-memory-facing`
  - facing source address: `0x216F2F26020`
  - facing forward basis offset: `0x60`
- turn-only auto-turn preflight is green:
  - script:
    - `C:\RIFT MODDING\RiftReader\scripts\navigation\run-a-to-b-prototype.ps1`
  - mode:
    - `-PreflightOnly -AutoTurnBeforeMove`
  - custom current-session waypoint file:
    - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\autoturn-current-session-waypoints.json`
  - log:
    - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\autoturn-preflight-only.ndjson`
  - start yaw/delta:
    - `1.450°` yaw, `42.135°` absolute delta, turn `right`
  - final yaw/delta:
    - `48.287°` yaw, `4.702°` absolute delta, turn hint `left`
  - pulses:
    - three exact-target `d` pulses at `75 ms`
  - movement:
    - no forward movement was sent; this was preflight-only
- smallest active forward smoke is green:
  - route file:
    - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\active-forward-smoke-waypoints.json`
  - log:
    - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\active-forward-smoke.ndjson`
  - stdout:
    - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\active-forward-smoke.stdout.txt`
  - compact summary:
    - `C:\RIFT MODDING\RiftReader\scripts\navigation\summarize-a-to-b-log.ps1 -LogFile <active-forward-smoke.ndjson>`
    - emits `lastNavigationSummary` with status, stop reason, pulse count,
      distances, positions, and computed planar movement
  - command mode:
    - `--navigate-waypoints`
  - status:
    - `success`
  - stop reason:
    - `arrived`
  - anchor source:
    - `coord-trace-anchor`
  - preflight:
    - yaw `48.287°`, bearing `48.287°`, heading delta `0.000°`
  - movement input:
    - two `w` pulses
  - initial/final planar distance:
    - `2.600 -> 1.890`
  - initial position:
    - `X = 7260.58544921875`
    - `Y = 875.6790161132812`
    - `Z = 3052.92138671875`
  - final position:
    - `X = 7261.05712890625`
    - `Y = 875.696533203125`
    - `Z = 3053.451904296875`
  - planar movement:
    - about `0.710`
  - post-active telemetry after proof refresh:
    - memory coords valid: `true`
    - facing valid: `true`
    - effective position source: `memory`
    - effective facing source: `memory-facing`
  - post-active navigation read:
    - current address: `0x216F2F26068`
    - within arrival radius: `true`
    - facing source: `0x216F2F26020 @ +0x60`
    - yaw/bearing delta: about `0.027°`

Operational interpretation:

- `0x216F2F26020 @ +0x60/+0x94` is the current live behavior-backed
  actor-facing/yaw truth for this PID/HWND.
- The old behavior-backed lead `0x216FE3C6280 @ +0xD4` is stale/unreadable in
  this live session and must not be used unless separately re-proven.
- These addresses are still session-bound; after restart/client update,
  refresh proof coord readiness and rerun short exact-target yaw validation
  before treating them as current.
- Durable owner/source recovery is still unresolved.

## Historical April 28 proof coord anchor truth

_Historical: this section is retained as proof context only. April 30, 2026
re-promoted current coord truth to `0x216F2F26068` on source object
`0x216F2F26020`; use the April 30 section above for current live-session
addresses._

April 28 live validation established the then-current proof-grade movement
coord source:

- live process: `rift_x64` PID `41220`
- target window: `0xBD0D94`
- canonical live coord region: `0x216F87CDE18`
- canonical live coord-trace object base: `0x216F87CDE18`
- current trace-linked source object: `0x216F87CDDD0`
- source-object coord offset: `+0x48`
- verification method: `coord-triplet-access`
- match source: `readerbridge-live`
- sample memory coords after final active-proof ReaderBridge refresh:
  - `X = 7449.1753`
  - `Y = 863.58527`
  - `Z = 2973.069`
- ReaderBridge deltas at validation:
  - `DeltaX = -0.0043945312`
  - `DeltaY = -0.004699707`
  - `DeltaZ = -0.00073242193`
- current proof cache file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json`

Operational interpretation:

- this validated coord-trace anchor remains the **only** proof-grade movement
  source
- `read-player-current.ps1`, heuristic current-player anchors, and cached
  current-player snapshots remain read-only/exploration aids only
- if a proof watchset does not include this validated coord-trace coord region,
  treat it as a blocker instead of silently accepting a stale/candidate source
- current proof watchset file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\proof-polling-watchset.json`
- the current proof watchset contains required region `coord-trace-coords` at
  `0x216F87CDE18`, length `12`
- active route movement was **not** rerun in this April 28 pass; use the fresh
  proof anchor again immediately before any movement-polling proof

## Historical April 28 source-chain / accessor-family coord evidence

_Historical: retained for recovery pattern/provenance context. Do not treat the
April 28 object addresses below as current unless separately re-proven._

The April 28 current-session source-chain capture rebuilt the coord
source-chain on PID `41220`:

- selected/source object: `0x216F87CDDD0`
- cluster trace instruction: `0x7FF7879B117E`
- cluster pattern offset: `rift_x64.exe+0x931169`
- source container load: `0x7FF7879B1133` / `mov rcx,[rax+78]`
- source object load: `0x7FF7879B1137` / `mov rdi,[rcx+rdx*8]`
- source resolve target: `0x7FF787705C30`
- accessor return offset: `72` (`+0x48`)
- suggested source-chain scan: `rift_x64.exe+0x931133`
- suggested accessor scan: `rift_x64.exe+0x685C30`

Script fix validated in this pass:

- `C:\RIFT MODDING\RiftReader\scripts\resolve-proof-coord-anchor.ps1` now uses
  named hashtable splatting when invoking `trace-player-coord-write.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-trace-cluster.ps1` now
  uses named hashtable splatting, a 12-byte access watch window, and
  `MaxCandidates=4`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-discovery-chain.ps1` now accepts
  and propagates exact `-ProcessId` / `-TargetWindowHandle` through the
  provenance chain instead of relying on process-name-only defaults
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-source-accessor-family.ps1`
  and `C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1`
  now support exact target args for reader calls and record the target in their
  output artifacts
- `C:\RIFT MODDING\RiftReader\scripts\refresh-actor-facing-discovery.ps1` now
  passes the exact live target into `refresh-discovery-chain.ps1` during
  `-RunProvenance`
- both patched paths were exercised live and then covered by the source-chain
  regression tests listed below

## Historical April 28 actor yaw / pitch truth

_Historical: April 30 re-promoted actor yaw/facing to
`0x216F2F26020 @ +0x60/+0x94`; the April 28 `+0xD4` lead below is stale in the
current April 30 proof packet unless separately re-proven._

April 28 live agentic discovery promoted a then-current session-bound lead:

- canonical live source address: `0x216FE3C6280`
- canonical forward basis row:
  - `X = +0xD4`
  - `Y = +0xD8`
  - `Z = +0xDC`
- canonical formulas:
  - yaw = `atan2(forwardZ, forwardX)`
  - pitch = `atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))`

April 28 live checks on the promoted lead:

- `refresh-actor-facing-discovery.ps1 -RestartSession -StimulusMode AutoHotkey`
  promoted `0x216FE3C6280 @ +0xD4`
- reversible validation observed yaw peaks of about `59.055°` and `74.600°`
  with `0.0` coord drift across one D/A cycle
- `dotnet ... -- --pid 41220 --read-player-orientation --json` resolved the
  same behavior-backed lead
- telemetry preflight used memory-facing from `0x216FE3C6280 @ +0xD4`
- `refresh-actor-facing-discovery.ps1 -RunProvenance -ProcessId 41220
  -TargetWindowHandle 0xBD0D94` completed successfully after exact-target
  plumbing was added
- provenance summary: `SuccessfulSteps=1`, `FailedSteps=0`,
  `ProvenanceStatus=confirmed`

Operational interpretation:

- the April 28 live actor-facing truth was the validated `0xD4` forward row on
  `0x216FE3C6280`
- this is facing-only truth; it is not the movement coord source
- the April 23 actor-facing address `0x12CC0FA0F70 @ +0xD4` and earlier April
  source-chain/accessor-family addresses are historical after the April 28
  client update unless separately re-proven
- the exact-target post-update provenance chain was green for that live
  PID/HWND, but it remains session-bound evidence; rerun it after a client
  restart/update before treating addresses as current again

## Historical April 28 telemetry and navigation validation

_Historical: retained as the earlier post-update movement proof. The April 30
section above is the current actor-yaw/coord truth after the later live
recovery._

April 28 telemetry preflight after final active-proof ReaderBridge refresh on
**April 28, 2026**:

- memory coords available: `true`
- memory coords valid: `true`
- memory facing available: `true`
- facing valid: `true`
- effective position source: `memory`
- effective facing source: `memory-facing`
- position source address: `0x216F87CDE18`
- facing source address: `0x216FE3C6280`
- facing forward basis offset: `0xD4`

Read-only navigation preflight was also validated with the active-proof
current-session smoke waypoint file:

- waypoint file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\post-update-inworld-20260428-141625\current-session-smoke-waypoints-active-proof.json`
- command mode: `--read-navigation-current`
- anchor source: `coord-trace-anchor`
- current address: `0x216F87CDE18`
- planar distance to smoke destination after active proof: about `1.784`
- arrival radius: `2.1`
- within arrival radius: `true`
- facing source: `0x216FE3C6280 @ +0xD4`
- signed bearing delta before the active proof: about `0.065°`
- suggested turn direction: `right`

Smallest active `--navigate-waypoints` smoke proof also passed:

- runner:
  - `C:\RIFT MODDING\RiftReader\scripts\navigation\run-a-to-b-prototype.ps1`
- log:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\post-update-inworld-20260428-141625\a-to-b-prototype-active-proof.ndjson`
- route file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\post-update-inworld-20260428-141625\current-session-smoke-waypoints-active-proof.json`
- status: `success`
- stop reason: `arrived`
- anchor source: `coord-trace-anchor`
- pulse count: `1`
- input: one `w` pulse for `250 ms`
- initial planar distance: `2.5991395661`
- final planar distance: `1.7840590320`
- elapsed: `2406 ms`
- initial position:
  - `X = 7448.36083984375`
  - `Y = 863.5816650390625`
  - `Z = 2973.037109375`
- final position:
  - `X = 7449.17529296875`
  - `Y = 863.5852661132812`
  - `Z = 2973.069091796875`

No active multi-segment route-chain proof was run during this post-update
validation slice.

## Validation commands from this pass

These checks passed after the April 28 update and the small script fixes:

- PowerShell parser checks for:
  - `C:\RIFT MODDING\RiftReader\scripts\resolve-proof-coord-anchor.ps1`
  - `C:\RIFT MODDING\RiftReader\scripts\capture-player-trace-cluster.ps1`
- whitespace check:
  - `git diff --check -- scripts/resolve-proof-coord-anchor.ps1 scripts/capture-player-trace-cluster.ps1`
- source-chain recovery regression:
  - `C:\RIFT MODDING\RiftReader\scripts\test-player-source-chain-recovery.ps1`
- source-chain fresh rebuild regression:
  - `C:\RIFT MODDING\RiftReader\scripts\test-player-source-chain-fresh-rebuild.ps1`
- actor-facing proof suite:
- `C:\RIFT MODDING\RiftReader\scripts\test-actor-facing-proof-suite.ps1`
- navigation proof suite, non-live/default mode:
  - `C:\RIFT MODDING\RiftReader\scripts\navigation\test-navigation-proof-suite.ps1`
- live exact-target provenance chain:
  - `C:\RIFT MODDING\RiftReader\scripts\refresh-actor-facing-discovery.ps1 -RunProvenance -ProcessId 41220 -TargetWindowHandle 0xBD0D94`
- final post-provenance ReaderBridge refresh, proof anchor, telemetry preflight,
  and read-only navigation-current sanity checks
- exact-target proof polling watchset export:
  - `C:\RIFT MODDING\RiftReader\scripts\export-proof-polling-watchset.ps1 -ProcessId 41220 -TargetWindowHandle 0xBD0D94 -Json`
- proof watchset reader smoke:
  - `dotnet ... -- --pid 41220 --record-session --session-watchset-file scripts\captures\proof-polling-watchset.json --session-sample-count 2 --session-interval-ms 100 --json`
- active movement smoke proof:
  - `C:\RIFT MODDING\RiftReader\scripts\navigation\run-a-to-b-prototype.ps1 -ProcessId 41220 -TargetWindowHandle 0xBD0D94 -WaypointFile <active-proof-route> -UseExistingWaypoints -AutoConfirm -SkipRefresh -ArrivalRadius 2.1 -MaxTravelSeconds 5`
- final post-active ReaderBridge refresh, proof anchor, telemetry preflight, and
  read-only navigation-current sanity checks

## Broken, stale, or pending right now

- April 23 live addresses are historical after the April 28 client update:
  - old coord anchor: `0x12C9B02B888`
  - old actor-facing lead: `0x12CC0FA0F70 @ +0xD4`
- active single-segment smoke movement has been re-promoted after the update;
  multi-segment route-chain movement is still pending
- actor-facing selector/source-chain provenance is green only for the current
  live PID/HWND; it is not durable across restarts or future client updates
- proof polling watchset is current for PID `41220` / HWND `0xBD0D94`, but it
  must be rebuilt after client restart/update before movement proof
- camera yaw/pitch/distance on `main` remains stale/unverified after the update
- `--read-player-orientation` without explicit `--pid` / `--process-name`
  remains the historical artifact-only path until the owner/source artifact path
  is rebuilt

## Canonical scripts on `main`

- `C:\RIFT MODDING\RiftReader\scripts\resolve-proof-coord-anchor.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-trace-cluster.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-source-chain.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-actor-facing-discovery.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\profile-actor-orientation-keys.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\invoke-gated-forward-smoke.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\navigation\test-navigation-proof-suite.ps1`

## Evidence folder

Post-update recovery evidence for this pass is under:

- `C:\RIFT MODDING\RiftReader\scripts\captures\post-update-inworld-20260428-141625`

Key files:

- `process-info.json`
- `smart-capture-player-family.stdout.txt`
- `capture-player-source-chain-refreshcluster-size12-max4.stdout.txt`
- `resolve-proof-coord-anchor-after-sourcechain.stdout.txt`
- `resolve-proof-coord-anchor-final-refresh.stdout.txt`
- `read-player-orientation-after-facing-promotion.stdout.txt`
- `telemetry-preflight-after-facing-promotion.stdout.txt`
- `current-session-smoke-waypoints.json`
- `read-navigation-current-current-smoke.stdout.txt`
- `refresh-actor-facing-discovery-runprovenance-exact-target.stdout.txt`
- `refresh-readerbridge-export-post-provenance.stdout.txt`
- `resolve-proof-coord-anchor-post-provenance-after-readerbridge-refresh.stdout.txt`
- `telemetry-preflight-post-provenance-after-readerbridge-refresh.stdout.txt`
- `current-session-smoke-waypoints-post-provenance.json`
- `read-navigation-current-post-provenance-after-readerbridge-refresh.stdout.txt`
- `export-proof-polling-watchset-exact-target.stdout.txt`
- `record-session-proof-watchset-smoke.stdout.txt`
- `watchset-record-session-smoke`
- `current-session-smoke-waypoints-active-proof.json`
- `run-a-to-b-prototype-active-proof.stdout.txt`
- `a-to-b-prototype-active-proof.ndjson`
- `resolve-proof-coord-anchor-after-active-proof.stdout.txt`
- `telemetry-preflight-after-active-proof.stdout.txt`
- `read-navigation-current-after-active-proof.stdout.txt`

## Camera script location note

The currently documented live camera helpers are **not present** on the `main`
worktree during this pass.

The active camera workflow currently lives on:

- branch: `feature/camera-orientation-discovery`
- worktree: `C:\RIFT MODDING\RiftReader_camera_feature`

Relevant scripts there:

- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\read-live-camera-yaw-pitch.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\find-live-camera-angle-candidates.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\test-camera-stimulus.ps1`

Do not treat camera outputs as current truth on `main` until the camera path is
revalidated on the updated client.
