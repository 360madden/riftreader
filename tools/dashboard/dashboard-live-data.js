window.DASHBOARD_LIVE_DATA = {
    "meta":  {
                 "generatedAt":  "2026-04-18T00:42:47.3479952-04:00",
                 "staleAfterSeconds":  10,
                 "status":  "active",
                 "sources":  {
                                 "repo":  {
                                              "status":  "active",
                                              "updatedAt":  "2026-04-18T00:42:47.3479952-04:00",
                                              "usingPrevious":  false,
                                              "fallback":  "",
                                              "error":  ""
                                          },
                                 "snapshot":  {
                                                  "status":  "active",
                                                  "updatedAt":  "2026-04-18T00:42:47.3479952-04:00",
                                                  "usingPrevious":  false,
                                                  "fallback":  "",
                                                  "error":  ""
                                              },
                                 "player":  {
                                                "status":  "active",
                                                "updatedAt":  "2026-04-18T00:42:47.3479952-04:00",
                                                "usingPrevious":  false,
                                                "fallback":  "",
                                                "error":  ""
                                            },
                                 "target":  {
                                                "status":  "active",
                                                "updatedAt":  "2026-04-18T00:42:47.3479952-04:00",
                                                "usingPrevious":  false,
                                                "fallback":  "",
                                                "error":  ""
                                            }
                             }
             },
    "repo":  {
                 "repoPath":  "C:/RIFT MODDING/RiftReader",
                 "currentBranch":  "scanner-with-debug",
                 "changedFileCount":  17,
                 "dirty":  true,
                 "dirtyCounts":  {
                                     "modified":  9,
                                     "added":  0,
                                     "deleted":  0,
                                     "renamed":  0,
                                     "untracked":  8
                                 },
                 "changes":  [
                                 " M README.md",
                                 " M docs/analysis/2026-04-17-debug-trace-progress-and-live-attach-status.md",
                                 " M reader/RiftReader.Reader/Debugging/DebugTraceWorker.cs",
                                 " M scripts/build-dashboard-summary.ps1",
                                 " M scripts/captures/player-signature-captures.tsv",
                                 " M scripts/open-x64dbg.ps1",
                                 " M tools/dashboard/dashboard-data.js",
                                 " M tools/dashboard/dashboard-live-data.js",
                                 " M tools/reverse-engineering/README.md",
                                 "?? artifacts/",
                                 "?? docs/recovery/focused-postmessage-discovery-prompt.json",
                                 "?? scripts/inspect-rift-debug-state.cmd",
                                 "?? scripts/inspect-rift-debug-state.ps1",
                                 "?? scripts/open-rift-in-x64dbg.cmd",
                                 "?? scripts/open-rift-in-x64dbg.ps1",
                                 "?? tools/reverse-engineering/game_debug_scanner_hub.py",
                                 "?? tools/reverse-engineering/test-game-debug-scanner-hub.ps1"
                             ],
                 "updatedAt":  "2026-04-18T00:42:47.3479952-04:00"
             },
    "snapshot":  {
                     "available":  true,
                     "updatedAt":  "2026-04-18T00:42:47.3479952-04:00",
                     "sourceFile":  "C:\\Users\\mrkoo\\OneDrive\\Documents\\RIFT\\Interface\\Saved\\rift315.1@gmail.com\\Deepwood\\Atank\\SavedVariables\\ReaderBridgeExport.lua",
                     "loadedAt":  "2026-04-18T04:42:53.7813517+00:00",
                     "exportCount":  923,
                     "lastReason":  "save-begin",
                     "status":  "ready",
                     "exportReason":  "save-begin",
                     "sourceMode":  "DirectAPI",
                     "sourceAddon":  "RiftAPI",
                     "sourceVersion":  null,
                     "generatedAtReal":  9524.935546875,
                     "playerName":  "Atank",
                     "targetName":  null
                 },
    "player":  {
                   "available":  true,
                   "updatedAt":  "2026-04-18T00:42:47.3479952-04:00",
                   "sourceMode":  "memory+snapshot",
                   "sourceFile":  "C:\\Users\\mrkoo\\OneDrive\\Documents\\RIFT\\Interface\\Saved\\rift315.1@gmail.com\\Deepwood\\Atank\\SavedVariables\\ReaderBridgeExport.lua",
                   "name":  "Atank",
                   "role":  "tank",
                   "location":  "Thedeor\u0027s Circle",
                   "level":  {
                                 "current":  45,
                                 "memory":  45,
                                 "expected":  45,
                                 "matches":  true
                             },
                   "health":  {
                                  "current":  18148,
                                  "max":  18148,
                                  "percent":  100,
                                  "memory":  18148,
                                  "expected":  18148,
                                  "matches":  true
                              },
                   "resource":  {
                                    "kind":  "Power",
                                    "current":  100,
                                    "max":  100,
                                    "percent":  100
                                },
                   "coords":  {
                                  "x":  7419.4897460938,
                                  "y":  863.58996582031,
                                  "z":  2945.4099121094,
                                  "memoryX":  7419.4897,
                                  "memoryY":  863.58997,
                                  "memoryZ":  2945.41,
                                  "expectedX":  7419.4897460938,
                                  "expectedY":  863.58996582031,
                                  "expectedZ":  2945.4099121094
                              },
                   "memoryMatch":  {
                                       "LevelMatches":  true,
                                       "HealthMatches":  true,
                                       "CoordMatchesWithinTolerance":  true,
                                       "DeltaX":  0,
                                       "DeltaY":  0,
                                       "DeltaZ":  0
                                   },
                   "anchor":  {
                                  "address":  "0x15D85EF4720",
                                  "familyId":  "fam-6F81F26E",
                                  "familyNotes":  "location/cache blob",
                                  "signature":  "level@-144|health[1]@-136|health[2]@-128|health[3]@-120|coords@0",
                                  "selectionSource":  "ce-guided-family",
                                  "anchorProvenance":  "ce-guided-family",
                                  "anchorCacheFile":  "C:\\RIFT MODDING\\RiftReader\\scripts\\captures\\player-current-anchor.json",
                                  "anchorCacheUsed":  false,
                                  "anchorCacheUpdated":  true,
                                  "confirmationFile":  "C:\\RIFT MODDING\\RiftReader\\scripts\\captures\\ce-smart-player-family.json"
                              },
                   "process":  {
                                   "processId":  10828,
                                   "processName":  "rift_x64"
                               }
               },
    "target":  {
                   "available":  true,
                   "hasTarget":  true,
                   "updatedAt":  "2026-04-18T00:42:47.3479952-04:00",
                   "sourceMode":  "memory+snapshot",
                   "sourceFile":  null,
                   "name":  null,
                   "role":  null,
                   "location":  null,
                   "level":  {
                                 "current":  null,
                                 "memory":  null,
                                 "expected":  null,
                                 "matches":  null
                             },
                   "health":  {
                                  "current":  null,
                                  "max":  null,
                                  "percent":  null,
                                  "memory":  null,
                                  "expected":  null,
                                  "matches":  null
                              },
                   "resource":  {
                                    "kind":  null,
                                    "current":  null,
                                    "max":  null,
                                    "percent":  null
                                },
                   "coords":  {
                                  "x":  null,
                                  "y":  null,
                                  "z":  null,
                                  "memoryX":  null,
                                  "memoryY":  null,
                                  "memoryZ":  null,
                                  "expectedX":  null,
                                  "expectedY":  null,
                                  "expectedZ":  null
                              },
                   "distance":  {
                                    "current":  null,
                                    "memory":  null,
                                    "expected":  null,
                                    "matches":  null,
                                    "delta":  null
                                },
                   "memoryMatch":  null,
                   "anchor":  {
                                  "address":  null,
                                  "familyId":  null,
                                  "familyNotes":  null,
                                  "signature":  null,
                                  "selectionSource":  null,
                                  "anchorProvenance":  null,
                                  "anchorCacheFile":  null,
                                  "anchorCacheUsed":  null,
                                  "anchorCacheUpdated":  null,
                                  "confirmationFile":  null
                              },
                   "process":  {
                                   "processId":  10828,
                                   "processName":  "rift_x64"
                               }
               },
    "errors":  {
                   "repo":  null,
                   "snapshot":  null,
                   "player":  null,
                   "target":  null
               }
};

