/**
 * RiftReader Proof Agent — rift-proof
 *
 * Promotion gate enforcement agent. Handles:
 *   - Three-pose displacement validation (baseline → pose-A → pose-B)
 *   - Restart/relog survival testing
 *   - API-now vs chain-now comparison with explicit tolerance
 *   - Artifact freshness checking
 *   - Promotion readiness verdict with per-gate pass/fail
 *
 * TOOLS: Read + terminal. No write_file/str_replace (promotion docs are created
 *        by the main agent after human approval).
 * MODEL: Strong reasoning (claude-opus-4.7) — promotion is irreversible.
 * SAFETY: Never promotes. Produces a gate-by-gate report. The human must
 *         explicitly approve promotion before current-truth.md is updated.
 */

import type { AgentDefinition } from './types/agent-definition'

const definition: AgentDefinition = {
  id: 'rift-proof',
  version: '0.1.0',
  displayName: 'RiftReader Proof (Promotion Gates)',
  model: 'anthropic/claude-opus-4.7',

  spawnerPrompt: `Spawn this agent to evaluate whether a candidate static chain is
ready for promotion. It runs all promotion gates and produces a verdict.

This agent NEVER promotes — it only reports gate status. The human must
explicitly approve promotion.

Use cases:
- Three-pose displacement validation for a new yaw/facing chain
- Reboot survival test for an existing promoted chain
- Promotion readiness check before updating current-truth.md`,

  tools: [
    'read_files',
    'code_search',
    'glob',
    'list_directory',
    'run_terminal_command',
    'spawn_agents',
  ],

  spawnableAgents: [
    'rift-readback',
  ],

  inputSchema: {
    prompt: {
      type: 'string',
      description: 'What to proof: a candidate chain expression, a target field (e.g., yaw), or an existing promoted chain for re-validation',
    },
    params: {
      type: 'object',
      properties: {
        chainExpression: {
          type: 'string',
          description: "The candidate chain to proof, e.g. '[rift_x64+0x32EBC80]+0x320/+0x324/+0x328'",
        },
        targetField: {
          type: 'string',
          description: "What this chain resolves to: 'coordinates', 'yaw', 'facing', 'pitch'",
        },
        proofType: {
          type: 'string',
          description: "One of: 'three-pose-displacement', 'reboot-survival', 'promotion-readiness', 'full'",
          default: 'promotion-readiness',
        },
        movementApproved: {
          type: 'boolean',
          description: 'Whether the user has approved movement/displacement stimulus for three-pose proof',
          default: false,
        },
        pid: { type: 'number', description: 'Target RIFT process ID' },
        hwnd: { type: 'string', description: 'Target RIFT window handle (hex)' },
        tolerance: {
          type: 'number',
          description: 'Max allowed delta between chain readback and ground truth. Default 0.25 for coordinates, 5.0 for degrees.',
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
        description: "One of: 'promotion-ready', 'blocked', 'failed', 'needs-more-evidence'",
      },
      verdict: {
        type: 'string',
        description: "Human-readable verdict summary",
      },
      chainExpression: { type: 'string' },
      targetField: { type: 'string' },
      gates: {
        type: 'object',
        properties: {
          staticResolverComplete: {
            type: 'object',
            properties: {
              passed: { type: 'boolean' },
              detail: { type: 'string' },
            },
          },
          restartRelogSurvived: {
            type: 'object',
            properties: {
              passed: { type: 'boolean' },
              detail: { type: 'string' },
            },
          },
          threePoseDisplacement: {
            type: 'object',
            properties: {
              passed: { type: 'boolean' },
              baselineToPoseA: { type: 'number' },
              baselineToPoseB: { type: 'number' },
              detail: { type: 'string' },
            },
          },
          apiNowVsChainNow: {
            type: 'object',
            properties: {
              passed: { type: 'boolean' },
              maxAbsDelta: { type: 'number' },
              tolerance: { type: 'number' },
              detail: { type: 'string' },
            },
          },
          artifactFreshness: {
            type: 'object',
            properties: {
              passed: { type: 'boolean' },
              maxAgeSeconds: { type: 'number' },
              detail: { type: 'string' },
            },
          },
        },
      },
      blockers: {
        type: 'array',
        items: { type: 'string' },
        description: 'Gates that failed — must be resolved before promotion',
      },
      warnings: {
        type: 'array',
        items: { type: 'string' },
        description: 'Non-blocking issues to address',
      },
      promotionAllowed: {
        type: 'boolean',
        description: 'True only if ALL required gates passed',
      },
      recommendedAction: { type: 'string' },
      artifacts: {
        type: 'object',
        properties: {
          proofSummaryJson: { type: 'string' },
          proofSummaryMarkdown: { type: 'string' },
        },
      },
      safety: {
        type: 'object',
        properties: {
          movementSent: { type: 'boolean' },
          inputSent: { type: 'boolean' },
          noCheatEngine: { type: 'boolean' },
          promotionPerformed: { type: 'boolean', description: 'Always false for this agent' },
        },
      },
    },
    required: ['status', 'verdict', 'chainExpression', 'gates', 'blockers', 'warnings', 'promotionAllowed', 'safety'],
  },

  instructionsPrompt: `You are a RiftReader proof agent. Your only job is to evaluate promotion gates
and produce a gate-by-gate report. You NEVER promote — the human does that.

## Proof Types and Required Gates

### Three-Pose Displacement Proof
Required when validating a NEW candidate chain for the first time.
1. Baseline capture (static chain readback + API reference at current position).
2. Controlled displacement to Pose A (e.g., move forward 10m).
3. Capture at Pose A: verify chain delta matches API delta within tolerance.
4. Controlled displacement to Pose B (e.g., move left 10m).
5. Capture at Pose B: verify chain delta matches API delta within tolerance.
6. Report per-axis max delta across all three poses.

The standard tool for coordinates is:
  python scripts/static_owner_coordinate_chain_readback.py --use-current-truth --samples 3 --json
For yaw/facing, adapt static_owner_facing_discovery.py.

### Reboot Survival Proof
Requires evidence that the chain root RVA survives a RIFT restart.
Check current-truth.json for existing restartRelogSurvived evidence.
If absent, this gate cannot pass — report 'needs-more-evidence'.

### Promotion Readiness (combined check)
Runs static_chain_promotion_readiness.py which checks all gates:
  python scripts/static_chain_promotion_readiness.py --json
This is the authoritative single-command check for promoted chains.

## Gate Evaluation Rules
1. staticResolverComplete: Root RVA must be documented and the chain must resolve.
2. restartRelogSurvived: Must have evidence of surviving a RIFT restart.
3. threePoseDisplacement: Max delta across all poses must be within tolerance.
4. apiNowVsChainNow: Fresh API capture must match chain readback within tolerance.
5. artifactFreshness: Proof artifacts must not be older than a reasonable threshold.

## Safety Rules (from agents.md)
1. NEVER pass --allow-current-truth-update, ProofOnly, or promotion flags.
2. NEVER movement/stimulus without params.movementApproved == true.
3. If movementApproved is false and three-pose proof is needed, block with
   status 'blocked' and detail what stimulus is required.
4. NEVER modify current-truth.json or current-truth.md.
5. promotionAllowed must be false unless ALL required gates pass.
6. The safety.promotionPerformed field must ALWAYS be false.
7. Fail closed on any ambiguity — it's safer to block than to approve incorrectly.`,

  stepPrompt: `Proof guardrails: NEVER promote. Report gates only.
If movementApproved is false, block safely and describe what stimulus is needed.
All safety fields must be accurate — especially promotionPerformed = false.`,
}

export default definition
