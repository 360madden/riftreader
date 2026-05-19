<!--
Version: riftreader-local-artifact-bridge-docs-v0.3.2
Purpose: Operator documentation for the RiftReader local artifact bridge v0.3, Desktop ChatGPT session-start packet, Desktop ChatGPT handoff packet, and guarded Local Inbox v0.
-->

# RiftReader Local Artifact Bridge v0.3

## Purpose

The Local Artifact Bridge is a repo-owned HTTP bridge for curated RiftReader analysis payloads plus a guarded Local Inbox v0 for JSON proposals.

Its primary purpose is to let ChatGPT repeatedly inspect local payload manifests, summaries, chunk indexes, and registered text chunks without copy/paste, Google Drive dependency, another local agent dependency, GitHub connector writes, or unsafe filesystem exposure.

Its secondary purpose is to let ChatGPT send operator-approved instructions or data back as inert JSON inbox proposals under `.riftreader-local`. v0 does not apply, execute, stage, commit, push, or send live RIFT input from inbox content.

The bridge is for these data flows only:

```text
RiftReader local payload artifacts
-> tokenized local HTTP bridge
-> optional operator-managed tunnel
-> ChatGPT reads curated payload endpoints

ChatGPT JSON proposal
-> tokenized Local Inbox v0 POST endpoint
-> .riftreader-local\artifact-bridge-inbox
-> operator reviews locally before any separate explicit action

Operator-approved package-proposal inbox item
-> --inbox-package-draft
-> .riftreader-local\artifact-bridge-package-drafts
-> newest draft summary review
-> package intake dry-run only as a separate explicit operator step
```

It is not a control channel for RIFT, Git, shell commands, memory tools, debugger tools, or repo mutation.

## Safety model

Artifact reads deliberately expose only `GET` and `HEAD`.

The only write-shaped HTTP surface is:

```text
POST /<token>/inbox/messages
```

That endpoint accepts a small JSON object, stores it under `.riftreader-local\artifact-bridge-inbox`, and stops there. It is an intake box, not an execution or patch channel.

The bridge does not expose:

```text
PUT
PATCH
DELETE
arbitrary POST endpoints
command execution
arbitrary file read
repo target write/delete endpoints
live RIFT controls
ProofOnly controls
Cheat Engine
x64dbg
```

## Files

```text
tools/riftreader_workflow/local_artifact_bridge.py
scripts/riftreader-local-artifact-bridge.cmd
scripts/test_local_artifact_bridge.py
docs/workflow/local-artifact-bridge.md
```

## Start locally

From the repo root:

```powershell
Set-Location -LiteralPath "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-local-artifact-bridge.cmd --preflight --payload-root artifacts\chatgpt-payloads --json
```

For one copy/review packet that combines preflight, latest payload, latest inbox, redacted URL patterns, manual start command, and Desktop ChatGPT prompt guidance:

```powershell
Set-Location -LiteralPath "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-local-artifact-bridge.cmd --session-start --payload-root artifacts\chatgpt-payloads --json
```

Only start serving after preflight reports `status: "passed"`:

```powershell
Set-Location -LiteralPath "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-local-artifact-bridge.cmd --serve --payload-root artifacts\chatgpt-payloads --port 8765 --token auto --max-response-mb 25 --max-inbox-mb 1
```

The server binds to `127.0.0.1`. v0.3 rejects other bind hosts. The startup output prints tokenized handoff, health, inbox schema, and inbox URLs. Treat the token as temporary operator-local access material.

## Optional tunnel with cloudflared

The bridge does not create or manage tunnels. If a tunnel is needed, start it manually in a separate terminal:

```powershell
cloudflared tunnel --url http://127.0.0.1:8765
```

Then provide ChatGPT only the public HTTPS tunnel URL plus the tokenized `/chatgpt-handoff.json`, `/health`, or landing path. Do not provide arbitrary local paths. Stop the bridge and tunnel when finished.

## Operator Lite integration

`scripts\riftreader-operator-lite.cmd` exposes only safe bridge-adjacent buttons:

```text
Bridge Self-Test
Bridge Preflight
Bridge Session Start
Bridge ChatGPT Handoff
Bridge Bootstrap Payload
Bridge Payload Index
Bridge Inbox Index
Bridge Latest Inbox
Bridge Package Draft
Draft Index
Latest Draft Summary
Dry-Run Latest Draft
Latest Operator Draft
Dry-Run Operator Draft
Draft Loop Self-Test
Proposal Loop Checks
Trial Readiness Gate
Open Bridge Docs
Copy Bridge Start Command
Copy Inbox JSON Template
Copy Package Proposal Template
Copy Redacted Bridge Instructions
Copy ChatGPT Bridge Prompt
```

Operator Lite does not start `--serve`, start `cloudflared`, mint/copy a real token, apply inbox content, or manage public tunnels. The Session Start button prints a redacted, one-shot setup packet only. The Bootstrap Payload button writes only a curated payload folder under `artifacts\chatgpt-payloads` from fixed repo-owned docs; it does not edit source files or mutate Git. The Package Draft button converts only the latest `package-proposal` inbox item into an inert package folder under `.riftreader-local\artifact-bridge-package-drafts`; it does not apply that package. The Draft Index button lists ignored package drafts without dry-running them. The Latest Draft Summary button prints the newest ignored draft summary. The Latest Operator Draft button ignores self-test drafts and selects only real operator-proposal drafts. The Dry-Run Latest Draft and Dry-Run Operator Draft buttons invoke package intake without `--apply` only after the operator explicitly clicks/runs them. The Draft Loop Self-Test button writes a synthetic ignored inbox proposal/draft and package-intake dry-run summary to prove the loop locally. The Proposal Loop Checks button runs both bridge HTTP proposal-to-draft and local draft-to-dry-run self-tests. The Trial Readiness Gate runs self-test, preflight, session-start, inbox index, draft index, and the operator-draft availability check without exporting drafts or dry-running intake. It copies only redacted placeholder instructions/prompts/templates. Persistent serving and tunneling remain explicit operator actions.

## Real payload smoke checklist

Use this checklist before giving Desktop ChatGPT a real bridge URL:

1. Confirm the curated payload root exists: `artifacts\chatgpt-payloads`.
2. Run preflight: `.\scripts\riftreader-local-artifact-bridge.cmd --preflight --payload-root artifacts\chatgpt-payloads --json`.
3. If preflight reports `no_valid_payloads`, run the bootstrap command or Operator Lite Bootstrap Payload button:
   `.\scripts\riftreader-local-artifact-bridge.cmd --bootstrap-payload --payload-root artifacts\chatgpt-payloads --json`.
4. Re-run preflight and confirm it reports:
   - `status` is `passed`;
   - `payloadCount` is at least `1`;
   - `latestPayloadId` is not null;
   - `latestSummaryCandidates` is not empty;
   - `safety.noServerStarted` is `true`;
   - `safety.tokenRedacted` is `true`;
   - `safety.artifactReadGetHeadOnly` is `true`;
   - `safety.inboxJsonPostOnly` is `true`.
5. Run `.\scripts\riftreader-local-artifact-bridge.cmd --session-start --payload-root artifacts\chatgpt-payloads --json` for the combined redacted session-start packet.
6. Start `--serve` manually only after preflight/session-start status is ready.
7. Open the tokenized landing page locally: `http://127.0.0.1:8765/<token>/`.
8. Open `/<token>/chatgpt-handoff.json`, `/<token>/health`, `/<token>/payloads/latest/readme.md`, and `/<token>/payloads/latest/chunks.json`.
9. Fetch one registered chunk from `chunks.json`.
10. If using Local Inbox v0, fetch `/<token>/inbox/schema.json`, then POST only a small JSON proposal to `/<token>/inbox/messages`.
11. Run `.\scripts\riftreader-local-artifact-bridge.cmd --inbox-index --json` and `.\scripts\riftreader-local-artifact-bridge.cmd --inbox-read-latest --json` and confirm the item is listed/readable.
12. If the latest inbox item is an operator-approved `package-proposal`, run `.\scripts\riftreader-local-artifact-bridge.cmd --inbox-package-draft --json` to create an ignored local package draft.
13. List package drafts with `.\scripts\riftreader-package-draft-review.cmd --index --json`.
14. Review the newest draft summary with `.\scripts\riftreader-package-draft-review.cmd --latest --json`.
15. If review looks safe, explicitly dry-run package intake with `.\scripts\riftreader-package-draft-review.cmd --dry-run-latest --json`; this never passes `--apply`.
16. To prove the local proposal loop without Desktop ChatGPT, run `.\scripts\riftreader-package-draft-review.cmd --self-test --json`.
17. To prove both HTTP proposal-to-draft and local draft-to-dry-run paths, run `.\scripts\riftreader-operator-lite.cmd --proposal-loop-checks --json`.
18. To check bridge trial readiness without exporting drafts or dry-running intake, run `.\scripts\riftreader-operator-lite.cmd --trial-readiness --json`. Exit `2` is a safe blocker when no real operator draft exists yet.
19. If using a tunnel, start it manually and stop both bridge and tunnel when finished.

## Endpoints

All endpoints require the token as the first path segment:

```text
/<token>/
/<token>/chatgpt-handoff.json
/<token>/health
/<token>/inbox/schema.json
/<token>/inbox/messages/<inbox_id>
/<token>/status.json
/<token>/payloads/index.json
/<token>/payloads/latest/manifest.json
/<token>/payloads/latest/summary.md
/<token>/payloads/latest/readme.md
/<token>/payloads/latest/chunk-index.json
/<token>/payloads/latest/chunks.json
/<token>/payloads/latest/chunks/<chunk_id>
POST /<token>/inbox/messages
```

### `/<token>/`

Returns a compact Markdown landing page with the safest starting links, recommended read order, endpoint list, Local Inbox v0 summary, and bridge safety reminder. This is the best single URL to paste into Desktop ChatGPT after the bridge/tunnel is already running.

### `/chatgpt-handoff.json`

Returns one Desktop ChatGPT handoff packet with redacted URL patterns, operator setup commands, recommended read order, inbox schema, prompt guidance, blockers, and safety rules. This is the easiest endpoint for ChatGPT to read first.

### `/health`

Returns bridge health, version, mode, payload count, latest payload ID, extension policy, endpoint list, Local Inbox v0 schema hints, `recommendedReadOrder`, `chatgptInstructions`, and safety flags.

### `/inbox/messages/<inbox_id>`

Reads back one stored Local Inbox v0 proposal by exact `inboxId`. The ID must have been returned by `POST /<token>/inbox/messages` or listed by `--inbox-index --json`. This endpoint is for confirmation/review only; it does not apply or execute the message.

### `/status.json`

Returns a safe status summary:

```text
branch
HEAD
dirty paths
payload root
latest payload
payload count
inbox root
inbox count
warnings
```

Git status is collected through fixed read-only Git commands. There is no command-execution endpoint and no client-supplied command input.

### `/payloads/index.json`

Lists valid payload folders under the payload root.

A valid payload folder must contain:

```text
manifest.json
chunk-index.json
```

The bridge does not scan raw memory dumps during request handling.

### `/payloads/latest/manifest.json`

Serves the latest payload manifest.

### `/payloads/latest/summary.md`

Serves the latest summary file, preferring:

```text
README.md
reports/reducer-summary.md
```

### `/payloads/latest/readme.md`

Alias for the same selected latest summary as `/payloads/latest/summary.md`. This gives Desktop ChatGPT an obvious README-shaped URL.

### `/payloads/latest/chunk-index.json`

Serves the latest payload chunk registry.

### `/payloads/latest/chunks.json`

Alias for the same latest chunk registry as `/payloads/latest/chunk-index.json`. This gives Desktop ChatGPT an obvious chunk-discovery URL before requesting individual chunk IDs.

### `/payloads/latest/chunks/<chunk_id>`

Serves a registered text chunk only when:

```text
the chunk ID exists in chunk-index.json
the chunk ID is not path-like
the registered path is relative
the registered path stays under the payload folder
the file extension is allowed
the file is not oversized
```

### `/inbox/schema.json`

Returns the Local Inbox v0 JSON schema, accepted `kind` values, validation rules, max request size, safety flags, a ready-to-copy message template, and a ready-to-copy `package-proposal` template.

### `POST /<token>/inbox/messages`

Stores one guarded Local Inbox v0 proposal under:

```text
.riftreader-local\artifact-bridge-inbox\<inbox-id>\
  message.json
  metadata.json
```

Required request headers/body:

```text
Content-Type: application/json
Content-Length: <set by client>
```

Request JSON schema:

```json
{
  "schemaVersion": 1,
  "kind": "chatgpt-message",
  "title": "Short operator-readable title",
  "body": "Text instructions or notes",
  "payload": {
    "optional": "structured JSON data"
  },
  "source": {
    "optional": "source metadata"
  },
  "metadata": {
    "optional": "extra metadata"
  }
}
```

Allowed `kind` values:

```text
artifact-note
chatgpt-data
chatgpt-instructions
chatgpt-message
package-proposal
```

Rules:

```text
schemaVersion must be 1
title is required
kind must be allowlisted
body or payload is required
unknown fields are rejected
body must be UTF-8 JSON text
default max request size is 1 MiB
duplicates are detected by sha256(canonical JSON)
content is stored only under .riftreader-local
content is never applied or executed by the bridge
```

### `--inbox-package-draft`

`--inbox-package-draft` is a local CLI-only bridge helper. It has no HTTP endpoint.

It converts a stored, operator-reviewed Local Inbox message with `kind: "package-proposal"` into an inert package draft under:

```text
.riftreader-local\artifact-bridge-package-drafts\<inbox-id>\
  summary.json
  package\
    riftreader-package-manifest.json
    files\file-0001.txt
```

Default usage converts the latest inbox item:

```powershell
.\scripts\riftreader-local-artifact-bridge.cmd --inbox-package-draft --json
```

To convert a specific item:

```powershell
.\scripts\riftreader-local-artifact-bridge.cmd --inbox-package-draft <inbox-id> --json
```

Accepted `package-proposal` payload shape:

```json
{
  "schemaVersion": 1,
  "kind": "package-proposal",
  "title": "Short patch title",
  "payload": {
    "packageName": "Desktop ChatGPT proposed patch",
    "files": [
      {
        "target": "docs/example.md",
        "content": "# Example\n",
        "encoding": "utf-8"
      }
    ],
    "checks": [
      {
        "name": "compile-bridge",
        "args": ["python", "-m", "py_compile", "tools/riftreader_workflow/local_artifact_bridge.py"],
        "expectedExitCodes": [0],
        "timeoutSeconds": 120
      }
    ]
  }
}
```

The same shape is exposed as `packageProposalTemplate` from `/inbox/schema.json` so Desktop ChatGPT can copy the correct structure before POSTing a proposal.

Guardrails:

```text
requires kind package-proposal
requires 1-20 text files
requires UTF-8 string content
uses the package intake manifest validator
writes only under .riftreader-local\artifact-bridge-package-drafts
does not apply, execute, stage, commit, push, or write repo target files
```

Unsafe targets such as `.git/config` are blocked by manifest validation. The command may still leave a blocked `summary.json` under `.riftreader-local` so the operator can inspect the exact validation errors without re-running blindly.

### Newest package draft review/dry-run

`scripts\riftreader-package-draft-review.cmd` is a local CLI-only review helper
for drafts created by `--inbox-package-draft`. It has no HTTP endpoint and does
not serve, tunnel, apply, stage, commit, push, or send live RIFT input.

Review the newest draft summary:

```powershell
.\scripts\riftreader-package-draft-review.cmd --latest --json
```

List all discovered drafts:

```powershell
.\scripts\riftreader-package-draft-review.cmd --index --json
```

The index classifies drafts as `operator-proposal` or `self-test`, reports
`operatorDraftCount`, `selfTestDraftCount`, and `latestOperatorDraftId`, and
warns with `latest_draft_is_self_test` when repeated smoke checks have made a
self-test draft newer than the latest real operator proposal.

Explicitly dry-run package intake for the newest draft:

```powershell
.\scripts\riftreader-package-draft-review.cmd --dry-run-latest --json
```

Use the operator-only variants when self-test drafts are newer than the latest
real Desktop ChatGPT proposal:

```powershell
.\scripts\riftreader-package-draft-review.cmd --latest-operator --json
.\scripts\riftreader-package-draft-review.cmd --dry-run-latest-operator --json
```

These return `PACKAGE_DRAFT_OPERATOR_EMPTY` when no real operator-proposal draft
exists, even if self-test drafts exist.

Run the local synthetic proposal loop self-test:

```powershell
.\scripts\riftreader-package-draft-review.cmd --self-test --json
```

The dry-run helper invokes:

```text
scripts\riftreader-package-intake.cmd --package <newest-draft-package-root> --compact-json
```

It intentionally does not pass `--apply`. Safe blockers return exit code `2`;
successful dry-runs write normal ignored package-intake summaries under
`.riftreader-local\package-intake`. The self-test stores a synthetic
`package-proposal` under `.riftreader-local\artifact-bridge-inbox`, exports an
inert package draft under `.riftreader-local\artifact-bridge-package-drafts`,
and then runs the same dry-run path.

The review helper fails closed if a draft summary points `packageRoot` or
`manifestPath` outside `.riftreader-local\artifact-bridge-package-drafts`, even
when that outside path exists. In that state it reports
`PACKAGE_DRAFT_NOT_REVIEW_READY` and does not invoke package intake.

## Payload folder contract

Default payload root:

```text
artifacts\chatgpt-payloads
```

Expected shape:

```text
artifacts\chatgpt-payloads\<payload-id>\
  README.md
  manifest.json
  chunk-index.json
  reports\reducer-summary.md
  reports\questions-for-chatgpt.md
  candidates\chain-candidates.csv
  candidates\coord-candidates-top-1000.csv
  candidates\pointer-edges-family-0007.jsonl
```

Required files:

```text
manifest.json
chunk-index.json
```

Example chunk index:

```json
{
  "schemaVersion": 1,
  "payloadId": "pointer-chain-pack-20260517-001",
  "chunks": [
    {
      "chunkId": "chain-candidates",
      "path": "candidates/chain-candidates.csv",
      "kind": "csv",
      "sizeBytes": 842112,
      "sha256": "<sha256>",
      "description": "Ranked static pointer-chain candidates"
    }
  ]
}
```

## Security rules

v0.3 enforces these rules:

```text
bind host: 127.0.0.1 only
token in URL path
random high-entropy token when --token auto
GET and HEAD only for artifact read endpoints
POST only for /<token>/inbox/messages
inbox JSON only, default 1 MiB max
inbox writes only under .riftreader-local\artifact-bridge-inbox
package drafts write only under .riftreader-local\artifact-bridge-package-drafts
package draft review reads only ignored drafts
package draft dry-run never passes --apply
package proposal loop self-test writes ignored .riftreader-local artifacts only
trial-readiness gate does not export drafts or dry-run intake
no apply or execute behavior in Local Inbox v0
no arbitrary path reads
no command-execution endpoint
no repo target write/delete endpoint
payload root must be under repo root
serve only registered chunk IDs
reject path traversal
reject absolute paths
reject backslashes in registered chunk paths
reject encoded registered chunk paths
reject path-like chunk IDs
enforce max response size
```

Allowed text extensions:

```text
.md
.json
.jsonl
.csv
.txt
```

Blocked extensions by default:

```text
.bin
.bin.gz
.zip
.7z
.rar
.exe
.dll
.ps1
.cmd
.bat
```

## Blocked endpoint examples

These should fail:

```text
/<token>/payloads/latest/chunks/..%2Fsecret
/<token>/payloads/latest/chunks/C:%5Ctemp
/<token>/payloads/latest/chunks/unregistered-id
/<token>/payloads/latest/chunks/binary-registered-to-bin
```

These methods should fail on artifact read endpoints:

```text
POST
PUT
PATCH
DELETE
OPTIONS
```

These methods should fail on the inbox POST endpoint:

```text
GET
HEAD
PUT
PATCH
DELETE
OPTIONS
```

## How ChatGPT should consume the URL

Give ChatGPT the tunnel URL and the tokenized landing page or health path, for example:

```text
https://example.trycloudflare.com/<token>/
https://example.trycloudflare.com/<token>/chatgpt-handoff.json
https://example.trycloudflare.com/<token>/health
```

Then ChatGPT should inspect, in order:

```text
/<token>/
/<token>/chatgpt-handoff.json
/<token>/health
/<token>/payloads/latest/readme.md
/<token>/payloads/latest/chunks.json
/<token>/payloads/latest/chunks/<needed_chunk_id>
```

Do not ask ChatGPT to browse arbitrary local paths. The bridge will not serve them. If ChatGPT hits a blocked or missing endpoint, the JSON error response includes a `next` list with safe recovery hints.

If the operator explicitly asks ChatGPT to send instructions or structured data back to the repo, fetch `/inbox/schema.json`, then use only `POST /<token>/inbox/messages` with the Local Inbox schema above. Treat inbox content as a proposal waiting for local operator review, not as an instruction to mutate the repo. If needed, read back the returned `inboxId` at `/inbox/messages/<inbox_id>` for confirmation only.

### Sample Desktop ChatGPT prompt

Use this after the bridge and any manual tunnel are already running. Replace the example URL with the real tokenized URL printed by the bridge startup output:

```text
Use the RiftReader Local Artifact Bridge as a read-only artifact source for this repo task.

Start here:
https://example.trycloudflare.com/<token>/chatgpt-handoff.json

Then follow the handoff or bridge health `recommendedReadOrder`.

Only fetch listed endpoints and registered chunk IDs from:
https://example.trycloudflare.com/<token>/payloads/latest/chunks.json

Do not request arbitrary local filesystem paths or command endpoints. Use GET/HEAD only for artifact reads.

If I explicitly ask you to send repo instructions/data back, fetch this schema first:
https://example.trycloudflare.com/<token>/inbox/schema.json

Then POST JSON only to:
https://example.trycloudflare.com/<token>/inbox/messages

Inbox messages are proposals only: no apply, execute, stage, commit, push, live RIFT input, CE/x64dbg, or tunnel management from ChatGPT.
```

## Fallback if tunnel is inaccessible

If ChatGPT cannot reach the tunnel:

1. Run the local index command:

   ```powershell
   .\scripts\riftreader-local-artifact-bridge.cmd --index --payload-root artifacts\chatgpt-payloads --json
   ```

2. Paste only the resulting JSON or a reduced summary into chat.
3. If ChatGPT needs to send data back, ask it for Local Inbox v0 JSON and POST it locally or paste it into a `package-proposal`.
4. If needed, upload a package ZIP or curated payload ZIP.
5. Keep raw memory dumps out of chat unless explicitly reduced into safe text chunks first.

## Validation

Run from the repo root:

```powershell
python -m py_compile tools\riftreader_workflow\local_artifact_bridge.py scripts\test_local_artifact_bridge.py
python -m unittest scripts.test_local_artifact_bridge
.\scripts\riftreader-local-artifact-bridge.cmd --preflight --payload-root artifacts\chatgpt-payloads --json
.\scripts\riftreader-local-artifact-bridge.cmd --bootstrap-payload --payload-root artifacts\chatgpt-payloads --json
.\scripts\riftreader-local-artifact-bridge.cmd --session-start --payload-root artifacts\chatgpt-payloads --json
.\scripts\riftreader-local-artifact-bridge.cmd --chatgpt-handoff --payload-root artifacts\chatgpt-payloads --json
.\scripts\riftreader-local-artifact-bridge.cmd --inbox-index --json
.\scripts\riftreader-local-artifact-bridge.cmd --inbox-read-latest --json
.\scripts\riftreader-local-artifact-bridge.cmd --self-test
git --no-pager diff --check
```

Expected result:

```text
py_compile passes
unit tests pass
preflight returns passed when at least one valid payload exists, or blocked for an empty first-run payload root
bootstrap-payload creates a valid starter payload when no curated payload exists
session-start returns a redacted Desktop ChatGPT setup packet and exits 2 when preflight is blocked
chatgpt-handoff returns a redacted Desktop ChatGPT starter packet
inbox-index returns Local Inbox v0 metadata without applying anything
inbox-read-latest returns the newest inbox proposal or a safe `INBOX_EMPTY` blocker
self-test passes and covers read endpoints, guarded inbox POST, duplicate detection, malformed JSON, and an HTTP `package-proposal` to inert package-draft loop
diff whitespace check passes
```

<!-- END_OF_SCRIPT_MARKER -->
