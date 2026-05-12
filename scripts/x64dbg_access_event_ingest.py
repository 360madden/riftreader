#!/usr/bin/env python3
"""Ingest manual x64dbg access events into a candidate-only coord-chain packet."""
from __future__ import annotations

import sys

from rift_live_test.x64dbg_access_event_ingest import main


if __name__ == "__main__":
    sys.exit(main())
