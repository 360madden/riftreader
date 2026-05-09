#!/usr/bin/env python3
# Version: riftreader-check-live-visual-gate-target-control-v0.2.0
# Total-Character-Count: 405
# Purpose: Thin CLI entrypoint for running target-control first and then the no-input visual gate.

from __future__ import annotations

import sys

from rift_live_test.visual_gate_with_target_control import main


if __name__ == "__main__":
    sys.exit(main())

# END_OF_SCRIPT_MARKER
