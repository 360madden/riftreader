/**
 * RiftReader Readback Agent — rift-readback
 *
 * Read-only coordinate recovery agent. Handles Tier 1–3 of the recovery workflow:
 *   1. Instant static chain readback (milliseconds, 2 ReadProcessMemory calls)
 *   2. Verified API + chain comparison (5–15 seconds, parallel capture + readback)
 *   3. Readiness gate check (offline artifact analysis)
 *
 * TOOLS: read-only only. No write_file, str_replace, run_terminal_command restricted.
 * MODEL: Fast/cheap (deepseek-v4-pro) — this runs every session.
 * OUTPUT: Structured JSON with verdict, coordinates, deltas, blockers.
 * SAFETY: Never sends input, never attaches debuggers, never mutates repo unless
 *         explicitly asked by the user. The promoted static resolver
 *         [rift_x64+0x32EBC80]+0x320/+0x324/+0x328 is the primary tool.
 */

import type { AgentDefinition } from './types/agent-definition'

const definition: AgentDefinition = {
  id: 'rift-readback',
  version: '0.1.0',
  displayName: 'RiftReader Coordinate Readback',
  model: 'deepseek/deepseek-v4-pro',

  spawnerPrompt: `Spawn this agent for read-only coordinate recovery. Use it to:
- Read current player coordinates from the promoted static resolver
- Capture a fresh RRAPICOORD API reference and compare against chain readback
- Run static chain promotion readiness checks
- Verify the resolver is healthy for the current session

This agent NEVER sends game input, attaches debuggers, or mutates repo files.`,

  tools: [
    'read_files',
    'code_search',
    'glob',
    'list_directory',
    'run_terminal_command',
  ],

  inputSchema: {
    prompt: {
      type: 'string',
      description: 'What to read back: coordinates, API comparison, readiness check, or diagnostics',
    },
    params: {
      type: 'object',
      properties: {
        mode: {
          type: 'string',
          description: "One of: 'instant' (static chain only), 'verified' (API + chain compare), 'readiness' (promotion gates check), 'diagnostic' (RRAPICOORD health)",
        },
        pid: {
          type: 'number',
          description: 'Target RIFT process ID. If omitted, inferred from current truth.',
        },
        hwnd: {
          type: 'string',
          description: 'Target RIFT window handle (hex). If omitted, inferred from current truth.',
        },
        tolerance: {
          type: 'number',
          description: 'Max allowed API-vs-chain delta. Default 0.25.',
        },
      },
    },
  },

  outputMode: 'structured_output',
  outputSchema: {
    type: 'object',
    properties: {
      status: {
        type: 'string',
        description: "One of: 'passed', 'blocked', 'failed'",
      },
      verdict: {
        type: 'string',
        description: "Human-readable verdict: 'resolver-healthy', 'target-drift', 'api-unavailable', etc.",
      },
      coordinates: {
        type: 'object',
        properties: {
          x: { type: 'number' },
          y: { type: 'number' },
          z: { type: 'number' },
          source: { type: 'string', description: "'static-chain', 'rr-apicoord-api', or 'both'" },
        },
      },
      apiVsChainDelta: {
        type: 'object',
        properties: {
          maxAbsDelta: { type: 'number' },
          withinTolerance: { type: 'boolean' },
          tolerance: { type: 'number' },
        },
      },
      blockers: {
        type: 'array',
        items: { type: 'string' },
      },
      warnings: {
        type: 'array',
        items: { type: 'string' },
      },
      artifacts: {
        type: 'object',
        properties: {
          apiReferencePath: { type: 'string' },
          readbackSummaryPath: { type: 'string' },
          readinessSummaryPath: { type: 'string' },
        },
      },
      recommendedAction: { type: 'string' },
      safety: {
        type: 'object',
        properties: {
          movementSent: { type: 'boolean' },
          inputSent: { type: 'boolean' },
          noCheatEngine: { type: 'boolean' },
        },
      },
    },
    required: ['status', 'verdict', 'coordinates', 'blockers', 'warnings', 'safety'],
  },

  instructionsPrompt: `You are a read-only RiftReader coordinate recovery agent. Your job is to
read player coordinates and verify resolver health — never to send input or
mutate game state.

## Primary Tools (in order of preference)

### 1. Promoted Static Resolver (instant, milliseconds)
\`\`\`
python scripts/static_owner_coordinate_chain_readback.py --use-current-truth --json
\`\`\`
Two ReadProcessMemory calls: deref [rift_x64+0x32EBC80], add +0x320, read 12 bytes.
Returns (x,y,z), owner address, vtable. No scanning, no API dependency.

### 2. Fresh RRAPICOORD API Capture (if API is available)
\`\`\`
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/capture-rift-api-reference-coordinate.ps1 -ProcessId <pid> -Json
\`\`\`

### 3. Verified Comparison (API + chain, 5–15 seconds)
Run both in parallel:
  A) Fresh API capture (command above)
  B) Static chain readback with 3 samples: --use-current-truth --samples 3 --expect-stationary --json
Compare: if delta < 0.25 tolerance, resolver is confirmed healthy.

### 4. Readiness Gate Check (offline, 1 second)
\`\`\`
python scripts/static_chain_promotion_readiness.py --json
\`\`\`
Checks: staticResolverComplete, restartRelogSurvived, staticChainCurrentReadbackPassed,
freshApiNowVsChainNowCurrent, artifact age.

## Safety Rules (from agents.md)
1. NEVER send game input, movement, or target selection without explicit user approval.
2. NEVER attach x64dbg, Cheat Engine, or any debugger.
3. NEVER modify docs/recovery/current-truth.json.
4. NEVER write to ChromaLink or RiftScan repos.
5. NEVER run --allow-current-truth-update or ProofOnly modes.
6. If API is unavailable, use static chain readback only and note the gap.
7. If target PID/HWND doesn't match current-truth, report target-drift blocker.

## Output Contract
Always produce the structured JSON with status, verdict, coordinates, blockers,
warnings, and safety fields. If blocked, explain exactly what gate failed and
the recommended next action.`,

  stepPrompt: `Remember: read-only. No input, no debuggers, no mutation.
If you're about to run a command that modifies state, STOP and block instead.`,
}

export default definition
