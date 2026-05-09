#!/usr/bin/env python3
# Version: riftreader-check-target-control-v0.1.2
# Total-Character-Count: 357
# Purpose: Thin CLI entrypoint for the no-input RiftReader target-control preflight.

from __future__ import annotations

import sys

from rift_live_test.target_control import main


if __name__ == "__main__":
    sys.exit(main())

# END_OF_SCRIPT_MARKER
