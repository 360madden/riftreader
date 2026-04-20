window.DASHBOARD_DATA = {
  "meta": {
    "generatedAt": "2026-04-19T14:02:00.3030450-04:00",
    "repoPath": "C:/RIFT MODDING/RiftReader_facing",
    "currentBranch": "facing",
    "worktrees": [
      {
        "path": "C:/RIFT MODDING/RiftReader",
        "head": "9ab6eb00c37e2115e317d8aeb1e8b76eaf1096c4",
        "branch": "scanner-with-debug",
        "isCurrent": false
      },
      {
        "path": "C:/RIFT MODDING/RiftReader_apr15_replay",
        "head": "73e7e6e3d29955526171f73b31e597a468b1e3ec",
        "branch": null,
        "isCurrent": false
      },
      {
        "path": "C:/RIFT MODDING/RiftReader_camera_feature",
        "head": "885a2c251ad41f02dd5a93341ee10813805117f6",
        "branch": "feature/camera-orientation-discovery",
        "isCurrent": false
      },
      {
        "path": "C:/RIFT MODDING/RiftReader_facing",
        "head": "91a3d1f3e38af0257bce471bdf08b866be185f75",
        "branch": "facing",
        "isCurrent": true
      },
      {
        "path": "C:/Users/mrkoo/.local/share/opencode/worktree/a5bb6559dabaa305972a37e45ae4b9b01c63b7bd/hidden-tiger",
        "head": "1c0d04f225b7ee06320061631186298241a76a78",
        "branch": "opencode/hidden-tiger",
        "isCurrent": false
      }
    ]
  },
  "branches": [
    {
      "id": "facing",
      "name": "facing",
      "path": "C:/RIFT MODDING/RiftReader_facing",
      "isCurrent": true,
      "role": "branch",
      "status": "partial",
      "bottleneck": "Current working branch with no branch-specific dashboard summary yet.",
      "truth": [],
      "latestRuns": {
        "screen": {
          "label": "Latest screen run",
          "at": null,
          "summary": "No structured screen run data configured."
        },
        "recovery": {
          "label": "Latest recovery run",
          "at": null,
          "summary": "No structured recovery data configured."
        },
        "probe": {
          "label": "Latest addon probe",
          "at": null,
          "summary": "No structured probe data configured."
        }
      },
      "workboard": {
        "now": [],
        "parallelNow": [],
        "next": [],
        "parked": []
      },
      "candidates": {
        "counts": {},
        "top": [],
        "rows": []
      },
      "handoff": {
        "ready": false,
        "path": "",
        "summary": "No branch handoff doc configured in v1."
      },
      "docs": {
        "truthUpdatedAt": null,
        "workboardUpdatedAt": null,
        "handoffUpdatedAt": null
      },
      "sources": [],
      "warnings": [
        "No rich branch-local dashboard data is configured for this branch in v1."
      ]
    },
    {
      "path": "C:/RIFT MODDING/RiftReader_facing",
      "sources": [
        {
          "label": "Current truth doc",
          "path": "C:/RIFT MODDING/RiftReader_facing/docs/recovery/current-truth.md",
          "note": "Parsed for the truth rows shown in the branch overview.",
          "present": true,
          "updatedAt": "2026-04-16T20:55:41.7873768-04:00"
        },
        {
          "label": "Branch workboard",
          "path": "C:/RIFT MODDING/RiftReader_facing/docs/branch-workboard-codex-actor-yaw-pitch.md",
          "note": "Parsed for Now / Parallel now / Next sections.",
          "present": false,
          "updatedAt": null
        },
        {
          "label": "Branch handoff",
          "path": "C:/RIFT MODDING/RiftReader_facing/docs/handoffs/2026-04-15-codex-actor-yaw-pitch.md",
          "note": "Used for handoff readiness and next-conversation summary.",
          "present": true,
          "updatedAt": "2026-04-19T13:26:16.5594914-04:00"
        },
        {
          "label": "Offline analysis JSON",
          "path": "C:/RIFT MODDING/RiftReader_facing/scripts/captures/actor-orientation-offline-analysis.json",
          "note": "Drives candidate counts, ranking, and the detailed table.",
          "present": false,
          "updatedAt": null
        },
        {
          "label": "Candidate screen JSON",
          "path": "C:/RIFT MODDING/RiftReader_facing/scripts/captures/actor-orientation-candidate-screen.json",
          "note": "Feeds the latest screen-run summary.",
          "present": false,
          "updatedAt": null
        },
        {
          "label": "Recovery JSON",
          "path": "C:/RIFT MODDING/RiftReader_facing/scripts/captures/actor-orientation-recovery.json",
          "note": "Feeds the latest recovery summary.",
          "present": false,
          "updatedAt": null
        },
        {
          "label": "ReaderBridge probe JSON",
          "path": "C:/RIFT MODDING/RiftReader_facing/scripts/captures/readerbridge-orientation-probe.json",
          "note": "Feeds the latest addon-probe summary.",
          "present": false,
          "updatedAt": null
        }
      ],
      "latestRuns": {
        "screen": {
          "label": "Latest screen run",
          "at": null,
          "summary": "No structured screen run data configured."
        },
        "recovery": {
          "label": "Latest recovery run",
          "at": null,
          "summary": "No structured recovery data configured."
        },
        "probe": {
          "label": "Latest addon probe",
          "at": null,
          "summary": "No structured probe data configured."
        }
      },
      "handoff": {
        "ready": false,
        "path": "C:/RIFT MODDING/RiftReader_facing/docs/handoffs/2026-04-15-codex-actor-yaw-pitch.md",
        "summary": "Reacquire the live selected-source / transform family from the working coord anchor with `C:\\RIFT MODDING\\RiftReader_facing\\scripts\\capture-player-trace-cluster.ps1` plus `C:\\RIFT MODDING\\RiftReader_facing\\scripts\\capture-owner-state-neighborhood.ps1`, then run turn-response validation on the top basis-like candidate before doing any more navigation work."
      },
      "bottleneck": "No trusted surviving yaw candidate after the latest merge.",
      "candidates": {
        "counts": {},
        "top": null,
        "rows": null
      },
      "isCurrent": false,
      "workboard": {
        "now": null,
        "parallelNow": null,
        "next": null,
        "parked": null
      },
      "role": "actor-recovery",
      "status": "active",
      "truth": [
        {
          "label": "Low-level reader",
          "status": "reliable enough for active work"
        },
        {
          "label": "ReaderBridge snapshot load",
          "status": "working"
        },
        {
          "label": "Player current read",
          "status": "working"
        },
        {
          "label": "Coord-anchor module pattern",
          "status": "working"
        },
        {
          "label": "Source-chain refresh",
          "status": "broken after the update"
        },
        {
          "label": "Selector-owner trace",
          "status": "broken after the update"
        },
        {
          "label": "Player orientation read",
          "status": "stale until the owner/source chain is rebuilt"
        },
        {
          "label": "Camera yaw / pitch / distance on `main`",
          "status": "stale / unverified after the update"
        },
        {
          "label": "Authoritative camera controller",
          "status": "not yet isolated"
        }
      ],
      "id": "codex/actor-yaw-pitch",
      "name": "codex/actor-yaw-pitch",
      "warnings": [
        "No dedicated worktree is currently checked out for this branch.",
        "Workboard Now section could not be parsed.",
        "Offline candidate analysis JSON is missing.",
        "Current candidate screen JSON is missing.",
        "Recovery JSON is missing.",
        "ReaderBridge probe JSON is missing.",
        "Source-chain refresh is still broken after the update."
      ],
      "docs": {
        "truthUpdatedAt": "2026-04-16T20:55:41.7873768-04:00",
        "workboardUpdatedAt": null,
        "handoffUpdatedAt": "2026-04-19T13:26:16.5594914-04:00"
      }
    },
    {
      "path": "C:/RIFT MODDING/RiftReader_facing",
      "sources": [
        {
          "label": "Dashboard app shell",
          "path": "C:/RIFT MODDING/RiftReader_facing/tools/dashboard/index.html",
          "note": "Static HTML entrypoint that loads the generated dashboard data and UI bundle.",
          "present": true,
          "updatedAt": "2026-04-16T20:55:42.1805697-04:00"
        },
        {
          "label": "Dashboard UI bundle",
          "path": "C:/RIFT MODDING/RiftReader_facing/tools/dashboard/app.js",
          "note": "Vanilla JS renderer for the branch list, overview cards, metrics, and details.",
          "present": true,
          "updatedAt": "2026-04-16T20:55:42.1732157-04:00"
        },
        {
          "label": "Dashboard stylesheet",
          "path": "C:/RIFT MODDING/RiftReader_facing/tools/dashboard/styles.css",
          "note": "Dark responsive layout and component styling for the dashboard shell.",
          "present": true,
          "updatedAt": "2026-04-16T20:55:42.1815837-04:00"
        },
        {
          "label": "Compiled dashboard data",
          "path": "C:/RIFT MODDING/RiftReader_facing/tools/dashboard/dashboard-data.js",
          "note": "Generated snapshot consumed directly by the browser.",
          "present": true,
          "updatedAt": "2026-04-16T20:55:42.1767229-04:00"
        },
        {
          "label": "Dashboard generator",
          "path": "C:/RIFT MODDING/RiftReader_facing/scripts/build-dashboard-summary.ps1",
          "note": "Compiles git, docs, and capture artifacts into dashboard-data.js.",
          "present": true,
          "updatedAt": "2026-04-19T14:01:56.4371793-04:00"
        },
        {
          "label": "Dashboard README",
          "path": "C:/RIFT MODDING/RiftReader_facing/tools/dashboard/README.md",
          "note": "Usage and maintenance notes for the dashboard workflow.",
          "present": true,
          "updatedAt": "2026-04-16T20:55:42.1703626-04:00"
        },
        {
          "label": "Launcher script",
          "path": "C:/RIFT MODDING/RiftReader_facing/scripts/open-dashboard.ps1",
          "note": "Rebuilds and opens the dashboard in the default browser.",
          "present": true,
          "updatedAt": "2026-04-16T20:55:42.0923609-04:00"
        },
        {
          "label": "Launcher CMD wrapper",
          "path": "C:/RIFT MODDING/RiftReader_facing/scripts/open-dashboard.cmd",
          "note": "Convenience entrypoint for cmd.exe users.",
          "present": true,
          "updatedAt": "2026-04-16T20:55:42.0908279-04:00"
        },
        {
          "label": "Branch workboard",
          "path": "C:/RIFT MODDING/RiftReader_facing/docs/branch-workboard-codex-dashboard-hud.md",
          "note": "Parsed for the dashboard branch Now / Parallel now / Next sections.",
          "present": false,
          "updatedAt": null
        },
        {
          "label": "Branch handoff",
          "path": "C:/RIFT MODDING/RiftReader_facing/docs/handoffs/2026-04-15-codex-dashboard-hud.md",
          "note": "Used for handoff readiness and next-conversation summary.",
          "present": false,
          "updatedAt": null
        }
      ],
      "latestRuns": {
        "screen": {
          "label": "Latest dashboard build",
          "at": "2026-04-19T14:02:00.3030450-04:00",
          "summary": "Compiled 10 branches across 5 worktree(s) into dashboard-data.js."
        },
        "recovery": {
          "label": "Latest branch commit",
          "at": "2026-04-19T13:54:18-04:00",
          "summary": "Add passive actor-facing analysis docs (91a3d1f)"
        },
        "probe": {
          "label": "Working tree state",
          "at": "2026-04-19T14:02:00.8474580-04:00",
          "summary": "dirty=11; modified=6; added=0; deleted=0; renamed=0; untracked=5."
        }
      },
      "handoff": {
        "ready": false,
        "path": "C:/RIFT MODDING/RiftReader_facing/docs/handoffs/2026-04-15-codex-dashboard-hud.md",
        "summary": "Keep the dashboard branch aligned with real source files, rich branch inputs, and the launcher flow."
      },
      "bottleneck": "Implement the display-only branch-aware dashboard v1.",
      "candidates": {
        "counts": {
          "branches": 10,
          "richBranches": 3,
          "worktrees": 5,
          "sources": 8,
          "dirtyFiles": 11
        },
        "top": [
          {
            "label": "Dashboard toolchain",
            "classification": "active",
            "reason": "8 dashboard source file(s) are present, including the generator and launcher.",
            "discoveryMode": "codex/dashboard-hud",
            "searchScore": 8
          },
          {
            "label": "Cross-branch coverage",
            "classification": "active",
            "reason": "3 rich branch view(s) are configured in the current snapshot.",
            "discoveryMode": "branch coverage",
            "searchScore": 3
          },
          {
            "label": "Worktree visibility",
            "classification": "active",
            "reason": "5 checked-out worktree(s) are visible to the dashboard generator.",
            "discoveryMode": "git worktree",
            "searchScore": 5
          },
          {
            "label": "Current worktree state",
            "classification": "dirty",
            "reason": "dirty=11; modified=6; added=0; deleted=0; renamed=0; untracked=5.",
            "discoveryMode": "git status",
            "searchScore": 11
          }
        ],
        "rows": []
      },
      "isCurrent": false,
      "workboard": {
        "now": null,
        "parallelNow": null,
        "next": null,
        "parked": null
      },
      "role": "dashboard",
      "status": "partial",
      "truth": [
        {
          "label": "Dashboard shell",
          "status": "working"
        },
        {
          "label": "Snapshot generator",
          "status": "working"
        },
        {
          "label": "Open-in-browser launcher",
          "status": "working"
        },
        {
          "label": "Rich branch coverage",
          "status": "3 configured"
        },
        {
          "label": "Refresh model",
          "status": "manual snapshot"
        },
        {
          "label": "Current worktree",
          "status": "dirty"
        }
      ],
      "id": "codex/dashboard-hud",
      "name": "codex/dashboard-hud",
      "warnings": [
        "No dedicated worktree is currently checked out for this branch.",
        "Dashboard branch workboard doc is missing.",
        "Dashboard branch handoff doc is missing.",
        "Dashboard workboard Now section could not be parsed.",
        "Current worktree has 11 pending change(s)."
      ],
      "docs": {
        "truthUpdatedAt": "2026-04-19T14:01:56.4371793-04:00",
        "workboardUpdatedAt": null,
        "handoffUpdatedAt": null
      }
    },
    {
      "id": "main",
      "name": "main",
      "path": "C:/RIFT MODDING/RiftReader_facing",
      "isCurrent": false,
      "role": "baseline",
      "status": "minimal",
      "bottleneck": "Reference baseline only; not the active recovery branch.",
      "truth": [],
      "latestRuns": {
        "screen": {
          "label": "Latest screen run",
          "at": null,
          "summary": "No structured screen run data configured."
        },
        "recovery": {
          "label": "Latest recovery run",
          "at": null,
          "summary": "No structured recovery data configured."
        },
        "probe": {
          "label": "Latest addon probe",
          "at": null,
          "summary": "No structured probe data configured."
        }
      },
      "workboard": {
        "now": [],
        "parallelNow": [],
        "next": [],
        "parked": []
      },
      "candidates": {
        "counts": {},
        "top": [],
        "rows": []
      },
      "handoff": {
        "ready": false,
        "path": "",
        "summary": "No branch handoff doc configured in v1."
      },
      "docs": {
        "truthUpdatedAt": null,
        "workboardUpdatedAt": null,
        "handoffUpdatedAt": null
      },
      "sources": [],
      "warnings": [
        "No dedicated worktree is currently checked out for this branch.",
        "No rich branch-local dashboard data is configured for this branch in v1."
      ]
    },
    {
      "path": "C:/RIFT MODDING/RiftReader_camera_feature",
      "sources": [
        {
          "label": "Active camera workflow doc",
          "path": "C:/RIFT MODDING/RiftReader_camera_feature/docs/camera-orientation-discovery.md",
          "note": "Primary source for the current camera-branch truth and bottleneck.",
          "present": true,
          "updatedAt": "2026-04-16T08:45:28.5557920-04:00"
        },
        {
          "label": "Input/control workflow doc",
          "path": "C:/RIFT MODDING/RiftReader_camera_feature/docs/input-control-workflow.md",
          "note": "Parsed for the recommended action order shown in the workboard.",
          "present": true,
          "updatedAt": "2026-04-16T08:45:28.5572825-04:00"
        },
        {
          "label": "Historical handoff doc",
          "path": "C:/RIFT MODDING/RiftReader_camera_feature/docs/camera-discovery-handoff.md",
          "note": "Background-only handoff retained for context; not the active workflow.",
          "present": true,
          "updatedAt": "2026-04-14T08:15:06.8461888-04:00"
        },
        {
          "label": "Current anchor capture",
          "path": "C:/RIFT MODDING/RiftReader_camera_feature/scripts/captures/player-current-anchor.json",
          "note": "Feeds the latest anchor-capture summary.",
          "present": true,
          "updatedAt": "2026-04-16T10:00:42.1277425-04:00"
        },
        {
          "label": "Coord write-trace status",
          "path": "C:/RIFT MODDING/RiftReader_camera_feature/scripts/captures/player-coord-write-trace.status.txt",
          "note": "Feeds the latest coord write-trace summary and warnings.",
          "present": true,
          "updatedAt": "2026-04-16T07:38:20.6893334-04:00"
        }
      ],
      "latestRuns": {
        "screen": {
          "label": "Latest anchor capture",
          "at": "2026-04-16T10:00:42.1158569-04:00",
          "summary": "Anchor 0x245A3DB7070; family=fam-6F81F26E; selection=ce-guided-family; coords=[0, 4, 8]."
        },
        "recovery": {
          "label": "Latest coord write trace",
          "at": "2026-04-16T11:38:20Z",
          "summary": "status=hit; stage=breakpoint-set"
        },
        "probe": {
          "label": "Workflow freshness",
          "at": "2026-04-16T08:45:28.5557920-04:00",
          "summary": "Live yaw verified; derived pitch usable via orbit derivation; direct pitch scalar unresolved."
        }
      },
      "handoff": {
        "ready": true,
        "path": "C:/RIFT MODDING/RiftReader_camera_feature/docs/camera-orientation-discovery.md",
        "summary": "trace from mirrored orbit / yaw families toward the authoritative camera/controller object"
      },
      "bottleneck": "trace from mirrored orbit / yaw families toward the authoritative camera/controller object",
      "candidates": {
        "counts": {
          "workflowDocs": 2,
          "captures": 2
        },
        "top": [],
        "rows": []
      },
      "isCurrent": false,
      "workboard": {
        "now": [
          {
            "item": "Alt+Z alternate zoom toggle",
            "lane": "P1",
            "note": "`C:\\RIFT MODDING\\RiftReader\\Run-AltZRetry.ps1` or `C:\\RIFT MODDING\\RiftReader\\scripts\\test-camera-altz-stimulus-safe.ps1` — Strong zoom/distance cross-check; helps separate distance fields from orientation fields."
          },
          {
            "item": "RMB hold + mouse move",
            "lane": "P2",
            "note": "`C:\\RIFT MODDING\\RiftReader\\scripts\\test-rmb-camera.ps1` — Closest to real camera yaw/pitch behavior; preferred orientation stimulus because Alt+S resets on release."
          },
          {
            "item": "Mouse wheel zoom",
            "lane": "P3",
            "note": "`C:\\RIFT MODDING\\RiftReader\\scripts\\zoom-camera.ps1` or `C:\\RIFT MODDING\\RiftReader\\scripts\\test-camera-stimulus.ps1` — Clean scalar-style zoom stimulus."
          }
        ],
        "parallelNow": [
          {
            "item": "preserve the current working live read path",
            "lane": "workflow",
            "note": ""
          },
          {
            "item": "trace from mirrored orbit / yaw families toward the authoritative camera/controller object",
            "lane": "workflow",
            "note": ""
          },
          {
            "item": "replace derived pitch only after a direct source beats it in live repeatability",
            "lane": "workflow",
            "note": ""
          }
        ],
        "next": [
          {
            "item": "Movement nudges (`W/A/S/D`)",
            "lane": "P4",
            "note": "`C:\\RIFT MODDING\\RiftReader\\scripts\\send-rift-key.ps1` — Best for reacquiring anchors or forcing small movement deltas, not the first camera-discovery stimulus."
          }
        ],
        "parked": []
      },
      "role": "camera-discovery",
      "status": "partial",
      "truth": [
        {
          "label": "Live yaw path",
          "status": "verified"
        },
        {
          "label": "Derived pitch path",
          "status": "usable"
        },
        {
          "label": "Direct standalone pitch scalar",
          "status": "unresolved"
        },
        {
          "label": "Controller object",
          "status": "unresolved"
        },
        {
          "label": "Input/control workflow",
          "status": "canonical"
        }
      ],
      "id": "feature/camera-orientation-discovery",
      "name": "feature/camera-orientation-discovery",
      "warnings": [
        "Checked out in a separate worktree: C:/RIFT MODDING/RiftReader_camera_feature",
        "Latest coord write trace recorded hit: non-ok status recorded"
      ],
      "docs": {
        "truthUpdatedAt": "2026-04-16T08:45:28.5557920-04:00",
        "workboardUpdatedAt": "2026-04-16T08:45:28.5572825-04:00",
        "handoffUpdatedAt": "2026-04-16T08:45:28.5557920-04:00"
      }
    },
    {
      "id": "backup-camera-orientation-local",
      "name": "backup-camera-orientation-local",
      "path": "C:/RIFT MODDING/RiftReader_facing",
      "isCurrent": false,
      "role": "camera-branch",
      "status": "minimal",
      "bottleneck": "Fix narrowing order: changed first (fast), then unchanged/changed alternation",
      "truth": [],
      "latestRuns": {
        "screen": {
          "label": "Latest screen run",
          "at": null,
          "summary": "No structured screen run data configured."
        },
        "recovery": {
          "label": "Latest recovery run",
          "at": null,
          "summary": "No structured recovery data configured."
        },
        "probe": {
          "label": "Latest addon probe",
          "at": null,
          "summary": "No structured probe data configured."
        }
      },
      "workboard": {
        "now": [],
        "parallelNow": [],
        "next": [],
        "parked": []
      },
      "candidates": {
        "counts": {},
        "top": [],
        "rows": []
      },
      "handoff": {
        "ready": false,
        "path": "",
        "summary": "No branch handoff doc configured in v1."
      },
      "docs": {
        "truthUpdatedAt": null,
        "workboardUpdatedAt": null,
        "handoffUpdatedAt": null
      },
      "sources": [],
      "warnings": [
        "No dedicated worktree is currently checked out for this branch.",
        "No rich branch-local dashboard data is configured for this branch in v1."
      ]
    },
    {
      "id": "codex/camera-yaw-pitch",
      "name": "codex/camera-yaw-pitch",
      "path": "C:/RIFT MODDING/RiftReader_facing",
      "isCurrent": false,
      "role": "camera-branch",
      "status": "minimal",
      "bottleneck": "Update camera recovery flow and guard window restores",
      "truth": [],
      "latestRuns": {
        "screen": {
          "label": "Latest screen run",
          "at": null,
          "summary": "No structured screen run data configured."
        },
        "recovery": {
          "label": "Latest recovery run",
          "at": null,
          "summary": "No structured recovery data configured."
        },
        "probe": {
          "label": "Latest addon probe",
          "at": null,
          "summary": "No structured probe data configured."
        }
      },
      "workboard": {
        "now": [],
        "parallelNow": [],
        "next": [],
        "parked": []
      },
      "candidates": {
        "counts": {},
        "top": [],
        "rows": []
      },
      "handoff": {
        "ready": false,
        "path": "",
        "summary": "No branch handoff doc configured in v1."
      },
      "docs": {
        "truthUpdatedAt": null,
        "workboardUpdatedAt": null,
        "handoffUpdatedAt": null
      },
      "sources": [],
      "warnings": [
        "No dedicated worktree is currently checked out for this branch.",
        "No rich branch-local dashboard data is configured for this branch in v1."
      ]
    },
    {
      "id": "navigation",
      "name": "navigation",
      "path": "C:/RIFT MODDING/RiftReader_facing",
      "isCurrent": false,
      "role": "branch",
      "status": "minimal",
      "bottleneck": "docs: add ReaderBridge compact GUI handoff",
      "truth": [],
      "latestRuns": {
        "screen": {
          "label": "Latest screen run",
          "at": null,
          "summary": "No structured screen run data configured."
        },
        "recovery": {
          "label": "Latest recovery run",
          "at": null,
          "summary": "No structured recovery data configured."
        },
        "probe": {
          "label": "Latest addon probe",
          "at": null,
          "summary": "No structured probe data configured."
        }
      },
      "workboard": {
        "now": [],
        "parallelNow": [],
        "next": [],
        "parked": []
      },
      "candidates": {
        "counts": {},
        "top": [],
        "rows": []
      },
      "handoff": {
        "ready": false,
        "path": "",
        "summary": "No branch handoff doc configured in v1."
      },
      "docs": {
        "truthUpdatedAt": null,
        "workboardUpdatedAt": null,
        "handoffUpdatedAt": null
      },
      "sources": [],
      "warnings": [
        "No dedicated worktree is currently checked out for this branch.",
        "No rich branch-local dashboard data is configured for this branch in v1."
      ]
    },
    {
      "id": "opencode/hidden-tiger",
      "name": "opencode/hidden-tiger",
      "path": "C:/Users/mrkoo/.local/share/opencode/worktree/a5bb6559dabaa305972a37e45ae4b9b01c63b7bd/hidden-tiger",
      "isCurrent": false,
      "role": "branch",
      "status": "partial",
      "bottleneck": "enhance: add help parameter and improve error handling to send-rift-command script",
      "truth": [],
      "latestRuns": {
        "screen": {
          "label": "Latest screen run",
          "at": null,
          "summary": "No structured screen run data configured."
        },
        "recovery": {
          "label": "Latest recovery run",
          "at": null,
          "summary": "No structured recovery data configured."
        },
        "probe": {
          "label": "Latest addon probe",
          "at": null,
          "summary": "No structured probe data configured."
        }
      },
      "workboard": {
        "now": [],
        "parallelNow": [],
        "next": [],
        "parked": []
      },
      "candidates": {
        "counts": {},
        "top": [],
        "rows": []
      },
      "handoff": {
        "ready": false,
        "path": "",
        "summary": "No branch handoff doc configured in v1."
      },
      "docs": {
        "truthUpdatedAt": null,
        "workboardUpdatedAt": null,
        "handoffUpdatedAt": null
      },
      "sources": [],
      "warnings": [
        "Checked out in a separate worktree: C:/Users/mrkoo/.local/share/opencode/worktree/a5bb6559dabaa305972a37e45ae4b9b01c63b7bd/hidden-tiger",
        "No rich branch-local dashboard data is configured for this branch in v1."
      ]
    },
    {
      "id": "scanner-with-debug",
      "name": "scanner-with-debug",
      "path": "C:/RIFT MODDING/RiftReader",
      "isCurrent": false,
      "role": "branch",
      "status": "partial",
      "bottleneck": "[ahead 1] Stabilize coord-refresh truth promotion",
      "truth": [],
      "latestRuns": {
        "screen": {
          "label": "Latest screen run",
          "at": null,
          "summary": "No structured screen run data configured."
        },
        "recovery": {
          "label": "Latest recovery run",
          "at": null,
          "summary": "No structured recovery data configured."
        },
        "probe": {
          "label": "Latest addon probe",
          "at": null,
          "summary": "No structured probe data configured."
        }
      },
      "workboard": {
        "now": [],
        "parallelNow": [],
        "next": [],
        "parked": []
      },
      "candidates": {
        "counts": {},
        "top": [],
        "rows": []
      },
      "handoff": {
        "ready": false,
        "path": "",
        "summary": "No branch handoff doc configured in v1."
      },
      "docs": {
        "truthUpdatedAt": null,
        "workboardUpdatedAt": null,
        "handoffUpdatedAt": null
      },
      "sources": [],
      "warnings": [
        "Checked out in a separate worktree: C:/RIFT MODDING/RiftReader",
        "No rich branch-local dashboard data is configured for this branch in v1."
      ]
    }
  ],
  "defaultBranchId": "facing"
};

