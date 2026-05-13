#!/usr/bin/env python3
"""Launch local x64dbg without attaching to RIFT."""
from __future__ import annotations

import sys

from rift_live_test.x64dbg_launcher import main


if __name__ == "__main__":
    sys.exit(main())
