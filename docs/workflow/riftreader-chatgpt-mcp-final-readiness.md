# RiftReader ChatGPT MCP final readiness contract

Status: Implemented contract. Phase 3 added the final gate; Phase 4 added
environment preflight fields for loopback port allocation and local artifact
root safety; Phase 6 tightened offline safety fixtures for MCP proposal targets,
proposal checks, tool-boundary flags, root-safety flags, and unsafe-action
detection.

## Purpose

This document defines the exact conditions for calling the RiftReader ChatGPT
MCP workflow **final-product ready**. It is the contract that Phase 3's
`riftreader-mcp-final` gate must implement.

Final-ready means the MCP adapter can be validated, started, registered in
ChatGPT Developer Mode, proven, replayed, and recovered by an operator from a
clean checkout without Codex context and without hidden unsafe actions.

## Non-goals

- Do not add MCP tools outside the approved narrow surface in this contract.
- Do not broaden the adapter into shell, Git, arbitrary filesystem, RIFT input,
  CE, x64dbg, provider-repo, or target-control access.
- Do not start a public tunnel or ChatGPT registration from final status checks.
- Do not treat expired quick-tunnel URLs as a blocker when their summaries prove
  the tunnel/server stopped.
- Do not treat RIFT coordinate or movement proof as part of MCP readiness.

## Final readiness verdicts

| Verdict | Meaning | Exit code |
|---|---|---:|
| `passed` | All required final-product checks passed and warnings are non-blocking. | `0` |
| `blocked` | A known gate prevents final readiness; no unsafe action occurred. | `2` |
| `failed` | A helper error, malformed artifact, unexpected exception, or unsupported state prevented a reliable verdict. | `1` |

A final gate must never report `passed` when any required check is missing,
stale, failing, or unknown.

## Required final readiness fields

The Phase 3 final gate should emit JSON with at least these top-level fields:

```json
{
  "schemaVersion": 1,
  "kind": "riftreader-mcp-final-readiness",
  "generatedAtUtc": "2026-05-19T00:00:00Z",
  "status": "passed|blocked|failed",
  "ok": true,
  "blockers": [],
  "warnings": [],
  "currentHead": "<full git sha>",
  "git": {},
  "ci": {},
  "phase2": {},
  "artifacts": {},
  "dependencies": {},
  "publicSession": {},
  "safety": {},
  "recommendedNextAction": {}
}
```

## Required checks

| Check | Required condition for `passed` | Blocker key when not satisfied |
|---|---|---|
| Repo root | Command runs inside the RiftReader repo. | `repo:not-riftreader-root` |
| Git cleanliness | `git status --short --branch --untracked-files=all` has no tracked or untracked source/doc changes except ignored local artifacts. | `git:dirty-worktree` |
| Current HEAD | `git rev-parse HEAD` succeeds and matches current local branch HEAD. | `git:head-unavailable` |
| Upstream sync | Local branch has an upstream and is neither ahead nor behind when final-ready is claimed. | `git:upstream-not-synced` |
| Current-head CI | Required GitHub workflows for current HEAD are completed and successful. | `ci:missing`, `ci:not-completed`, `ci:failed` |
| Phase 2 gate | `scripts\riftreader-mcp-phase2.cmd --status --json` returns `status=passed`. | `phase2:not-ready` |
| Actual-client proof replay | Latest actual-client proof exists and replays with required proof rules. | `proof:missing`, `proof:replay-failed` |
| Proof freshness | Latest proof age is within the final proof freshness budget. | `proof:stale` |
| Trial readiness freshness | Latest trial-readiness artifact exists and is fresh. | `artifact:trial-readiness-stale` |
| Proposal smoke freshness | Latest proposal transport smoke exists and is fresh. | `artifact:proposal-smoke-stale` |
| Public session state | No public tunnel or trial session is expected to still be running unless the final gate is explicitly in live-trial mode. | `public-session:unexpected-active` |
| Dependency preflight | Required dependencies for the requested mode are available. | `dependency:missing:<name>` |
| Environment preflight | Repo markers are present, loopback ephemeral port allocation works, and local generated MCP artifacts stay under ignored `.riftreader-local`. | `repo:not-riftreader-root`, `environment:*` |
| Tool exposure | MCP tool list is exactly the approved narrow surface. | `safety:unexpected-tool-surface` |
| Repo-root redaction | Public health/proof reports `repoRoot="."` and `absoluteRepoRootExposed=false`; ChatGPT-facing nested helper payloads do not expose the absolute local repo root. | `safety:absolute-repo-root-exposed` |
| Local-only writes | ChatGPT-originated writes are limited to `.riftreader-local` inbox/draft/audit artifacts. | `safety:write-boundary-broken` |
| Unsafe actions | No shell, Git mutation, package apply, provider write, RIFT input, CE, x64dbg, target-control, reloadui, or screenshot action occurred. | `safety:unsafe-action` |
| Unsafe-action unknowns | Required safety flags in proof/smoke artifacts must be present, not omitted. | `safety:unsafe-action-unknown:<flag>` |

## Approved MCP tool surface

The final-ready adapter may expose exactly these tools unless a future contract
updates this list:

| Tool | Access class | Final-readiness requirement |
|---|---|---|
| `health` | Read-only | Must redact absolute repo root and report safety flags. |
| `get_repo_status` | Read-only | Must not mutate Git, repo files, provider repos, RIFT, CE, or x64dbg. |
| `get_latest_handoff` | Read-only | Must read only `docs/handoffs`. |
| `get_package_proposal_template` | Read-only | Must return the accepted package-proposal shape only. |
| `submit_package_proposal` | Guarded local write | May write only inert proposal artifacts under `.riftreader-local\artifact-bridge-inbox`. |
| `list_inbox` | Read-only | Must list inbox metadata only. |
| `create_package_draft_from_inbox` | Guarded local write | May create only inert package-draft artifacts under `.riftreader-local\artifact-bridge-package-drafts` from an explicit validated `inboxId`; must never apply files or execute checks. |
| `review_latest_package_draft` | Read-only | Must review inert draft summaries only. |
| `dry_run_latest_package_draft` | Explicit dry-run action | May run dry-run only; must never pass `--apply`; may return only a bounded `dryRun.diffPreview` from `.riftreader-local\package-intake\*\package.diff`. |
| `get_workflow_control_plan` | Read-only | Must report Mission Control, safe commit-plan guidance, bidirectional data-flow steps, and gated boundaries without executing shell, Git, tunnel, RIFT, CE, x64dbg, or provider actions. |

Any extra tool is a final-readiness blocker until the contract is updated and
tests prove the new tool stays within the safety model.

Every approved tool must also enforce a strict wrapper-argument allowlist. Any
unknown top-level argument key, non-object argument payload, non-JSON-
serializable payload, or oversized argument payload must block before inbox,
draft, audit-expansion, dry-run, shell, Git, tunnel, RIFT, CE, x64dbg, or
provider side effects can occur.

## Freshness budgets

| Artifact | Budget | Stale behavior |
|---|---:|---|
| Trial readiness | 6 hours | Block final readiness; rerun local readiness. |
| Proposal transport smoke | 6 hours | Block final readiness; rerun proposal smoke. |
| Actual-client proof replay | 24 hours | Block final readiness; record fresh actual-client proof. |
| Current-head CI | Must match current HEAD | Block if missing, queued, in-progress, failed, or for another SHA. |
| Public quick-tunnel smoke | No freshness requirement for final-ready | Historical stopped/expired URLs are warnings only. |
| Bounded ChatGPT trial session final summary | No freshness requirement unless in live-trial mode | Expired/stopped URLs are warnings only; active unexpected sessions block. |

## Dependency classes

| Dependency | Required for | Final-readiness behavior |
|---|---|---|
| Python runtime | All local MCP helpers | Missing or unusable Python is `failed` or `dependency:missing:python`. |
| Python MCP SDK | SDK validation, serving, transport smoke, ChatGPT trial | Missing SDK blocks modes that require server/client validation. |
| `gh` CLI authenticated for repo read access | Current-head CI verification | Missing/unavailable `gh` blocks final readiness unless a future equivalent read-only CI source is implemented. |
| `cloudflared` or equivalent HTTPS tunnel tool | Public/ChatGPT trial mode only | Missing blocks live-trial readiness, not local-only final-contract validation. |
| `curl` | Public tunnel smoke verification | Missing blocks public-smoke/live-trial modes that use curl verification. |

## Environment preflight fields

The implemented final gate also reports an `environment` object. This check is
read-only and does not start the MCP server or a public tunnel.

| Field | Required condition | Failure behavior |
|---|---|---|
| Repo markers | `agents.md` or `AGENTS.md`, `.git`, and `tools\riftreader_workflow` exist under the resolved repo root. | Block with `repo:not-riftreader-root`. |
| Loopback ephemeral port | Binding `127.0.0.1:0` succeeds and returns an assigned port. | Block with `environment:loopback-ephemeral-port-unavailable`. |
| Default serve port | Binding `127.0.0.1:8770` succeeds. | Warning only; trial/smoke helpers use ephemeral ports, and manual serve can choose another port. |
| Ignored local artifact root | `.riftreader-local` is ignored by Git. | Block with `environment:artifact-root-not-ignored:.riftreader-local`. |
| Local MCP roots | MCP local roots remain under `.riftreader-local`. | Block with `environment:local-artifact-root-outside-ignored-root:<name>`. |

## Safety invariants

A final gate must report these safety facts explicitly and fail closed if any are
false in a required proof or smoke artifact:

```yaml
movementSent: false
inputSent: false
reloaduiSent: false
screenshotKeySent: false
noCheatEngine: true
x64dbgAttach: false
providerWrites: false
gitMutation: false
applyFlagSent: false
chatGptRegistrationPerformed: false # except explicitly recorded actual-client proof metadata
publicTunnelStarted: false # except explicit public smoke/live-trial helpers
persistentServerStarted: false # except explicit serve/live-trial helpers with teardown evidence
savedVariablesUsedAsLiveTruth: false
noShellExecutionEndpoint: true
noGitMutationEndpoint: true
noArbitraryFilesystemRead: true
noArbitraryFilesystemWrite: true
noRiftLiveInputEndpoint: true
noTargetControlEndpoint: true
noPersistentServerStartedByTool: true
noTunnelStartedByTool: true
chatGptOriginatedWritesLocalOnly: true
noExistingMcpProxy: true
noWindowsMcpProxy: true
noRiftGameMcpProxy: true
```

## Phase 6 safety fixture acceptance criteria

Phase 6 may be considered complete when:

1. `submit_package_proposal` rejects unsafe package targets before any inbox
   write, including parent traversal, absolute/drive-qualified paths, `.git`,
   `.riftreader-local`, and generated capture/session roots.
2. `submit_package_proposal` rejects unsafe package checks before any inbox
   write, including Git mutation, RIFT input helpers, Cheat Engine, and x64dbg
   command fragments.
3. The final gate blocks when tool-surface health exposes an absolute repo root,
   omits or falsifies required endpoint-boundary flags, or reports unapproved
   tools.
4. The final gate blocks when root proof/smoke safety flags are missing,
   unknown, or report Git mutation, provider writes, RIFT input, x64dbg attach,
   SavedVariables-as-live-truth, package apply, or CE usage.
5. A refreshed guarded proposal transport smoke still passes locally through
   submit, inbox list, inert draft creation, draft review, dry-run, and bounded
   `dryRun.diffPreview`, with no public tunnel, ChatGPT registration, Git
   mutation, RIFT input, CE, x64dbg, package apply, or provider write.

## Public session states

| State | Meaning | Final readiness impact |
|---|---|---|
| `not-started` | No public endpoint was started in this check. | Passable. |
| `ready-active` | A bounded trial helper reports a currently usable public URL. | Passable only in explicit live-trial mode; otherwise block as unexpected active exposure. |
| `stopped` | Helper recorded clean server/tunnel teardown. | Passable. |
| `expected-expired` | Historical quick-tunnel URL is known expired/stopped. | Warning only. |
| `interrupted-stopped` | Session was interrupted but server/tunnel stopped. | Warning unless the current task is to prove a fresh live trial. |
| `unknown` | Artifact lacks enough state to prove whether a public endpoint is active or stopped. | Block. |

## Recommended next-action mapping

| Condition | Recommended key | Command |
|---|---|---|
| Dirty worktree | `safe-commit-plan` | `scripts\riftreader-safe-commit-packager.cmd --plan --json` |
| CI missing/pending/failing | `inspect-current-head-ci` | `gh run list --limit 10 --json databaseId,workflowName,headSha,status,conclusion,createdAt,updatedAt,event,url` |
| Trial readiness stale | `refresh-trial-readiness` | `scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json` |
| Proposal smoke stale | `refresh-proposal-smoke` | `scripts\riftreader-chatgpt-mcp.cmd --proposal-transport-smoke --json` |
| Proof stale/missing | `record-actual-client-proof` | `scripts\riftreader-chatgpt-trial-recorder.cmd --template --json` |
| Final local checks pass but fresh external proof needed | `start-bounded-chatgpt-trial` | `scripts\riftreader-chatgpt-mcp.cmd --chatgpt-trial-session --chatgpt-session-seconds 900 --json` |
| All checks pass | `ready-for-release-handoff` | Write/update final release handoff. |

## Phase 3 implementation acceptance criteria

Phase 3 may be considered complete when:

1. `scripts\riftreader-mcp-final.cmd --status --json` exists and returns this
   contract's schema.
2. `scripts\riftreader-mcp-final.cmd --status --compact-json` exists for fast
   operator checks.
3. The final gate fails closed for dirty tree, CI pending/failing, stale
   readiness, stale proposal smoke, stale/missing proof, unsafe tool exposure,
   public-session unknown, and missing required dependency cases.
4. Tests cover each required blocker class and at least one all-pass fixture.
5. Mission Control and Workflow Router can reference the final gate without
   replacing the existing Phase 2 gate.
6. No public tunnel, ChatGPT registration, Git mutation, RIFT input, CE, x64dbg,
   package apply, or provider write occurs during final status checks.

## Operator validation order

RUN THIS:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-mcp-phase2.cmd --status --compact-json
.\scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json
.\scripts\riftreader-chatgpt-mcp.cmd --proposal-transport-smoke --json
.\scripts\riftreader-mcp-mission-control.cmd --json
```

After Phase 3 exists, replace the first command with:

```powershell
.\scripts\riftreader-mcp-final.cmd --status --compact-json
```

For a full final-readiness packet including dependency and environment details:

```powershell
.\scripts\riftreader-mcp-final.cmd --status --json
```
