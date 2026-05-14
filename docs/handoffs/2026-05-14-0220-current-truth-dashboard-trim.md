# Current-truth dashboard trim handoff

_Last updated: 2026-05-14 02:20 UTC._

## Verdict

`docs/recovery/current-truth.md` is now a dashboard, not an audit log. The superseded full chronology was moved to `docs/recovery/historical/current-truth-full-2026-05-14-0216-before-trim.md` with a stale/audit-only banner. A compact machine-readable contract now lives at `docs/recovery/current-truth.json` and validates with `scripts/validate_current_truth.py`.

## Current operating truth

| Item | Value |
|---|---|
| Current human truth | `docs/recovery/current-truth.md` |
| Current machine truth | `docs/recovery/current-truth.json` |
| Historical full chronology | `docs/recovery/historical/current-truth-full-2026-05-14-0216-before-trim.md` |
| Historical folder policy | `docs/recovery/historical/README.md` |
| Validator | `scripts/validate_current_truth.py` |

## Safety status

| Gate | Status |
|---|---|
| Movement | blocked |
| Live reference | `ReaderBridge_RRAPICOORD1` usable for read-only proof |
| Best candidate | `family-snapshot-hit-000001` / `0x268D1FA6120` |
| Static chain | not proven |
| Same-target ProofOnly | not passing |

## Validation

- `python -m py_compile scripts\rift_live_test\current_truth_validator.py scripts\validate_current_truth.py scripts\test_validate_current_truth.py`
- `python scripts\test_validate_current_truth.py -v`
- `python scripts\validate_current_truth.py --json`

## Resume prompt

Resume in `C:\RIFT MODDING\RiftReader` on `main`. Read `docs/recovery/current-truth.md` first for the dashboard and `docs/recovery/current-truth.json` for machine-readable truth. Do not mine old truth from historical files unless explicitly auditing. Historical files under `docs/recovery/historical/` are stale by default. Movement remains blocked; continue with bounded read-only static-chain/owner investigation from `family-snapshot-hit-000001` only.
