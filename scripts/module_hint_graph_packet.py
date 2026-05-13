#!/usr/bin/env python3
"""Build an offline graph packet for a module hint -> owner -> coord pointer chain."""
from __future__ import annotations

import sys

from rift_live_test.module_hint_graph_packet import main


if __name__ == "__main__":
    sys.exit(main())
