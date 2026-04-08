import { appendFile, mkdir } from 'node:fs/promises';
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

const state = {
  boundWindow: null,
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
      state.boundWindow = boundWindow;

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
      state.boundWindow = {
        ...state.boundWindow,
        ...window,
      };

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
      await ensureRuntimeDirs();
      const screenshotPath = nextScreenshotPath();
      const result = await runPowerShell('capture', {
        ...buildBoundWindowSpec(),
        OutputPath: screenshotPath,
      });

      state.boundWindow = {
        ...state.boundWindow,
        ...result.window,
      };

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

      state.boundWindow = {
        ...state.boundWindow,
        ...result.window,
      };

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
      const result = await runPowerShell('send-key', {
        ...buildBoundWindowSpec(),
        KeyChord: keyChord,
        HoldMilliseconds: holdMilliseconds,
      });

      state.boundWindow = {
        ...state.boundWindow,
        ...result.window,
      };

      return {
        sent: true,
        keyChord,
        holdMilliseconds,
        window: state.boundWindow,
      };
    }),
);

await ensureRuntimeDirs();
const transport = new StdioServerTransport();
await server.connect(transport);
