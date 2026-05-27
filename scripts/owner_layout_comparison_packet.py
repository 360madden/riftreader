#!/usr/bin/env python3
"""Build a no-debug/read-only owner-layout comparison packet."""
from __future__ import annotations

import sys

from rift_live_test.owner_layout_comparison_packet import main


if __name__ == "__main__":
    sys.exit(main())
