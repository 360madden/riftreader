# 2026-06-08 - Computer Use reboot resume handoff

## Current truth

| Item | Status |
|---|---|
| Repo branch | `main` is ahead of `origin/main` by 2 commits: `8b9a5d8 Add MCP dashboard queue draft viewer` and `011e74a Record no-live RIFT target gate handoff`. |
| Worktree before this handoff | Clean except for ignored `.riftreader-local` decision-packet refresh artifacts; this handoff intentionally adds tracked docs. |
| Latest repo handoff before this | `docs/handoffs/2026-06-08-mcp-dashboard-queue-draft-viewer-ci-actions-handoff.md`. |
| MCP/dashboard progress | Readiness Summary, Desktop Queue Draft Viewer, Status JSON card, and Node 24-compatible CI action versions are documented in the latest handoff. |
| Computer Use before local repair | Codex Settings > Computer use showed `Computer Use plugins unavailable`; Computer Use bootstrap failed with `Computer Use native pipe path is unavailable`. |
| Root cause found | The configured bundled marketplace snapshot at `C:\Users\mrkoo\.codex\.tmp\bundled-marketplaces\openai-bundled` was incomplete: it lacked `.agents\plugins\marketplace.json` and missing bundled plugin directories including `computer-use`. |
| Local repair performed outside repo | Additive repair copied `.agents`, `plugins\browser`, `plugins\computer-use`, `plugins\latex`, and `plugins\sites` from the installed Codex app resources into the active bundled marketplace snapshot. The locked `plugins\chrome` directory was left in place. |
| Local repair verification | `codex plugin list` now shows `Marketplace openai-bundled` and `computer-use@openai-bundled  installed, enabled  26.602.40724`. |
| Remaining required step | Reboot or fully restart Codex so the app can reload the repaired marketplace and recreate/expose the Computer Use native pipe. |
| Not yet verified | Post-reboot Settings UI, Computer Use native pipe availability, and `sky.list_apps()`/app-list smoke. |
| Decision packet after refresh | `status=blocked`, `lane=proof-recovery`, blocker `latest-static-owner-readback-root-pointer-null`; safe next repo command remains `python .\scripts\postupdate_owner_root_rediscovery.py --json`. |

## Exact post-reboot resume sequence

Run this order after reboot or full Codex restart:

1. Open Codex Settings > Computer use.
   - Expected: no `Computer Use plugins unavailable` banner.
   - If still shown, do not attempt desktop automation; rerun plugin-list diagnostics below.
2. In a fresh Codex thread, ask for a no-input Computer Use smoke only:
   - `Use @Computer only to list open apps. Do not click, type, activate windows, or change app state.`
   - Expected result: Computer Use bootstrap succeeds and `list_apps` returns a non-error app list.
3. From the RiftReader repo, confirm the plugin marketplace is still visible:

```cmd
codex plugin list | findstr /I "openai-bundled computer-use browser chrome"
```

Expected lines include:

```text
Marketplace openai-bundled
computer-use@openai-bundled  installed, enabled
```

4. Record a success observation only after `@Computer` app-list smoke passes:

```cmd
scripts\riftreader-desktop-control-readiness.cmd --record-observation --computer-use-native-pipe-ok --computer-use-list-apps-ok --computer-use-stage post-reboot-list-apps --computer-notes "Post-reboot Computer Use bootstrap/list_apps smoke passed; no clicks or typing sent." --json
```

5. If Computer Use is still blocked after reboot, record the blocker instead:

```cmd
scripts\riftreader-desktop-control-readiness.cmd --record-observation --computer-use-stage post-reboot-list-apps --computer-use-error "Computer Use still unavailable after reboot; capture exact UI text or bootstrap error here." --computer-notes "Post-reboot blocked observation; no fallback SendKeys or manual helper launch attempted." --json
```

## Safety boundaries for the resume

| Boundary | Rule |
|---|---|
| Computer Use smoke | Allowed only for bootstrap/list-apps/no-input discovery until readiness is recorded. |
| Desktop input | Do not click, type, activate windows, or drive apps during the first post-reboot smoke. |
| RIFT/game input | Still requires explicit approval; generic reboot/resume does not authorize live input or movement. |
| Queue execution | Still disabled; the dashboard queue viewer is read-only and inert. |
| Manual helper launch | Do not manually launch `codex-computer-use.exe` or fake `SKY_CUA_NATIVE_PIPE_DIRECTORY`; use the supported Codex plugin path. |
| Git | Do not push unless explicitly approved; branch was already ahead of `origin/main` before this handoff. |

## If the marketplace regresses again

If `codex plugin list` no longer shows `computer-use@openai-bundled`, compare these paths:

| Path | Expected |
|---|---|
| `C:\Users\mrkoo\.codex\.tmp\bundled-marketplaces\openai-bundled\.agents\plugins\marketplace.json` | Exists and lists `computer-use`. |
| `C:\Users\mrkoo\.codex\.tmp\bundled-marketplaces\openai-bundled\plugins\computer-use` | Exists. |
| `C:\Program Files\WindowsApps\OpenAI.Codex_26.602.4764.0_x64__2p2nqsd0c76g0\app\resources\plugins\openai-bundled\.agents\plugins\marketplace.json` | Source-of-truth app-resource snapshot for this installed Codex build. |

Do not replace/delete the active bundled marketplace while Codex is running if `extension-host.exe` is locked. The safe repair pattern that worked was additive copy of missing files/directories, not moving or deleting the locked `chrome` folder.

## Validation already run in this session

- `codex plugin list` before repair: `computer-use` was not found in marketplace `openai-bundled`.
- Active temp marketplace inspection: missing `.agents\plugins\marketplace.json`; only `plugins\chrome` was present.
- App-resource marketplace inspection: `sites`, `browser`, `chrome`, `computer-use`, and `latex` existed under the installed Codex app resources.
- Additive repair completed and `codex plugin list` then showed `computer-use@openai-bundled installed, enabled`.
- `scripts\riftreader-decision-packet.cmd --compact-json --write` refreshed local blocked-safe repo status; it exited blocked as expected with `latest-static-owner-readback-root-pointer-null`.

## Next action after the reboot smoke

If Computer Use app-list smoke passes, record the success observation, refresh the MCP dashboard/readiness JSON, and then continue repo work from the latest safe packet. For core RiftReader proof-recovery work, the safe next command remains:

```cmd
python .\scripts\postupdate_owner_root_rediscovery.py --json
```
