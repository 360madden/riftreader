import { appendFile, mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const runtimeDir = path.join(__dirname, '.runtime');
const screenshotsDir = path.join(runtimeDir, 'screenshots');
const logsDir = path.join(runtimeDir, 'logs');
const logFilePath = path.join(logsDir, 'actions.jsonl');
const helperScriptPath = path.join(__dirname, 'helpers', 'window-tools.ps1');
const configDir = path.join(__dirname, 'config');
const bindingsFilePath = path.join(configDir, 'bindings.json');

const defaultBindings = Object.freeze({
  inventory: null,
  hotbarSlots: {
    '1': '1',
    '2': '2',
    '3': '3',
    '4': '4',
    '5': '5',
    '6': '6',
    '7': '7',
    '8': '8',
    '9': '9',
    '10': '0',
    '11': '-',
    '12': '=',
  },
});

const state = {
  boundWindow: null,
  lastCapturePath: null,
};

function nowStamp() {
  const now = new Date();
  const pad = (value, size = 2) => String(value).padStart(size, '0');
  return [
    now.getFullYear(),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    '-',
    pad(now.getHours()),
    pad(now.getMinutes()),
    pad(now.getSeconds()),
    '-',
    pad(now.getMilliseconds(), 3),
  ].join('');
}

async function ensureRuntimeDirs() {
  await Promise.all([
    mkdir(screenshotsDir, { recursive: true }),
    mkdir(logsDir, { recursive: true }),
    mkdir(configDir, { recursive: true }),
  ]);
}

async function logAction(action, details) {
  await ensureRuntimeDirs();
  const entry = {
    timestamp: new Date().toISOString(),
    action,
    details,
  };

  await appendFile(logFilePath, `${JSON.stringify(entry)}\n`, 'utf8');
}

function toToolResult(payload) {
  return {
    structuredContent: payload,
    content: [
      {
        type: 'text',
        text: JSON.stringify(payload, null, 2),
      },
    ],
  };
}

function toToolError(message, details = {}) {
  return {
    isError: true,
    structuredContent: { error: message, ...details },
    content: [
      {
        type: 'text',
        text: message,
      },
    ],
  };
}

function nextScreenshotPath() {
  return path.join(screenshotsDir, `capture-${nowStamp()}.png`);
}

function buildBoundWindowSpec() {
  if (!state.boundWindow) {
    throw new Error('No bound game window. Call find_game_window first.');
  }

  return {
    WindowHandle: state.boundWindow.windowHandle,
    ExpectedProcessId: String(state.boundWindow.processId),
    ExpectedProcessName: state.boundWindow.processName,
    ...(state.boundWindow.titleContains
      ? { ExpectedTitleContains: state.boundWindow.titleContains }
      : {}),
  };
}

function normalizeFindResult(raw, titleContains) {
  return {
    ...raw,
    titleContains: titleContains ?? null,
  };
}

function updateBoundWindow(window) {
  state.boundWindow = {
    ...(state.boundWindow ?? {}),
    ...window,
  };
}

function updateLastCapturePath(screenshotPath) {
  state.lastCapturePath = screenshotPath || state.lastCapturePath;
}

async function loadBindings() {
  await ensureRuntimeDirs();

  try {
    const raw = JSON.parse(await readFile(bindingsFilePath, 'utf8'));
    return {
      inventory: raw.inventory ?? defaultBindings.inventory,
      hotbarSlots: {
        ...defaultBindings.hotbarSlots,
        ...(raw.hotbarSlots ?? {}),
      },
    };
  } catch (error) {
    if (error?.code === 'ENOENT') {
      return {
        inventory: defaultBindings.inventory,
        hotbarSlots: { ...defaultBindings.hotbarSlots },
      };
    }

    throw new Error(
      `Failed to load key bindings from ${bindingsFilePath}: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
}

async function captureBoundWindow(outputPath = nextScreenshotPath()) {
  await ensureRuntimeDirs();
  const result = await runPowerShell('capture', {
    ...buildBoundWindowSpec(),
    OutputPath: outputPath,
  });

  updateBoundWindow(result.window);
  updateLastCapturePath(result.screenshotPath);
  return result;
}

async function sendBoundKey(keyChord, holdMilliseconds) {
  const result = await runPowerShell('send-key', {
    ...buildBoundWindowSpec(),
    KeyChord: keyChord,
    HoldMilliseconds: holdMilliseconds,
  });

  updateBoundWindow(result.window);
  return result;
}

function buildRegionParameters({
  regionX,
  regionY,
  regionWidth,
  regionHeight,
}) {
  const hasRegion =
    regionWidth !== undefined ||
    regionHeight !== undefined ||
    regionX !== undefined ||
    regionY !== undefined;

  if (!hasRegion) {
    return {};
  }

  if (
    regionX === undefined ||
    regionY === undefined ||
    regionWidth === undefined ||
    regionHeight === undefined
  ) {
    throw new Error(
      'Region filtering requires regionX, regionY, regionWidth, and regionHeight together.',
    );
  }

  return {
    RegionX: regionX,
    RegionY: regionY,
    RegionWidth: regionWidth,
    RegionHeight: regionHeight,
  };
}

async function resolveSemanticBinding({
  overrideKeyChord,
  bindingName,
  slot,
}) {
  if (overrideKeyChord) {
    return {
      keyChord: overrideKeyChord,
      bindingSource: 'argument',
    };
  }

  const bindings = await loadBindings();
  const configKeyChord =
    slot === undefined
      ? bindings[bindingName]
      : bindings.hotbarSlots?.[String(slot)];

  if (!configKeyChord) {
    const settingName =
      slot === undefined
        ? `"${bindingName}"`
        : `"hotbarSlots.${slot}"`;

    throw new Error(
      `No semantic binding is configured for ${settingName}. Update ${bindingsFilePath} or pass keyChord explicitly.`,
    );
  }

  return {
    keyChord: configKeyChord,
    bindingSource: 'config',
  };
}

function stripAnsi(text) {
  return String(text).replace(/\u001b\[[0-9;]*m/g, '');
}

async function runPowerShell(operation, parameters = {}) {
  const candidates = ['pwsh.exe', 'powershell.exe'];
  const args = [
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    helperScriptPath,
    '-Operation',
    operation,
  ];

  for (const [key, value] of Object.entries(parameters)) {
    if (value === undefined || value === null || value === '') {
      continue;
    }

    args.push(`-${key}`, String(value));
  }

  let lastFailure;

  for (const command of candidates) {
    try {
      return await new Promise((resolve, reject) => {
        const child = spawn(command, args, {
          cwd: __dirname,
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

        child.on('error', (error) => {
          reject(error);
        });

        child.on('close', (code) => {
          const cleanStdout = stripAnsi(stdout).trim();
          const cleanStderr = stripAnsi(stderr).trim();

          if (code !== 0) {
            reject(
              new Error(
                cleanStderr ||
                  cleanStdout ||
                  `PowerShell helper exited with code ${code}.`,
              ),
            );
            return;
          }

          const trimmed = cleanStdout;
          if (!trimmed) {
            reject(new Error('PowerShell helper returned no JSON output.'));
            return;
          }

          try {
            resolve(JSON.parse(trimmed));
          } catch (error) {
            reject(
              new Error(
                `Failed to parse helper JSON output: ${error instanceof Error ? error.message : String(error)}\n${trimmed}`,
              ),
            );
          }
        });
      });
    } catch (error) {
      if (error?.code === 'ENOENT') {
        lastFailure = error;
        continue;
      }

      throw error;
    }
  }

  throw lastFailure ?? new Error('No PowerShell executable was available.');
}

async function runLoggedTool(action, fn) {
  try {
    const payload = await fn();
    await logAction(action, payload);
    return toToolResult(payload);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await logAction(`${action}:error`, { message });
    return toToolError(message);
  }
}

const server = new McpServer(
  {
    name: 'rift-game-mcp',
    version: '0.1.0',
  },
  {
    capabilities: {
      logging: {},
    },
  },
);

server.registerTool(
  'find_game_window',
  {
    title: 'Find and bind game window',
    description:
      'Finds the Rift game window by process name and optional title filter, then binds it for later focus/capture/input tools.',
    inputSchema: {
      processName: z
        .string()
        .default('rift_x64')
        .describe('Target process name without .exe, usually rift_x64.'),
      titleContains: z
        .string()
        .optional()
        .describe('Optional substring that must appear in the window title.'),
    },
  },
  async ({ processName, titleContains }) =>
    runLoggedTool('find_game_window', async () => {
      const raw = await runPowerShell('find', {
        ProcessName: processName,
        TitleContains: titleContains,
      });

      const boundWindow = normalizeFindResult(raw, titleContains);
      updateBoundWindow(boundWindow);

      return {
        bound: true,
        window: boundWindow,
      };
    }),
);

server.registerTool(
  'focus_game_window',
  {
    title: 'Focus bound game window',
    description:
      'Restores and focuses the bound game window. Call this before click_client or send_key.',
  },
  async () =>
    runLoggedTool('focus_game_window', async () => {
      const window = await runPowerShell('focus', buildBoundWindowSpec());
      updateBoundWindow(window);

      return {
        focused: true,
        window: state.boundWindow,
      };
    }),
);

server.registerTool(
  'capture_game_window',
  {
    title: 'Capture bound game window',
    description:
      'Captures a PNG screenshot of the bound game window client area and returns the saved file path.',
  },
  async () =>
    runLoggedTool('capture_game_window', async () => {
      const result = await captureBoundWindow();

      return {
        screenshotPath: result.screenshotPath,
        window: state.boundWindow,
        imageSize: result.imageSize,
      };
    }),
);

server.registerTool(
  'click_client',
  {
    title: 'Click client coordinates',
    description:
      'Clicks at client-area coordinates inside the bound game window. Rejects the action if the bound window is not foreground.',
    inputSchema: {
      x: z.number().int().nonnegative().describe('Client-area X coordinate.'),
      y: z.number().int().nonnegative().describe('Client-area Y coordinate.'),
    },
  },
  async ({ x, y }) =>
    runLoggedTool('click_client', async () => {
      const result = await runPowerShell('click', {
        ...buildBoundWindowSpec(),
        ClientX: x,
        ClientY: y,
      });

      updateBoundWindow(result.window);

      return {
        clicked: true,
        clientPoint: { x, y },
        screenPoint: result.screenPoint,
        window: state.boundWindow,
      };
    }),
);

server.registerTool(
  'send_key',
  {
    title: 'Send key to bound window',
    description:
      'Sends a key or key chord such as "1", "space", or "ctrl+shift+i" to the bound game window. Rejects the action if the bound window is not foreground.',
    inputSchema: {
      keyChord: z
        .string()
        .min(1)
        .describe(
          'Key or chord to send. Use lowercase letters in combos unless Shift is intentional, e.g. "1", "space", "ctrl+i".',
        ),
      holdMilliseconds: z
        .number()
        .int()
        .min(10)
        .max(5000)
        .default(80)
        .describe('How long to hold the main key(s) down.'),
    },
  },
  async ({ keyChord, holdMilliseconds }) =>
    runLoggedTool('send_key', async () => {
      await sendBoundKey(keyChord, holdMilliseconds);

      return {
        sent: true,
        keyChord,
        holdMilliseconds,
        window: state.boundWindow,
      };
    }),
);

server.registerTool(
  'wait_for_frame_change',
  {
    title: 'Wait for frame change',
    description:
      'Waits until the bound game window visibly changes compared with the last capture or an explicit baseline screenshot path.',
    inputSchema: {
      baselineScreenshotPath: z
        .string()
        .optional()
        .describe(
          'Optional existing screenshot path to compare against. Defaults to the last capture_game_window or wait_for_frame_change output.',
        ),
      timeoutMilliseconds: z
        .number()
        .int()
        .min(100)
        .max(60000)
        .default(3000)
        .describe('How long to wait before timing out.'),
      pollIntervalMilliseconds: z
        .number()
        .int()
        .min(25)
        .max(5000)
        .default(150)
        .describe('Delay between capture attempts.'),
      changeThresholdPercent: z
        .number()
        .min(0.01)
        .max(100)
        .default(0.5)
        .describe(
          'Minimum percentage of sampled pixels that must change before the frame is considered different.',
        ),
      regionX: z
        .number()
        .int()
        .nonnegative()
        .optional()
        .describe('Optional client-area region X for targeted change detection.'),
      regionY: z
        .number()
        .int()
        .nonnegative()
        .optional()
        .describe('Optional client-area region Y for targeted change detection.'),
      regionWidth: z
        .number()
        .int()
        .positive()
        .optional()
        .describe('Optional client-area region width for targeted change detection.'),
      regionHeight: z
        .number()
        .int()
        .positive()
        .optional()
        .describe('Optional client-area region height for targeted change detection.'),
    },
  },
  async ({
    baselineScreenshotPath,
    timeoutMilliseconds,
    pollIntervalMilliseconds,
    changeThresholdPercent,
    regionX,
    regionY,
    regionWidth,
    regionHeight,
  }) =>
    runLoggedTool('wait_for_frame_change', async () => {
      let effectiveBaselinePath =
        baselineScreenshotPath || state.lastCapturePath || null;

      if (!effectiveBaselinePath) {
        const baselineCapture = await captureBoundWindow();
        effectiveBaselinePath = baselineCapture.screenshotPath;
      }

      const outputPath = nextScreenshotPath();
      const result = await runPowerShell('wait-for-change', {
        ...buildBoundWindowSpec(),
        BaselinePath: effectiveBaselinePath,
        OutputPath: outputPath,
        TimeoutMilliseconds: timeoutMilliseconds,
        PollIntervalMilliseconds: pollIntervalMilliseconds,
        ChangeThresholdPercent: changeThresholdPercent,
        ...buildRegionParameters({
          regionX,
          regionY,
          regionWidth,
          regionHeight,
        }),
      });

      updateBoundWindow(result.window);
      updateLastCapturePath(result.screenshotPath);

      return {
        changed: result.changed,
        baselineScreenshotPath: effectiveBaselinePath,
        screenshotPath: result.screenshotPath,
        imageSize: result.imageSize,
        attempts: result.attempts,
        elapsedMilliseconds: result.elapsedMilliseconds,
        changePercent: result.changePercent,
        region: result.region,
        window: state.boundWindow,
      };
    }),
);

server.registerTool(
  'open_inventory',
  {
    title: 'Open inventory',
    description:
      'Presses the configured inventory binding for the bound game window. Pass keyChord to override config bindings.',
    inputSchema: {
      keyChord: z
        .string()
        .min(1)
        .optional()
        .describe(
          'Optional override for the inventory key binding. If omitted, tools/rift-game-mcp/config/bindings.json inventory is used.',
        ),
      holdMilliseconds: z
        .number()
        .int()
        .min(10)
        .max(5000)
        .default(80)
        .describe('How long to hold the key down.'),
    },
  },
  async ({ keyChord, holdMilliseconds }) =>
    runLoggedTool('open_inventory', async () => {
      const binding = await resolveSemanticBinding({
        overrideKeyChord: keyChord,
        bindingName: 'inventory',
      });

      await sendBoundKey(binding.keyChord, holdMilliseconds);

      return {
        action: 'open_inventory',
        usedBinding: binding.keyChord,
        bindingSource: binding.bindingSource,
        holdMilliseconds,
        window: state.boundWindow,
      };
    }),
);

server.registerTool(
  'press_hotbar_slot',
  {
    title: 'Press hotbar slot',
    description:
      'Presses a configured hotbar slot binding for the bound game window. Pass keyChord to override config bindings.',
    inputSchema: {
      slot: z
        .number()
        .int()
        .min(1)
        .max(12)
        .describe('Hotbar slot number to activate.'),
      keyChord: z
        .string()
        .min(1)
        .optional()
        .describe(
          'Optional override binding for the requested slot. If omitted, tools/rift-game-mcp/config/bindings.json hotbarSlots is used.',
        ),
      holdMilliseconds: z
        .number()
        .int()
        .min(10)
        .max(5000)
        .default(80)
        .describe('How long to hold the key down.'),
    },
  },
  async ({ slot, keyChord, holdMilliseconds }) =>
    runLoggedTool('press_hotbar_slot', async () => {
      const binding = await resolveSemanticBinding({
        overrideKeyChord: keyChord,
        bindingName: 'hotbarSlots',
        slot,
      });

      await sendBoundKey(binding.keyChord, holdMilliseconds);

      return {
        action: 'press_hotbar_slot',
        slot,
        usedBinding: binding.keyChord,
        bindingSource: binding.bindingSource,
        holdMilliseconds,
        window: state.boundWindow,
      };
    }),
);

await ensureRuntimeDirs();
const transport = new StdioServerTransport();
await server.connect(transport);
