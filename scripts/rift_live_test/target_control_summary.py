# Version: riftreader-target-control-summary-v0.3.0
# Total-Character-Count: 2016
# Purpose: Compact target-control summaries for live-test run artifacts. Pure helper; no live game access.

from __future__ import annotations

from typing import Any


def compact_target_control_summary(summary: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {
            "status": "target-control-missing",
            "classification": "target-control-missing",
            "ok": False,
            "readyForReadOnlyProof": False,
            "readyForVisualGate": False,
            "readyForLiveInput": False,
            "summaryPath": None,
            "blockers": ["target_control_summary_missing"],
            "warnings": [],
            "capabilities": {},
        }

    return {
        "status": summary.get("status"),
        "classification": summary.get("classification"),
        "ok": bool(summary.get("ok")),
        "readyForReadOnlyProof": bool(summary.get("readyForReadOnlyProof")),
        "readyForVisualGate": bool(summary.get("readyForVisualGate")),
        "readyForLiveInput": bool(summary.get("readyForLiveInput")),
        "summaryPath": summary.get("summaryPath"),
        "blockers": list(summary.get("blockers") or []),
        "warnings": list(summary.get("warnings") or []),
        "capabilities": dict(summary.get("capabilities") or {}),
    }


def target_control_state_detail(summary: dict[str, Any] | None) -> str:
    compact = compact_target_control_summary(summary)
    blockers = compact.get("blockers") or []
    parts = [
        f"classification={compact.get('classification')}",
        f"readyForReadOnlyProof={compact.get('readyForReadOnlyProof')}",
        f"readyForVisualGate={compact.get('readyForVisualGate')}",
        f"readyForLiveInput={compact.get('readyForLiveInput')}",
    ]
    if blockers:
        parts.append("blockers=" + ",".join(str(item) for item in blockers))
    return ";".join(parts)


# END_OF_SCRIPT_MARKER
