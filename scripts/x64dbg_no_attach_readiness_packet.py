#!/usr/bin/env python3
"""Generate a no-attach x64dbg readiness packet for RIFT."""
from __future__ import annotations

import sys

from rift_live_test.x64dbg_no_attach_readiness_packet import main


if __name__ == "__main__":
    sys.exit(main())
