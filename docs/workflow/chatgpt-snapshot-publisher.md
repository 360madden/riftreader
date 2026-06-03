<!--
Version: riftreader-chatgpt-snapshot-publisher-docs-v0.1.0
Purpose: Operator documentation for publishing a compact GitHub-readable ChatGPT snapshot from the local RiftReader bridge.
-->

# RiftReader ChatGPT Snapshot Publisher v0.1

## Purpose

The ChatGPT Snapshot Publisher captures selected, curated Local Artifact Bridge endpoints from `127.0.0.1` and writes a compact snapshot that ChatGPT can inspect through GitHub when direct tunnel fetches are unreliable.

It is a transport helper only. It does not send live RIFT input, run ProofOnly, attach Cheat Engine, attach x64dbg, execute arbitrary commands, read arbitrary local paths, or mutate `main` unless the operator separately commits implementation files.

## Files

```text
tools/riftreader_workflow/chatgpt_snapshot_publisher.py
scripts/riftreader-publish-chatgpt-snapshot.cmd
scripts/test_chatgpt_snapshot_publisher.py
docs/workflow/chatgpt-snapshot-publisher.md
```

## Basic workflow

Start the bridge/tunnel helper in one PowerShell window and keep it open:

```powershell
Set-Location -LiteralPath "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-bridge-tunnel-session.cmd
```

Then run the snapshot publisher from a second PowerShell window:

```powershell
Set-Location -LiteralPath "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-publish-chatgpt-snapshot.cmd --capture --write --push --wait-url-file-seconds 90
```

The publisher reads the tokenized URL file written by the bridge/tunnel helper, extracts only the token, and fetches the bridge through localhost. With `--write`, it writes:

```text
handoffs/current/RIFTREADER_CHATGPT_SNAPSHOT.md
handoffs/current/RIFTREADER_CHATGPT_SNAPSHOT.json
```

With `--write`, it also writes the two snapshot files into the current worktree. With `--push`, it publishes those two files to the dedicated transport branch from a temporary worktree:

```text
chatgpt/snapshot
```

ChatGPT then inspects the snapshot files from GitHub read-only.

## What gets captured by default

Fixed endpoints:

```text
/<token>/chatgpt-handoff.json
/<token>/health
/<token>/payloads/latest/readme.md
/<token>/payloads/latest/chunks.json
```

Default chunks, when registered:

```text
desktop-chatgpt-workflow
local-artifact-bridge-docs
repo-status
```

Optional chunk additions:

```powershell
.\scripts\riftreader-publish-chatgpt-snapshot.cmd --capture --write --chunk repo-readme
```

The helper rejects path-like chunk IDs and only fetches registered chunk endpoints through the existing bridge.

## Git behavior

By default, the helper does not push anything. `--write` creates or updates the two local snapshot files in the current worktree. `--push` uses a temporary Git worktree, commits only the two snapshot files, and pushes them to `chatgpt/snapshot` with `--force-with-lease` without switching the current working branch.

The current working branch is not switched by the push path.

## Validation

Run from the repo root:

```powershell
python -m py_compile tools\riftreader_workflow\chatgpt_snapshot_publisher.py scripts\test_chatgpt_snapshot_publisher.py
python tools\riftreader_workflow\chatgpt_snapshot_publisher.py --self-test
python -m unittest scripts.test_chatgpt_snapshot_publisher
git --no-pager diff --check
```

## Safety boundaries

Allowed:

```text
GET fixed localhost bridge endpoints
GET registered chunk IDs through the bridge
write snapshot Markdown/JSON under handoffs/current
optionally push only snapshot files to chatgpt/snapshot
```

Forbidden:

```text
live RIFT input
movement
ProofOnly
Cheat Engine
x64dbg
arbitrary file read
arbitrary command execution
repo target writes through the bridge
staging broad paths
git add .
pushing main automatically
```

## END_OF_SCRIPT_MARKER
