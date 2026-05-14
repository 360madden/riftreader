import { appendFile, mkdir, readFile, stat, writeFile } from 'node:fs/promises';
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
const repoRoot = path.resolve(__dirname, '..', '..');
const currentTruthPath = path.join(repoRoot, 'docs', 'recovery', 'current-truth.json');
const windowToolsProjectPath = path.join(
  repoRoot,
  'tools',
  'RiftReader.WindowTools',
  'RiftReader.WindowTools.csproj',
);
const windowToolsExePath = path.join(
  repoRoot,
  'tools',
  'RiftReader.WindowTools',
  'bin',
  'Debug',
  'net10.0-windows',
  'RiftReader.WindowTools.exe',
);
const inventoryReferencesDir = path.join(
  repoRoot,
  'artifacts',
  'rift-game-mcp',
  'references',
);
const configDir = path.join(__dirname, 'config');
const bindingsFilePath = path.join(configDir, 'bindings.json');

const defaultBindings = Object.freeze({
  inventory: null,
  inventoryVerification: Object.freeze({
    openReferencePath: null,
    closedReferencePath: null,
    matchThresholdPercent: 3,
    waitForChangeTimeoutMilliseconds: 3000,
    waitForChangePollIntervalMilliseconds: 150,
    changeThresholdPercent: 0.5,
    region: null,
  }),
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

const toolRiskClasses = Object.freeze({
  validate_config: 'readOnly',
  find_game_window: 'readOnly',
  get_bound_window_state: 'readOnly',
  inspect_bound_window: 'readOnly',
  get_riftreader_current_truth: 'readOnly',
  focus_game_window: 'windowMutation',
  capture_game_window: 'readOnly',
  capture_inventory_reference: 'readOnly',
  click_client: 'uiInput',
  send_key: 'uiInput',
  wait_for_frame_change: 'readOnly',
  suggest_inventory_region: 'readOnlyConfigWriteOptional',
  toggle_inventory: 'uiInput',
  ensure_inventory_open: 'uiInput',
  ensure_inventory_closed: 'uiInput',
  open_inventory: 'uiInput',
  open_bags: 'uiInput',
  press_hotbar_slot: 'uiInput',
  resize_game_window: 'windowMutation',
});

const keyModifiers = new Set(['shift', 'ctrl', 'control', 'alt']);
const movementKeys = new Set([
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
const keyAliases = new Map([
  ['arrowup', 'up'],
  ['arrowdown', 'down'],
  ['arrowleft', 'left'],
  ['arrowright', 'right'],
  [' ', 'space'],
]);

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
    mkdir(inventoryReferencesDir, { recursive: true }),
  ]);
}

async function getFileStatus(filePath) {
  if (!filePath) {
    return {
      exists: false,
      isFile: false,
      sizeBytes: null,
    };
  }

  try {
    const stats = await stat(filePath);
    return {
      exists: true,
      isFile: stats.isFile(),
      sizeBytes: stats.size,
    };
  } catch (error) {
    if (error?.code === 'ENOENT') {
      return {
        exists: false,
        isFile: false,
        sizeBytes: null,
      };
    }

    throw error;
  }
}

async function fileExists(filePath) {
  const status = await getFileStatus(filePath);
  return status.exists;
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

function createDetailedError(message, details = {}) {
  const error = new Error(message);
  error.details = details;
  return error;
}

function getErrorDetails(error) {
  if (
    error &&
    typeof error === 'object' &&
    'details' in error &&
    error.details &&
    typeof error.details === 'object'
  ) {
    return error.details;
  }

  return {};
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

function normalizeNumber(value, name, { min } = {}) {
  const normalized = Number(value);
  if (!Number.isFinite(normalized)) {
    throw new Error(`${name} must be a finite number.`);
  }

  if (min !== undefined && normalized < min) {
    throw new Error(`${name} must be greater than or equal to ${min}.`);
  }

  return normalized;
}

function normalizeKeyToken(token) {
  const raw = String(token ?? '');
  const trimmed = raw.trim().toLowerCase();
  const normalized = trimmed || (raw.includes(' ') ? ' ' : '');
  return keyAliases.get(normalized) ?? normalized;
}

function classifyKeyChord(keyChord) {
  const tokens = String(keyChord ?? '')
    .split('+')
    .map(normalizeKeyToken)
    .filter(Boolean);
  const mainKeys = tokens.filter((token) => !keyModifiers.has(token));
  const movementMatches = mainKeys.filter((token) => movementKeys.has(token));
  const hasMovementKey = movementMatches.length > 0;

  return {
    keyChord,
    tokens,
    mainKeys,
    movementKeys: movementMatches,
    riskClass: hasMovementKey ? 'movementInput' : 'uiInput',
    blockedByDefault: hasMovementKey,
    blockReason: hasMovementKey
      ? `movement-risk key(s): ${movementMatches.join(', ')}`
      : null,
  };
}

function getToolRiskClass(action) {
  return toolRiskClasses[action] ?? 'unknown';
}

function normalizeInteger(value, name, { min } = {}) {
  const normalized = Number(value);
  if (!Number.isInteger(normalized)) {
    throw new Error(`${name} must be an integer.`);
  }

  if (min !== undefined && normalized < min) {
    throw new Error(`${name} must be greater than or equal to ${min}.`);
  }

  return normalized;
}

function normalizeConfiguredPath(configuredPath) {
  if (!configuredPath) {
    return null;
  }

  return path.isAbsolute(configuredPath)
    ? path.normalize(configuredPath)
    : path.resolve(configDir, configuredPath);
}

function normalizeVerificationRegion(rawRegion) {
  if (rawRegion === undefined || rawRegion === null) {
    return null;
  }

  if (typeof rawRegion !== 'object' || Array.isArray(rawRegion)) {
    throw new Error(
      'inventoryVerification.region must be an object with x, y, width, and height.',
    );
  }

  return {
    x: normalizeInteger(
      rawRegion.x,
      'inventoryVerification.region.x',
      { min: 0 },
    ),
    y: normalizeInteger(
      rawRegion.y,
      'inventoryVerification.region.y',
      { min: 0 },
    ),
    width: normalizeInteger(
      rawRegion.width,
      'inventoryVerification.region.width',
      { min: 1 },
    ),
    height: normalizeInteger(
      rawRegion.height,
      'inventoryVerification.region.height',
      { min: 1 },
    ),
  };
}

function normalizeInventoryVerification(rawVerification = {}) {
  const source =
    rawVerification &&
    typeof rawVerification === 'object' &&
    !Array.isArray(rawVerification)
      ? rawVerification
      : {};

  return {
    openReferencePath: normalizeConfiguredPath(
      source.openReferencePath ??
        defaultBindings.inventoryVerification.openReferencePath,
    ),
    closedReferencePath: normalizeConfiguredPath(
      source.closedReferencePath ??
        defaultBindings.inventoryVerification.closedReferencePath,
    ),
    matchThresholdPercent:
      source.matchThresholdPercent === undefined
        ? defaultBindings.inventoryVerification.matchThresholdPercent
        : normalizeNumber(
            source.matchThresholdPercent,
            'inventoryVerification.matchThresholdPercent',
            { min: 0.01 },
          ),
    waitForChangeTimeoutMilliseconds:
      source.waitForChangeTimeoutMilliseconds === undefined
        ? defaultBindings.inventoryVerification
            .waitForChangeTimeoutMilliseconds
        : normalizeInteger(
            source.waitForChangeTimeoutMilliseconds,
            'inventoryVerification.waitForChangeTimeoutMilliseconds',
            { min: 100 },
          ),
    waitForChangePollIntervalMilliseconds:
      source.waitForChangePollIntervalMilliseconds === undefined
        ? defaultBindings.inventoryVerification
            .waitForChangePollIntervalMilliseconds
        : normalizeInteger(
            source.waitForChangePollIntervalMilliseconds,
            'inventoryVerification.waitForChangePollIntervalMilliseconds',
            { min: 25 },
          ),
    changeThresholdPercent:
      source.changeThresholdPercent === undefined
        ? defaultBindings.inventoryVerification.changeThresholdPercent
        : normalizeNumber(
            source.changeThresholdPercent,
            'inventoryVerification.changeThresholdPercent',
            { min: 0.01 },
          ),
    region: normalizeVerificationRegion(
      source.region ?? defaultBindings.inventoryVerification.region,
    ),
  };
}

async function loadBindings() {
  await ensureRuntimeDirs();

  try {
    const raw = JSON.parse(await readFile(bindingsFilePath, 'utf8'));
    return {
      inventory: raw.inventory ?? defaultBindings.inventory,
      inventoryVerification: normalizeInventoryVerification(
        raw.inventoryVerification,
      ),
      hotbarSlots: {
        ...defaultBindings.hotbarSlots,
        ...(raw.hotbarSlots ?? {}),
      },
    };
  } catch (error) {
    if (error?.code === 'ENOENT') {
      return {
        inventory: defaultBindings.inventory,
        inventoryVerification: normalizeInventoryVerification(),
        hotbarSlots: { ...defaultBindings.hotbarSlots },
      };
    }

    throw new Error(
      `Failed to load key bindings from ${bindingsFilePath}: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
}

async function loadBindingsDocument() {
  await ensureRuntimeDirs();

  try {
    return JSON.parse(await readFile(bindingsFilePath, 'utf8'));
  } catch (error) {
    if (error?.code === 'ENOENT') {
      return {};
    }

    throw new Error(
      `Failed to load bindings document from ${bindingsFilePath}: ${error instanceof Error ? error.message : String(error)}`,
    );
  }
}

async function saveBindingsDocument(document) {
  await ensureRuntimeDirs();
  await writeFile(
    bindingsFilePath,
    `${JSON.stringify(document, null, 2)}\n`,
    'utf8',
  );
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

function getBoundWindowState() {
  return {
    bound: Boolean(state.boundWindow),
    window: state.boundWindow,
    lastCapturePath: state.lastCapturePath,
    runtime: {
      screenshotsDir,
      logFilePath,
    },
  };
}

async function inspectBoundWindow() {
  const window = await runDotnetWindowTool('inspect', buildBoundWindowSpec());
  updateBoundWindow(window);
  return {
    bound: true,
    window: state.boundWindow,
  };
}

async function getRiftReaderCurrentTruth() {
  const status = await getFileStatus(currentTruthPath);
  if (!status.exists || !status.isFile) {
    return {
      ok: false,
      path: currentTruthPath,
      file: status,
      error: 'current-truth.json was not found.',
    };
  }

  let document;
  try {
    document = JSON.parse(await readFile(currentTruthPath, 'utf8'));
  } catch (error) {
    return {
      ok: false,
      path: currentTruthPath,
      file: status,
      error: `current-truth.json could not be parsed: ${error instanceof Error ? error.message : String(error)}`,
    };
  }

  return {
    ok: true,
    path: currentTruthPath,
    file: status,
    schemaVersion: document.schemaVersion ?? null,
    kind: document.kind ?? null,
    updatedAtUtc: document.updatedAtUtc ?? null,
    status: document.status ?? null,
    target: document.target ?? null,
    liveTestingBoundary: document.liveTestingBoundary ?? null,
    movementGate: document.movementGate ?? null,
    liveReferenceSurface: document.liveReferenceSurface ?? null,
    bestCurrentCandidate: document.bestCurrentCandidate ?? null,
    latestReadOnlyApiRefresh: document.latestReadOnlyApiRefresh ?? null,
    latestReadOnlyMemoryReadback: document.latestReadOnlyMemoryReadback ?? null,
    currentBlockers: document.currentBlockers ?? [],
    nextRecommendedAction: document.nextRecommendedAction ?? null,
    canonicalArtifacts: document.canonicalArtifacts ?? null,
  };
}

async function resizeBoundWindow({ clientWidth, clientHeight, dryRun }) {
  const result = await runDotnetWindowTool('resize', {
    ...buildBoundWindowSpec(),
    ClientWidth: clientWidth,
    ClientHeight: clientHeight,
    DryRun: dryRun,
  });

  if (result.after) {
    updateBoundWindow(result.after);
  } else if (result.before) {
    updateBoundWindow(result.before);
  }

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

function buildRegionParametersFromRegion(region) {
  if (!region) {
    return {};
  }

  return buildRegionParameters({
    regionX: region.x,
    regionY: region.y,
    regionWidth: region.width,
    regionHeight: region.height,
  });
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

function hasInventoryStateReferences(verification) {
  return Boolean(
    verification?.openReferencePath && verification?.closedReferencePath,
  );
}

function buildInventoryVerificationConfigMessage() {
  return `Inventory state verification is not configured. Set inventoryVerification.openReferencePath and inventoryVerification.closedReferencePath in ${bindingsFilePath} to screenshots of the same client size, then optionally set inventoryVerification.region to the bags panel area.`;
}

function getInventoryVerification(bindings, { requireStateReferences = false } = {}) {
  const verification =
    bindings.inventoryVerification ?? normalizeInventoryVerification();

  if (requireStateReferences && !hasInventoryStateReferences(verification)) {
    throw createDetailedError(buildInventoryVerificationConfigMessage(), {
      bindingsFilePath,
      inventoryVerification: verification,
    });
  }

  return verification;
}

function resolveReferencePath(overridePath, configuredPath) {
  if (overridePath) {
    return normalizeConfiguredPath(overridePath);
  }

  return configuredPath ?? null;
}

function buildInventoryReferenceConfigMessage(openReferencePath, closedReferencePath) {
  const missing = [];

  if (!openReferencePath) {
    missing.push('inventoryVerification.openReferencePath');
  }

  if (!closedReferencePath) {
    missing.push('inventoryVerification.closedReferencePath');
  }

  return `Inventory reference screenshots are not configured for region suggestion. Set ${missing.join(' and ')} in ${bindingsFilePath} or pass the reference paths explicitly.`;
}

function isResolvedInventoryState(value) {
  return value === 'open' || value === 'closed';
}

async function compareImages(baselinePath, comparePath, region = null) {
  return runPowerShell('compare-images', {
    BaselinePath: baselinePath,
    ComparePath: comparePath,
    ...buildRegionParametersFromRegion(region),
  });
}

async function detectImageDifferenceRegion({
  baselinePath,
  comparePath,
  paddingPixels = 12,
  region = null,
}) {
  return runPowerShell('detect-diff-region', {
    BaselinePath: baselinePath,
    ComparePath: comparePath,
    PaddingPixels: paddingPixels,
    ...buildRegionParametersFromRegion(region),
  });
}

function addConfigCheck(checks, { id, status, message, details = {} }) {
  checks.push({
    id,
    status,
    message,
    ...(Object.keys(details).length > 0 ? { details } : {}),
  });
}

function summarizeConfigChecks(checks) {
  const errorCount = checks.filter((check) => check.status === 'error').length;
  const warningCount = checks.filter(
    (check) => check.status === 'warning',
  ).length;

  return {
    ok: errorCount === 0,
    errorCount,
    warningCount,
  };
}

async function validateRiftMcpConfig() {
  const checks = [];
  const configFileStatus = await getFileStatus(bindingsFilePath);

  addConfigCheck(checks, {
    id: 'bindings_file',
    status: configFileStatus.exists ? 'ok' : 'warning',
    message: configFileStatus.exists
      ? 'bindings.json exists.'
      : 'bindings.json does not exist; default bindings will be used.',
    details: {
      path: bindingsFilePath,
      ...configFileStatus,
    },
  });

  let bindingsDocument;
  try {
    bindingsDocument = await loadBindingsDocument();
    addConfigCheck(checks, {
      id: 'bindings_json',
      status: 'ok',
      message: 'bindings.json is readable JSON.',
    });
  } catch (error) {
    addConfigCheck(checks, {
      id: 'bindings_json',
      status: 'error',
      message: `bindings.json could not be read or parsed: ${error instanceof Error ? error.message : String(error)}`,
    });

    return {
      ...summarizeConfigChecks(checks),
      configPath: bindingsFilePath,
      inventoryReferencesDir,
      checks,
      capabilities: {
        canUseInventoryBinding: false,
        canUseInventoryToggle: false,
        canUseInventoryEnsure: false,
        canSuggestInventoryRegion: false,
      },
    };
  }

  let bindings;
  try {
    bindings = await loadBindings();
    addConfigCheck(checks, {
      id: 'bindings_schema',
      status: 'ok',
      message: 'bindings.json normalized successfully.',
    });
  } catch (error) {
    addConfigCheck(checks, {
      id: 'bindings_schema',
      status: 'error',
      message: `bindings.json has invalid values: ${error instanceof Error ? error.message : String(error)}`,
    });

    return {
      ...summarizeConfigChecks(checks),
      configPath: bindingsFilePath,
      inventoryReferencesDir,
      checks,
      rawBindings: bindingsDocument,
      capabilities: {
        canUseInventoryBinding: false,
        canUseInventoryToggle: false,
        canUseInventoryEnsure: false,
        canSuggestInventoryRegion: false,
      },
    };
  }

  const inventoryBindingConfigured =
    typeof bindings.inventory === 'string' && bindings.inventory.trim().length > 0;
  addConfigCheck(checks, {
    id: 'inventory_binding',
    status: inventoryBindingConfigured ? 'ok' : 'error',
    message: inventoryBindingConfigured
      ? `Inventory binding is configured as "${bindings.inventory}".`
      : 'Inventory binding is missing. Configure "inventory" or pass keyChord explicitly.',
    details: {
      inventory: bindings.inventory,
    },
  });

  const missingHotbarSlots = [];
  for (let slot = 1; slot <= 12; slot++) {
    const keyChord = bindings.hotbarSlots?.[String(slot)];
    if (typeof keyChord !== 'string' || keyChord.trim().length === 0) {
      missingHotbarSlots.push(slot);
    }
  }

  addConfigCheck(checks, {
    id: 'hotbar_slots',
    status: missingHotbarSlots.length === 0 ? 'ok' : 'warning',
    message:
      missingHotbarSlots.length === 0
        ? 'Hotbar slots 1-12 have bindings.'
        : `Hotbar slots missing bindings: ${missingHotbarSlots.join(', ')}.`,
    details: {
      missingHotbarSlots,
    },
  });

  const verification = bindings.inventoryVerification;
  const openReferenceStatus = await getFileStatus(verification.openReferencePath);
  const closedReferenceStatus = await getFileStatus(
    verification.closedReferencePath,
  );
  const openReferenceUsable = openReferenceStatus.exists && openReferenceStatus.isFile;
  const closedReferenceUsable =
    closedReferenceStatus.exists && closedReferenceStatus.isFile;

  addConfigCheck(checks, {
    id: 'inventory_open_reference',
    status: openReferenceUsable
      ? 'ok'
      : verification.openReferencePath
        ? 'error'
        : 'warning',
    message: openReferenceUsable
      ? 'Inventory-open reference screenshot exists.'
      : verification.openReferencePath
        ? 'Inventory-open reference path is configured but is not a readable file.'
        : 'Inventory-open reference screenshot is not configured.',
    details: {
      path: verification.openReferencePath,
      ...openReferenceStatus,
    },
  });

  addConfigCheck(checks, {
    id: 'inventory_closed_reference',
    status: closedReferenceUsable
      ? 'ok'
      : verification.closedReferencePath
        ? 'error'
        : 'warning',
    message: closedReferenceUsable
      ? 'Inventory-closed reference screenshot exists.'
      : verification.closedReferencePath
        ? 'Inventory-closed reference path is configured but is not a readable file.'
        : 'Inventory-closed reference screenshot is not configured.',
    details: {
      path: verification.closedReferencePath,
      ...closedReferenceStatus,
    },
  });

  addConfigCheck(checks, {
    id: 'inventory_region',
    status: verification.region ? 'ok' : 'warning',
    message: verification.region
      ? 'Inventory verification region is configured.'
      : 'Inventory verification region is not configured; full-screen matching may be noisy.',
    details: {
      region: verification.region,
    },
  });

  let referencesComparable = false;
  let referencesDistinct = false;
  let referenceComparison = null;
  if (openReferenceUsable && closedReferenceUsable) {
    try {
      referenceComparison = await compareImages(
        verification.closedReferencePath,
        verification.openReferencePath,
        verification.region,
      );
      referencesComparable = true;
      referencesDistinct =
        referenceComparison.changePercent > verification.matchThresholdPercent;

      addConfigCheck(checks, {
        id: 'inventory_reference_pair',
        status: referencesDistinct ? 'ok' : 'warning',
        message:
          referencesDistinct
            ? 'Inventory reference screenshots are comparable and visually distinct.'
            : 'Inventory reference screenshots are very similar; state detection may be ambiguous.',
        details: {
          changePercent: referenceComparison.changePercent,
          matchThresholdPercent: verification.matchThresholdPercent,
          region: referenceComparison.region,
          openReferencePath: verification.openReferencePath,
          closedReferencePath: verification.closedReferencePath,
        },
      });
    } catch (error) {
      addConfigCheck(checks, {
        id: 'inventory_reference_pair',
        status: 'error',
        message: `Inventory reference screenshots could not be compared: ${error instanceof Error ? error.message : String(error)}`,
        details: {
          openReferencePath: verification.openReferencePath,
          closedReferencePath: verification.closedReferencePath,
          region: verification.region,
        },
      });
    }
  } else {
    addConfigCheck(checks, {
      id: 'inventory_reference_pair',
      status: 'warning',
      message:
        'Inventory open/closed reference pair is incomplete; ensure_inventory_open and ensure_inventory_closed are not ready.',
    });
  }

  const summary = summarizeConfigChecks(checks);
  return {
    ...summary,
    configPath: bindingsFilePath,
    inventoryReferencesDir,
    checks,
    capabilities: {
      keyboardInputMethod: 'window-message',
      canUseInventoryBinding: inventoryBindingConfigured,
      canUseInventoryToggle: inventoryBindingConfigured,
      canUseInventoryEnsure:
        inventoryBindingConfigured && referencesDistinct && summary.errorCount === 0,
      canSuggestInventoryRegion: openReferenceUsable && closedReferenceUsable,
      inventoryStateVerificationNarrowed: Boolean(verification.region),
    },
    inventoryVerification: verification,
    hotbarSlots: bindings.hotbarSlots,
    referenceComparison,
  };
}

function inventoryReferenceKey(referenceState) {
  return referenceState === 'open' ? 'openReferencePath' : 'closedReferencePath';
}

function resolveInventoryReferenceOutputPath(referenceState, outputPath) {
  if (!outputPath) {
    return path.join(
      inventoryReferencesDir,
      `inventory-${referenceState}-${nowStamp()}.png`,
    );
  }

  return path.isAbsolute(outputPath)
    ? path.normalize(outputPath)
    : path.resolve(inventoryReferencesDir, outputPath);
}

async function captureInventoryReference({
  referenceState,
  outputPath,
  updateBindings,
  overwrite,
}) {
  const resolvedOutputPath = resolveInventoryReferenceOutputPath(
    referenceState,
    outputPath,
  );
  const existing = await fileExists(resolvedOutputPath);
  if (existing && !overwrite) {
    throw new Error(
      `Refusing to overwrite existing inventory reference screenshot: ${resolvedOutputPath}. Pass overwrite=true or choose a different outputPath.`,
    );
  }

  await mkdir(path.dirname(resolvedOutputPath), { recursive: true });
  const capture = await captureBoundWindow(resolvedOutputPath);
  const configKey = inventoryReferenceKey(referenceState);

  if (updateBindings) {
    const bindingsDocument = await loadBindingsDocument();
    bindingsDocument.inventoryVerification = {
      ...(bindingsDocument.inventoryVerification ?? {}),
      [configKey]: capture.screenshotPath,
    };
    await saveBindingsDocument(bindingsDocument);
  }

  return {
    referenceState,
    screenshotPath: capture.screenshotPath,
    imageSize: capture.imageSize,
    updatedBindings: updateBindings,
    updatedConfigKey: updateBindings
      ? `inventoryVerification.${configKey}`
      : null,
    configPath: bindingsFilePath,
    window: state.boundWindow,
  };
}

async function suggestInventoryVerificationRegion({
  openReferencePath,
  closedReferencePath,
  paddingPixels,
  searchRegion = null,
  saveToBindings = false,
}) {
  const bindings = await loadBindings();
  const verification = getInventoryVerification(bindings);
  const resolvedOpenReferencePath = resolveReferencePath(
    openReferencePath,
    verification.openReferencePath,
  );
  const resolvedClosedReferencePath = resolveReferencePath(
    closedReferencePath,
    verification.closedReferencePath,
  );

  if (!resolvedOpenReferencePath || !resolvedClosedReferencePath) {
    throw createDetailedError(
      buildInventoryReferenceConfigMessage(
        resolvedOpenReferencePath,
        resolvedClosedReferencePath,
      ),
      {
        bindingsFilePath,
        inventoryVerification: verification,
      },
    );
  }

  const detection = await detectImageDifferenceRegion({
    baselinePath: resolvedClosedReferencePath,
    comparePath: resolvedOpenReferencePath,
    paddingPixels,
    region: searchRegion,
  });

  if (!detection.hasChanges) {
    throw createDetailedError(
      'No visual difference was found between the configured open/closed inventory reference screenshots. Capture new references with the bags panel clearly closed vs open, then try again.',
      {
        openReferencePath: resolvedOpenReferencePath,
        closedReferencePath: resolvedClosedReferencePath,
        searchRegion,
      },
    );
  }

  const suggestedRegion = normalizeVerificationRegion(detection.region);

  if (saveToBindings) {
    const bindingsDocument = await loadBindingsDocument();
    bindingsDocument.inventoryVerification = {
      ...(bindingsDocument.inventoryVerification ?? {}),
      region: suggestedRegion,
    };
    await saveBindingsDocument(bindingsDocument);
  }

  return {
    suggestedRegion,
    savedToBindings: saveToBindings,
    openReferencePath: resolvedOpenReferencePath,
    closedReferencePath: resolvedClosedReferencePath,
    paddingPixels,
    searchRegion: detection.searchRegion,
    changedPixelCount: detection.changedPixelCount,
    changedPixelPercent: detection.changedPixelPercent,
    rawRegion: detection.rawRegion,
  };
}

async function detectInventoryStateFromScreenshot(screenshotPath, verification) {
  if (!hasInventoryStateReferences(verification)) {
    throw createDetailedError(buildInventoryVerificationConfigMessage(), {
      bindingsFilePath,
      inventoryVerification: verification,
    });
  }

  const openComparison = await compareImages(
    verification.openReferencePath,
    screenshotPath,
    verification.region,
  );
  const closedComparison = await compareImages(
    verification.closedReferencePath,
    screenshotPath,
    verification.region,
  );
  const thresholdPercent = verification.matchThresholdPercent;
  const openMatches = openComparison.changePercent <= thresholdPercent;
  const closedMatches = closedComparison.changePercent <= thresholdPercent;

  let inventoryState = 'unknown';
  if (openMatches && !closedMatches) {
    inventoryState = 'open';
  } else if (closedMatches && !openMatches) {
    inventoryState = 'closed';
  } else if (openMatches && closedMatches) {
    inventoryState = 'ambiguous';
  }

  return {
    state: inventoryState,
    screenshotPath,
    thresholdPercent,
    region: openComparison.region,
    openReferencePath: verification.openReferencePath,
    closedReferencePath: verification.closedReferencePath,
    openComparison: {
      ...openComparison,
      matchesThreshold: openMatches,
    },
    closedComparison: {
      ...closedComparison,
      matchesThreshold: closedMatches,
    },
  };
}

function assertInventoryStateIsKnown(detection, actionName) {
  if (isResolvedInventoryState(detection.state)) {
    return;
  }

  const reason =
    detection.state === 'ambiguous'
      ? 'the current screenshot matches both configured references'
      : 'the current screenshot does not match either configured reference';

  throw createDetailedError(
    `${actionName} requires a known starting inventory state, but ${reason}. Update inventoryVerification in ${bindingsFilePath} or capture better reference screenshots.`,
    {
      detection,
      bindingsFilePath,
    },
  );
}

async function waitForFrameChangeInternal({
  baselineScreenshotPath,
  timeoutMilliseconds = 3000,
  pollIntervalMilliseconds = 150,
  changeThresholdPercent = 0.5,
  region = null,
} = {}) {
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
    ...buildRegionParametersFromRegion(region),
  });

  updateBoundWindow(result.window);
  updateLastCapturePath(result.screenshotPath);

  return {
    ...result,
    baselineScreenshotPath: effectiveBaselinePath,
  };
}

async function runInventoryVerificationAction({
  actionName,
  desiredState = null,
  keyChord,
  holdMilliseconds,
}) {
  const bindings = await loadBindings();
  const binding = await resolveSemanticBinding({
    overrideKeyChord: keyChord,
    bindingName: 'inventory',
  });
  const verification = getInventoryVerification(bindings, {
    requireStateReferences: desiredState !== null,
  });
  const stateVerificationEnabled = hasInventoryStateReferences(verification);

  const beforeCapture = await captureBoundWindow();
  const beforeState = stateVerificationEnabled
    ? await detectInventoryStateFromScreenshot(
        beforeCapture.screenshotPath,
        verification,
      )
    : null;

  if (desiredState !== null) {
    assertInventoryStateIsKnown(beforeState, actionName);

    if (beforeState.state === desiredState) {
      return {
        action: actionName,
        desiredState,
        alreadyInDesiredState: true,
        sent: false,
        usedBinding: binding.keyChord,
        bindingSource: binding.bindingSource,
        holdMilliseconds,
        baselineScreenshotPath: beforeCapture.screenshotPath,
        screenshotPath: beforeCapture.screenshotPath,
        changed: false,
        beforeState,
        afterState: beforeState,
        verification: {
          stateVerificationEnabled,
          ...verification,
        },
        window: state.boundWindow,
      };
    }
  }

  const keyResult = await sendBoundKey(binding.keyChord, holdMilliseconds);

  const waitResult = await waitForFrameChangeInternal({
    baselineScreenshotPath: beforeCapture.screenshotPath,
    timeoutMilliseconds: verification.waitForChangeTimeoutMilliseconds,
    pollIntervalMilliseconds:
      verification.waitForChangePollIntervalMilliseconds,
    changeThresholdPercent: verification.changeThresholdPercent,
    region: verification.region,
  });

  const afterState = stateVerificationEnabled
    ? await detectInventoryStateFromScreenshot(
        waitResult.screenshotPath,
        verification,
      )
    : null;

  if (desiredState !== null) {
    if (afterState.state !== desiredState) {
      const verificationIssue =
        afterState.state === 'ambiguous' || afterState.state === 'unknown'
          ? `Inventory did not verify as ${desiredState} after toggling. The resulting screenshot could not be classified cleanly against the configured references.`
          : `Inventory did not verify as ${desiredState} after toggling. Detected "${afterState.state}" instead.`;

      throw createDetailedError(verificationIssue, {
        beforeState,
        afterState,
        waitResult,
        bindingsFilePath,
      });
    }
  } else if (stateVerificationEnabled) {
    const beforeResolved = isResolvedInventoryState(beforeState?.state);
    const afterResolved = isResolvedInventoryState(afterState?.state);

    if (beforeResolved && afterResolved && beforeState.state === afterState.state) {
      throw createDetailedError(
        `Inventory toggle did not change the verified state. It remained "${afterState.state}" after sending ${binding.keyChord}.`,
        {
          beforeState,
          afterState,
          waitResult,
        },
      );
    }

    if (!waitResult.changed && !afterResolved) {
      throw createDetailedError(
        'Inventory toggle was not visually confirmed. No frame change was detected and the resulting inventory state could not be verified.',
        {
          beforeState,
          afterState,
          waitResult,
        },
      );
    }
  } else if (!waitResult.changed) {
    throw createDetailedError(
      'Inventory toggle was not visually confirmed because no frame change was detected. Check chat/text-entry focus, the configured key binding, or use a narrower inventoryVerification.region.',
      {
        waitResult,
        bindingsFilePath,
      },
    );
  }

  return {
    action: actionName,
    desiredState,
    alreadyInDesiredState: false,
    sent: true,
    usedBinding: binding.keyChord,
    bindingSource: binding.bindingSource,
    keyboardInputMethod: keyResult.keyboardInputMethod,
    holdMilliseconds,
    baselineScreenshotPath: beforeCapture.screenshotPath,
    screenshotPath: waitResult.screenshotPath,
    changed: waitResult.changed,
    attempts: waitResult.attempts,
    elapsedMilliseconds: waitResult.elapsedMilliseconds,
    changePercent: waitResult.changePercent,
    region: waitResult.region,
    beforeState,
    afterState,
    verification: {
      stateVerificationEnabled,
      ...verification,
    },
    window: state.boundWindow,
  };
}

function stripAnsi(text) {
  return String(text).replace(/\u001b\[[0-9;]*m/g, '');
}

function buildWindowToolArgs(command, parameters = {}) {
  const optionMap = new Map([
    ['WindowHandle', '--hwnd'],
    ['ExpectedProcessId', '--expected-pid'],
    ['ExpectedProcessName', '--expected-process-name'],
    ['ExpectedTitleContains', '--expected-title-contains'],
    ['ClientWidth', '--client-width'],
    ['ClientHeight', '--client-height'],
    ['DryRun', '--dry-run'],
  ]);
  const args = [command, '--json'];

  for (const [key, value] of Object.entries(parameters)) {
    if (value === undefined || value === null || value === '') {
      continue;
    }

    const optionName = optionMap.get(key);
    if (!optionName) {
      throw new Error(`Unsupported RiftReader.WindowTools parameter: ${key}`);
    }

    args.push(optionName, String(value));
  }

  return args;
}

async function runDotnetWindowTool(command, parameters = {}) {
  const toolArgs = buildWindowToolArgs(command, parameters);
  const useBuiltExe = await fileExists(windowToolsExePath);
  const executable = useBuiltExe ? windowToolsExePath : 'dotnet';
  const args = useBuiltExe
    ? toolArgs
    : ['run', '--project', windowToolsProjectPath, '--', ...toolArgs];

  return await new Promise((resolve, reject) => {
    const child = spawn(executable, args, {
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

    child.on('error', (error) => {
      reject(error);
    });

    child.on('close', (code) => {
      const cleanStdout = stripAnsi(stdout).trim();
      const cleanStderr = stripAnsi(stderr).trim();
      let parsedStdout = null;

      if (cleanStdout) {
        try {
          parsedStdout = JSON.parse(cleanStdout);
        } catch {
          parsedStdout = null;
        }
      }

      if (code !== 0) {
        const message =
          parsedStdout?.error ||
          cleanStderr ||
          cleanStdout ||
          `RiftReader.WindowTools exited with code ${code}.`;
        reject(
          createDetailedError(message, {
            helper: 'RiftReader.WindowTools',
            exitCode: code,
            status: parsedStdout?.status ?? 'failed',
            output: parsedStdout,
            stderr: cleanStderr || null,
          }),
        );
        return;
      }

      if (!cleanStdout) {
        reject(new Error('RiftReader.WindowTools returned no JSON output.'));
        return;
      }

      if (!parsedStdout) {
        reject(
          new Error(
            `Failed to parse RiftReader.WindowTools JSON output.\n${cleanStdout}`,
          ),
        );
        return;
      }

      resolve(parsedStdout);
    });
  });
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
  const startedAtUtc = new Date();
  const startedMs = Date.now();
  const riskClass = getToolRiskClass(action);
  try {
    const payload = await fn();
    const endedAtUtc = new Date();
    await logAction(action, {
      status: 'passed',
      riskClass,
      startedAtUtc: startedAtUtc.toISOString(),
      endedAtUtc: endedAtUtc.toISOString(),
      durationMs: endedAtUtc.getTime() - startedMs,
      boundWindow: state.boundWindow,
      result: payload,
    });
    return toToolResult(payload);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const details = getErrorDetails(error);
    const endedAtUtc = new Date();
    await logAction(`${action}:error`, {
      status: 'failed',
      riskClass,
      startedAtUtc: startedAtUtc.toISOString(),
      endedAtUtc: endedAtUtc.toISOString(),
      durationMs: endedAtUtc.getTime() - startedMs,
      boundWindow: state.boundWindow,
      message,
      ...details,
    });
    return toToolError(message, details);
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
  'validate_config',
  {
    title: 'Validate Rift MCP config',
    description:
      'Checks tools/rift-game-mcp/config/bindings.json, configured inventory references, hotbar bindings, and readiness for inventory state verification. Does not require or control the live game window.',
  },
  async () =>
    runLoggedTool('validate_config', async () => validateRiftMcpConfig()),
);

server.registerTool(
  'find_game_window',
  {
    title: 'Find and bind game window',
    description:
      'Finds the Rift game window by exact process id/window handle or by process name and optional title filter, then binds it for later focus/capture/input tools.',
    inputSchema: {
      processId: z
        .number()
        .int()
        .positive()
        .optional()
        .describe('Exact target process id. Prefer this when more than one Rift client is running.'),
      windowHandle: z
        .string()
        .optional()
        .describe('Exact target window handle, decimal or hex like 0x109126C. Strongest binding selector.'),
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
  async ({ processId, windowHandle, processName, titleContains }) =>
    runLoggedTool('find_game_window', async () => {
      const raw = await runPowerShell('find', {
        ProcessId: processId,
        WindowHandle: windowHandle,
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
  'get_bound_window_state',
  {
    title: 'Get bound game window state',
    description:
      'Returns the MCP session bound-window state and last capture path without touching the live game window.',
  },
  async () =>
    runLoggedTool('get_bound_window_state', async () => getBoundWindowState()),
);

server.registerTool(
  'inspect_bound_window',
  {
    title: 'Inspect bound game window',
    description:
      'Re-checks the bound Rift window against the stored exact HWND/process identity and returns current window/client rectangles. Read-only.',
  },
  async () =>
    runLoggedTool('inspect_bound_window', async () => inspectBoundWindow()),
);

server.registerTool(
  'get_riftreader_current_truth',
  {
    title: 'Get RiftReader current truth',
    description:
      'Reads docs/recovery/current-truth.json and returns the current target, live-testing boundary, movement gate, latest proof/readback status, and blockers. Read-only.',
  },
  async () =>
    runLoggedTool('get_riftreader_current_truth', async () =>
      getRiftReaderCurrentTruth(),
    ),
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
  'resize_game_window',
  {
    title: 'Resize bound game window',
    description:
      'Resizes the bound game window to an exact client-area width/height. Defaults to dry-run; pass dryRun=false to apply. Does not send game input.',
    inputSchema: {
      clientWidth: z
        .number()
        .int()
        .min(160)
        .max(7680)
        .describe('Requested game client-area width in pixels.'),
      clientHeight: z
        .number()
        .int()
        .min(120)
        .max(4320)
        .describe('Requested game client-area height in pixels.'),
      dryRun: z
        .boolean()
        .default(true)
        .describe(
          'When true, only reports the resize plan. Set false to call SetWindowPos.',
        ),
    },
  },
  async ({ clientWidth, clientHeight, dryRun }) =>
    runLoggedTool('resize_game_window', async () => {
      const result = await resizeBoundWindow({
        clientWidth,
        clientHeight,
        dryRun,
      });

      return {
        resized: Boolean(result.resizeApplied),
        dryRun: Boolean(result.dryRun),
        resizeOk: Boolean(result.resizeOk),
        requestedClientSize: result.requestedClientSize,
        requestedWindow: result.requestedWindow,
        border: result.border,
        before: result.before,
        after: result.after,
        window: state.boundWindow,
      };
    }),
);

server.registerTool(
  'capture_inventory_reference',
  {
    title: 'Capture inventory reference',
    description:
      'Captures the currently visible bound game window as an inventory open/closed reference screenshot and can update bindings.json. This does not toggle bags; visually put bags in the requested state first.',
    inputSchema: {
      referenceState: z
        .enum(['open', 'closed'])
        .describe('The inventory state visible in the current game window.'),
      outputPath: z
        .string()
        .min(1)
        .optional()
        .describe(
          'Optional output PNG path. Relative paths are resolved under artifacts/rift-game-mcp/references. If omitted, a timestamped path is used.',
        ),
      updateBindings: z
        .boolean()
        .default(true)
        .describe(
          'When true, writes the captured path into inventoryVerification.openReferencePath or closedReferencePath.',
        ),
      overwrite: z
        .boolean()
        .default(false)
        .describe(
          'When false, refuses to overwrite an existing outputPath.',
        ),
    },
  },
  async ({ referenceState, outputPath, updateBindings, overwrite }) =>
    runLoggedTool('capture_inventory_reference', async () =>
      captureInventoryReference({
        referenceState,
        outputPath,
        updateBindings,
        overwrite,
      }),
    ),
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
      dryRun: z
        .boolean()
        .default(false)
        .describe('When true, classifies the key and returns the plan without sending input.'),
      allowMovementKeys: z
        .boolean()
        .default(false)
        .describe(
          'Required to actually send movement-risk keys such as W/A/S/D/Q/E, arrows, or Space.',
        ),
    },
  },
  async ({ keyChord, holdMilliseconds, dryRun, allowMovementKeys }) =>
    runLoggedTool('send_key', async () => {
      const keyClassification = classifyKeyChord(keyChord);
      const blockedByMovementPolicy =
        keyClassification.blockedByDefault && !allowMovementKeys;

      if (dryRun) {
        return {
          sent: false,
          dryRun: true,
          wouldSend: !blockedByMovementPolicy,
          keyChord,
          keyClassification,
          allowMovementKeys,
          holdMilliseconds,
          window: state.boundWindow,
        };
      }

      if (blockedByMovementPolicy) {
        throw createDetailedError(
          `Refusing send_key for movement-risk keyChord "${keyChord}". Pass allowMovementKeys=true only after the current movement/input approval gate is satisfied.`,
          {
            keyClassification,
            allowMovementKeys,
            holdMilliseconds,
          },
        );
      }

      const keyResult = await sendBoundKey(keyChord, holdMilliseconds);

      return {
        sent: true,
        keyChord,
        keyClassification,
        allowMovementKeys,
        keyboardInputMethod: keyResult.keyboardInputMethod,
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
      const result = await waitForFrameChangeInternal({
        baselineScreenshotPath,
        timeoutMilliseconds,
        pollIntervalMilliseconds,
        changeThresholdPercent,
        region:
          regionX === undefined &&
          regionY === undefined &&
          regionWidth === undefined &&
          regionHeight === undefined
            ? null
            : {
                x: regionX,
                y: regionY,
                width: regionWidth,
                height: regionHeight,
              },
      });

      return {
        changed: result.changed,
        baselineScreenshotPath: result.baselineScreenshotPath,
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
  'suggest_inventory_region',
  {
    title: 'Suggest inventory verification region',
    description:
      'Finds the changed panel area between open/closed bags reference screenshots and can optionally save the suggested region into tools/rift-game-mcp/config/bindings.json.',
    inputSchema: {
      openReferencePath: z
        .string()
        .min(1)
        .optional()
        .describe(
          'Optional override path to the bags-open reference screenshot. If omitted, inventoryVerification.openReferencePath from bindings.json is used.',
        ),
      closedReferencePath: z
        .string()
        .min(1)
        .optional()
        .describe(
          'Optional override path to the bags-closed reference screenshot. If omitted, inventoryVerification.closedReferencePath from bindings.json is used.',
        ),
      paddingPixels: z
        .number()
        .int()
        .min(0)
        .max(500)
        .default(12)
        .describe(
          'Extra padding added around the detected changed area before returning the suggested region.',
        ),
      saveToBindings: z
        .boolean()
        .default(false)
        .describe(
          'When true, writes the suggested region into tools/rift-game-mcp/config/bindings.json inventoryVerification.region.',
        ),
      regionX: z
        .number()
        .int()
        .nonnegative()
        .optional()
        .describe('Optional X of a search region that limits where the diff detector looks.'),
      regionY: z
        .number()
        .int()
        .nonnegative()
        .optional()
        .describe('Optional Y of a search region that limits where the diff detector looks.'),
      regionWidth: z
        .number()
        .int()
        .positive()
        .optional()
        .describe('Optional width of a search region that limits where the diff detector looks.'),
      regionHeight: z
        .number()
        .int()
        .positive()
        .optional()
        .describe('Optional height of a search region that limits where the diff detector looks.'),
    },
  },
  async ({
    openReferencePath,
    closedReferencePath,
    paddingPixels,
    saveToBindings,
    regionX,
    regionY,
    regionWidth,
    regionHeight,
  }) =>
    runLoggedTool('suggest_inventory_region', async () =>
      suggestInventoryVerificationRegion({
        openReferencePath,
        closedReferencePath,
        paddingPixels,
        saveToBindings,
        searchRegion:
          regionX === undefined &&
          regionY === undefined &&
          regionWidth === undefined &&
          regionHeight === undefined
            ? null
            : {
                x: regionX,
                y: regionY,
                width: regionWidth,
                height: regionHeight,
              },
      }),
    ),
);

server.registerTool(
  'toggle_inventory',
  {
    title: 'Toggle inventory',
    description:
      'Toggles the configured bags/inventory binding, then verifies that the window changed. If inventory reference screenshots are configured, it also reports the detected before/after state.',
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
    runLoggedTool('toggle_inventory', async () =>
      runInventoryVerificationAction({
        actionName: 'toggle_inventory',
        keyChord,
        holdMilliseconds,
      }),
    ),
);

server.registerTool(
  'ensure_inventory_open',
  {
    title: 'Ensure inventory open',
    description:
      'Uses configured inventory reference screenshots to verify whether bags are already open and only toggles when it can safely confirm the current state.',
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
    runLoggedTool('ensure_inventory_open', async () =>
      runInventoryVerificationAction({
        actionName: 'ensure_inventory_open',
        desiredState: 'open',
        keyChord,
        holdMilliseconds,
      }),
    ),
);

server.registerTool(
  'ensure_inventory_closed',
  {
    title: 'Ensure inventory closed',
    description:
      'Uses configured inventory reference screenshots to verify whether bags are already closed and only toggles when it can safely confirm the current state.',
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
    runLoggedTool('ensure_inventory_closed', async () =>
      runInventoryVerificationAction({
        actionName: 'ensure_inventory_closed',
        desiredState: 'closed',
        keyChord,
        holdMilliseconds,
      }),
    ),
);

server.registerTool(
  'open_inventory',
  {
    title: 'Press inventory binding',
    description:
      'Presses the configured inventory binding for the bound game window. This is usually a toggle; use ensure_inventory_open or ensure_inventory_closed when you need a verified final state.',
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

      const keyResult = await sendBoundKey(binding.keyChord, holdMilliseconds);

      return {
        action: 'open_inventory',
        usedBinding: binding.keyChord,
        bindingSource: binding.bindingSource,
        keyboardInputMethod: keyResult.keyboardInputMethod,
        holdMilliseconds,
        window: state.boundWindow,
      };
    }),
);

server.registerTool(
  'open_bags',
  {
    title: 'Press bags binding',
    description:
      'Alias for open_inventory. This sends the configured bags/inventory key as-is; use ensure_inventory_open or ensure_inventory_closed when you need a verified state.',
    inputSchema: {
      keyChord: z
        .string()
        .min(1)
        .optional()
        .describe(
          'Optional override for the bags/inventory key binding. If omitted, tools/rift-game-mcp/config/bindings.json inventory is used.',
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
    runLoggedTool('open_bags', async () => {
      const binding = await resolveSemanticBinding({
        overrideKeyChord: keyChord,
        bindingName: 'inventory',
      });

      const keyResult = await sendBoundKey(binding.keyChord, holdMilliseconds);

      return {
        action: 'open_bags',
        usedBinding: binding.keyChord,
        bindingSource: binding.bindingSource,
        keyboardInputMethod: keyResult.keyboardInputMethod,
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

      const keyResult = await sendBoundKey(binding.keyChord, holdMilliseconds);

      return {
        action: 'press_hotbar_slot',
        slot,
        usedBinding: binding.keyChord,
        bindingSource: binding.bindingSource,
        keyboardInputMethod: keyResult.keyboardInputMethod,
        holdMilliseconds,
        window: state.boundWindow,
      };
    }),
);

await ensureRuntimeDirs();
const transport = new StdioServerTransport();
await server.connect(transport);
