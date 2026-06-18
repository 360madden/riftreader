import assert from 'node:assert/strict';
import { access, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..', '..');
const serverPath = path.join(__dirname, 'index.mjs');
const movementPlanRoot = path.join(
  repoRoot,
  '.riftreader-local',
  'rift-game-mcp',
  'movement-plans',
);
const currentWindowSmokeRoot = path.join(
  repoRoot,
  '.riftreader-local',
  'rift-game-mcp',
  'current-window-smoke',
);

function getStructured(result) {
  if (result.structuredContent) {
    return result.structuredContent;
  }

  const text = result.content?.find((item) => item.type === 'text')?.text;
  assert.ok(text, 'tool result should contain text content');
  return JSON.parse(text);
}

async function assertFileExists(filePath) {
  await access(filePath);
}

function assertControlSafety(payload, description) {
  assert.equal(payload.safety.movementSent, false, `${description}: movementSent`);
  assert.equal(payload.safety.inputSent, false, `${description}: inputSent`);
  assert.equal(
    payload.safety.savedVariablesUsedAsLiveTruth,
    false,
    `${description}: savedVariablesUsedAsLiveTruth`,
  );
}

const transport = new StdioClientTransport({
  command: process.execPath,
  args: [serverPath],
  cwd: __dirname,
  stderr: 'pipe',
});

if (transport.stderr) {
  transport.stderr.on('data', (chunk) => {
    process.stderr.write(chunk);
  });
}

const client = new Client(
  {
    name: 'rift-game-mcp-control-tools-test',
    version: '0.1.0',
  },
  {
    capabilities: {},
  },
);

try {
  await client.connect(transport);

  const movementRiskKeyChords = [
    'w',
    'a',
    's',
    'd',
    'q',
    'e',
    'up',
    'down',
    'left',
    'right',
    'space',
  ];
  for (const keyChord of movementRiskKeyChords) {
    const movementClassification = getStructured(
      await client.callTool({
        name: 'classify_game_action',
        arguments: { keyChord, holdMilliseconds: 500 },
      }),
    );
    assert.equal(movementClassification.ok, true, `${keyChord}: ok`);
    assert.equal(
      movementClassification.riskClass,
      'movementInput',
      `${keyChord}: riskClass`,
    );
    assert.equal(movementClassification.movementRisk, true, `${keyChord}: movementRisk`);
    assert.equal(
      movementClassification.requiresApproval,
      true,
      `${keyChord}: requiresApproval`,
    );
    assert.equal(
      movementClassification.blockedByDefault,
      true,
      `${keyChord}: blockedByDefault`,
    );
    assert.equal(movementClassification.primitiveTool, 'send_key', `${keyChord}: primitiveTool`);
    assert.deepEqual(
      movementClassification.keyClassification.movementKeys,
      [keyChord],
      `${keyChord}: movementKeys`,
    );
    assertControlSafety(movementClassification, `${keyChord} classification`);
  }

  const hotbarClassification = getStructured(
    await client.callTool({
      name: 'classify_game_action',
      arguments: { actionName: 'hotbar_1', holdMilliseconds: 80 },
    }),
  );
  assert.equal(hotbarClassification.ok, true);
  assert.equal(hotbarClassification.riskClass, 'semanticActionInput');
  assert.equal(hotbarClassification.movementRisk, false);
  assert.equal(hotbarClassification.requiresApproval, false);
  assert.equal(hotbarClassification.semanticAction, 'press_hotbar_slot');
  assert.equal(hotbarClassification.primitiveTool, 'press_hotbar_slot');
  assert.equal(hotbarClassification.slot, 1);
  assertControlSafety(hotbarClassification, 'hotbar classification');

  const inventorySemanticActions = [
    ['inventory', 'open_inventory'],
    ['open_inventory', 'open_inventory'],
    ['open_bags', 'open_bags'],
    ['toggle_inventory', 'toggle_inventory'],
    ['ensure_inventory_open', 'ensure_inventory_open'],
    ['ensure_inventory_closed', 'ensure_inventory_closed'],
  ];
  for (const [actionName, primitiveTool] of inventorySemanticActions) {
    const inventoryClassification = getStructured(
      await client.callTool({
        name: 'classify_game_action',
        arguments: { actionName, holdMilliseconds: 80 },
      }),
    );
    assert.equal(inventoryClassification.ok, true, `${actionName}: ok`);
    assert.equal(
      inventoryClassification.riskClass,
      'semanticUiInput',
      `${actionName}: riskClass`,
    );
    assert.equal(inventoryClassification.movementRisk, false, `${actionName}: movementRisk`);
    assert.equal(
      inventoryClassification.requiresApproval,
      false,
      `${actionName}: requiresApproval`,
    );
    assert.equal(
      inventoryClassification.blockedByDefault,
      false,
      `${actionName}: blockedByDefault`,
    );
    assert.equal(
      inventoryClassification.semanticAction,
      primitiveTool,
      `${actionName}: semanticAction`,
    );
    assert.equal(
      inventoryClassification.primitiveTool,
      primitiveTool,
      `${actionName}: primitiveTool`,
    );
    assertControlSafety(inventoryClassification, `${actionName} classification`);
  }

  const releaseDryRun = getStructured(
    await client.callTool({
      name: 'release_all_movement_keys',
      arguments: { dryRun: true },
    }),
  );
  assert.equal(releaseDryRun.ok, true);
  assert.equal(releaseDryRun.status, 'dry-run');
  assert.equal(releaseDryRun.dryRun, true);
  assert.equal(releaseDryRun.releaseAttempted, false);
  assert.deepEqual(releaseDryRun.keyChords, [
    'w',
    'a',
    's',
    'd',
    'q',
    'e',
    'up',
    'down',
    'left',
    'right',
    'space',
  ]);
  assert.equal(releaseDryRun.safety.movementSent, false);
  assert.equal(releaseDryRun.safety.inputSent, false);
  assert.equal(releaseDryRun.safety.keysReleased, false);
  assert.equal(releaseDryRun.safety.noCheatEngine, true);
  assert.equal(releaseDryRun.safety.x64dbgAttach, false);
  assert.equal(releaseDryRun.safety.providerWrites, false);
  assert.equal(releaseDryRun.safety.savedVariablesUsedAsLiveTruth, false);

  const plan = getStructured(
    await client.callTool({
      name: 'plan_movement_step',
      arguments: {
        semanticAction: 'move_forward',
        holdMilliseconds: 250,
        target: {
          processId: 1234,
          processName: 'rift_x64',
          windowHandle: '0xABCDEF',
          processStartTimeUtc: '2026-06-17T00:00:00Z',
        },
        verification: {
          requireFrameChange: true,
          requireLiveCoordinateDelta: true,
          coordinateTolerance: 0.25,
        },
      },
    }),
  );

  assert.equal(plan.ok, true);
  assert.equal(plan.status, 'planned');
  assert.equal(plan.movementRisk, true);
  assert.equal(plan.requiresApproval, true);
  assert.equal(plan.reusableApprovalTokenGenerated, false);
  assert.equal(plan.safety.movementSent, false);
  assert.equal(plan.safety.inputSent, false);
  assert.equal(plan.safety.keysReleased, true);
  assert.equal(plan.safety.noCheatEngine, true);
  assert.equal(plan.safety.x64dbgAttach, false);
  assert.equal(plan.safety.providerWrites, false);
  assert.equal(plan.safety.savedVariablesUsedAsLiveTruth, false);
  assert.ok(plan.artifactPaths.summaryJson, 'plan should write a summary JSON artifact');
  assert.ok(plan.artifactPaths.summaryMarkdown, 'plan should write a summary Markdown artifact');
  assert.ok(
    path.resolve(plan.artifactPaths.summaryJson).startsWith(movementPlanRoot),
    `summaryJson should stay under ${movementPlanRoot}`,
  );
  assert.ok(
    path.resolve(plan.artifactPaths.summaryMarkdown).startsWith(movementPlanRoot),
    `summaryMarkdown should stay under ${movementPlanRoot}`,
  );
  assert.equal('approvalToken' in plan, false);
  assert.match(plan.approvalPacket.operatorPrompt, /Approve exactly one bounded RIFT movement step/);

  await assertFileExists(plan.artifactPaths.summaryJson);
  await assertFileExists(plan.artifactPaths.summaryMarkdown);
  const diskPlan = JSON.parse(await readFile(plan.artifactPaths.summaryJson, 'utf8'));
  assert.equal(diskPlan.planId, plan.planId);
  assert.equal(diskPlan.safety.movementSent, false);
  assert.equal(diskPlan.safety.inputSent, false);
  assert.equal(diskPlan.reusableApprovalTokenGenerated, false);
  assert.equal('approvalToken' in diskPlan, false);

  const latest = getStructured(
    await client.callTool({
      name: 'get_latest_control_artifact',
      arguments: { kind: 'movement-plan' },
    }),
  );
  assert.equal(latest.ok, true);
  assert.equal(latest.requestedKind, 'movement-plan');
  assert.ok(latest.latest, 'latest movement-plan artifact should be present');
  assert.equal(path.resolve(latest.latest.path), path.resolve(plan.artifactPaths.summaryJson));

  await mkdir(currentWindowSmokeRoot, { recursive: true });
  const smokeArtifactPath = path.join(
    currentWindowSmokeRoot,
    `test-current-window-smoke-${Date.now()}.json`,
  );
  await writeFile(
    smokeArtifactPath,
    `${JSON.stringify({
      schemaVersion: 1,
      kind: 'rift-game-mcp-current-window-safe-smoke',
      status: 'passed',
      ok: true,
      generatedAtUtc: new Date().toISOString(),
      safety: {
        movementSent: false,
        inputSent: false,
        keysReleased: false,
        noCheatEngine: true,
        x64dbgAttach: false,
        providerWrites: false,
        savedVariablesUsedAsLiveTruth: false,
      },
    }, null, 2)}\n`,
    'utf8',
  );

  const latestSmoke = getStructured(
    await client.callTool({
      name: 'get_latest_control_artifact',
      arguments: { kind: 'current-window-smoke' },
    }),
  );
  assert.equal(latestSmoke.ok, true);
  assert.equal(latestSmoke.requestedKind, 'current-window-smoke');
  assert.ok(latestSmoke.latest, 'latest current-window-smoke artifact should be present');
  assert.equal(path.resolve(latestSmoke.latest.path), path.resolve(smokeArtifactPath));
  assert.equal(latestSmoke.latestByKind['current-window-smoke'].kind, 'current-window-smoke');

  console.log(
    JSON.stringify(
      {
        ok: true,
        planId: plan.planId,
        summaryJson: plan.artifactPaths.summaryJson,
        checkedTools: [
          'classify_game_action',
          'release_all_movement_keys',
          'plan_movement_step',
          'get_latest_control_artifact',
        ],
        classificationMatrix: {
          movementRiskKeyChords,
          inventorySemanticActions: inventorySemanticActions.map(([actionName]) => actionName),
        },
        safety: {
          movementSent: false,
          inputSent: false,
        },
      },
      null,
      2,
    ),
  );
} finally {
  await client.close();
}
