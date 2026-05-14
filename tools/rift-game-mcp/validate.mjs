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
    'click_client',
    'ensure_inventory_closed',
    'ensure_inventory_open',
    'find_game_window',
    'focus_game_window',
    'get_bound_window_state',
    'get_riftreader_current_truth',
    'inspect_bound_window',
    'open_bags',
    'open_inventory',
    'press_hotbar_slot',
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

  console.log(
    JSON.stringify(
      {
        ok: true,
        toolNames,
        expectedToolNames,
        windowToolsProjectPath,
        findGameWindowProperties: Object.keys(findWindowProperties).sort(),
        sendKeyProperties: Object.keys(sendKeyProperties).sort(),
        resizeGameWindowProperties: Object.keys(resizeProperties).sort(),
      },
      null,
      2,
    ),
  );
} finally {
  await client.close();
}
