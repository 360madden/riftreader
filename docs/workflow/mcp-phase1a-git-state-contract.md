# MCP Phase 1A — Git State Contract

Version: riftreader-mcp-phase1a-git-state-contract-doc-v0.1.0
Total-Character-Count: 0000002914
Purpose: Define the read-only Git state MCP tool contract that must exist before commit/push automation.

## Goal

Phase 1 expands automation with a safe Git publication lane. The first subphase is read-only visibility so ChatGPT can verify local truth without relying on stale memory.

## New read-only tools

```text
get_recent_commits
get_dirty_paths
```

## get_recent_commits contract

Input:

```json
{
  "limit": 10
}
```

Output:

```json
{
  "schemaVersion": 1,
  "kind": "riftreader-mcp-recent-commits",
  "status": "passed",
  "ok": true,
  "head": "<full sha>",
  "branch": "main",
  "ahead": 0,
  "behind": 0,
  "commits": [
    {
      "sha": "<full sha>",
      "shortSha": "<short sha>",
      "subject": "Commit subject",
      "authorDateIso": "2026-06-09T00:00:00Z"
    }
  ],
  "safety": {
    "gitMutation": false,
    "providerWrites": false,
    "inputSent": false,
    "movementSent": false,
    "noCheatEngine": true,
    "x64dbgAttach": false
  }
}
```

## get_dirty_paths contract

Input:

```json
{
  "includeIgnored": false
}
```

Output:

```json
{
  "schemaVersion": 1,
  "kind": "riftreader-mcp-dirty-paths",
  "status": "clean | dirty | blocked",
  "ok": true,
  "branch": "main",
  "isClean": true,
  "paths": [],
  "safety": {
    "gitMutation": false,
    "providerWrites": false,
    "inputSent": false,
    "movementSent": false,
    "noCheatEngine": true,
    "x64dbgAttach": false
  }
}
```

## Safety rules

```text
- read-only Git commands only
- no staging
- no commit
- no push
- no branch rewrite
- no arbitrary shell endpoint
- no arbitrary file read endpoint
- no RIFT input
- no CE
- no x64dbg
```

## Validation requirements

The implementation package must include:

```text
- pure helper tests for parsing Git porcelain/status output
- py_compile for helper and tests
- unit tests
- git diff --check
```

## Next subphase

After Phase 1A is exposed and validated, implement:

```text
commit_reviewed_slice
push_current_branch
```

Both mutation tools must require explicit expected paths/SHAs and fail closed on mismatch.

## END_OF_SCRIPT_MARKER
