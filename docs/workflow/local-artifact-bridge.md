<!--
Version: riftreader-local-artifact-bridge-docs-v0.1.0
Total-Character-Count: 7090
Purpose: Operator documentation for the RiftReader read-only local artifact bridge v0.1.
-->

# RiftReader Local Artifact Bridge v0.1

## Purpose

The Local Artifact Bridge is a repo-owned, read-only HTTP bridge for curated RiftReader analysis payloads.

Its purpose is to let ChatGPT repeatedly inspect local payload manifests, summaries, chunk indexes, and registered text chunks without copy/paste, Google Drive dependency, another local agent dependency, GitHub connector writes, or unsafe filesystem exposure.

The bridge is for this data flow only:

```text
RiftReader local payload artifacts
-> tokenized local HTTP bridge
-> optional operator-managed tunnel
-> ChatGPT reads curated payload endpoints
```

It is not a control channel for RIFT, Git, shell commands, memory tools, or repo mutation.

## Why it is read-only

The bridge deliberately exposes only `GET` and `HEAD`.

It does not expose:

```text
POST
PUT
PATCH
DELETE
command execution
arbitrary file read
write/delete endpoints
live RIFT controls
ProofOnly controls
Cheat Engine
x64dbg
```

This prevents ChatGPT or any tunnel consumer from turning the bridge into a general local filesystem or command API.

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
.\scripts\riftreader-local-artifact-bridge.cmd --serve --payload-root artifacts\chatgpt-payloads --port 8765 --token auto --max-response-mb 25
```

The server binds to:

```text
127.0.0.1
```

v0.1 rejects other bind hosts.

The startup output prints a tokenized local health URL. Treat the token as temporary operator-local access material.

## Optional tunnel with cloudflared

The bridge does not create or manage tunnels. If a tunnel is needed, start it manually in a separate terminal:

```powershell
cloudflared tunnel --url http://127.0.0.1:8765
```

Then provide ChatGPT only the public HTTPS tunnel URL plus the tokenized `/health` path.

Do not provide arbitrary local paths.

Stop the bridge and tunnel when finished.

## Operator Lite integration

`scripts\riftreader-operator-lite.cmd` exposes only safe bridge-adjacent
buttons:

```text
Bridge Self-Test
Bridge Payload Index
Open Bridge Docs
Copy Redacted Bridge Instructions
Copy ChatGPT Bridge Prompt
```

Operator Lite does not start `--serve`, start `cloudflared`, mint/copy a real
token, expose write endpoints, or manage public tunnels. It copies only
redacted placeholder instructions/prompts. Persistent serving and tunneling
remain explicit operator actions.

## Endpoints

All endpoints require the token as the first path segment:

```text
/<token>/
/<token>/health
/<token>/status.json
/<token>/payloads/index.json
/<token>/payloads/latest/manifest.json
/<token>/payloads/latest/summary.md
/<token>/payloads/latest/readme.md
/<token>/payloads/latest/chunk-index.json
/<token>/payloads/latest/chunks.json
/<token>/payloads/latest/chunks/<chunk_id>
```

### `/<token>/`

Returns a compact Markdown landing page with the safest starting links,
recommended read order, endpoint list, and bridge safety reminder. This is the
best single URL to paste into Desktop ChatGPT after the bridge/tunnel is already
running.

### `/health`

Returns bridge health, version, read-only mode, payload count, latest payload
ID, extension policy, endpoint list, `recommendedReadOrder`, and
`chatgptInstructions`.

### `/status.json`

Returns a safe status summary:

```text
branch
HEAD
dirty paths
payload root
latest payload
payload count
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

Alias for the same selected latest summary as `/payloads/latest/summary.md`.
This gives Desktop ChatGPT an obvious README-shaped URL.

### `/payloads/latest/chunk-index.json`

Serves the latest payload chunk registry.

### `/payloads/latest/chunks.json`

Alias for the same latest chunk registry as
`/payloads/latest/chunk-index.json`. This gives Desktop ChatGPT an obvious
chunk-discovery URL before requesting individual chunk IDs.

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

v0.1 enforces these rules:

```text
bind host: 127.0.0.1 only
token in URL path
random high-entropy token when --token auto
GET and HEAD only
no arbitrary path reads
no command-execution endpoint
no write/delete endpoint
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

These methods should fail:

```text
POST
PUT
PATCH
DELETE
OPTIONS
```

## How ChatGPT should consume the URL

Give ChatGPT the tunnel URL and the tokenized landing page or health path, for
example:

```text
https://example.trycloudflare.com/<token>/
https://example.trycloudflare.com/<token>/health
```

Then ChatGPT should inspect, in order:

```text
/<token>/
/<token>/health
/<token>/payloads/latest/readme.md
/<token>/payloads/latest/chunks.json
/<token>/payloads/latest/chunks/<needed_chunk_id>
```

Do not ask ChatGPT to browse arbitrary local paths. The bridge will not serve them.
If ChatGPT hits a blocked or missing endpoint, the JSON error response includes
a `next` list with safe recovery hints.

### Sample Desktop ChatGPT prompt

Use this after the bridge and any manual tunnel are already running. Replace the
example URL with the real tokenized URL printed by the bridge startup output:

```text
Use the RiftReader Local Artifact Bridge as a read-only source for this repo task.

Start here:
https://example.trycloudflare.com/<token>/

Then follow the bridge health `recommendedReadOrder`.

Only fetch listed endpoints and registered chunk IDs from:
https://example.trycloudflare.com/<token>/payloads/latest/chunks.json

Do not request arbitrary local filesystem paths or command endpoints. Assume
GET/HEAD only; no repo writes, no live RIFT input, no CE/x64dbg, and no tunnel
management from ChatGPT.
```

## Fallback if tunnel is inaccessible

If ChatGPT cannot reach the tunnel:

1. Run the local index command:

   ```powershell
   .\scripts\riftreader-local-artifact-bridge.cmd --index --payload-root artifacts\chatgpt-payloads --json
   ```

2. Paste only the resulting JSON or a reduced summary into chat.
3. If needed, upload a package ZIP or curated payload ZIP.
4. Keep raw memory dumps out of chat unless explicitly reduced into safe text chunks first.

## Validation

Run from the repo root:

```powershell
python -m py_compile tools\riftreader_workflow\local_artifact_bridge.py scripts\test_local_artifact_bridge.py
python -m unittest scripts.test_local_artifact_bridge
.\scripts\riftreader-local-artifact-bridge.cmd --self-test
git --no-pager diff --check
```

Expected result:

```text
py_compile passes
unit tests pass
self-test passes
diff whitespace check passes
```

<!-- END_OF_SCRIPT_MARKER -->
