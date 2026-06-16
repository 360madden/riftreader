# 2026-06-16 - MCP commit tool design contract

## Current lane

Safe MCP roadmap design work. This slice does not implement or expose a commit
tool, does not run package apply, and does not perform Git mutation beyond the
normal local commit/push used to publish this docs slice.

## Result

| Item | Current truth |
|---|---|
| Stage | Stage 23 safe commit design spec is documented. |
| Design doc | `docs\workflow\riftreader-chatgpt-mcp-commit-tool-design.md`. |
| Planned tool | `commit_reviewed_slice`. |
| Boundary | Local commit only after explicit approval; no push, branch rewrite, reset, clean, package apply, provider write, live RIFT input, CE, or x64dbg. |
| Key safety rule | Future helper must stage explicit paths only; `git add .`, `git add -A`, `git commit -a`, shell strings, and unrelated dirty paths are forbidden. |
| Next implementation stage | Stage 24 read-only commit preflight helper. |

## Files changed

- `docs/workflow/riftreader-chatgpt-mcp-commit-tool-design.md`
- `docs/workflow/riftreader-chatgpt-mcp-50-stage-plan.md`
- `docs/HANDOFF.md`
- `docs/handoffs/2026-06-16-mcp-commit-tool-design.md`

## Validation evidence

| Check | Result |
|---|---|
| Diff check | `git --no-pager diff --check` should pass before commit. |
| Final gate | Rerun `scripts\riftreader-mcp-final.cmd --status --compact-json` after publication so current-head CI and proof freshness stay honest. |

## Next action

Implement Stage 24 as a Python read-only helper that returns commit approval
facts and exact explicit-path commands, but does not stage or commit.
