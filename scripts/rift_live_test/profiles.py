from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

_VALID_MODES = {
    "baseline-only",
    "proof-only",
    "recover-proof",
    "live-input",
    "live-input-series",
}


def load_profiles(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Profile config not found: {path}")
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Profile config root must be an object")
    if not isinstance(data.get("profiles"), dict):
        raise ValueError("Profile config must contain a profiles object")
    return data


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _resolve_repo_relative(repo_root: Path, value: str | None) -> str | None:
    if not value:
        return value
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((repo_root / path).resolve())


def load_profile(repo_root: Path, profiles_file: Path, name: str) -> dict[str, Any]:
    config = load_profiles(profiles_file)
    profiles = config["profiles"]
    if name not in profiles:
        raise KeyError(f"Profile '{name}' not found in {profiles_file}")

    defaults = config.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ValueError("defaults must be an object when present")

    profile = deep_merge(defaults, profiles[name])
    profile["name"] = name
    profile["profilesFile"] = str(profiles_file)

    for key in (
        "outputRoot",
        "proofAnchorFile",
        "promotionBaselinePoolFile",
        "promotionReferenceReadbackSummary",
    ):
        if key in profile:
            profile[key] = _resolve_repo_relative(repo_root, profile.get(key))

    mode = profile.get("mode")
    if mode not in _VALID_MODES:
        raise ValueError(f"Profile '{name}' has invalid mode '{mode}'")

    input_cfg = profile.get("input")
    if mode in {"live-input", "live-input-series"}:
        if not isinstance(input_cfg, dict):
            raise ValueError(f"Profile '{name}' mode '{mode}' requires an input object")
        if profile.get("requireLiveFlagForInput") is False:
            raise ValueError(
                f"Profile '{name}' cannot disable requireLiveFlagForInput; "
                "all input profiles require the CLI --live flag"
            )
        hold = int(input_cfg.get("holdMilliseconds", 0))
        pulses = int(input_cfg.get("pulseCount", 0))
        max_hold = int(profile.get("maxHoldMilliseconds", 1000))
        max_pulses = int(profile.get("maxPulseCount", 3))
        if hold <= 0 or hold > max_hold:
            raise ValueError(f"Profile '{name}' holdMilliseconds must be 1..{max_hold}")
        if pulses <= 0 or pulses > max_pulses:
            raise ValueError(f"Profile '{name}' pulseCount must be 1..{max_pulses}")
        if not input_cfg.get("key"):
            raise ValueError(f"Profile '{name}' input.key is required")
    elif input_cfg not in (None, {}):
        raise ValueError(f"Profile '{name}' mode '{mode}' must not define live input")

    if int(profile.get("maxAutoRefreshAttempts", 0)) < 0:
        raise ValueError("maxAutoRefreshAttempts cannot be negative")
    return profile
