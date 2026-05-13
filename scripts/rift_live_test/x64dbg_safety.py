from __future__ import annotations

from typing import Any


DEFAULT_MAX_LIVE_ATTACH_SECONDS = 30
MAX_LIVE_ATTACH_SECONDS = 90
DEFAULT_UNRESPONSIVE_ABORT_SECONDS = 15
DEFAULT_MAX_GO_ATTEMPTS = 1


def live_attach_policy(
    *,
    max_live_attach_seconds: int = DEFAULT_MAX_LIVE_ATTACH_SECONDS,
    unresponsive_abort_seconds: int = DEFAULT_UNRESPONSIVE_ABORT_SECONDS,
    max_go_attempts: int = DEFAULT_MAX_GO_ATTEMPTS,
) -> dict[str, Any]:
    return {
        "maxLiveAttachSeconds": max_live_attach_seconds,
        "hardMaxLiveAttachSeconds": MAX_LIVE_ATTACH_SECONDS,
        "unresponsiveAbortSeconds": unresponsive_abort_seconds,
        "maxGoAttempts": max_go_attempts,
        "detachBeforeAnalysis": True,
        "captureMinimalStopContextBeforeDetach": True,
        "exceptionSwallowRetryLoopAllowed": False,
        "watchpointsRequirePredictablyRunningTarget": True,
        "staleAbsoluteAddressesAfterLogoutRelogRestart": True,
        "prebuildCommandsAndDetachPathBeforeAttach": True,
    }


def validate_live_attach_policy(
    *,
    max_live_attach_seconds: int,
    unresponsive_abort_seconds: int,
    max_go_attempts: int,
) -> list[str]:
    blockers: list[str] = []
    if max_live_attach_seconds <= 0:
        blockers.append("max-live-attach-seconds-must-be-positive")
    if max_live_attach_seconds > MAX_LIVE_ATTACH_SECONDS:
        blockers.append(
            f"max-live-attach-seconds-exceeds-hard-limit:{max_live_attach_seconds}>{MAX_LIVE_ATTACH_SECONDS}"
        )
    if unresponsive_abort_seconds <= 0:
        blockers.append("unresponsive-abort-seconds-must-be-positive")
    if max_live_attach_seconds > 0 and unresponsive_abort_seconds > max_live_attach_seconds:
        blockers.append(
            f"unresponsive-abort-seconds-exceeds-live-window:{unresponsive_abort_seconds}>{max_live_attach_seconds}"
        )
    if max_go_attempts < 0:
        blockers.append("max-go-attempts-must-be-non-negative")
    if max_go_attempts > DEFAULT_MAX_GO_ATTEMPTS:
        blockers.append(f"max-go-attempts-exceeds-safe-default:{max_go_attempts}>{DEFAULT_MAX_GO_ATTEMPTS}")
    return blockers
