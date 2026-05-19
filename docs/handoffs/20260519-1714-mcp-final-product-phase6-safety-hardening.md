# RiftReader ChatGPT MCP Final Product - Phase 6 Safety/Security Handoff

- Created UTC: 2026-05-19T17:14:00Z
- Repo: C:\RIFT MODDING\RiftReader
- Branch: main
- Base HEAD before this slice: 35c64bcfbb9c257e7131c403298ac267b041379f

## Phase 6 interpretation

Phase 6 means offline safety/security hardening before the next public ChatGPT trial. The slice must keep the MCP adapter narrow, proposal-only, and local-artifact-only by proving unsafe tool exposure, unsafe package proposal targets/checks, absolute repo-root exposure, missing safety flags, and unsafe-action reports all fail closed. It must not start a public tunnel, register ChatGPT, mutate provider repos, send RIFT input, attach CE, attach x64dbg, or apply packages.

## Completed work

- Hardened `submit_package_proposal` validation before local inbox storage.
  - Rejects unsafe package targets before any inbox write: parent traversal, drive-qualified/absolute paths, `.git`, `.riftreader-local`, and generated capture/session roots through the shared package target policy.
  - Rejects unsafe dry-run check command fragments before any inbox write: Git mutation, RIFT input helpers, Cheat Engine, and x64dbg.
- Added public package-manifest validators for target path and check-definition validation without executing anything.
- Added `applyFlagSent=false` to shared safety flags so proof/smoke artifacts can prove package apply was not requested.
- Tightened the final readiness tool-surface parser.
  - Requires additional health boundary flags: target-control endpoint absent, persistent-server endpoint absent, tunnel endpoint absent, and ChatGPT-originated writes local-only.
  - Blocks missing/unknown root safety flags with `safety:unsafe-action-unknown:<flag>`.
  - Blocks `noCheatEngine` unless it is explicitly `true`.
- Updated Mission Control Phase 6 progress wording so a clean final gate can mark Phase 6 complete and route to Phase 7.
- Updated the final readiness contract with Phase 6 acceptance criteria.
- Refreshed a guarded proposal transport smoke artifact under `.riftreader-local` with the expanded safety keys.

## Validation results before commit

| Command | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\common.py tools\riftreader_workflow\package_manifest.py tools\riftreader_workflow\riftreader_chatgpt_mcp.py tools\riftreader_workflow\mcp_final_readiness.py tools\riftreader_workflow\mcp_mission_control.py scripts\test_riftreader_chatgpt_mcp.py scripts\test_mcp_final_readiness.py scripts\test_mcp_mission_control.py` | Passed |
| `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_mcp_final_readiness scripts.test_mcp_mission_control` | Passed: 60 tests |
| `.\scripts\riftreader-chatgpt-mcp.cmd --proposal-transport-smoke --json` | Passed; loopback-only, no public tunnel; artifact `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260519T171124Z-proposal-transport-smoke.json` |
| `.\scripts\riftreader-mcp-final.cmd --status --compact-json` | Blocked only by `git:dirty-worktree`, as expected before commit; tool surface passed |
| `python -m unittest discover -s scripts -p "test_*.py"` | Passed: 844 tests |
| `dotnet build .\RiftReader.slnx --configuration Release` | Passed: 0 warnings, 0 errors |
| `dotnet test .\RiftReader.slnx --configuration Release --no-build --verbosity normal` | Passed: 102 tests |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed with existing advisory large-library test warnings |
| `git --no-pager diff --check` | Passed; Git emitted only CRLF normalization warnings |

## Current blockers / risks

- Pre-commit final gate blocks on `git:dirty-worktree`, as designed.
- Remote CI must be checked after this Phase 6 commit is pushed.
- No public tunnel, ChatGPT registration, live RIFT input, CE, x64dbg, package apply, provider writes, or Git mutation beyond the requested commit/push workflow were performed by the Phase 6 helpers.

## Exact next commands

After commit/push/CI, verify Phase 6 from the final gate and Mission Control:

```powershell
.\scripts\riftreader-mcp-final.cmd --status --compact-json
.\scripts\riftreader-mcp-mission-control.cmd --json
```

Then run the required cross-lane strategy check:

```powershell
python scripts\riftscan_milestone_review.py --compact-json
```

## Remaining final-product phases

| Phase | Remaining focus |
|---|---|
| 7 | Fresh real ChatGPT trial with a new actual-client proof packet. |
| 8 | Final release handoff and maintenance loop after fresh external proof. |
