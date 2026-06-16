# 2026-06-16 - repo_context_pack now prefers current docs and newest handoffs

## Current lane

Safe local MCP tracked-repo context maintenance. This is a read-only context
surface fix, not a live RIFT input, movement, package apply, Git endpoint,
provider-write, CE, x64dbg, or proof-promotion lane.

## Result

| Item | Current truth |
|---|---|
| Problem | `repo_context_pack(packName="workflow-docs")` could be dominated by old handoff files because pack selection globally sorted all matched paths and truncated after `maxFiles`. |
| Fix | Context-pack selection now preserves curated pack order, de-duplicates without re-sorting globally, and sorts `docs/handoffs/*.md` by leading handoff date/time newest-first for `workflow-docs`. |
| Current pack priority | `docs/HANDOFF.md`, active ChatGPT MCP plan/workflow docs, then newest handoffs, then remaining workflow docs if room remains. |
| Tool version | `riftreader-tracked-repo-context-v0.1.1`. |
| Direct smoke | `scripts\riftreader-tracked-repo-context.cmd context-pack workflow-docs --max-files 8 --max-file-bytes 200000 --max-total-bytes 1000000 --json` passed and selected the 2026-06-16 release handoff before older 2026-06-14 and 2026-06-12 handoffs. |

## Files changed

- `tools/riftreader_workflow/tracked_repo_context.py`
- `scripts/test_tracked_repo_context.py`
- `docs/workflow/tracked-repo-context-tools.md`
- `docs/HANDOFF.md`
- `docs/handoffs/2026-06-16-repo-context-pack-newest-handoffs.md`

## Validation evidence

| Check | Result |
|---|---|
| py_compile | Passed for `tools\riftreader_workflow\tracked_repo_context.py` and `scripts\test_tracked_repo_context.py`. |
| Unit tests | Passed: `python -m unittest scripts.test_tracked_repo_context scripts.test_riftreader_chatgpt_mcp` (`84` tests). |
| Direct context-pack smoke | Passed with `ok=true`, `status=passed`, `fileCount=8`, and newest/current docs selected first. |

## Next action

Use the improved `workflow-docs` pack as the default starter context for
non-Codex ChatGPT MCP handoffs. The next higher-power MCP stage remains Stage
21 approved package-apply proof, which should stay separate from this read-only
context fix.
