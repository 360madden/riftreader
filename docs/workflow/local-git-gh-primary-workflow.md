# Local Git/GitHub CLI Primary Workflow

Generated UTC: `2026-05-17T20:40:09Z`

## Decision

RiftReader's default workflow is now **local Python plus local git/gh CLI**.

Google Drive and OpenCode are not default control-plane tools. They remain available only for specific fallback cases.

## Tool roles

| Tool | Role |
|---|---|
| Local repo | Source of truth and execution environment |
| Repo-owned Python helpers | Primary automation and validation layer |
| PowerShell / CMD | Thin launchers only |
| Local `git` | Stage explicit files, commit, push, verify remote SHA |
| Local `gh` CLI | GitHub auth/status/API/PR/check helper when needed |
| GitHub connector | Read-only remote inspection by ChatGPT |
| Google Drive | Optional archive for large ignored artifacts |
| OpenCode | Optional scoped assistant only when explicitly authorized |

## Primary flow

```text
ChatGPT plans/reviews
-> local repo-owned Python helper
-> local validation
-> local git/gh commit-push-verify
-> ChatGPT reads GitHub read-only
```

## Hard rules

- Do not rely on GitHub connector writes.
- Do not use OpenCode by default.
- Do not use Google Drive as the normal control plane.
- Do not use `git add .`.
- Stage explicit files only.
- Verify local HEAD equals remote HEAD after push.
- Keep live RIFT input, proof promotion, CE, and x64dbg outside workflow-integration lanes unless explicitly selected.

## Fallback use

| Fallback | Allowed use |
|---|---|
| Google Drive | Large logs, screenshots, capture bundles, ignored `.riftreader-local` artifacts, archive material |
| OpenCode | Explicitly authorized scoped local assistance only |
