const state = {
  status: null,
  latestAction: null,
  actionsByKey: new Map(),
  busy: false,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function asText(value, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function clear(node) {
  if (node) node.replaceChildren();
}

function setText(id, value, fallback = "—") {
  const node = document.getElementById(id);
  if (node) node.textContent = asText(value, fallback);
}

function pretty(value) {
  return JSON.stringify(value ?? null, null, 2);
}

function statusClass(ok, status) {
  const normalized = String(status ?? "").toLowerCase();
  if (["blocked", "failed", "stopped", "not_running", "service_configured_not_running"].includes(normalized) || ok === false) return "badge--bad";
  if (ok === true || ["passed", "ready", "running", "started", "service_only"].includes(normalized)) return "badge--good";
  if (["skipped", "disabled", "not-started", "unknown"].includes(normalized)) return "badge--neutral";
  return "badge--warn";
}

function makeBadge(label, ok, status) {
  const span = document.createElement("span");
  span.className = `badge ${statusClass(ok, status)}`;
  span.textContent = `${label}: ${asText(status ?? ok)}`;
  return span;
}

function showToast(message, tone = "neutral") {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.hidden = false;
  toast.textContent = message;
  toast.style.borderColor = tone === "bad" ? "rgba(251, 113, 133, 0.72)" : tone === "good" ? "rgba(52, 211, 153, 0.72)" : "rgba(148, 163, 184, 0.36)";
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toast.hidden = true;
  }, 4200);
}

function setBusy(isBusy) {
  state.busy = isBusy;
  document.body.classList.toggle("is-busy", isBusy);
  $$("button, select").forEach((node) => {
    if (node.id === "actionSelect") node.disabled = isBusy;
    if (node.tagName === "BUTTON") node.disabled = isBusy;
  });
}

async function copyText(text, label = "Copied") {
  const value = String(text ?? "");
  if (!value) {
    showToast("Nothing to copy.", "bad");
    return;
  }
  try {
    await navigator.clipboard.writeText(value);
  } catch {
    const temp = document.createElement("textarea");
    temp.value = value;
    temp.style.position = "fixed";
    temp.style.left = "-9999px";
    document.body.appendChild(temp);
    temp.select();
    document.execCommand("copy");
    temp.remove();
  }
  showToast(label, "good");
}

function detailItem(label, value) {
  const item = document.createElement("div");
  item.className = "detail-item";
  const labelNode = document.createElement("div");
  labelNode.className = "detail-item__label";
  labelNode.textContent = label;
  const valueNode = document.createElement("div");
  valueNode.className = "detail-item__value";
  valueNode.textContent = asText(value);
  item.append(labelNode, valueNode);
  return item;
}

function summaryItem(label, value) {
  const item = document.createElement("div");
  item.className = "summary-item";
  const labelNode = document.createElement("div");
  labelNode.className = "summary-item__label";
  labelNode.textContent = label;
  const valueNode = document.createElement("div");
  valueNode.className = "summary-item__value";
  valueNode.textContent = asText(value);
  item.append(labelNode, valueNode);
  return item;
}

function copyRow(label, text) {
  const row = document.createElement("div");
  row.className = "copy-row";
  const code = document.createElement("div");
  code.className = "code-pill";
  code.textContent = text || "unavailable";
  const button = document.createElement("button");
  button.className = "button button--secondary";
  button.type = "button";
  button.textContent = `Copy ${label}`;
  button.addEventListener("click", () => copyText(text, `${label} copied.`));
  row.append(code, button);
  return row;
}

function actionCard(action, includeButton = true) {
  const card = document.createElement("div");
  card.className = "action-card";
  const top = document.createElement("div");
  top.className = "action-card__title";
  const title = document.createElement("span");
  title.textContent = action.label || action.key;
  const meta = document.createElement("span");
  meta.className = "badge badge--neutral";
  meta.textContent = action.category || "action";
  top.append(title, meta);
  const desc = document.createElement("div");
  desc.className = "action-card__desc";
  desc.textContent = action.description || "";
  card.append(top, desc);
  if (action.commandText) {
    const command = document.createElement("div");
    command.className = "code-pill";
    command.style.marginTop = "10px";
    command.textContent = action.commandText;
    card.append(command);
  }
  if (includeButton) {
    const button = document.createElement("button");
    button.className = "button button--secondary";
    button.type = "button";
    button.style.marginTop = "10px";
    button.textContent = action.requiresConfirmation ? "Run with confirmation" : "Run";
    button.addEventListener("click", () => runAction(action.key));
    card.append(button);
  }
  return card;
}

function findBadge(status, key) {
  return (status?.dashboardStatus?.readinessBadges || []).find((badge) => badge.key === key) || {};
}

function renderMetrics(status) {
  const backend = status?.dashboardStatus?.backend || {};
  const route = status?.dashboardStatus?.domain || {};
  const finalGate = findBadge(status, "repo-final-gate");
  setText("metricBackend", backend.connect?.ok ? "Running" : "Stopped");
  setText("metricBackendDetail", `${backend.host || "127.0.0.1"}:${backend.port || "8770"}`);
  setText("metricRoute", route.publicSmoke?.ok ? "Reachable" : route.dns?.ok ? "DNS OK" : "Blocked");
  setText("metricRouteDetail", status?.route?.publicMcpUrl);
  setText("metricFinalGate", finalGate.status || "unknown");
  setText("metricFinalGateDetail", (finalGate.blockers || []).slice(0, 2).join(", ") || "no blockers listed");
  setText("metricToolSurface", `${status?.toolSurface?.expectedToolCount || "?"} tools`);
  setText("metricToolSurfaceDetail", status?.toolSurface?.finalProofMode);

  const overallBadge = document.getElementById("overallBadge");
  if (overallBadge) {
    overallBadge.className = `badge ${statusClass(status?.ok, status?.status)}`;
    overallBadge.textContent = `Overall: ${asText(status?.status)}`;
  }
}

function renderOverview(status) {
  const backend = status?.dashboardStatus?.backend || {};
  const finalGate = findBadge(status, "repo-final-gate");
  const overview = document.getElementById("overviewSummary");
  clear(overview);
  overview?.append(
    summaryItem("Local backend", `${backend.host || "127.0.0.1"}:${backend.port || "8770"} · ${backend.connect?.ok ? "running" : "not listening"}`),
    summaryItem("ChatGPT Server URL", status?.chatGpt?.serverUrl),
    summaryItem("Authentication", status?.chatGpt?.authentication),
    summaryItem("Named tunnel", status?.route?.namedTunnel),
    summaryItem("Final gate", `${finalGate.status || "unknown"} · ${(finalGate.blockers || []).length} blockers`),
    summaryItem("Tool surface", `${status?.toolSurface?.expectedToolCount} expected tools`)
  );

  const summary = document.getElementById("chatGptSummary");
  clear(summary);
  [
    ["Surface", status?.chatGpt?.surface],
    ["App", status?.chatGpt?.appName],
    ["Server URL", status?.chatGpt?.serverUrl],
    ["Auth", status?.chatGpt?.authentication],
    ["Starts server?", status?.chatGpt?.connectorStartsServer ? "yes" : "no"],
  ].forEach(([label, value]) => {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = asText(value);
    summary?.append(dt, dd);
  });

  renderRecommendedActions(status);
}

function renderRecommendedActions(status) {
  const target = document.getElementById("recommendedActions");
  clear(target);
  const recommendations = [];
  if (!status?.dashboardStatus?.backend?.connect?.ok) recommendations.push("start_full_server");
  const finalGate = findBadge(status, "repo-final-gate");
  if (finalGate.ok !== true) recommendations.push("final_gate");
  if (status?.dashboardStatus?.domain?.publicSmoke?.ok !== true) {
    recommendations.push("cloudflared_status", "domain_diagnostics");
  }
  if (!status?.dashboardStatus?.proof?.latestTemplatePath) recommendations.push("write_proof_template");
  recommendations.push("mcp_trial_readiness");

  [...new Set(recommendations)].slice(0, 6).forEach((key) => {
    const action = state.actionsByKey.get(key);
    if (action) target?.append(actionCard(action));
  });
}

function renderServer(status) {
  const managed = status?.managedServer || {};
  const badge = document.getElementById("managedServerBadge");
  if (badge) {
    badge.className = `badge ${statusClass(managed.ok, managed.status)}`;
    badge.textContent = `Managed: ${asText(managed.status)}`;
  }
  const details = document.getElementById("serverDetails");
  clear(details);
  details?.append(
    detailItem("Tracked", managed.tracked),
    detailItem("Profile", managed.profile),
    detailItem("PID", managed.pid),
    detailItem("Started UTC", managed.startedAtUtc),
    detailItem("State file", managed.statePath),
    detailItem("Stop scope", managed.stopScope)
  );

  const commands = document.getElementById("serverCommands");
  clear(commands);
  commands?.append(
    copyRow("full server", 'cd /d "C:\\RIFT MODDING\\RiftReader" && START_RIFTREADER_CHATGPT_MCP.cmd'),
    copyRow("read-only server", 'cd /d "C:\\RIFT MODDING\\RiftReader" && START_RIFTREADER_CHATGPT_MCP.cmd readonly'),
    copyRow("health check", 'cd /d "C:\\RIFT MODDING\\RiftReader" && START_RIFTREADER_CHATGPT_MCP.cmd --call health --json')
  );
}

function renderReadiness(status) {
  const target = document.getElementById("readinessBadges");
  clear(target);
  (status?.dashboardStatus?.readinessBadges || []).forEach((item) => {
    const card = document.createElement("div");
    card.className = "badge-card";
    const top = document.createElement("div");
    top.className = "badge-card__top";
    const title = document.createElement("strong");
    title.textContent = item.label || item.key;
    top.append(title, makeBadge(item.key || "status", item.ok, item.status));
    card.append(top);
    const blockers = item.blockers || [];
    if (blockers.length) {
      const list = document.createElement("ul");
      blockers.forEach((blocker) => {
        const li = document.createElement("li");
        li.textContent = blocker;
        list.append(li);
      });
      card.append(list);
    }
    target?.append(card);
  });
  const mission = document.getElementById("missionControl");
  if (mission) mission.textContent = pretty(status?.dashboardStatus?.missionControl || {});
}

function renderRoute(status) {
  const details = document.getElementById("routeDetails");
  clear(details);
  details?.append(
    detailItem("Server URL", status?.route?.publicMcpUrl),
    detailItem("Local backend", status?.route?.localBackend),
    detailItem("Named tunnel", status?.route?.namedTunnel),
    detailItem("Cloudflare rule", status?.route?.browserIntegrityRule),
    detailItem("DNS", status?.dashboardStatus?.domain?.dns?.status),
    detailItem("Public smoke", status?.dashboardStatus?.domain?.publicSmoke?.status)
  );
  const checklist = document.getElementById("chatGptChecklist");
  clear(checklist);
  [
    `Run or confirm the local adapter is listening at ${status?.route?.localBackend || "http://127.0.0.1:8770/mcp"}.`,
    `Confirm Cloudflared named tunnel ${status?.route?.namedTunnel || "riftreader-mcp-360madden"} is healthy.`,
    `In ChatGPT Web/Desktop Developer Mode, use Server URL ${status?.route?.publicMcpUrl || "https://mcp.360madden.com/mcp"}.`,
    "Use No Authentication.",
    "Run health, repo status, proposal, draft, dry-run, and approval-block checks before recording actual-client proof.",
  ].forEach((text) => {
    const li = document.createElement("li");
    li.textContent = text;
    checklist?.append(li);
  });
  const domain = document.getElementById("domainDiagnostics");
  if (domain) domain.textContent = pretty(status?.dashboardStatus?.domain || {});
}

function renderProof(status) {
  const proof = status?.dashboardStatus?.proof || {};
  const details = document.getElementById("proofDetails");
  clear(details);
  details?.append(
    detailItem("Final proof mode", status?.toolSurface?.finalProofMode),
    detailItem("Latest template", proof.latestTemplatePath),
    detailItem("Template mode", proof.latestTemplateProofMode),
    detailItem("Latest proof", proof.latestProofPath),
    detailItem("Proof status", proof.latestProofStatus),
    detailItem("Expected tool count", status?.toolSurface?.expectedToolCount)
  );
  const tools = document.getElementById("toolSurface");
  clear(tools);
  (status?.toolSurface?.expectedToolNames || []).forEach((name) => {
    const chip = document.createElement("span");
    chip.className = "code-pill";
    chip.textContent = name;
    tools?.append(chip);
  });
}

function renderValidation(status) {
  const latest = document.getElementById("latestActionResult");
  if (latest) latest.textContent = state.latestAction ? pretty(state.latestAction) : "No action run yet.";
  const history = document.getElementById("recentActions");
  clear(history);
  (status?.recentActions || []).slice().reverse().forEach((item) => {
    const row = document.createElement("div");
    row.className = "history-item";
    const meta = document.createElement("div");
    meta.className = "history-item__meta";
    const label = document.createElement("span");
    label.className = "history-item__label";
    label.textContent = item.action?.label || item.action?.key || "action";
    meta.append(label, makeBadge("result", item.ok, item.status));
    const time = document.createElement("div");
    time.className = "muted";
    time.textContent = item.generatedAtUtc || "";
    row.append(meta, time);
    history?.append(row);
  });
  if (history && !history.childElementCount) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "No action history yet.";
    history.append(empty);
  }
}

function renderLogs(status) {
  setText("stdoutTail", status?.managedServer?.stdoutTail, "No stdout log yet.");
  setText("stderrTail", status?.managedServer?.stderrTail, "No stderr log yet.");
  setText("statusJson", pretty(status));
}

function renderSafety(status) {
  const safety = document.getElementById("safetyGrid");
  clear(safety);
  Object.entries(status?.safety || {}).forEach(([key, value]) => {
    const item = document.createElement("div");
    item.className = "safety-item";
    const label = document.createElement("div");
    label.className = "safety-item__label";
    label.textContent = key;
    const val = document.createElement("div");
    val.className = "safety-item__value";
    val.textContent = asText(value);
    item.append(label, val);
    safety?.append(item);
  });

  const registry = document.getElementById("actionRegistry");
  clear(registry);
  (status?.actions || []).forEach((action) => registry?.append(actionCard(action, false)));
}

function populateActionSelect(actions) {
  state.actionsByKey = new Map((actions || []).map((action) => [action.key, action]));
  const select = document.getElementById("actionSelect");
  const previousValue = select?.value;
  clear(select);
  const groups = new Map();
  (actions || []).forEach((action) => {
    const category = action.category || "other";
    if (!groups.has(category)) groups.set(category, []);
    groups.get(category).push(action);
  });
  groups.forEach((items, category) => {
    const group = document.createElement("optgroup");
    group.label = category;
    items.forEach((action) => {
      const option = document.createElement("option");
      option.value = action.key;
      option.textContent = action.label || action.key;
      group.append(option);
    });
    select?.append(group);
  });
  if (previousValue && state.actionsByKey.has(previousValue) && select) {
    select.value = previousValue;
  }
  updateActionHint();
}

function updateActionHint() {
  const select = document.getElementById("actionSelect");
  const hint = document.getElementById("actionHint");
  const action = state.actionsByKey.get(select?.value);
  if (hint) {
    hint.textContent = action
      ? `${action.description}${action.requiresConfirmation ? " Confirmation required." : ""}`
      : "Actions are fixed allowlisted workflows; there is no arbitrary shell endpoint.";
  }
}

function render(status) {
  if (!status) return;
  populateActionSelect(status.actions || []);
  renderMetrics(status);
  renderOverview(status);
  renderServer(status);
  renderReadiness(status);
  renderRoute(status);
  renderProof(status);
  renderValidation(status);
  renderLogs(status);
  renderSafety(status);
}

async function refreshStatus({ publicSmoke = false, force = false } = {}) {
  const query = new URLSearchParams();
  if (publicSmoke) query.set("publicSmoke", "1");
  if (force) query.set("force", "1");
  const response = await fetch(`/api/status?${query.toString()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`status HTTP ${response.status}`);
  state.status = await response.json();
  render(state.status);
}

async function runAction(key) {
  const action = state.actionsByKey.get(key);
  if (!action) {
    showToast(`Unknown action: ${key}`, "bad");
    return;
  }
  let confirmed = false;
  if (action.requiresConfirmation) {
    confirmed = window.confirm(`${action.label}\n\n${action.description}\n\nProceed?`);
    if (!confirmed) return;
  }
  setBusy(true);
  try {
    const response = await fetch("/api/actions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-RiftReader-Control-Center": "1",
      },
      body: JSON.stringify({ action: key, confirm: confirmed }),
    });
    const payload = await response.json();
    state.latestAction = payload;
    renderValidation(state.status || {});
    const resultStatus = payload.status || (payload.ok ? "passed" : "blocked");
    showToast(`${action.label}: ${resultStatus}`, resultStatus === "passed" || resultStatus === "started" || resultStatus === "stopped" ? "good" : "bad");
    await refreshStatus({ force: true });
  } catch (error) {
    showToast(`Action failed: ${error}`, "bad");
  } finally {
    setBusy(false);
  }
}

function initTabs() {
  $$(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const tabName = tab.dataset.tab;
      $$(".tab").forEach((node) => {
        const active = node === tab;
        node.classList.toggle("is-active", active);
        node.setAttribute("aria-selected", active ? "true" : "false");
      });
      $$(".panel").forEach((panel) => {
        const active = panel.id === `panel-${tabName}`;
        panel.classList.toggle("is-active", active);
        panel.hidden = !active;
      });
    });
  });
}

function initEvents() {
  document.getElementById("refreshButton")?.addEventListener("click", async () => {
    setBusy(true);
    try {
      await refreshStatus({ force: true });
      showToast("Status refreshed.", "good");
    } catch (error) {
      showToast(`Refresh failed: ${error}`, "bad");
    } finally {
      setBusy(false);
    }
  });
  document.getElementById("refreshPublicSmokeButton")?.addEventListener("click", async () => {
    setBusy(true);
    try {
      await refreshStatus({ publicSmoke: true, force: true });
      showToast("Status + public smoke refreshed.", "good");
    } catch (error) {
      showToast(`Public smoke refresh failed: ${error}`, "bad");
    } finally {
      setBusy(false);
    }
  });
  document.getElementById("actionSelect")?.addEventListener("change", updateActionHint);
  document.getElementById("runSelectedActionButton")?.addEventListener("click", () => {
    const key = document.getElementById("actionSelect")?.value;
    if (key) runAction(key);
  });
  document.body.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    runAction(button.dataset.action);
  });
  document.getElementById("copyServerUrlButton")?.addEventListener("click", () => copyText(state.status?.chatGpt?.serverUrl, "Server URL copied."));
  document.getElementById("copyChatGptUrlOverviewButton")?.addEventListener("click", () => copyText(state.status?.chatGpt?.serverUrl, "Server URL copied."));
  document.getElementById("copyControlCommandButton")?.addEventListener("click", () => copyText(state.status?.controlCenter?.command, "Control Center command copied."));
}

async function boot() {
  initTabs();
  initEvents();
  setBusy(true);
  try {
    await refreshStatus({ force: true });
    showToast("Control Center loaded.", "good");
  } catch (error) {
    showToast(`Initial load failed: ${error}`, "bad");
    setText("statusJson", String(error));
  } finally {
    setBusy(false);
  }
  window.setInterval(() => {
    if (!state.busy) refreshStatus().catch(() => undefined);
  }, 12000);
}

boot();
