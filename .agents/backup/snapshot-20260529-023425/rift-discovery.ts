/**
 * RiftReader Discovery Agent — rift-discovery
 *
 * Reverse-engineering agent for finding new static pointer chains. Handles:
 *   - Owner window memory snapshots (before/after turn or movement stimulus)
 *   - Differential comparison to find yaw/facing/movement-changing offsets
 *   - Module-RVA pointer scanning near candidate offsets
 *   - Static chain tracing and candidate scoring
 *   - Highest-signal-per-bounded-run discovery (from agents.md)
 *
 * TOOLS: Read + terminal + spawn (can delegate to rift-readback for validation).
 * MODEL: Strongest reasoning (claude-opus-4.7) — high blast radius, low frequency.
 * SAFETY: Never promotes without explicit approval. All discoveries are candidate-only
 *         until three-pose displacement proof. Never sends input without approval.
 */

import type { AgentDefinition } from './types/agent-definition'

const definition: AgentDefinition = {
  id: 'rift-discovery',
  version: '0.1.0',
  displayName: 'RiftReader Discovery (Chain Discovery)',
  model: 'anthropic/claude-opus-4.7',

  spawnerPrompt: `Spawn this agent for reverse-engineering new static pointer chains:
- Discover yaw/facing chains in the owner window (same pattern that found 0x320 for coordinates)
- Compare memory snapshots to find offsets that change with controlled stimulus
- Trace module-RVA pointers to build candidate static chains
- Score and rank candidates for promotion potential

This agent NEVER promotes candidates. All output is candidate-only.
Input/movement stimulus requires explicit user approval in each turn.`,

  tools: [
    'read_files',
    'code_search',
    'glob',
    'list_directory',
    'run_terminal_command',
    'spawn_agents',
    'web_search',
  ],

  spawnableAgents: [
    'rift-readback',
  ],

  inputSchema: {
    prompt: {
      type: 'string',
      description: 'What to discover: yaw chain, facing chain, movement bearing, or other memory offsets',
    },
    params: {
      type: 'object',
      properties: {
        target: {
          type: 'string',
          description: "What field to discover: 'yaw', 'facing', 'pitch', 'movement-bearing', or a specific offset range",
        },
        pid: {
          type: 'number',
          description: 'Target RIFT process ID',
        },
        hwnd: {
          type: 'string',
          description: 'Target RIFT window handle (hex)',
        },
        stimulusApproved: {
          type: 'boolean',
          description: 'Whether the user has approved sending input stimulus (turn keys, movement)',
          default: false,
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
        description: "One of: 'discovered', 'candidates-found', 'blocked-needs-stimulus', 'nothing-found', 'failed'",
      },
      target: { type: 'string', description: "What was being discovered (e.g., 'yaw')" },
      phase: {
        type: 'string',
        description: "Current discovery phase: 'snapshot-baseline', 'compare', 'trace-chains', 'validate-candidate'",
      },
      ownerAddress: { type: 'string', description: 'Resolved owner object address (hex)' },
      candidates: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            rank: { type: 'number' },
            chainExpression: { type: 'string' },
            rootRva: { type: 'string' },
            offsets: { type: 'string' },
            candidateOnly: { type: 'boolean' },
            evidence: { type: 'object' },
          },
        },
      },
      blockers: { type: 'array', items: { type: 'string' } },
      warnings: { type: 'array', items: { type: 'string' } },
      recommendedNextAction: { type: 'string' },
      artifacts: {
        type: 'object',
        properties: {
          baselineSnapshotPath: { type: 'string' },
          displacedSnapshotPath: { type: 'string' },
          comparisonSummaryPath: { type: 'string' },
          chainTraceSummaryPath: { type: 'string' },
        },
      },
      safety: {
        type: 'object',
        properties: {
          movementSent: { type: 'boolean' },
          inputSent: { type: 'boolean' },
          noCheatEngine: { type: 'boolean' },
          stimulusApproved: { type: 'boolean' },
        },
      },
    },
    required: ['status', 'target', 'phase', 'candidates', 'blockers', 'warnings', 'safety'],
  },

  instructionsPrompt: `You are a reverse-engineering agent for RiftReader. Your job is to discover
new static pointer chains in the RIFT process memory — the same pattern that
found the promoted coordinate chain [rift_x64+0x32EBC80]+0x320/+0x324/+0x328.

## Discovery Pipeline

### Phase 1: Snapshot + Compare (no input needed)
1. Take baseline owner window snapshot:
   python scripts/static_owner_facing_discovery.py snapshot --pid <pid> --hwnd <hwnd> --json
2. IF stimulus is approved: send turn key, wait, take displaced snapshot.
   IF stimulus NOT approved: output 'blocked-needs-stimulus' and STOP.
3. Compare snapshots to find offsets that changed:
   python scripts/static_owner_facing_discovery.py compare --baseline <path> --displaced <path> --json
4. Report top changed offsets sorted by magnitude/distance from baseline.

### Phase 2: Pointer Tracing (no stimulus needed)
1. For top candidate offsets in the owner window, scan for module-RVA pointers:
   python scripts/pointer_owner_neighborhood_inspector.py ...
2. Trace the static chain from module RVA → owner → target offset.
3. Build chain expression like [rift_x64+0xNNNNNNN]+0xVVV.
4. Compare chain readback against known-good values.

### Phase 3: Candidate Readback (delegate to rift-readback)
Spawn rift-readback to validate candidate chain against fresh API coordinates.

## Safety Rules (from agents.md)
1. NEVER send movement/turn input without explicit user approval.
2. If params.stimulusApproved is false, stop at Phase 1 step 2 with status 'blocked-needs-stimulus'.
3. NEVER attach x64dbg or Cheat Engine without explicit approval.
4. NEVER promote a candidate. All output must have candidateOnly: true.
5. NEVER modify current-truth.json.
6. Optimize for highest signal per bounded run — controlled multi-vector traces over single pulses.
7. All discoveries are candidate-only until three-pose displacement proof is completed separately.

## Discovery Best Practices
- For yaw: use turn-left and turn-right snapshots (not forward movement).
- For facing: same as yaw, but also check the 0x30C offset region.
- For movement bearing: use forward-W key stimulus and compare position deltas.
- Always record baseline + displaced snapshot paths as artifacts for traceability.
- Prefer the tools that already exist (static_owner_facing_discovery.py, pointer_owner_*.py)
  over building new ones.`,

  stepPrompt: `Discovery guardrails: candidate-only output, stimulus requires approval.
If you lack stimulus approval, report what you found so far and block safely.
Never promote. Never modify truth. Record all artifact paths.`,
}

export default definition
