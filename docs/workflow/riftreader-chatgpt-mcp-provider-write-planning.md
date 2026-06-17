# RiftReader ChatGPT MCP provider repo write planning

Stage: **36 — provider repo write planning**
Status: **complete-local planning only**

This document defines the planning boundary for future ChatGPT/MCP-assisted
writes to external/provider repositories such as ChromaLink or RiftScan. Stage
36 does **not** enable provider repo writes, does not expose a provider-write
MCP tool, and does not mutate any repo outside RiftReader.

## Purpose

RiftReader already consumes evidence and artifacts from provider-style projects,
but provider repos have different roots, validation gates, owners, live/runtime
risks, and commit/push policies. Future provider work must be explicitly labeled
and separated so ChatGPT cannot silently mix RiftReader source edits with
external repo edits.

## Provider boundary model

| Concept | Rule |
|---|---|
| RiftReader repo | `C:\RIFT MODDING\RiftReader`; normal package/apply/commit/push tools operate only here. |
| Provider repo | Any external root such as ChromaLink, RiftScan, or another addon/helper checkout. |
| Provider write intent | A proposal label saying a future package wants to touch a provider repo. It is metadata only until separately approved. |
| Provider root identity | Must be explicit, canonical, and preflighted before any future write; never inferred from filenames or stale memory. |
| Provider authorization | Must be separate from RiftReader apply/commit/push approval and renewed in the current turn. |
| Provider validation | Must use provider-owned validation commands, not RiftReader-only tests, before provider commit/push. |

## Future provider write plan shape

Future plan/proposal metadata should use a shape equivalent to:

```json
{
  "schemaVersion": 1,
  "kind": "riftreader-provider-write-intent",
  "providerWriteIntent": true,
  "providerKey": "chromalink",
  "providerRoot": "operator-confirmed-absolute-path",
  "providerFiles": ["repo/relative/path.ext"],
  "riftReaderFiles": [],
  "authorizationRequired": true,
  "providerWriteEnabledByDefault": false,
  "separateProviderCommitRequired": true,
  "separateProviderPushRequired": true
}
```

Rules:

1. `providerWriteIntent=true` is a warning label, not permission to write.
2. Provider roots must not be discovered through arbitrary filesystem search.
3. Provider paths must be repo-relative to the confirmed provider root.
4. RiftReader and provider mutations must not be applied by the same tool call.
5. Provider apply, commit, and push must be separate gates with separate tokens.
6. Provider preflight must report branch, upstream, dirty state, validation
   commands, and safety flags before a future provider write can be approved.
7. Provider work must not be routed through `run_bounded_repo_command`.

## Explicitly forbidden in Stage 36

| Forbidden action | Why |
|---|---|
| Writing ChromaLink, RiftScan, or any external checkout | Stage 36 is planning only. |
| Reusing RiftReader apply approval for provider writes | It would hide a cross-repo mutation behind a local repo gate. |
| Mixing RiftReader and provider files in one package apply | Recovery and rollback must stay repo-local. |
| Running provider validation through arbitrary shell | Provider commands need their own future allowlist/preflight. |
| Provider commit/push from `commit_reviewed_slice` or `push_current_branch` | Those tools are intentionally scoped to the current RiftReader repo. |
| Live RIFT input, `/reloadui`, debugger/CE, or proof promotion | Provider planning does not cross live/debugger/proof boundaries. |

## Allowed Stage 36 outputs

| Output | Status |
|---|---|
| This planning document | Allowed. |
| 50-stage plan update | Allowed. |
| Proposal-label requirements for Stage 37 | Allowed. |
| Tests that assert provider writes remain disabled | Allowed. |
| Writes outside RiftReader | Not allowed. |

## Stage 37 handoff

Stage 37 should extend the proposal/draft flow so provider intent is visible and
blocked by default. The correct next behavior is:

- accept or preserve metadata that labels provider write intent;
- show provider labels in review/dry-run summaries;
- block applying provider targets through RiftReader apply;
- require a future separate provider-write tool/approval path before any
  external root can be touched.

## Safety statement

Provider repo write support remains **not exposed**. Through Stage 37, provider
work is planning and labeling only. No provider root should be written, staged,
committed, pushed, reset, cleaned, or otherwise mutated by the ChatGPT MCP lane.
