#!/usr/bin/env python3
"""Read-only no-attach x64dbg target preflight for RIFT."""
from __future__ import annotations

import sys

from rift_live_test.x64dbg_preflight import main


if __name__ == "__main__":
    sys.exit(main())
