import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..', '..');
const serverPath = path.join(__dirname, 'index.mjs');
const defaultOutputRoot = path.join(
  repoRoot,
  '.riftreader-local',
  'rift-game-mcp',
  'current-window-smoke',
);

function parseArgs(argv) {
  const parsed = {
    processName: 'rift_x64',
    semanticAction: 'move_forward',
    holdMilliseconds: 250,
    fromTargetDiscovery: false,
    targetLane: 'movement',
    allowMultipleTargets: false,
    json: false,
    output: null,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const nextValue = () => {
      index += 1;
      if (index >= argv.length || argv[index].startsWith('--')) {
        throw new Error(`${arg} requires a value.`);
      }
      return argv[index];
    };

    switch (arg) {
      case '--process-id':
        parsed.processId = Number(nextValue());
        break;
      case '--window-handle':
        parsed.windowHandle = nextValue();
        break;
      case '--process-name':
        parsed.processName = nextValue();
        break;
      case '--semantic-action':
        parsed.semanticAction = nextValue();
        break;
      case '--hold-ms':
      case '--hold-milliseconds':
        parsed.holdMilliseconds = Number(nextValue());
        break;
      case '--from-target-discovery':
        parsed.fromTargetDiscovery = true;
        break;
      case '--target-lane':
        parsed.targetLane = nextValue();
        break;
      case '--allow-multiple-targets':
        parsed.allowMultipleTargets = true;
        break;
      case '--output':
        parsed.output = nextValue();
        break;
      case '--json':
        parsed.json = true;
        break;
      case '--help':
      case '-h':
        parsed.help = true;
        break;
      default:
        throw new Error(`Unknown argument: ${arg}`);
    }
  }

  return parsed;
}

function usage() {
  return [
    'Usage:',
    '  node safe-current-window-smoke.mjs --process-id <pid> --window-handle <hwnd> --json',
    '  node safe-current-window-smoke.mjs --from-target-discovery --json',
    '  node safe-current-window-smoke.mjs --from-target-discovery --allow-multiple-targets --json',
    '',
    'Safe behavior:',
    '  - Optional --from-target-discovery calls scripts\\get-rift-window-targets.cmd -Json.',
    '  - Auto discovery fails closed when multiple RIFT targets are present unless',
    '    --allow-multiple-targets is explicitly passed.',
    '  - Binds/inspects the exact target window read-only.',
    '  - Calls get_game_control_readiness.',
    '  - Classifies one semantic movement action.',
    '  - Calls release_all_movement_keys with dryRun=true.',
    '  - Calls plan_movement_step with dryRun=true.',
    '  - Never focuses, clicks, resizes, sends input, attaches debuggers,',
    '    writes providers, promotes proof/truth, or uses SavedVariables as live truth.',
  ].join('\n');
}

function requireFiniteInteger(value, name, { min } = {}) {
  if (!Number.isInteger(value)) {
    throw new Error(`${name} must be an integer.`);
  }

  if (min !== undefined && value < min) {
    throw new Error(`${name} must be greater than or equal to ${min}.`);
  }

  return value;
}

function validateArgs(args) {
  if (args.help) {
    return;
  }

  if (!args.processId && !args.windowHandle && !args.fromTargetDiscovery) {
    throw new Error(
      'An exact target is required. Pass --process-id, --window-handle, or --from-target-discovery.',
    );
  }

  if (args.processId !== undefined) {
    args.processId = requireFiniteInteger(args.processId, 'process-id', {
      min: 1,
    });
  }

  args.holdMilliseconds = requireFiniteInteger(
    args.holdMilliseconds,
    'hold-ms',
    { min: 10 },
  );

  if (!args.processName || !String(args.processName).trim()) {
    throw new Error('process-name must not be blank.');
  }

  if (!args.semanticAction || !String(args.semanticAction).trim()) {
    throw new Error('semantic-action must not be blank.');
  }

  const allowedTargetLanes = new Set(['movement', 'background']);
  if (!allowedTargetLanes.has(args.targetLane)) {
    throw new Error('target-lane must be movement or background.');
  }
}

function getStructured(result) {
  if (result.structuredContent) {
    return result.structuredContent;
  }

  const text = result.content?.find((item) => item.type === 'text')?.text;
  assert.ok(text, 'tool result should include text content');
  return JSON.parse(text);
}

function buildSafety(overrides = {}) {
  return {
    movementSent: false,
    inputSent: false,
    keysReleased: false,
    noCheatEngine: true,
    x64dbgAttach: false,
    providerWrites: false,
    savedVariablesUsedAsLiveTruth: false,
    focusSent: false,
    clickSent: false,
    resizeSent: false,
    proofPromotion: false,
    ...overrides,
  };
}

function buildTarget(args) {
  return {
    ...(args.processId ? { processId: args.processId } : {}),
    ...(args.windowHandle ? { windowHandle: args.windowHandle } : {}),
    processName: args.processName,
  };
}

async function runReadOnlyTargetDiscovery() {
  const scriptPath = path.join(repoRoot, 'scripts', 'get-rift-window-targets.cmd');
  const startedAtUtc = new Date().toISOString();
  return await new Promise((resolve, reject) => {
    const child = spawn('cmd.exe', ['/d', '/c', 'call', scriptPath, '-Json'], {
      cwd: repoRoot,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    });

    let stdout = '';
    let stderr = '';
    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', (chunk) => {
      stdout += chunk;
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk;
    });
    child.on('error', reject);
    child.on('close', (exitCode) => {
      const endedAtUtc = new Date().toISOString();
      const cleanStdout = stdout.trim();
      const cleanStderr = stderr.trim();

      if (exitCode !== 0) {
        reject(
          new Error(
            cleanStderr ||
              cleanStdout ||
              `get-rift-window-targets.cmd exited with code ${exitCode}.`,
          ),
        );
        return;
      }

      if (!cleanStdout) {
        reject(new Error('get-rift-window-targets.cmd returned no JSON output.'));
        return;
      }

      try {
        resolve({
          startedAtUtc,
          endedAtUtc,
          command: ['scripts\\get-rift-window-targets.cmd', '-Json'],
          exitCode,
          result: JSON.parse(cleanStdout),
        });
      } catch (error) {
        reject(
          new Error(
            `Failed to parse target discovery JSON: ${
              error instanceof Error ? error.message : String(error)
            }`,
          ),
        );
      }
    });
  });
}

function selectDiscoveredTarget(discovery, { lane, allowMultipleTargets }) {
  const result = discovery?.result ?? {};
  const targetCount = Number(result.count ?? result.windows?.length ?? 0);
  if (targetCount > 1 && !allowMultipleTargets) {
    throw new Error(
      `Target discovery found ${targetCount} RIFT windows. Pass exact --process-id/--window-handle, or rerun with --allow-multiple-targets if auto lane selection is intentional.`,
    );
  }

  const selected = result[lane];
  if (!selected) {
    throw new Error(`Target discovery did not return a ${lane} target.`);
  }

  if (!selected.ProcessId || !selected.WindowHandleHex) {
    throw new Error(`Target discovery ${lane} target lacks exact PID/HWND facts.`);
  }

  return {
    processId: Number(selected.ProcessId),
    windowHandle: String(selected.WindowHandleHex),
    processName: selected.ProcessName ?? 'rift_x64',
  };
}

function nowStamp() {
  return new Date()
    .toISOString()
    .replace(/[-:]/g, '')
    .replace(/\.\d{3}Z$/, 'Z');
}

async function writeSummary(outputPath, summary) {
  const resolved = path.isAbsolute(outputPath)
    ? path.normalize(outputPath)
    : path.resolve(defaultOutputRoot, outputPath);
  const relative = path.relative(defaultOutputRoot, resolved);
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error(`Output path must stay under ${defaultOutputRoot}.`);
  }

  await mkdir(path.dirname(resolved), { recursive: true });
  await writeFile(resolved, `${JSON.stringify(summary, null, 2)}\n`, 'utf8');
  return resolved;
}

async function runSmoke(args) {
  let targetDiscovery = null;
  if (args.fromTargetDiscovery) {
    targetDiscovery = await runReadOnlyTargetDiscovery();
    const discoveredTarget = selectDiscoveredTarget(targetDiscovery, {
      lane: args.targetLane,
      allowMultipleTargets: args.allowMultipleTargets,
    });
    args.processId = discoveredTarget.processId;
    args.windowHandle = discoveredTarget.windowHandle;
    args.processName = discoveredTarget.processName;
  }

  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [serverPath],
    cwd: __dirname,
    stderr: 'pipe',
  });

  if (transport.stderr) {
    transport.stderr.on('data', (chunk) => process.stderr.write(chunk));
  }

  const client = new Client(
    {
      name: 'rift-game-current-window-safe-smoke',
      version: '0.1.0',
    },
    {
      capabilities: {},
    },
  );

  try {
    await client.connect(transport);
    const target = buildTarget(args);
    const find = getStructured(
      await client.callTool({
        name: 'find_game_window',
        arguments: target,
      }),
    );
    assert.equal(find.bound, true, 'find_game_window should bind exact target');

    const readiness = getStructured(
      await client.callTool({
        name: 'get_game_control_readiness',
        arguments: {},
      }),
    );

    const classification = getStructured(
      await client.callTool({
        name: 'classify_game_action',
        arguments: {
          actionName: args.semanticAction,
          holdMilliseconds: args.holdMilliseconds,
        },
      }),
    );

    const releaseDryRun = getStructured(
      await client.callTool({
        name: 'release_all_movement_keys',
        arguments: { dryRun: true },
      }),
    );

    const windowHandle =
      find.window.windowHandleHex ?? find.window.windowHandle ?? target.windowHandle;
    const planDryRun = getStructured(
      await client.callTool({
        name: 'plan_movement_step',
        arguments: {
          semanticAction: args.semanticAction,
          holdMilliseconds: args.holdMilliseconds,
          target: {
            processId: find.window.processId,
            processName: find.window.processName,
            windowHandle,
            title: find.window.title,
          },
          dryRun: true,
        },
      }),
    );

    const safety = buildSafety({
      movementSent: Boolean(
        readiness.safety?.movementSent ||
          classification.safety?.movementSent ||
          releaseDryRun.safety?.movementSent ||
          planDryRun.safety?.movementSent,
      ),
      inputSent: Boolean(
        readiness.safety?.inputSent ||
          classification.safety?.inputSent ||
          releaseDryRun.safety?.inputSent ||
          planDryRun.safety?.inputSent,
      ),
      keysReleased: Boolean(releaseDryRun.safety?.keysReleased),
      savedVariablesUsedAsLiveTruth: Boolean(
        readiness.safety?.savedVariablesUsedAsLiveTruth ||
          classification.safety?.savedVariablesUsedAsLiveTruth ||
          releaseDryRun.safety?.savedVariablesUsedAsLiveTruth ||
          planDryRun.safety?.savedVariablesUsedAsLiveTruth,
      ),
    });

    const blockers = [
      ...(readiness.blockers ?? []).map((item) => `readiness:${item}`),
      ...(classification.blockers ?? []).map((item) => `classification:${item}`),
      ...(releaseDryRun.blockers ?? []).map((item) => `release:${item}`),
      ...(planDryRun.blockers ?? []).map((item) => `plan:${item}`),
    ];
    const warnings = [
      ...(readiness.warnings ?? []).map((item) => `readiness:${item}`),
      ...(classification.warnings ?? []).map((item) => `classification:${item}`),
      ...(releaseDryRun.warnings ?? []).map((item) => `release:${item}`),
      ...(planDryRun.warnings ?? []).map((item) => `plan:${item}`),
    ];

    if (safety.inputSent || safety.movementSent || safety.keysReleased) {
      blockers.push('dry-run-smoke-reported-live-input');
    }

    const ok =
      blockers.length === 0 &&
      classification.ok === true &&
      releaseDryRun.ok === true &&
      releaseDryRun.status === 'dry-run' &&
      releaseDryRun.releaseAttempted === false &&
      planDryRun.ok === true &&
      planDryRun.dryRun === true &&
      !planDryRun.artifactPaths?.summaryJson;

    const summary = {
      schemaVersion: 1,
      kind: 'rift-game-mcp-current-window-safe-smoke',
      status: ok ? 'passed' : 'blocked',
      ok,
      generatedAtUtc: new Date().toISOString(),
      targetDiscovery: targetDiscovery
        ? {
            status: 'passed',
            ok: true,
            command: targetDiscovery.command,
            startedAtUtc: targetDiscovery.startedAtUtc,
            endedAtUtc: targetDiscovery.endedAtUtc,
            selectedLane: args.targetLane,
            allowMultipleTargets: args.allowMultipleTargets,
            count: targetDiscovery.result.count,
            selectedTarget: targetDiscovery.result[args.targetLane] ?? null,
            notes: targetDiscovery.result.notes ?? [],
          }
        : null,
      target,
      boundWindow: find.window,
      readiness: {
        status: readiness.status,
        ok: readiness.ok,
        blockers: readiness.blockers,
        recommendedNextAction: readiness.recommendedNextAction,
      },
      classification: {
        status: classification.status,
        riskClass: classification.riskClass,
        movementRisk: classification.movementRisk,
        requiresApproval: classification.requiresApproval,
        blockedByDefault: classification.blockedByDefault,
      },
      releaseDryRun: {
        status: releaseDryRun.status,
        releaseAttempted: releaseDryRun.releaseAttempted,
        keyCount: releaseDryRun.keyChords?.length ?? 0,
      },
      planDryRun: {
        status: planDryRun.status,
        ok: planDryRun.ok,
        blockers: planDryRun.blockers,
        warnings: planDryRun.warnings,
        artifactWritten: Boolean(planDryRun.artifactPaths?.summaryJson),
      },
      blockers,
      warnings,
      safety,
    };

    if (args.output) {
      summary.outputPath = await writeSummary(args.output, summary);
    } else {
      summary.outputPath = await writeSummary(
        `current-window-safe-smoke-${nowStamp()}.json`,
        summary,
      );
    }

    return summary;
  } finally {
    await client.close();
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(usage());
    return;
  }

  validateArgs(args);
  const summary = await runSmoke(args);
  const text = JSON.stringify(summary, null, 2);
  console.log(text);

  if (!summary.ok) {
    process.exitCode = 2;
  }
}

main().catch((error) => {
  const payload = {
    schemaVersion: 1,
    kind: 'rift-game-mcp-current-window-safe-smoke',
    status: 'failed',
    ok: false,
    blockers: ['safe-current-window-smoke-failed'],
    warnings: [],
    safety: buildSafety(),
    error: error instanceof Error ? error.message : String(error),
  };
  console.error(JSON.stringify(payload, null, 2));
  process.exitCode = 1;
});
