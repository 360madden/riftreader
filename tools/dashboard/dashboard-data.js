window.DASHBOARD_DATA = {
    "meta":  {
                 "generatedAt":  "2026-04-15T17:01:33.3930940-04:00",
                 "repoPath":  "C:/RIFT MODDING/RiftReader",
                 "currentBranch":  "codex/dashboard-hud",
                 "worktrees":  [
                                   {
                                       "path":  "C:/RIFT MODDING/RiftReader",
                                       "head":  "9144f8b26866c5214b67ecf456155818613c0b0e",
                                       "branch":  "codex/dashboard-hud",
                                       "isCurrent":  true
                                   },
                                   {
                                       "path":  "C:/RIFT MODDING/RiftReader_camera_feature",
                                       "head":  "07aebc6afa12ce437e7982ab721c73ed0ed48ef4",
                                       "branch":  "feature/camera-orientation-discovery",
                                       "isCurrent":  false
                                   },
                                   {
                                       "path":  "C:/Users/mrkoo/.local/share/opencode/worktree/a5bb6559dabaa305972a37e45ae4b9b01c63b7bd/hidden-tiger",
                                       "head":  "1c0d04f225b7ee06320061631186298241a76a78",
                                       "branch":  "opencode/hidden-tiger",
                                       "isCurrent":  false
                                   }
                               ]
             },
    "branches":  [
                     {
                         "path":  "C:/RIFT MODDING/RiftReader",
                         "handoff":  {
                                         "ready":  true,
                                         "path":  "C:/RIFT MODDING/RiftReader/docs/handoffs/2026-04-15-codex-dashboard-hud.md",
                                         "summary":  "Keep the current branch summary, launcher flow, and source-file coverage aligned with the actual dashboard files before widening the schema again."
                                     },
                         "name":  "codex/dashboard-hud",
                         "sources":  [
                                         {
                                             "label":  "Dashboard app shell",
                                             "path":  "C:/RIFT MODDING/RiftReader/tools/dashboard/index.html",
                                             "note":  "Static HTML entrypoint that loads the generated dashboard data and UI bundle.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T16:20:39.4929409-04:00"
                                         },
                                         {
                                             "label":  "Dashboard UI bundle",
                                             "path":  "C:/RIFT MODDING/RiftReader/tools/dashboard/app.js",
                                             "note":  "Vanilla JS renderer for the branch list, overview cards, metrics, and details.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T16:12:10.5371930-04:00"
                                         },
                                         {
                                             "label":  "Dashboard stylesheet",
                                             "path":  "C:/RIFT MODDING/RiftReader/tools/dashboard/styles.css",
                                             "note":  "Dark responsive layout and component styling for the dashboard shell.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T15:08:46.3206839-04:00"
                                         },
                                         {
                                             "label":  "Compiled dashboard data",
                                             "path":  "C:/RIFT MODDING/RiftReader/tools/dashboard/dashboard-data.js",
                                             "note":  "Generated snapshot consumed directly by the browser.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T17:00:09.3481963-04:00"
                                         },
                                         {
                                             "label":  "Dashboard generator",
                                             "path":  "C:/RIFT MODDING/RiftReader/scripts/build-dashboard-summary.ps1",
                                             "note":  "Compiles git, docs, and capture artifacts into dashboard-data.js.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T14:07:58.6180829-04:00"
                                         },
                                         {
                                             "label":  "Dashboard README",
                                             "path":  "C:/RIFT MODDING/RiftReader/tools/dashboard/README.md",
                                             "note":  "Usage and maintenance notes for the dashboard workflow.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T16:12:38.1412020-04:00"
                                         },
                                         {
                                             "label":  "Launcher script",
                                             "path":  "C:/RIFT MODDING/RiftReader/scripts/open-dashboard.ps1",
                                             "note":  "Rebuilds and opens the dashboard in the default browser.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T15:16:37.4748386-04:00"
                                         },
                                         {
                                             "label":  "Launcher CMD wrapper",
                                             "path":  "C:/RIFT MODDING/RiftReader/scripts/open-dashboard.cmd",
                                             "note":  "Convenience entrypoint for cmd.exe users.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T14:07:26.8802687-04:00"
                                         },
                                         {
                                             "label":  "Branch workboard",
                                             "path":  "C:/RIFT MODDING/RiftReader/docs/branch-workboard-codex-dashboard-hud.md",
                                             "note":  "Parsed for the dashboard branch Now / Parallel now / Next sections.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T14:06:54.4786521-04:00"
                                         },
                                         {
                                             "label":  "Branch handoff",
                                             "path":  "C:/RIFT MODDING/RiftReader/docs/handoffs/2026-04-15-codex-dashboard-hud.md",
                                             "note":  "Used for handoff readiness and next-conversation summary.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T14:07:01.7946519-04:00"
                                         }
                                     ],
                         "candidates":  {
                                            "counts":  {
                                                           "branches":  7,
                                                           "richBranches":  3,
                                                           "worktrees":  3,
                                                           "sources":  10,
                                                           "dirtyFiles":  16
                                                       },
                                            "top":  [
                                                        {
                                                            "label":  "Dashboard toolchain",
                                                            "classification":  "active",
                                                            "reason":  "10 dashboard source file(s) are present, including the generator and launcher.",
                                                            "discoveryMode":  "codex/dashboard-hud",
                                                            "searchScore":  10
                                                        },
                                                        {
                                                            "label":  "Cross-branch coverage",
                                                            "classification":  "active",
                                                            "reason":  "3 rich branch view(s) are configured in the current snapshot.",
                                                            "discoveryMode":  "branch coverage",
                                                            "searchScore":  3
                                                        },
                                                        {
                                                            "label":  "Worktree visibility",
                                                            "classification":  "active",
                                                            "reason":  "3 checked-out worktree(s) are visible to the dashboard generator.",
                                                            "discoveryMode":  "git worktree",
                                                            "searchScore":  3
                                                        },
                                                        {
                                                            "label":  "Current worktree state",
                                                            "classification":  "dirty",
                                                            "reason":  "dirty=16; modified=7; added=0; deleted=0; renamed=0; untracked=9.",
                                                            "discoveryMode":  "git status",
                                                            "searchScore":  16
                                                        }
                                                    ],
                                            "rows":  [

                                                     ]
                                        },
                         "role":  "dashboard",
                         "workboard":  {
                                           "now":  [
                                                       {
                                                           "item":  "Keep the current branch dashboard summary tied to real source files and git state",
                                                           "lane":  "Integrator",
                                                           "note":  "The active branch should not regress to placeholder-only status."
                                                       },
                                                       {
                                                           "item":  "Keep actor and camera branches aligned with the docs and artifacts that feed their rich views",
                                                           "lane":  "Data",
                                                           "note":  "Dashboard trust depends on upstream branch truth staying coherent."
                                                       },
                                                       {
                                                           "item":  "Keep source-file freshness visible in the UI",
                                                           "lane":  "UX",
                                                           "note":  "Makes stale snapshot risk obvious during handoff and review."
                                                       }
                                                   ],
                                           "parallelNow":  [
                                                               {
                                                                   "item":  "Keep the rebuild-and-open launcher working as dashboard files move",
                                                                   "lane":  "Tooling",
                                                                   "note":  "launcher stays current + no broken entrypoint"
                                                               },
                                                               {
                                                                   "item":  "Keep dashboard usage docs aligned with the real workflow",
                                                                   "lane":  "Docs",
                                                                   "note":  "README reflects regenerate/open steps"
                                                               },
                                                               {
                                                                   "item":  "Keep generic branches readable even when they only have fallback metadata",
                                                                   "lane":  "UX",
                                                                   "note":  "no confusing empty states or bogus rich-data claims"
                                                               }
                                                           ],
                                           "next":  [
                                                        {
                                                            "item":  "Add a lightweight dashboard generator smoke check",
                                                            "lane":  "Tooling",
                                                            "note":  "after the current data shape settles"
                                                        },
                                                        {
                                                            "item":  "Move branch-specific config out of hard-coded switches",
                                                            "lane":  "Architecture",
                                                            "note":  "after rich branch coverage stops moving around"
                                                        },
                                                        {
                                                            "item":  "Run a browser visual pass on narrower widths",
                                                            "lane":  "UX",
                                                            "note":  "after the current dashboard cards and labels stabilize"
                                                        }
                                                    ],
                                           "parked":  [
                                                          {
                                                              "item":  "Live auto-refresh",
                                                              "lane":  "",
                                                              "note":  "static snapshots are the intended v1 model"
                                                          },
                                                          {
                                                              "item":  "Inline editing/actions from the dashboard",
                                                              "lane":  "",
                                                              "note":  "out of scope for the display-only branch"
                                                          },
                                                          {
                                                              "item":  "Adding a backend or service layer",
                                                              "lane":  "",
                                                              "note":  "unnecessary for the current repo workflow"
                                                          }
                                                      ]
                                       },
                         "latestRuns":  {
                                            "screen":  {
                                                           "label":  "Latest dashboard build",
                                                           "at":  "2026-04-15T17:01:33.3930940-04:00",
                                                           "summary":  "Compiled 7 branches across 3 worktree(s) into dashboard-data.js."
                                                       },
                                            "recovery":  {
                                                             "label":  "Latest branch commit",
                                                             "at":  "2026-04-15T13:47:27-04:00",
                                                             "summary":  "Clean up UI artifacts and note actor-yaw branch overlay (9144f8b)"
                                                         },
                                            "probe":  {
                                                          "label":  "Working tree state",
                                                          "at":  "2026-04-15T17:01:33.6090692-04:00",
                                                          "summary":  "dirty=16; modified=7; added=0; deleted=0; renamed=0; untracked=9."
                                                      }
                                        },
                         "docs":  {
                                      "truthUpdatedAt":  "2026-04-15T14:07:58.6180829-04:00",
                                      "workboardUpdatedAt":  "2026-04-15T14:06:54.4786521-04:00",
                                      "handoffUpdatedAt":  "2026-04-15T14:07:01.7946519-04:00"
                                  },
                         "id":  "codex/dashboard-hud",
                         "truth":  [
                                       {
                                           "label":  "Dashboard shell",
                                           "status":  "working"
                                       },
                                       {
                                           "label":  "Snapshot generator",
                                           "status":  "working"
                                       },
                                       {
                                           "label":  "Open-in-browser launcher",
                                           "status":  "working"
                                       },
                                       {
                                           "label":  "Rich branch coverage",
                                           "status":  "3 configured"
                                       },
                                       {
                                           "label":  "Refresh model",
                                           "status":  "manual snapshot"
                                       },
                                       {
                                           "label":  "Current worktree",
                                           "status":  "dirty"
                                       }
                                   ],
                         "isCurrent":  true,
                         "status":  "partial",
                         "bottleneck":  "Keep the current branch dashboard summary tied to real source files and git state",
                         "warnings":  [
                                          "Current worktree has 16 pending change(s)."
                                      ]
                     },
                     {
                         "path":  "C:/RIFT MODDING/RiftReader",
                         "handoff":  {
                                         "ready":  true,
                                         "path":  "C:/RIFT MODDING/RiftReader/docs/handoffs/2026-04-15-codex-actor-yaw-pitch.md",
                                         "summary":  "**\"Pick the next retest target from the latest offline analysis and explain why.\"**"
                                     },
                         "name":  "codex/actor-yaw-pitch",
                         "sources":  [
                                         {
                                             "label":  "Current truth doc",
                                             "path":  "C:/RIFT MODDING/RiftReader/docs/recovery/current-truth.md",
                                             "note":  "Parsed for the truth rows shown in the branch overview.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T00:03:28.1799404-04:00"
                                         },
                                         {
                                             "label":  "Branch workboard",
                                             "path":  "C:/RIFT MODDING/RiftReader/docs/branch-workboard-codex-actor-yaw-pitch.md",
                                             "note":  "Parsed for Now / Parallel now / Next sections.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T12:35:03.2579753-04:00"
                                         },
                                         {
                                             "label":  "Branch handoff",
                                             "path":  "C:/RIFT MODDING/RiftReader/docs/handoffs/2026-04-15-codex-actor-yaw-pitch.md",
                                             "note":  "Used for handoff readiness and next-conversation summary.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T12:35:30.4302340-04:00"
                                         },
                                         {
                                             "label":  "Offline analysis JSON",
                                             "path":  "C:/RIFT MODDING/RiftReader/scripts/captures/actor-orientation-offline-analysis.json",
                                             "note":  "Drives candidate counts, ranking, and the detailed table.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T09:13:56.6528947-04:00"
                                         },
                                         {
                                             "label":  "Candidate screen JSON",
                                             "path":  "C:/RIFT MODDING/RiftReader/scripts/captures/actor-orientation-candidate-screen.json",
                                             "note":  "Feeds the latest screen-run summary.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T07:34:07.8788217-04:00"
                                         },
                                         {
                                             "label":  "Recovery JSON",
                                             "path":  "C:/RIFT MODDING/RiftReader/scripts/captures/actor-orientation-recovery.json",
                                             "note":  "Feeds the latest recovery summary.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T02:36:56.9616116-04:00"
                                         },
                                         {
                                             "label":  "ReaderBridge probe JSON",
                                             "path":  "C:/RIFT MODDING/RiftReader/scripts/captures/readerbridge-orientation-probe.json",
                                             "note":  "Feeds the latest addon-probe summary.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-15T01:32:54.2849529-04:00"
                                         }
                                     ],
                         "candidates":  {
                                            "counts":  {
                                                           "basis-unresolved":  1,
                                                           "dead-nonresponsive":  15,
                                                           "drifting":  1
                                                       },
                                            "top":  [
                                                        {
                                                            "label":  "0x245B6D37C20@0xD4",
                                                            "classification":  "drifting",
                                                            "reason":  "idle_drift",
                                                            "discoveryMode":  "",
                                                            "searchScore":  null
                                                        },
                                                        {
                                                            "label":  "0x245D64D1100@0x114",
                                                            "classification":  "basis-unresolved",
                                                            "reason":  "",
                                                            "discoveryMode":  "",
                                                            "searchScore":  null
                                                        },
                                                        {
                                                            "label":  "0x245CDD820E0@0xD4",
                                                            "classification":  "dead-nonresponsive",
                                                            "reason":  "stable_but_nonresponsive",
                                                            "discoveryMode":  "pointer-hop",
                                                            "searchScore":  161
                                                        },
                                                        {
                                                            "label":  "0x245CDD91530@0xD4",
                                                            "classification":  "dead-nonresponsive",
                                                            "reason":  "stable_but_nonresponsive",
                                                            "discoveryMode":  "pointer-hop",
                                                            "searchScore":  161
                                                        }
                                                    ],
                                            "rows":  [
                                                         {
                                                             "candidate":  "0x245B6D37C20@0xD4",
                                                             "sourceAddress":  "0x245B6D37C20",
                                                             "basisOffset":  "0xD4",
                                                             "classification":  "drifting",
                                                             "rejectedReason":  "idle_drift",
                                                             "discoveryMode":  "",
                                                             "rootAddress":  "",
                                                             "responsive":  true,
                                                             "basisRecovered":  true,
                                                             "yawRecovered":  false,
                                                             "searchScore":  null,
                                                             "ledgerPenalty":  null,
                                                             "observedAt":  "04/15/2026 07:20:23"
                                                         },
                                                         {
                                                             "candidate":  "0x245D64D1100@0x114",
                                                             "sourceAddress":  "0x245D64D1100",
                                                             "basisOffset":  "0x114",
                                                             "classification":  "basis-unresolved",
                                                             "rejectedReason":  "",
                                                             "discoveryMode":  "",
                                                             "rootAddress":  "",
                                                             "responsive":  false,
                                                             "basisRecovered":  false,
                                                             "yawRecovered":  false,
                                                             "searchScore":  null,
                                                             "ledgerPenalty":  null,
                                                             "observedAt":  "04/15/2026 02:36:56"
                                                         },
                                                         {
                                                             "candidate":  "0x245CDD91530@0xD4",
                                                             "sourceAddress":  "0x245CDD91530",
                                                             "basisOffset":  "0xD4",
                                                             "classification":  "dead-nonresponsive",
                                                             "rejectedReason":  "stable_but_nonresponsive",
                                                             "discoveryMode":  "pointer-hop",
                                                             "rootAddress":  "0x245D9818070",
                                                             "responsive":  false,
                                                             "basisRecovered":  true,
                                                             "yawRecovered":  false,
                                                             "searchScore":  161,
                                                             "ledgerPenalty":  0,
                                                             "observedAt":  "04/15/2026 07:34:07"
                                                         },
                                                         {
                                                             "candidate":  "0x245CDD820E0@0xD4",
                                                             "sourceAddress":  "0x245CDD820E0",
                                                             "basisOffset":  "0xD4",
                                                             "classification":  "dead-nonresponsive",
                                                             "rejectedReason":  "stable_but_nonresponsive",
                                                             "discoveryMode":  "pointer-hop",
                                                             "rootAddress":  "0x245D9818070",
                                                             "responsive":  false,
                                                             "basisRecovered":  true,
                                                             "yawRecovered":  false,
                                                             "searchScore":  161,
                                                             "ledgerPenalty":  0,
                                                             "observedAt":  "04/15/2026 07:34:07"
                                                         },
                                                         {
                                                             "candidate":  "0x245BA2654A0@0xD4",
                                                             "sourceAddress":  "0x245BA2654A0",
                                                             "basisOffset":  "0xD4",
                                                             "classification":  "dead-nonresponsive",
                                                             "rejectedReason":  "stable_but_nonresponsive",
                                                             "discoveryMode":  "",
                                                             "rootAddress":  "",
                                                             "responsive":  false,
                                                             "basisRecovered":  true,
                                                             "yawRecovered":  false,
                                                             "searchScore":  null,
                                                             "ledgerPenalty":  null,
                                                             "observedAt":  "04/15/2026 07:27:35"
                                                         },
                                                         {
                                                             "candidate":  "0x245CE02F9B0@0x60",
                                                             "sourceAddress":  "0x245CE02F9B0",
                                                             "basisOffset":  "0x60",
                                                             "classification":  "dead-nonresponsive",
                                                             "rejectedReason":  "stable_but_nonresponsive",
                                                             "discoveryMode":  "",
                                                             "rootAddress":  "",
                                                             "responsive":  false,
                                                             "basisRecovered":  true,
                                                             "yawRecovered":  false,
                                                             "searchScore":  null,
                                                             "ledgerPenalty":  null,
                                                             "observedAt":  "04/15/2026 07:26:32"
                                                         },
                                                         {
                                                             "candidate":  "0x2459E7C0E40@0xD4",
                                                             "sourceAddress":  "0x2459E7C0E40",
                                                             "basisOffset":  "0xD4",
                                                             "classification":  "dead-nonresponsive",
                                                             "rejectedReason":  "stable_but_nonresponsive",
                                                             "discoveryMode":  "",
                                                             "rootAddress":  "",
                                                             "responsive":  false,
                                                             "basisRecovered":  true,
                                                             "yawRecovered":  false,
                                                             "searchScore":  null,
                                                             "ledgerPenalty":  null,
                                                             "observedAt":  "04/15/2026 07:25:32"
                                                         },
                                                         {
                                                             "candidate":  "0x2459EAD6610@0xD4",
                                                             "sourceAddress":  "0x2459EAD6610",
                                                             "basisOffset":  "0xD4",
                                                             "classification":  "dead-nonresponsive",
                                                             "rejectedReason":  "stable_but_nonresponsive",
                                                             "discoveryMode":  "",
                                                             "rootAddress":  "",
                                                             "responsive":  false,
                                                             "basisRecovered":  true,
                                                             "yawRecovered":  false,
                                                             "searchScore":  null,
                                                             "ledgerPenalty":  null,
                                                             "observedAt":  "04/15/2026 07:24:20"
                                                         },
                                                         {
                                                             "candidate":  "0x2459EAD5630@0xD4",
                                                             "sourceAddress":  "0x2459EAD5630",
                                                             "basisOffset":  "0xD4",
                                                             "classification":  "dead-nonresponsive",
                                                             "rejectedReason":  "stable_but_nonresponsive",
                                                             "discoveryMode":  "",
                                                             "rootAddress":  "",
                                                             "responsive":  false,
                                                             "basisRecovered":  true,
                                                             "yawRecovered":  false,
                                                             "searchScore":  null,
                                                             "ledgerPenalty":  null,
                                                             "observedAt":  "04/15/2026 07:23:20"
                                                         },
                                                         {
                                                             "candidate":  "0x245B8AE5F60@0xD4",
                                                             "sourceAddress":  "0x245B8AE5F60",
                                                             "basisOffset":  "0xD4",
                                                             "classification":  "dead-nonresponsive",
                                                             "rejectedReason":  "stable_but_nonresponsive",
                                                             "discoveryMode":  "",
                                                             "rootAddress":  "",
                                                             "responsive":  false,
                                                             "basisRecovered":  true,
                                                             "yawRecovered":  false,
                                                             "searchScore":  null,
                                                             "ledgerPenalty":  null,
                                                             "observedAt":  "04/15/2026 07:22:21"
                                                         },
                                                         {
                                                             "candidate":  "0x245B8AE6240@0xD4",
                                                             "sourceAddress":  "0x245B8AE6240",
                                                             "basisOffset":  "0xD4",
                                                             "classification":  "dead-nonresponsive",
                                                             "rejectedReason":  "stable_but_nonresponsive",
                                                             "discoveryMode":  "",
                                                             "rootAddress":  "",
                                                             "responsive":  false,
                                                             "basisRecovered":  true,
                                                             "yawRecovered":  false,
                                                             "searchScore":  null,
                                                             "ledgerPenalty":  null,
                                                             "observedAt":  "04/15/2026 07:21:22"
                                                         },
                                                         {
                                                             "candidate":  "0x245B8AE60D0@0xD4",
                                                             "sourceAddress":  "0x245B8AE60D0",
                                                             "basisOffset":  "0xD4",
                                                             "classification":  "dead-nonresponsive",
                                                             "rejectedReason":  "stable_but_nonresponsive",
                                                             "discoveryMode":  "",
                                                             "rootAddress":  "",
                                                             "responsive":  false,
                                                             "basisRecovered":  true,
                                                             "yawRecovered":  false,
                                                             "searchScore":  null,
                                                             "ledgerPenalty":  null,
                                                             "observedAt":  "04/15/2026 03:43:27"
                                                         },
                                                         {
                                                             "candidate":  "0x245B8AE5DF0@0xD4",
                                                             "sourceAddress":  "0x245B8AE5DF0",
                                                             "basisOffset":  "0xD4",
                                                             "classification":  "dead-nonresponsive",
                                                             "rejectedReason":  "stable_but_nonresponsive",
                                                             "discoveryMode":  "",
                                                             "rootAddress":  "",
                                                             "responsive":  false,
                                                             "basisRecovered":  true,
                                                             "yawRecovered":  false,
                                                             "searchScore":  null,
                                                             "ledgerPenalty":  null,
                                                             "observedAt":  "04/15/2026 03:42:28"
                                                         },
                                                         {
                                                             "candidate":  "0x245DC287020@0xD4",
                                                             "sourceAddress":  "0x245DC287020",
                                                             "basisOffset":  "0xD4",
                                                             "classification":  "dead-nonresponsive",
                                                             "rejectedReason":  "stable_but_nonresponsive",
                                                             "discoveryMode":  "",
                                                             "rootAddress":  "",
                                                             "responsive":  false,
                                                             "basisRecovered":  true,
                                                             "yawRecovered":  false,
                                                             "searchScore":  null,
                                                             "ledgerPenalty":  null,
                                                             "observedAt":  "04/15/2026 03:39:13"
                                                         },
                                                         {
                                                             "candidate":  "0x245D64B59B0@0xA0",
                                                             "sourceAddress":  "0x245D64B59B0",
                                                             "basisOffset":  "0xA0",
                                                             "classification":  "dead-nonresponsive",
                                                             "rejectedReason":  "stable_but_nonresponsive",
                                                             "discoveryMode":  "",
                                                             "rootAddress":  "",
                                                             "responsive":  false,
                                                             "basisRecovered":  true,
                                                             "yawRecovered":  false,
                                                             "searchScore":  null,
                                                             "ledgerPenalty":  null,
                                                             "observedAt":  "04/15/2026 03:37:50"
                                                         },
                                                         {
                                                             "candidate":  "0x245D1B92980@0xA0",
                                                             "sourceAddress":  "0x245D1B92980",
                                                             "basisOffset":  "0xA0",
                                                             "classification":  "dead-nonresponsive",
                                                             "rejectedReason":  "stable_but_nonresponsive",
                                                             "discoveryMode":  "",
                                                             "rootAddress":  "",
                                                             "responsive":  false,
                                                             "basisRecovered":  true,
                                                             "yawRecovered":  false,
                                                             "searchScore":  null,
                                                             "ledgerPenalty":  null,
                                                             "observedAt":  "04/15/2026 03:35:54"
                                                         },
                                                         {
                                                             "candidate":  "0x2459E74F1B0@0xD4",
                                                             "sourceAddress":  "0x2459E74F1B0",
                                                             "basisOffset":  "0xD4",
                                                             "classification":  "dead-nonresponsive",
                                                             "rejectedReason":  "stable_but_nonresponsive",
                                                             "discoveryMode":  "",
                                                             "rootAddress":  "",
                                                             "responsive":  false,
                                                             "basisRecovered":  true,
                                                             "yawRecovered":  false,
                                                             "searchScore":  null,
                                                             "ledgerPenalty":  null,
                                                             "observedAt":  "04/15/2026 03:34:32"
                                                         }
                                                     ]
                                        },
                         "role":  "actor-recovery",
                         "workboard":  {
                                           "now":  [
                                                       {
                                                           "item":  "Choose the next live retest target from current evidence",
                                                           "lane":  "Integrator",
                                                           "note":  "This is the current branch bottleneck."
                                                       },
                                                       {
                                                           "item":  "Keep ranking pressure on pointer-hop false positives",
                                                           "lane":  "B",
                                                           "note":  "Top-ranked candidates can still be stable-but-nonresponsive."
                                                       },
                                                       {
                                                           "item":  "Keep screen/ledger/recovery outputs coherent",
                                                           "lane":  "A",
                                                           "note":  "The branch depends on a single evidence story."
                                                       },
                                                       {
                                                           "item":  "Keep current-truth aligned with actual branch findings",
                                                           "lane":  "D",
                                                           "note":  "Prevents drift before the next conversation handoff."
                                                       }
                                                   ],
                                           "parallelNow":  [
                                                               {
                                                                   "item":  "Produce a concise ranked retest table from the latest offline analysis",
                                                                   "lane":  "A",
                                                                   "note":  "one table + recommended retest order"
                                                               },
                                                               {
                                                                   "item":  "Tighten rejection-reason/reporting clarity in one script family only",
                                                                   "lane":  "B",
                                                                   "note":  "patch + validation note + changed files"
                                                               },
                                                               {
                                                                   "item":  "Summarize addon-visible validation fields that help test-envelope trust",
                                                                   "lane":  "C",
                                                                   "note":  "coverage note + gap list"
                                                               },
                                                               {
                                                                   "item":  "Keep branch docs synchronized with the latest lane outputs",
                                                                   "lane":  "D",
                                                                   "note":  "updated docs + stale/active note"
                                                               },
                                                               {
                                                                   "item":  "Keep archive/retention docs current as cleanup changes land",
                                                                   "lane":  "E",
                                                                   "note":  "manifest/doc update only"
                                                               }
                                                           ],
                                           "next":  [
                                                        {
                                                            "item":  "Re-run post-update triage with the current ledger-aware flow",
                                                            "lane":  "B",
                                                            "note":  "after the next candidate-selection decision"
                                                        },
                                                        {
                                                            "item":  "Consolidate historical owner/source artifacts into a lighter reference summary",
                                                            "lane":  "A or D",
                                                            "note":  "after live recovery pace stabilizes"
                                                        },
                                                        {
                                                            "item":  "Formalize addon stable vs research schema split",
                                                            "lane":  "C + D",
                                                            "note":  "after current branch testing needs are clearer"
                                                        },
                                                        {
                                                            "item":  "Add a branch-local task board summary into README or recovery docs if needed",
                                                            "lane":  "D",
                                                            "note":  "only if the branch workflow becomes stable enough"
                                                        }
                                                    ],
                                           "parked":  [
                                                          {
                                                              "item":  "Camera rediscovery on `main`",
                                                              "lane":  "",
                                                              "note":  "not the branch critical path"
                                                          },
                                                          {
                                                              "item":  "Broad owner/source-chain rebuild",
                                                              "lane":  "",
                                                              "note":  "useful reference lane, but not the default first step right now"
                                                          },
                                                          {
                                                              "item":  "Large repo-wide refactors",
                                                              "lane":  "",
                                                              "note":  "too much drift risk while recovery is still unresolved"
                                                          },
                                                          {
                                                              "item":  "Extra cleanup beyond the current retention pass",
                                                              "lane":  "",
                                                              "note":  "no longer the best use of branch time"
                                                          }
                                                      ]
                                       },
                         "latestRuns":  {
                                            "screen":  {
                                                           "label":  "Latest screen run",
                                                           "at":  "2026-04-15T11:34:07.8719328+00:00",
                                                           "summary":  "Screened 2 candidates; responsive=0; dead=2; recoveryRuns=0."
                                                       },
                                            "recovery":  {
                                                             "label":  "Latest recovery run",
                                                             "at":  "2026-04-15T06:36:56.9524867+00:00",
                                                             "summary":  "BasisRecovered=False; YawRecovered=False; PitchRecovered=False; IdleConsistencyPass=True."
                                                         },
                                            "probe":  {
                                                          "label":  "Latest addon probe",
                                                          "at":  "2026-04-15T05:32:54.2047319+00:00",
                                                          "summary":  "PlayerSignal=False; directHeadingApiAvailable=False; detailCandidates=0; stateCandidates=0."
                                                      }
                                        },
                         "docs":  {
                                      "truthUpdatedAt":  "2026-04-15T00:03:28.1799404-04:00",
                                      "workboardUpdatedAt":  "2026-04-15T12:35:03.2579753-04:00",
                                      "handoffUpdatedAt":  "2026-04-15T12:35:30.4302340-04:00"
                                  },
                         "id":  "codex/actor-yaw-pitch",
                         "truth":  [
                                       {
                                           "label":  "Low-level reader",
                                           "status":  "reliable enough for active work"
                                       },
                                       {
                                           "label":  "ReaderBridge snapshot load",
                                           "status":  "working"
                                       },
                                       {
                                           "label":  "Player current read",
                                           "status":  "working"
                                       },
                                       {
                                           "label":  "Coord-anchor module pattern",
                                           "status":  "working"
                                       },
                                       {
                                           "label":  "Source-chain refresh",
                                           "status":  "broken after the update"
                                       },
                                       {
                                           "label":  "Selector-owner trace",
                                           "status":  "broken after the update"
                                       },
                                       {
                                           "label":  "CE scan / inspection lane",
                                           "status":  "usable for bounded reintegration"
                                       },
                                       {
                                           "label":  "CE debugger-trace lane",
                                           "status":  "suspected Windows debugger attach instability; keep opt-in and log repeated failures before patching guards"
                                       },
                                       {
                                           "label":  "Player orientation read",
                                           "status":  "stale; resume actor yaw/pitch recovery via addon-first orientation probing before rebuilding the old owner/source chain"
                                       },
                                       {
                                           "label":  "Camera yaw / pitch / distance on `main`",
                                           "status":  "stale / unverified after the update"
                                       },
                                       {
                                           "label":  "Authoritative camera controller",
                                           "status":  "not yet isolated"
                                       },
                                       {
                                           "label":  "Direct gameplay key stimulus on `main`",
                                           "status":  "background `PostMessage` via `post-rift-key.ps1` revalidated; foreground `SendInput` remains untrusted"
                                       }
                                   ],
                         "isCurrent":  false,
                         "status":  "active",
                         "bottleneck":  "Choose the next live retest target from current evidence",
                         "warnings":  [
                                          "No dedicated worktree is currently checked out for this branch.",
                                          "No candidate currently has surviving positive evidence after the latest merge.",
                                          "ReaderBridge orientation probe currently reports no player-facing signal.",
                                          "Source-chain refresh is still broken after the update."
                                      ]
                     },
                     {
                         "id":  "main",
                         "name":  "main",
                         "path":  "C:/RIFT MODDING/RiftReader",
                         "isCurrent":  false,
                         "role":  "baseline",
                         "status":  "minimal",
                         "bottleneck":  "Reference baseline only; not the active recovery branch.",
                         "truth":  [

                                   ],
                         "latestRuns":  {
                                            "screen":  {
                                                           "label":  "Latest screen run",
                                                           "at":  null,
                                                           "summary":  "No structured screen run data configured."
                                                       },
                                            "recovery":  {
                                                             "label":  "Latest recovery run",
                                                             "at":  null,
                                                             "summary":  "No structured recovery data configured."
                                                         },
                                            "probe":  {
                                                          "label":  "Latest addon probe",
                                                          "at":  null,
                                                          "summary":  "No structured probe data configured."
                                                      }
                                        },
                         "workboard":  {
                                           "now":  [

                                                   ],
                                           "parallelNow":  [

                                                           ],
                                           "next":  [

                                                    ],
                                           "parked":  [

                                                      ]
                                       },
                         "candidates":  {
                                            "counts":  {

                                                       },
                                            "top":  [

                                                    ],
                                            "rows":  [

                                                     ]
                                        },
                         "handoff":  {
                                         "ready":  false,
                                         "path":  "",
                                         "summary":  "No branch handoff doc configured in v1."
                                     },
                         "docs":  {
                                      "truthUpdatedAt":  null,
                                      "workboardUpdatedAt":  null,
                                      "handoffUpdatedAt":  null
                                  },
                         "sources":  [

                                     ],
                         "warnings":  [
                                          "No dedicated worktree is currently checked out for this branch.",
                                          "No rich branch-local dashboard data is configured for this branch in v1."
                                      ]
                     },
                     {
                         "path":  "C:/RIFT MODDING/RiftReader_camera_feature",
                         "handoff":  {
                                         "ready":  true,
                                         "path":  "C:/RIFT MODDING/RiftReader_camera_feature/docs/camera-orientation-discovery.md",
                                         "summary":  "trace from mirrored orbit / yaw families toward the authoritative camera/controller object"
                                     },
                         "name":  "feature/camera-orientation-discovery",
                         "sources":  [
                                         {
                                             "label":  "Active camera workflow doc",
                                             "path":  "C:/RIFT MODDING/RiftReader_camera_feature/docs/camera-orientation-discovery.md",
                                             "note":  "Primary source for the current camera-branch truth and bottleneck.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-14T08:15:06.8481943-04:00"
                                         },
                                         {
                                             "label":  "Input/control workflow doc",
                                             "path":  "C:/RIFT MODDING/RiftReader_camera_feature/docs/input-control-workflow.md",
                                             "note":  "Parsed for the recommended action order shown in the workboard.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-14T08:15:06.8552724-04:00"
                                         },
                                         {
                                             "label":  "Historical handoff doc",
                                             "path":  "C:/RIFT MODDING/RiftReader_camera_feature/docs/camera-discovery-handoff.md",
                                             "note":  "Background-only handoff retained for context; not the active workflow.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-14T08:15:06.8461888-04:00"
                                         },
                                         {
                                             "label":  "Current anchor capture",
                                             "path":  "C:/RIFT MODDING/RiftReader_camera_feature/scripts/captures/player-current-anchor.json",
                                             "note":  "Feeds the latest anchor-capture summary.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-14T21:14:13.3147561-04:00"
                                         },
                                         {
                                             "label":  "Coord write-trace status",
                                             "path":  "C:/RIFT MODDING/RiftReader_camera_feature/scripts/captures/player-coord-write-trace.status.txt",
                                             "note":  "Feeds the latest coord write-trace summary and warnings.",
                                             "present":  true,
                                             "updatedAt":  "2026-04-14T21:14:23.0092052-04:00"
                                         }
                                     ],
                         "candidates":  {
                                            "counts":  {
                                                           "workflowDocs":  2,
                                                           "captures":  2
                                                       },
                                            "top":  [

                                                    ],
                                            "rows":  [

                                                     ]
                                        },
                         "role":  "camera-discovery",
                         "workboard":  {
                                           "now":  [
                                                        {
                                                            "item":  "Alt+Z alternate zoom toggle",
                                                            "lane":  "P1",
                                                            "note":  "`C:\\RIFT MODDING\\RiftReader\\Run-AltZRetry.ps1` or `C:\\RIFT MODDING\\RiftReader\\scripts\\test-camera-altz-stimulus-safe.ps1` â€” Strong zoom/distance cross-check; helps separate distance fields from orientation fields."
                                                        },
                                                        {
                                                            "item":  "RMB hold + mouse move",
                                                            "lane":  "P2",
                                                            "note":  "`C:\\RIFT MODDING\\RiftReader\\scripts\\test-rmb-camera.ps1` â€” Closest to real camera yaw/pitch behavior; preferred orientation stimulus because Alt+S resets on release."
                                                        }
                                                   ],
                                           "parallelNow":  [
                                                               {
                                                                   "item":  "preserve the current working live read path",
                                                                   "lane":  "workflow",
                                                                   "note":  ""
                                                               },
                                                               {
                                                                   "item":  "trace from mirrored orbit / yaw families toward the authoritative camera/controller object",
                                                                   "lane":  "workflow",
                                                                   "note":  ""
                                                               },
                                                               {
                                                                   "item":  "replace derived pitch only after a direct source beats it in live repeatability",
                                                                   "lane":  "workflow",
                                                                   "note":  ""
                                                               }
                                                           ],
                                           "next":  [
                                                        {
                                                            "item":  "Mouse wheel zoom",
                                                            "lane":  "P4",
                                                            "note":  "`C:\\RIFT MODDING\\RiftReader\\scripts\\zoom-camera.ps1` or `C:\\RIFT MODDING\\RiftReader\\scripts\\test-camera-stimulus.ps1` â€” Clean scalar-style zoom stimulus."
                                                        },
                                                        {
                                                            "item":  "Movement nudges (`W/A/S/D`)",
                                                            "lane":  "P5",
                                                            "note":  "`C:\\RIFT MODDING\\RiftReader\\scripts\\send-rift-key.ps1` â€” Best for reacquiring anchors or forcing small movement deltas, not the first camera-discovery stimulus."
                                                        }
                                                    ],
                                           "parked":  [

                                                      ]
                                       },
                         "latestRuns":  {
                                            "screen":  {
                                                           "label":  "Latest anchor capture",
                                                           "at":  "2026-04-15T01:14:13.293994+00:00",
                                                           "summary":  "Anchor 0x19130D0AED0; family=fam-6F81F26E; selection=heuristic; coords=[0, 4, 8]."
                                                       },
                                            "recovery":  {
                                                             "label":  "Latest coord write trace",
                                                             "at":  "2026-04-15T01:14:23Z",
                                                             "summary":  "status=error; stage=debug-ready; error=Debugger attach did not become ready."
                                                         },
                                            "probe":  {
                                                          "label":  "Workflow freshness",
                                                          "at":  "2026-04-14T08:15:06.8481943-04:00",
                                                          "summary":  "Live yaw verified; derived pitch usable via orbit derivation; direct pitch scalar unresolved."
                                                      }
                                        },
                         "docs":  {
                                      "truthUpdatedAt":  "2026-04-14T08:15:06.8481943-04:00",
                                      "workboardUpdatedAt":  "2026-04-14T08:15:06.8552724-04:00",
                                      "handoffUpdatedAt":  "2026-04-14T08:15:06.8481943-04:00"
                                  },
                         "id":  "feature/camera-orientation-discovery",
                         "truth":  [
                                       {
                                           "label":  "Live yaw path",
                                           "status":  "verified"
                                       },
                                       {
                                           "label":  "Derived pitch path",
                                           "status":  "usable"
                                       },
                                       {
                                           "label":  "Direct standalone pitch scalar",
                                           "status":  "unresolved"
                                       },
                                       {
                                           "label":  "Controller object",
                                           "status":  "unresolved"
                                       },
                                       {
                                           "label":  "Input/control workflow",
                                           "status":  "canonical"
                                       }
                                   ],
                         "isCurrent":  false,
                         "status":  "partial",
                         "bottleneck":  "trace from mirrored orbit / yaw families toward the authoritative camera/controller object",
                         "warnings":  [
                                          "Checked out in a separate worktree: C:/RIFT MODDING/RiftReader_camera_feature",
                                          "Latest coord write trace recorded error: Debugger attach did not become ready."
                                      ]
                     },
                     {
                         "id":  "backup-camera-orientation-local",
                         "name":  "backup-camera-orientation-local",
                         "path":  "C:/RIFT MODDING/RiftReader",
                         "isCurrent":  false,
                         "role":  "camera-branch",
                         "status":  "minimal",
                         "bottleneck":  "Fix narrowing order: changed first (fast), then unchanged/changed alternation",
                         "truth":  [

                                   ],
                         "latestRuns":  {
                                            "screen":  {
                                                           "label":  "Latest screen run",
                                                           "at":  null,
                                                           "summary":  "No structured screen run data configured."
                                                       },
                                            "recovery":  {
                                                             "label":  "Latest recovery run",
                                                             "at":  null,
                                                             "summary":  "No structured recovery data configured."
                                                         },
                                            "probe":  {
                                                          "label":  "Latest addon probe",
                                                          "at":  null,
                                                          "summary":  "No structured probe data configured."
                                                      }
                                        },
                         "workboard":  {
                                           "now":  [

                                                   ],
                                           "parallelNow":  [

                                                           ],
                                           "next":  [

                                                    ],
                                           "parked":  [

                                                      ]
                                       },
                         "candidates":  {
                                            "counts":  {

                                                       },
                                            "top":  [

                                                    ],
                                            "rows":  [

                                                     ]
                                        },
                         "handoff":  {
                                         "ready":  false,
                                         "path":  "",
                                         "summary":  "No branch handoff doc configured in v1."
                                     },
                         "docs":  {
                                      "truthUpdatedAt":  null,
                                      "workboardUpdatedAt":  null,
                                      "handoffUpdatedAt":  null
                                  },
                         "sources":  [

                                     ],
                         "warnings":  [
                                          "No dedicated worktree is currently checked out for this branch.",
                                          "No rich branch-local dashboard data is configured for this branch in v1."
                                      ]
                     },
                     {
                         "id":  "codex/camera-yaw-pitch",
                         "name":  "codex/camera-yaw-pitch",
                         "path":  "C:/RIFT MODDING/RiftReader",
                         "isCurrent":  false,
                         "role":  "camera-branch",
                         "status":  "minimal",
                         "bottleneck":  "Document post-update drift and add input safety guidance",
                         "truth":  [

                                   ],
                         "latestRuns":  {
                                            "screen":  {
                                                           "label":  "Latest screen run",
                                                           "at":  null,
                                                           "summary":  "No structured screen run data configured."
                                                       },
                                            "recovery":  {
                                                             "label":  "Latest recovery run",
                                                             "at":  null,
                                                             "summary":  "No structured recovery data configured."
                                                         },
                                            "probe":  {
                                                          "label":  "Latest addon probe",
                                                          "at":  null,
                                                          "summary":  "No structured probe data configured."
                                                      }
                                        },
                         "workboard":  {
                                           "now":  [

                                                   ],
                                           "parallelNow":  [

                                                           ],
                                           "next":  [

                                                    ],
                                           "parked":  [

                                                      ]
                                       },
                         "candidates":  {
                                            "counts":  {

                                                       },
                                            "top":  [

                                                    ],
                                            "rows":  [

                                                     ]
                                        },
                         "handoff":  {
                                         "ready":  false,
                                         "path":  "",
                                         "summary":  "No branch handoff doc configured in v1."
                                     },
                         "docs":  {
                                      "truthUpdatedAt":  null,
                                      "workboardUpdatedAt":  null,
                                      "handoffUpdatedAt":  null
                                  },
                         "sources":  [

                                     ],
                         "warnings":  [
                                          "No dedicated worktree is currently checked out for this branch.",
                                          "No rich branch-local dashboard data is configured for this branch in v1."
                                      ]
                     },
                     {
                         "id":  "opencode/hidden-tiger",
                         "name":  "opencode/hidden-tiger",
                         "path":  "C:/Users/mrkoo/.local/share/opencode/worktree/a5bb6559dabaa305972a37e45ae4b9b01c63b7bd/hidden-tiger",
                         "isCurrent":  false,
                         "role":  "branch",
                         "status":  "partial",
                         "bottleneck":  "enhance: add help parameter and improve error handling to send-rift-command script",
                         "truth":  [

                                   ],
                         "latestRuns":  {
                                            "screen":  {
                                                           "label":  "Latest screen run",
                                                           "at":  null,
                                                           "summary":  "No structured screen run data configured."
                                                       },
                                            "recovery":  {
                                                             "label":  "Latest recovery run",
                                                             "at":  null,
                                                             "summary":  "No structured recovery data configured."
                                                         },
                                            "probe":  {
                                                          "label":  "Latest addon probe",
                                                          "at":  null,
                                                          "summary":  "No structured probe data configured."
                                                      }
                                        },
                         "workboard":  {
                                           "now":  [

                                                   ],
                                           "parallelNow":  [

                                                           ],
                                           "next":  [

                                                    ],
                                           "parked":  [

                                                      ]
                                       },
                         "candidates":  {
                                            "counts":  {

                                                       },
                                            "top":  [

                                                    ],
                                            "rows":  [

                                                     ]
                                        },
                         "handoff":  {
                                         "ready":  false,
                                         "path":  "",
                                         "summary":  "No branch handoff doc configured in v1."
                                     },
                         "docs":  {
                                      "truthUpdatedAt":  null,
                                      "workboardUpdatedAt":  null,
                                      "handoffUpdatedAt":  null
                                  },
                         "sources":  [

                                     ],
                         "warnings":  [
                                          "Checked out in a separate worktree: C:/Users/mrkoo/.local/share/opencode/worktree/a5bb6559dabaa305972a37e45ae4b9b01c63b7bd/hidden-tiger",
                                          "No rich branch-local dashboard data is configured for this branch in v1."
                                      ]
                     }
                 ],
    "defaultBranchId":  "codex/dashboard-hud"
};

