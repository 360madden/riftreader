import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { access } from 'node:fs/promises';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..', '..');
const serverPath = path.join(__dirname, 'index.mjs');
const windowToolsProjectPath = path.join(
  repoRoot,
  'tools',
  'RiftReader.WindowTools',
  'RiftReader.WindowTools.csproj',
);

async function assertFileExists(filePath, description) {
  try {
    await access(filePath);
  } catch (error) {
    if (error?.code === 'ENOENT') {
      throw new Error(`${description} is missing: ${filePath}`);
    }

    throw error;
  }
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
    name: 'rift-game-mcp-validator',
    version: '0.1.0',
  },
  {
    capabilities: {},
  },
);

try {
  await assertFileExists(windowToolsProjectPath, '.NET 10 window tools project');
  await client.connect(transport);
  const result = await client.listTools();
  const toolNames = result.tools.map((tool) => tool.name).sort();
  const expectedToolNames = [
    'capture_game_window',
    'capture_inventory_reference',
    'classify_game_action',
    'click_client',
    'ensure_inventory_closed',
    'ensure_inventory_open',
    'find_game_window',
    'focus_game_window',
    'get_bound_window_state',
    'get_game_control_readiness',
    'get_latest_control_artifact',
    'get_riftreader_current_truth',
    'inspect_bound_window',
    'open_bags',
    'open_inventory',
    'plan_movement_step',
    'press_hotbar_slot',
    'release_all_movement_keys',
    'resize_game_window',
    'send_key',
    'suggest_inventory_region',
    'toggle_inventory',
    'validate_config',
    'wait_for_frame_change',
  ].sort();
  const missingTools = expectedToolNames.filter((toolName) => !toolNames.includes(toolName));
  if (missingTools.length > 0) {
    throw new Error(`Missing expected tool(s): ${missingTools.join(', ')}`);
  }

  const findWindowTool = result.tools.find((tool) => tool.name === 'find_game_window');
  if (!findWindowTool) {
    throw new Error('find_game_window tool is missing.');
  }

  const findWindowProperties = findWindowTool.inputSchema?.properties ?? {};
  const requiredFindWindowProperties = ['processId', 'windowHandle', 'processName', 'titleContains'];
  const missingFindWindowProperties = requiredFindWindowProperties.filter(
    (propertyName) => !(propertyName in findWindowProperties),
  );

  if (missingFindWindowProperties.length > 0) {
    throw new Error(
      `find_game_window input schema is missing exact-target properties: ${missingFindWindowProperties.join(', ')}`,
    );
  }

  const sendKeyTool = result.tools.find((tool) => tool.name === 'send_key');
  const sendKeyProperties = sendKeyTool?.inputSchema?.properties ?? {};
  const requiredSendKeyProperties = ['keyChord', 'holdMilliseconds', 'dryRun', 'allowMovementKeys'];
  const missingSendKeyProperties = requiredSendKeyProperties.filter(
    (propertyName) => !(propertyName in sendKeyProperties),
  );
  if (missingSendKeyProperties.length > 0) {
    throw new Error(
      `send_key input schema is missing safety properties: ${missingSendKeyProperties.join(', ')}`,
    );
  }

  const clickTool = result.tools.find((tool) => tool.name === 'click_client');
  const clickProperties = clickTool?.inputSchema?.properties ?? {};
  const requiredClickProperties = ['x', 'y', 'cursorSettleMilliseconds', 'clickDelayMilliseconds', 'dryRun'];
  const missingClickProperties = requiredClickProperties.filter(
    (propertyName) => !(propertyName in clickProperties),
  );
  if (missingClickProperties.length > 0) {
    throw new Error(
      `click_client input schema is missing diagnostic/timing properties: ${missingClickProperties.join(', ')}`,
    );
  }

  const resizeTool = result.tools.find((tool) => tool.name === 'resize_game_window');
  const resizeProperties = resizeTool?.inputSchema?.properties ?? {};
  const requiredResizeProperties = ['clientWidth', 'clientHeight', 'dryRun'];
  const missingResizeProperties = requiredResizeProperties.filter(
    (propertyName) => !(propertyName in resizeProperties),
  );
  if (missingResizeProperties.length > 0) {
    throw new Error(
      `resize_game_window input schema is missing properties: ${missingResizeProperties.join(', ')}`,
    );
  }

  const readinessTool = result.tools.find((tool) => tool.name === 'get_game_control_readiness');
  if (!readinessTool) {
    throw new Error('get_game_control_readiness tool is missing.');
  }
  if (readinessTool.annotations?.readOnlyHint !== true || readinessTool.annotations?.destructiveHint !== false) {
    throw new Error('get_game_control_readiness annotations must mark it read-only and non-destructive.');
  }
  const readinessOutputProperties = readinessTool.outputSchema?.properties ?? {};
  for (const propertyName of ['schemaVersion', 'kind', 'status', 'ok', 'blockers', 'warnings', 'safety']) {
    if (!(propertyName in readinessOutputProperties)) {
      throw new Error(`get_game_control_readiness output schema is missing ${propertyName}.`);
    }
  }

  const classifyTool = result.tools.find((tool) => tool.name === 'classify_game_action');
  const classifyProperties = classifyTool?.inputSchema?.properties ?? {};
  const requiredClassifyProperties = ['actionName', 'keyChord', 'holdMilliseconds'];
  const missingClassifyProperties = requiredClassifyProperties.filter(
    (propertyName) => !(propertyName in classifyProperties),
  );
  if (missingClassifyProperties.length > 0) {
    throw new Error(
      `classify_game_action input schema is missing properties: ${missingClassifyProperties.join(', ')}`,
    );
  }
  if (classifyTool.annotations?.readOnlyHint !== true || classifyTool.annotations?.destructiveHint !== false) {
    throw new Error('classify_game_action annotations must mark it read-only and non-destructive.');
  }

  const planTool = result.tools.find((tool) => tool.name === 'plan_movement_step');
  const planProperties = planTool?.inputSchema?.properties ?? {};
  const requiredPlanProperties = ['semanticAction', 'holdMilliseconds', 'target', 'verification', 'dryRun'];
  const missingPlanProperties = requiredPlanProperties.filter(
    (propertyName) => !(propertyName in planProperties),
  );
  if (missingPlanProperties.length > 0) {
    throw new Error(
      `plan_movement_step input schema is missing properties: ${missingPlanProperties.join(', ')}`,
    );
  }
  if (planTool.annotations?.readOnlyHint !== false || planTool.annotations?.destructiveHint !== false) {
    throw new Error('plan_movement_step annotations must mark it non-read-only but non-destructive.');
  }

  const latestArtifactTool = result.tools.find((tool) => tool.name === 'get_latest_control_artifact');
  if (!latestArtifactTool) {
    throw new Error('get_latest_control_artifact tool is missing.');
  }
  if (latestArtifactTool.annotations?.readOnlyHint !== true || latestArtifactTool.annotations?.destructiveHint !== false) {
    throw new Error('get_latest_control_artifact annotations must mark it read-only and non-destructive.');
  }

  const releaseMovementKeysTool = result.tools.find((tool) => tool.name === 'release_all_movement_keys');
  const releaseMovementKeysProperties = releaseMovementKeysTool?.inputSchema?.properties ?? {};
  if (!releaseMovementKeysTool) {
    throw new Error('release_all_movement_keys tool is missing.');
  }
  if (!('dryRun' in releaseMovementKeysProperties)) {
    throw new Error('release_all_movement_keys input schema is missing dryRun.');
  }
  if (
    releaseMovementKeysTool.annotations?.readOnlyHint !== false ||
    releaseMovementKeysTool.annotations?.destructiveHint !== false
  ) {
    throw new Error('release_all_movement_keys annotations must mark it non-read-only but non-destructive.');
  }

  console.log(
    JSON.stringify(
      {
        ok: true,
        toolNames,
        expectedToolNames,
        windowToolsProjectPath,
        findGameWindowProperties: Object.keys(findWindowProperties).sort(),
        clickClientProperties: Object.keys(clickProperties).sort(),
        sendKeyProperties: Object.keys(sendKeyProperties).sort(),
        resizeGameWindowProperties: Object.keys(resizeProperties).sort(),
        classifyGameActionProperties: Object.keys(classifyProperties).sort(),
        planMovementStepProperties: Object.keys(planProperties).sort(),
        releaseAllMovementKeysProperties: Object.keys(releaseMovementKeysProperties).sort(),
      },
      null,
      2,
    ),
  );
} finally {
  await client.close();
}
