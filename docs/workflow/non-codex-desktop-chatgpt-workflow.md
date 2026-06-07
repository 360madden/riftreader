# Non-Codex Desktop ChatGPT Workflow Policy

<!-- RIFTREADER-PRIMARY-WORKFLOW-POLICY-BEGIN -->
## Current primary workflow policy

Primary workflow is now **local Python helpers + local git/gh CLI + GitHub read-only inspection**.

- Google Drive is optional archive/fallback only.
- OpenCode is retired for this repo; do not recommend or launch it.
- GitHub connector is read-only for ChatGPT inspection.
- Repo writes should happen locally through `git`/`gh`.
- PowerShell/CMD should remain thin launchers only.
<!-- RIFTREADER-PRIMARY-WORKFLOW-POLICY-END -->

Created: 2026-05-10 10:45 EDT / 2026-05-10 14:45 UTC
Scope: RiftReader development, documentation, recovery, and live-test workflow when Codex is unavailable, quota-blocked, or not being used.

## Hard rule

When working from desktop ChatGPT instead of Codex, treat ChatGPT as **repo-aware through read-only sources only**, not as a direct local repo editor.

The default workflow is:

1. inspect the GitHub repository and pasted local output read-only;
2. produce a downloadable ZIP package or clearly labeled local applier content;
3. the user downloads/extracts/runs the applier locally;
4. the applier writes only explicit allowlisted files and records backups plus a diff;
5. the user reviews `git status` and `git diff`;
6. commit/push happens from the user's local terminal with explicit paths only;
7. ChatGPT verifies the pushed commit through the GitHub connector read-only.

This policy exists because direct GitHub connector writes and large pasted shell blocks have repeatedly wasted time through silent failure, blocking, partial execution, or terminal-host side effects.

## ChatGPT MCP runtime rule

The repo already has a narrow ChatGPT MCP adapter and launch scripts. Do not
invent a second MCP or duplicate tunnel launcher before checking the existing
entrypoints:

| Existing entrypoint | Role |
|---|---|
| `scripts\riftreader-chatgpt-mcp.cmd` | Main ChatGPT Developer Mode MCP adapter wrapper. |
| `scripts\riftreader-chatgpt-mcp.cmd --operator-launch-plan --json` | Plan-only inventory of the existing non-Codex operator-owned launch commands. It does not start a server or tunnel. |
| `scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host mcp.360madden.com --json` | Prints the active Cloudflare named Tunnel Server URL plan. The legacy flag name is retained for compatibility; it does not start the MCP server, start Cloudflared, or edit Cloudflare. |
| `scripts\riftreader-chatgpt-mcp.cmd --secure-tunnel-plan --json` | Retired OpenAI Secure MCP Tunnel path; not a backup. |
| `scripts\riftreader-chatgpt-mcp.cmd --chatgpt-trial-session --chatgpt-session-seconds 3600 --json` | Retired Cloudflare quick-tunnel path; not a backup. |
| `scripts\riftreader-bridge-tunnel-session.cmd` | Local Artifact Bridge tunnel session, related but not the narrow ChatGPT MCP adapter. |

For the "ChatGPT Web/Desktop without Codex" use case, the MCP runtime must be
started by the operator outside Codex. A Codex-launched `python.exe`,
`cloudflared.exe`, reverse-proxy process, or `tunnel-client.exe` is not final
proof that the workflow works when Codex is closed or quota blocked. The current
selected path is stable public-host Server URL through the persistent Cloudflare
named Tunnel `riftreader-mcp-360madden`: ChatGPT's saved custom MCP app points to
`https://mcp.360madden.com/mcp`, the Cloudflare published application targets
`http://127.0.0.1:8770`, and the local repo still runs its own MCP server.

A ChatGPT app/connector entry is only saved configuration. It does not start the
local repo server or Cloudflared. If the existing command window is closed, the
local MCP server stops. Do not use old `trycloudflare.com`, Caddy/router, or
OpenAI `tunnel-client` setup notes as backups for this lane.

## Tooling boundaries

| Surface | Default role when not using Codex |
|---|---|
| GitHub connector | Read-only inspection and post-push verification only. |
| Desktop ChatGPT | Designs patches, packages, commands, validation logic, and next-step analysis. |
| Local Python/CMD helpers | Status collection, validation, package intake, triage, Operator Lite, and artifact bridge. |
| User's local PowerShell 7 terminal | Executes short linear commands and local appliers. |
| ZIP package | Preferred delivery format for repo edits when the change is more than a trivial command. |
| Python applier | Preferred mechanism for applying docs/code changes with backups, summaries, and diffs. |
| PowerShell | Thin launcher only; avoid branching-heavy interactive logic. |
| Git | User-run local add/commit/push with explicit paths. |

## GitHub connector rule

The GitHub connector is **read-only by default** in this lane.

Allowed:

- search repository contents;
- fetch files;
- fetch commits;
- compare pushed SHAs;
- verify that remote `main` matches the user's local reported SHA.

Not allowed by default:

- create or update files through the connector;
- create commits through the connector;
- push through the connector;
- rely on connector writes for documentation or code changes.

Exception: direct connector writes require explicit current-turn authorization from the user.

## Package contract

For repo changes, the assistant should provide a ZIP package unless the change is trivial.

A good package contains:

| Required item | Purpose |
|---|---|
| `README.md` | Human instructions and target file list. |
| `tools/apply_*.py` | Python applier; main entry point. |
| optional `.cmd` wrapper | Dumb launcher only; no proof decisions or JSON parsing. |
| embedded or packaged content | The exact docs/code to apply. |
| explicit target allowlist | Prevents accidental broad writes. |
| backup path under `.riftreader-local/` | Allows rollback/review. |
| JSON summary | Machine-readable result. |
| diff output | Lets the user paste/review changes. |
| no Git mutation by default | Avoids accidental commits/pushes. |

## Applier behavior

A non-Codex applier must:

1. verify the repo root;
2. verify expected files exist before editing;
3. create backups before changing tracked files;
4. create new files only from an explicit allowlist;
5. replace marker blocks idempotently when updating existing docs;
6. write a JSON summary under `.riftreader-local/`;
7. write a diff under `.riftreader-local/`;
8. print enough final paths for the next chat turn;
9. not run movement, live input, `/reloadui`, screenshot key input, Cheat Engine, Git staging, Git commit, or Git push.

## Chat command rules

The assistant should avoid raw complex PowerShell in chat.

Use direct pasteable PowerShell only for short linear commands, such as:

```powershell
cd "C:\RIFT MODDING\RiftReader"
git status --short
python .\scripts\some_helper.py --json
Write-Host "DONE"
```

Do not paste large interactive blocks containing functions, loops, `try/catch`, JSON parsing, or `exit`. Put that logic in Python or in a saved script package.

## Apply-review-commit-push sequence

After an applier runs, use this local sequence:

```powershell
cd "C:\RIFT MODDING\RiftReader"
git status --short
git --no-pager diff -- <explicit paths>
git --no-pager diff --check
```

Only after review passes:

```powershell
git add <explicit paths>
git --no-pager diff --cached --stat
git --no-pager diff --cached --check
git commit -m "<message>"
git push origin main
git rev-parse HEAD
git ls-remote origin refs/heads/main
Write-Host "PUSH_DONE"
```

If any validation reports a problem, stop before commit and fix it.

## Retired OpenCode bridge

OpenCode is **not part of the RiftReader workflow going forward**. Do not
recommend, route to, or launch the OpenCode wrappers for this repo.

Use the local Python/CMD helpers directly instead:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-workflow-status.cmd --write
.\scripts\riftreader-workflow-status.cmd --compact
```

The historical OpenCode files may remain in the repo until a separate cleanup
pass removes or archives them, but they are not an active operator path. The
current active path is local ChatGPT plus deterministic local helpers, Package
Intake Lite, Live-Test Fast-Lane Triage, Operator Lite, and the read-only Local
Artifact Bridge.

## Local Artifact Bridge proposal loop

The Local Artifact Bridge gives Desktop ChatGPT a safer artifact path than
large paste blocks:

1. the operator runs bridge self-test/preflight/session-start locally;
2. Desktop ChatGPT reads only tokenized, curated payload endpoints;
3. if the operator approves a return path, ChatGPT sends a JSON
   `package-proposal` to Local Inbox v0;
4. the operator converts the reviewed inbox item into an inert package draft;
5. the operator reviews the newest draft summary;
6. only then does the operator run package intake dry-run, still without
   `--apply`.

Safe local commands:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd --bridge-startup-checks --json
.\scripts\riftreader-operator-lite.cmd --package-draft --json
.\scripts\riftreader-operator-lite.cmd --package-draft-index --json
.\scripts\riftreader-operator-lite.cmd --latest-package-draft --json
.\scripts\riftreader-operator-lite.cmd --latest-operator-draft --json
.\scripts\riftreader-operator-lite.cmd --package-draft-dry-run --json
.\scripts\riftreader-operator-lite.cmd --operator-draft-dry-run --json
.\scripts\riftreader-operator-lite.cmd --proposal-loop-checks --json
.\scripts\riftreader-operator-lite.cmd --trial-readiness --json
```

Smoke-test the whole local proposal loop without Desktop ChatGPT:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-package-draft-review.cmd --self-test --json
```

`--trial-readiness` is the safe gate to run before a real Desktop ChatGPT
proposal trial. It runs bridge self-test/preflight/session-start, inbox index,
package-draft index, and the operator-draft availability check without exporting
drafts, dry-running intake, serving, tunneling, applying, or mutating Git. Exit
`2` means a safe blocker, commonly no real operator-proposal draft yet.

The bridge and review helpers write only under `.riftreader-local` or
`artifacts\chatgpt-payloads`, never apply packages, never stage/commit/push,
never start a public tunnel automatically, and fail closed if a draft summary
points its package or manifest outside
`.riftreader-local\artifact-bridge-package-drafts`.

## Package Intake Lite

When desktop ChatGPT provides a manifest-based package, the local Package Intake
Lite helper may inspect or apply it:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-package-intake.cmd --package "C:\path\to\package" --compact-json
```


Smoke-test the local package-review lane without a real package:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-package-intake-selftest.cmd
```

Apply only after review:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-package-intake.cmd --package "C:\path\to\package" --apply --json
```

The helper validates the manifest, verifies SHA-256 checksums, backs up existing
targets under `.riftreader-local`, writes a unified diff even during dry-run,
writes compact Markdown/JSON for pasteback, runs declared checks after apply,
and rolls back on failed checks. It never stages, commits, pushes, sends live
input, attaches CE/x64dbg, or writes provider repos.

Durable package-intake guide:
`docs/workflow/package-intake-lite.md`.

## Live-Test Fast-Lane Triage

When desktop ChatGPT needs to know the current local blocker without live input,
use:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-live-triage.cmd --json --write
```


The helper classifies the failed stage from existing artifacts and safe status
helpers. It is read-only except for `.riftreader-local` reports and does not
send input, run movement, attach CE/x64dbg, stage, commit, or push.

Durable triage guide:
`docs/workflow/live-test-fast-lane-triage.md`.

## Operator Lite

After the CLI helpers are available, the optional local Operator Lite launcher
can provide a small button-based surface around safe commands:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd
```

Headless self-test:

```powershell
.\scripts\riftreader-operator-lite.cmd --self-test --json
```

Operator Lite v0 includes safe Local Artifact Bridge self-test/index/docs/copy
helpers, but intentionally disables target-control, visual gate, ProofOnly,
movement, CE/x64dbg, bridge serve/tunnel management, staging, committing, and
pushing.

Durable Operator Lite guide:
`docs/workflow/operator-lite.md`.

## Visibility rule

ChatGPT can see results clearly when the user pastes:

| Output | Why it matters |
|---|---|
| applier JSON summary | Shows changed paths, backups, diff path, and safety flags. |
| `git status --short` | Shows modified/untracked files. |
| `git diff -- ...` | Shows actual content changes. |
| `git diff --check` | Catches whitespace and patch hygiene issues. |
| commit output | Confirms local commit. |
| push output | Confirms remote update attempt. |
| local and remote SHA | Allows read-only connector verification. |

## Failure handling

| Failure | Correct response |
|---|---|
| Applier fails | Do not commit; inspect summary/errors and fix package or repo state. |
| `git diff --check` reports whitespace | Fix before commit. |
| Push fails | Do not assume remote updated; inspect error and retry locally. |
| Connector verification fails | Treat push as unverified until local/remote SHAs are reconciled. |
| User reports terminal closing | Remove `exit` from interactive scripts; use short commands or a local helper. |
| User reports workflow confusion | Restate the non-Codex workflow and return to package/apply/review/push/verify. |

## Live RIFT safety while not using Codex

The no-Codex workflow does not relax live-test safety.

- No movement until target-control, visual gate, current proof preflight, and same-target `ProofOnly` pass.
- Do not use cached coordinates as current truth.
- Do not use SavedVariables as live truth.
- Do not probe stale absolute proof addresses after PID/HWND drift.
- Use the current-PID coordinate-family scan policy for target drift.
- Use short, explicit local commands and paste the full JSON output back into chat.

## Assistant checklist

Before producing any repo-changing artifact, the assistant must verify:

| Question | Required answer |
|---|---|
| Is this a repo edit? | If yes, package it for local application. |
| Is the GitHub connector being used? | Read-only only, unless user explicitly authorizes write. |
| Is PowerShell complex? | If yes, move logic into Python helper or package. |
| Are target paths explicit? | Yes, no broad writes. |
| Does the package avoid Git mutation by default? | Yes. |
| Did the response include extract/apply commands? | Yes. |
| Is commit/push separated from apply? | Yes, unless user explicitly asks for full automation. |
| Can ChatGPT verify after push? | Yes, user must paste local/remote SHA or push output. |

## Resume phrase

When resuming without Codex, use:

> Resume RiftReader in non-Codex desktop ChatGPT workflow. GitHub connector is read-only. Provide downloadable/local applier packages for repo changes, then I will apply locally, review diff, commit/push from PowerShell, and paste output for read-only verification.

## Relationship to other policies

This workflow complements:

- `agents.md`
- `docs/recovery/current-pid-coordinate-family-recovery-policy.md`
- `docs/recovery/README.md`

The non-Codex workflow controls **how changes are delivered and verified**. Recovery policies control **what technical recovery path is correct**.
