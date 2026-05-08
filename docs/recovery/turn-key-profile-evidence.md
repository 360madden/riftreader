# Turn key profile evidence

_Generated from `scripts/summarize_turn_key_profiles.py`. This report is compact evidence only; individual run summaries remain authoritative._

| Generated UTC | Run | Keys | Modes | Hold | Attempts | Classifications | Delivery | Max abs yaw | Max coord delta | Promoted | Issues |
|---|---|---|---|---:|---:|---|---|---:|---:|---:|---|
| 2026-05-08T07:28:34.758141Z | `scripts\captures\turn-key-profile-currentpid-33912-20260508-072834\turn-key-profile-summary.json` | `a,d` | `post-message` | 125 | 4 | `planned:4` | `unknown:4` | 0.0000 | 0.0000 | 0 | - |
| 2026-05-08T07:32:48.987912Z | `scripts\captures\turn-key-profile-currentpid-33912-20260508-072955\turn-key-profile-summary.json` | `a,d` | `post-message` | 125 | 4 | `before-readback-failed:3, no-turn:1` | `unknown:4` | 0.0000 | 0.0000 | 0 | - |
| 2026-05-08T07:36:45.898650Z | `scripts\captures\turn-key-profile-currentpid-33912-20260508-073539\turn-key-profile-summary.json` | `d` | `post-message` | 125 | 1 | `turn-candidate:1` | `unknown:1` | 8.3837 | 0.0000 | 0 | - |
| 2026-05-08T07:39:33.249972Z | `scripts\captures\turn-key-profile-currentpid-33912-20260508-073726\turn-key-profile-summary.json` | `d` | `post-message` | 125 | 2 | `no-turn:2` | `unknown:2` | 0.0000 | 0.0000 | 0 | - |
| 2026-05-08T07:46:23.930866Z | `scripts\captures\turn-key-profile-currentpid-33912-20260508-074456\turn-key-profile-summary.json` | `d` | `foreground-sendinput` | 125 | 1 | `no-turn:1` | `unknown:1` | 0.0000 | 0.0000 | 0 | - |
| 2026-05-08T07:53:24.559226Z | `scripts\captures\turn-key-profile-currentpid-33912-20260508-075123\turn-key-profile-summary.json` | `Left,Right` | `foreground-sendinput` | 125 | 2 | `no-turn:2` | `unknown:2` | 0.0000 | 0.0000 | 0 | - |
| 2026-05-08T08:03:31.355502Z | `scripts\captures\turn-key-profile-currentpid-33912-20260508-075910\turn-key-profile-summary.json` | `d` | `foreground-sendinput,post-message` | 500 | 4 | `no-turn:2, turn-candidate:2` | `unknown:4` | 10.9922 | 0.0000 | 0 | - |
| 2026-05-08T08:12:44.628259Z | `scripts\captures\turn-key-profile-currentpid-33912-20260508-081125\turn-key-profile-summary.json` | `d` | `foreground-sendinput` | 125 | 1 | `no-turn:1` | `autohotkey-fallback:1` | 0.0000 | 0.0000 | 0 | - |
| 2026-05-08T08:14:54.585973Z | `scripts\captures\turn-key-profile-currentpid-33912-20260508-081354\turn-key-profile-summary.json` | `d` | `foreground-sendinput` | 125 | 1 | `no-turn:1` | `foreground-sendinput:1` | 0.0000 | 0.0000 | 0 | - |
| 2026-05-08T08:17:39.963127Z | `scripts\captures\turn-key-profile-currentpid-33912-20260508-081531\turn-key-profile-summary.json` | `d` | `foreground-sendinput` | 500 | 2 | `no-turn:2` | `foreground-sendinput:2` | 0.0000 | 0.0000 | 0 | - |
| 2026-05-08T08:24:21.832798Z | `scripts\captures\turn-key-profile-currentpid-33912-20260508-082051\turn-key-profile-summary.json` | `Left,Right` | `foreground-sendinput` | 250 | 4 | `no-turn:3, proof-refresh-failed:1` | `foreground-sendinput:3, unknown:1` | 0.0000 | 0.0000 | 0 | `003-pwsh-foreground-sendinput-Right-r1:proof_refresh_before_attempt_failed` |
| 2026-05-08T08:36:31.482439Z | `scripts\captures\turn-key-profile-currentpid-33912-20260508-083210\turn-key-profile-summary.json` | `q,e` | `foreground-sendinput` | 125 | 4 | `no-turn:4` | `foreground-sendinput:4` | 0.0000 | 0.0000 | 0 | - |

## Notable attempts

- `scripts\captures\turn-key-profile-currentpid-33912-20260508-072834\turn-key-profile-summary.json`
  - 001-pwsh-post-message-a-r1 a/post-message: planned, yaw=None
  - 002-pwsh-post-message-a-r2 a/post-message: planned, yaw=None
  - 003-pwsh-post-message-d-r1 d/post-message: planned, yaw=None
  - 004-pwsh-post-message-d-r2 d/post-message: planned, yaw=None
- `scripts\captures\turn-key-profile-currentpid-33912-20260508-072955\turn-key-profile-summary.json`
  - 002-pwsh-post-message-a-r2 a/post-message: before-readback-failed, yaw=None
  - 003-pwsh-post-message-d-r1 d/post-message: before-readback-failed, yaw=None
  - 004-pwsh-post-message-d-r2 d/post-message: before-readback-failed, yaw=None
- `scripts\captures\turn-key-profile-currentpid-33912-20260508-073539\turn-key-profile-summary.json`
  - 001-pwsh-post-message-d-r1 d/post-message: turn-candidate, yaw=-8.38371711655384
- `scripts\captures\turn-key-profile-currentpid-33912-20260508-075910\turn-key-profile-summary.json`
  - 003-pwsh-post-message-d-r1 d/post-message: turn-candidate, yaw=10.232531344273667
  - 004-pwsh-post-message-d-r2 d/post-message: turn-candidate, yaw=-10.99219056890891
- `scripts\captures\turn-key-profile-currentpid-33912-20260508-082051\turn-key-profile-summary.json`
  - 003-pwsh-foreground-sendinput-Right-r1 Right/foreground-sendinput: proof-refresh-failed, yaw=None
