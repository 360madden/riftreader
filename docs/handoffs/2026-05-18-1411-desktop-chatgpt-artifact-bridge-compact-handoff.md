# Compact handoff: Desktop ChatGPT Artifact Bridge integration

Created: 2026-05-18 14:11
Repo: `C:\RIFT MODDING\RiftReader`
Branch/head: `main` @ `97e53cedd19801b03459005beaa68d48c1949e4e` (`97e53ce`)
Remote state at creation: main was clean/synced with `origin/main` before this handoff file was written.

## TL;DR

Desktop ChatGPT integration now has a safe bidirectional proposal path:

1. ChatGPT reads curated bridge payloads through tokenized read-only endpoints.
2. ChatGPT can POST operator-approved JSON proposals to Local Inbox v0.
3. Operator/Codex can convert a reviewed `package-proposal` inbox item into an inert package draft under `.riftreader-local`.
4. Nothing applies, executes, stages, commits, pushes, starts a bridge/tunnel, sends RIFT input, or touches CE/x64dbg automatically.

## Latest pushed commits

```text
97e53ce Add package proposal template helpers
a1ab9ba Add bridge inbox package drafts
b0736d0 Add Operator Lite automation shortcuts
eee2c61 Add Operator Lite safe command switches
02340e9 Add Desktop ChatGPT session start packet
0c34940 Add Desktop ChatGPT bootstrap payload
```

Important commits in this slice:

| Commit | Summary |
|---|---|
| `97e53ce` | Added package-proposal template helpers. |
| `a1ab9ba` | Added guarded Local Inbox to inert package-draft export. |
| `b0736d0` | Added Operator Lite automation shortcuts. |
| `eee2c61` | Added Operator Lite safe command switches and `/help`. |
| `02340e9` | Added Desktop ChatGPT session-start packet. |

## What exists now

| Surface | Current capability |
|---|---|
| Local Artifact Bridge | Read-only tokenized payload endpoints plus guarded Local Inbox v0. |
| Local Inbox v0 | Stores JSON proposals only under `.riftreader-local\artifact-bridge-inbox`. |
| Package draft export | `--inbox-package-draft [INBOX_ID] --json` converts reviewed `package-proposal` inbox items into `.riftreader-local\artifact-bridge-package-drafts`. |
| Package proposal template | `/inbox/schema.json` includes `packageProposalTemplate`; Operator Lite can copy the same kind of template. |
| Operator Lite CLI | `/help`, `--list-commands`, `--run`, `--run-all`, shortcuts including `--package-draft`. |
| Operator Lite GUI | High-contrast bridge panel with package-draft and package-proposal-template helpers. |

## Key files

| File | Why it matters |
|---|---|
| `tools/riftreader_workflow/local_artifact_bridge.py` | Bridge endpoints, inbox schema, package draft exporter. |
| `tools/riftreader_workflow/operator_lite.py` | GUI/CLI bridge shortcuts and copy helpers. |
| `scripts/test_local_artifact_bridge.py` | Bridge/inbox/package-draft regression tests. |
| `scripts/test_operator_lite.py` | Operator Lite CLI/GUI wiring tests. |
| `docs/workflow/local-artifact-bridge.md` | Operator docs for bridge, inbox, package drafts. |
| `docs/workflow/operator-lite.md` | Operator Lite usage, buttons, safety contract. |

## Validation already completed

| Validation | Result |
|---|---|
| `python -m py_compile ...` | Passed. |
| Focused bridge/operator tests | `73` tests passed. |
| Broader workflow tests | `140` tests passed. |
| `scripts\riftreader-local-artifact-bridge.cmd --self-test --json` | Passed. |
| Bridge preflight against `artifacts\chatgpt-payloads` | Passed. |
| Real `--inbox-package-draft --json` with empty inbox | Safely blocked with `INBOX_EMPTY`. |
| Real Operator Lite `--package-draft --json` with empty inbox | Safely blocked/accepted as expected. |
| Operator Lite self-test/list commands | Passed. |
| `git --no-pager diff --check` | Passed. |
| Push verification | `origin/main` matched local HEAD at `97e53cedd19801b03459005beaa68d48c1949e4e`. |

## Safety boundaries still in force

- No automatic `--serve` startup.
- No automatic `cloudflared` tunnel startup.
- No real token copying/minting through Operator Lite.
- No package apply from inbox content.
- No command execution endpoint.
- No arbitrary filesystem reads.
- No repo target writes from the bridge or package-draft export.
- No Git stage/commit/push from Operator Lite.
- No RIFT live input, target-control, movement, CE, or x64dbg.

## Current known blocker / expected safe state

There are currently no real inbox proposals stored in the repo-local inbox, so package-draft smoke commands return `INBOX_EMPTY`. That is expected and safe.

## Resume command examples

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd --list-commands --json
.\scripts\riftreader-operator-lite.cmd --session-start --json
.\scripts\riftreader-operator-lite.cmd --package-draft --json
```

For a real Desktop ChatGPT loop, start serving manually only after preflight:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-local-artifact-bridge.cmd --preflight --payload-root artifacts\chatgpt-payloads --json
.\scripts\riftreader-local-artifact-bridge.cmd --serve --payload-root artifacts\chatgpt-payloads --port 8765 --token auto --max-response-mb 25 --max-inbox-mb 1
```

## Recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Launch Operator Lite and inspect bridge button layout | Confirms the new package-template/package-draft controls are visually usable. |
| 2 | Copy Package Proposal Template from Operator Lite | Gives Desktop ChatGPT the safest return-data shape. |
| 3 | Run manual bridge preflight | Confirms current payload and inbox readiness before serving. |
| 4 | Manually start bridge with `--serve --token auto` only when needed | Keeps local exposure explicit and controlled. |
| 5 | Have Desktop ChatGPT POST one small test `package-proposal` | Proves the bidirectional proposal path end-to-end. |
| 6 | Run `--inbox-index` and `--inbox-read-latest` | Verifies the exact inbox item before draft export. |
| 7 | Run `--inbox-package-draft --json` | Creates an inert package draft without modifying repo files. |
| 8 | Add newest-draft package-intake dry-run shortcut | Next useful automation step while still avoiding apply/execute. |
| 9 | Add open-newest-draft-summary button | Makes review faster before any dry-run/apply decision. |
| 10 | Keep tunnel automation and apply automation deferred | Preserves the manual safety boundary for exposure and repo mutation. |

## Paste-ready resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader from the compact handoff `docs/handoffs/2026-05-18-1411-desktop-chatgpt-artifact-bridge-compact-handoff.md`. The latest pushed head is `97e53cedd19801b03459005beaa68d48c1949e4e`. Continue the Desktop ChatGPT Artifact Bridge integration lane. Current safe next milestone: add a newest package-draft review/dry-run shortcut that prints or opens the newest draft summary and can invoke package intake dry-run only with explicit operator action; do not automate serve/tunnel/apply/Git/RIFT/CE/x64dbg.
```

## Git status snapshot before writing this handoff

```text
## main...origin/main
```
