#!/usr/bin/env python3
"""Build an offline static-chain work packet from x64dbg code leads."""
from __future__ import annotations

import sys

from rift_live_test.x64dbg_static_lead_packet import main


if __name__ == "__main__":
    sys.exit(main())
