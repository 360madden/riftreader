(function () {
  const appRoot = document.getElementById("app");
  const LIVE_REFRESH_MS = 2000;
  const LIVE_SCRIPT_ID = "dashboard-live-data-refresh";

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatTime(value) {
    if (!value) {
      return "—";
    }

    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return value;
    }

    return parsed.toLocaleString();
  }

  function formatNumber(value, digits = 2) {
    if (value === null || value === undefined || value === "") {
      return "—";
    }

    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return String(value);
    }

    return numeric.toFixed(digits).replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1");
  }

  function formatCoords(coords) {
    if (!coords) {
      return "—";
    }

    const parts = [coords.x, coords.y, coords.z].map((value) => formatNumber(value, 2));
    if (parts.every((part) => part === "—")) {
      return "—";
    }

    return parts.join(", ");
  }

  function humanizeKey(value) {
    return String(value ?? "")
      .replace(/([A-Z])/g, " $1")
      .replace(/_/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/^./, (match) => match.toUpperCase());
  }

  function getStatusClass(value) {
    const normalized = String(value ?? "").trim().toLowerCase();

    if (!normalized) {
      return "status-minimal";
    }

    if (["error", "failed", "broken", "missing", "unresolved", "absent"].some((token) => normalized.includes(token))) {
      return "status-error";
    }

    if (["stale", "partial", "dirty", "manual", "warning", "degraded", "fallback", "snapshot-only"].some((token) => normalized.includes(token))) {
      return "status-partial";
    }

    if (["minimal", "unknown", "idle", "unavailable", "none"].some((token) => normalized.includes(token))) {
      return "status-minimal";
    }

    if (/^\d+\s+configured$/.test(normalized)) {
      return "status-active";
    }

    if (["working", "active", "ready", "healthy", "clean", "current", "configured", "present", "loaded", "ok", "success"].some((token) => normalized.includes(token))) {
      return "status-active";
    }

    return "status-minimal";
  }

  function renderBadge(text, className) {
    return `<span class="badge ${escapeHtml(className)}">${escapeHtml(text)}</span>`;
  }

  function renderStatusBadge(text) {
    return renderBadge(text || "unknown", getStatusClass(text));
  }

  function renderBooleanBadge(value) {
    return renderBadge(value ? "Yes" : "No", value ? "boolean-true" : "boolean-false");
  }

  function normalizeWorkboardItem(item) {
    if (!item) {
      return { item: "", lane: "", note: "" };
    }

    if (typeof item === "string") {
      return { item, lane: "", note: "" };
    }

    return {
      item: item.item || item.label || item.title || "Untitled",
      lane: item.lane || item.owner || "",
      note: item.note || item.summary || item.reason || "",
    };
  }

  function renderTruthList(branch) {
    if (!branch.truth?.length) {
      return `<div class="empty-state">No structured current-truth data is configured for this branch in v1.</div>`;
    }

    return `
      <div class="truth-list">
        ${branch.truth
          .map(
            (row) => `
              <div class="truth-row">
                <div class="truth-row__header">
                  <span class="truth-row__label">${escapeHtml(row.label)}</span>
                  ${renderStatusBadge(row.status)}
                </div>
              </div>`
          )
          .join("")}
      </div>`;
  }

  function renderRunList(branch) {
    const entries = Object.values(branch.latestRuns ?? {});
    if (!entries.length) {
      return `<div class="empty-state">No structured run summaries are available for this branch.</div>`;
    }

    return `
      <div class="run-list">
        ${entries
          .map((run) => `
            <div class="run-row">
              <div class="detail-row__header">
                <span class="detail-row__label">${escapeHtml(run.label || "Latest run")}</span>
                <span class="meta-line">${escapeHtml(formatTime(run.at))}</span>
              </div>
              <div class="run-summary">${escapeHtml(run.summary || "No data")}</div>
            </div>`)
          .join("")}
      </div>`;
  }

  function renderWorkboard(branch) {
    const sections = [
      { key: "now", label: "Now" },
      { key: "parallelNow", label: "Parallel now" },
      { key: "next", label: "Next" },
      { key: "parked", label: "Parked" },
    ];

    return `
      <div class="workboard-sections">
        ${sections
          .map(({ key, label }) => {
            const items = (branch.workboard?.[key] ?? []).map(normalizeWorkboardItem);
            return `
              <div class="workboard-section">
                <div class="detail-row__header">
                  <span class="detail-row__label">${escapeHtml(label)}</span>
                  <span class="meta-line">${items.length} item${items.length === 1 ? "" : "s"}</span>
                </div>
                ${
                  items.length
                    ? `<div class="detail-list">
                        ${items
                          .map(
                            (item) => `
                              <div class="detail-row">
                                <div class="detail-row__header">
                                  <span class="detail-row__label">${escapeHtml(item.item)}</span>
                                  ${item.lane ? renderBadge(item.lane, "role") : ""}
                                </div>
                                ${item.note ? `<div class="detail-row__sub">${escapeHtml(item.note)}</div>` : ""}
                              </div>`
                          )
                          .join("")}
                      </div>`
                    : `<div class="empty-state">No structured workboard items for ${escapeHtml(label)}.</div>`
                }
              </div>`;
          })
          .join("")}
      </div>`;
  }

  function renderSourceList(branch) {
    const sources = branch.sources ?? [];
    if (!sources.length) {
      return `<div class="empty-state">No source-file references are configured for this branch.</div>`;
    }

    return `
      <div class="detail-list">
        ${sources
          .map(
            (source) => `
              <div class="detail-row">
                <div class="detail-row__header">
                  <span class="detail-row__label">${escapeHtml(source.label || source.path || "Source file")}</span>
                  <span class="header-bar__meta">
                    ${renderBadge(source.present ? "present" : "missing", source.present ? "status-active" : "status-error")}
                    <span class="meta-line">${escapeHtml(formatTime(source.updatedAt))}</span>
                  </span>
                </div>
                <div class="detail-row__sub">${escapeHtml(source.path || "—")}</div>
                ${source.note ? `<div class="detail-row__sub">${escapeHtml(source.note)}</div>` : ""}
              </div>`
          )
          .join("")}
      </div>`;
  }

  function renderOverviewPanel(branch) {
    const truthUpdated = branch.docs?.truthUpdatedAt ? formatTime(branch.docs.truthUpdatedAt) : "—";
    const handoffUpdated = branch.docs?.handoffUpdatedAt ? formatTime(branch.docs.handoffUpdatedAt) : "—";
    const workboardUpdated = branch.docs?.workboardUpdatedAt ? formatTime(branch.docs.workboardUpdatedAt) : "—";

    return `
      <div class="panel">
        <div class="panel__header">
          <div>
            <h2>${escapeHtml(branch.name)}</h2>
            <p class="panel__subtitle">${escapeHtml(branch.bottleneck || "No bottleneck summary.")}</p>
          </div>
          <div class="header-bar__meta">
            ${renderBadge(branch.role, "role")}
            ${renderStatusBadge(branch.status)}
          </div>
        </div>

        <div class="overview-grid">
          <div class="mini-card">
            <h3>Current truth</h3>
            ${renderTruthList(branch)}
          </div>

          <div class="mini-card">
            <h3>Latest runs</h3>
            ${renderRunList(branch)}
          </div>

          <div class="mini-card">
            <h3>Docs & handoff</h3>
            <div class="detail-list">
              <div class="detail-row">
                <div class="detail-row__header">
                  <span class="detail-row__label">Handoff ready</span>
                  ${renderBooleanBadge(branch.handoff?.ready)}
                </div>
                <div class="detail-row__sub">${escapeHtml(branch.handoff?.summary || "No handoff summary.")}</div>
              </div>
              <div class="detail-row">
                <div class="detail-row__header">
                  <span class="detail-row__label">Truth updated</span>
                  <span class="meta-line">${escapeHtml(truthUpdated)}</span>
                </div>
              </div>
              <div class="detail-row">
                <div class="detail-row__header">
                  <span class="detail-row__label">Workboard updated</span>
                  <span class="meta-line">${escapeHtml(workboardUpdated)}</span>
                </div>
              </div>
              <div class="detail-row">
                <div class="detail-row__header">
                  <span class="detail-row__label">Handoff updated</span>
                  <span class="meta-line">${escapeHtml(handoffUpdated)}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="mini-card">
            <h3>Next-step workboard</h3>
            ${renderWorkboard(branch)}
          </div>

          <div class="mini-card mini-card--wide">
            <h3>Source files</h3>
            ${renderSourceList(branch)}
          </div>
        </div>
      </div>`;
  }
  function renderSummaryPanel(branch) {
    const counts = Object.entries(branch.candidates?.counts ?? {});
    const highlights = branch.candidates?.top ?? [];

    return `
      <div class="stack">
        <div class="panel">
          <div class="panel__header">
            <div>
              <h2>Summary metrics</h2>
              <p class="panel__subtitle">Branch-level counts and compiled totals for the selected branch.</p>
            </div>
          </div>
          ${
            counts.length
              ? `<div class="metric-grid">
                  ${counts
                    .map(
                      ([label, value]) => `
                        <div class="metric-card">
                          <div class="metric-card__label">${escapeHtml(label)}</div>
                          <div class="metric-card__value">${escapeHtml(value)}</div>
                        </div>`
                    )
                    .join("")}
                </div>`
              : `<div class="empty-state">No structured summary metrics are configured for this branch.</div>`
          }
        </div>

        <div class="panel">
          <div class="panel__header">
            <div>
              <h2>Highlights</h2>
              <p class="panel__subtitle">Most relevant branch findings, wins, or caution flags surfaced by the compiler.</p>
            </div>
          </div>
          ${
            highlights.length
              ? `<div class="top-list">
                  ${highlights
                    .map(
                      (highlight) => `
                        <div class="top-row">
                          <div class="top-row__header">
                            <span class="top-row__label">${escapeHtml(highlight.label)}</span>
                            ${renderStatusBadge(highlight.classification || "unknown")}
                          </div>
                          <div class="top-row__sub">
                            ${escapeHtml(highlight.reason || "No supporting summary recorded.")}
                            ${highlight.discoveryMode ? ` • ${escapeHtml(highlight.discoveryMode)}` : ""}
                            ${highlight.searchScore !== null && highlight.searchScore !== undefined ? ` • score ${escapeHtml(highlight.searchScore)}` : ""}
                          </div>
                        </div>`
                    )
                    .join("")}
                </div>`
              : `<div class="empty-state">No structured highlights are available for this branch.</div>`
          }
        </div>

        <div class="panel">
          <div class="panel__header">
            <div>
              <h2>Warnings</h2>
              <p class="panel__subtitle">Branch-specific gaps and caution flags surfaced by the compiler.</p>
            </div>
          </div>
          ${
            branch.warnings?.length
              ? `<ul class="warning-list">${branch.warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>`
              : `<div class="empty-state">No warnings for this branch.</div>`
          }
        </div>
      </div>`;
  }

  function renderDetailTable(branch) {
    const rows = branch.candidates?.rows ?? [];

    if (!rows.length) {
      return `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th class="wrap">Field</th>
                <th class="wrap">Value</th>
              </tr>
            </thead>
            <tbody>
              <tr><td>Status</td><td class="wrap">${escapeHtml(branch.status)}</td></tr>
              <tr><td>Role</td><td class="wrap">${escapeHtml(branch.role)}</td></tr>
              <tr><td>Bottleneck</td><td class="wrap">${escapeHtml(branch.bottleneck || "—")}</td></tr>
              <tr><td>Path</td><td class="wrap">${escapeHtml(branch.path || "—")}</td></tr>
              <tr><td>Current branch</td><td>${branch.isCurrent ? "Yes" : "No"}</td></tr>
              <tr><td>Handoff ready</td><td>${branch.handoff?.ready ? "Yes" : "No"}</td></tr>
              <tr><td>Source references</td><td>${escapeHtml((branch.sources ?? []).length)}</td></tr>
            </tbody>
          </table>
        </div>`;
    }

    return `
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="wrap">Candidate</th>
              <th>Classification</th>
              <th class="wrap">Rejected reason</th>
              <th>Discovery</th>
              <th class="wrap">Root</th>
              <th>Responsive</th>
              <th>Basis</th>
              <th>Yaw</th>
              <th>Score</th>
              <th>Penalty</th>
              <th class="wrap">Observed</th>
            </tr>
          </thead>
          <tbody>
            ${rows
              .map(
                (row) => `
                  <tr>
                    <td class="wrap">${escapeHtml(row.candidate)}</td>
                    <td>${escapeHtml(row.classification || "—")}</td>
                    <td class="wrap">${escapeHtml(row.rejectedReason || "—")}</td>
                    <td>${escapeHtml(row.discoveryMode || "—")}</td>
                    <td class="wrap">${escapeHtml(row.rootAddress || row.sourceAddress || "—")}</td>
                    <td>${row.responsive === null || row.responsive === undefined ? "—" : row.responsive ? "Yes" : "No"}</td>
                    <td>${row.basisRecovered === null || row.basisRecovered === undefined ? "—" : row.basisRecovered ? "Yes" : "No"}</td>
                    <td>${row.yawRecovered === null || row.yawRecovered === undefined ? "—" : row.yawRecovered ? "Yes" : "No"}</td>
                    <td>${row.searchScore === null || row.searchScore === undefined ? "—" : escapeHtml(row.searchScore)}</td>
                    <td>${row.ledgerPenalty === null || row.ledgerPenalty === undefined ? "—" : escapeHtml(row.ledgerPenalty)}</td>
                    <td class="wrap">${escapeHtml(row.observedAt || "—")}</td>
                  </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>`;
  }

  function getCurrentBranchName(data, liveData) {
    return liveData?.repo?.currentBranch || data.meta.currentBranch || "";
  }

  function isCurrentBranchView(selectedBranch, data, liveData) {
    if (!selectedBranch) {
      return false;
    }

    const currentBranchName = getCurrentBranchName(data, liveData);
    return Boolean(currentBranchName && selectedBranch.name === currentBranchName) || Boolean(selectedBranch.isCurrent);
  }

  function getLiveSourceState(liveData, key) {
    return liveData?.meta?.sources?.[key] ?? null;
  }

  function getLiveAgeSeconds(liveData) {
    if (!liveData?.meta?.generatedAt) {
      return null;
    }

    const parsed = new Date(liveData.meta.generatedAt);
    if (Number.isNaN(parsed.getTime())) {
      return null;
    }

    return Math.max(0, (Date.now() - parsed.getTime()) / 1000);
  }

  function isLiveDataStale(liveData) {
    const ageSeconds = getLiveAgeSeconds(liveData);
    const threshold = Number(liveData?.meta?.staleAfterSeconds ?? 10);
    return ageSeconds !== null && Number.isFinite(threshold) && ageSeconds > threshold;
  }

  function getLiveOverallStatus(liveData, loadState) {
    if (!liveData) {
      if (loadState === "error") {
        return { text: "error", className: "status-error" };
      }

      if (loadState === "loading") {
        return { text: "loading", className: "status-minimal" };
      }

      return { text: "unavailable", className: "status-minimal" };
    }

    if (isLiveDataStale(liveData)) {
      return { text: "stale", className: "status-partial" };
    }

    const statusText = liveData.meta?.status || (loadState === "error" ? "partial" : "active");
    return { text: statusText, className: getStatusClass(statusText) };
  }

  function formatDirtyCounts(repo) {
    const counts = repo?.dirtyCounts ?? {};
    const segments = [
      ["modified", counts.modified],
      ["added", counts.added],
      ["deleted", counts.deleted],
      ["renamed", counts.renamed],
      ["untracked", counts.untracked],
    ]
      .filter(([, value]) => value !== null && value !== undefined)
      .map(([label, value]) => `${label} ${value}`);

    return segments.length ? segments.join(" • ") : "No git status counts available.";
  }

  function formatHealth(health) {
    if (!health) {
      return "—";
    }

    const current = formatNumber(health.current, 0);
    const max = formatNumber(health.max, 0);
    const percent = health.percent === null || health.percent === undefined ? null : `${formatNumber(health.percent, 1)}%`;
    const base = max === "—" ? current : `${current} / ${max}`;
    return percent ? `${base} (${percent})` : base;
  }

  function formatResource(resource) {
    if (!resource) {
      return "—";
    }

    const current = formatNumber(resource.current, 0);
    const max = formatNumber(resource.max, 0);
    const base = max === "—" ? current : `${current} / ${max}`;
    return resource.kind ? `${resource.kind}: ${base}` : base;
  }
  function formatDistance(distance) {
    if (!distance) {
      return "—";
    }

    const current = formatNumber(distance.current, 2);
    if (distance.delta === null || distance.delta === undefined) {
      return current;
    }

    return `${current} (Δ ${formatNumber(distance.delta, 2)})`;
  }

  function summarizeMatchFlags(match) {
    if (!match || typeof match !== "object") {
      return "No comparison data.";
    }

    const entries = Object.entries(match)
      .filter(([, value]) => typeof value === "boolean")
      .slice(0, 4)
      .map(([key, value]) => `${humanizeKey(key.replace(/MatchesWithinTolerance$/, " match").replace(/Matches$/, " match"))}: ${value ? "ok" : "mismatch"}`);

    return entries.length ? entries.join(" • ") : "No comparison flags.";
  }

  function renderLiveValueList(rows) {
    const renderedRows = rows
      .filter((row) => row)
      .map((row) => {
        const valueHtml = row.html ? row.value : escapeHtml(row.value ?? "—");
        return `
          <div class="live-value-row ${row.wide ? "live-value-row--wide" : ""}">
            <span class="live-value-row__label">${escapeHtml(row.label)}</span>
            <span class="live-value-row__value">${valueHtml}</span>
          </div>`;
      })
      .join("");

    return `<div class="live-value-list">${renderedRows}</div>`;
  }

  function getLiveErrorSummary(liveData) {
    const errors = Object.entries(liveData?.errors ?? {})
      .filter(([, value]) => Boolean(value))
      .map(([key, value]) => `${key}: ${value}`);

    return errors.length ? errors.join(" • ") : "";
  }

  function renderLiveFeedCard(liveData, loadState) {
    const overall = getLiveOverallStatus(liveData, loadState);
    const snapshot = liveData?.snapshot ?? {};
    const ageSeconds = getLiveAgeSeconds(liveData);
    const errorSummary = getLiveErrorSummary(liveData);
    const sourceKeys = ["repo", "snapshot", "player", "target"];
    const sourceBadges = sourceKeys
      .map((key) => {
        const sourceState = getLiveSourceState(liveData, key);
        if (!sourceState) {
          return renderBadge(`${key}: unavailable`, "status-minimal");
        }

        return renderBadge(`${key}: ${sourceState.status || "unknown"}`, getStatusClass(sourceState.status));
      })
      .join("");

    const loadSummary =
      loadState === "error"
        ? "Latest refresh failed; showing the last good live payload when available."
        : loadState === "loading"
          ? "Refreshing live payload from the generated dashboard-live-data.js feed."
          : "Live payload is being reloaded from the generated file every 2 seconds.";

    return `
      <div class="live-card">
        <div class="panel__header">
          <div>
            <h2 class="live-card__title">Live feed status</h2>
            <p class="panel__subtitle">${escapeHtml(loadSummary)}</p>
          </div>
          ${renderBadge(overall.text, overall.className)}
        </div>
        ${renderLiveValueList([
          { label: "Generated", value: formatTime(liveData?.meta?.generatedAt) },
          { label: "Age", value: ageSeconds === null ? "—" : `${formatNumber(ageSeconds, 1)}s` },
          { label: "Snapshot loaded", value: formatTime(snapshot.loadedAt) },
          { label: "Stale after", value: `${escapeHtml(String(liveData?.meta?.staleAfterSeconds ?? 10))}s`, html: true },
          { label: "Snapshot source", value: snapshot.sourceFile || "—", wide: true },
          { label: "Export reason", value: snapshot.exportReason || snapshot.lastReason || "—", wide: true },
          { label: "Export count", value: snapshot.exportCount },
          { label: "Snapshot status", value: snapshot.status || "—" },
          ...(errorSummary ? [{ label: "Source issues", value: errorSummary, wide: true }] : []),
        ])}
        <div class="live-badge-line">${sourceBadges}</div>
      </div>`;
  }

  function renderRepoLiveCard(liveData) {
    const repo = liveData?.repo ?? {};
    const changes = Array.isArray(repo.changes) ? repo.changes.slice(0, 3) : [];

    return `
      <div class="live-card">
        <div class="panel__header">
          <div>
            <h2 class="live-card__title">Current worktree status</h2>
            <p class="panel__subtitle">Live git status from the current repo root.</p>
          </div>
          ${renderBadge(repo.dirty ? "dirty" : "clean", repo.dirty ? "status-partial" : "status-active")}
        </div>
        ${renderLiveValueList([
          { label: "Branch", value: repo.currentBranch || "—" },
          { label: "Changed files", value: repo.changedFileCount },
          { label: "Updated", value: formatTime(repo.updatedAt) },
          { label: "Repo path", value: repo.repoPath || "—", wide: true },
          { label: "Status counts", value: formatDirtyCounts(repo), wide: true },
          { label: "Recent changes", value: changes.length ? changes.join(" • ") : "No pending changes listed.", wide: true },
        ])}
      </div>`;
  }

  function renderPlayerLiveCard(liveData) {
    const player = liveData?.player ?? {};

    if (!player.available) {
      return `
        <div class="live-card">
          <div class="panel__header">
            <div>
              <h2 class="live-card__title">Player live snapshot</h2>
              <p class="panel__subtitle">Current player details from ReaderBridge and memory reads.</p>
            </div>
            ${renderBadge("unavailable", "status-minimal")}
          </div>
          <div class="empty-state">Live player data is not available yet.</div>
        </div>`;
    }

    return `
      <div class="live-card">
        <div class="panel__header">
          <div>
            <h2 class="live-card__title">Player live snapshot</h2>
            <p class="panel__subtitle">Current player details from ReaderBridge and memory reads.</p>
          </div>
          ${renderBadge(player.sourceMode || "live", getStatusClass(player.sourceMode || "active"))}
        </div>
        ${renderLiveValueList([
          { label: "Name", value: player.name || "—" },
          { label: "Role", value: player.role || "—" },
          { label: "Level", value: player.level?.current },
          { label: "Health", value: formatHealth(player.health) },
          { label: "Resource", value: formatResource(player.resource) },
          { label: "Coords", value: formatCoords(player.coords) },
          { label: "Location", value: player.location || "—", wide: true },
          { label: "Match", value: summarizeMatchFlags(player.memoryMatch), wide: true },
          { label: "Source file", value: player.sourceFile || "—", wide: true },
        ])}
      </div>`;
  }

  function renderTargetLiveCard(liveData) {
    const target = liveData?.target ?? {};

    if (!target.available) {
      return `
        <div class="live-card">
          <div class="panel__header">
            <div>
              <h2 class="live-card__title">Target live snapshot</h2>
              <p class="panel__subtitle">Current target details from ReaderBridge and memory reads.</p>
            </div>
            ${renderBadge("unavailable", "status-minimal")}
          </div>
          <div class="empty-state">Live target data is not available yet.</div>
        </div>`;
    }

    if (target.hasTarget === false) {
      return `
        <div class="live-card">
          <div class="panel__header">
            <div>
              <h2 class="live-card__title">Target live snapshot</h2>
              <p class="panel__subtitle">Current target details from ReaderBridge and memory reads.</p>
            </div>
            ${renderBadge("no target", "status-minimal")}
          </div>
          ${renderLiveValueList([
            { label: "Updated", value: formatTime(target.updatedAt) },
            { label: "Source mode", value: target.sourceMode || "—" },
            { label: "Source file", value: target.sourceFile || "—", wide: true },
          ])}
          <div class="empty-state">No target selected.</div>
        </div>`;
    }

    return `
      <div class="live-card">
        <div class="panel__header">
          <div>
            <h2 class="live-card__title">Target live snapshot</h2>
            <p class="panel__subtitle">Current target details from ReaderBridge and memory reads.</p>
          </div>
          ${renderBadge(target.sourceMode || "live", getStatusClass(target.sourceMode || "active"))}
        </div>
        ${renderLiveValueList([
          { label: "Name", value: target.name || "—" },
          { label: "Role", value: target.role || "—" },
          { label: "Level", value: target.level?.current },
          { label: "Distance", value: formatDistance(target.distance) },
          { label: "Health", value: formatHealth(target.health) },
          { label: "Resource", value: formatResource(target.resource) },
          { label: "Coords", value: formatCoords(target.coords) },
          { label: "Location", value: target.location || "—", wide: true },
          { label: "Match", value: summarizeMatchFlags(target.memoryMatch), wide: true },
          { label: "Source file", value: target.sourceFile || "—", wide: true },
        ])}
      </div>`;
  }

  function renderLiveSection(data, selectedBranch, liveData, loadState) {
    if (!isCurrentBranchView(selectedBranch, data, liveData)) {
      return "";
    }

    return `
      <section class="panel live-panel">
        <div class="panel__header">
          <div>
            <h2>Live prototype overlay</h2>
            <p class="panel__subtitle">Local file-based live details for the current branch view. Static branch docs remain snapshot-driven.</p>
          </div>
        </div>
        <div class="live-grid">
          ${renderLiveFeedCard(liveData, loadState)}
          ${renderRepoLiveCard(liveData)}
          ${renderPlayerLiveCard(liveData)}
          ${renderTargetLiveCard(liveData)}
        </div>
      </section>`;
  }

  function renderHeader(data, selectedBranch, liveData, loadState) {
    const liveStatus = getLiveOverallStatus(liveData, loadState);
    const currentBranchName = getCurrentBranchName(data, liveData) || "unknown";
    const showLiveBadge = isCurrentBranchView(selectedBranch, data, liveData);

    return `
      <section class="header-bar">
        <div class="header-bar__title">
          <div>
            <h1>RiftReader Dashboard</h1>
            <div class="header-bar__path">${escapeHtml(data.meta.repoPath || "")}</div>
          </div>
          <div class="header-bar__meta">
            ${renderBadge(`Current: ${currentBranchName}`, "role")}
            ${renderBadge(`Selected: ${selectedBranch.name}`, getStatusClass(selectedBranch.status))}
            ${renderBadge(`Worktrees: ${(data.meta.worktrees || []).length}`, "role")}
            ${showLiveBadge ? renderBadge(`Live: ${liveStatus.text}`, liveStatus.className) : ""}
          </div>
        </div>
        <div class="meta-line">Generated ${escapeHtml(formatTime(data.meta.generatedAt))}</div>
      </section>`;
  }

  function renderSidebar(data, selectedBranchId) {
    return `
      <aside class="sidebar">
        <h2>Branches</h2>
        <p>Select a branch summary. Switching branches only changes the local view.</p>
        <div class="branch-list">
          ${data.branches
            .map(
              (branch) => `
                <button class="branch-card ${branch.id === selectedBranchId ? "active" : ""}" data-branch-id="${escapeHtml(branch.id)}" type="button">
                  <div class="branch-card__header">
                    <h3 class="branch-card__title">${escapeHtml(branch.name)}</h3>
                    ${renderStatusBadge(branch.status)}
                  </div>
                  <div class="branch-card__header">
                    ${renderBadge(branch.role, "role")}
                    ${branch.isCurrent ? renderBadge("current", "status-active") : ""}
                  </div>
                  <div class="branch-card__bottleneck">${escapeHtml(branch.bottleneck || "No bottleneck summary.")}</div>
                  <div class="branch-card__path">${escapeHtml(branch.path || "")}</div>
                </button>`
            )
            .join("")}
        </div>
      </aside>`;
  }
  function renderLayout(data, selectedBranch, liveData, loadState) {
    return `
      ${renderSidebar(data, selectedBranch.id)}
      <main class="main-content">
        ${renderHeader(data, selectedBranch, liveData, loadState)}
        ${renderLiveSection(data, selectedBranch, liveData, loadState)}

        <div class="panel-grid">
          <div class="stack">
            ${renderOverviewPanel(selectedBranch)}
          </div>
          ${renderSummaryPanel(selectedBranch)}
        </div>

        <section class="panel table-panel">
          <div class="panel__header">
            <div>
              <h2>Detailed rows</h2>
              <p class="panel__subtitle">Candidate rows for rich analysis branches; compact metadata when no structured row set exists.</p>
            </div>
          </div>
          ${renderDetailTable(selectedBranch)}
        </section>
      </main>`;
  }

  function renderError(message) {
    appRoot.innerHTML = `
      <div class="error-state">
        <h1>RiftReader Dashboard</h1>
        <p>${escapeHtml(message)}</p>
        <p class="meta-line">Run <code>C:\RIFT MODDING\RiftReader\scripts\build-dashboard-summary.ps1</code> to regenerate <code>tools/dashboard/dashboard-data.js</code>.</p>
      </div>`;
  }

  const data = window.DASHBOARD_DATA;
  if (!data || !Array.isArray(data.branches)) {
    renderError("Dashboard data is missing or invalid.");
    return;
  }

  const state = {
    selectedBranchId: data.defaultBranchId || data.branches[0]?.id,
    liveData: window.DASHBOARD_LIVE_DATA || null,
    liveDataLoadState: window.DASHBOARD_LIVE_DATA ? "loaded" : "idle",
    liveRequestId: 0,
  };

  function getSelectedBranch() {
    return data.branches.find((branch) => branch.id === state.selectedBranchId) || data.branches[0];
  }

  function render() {
    const selectedBranch = getSelectedBranch();
    if (!selectedBranch) {
      renderError("No branches were discovered for the dashboard.");
      return;
    }

    appRoot.innerHTML = renderLayout(data, selectedBranch, state.liveData, state.liveDataLoadState);

    appRoot.querySelectorAll("[data-branch-id]").forEach((button) => {
      button.addEventListener("click", () => {
        state.selectedBranchId = button.getAttribute("data-branch-id");
        render();
      });
    });
  }

  function refreshLiveData() {
    const requestId = ++state.liveRequestId;
    if (!state.liveData) {
      state.liveDataLoadState = "loading";
      render();
    }

    const priorScript = document.getElementById(LIVE_SCRIPT_ID);
    if (priorScript) {
      priorScript.remove();
    }

    const script = document.createElement("script");
    script.id = LIVE_SCRIPT_ID;
    script.src = `./dashboard-live-data.js?ts=${Date.now()}`;
    script.async = true;

    script.onload = () => {
      if (requestId !== state.liveRequestId) {
        return;
      }

      state.liveData = window.DASHBOARD_LIVE_DATA || state.liveData;
      state.liveDataLoadState = window.DASHBOARD_LIVE_DATA ? "loaded" : "idle";
      render();
    };

    script.onerror = () => {
      if (requestId !== state.liveRequestId) {
        return;
      }

      state.liveDataLoadState = "error";
      render();
    };

    document.body.appendChild(script);
  }

  render();
  refreshLiveData();
  window.setInterval(refreshLiveData, LIVE_REFRESH_MS);
})();
