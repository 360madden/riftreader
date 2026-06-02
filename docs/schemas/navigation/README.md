# Navigation consumer JSON schemas

These schemas are the tracked contract package for external projects that
consume RiftReader navigation artifacts.

| Schema | Artifact kind | Purpose |
|---|---|---|
| `navigation-consumer-state.schema.json` | `riftreader-navigation-consumer-state` | Read-only current position/yaw payload. |
| `normalized-waypoints.schema.json` | `riftreader-normalized-navigation-waypoints` | Canonical waypoint file emitted by waypoint readiness. |
| `static-owner-continuous-route-sequence.schema.json` | `static-owner-continuous-route-sequence` | Saved no-input continuous route sequence dry-run summary. |
| `static-owner-continuous-route-sequence-contract-report.schema.json` | `static-owner-continuous-route-sequence-contract-report` | Saved-summary consumer contract report. |
| `navigation-waypoint-readiness.schema.json` | `riftreader-navigation-waypoint-readiness` | One-command waypoint lint + dry-run + contract bundle. |
| `navigation-consumer-demo.schema.json` | `riftreader-navigation-consumer-demo` | Downstream consumer readiness report over saved navigation artifacts. |

Use the repo validator:

```powershell
scripts\riftreader-navigation-schema-validate.cmd --input <summary.json> --json
```

The validator infers the schema from `kind` or `provenance.kind`. It reads saved
JSON only and sends no live input/movement.
