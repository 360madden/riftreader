# ChatGPT MCP Stage 47 role/auth policy metadata complete

Date: 2026-06-18
Branch: `main`
Base before slice: `5c2a1dd`

## Result

Stage 47 is complete-local. The ChatGPT MCP surface remains 40 tools, and the
personal operator-owned `No Authentication` path remains the default. The new
surface is policy metadata only: it classifies personal, shared read-only, and
high-power usage without adding OAuth, Mixed Authentication, auth middleware,
secrets, connector mutation, server startup, or a new MCP tool.

## What changed

- Added `auth_role_policy()` metadata in
  `tools/riftreader_workflow/riftreader_chatgpt_mcp.py`.
- Surfaced compact/full `authRolePolicy` data through `health`, `tool_manifest`,
  and `get_chatgpt_connector_setup_packet`.
- Kept `get_workflow_control_plan` transport-budgeted while surfacing
  `futureCapabilityPolicy.status=stage47-auth-role-policy-metadata-complete`.
- Advanced the 50-stage current truth to Stage 47 complete-local and Stage 48
  next.
- Updated workflow/final-readiness/live-control/debugger docs and the root
  handoff pointer.
- Added regression assertions that No Authentication remains preserved, the
  `public-read-only` profile is the recommended shared no-auth path, and
  high-power tools still require future auth or explicit operator gates.

## Safety boundary

Stage 47 is non-executing metadata only. Required safety truth remains:

```yaml
authEnforcementChanged: false
oauthConfigured: false
mixedAuthConfigured: false
secretMaterialIncluded: false
serverStarted: false
publicTunnelStarted: false
chatGptRegistrationPerformed: false
gitMutation: false
providerWrites: false
movementSent: false
inputSent: false
x64dbgAttach: false
noCheatEngine: true
```

## Validation to run

```text
python -m py_compile tools\riftreader_workflow\riftreader_chatgpt_mcp.py scripts\test_riftreader_chatgpt_mcp.py scripts\test_chatgpt_mcp_workflow_docs.py
python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_mcp_workflow_docs
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --validate-sdk --tool-profile full --json
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --validate-sdk --tool-profile public-read-only --json
git --no-pager diff --check
```

## Post-commit refresh required

After committing/pushing this slice, restart or refresh the non-Codex local HTTP
MCP runtime before asking ChatGPT Web/Desktop to observe the current payloads.
Final readiness still requires fresh actual ChatGPT Web/Desktop proof for
`https://mcp.360madden.com/mcp`; local SDK/server status is not a substitute.

## Next stage

Stage 48 is next: an end-to-end eval suite covering allowed and denied paths
across the 40-tool surface, profile/auth policy metadata, and actual-client
proof gates. No live input, CE/x64dbg attach, proof promotion, provider writes,
or push is authorized by this handoff.
