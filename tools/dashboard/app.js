(function () {
  const appRoot = document.getElementById("app");

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

  function renderBadge(text, className) {
    return `<span class="badge ${escapeHtml(className)}">${escapeHtml(text)}</span>`;
  }

  function renderBooleanBadge(value) {
    return renderBadge(value ? "Yes" : "No", value ? "boolean-true" : "boolean-false");
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
                ${renderBadge(row.status, row.status.toLowerCase().includes("broken") || row.status.toLowerCase().includes("stale") ? "status-partial" : "status-active")}
              </div>
            </div>`
          )
          .join("")}
      </div>`;
  }

  function renderRunList(branch) {
    const entries = [
      { key: "screen", label: "Latest screen run" },
      { key: "recovery", label: "Latest recovery run" },
      { key: "probe", label: "Latest addon probe" },
    ];

    return `
      <div class="run-list">
        ${entries
          .map(({ key, label }) => {
            const run = branch.latestRuns?.[key] ?? {};
            return `
              <div class="run-row">
                <div class="detail-row__header">
                  <span class="detail-row__label">${escapeHtml(label)}</span>
                  <span class="meta-line">${escapeHtml(formatTime(run.at))}</span>
                </div>
                <div class="run-summary">${escapeHtml(run.summary || "No data")}</div>
              </div>`;
          })
          .join("")}
      </div>`;
  }

  function renderWorkboard(branch) {
    const sections = [
      { key: "now", label: "Now" },
      { key: "parallelNow", label: "Parallel now" },
      { key: "next", label: "Next" },
    ];

    return `
      <div class="workboard-sections">
        ${sections
          .map(({ key, label }) => {
            const items = branch.workboard?.[key] ?? [];
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
                          .slice(0, 3)
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

  function renderCandidateSummary(branch) {
    const counts = branch.candidates?.counts ?? {};
    const metricEntries = Object.entries(counts);
    const topCandidates = branch.candidates?.top ?? [];

    return `
      <div class="stack">
        <div class="panel">
          <div class="panel__header">
            <div>
              <h2>Candidate summary</h2>
              <p class="panel__subtitle">Only populated when structured candidate evidence exists.</p>
            </div>
          </div>
          ${
            metricEntries.length
              ? `<div class="metric-grid">
                  ${metricEntries
                    .map(
                      ([label, value]) => `
                        <div class="metric-card">
                          <div class="metric-card__label">${escapeHtml(label)}</div>
                          <div class="metric-card__value">${escapeHtml(value)}</div>
                        </div>`
                    )
                    .join("")}
                </div>`
              : `<div class="empty-state">No structured candidate counts are configured for this branch.</div>`
          }
        </div>

        <div class="panel">
          <div class="panel__header">
            <div>
              <h2>Top candidates</h2>
              <p class="panel__subtitle">Most relevant named candidates or near-misses for the selected branch.</p>
            </div>
          </div>
          ${
            topCandidates.length
              ? `<div class="top-list">
                  ${topCandidates
                    .map(
                      (candidate) => `
                        <div class="top-row">
                          <div class="top-row__header">
                            <span class="top-row__label">${escapeHtml(candidate.label)}</span>
                            ${renderBadge(candidate.classification || "unknown", "status-partial")}
                          </div>
                          <div class="top-row__sub">
                            ${escapeHtml(candidate.reason || "No rejection reason recorded.")}
                            ${candidate.discoveryMode ? ` • ${escapeHtml(candidate.discoveryMode)}` : ""}
                            ${candidate.searchScore !== null && candidate.searchScore !== undefined ? ` • score ${escapeHtml(candidate.searchScore)}` : ""}
                          </div>
                        </div>`
                    )
                    .join("")}
                </div>`
              : `<div class="empty-state">No structured top-candidate list is available for this branch.</div>`
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
                    <td class="wrap">${escapeHtml(row.rootAddress || "—")}</td>
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

  function renderHeader(data, selectedBranch) {
    return `
      <section class="header-bar">
        <div class="header-bar__title">
          <div>
            <h1>RiftReader Dashboard</h1>
            <div class="header-bar__path">${escapeHtml(data.meta.repoPath || "")}</div>
          </div>
          <div class="header-bar__meta">
            ${renderBadge(`Current: ${data.meta.currentBranch || "unknown"}`, "role")}
            ${renderBadge(`Selected: ${selectedBranch.name}`, `status-${selectedBranch.status}`)}
            ${renderBadge(`Worktrees: ${(data.meta.worktrees || []).length}`, "role")}
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
                    ${renderBadge(branch.status, `status-${branch.status}`)}
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
            ${renderBadge(branch.status, `status-${branch.status}`)}
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
        </div>
      </div>`;
  }

  function renderLayout(data, selectedBranch) {
    return `
      ${renderSidebar(data, selectedBranch.id)}
      <main class="main-content">
        ${renderHeader(data, selectedBranch)}

        <div class="panel-grid">
          <div class="stack">
            ${renderOverviewPanel(selectedBranch)}
          </div>
          ${renderCandidateSummary(selectedBranch)}
        </div>

        <section class="panel table-panel">
          <div class="panel__header">
            <div>
              <h2>Detailed table</h2>
              <p class="panel__subtitle">Candidate rows for rich branches; compact metadata when no structured candidate data exists.</p>
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

    appRoot.innerHTML = renderLayout(data, selectedBranch);

    appRoot.querySelectorAll("[data-branch-id]").forEach((button) => {
      button.addEventListener("click", () => {
        state.selectedBranchId = button.getAttribute("data-branch-id");
        render();
      });
    });
  }

  render();
})();
