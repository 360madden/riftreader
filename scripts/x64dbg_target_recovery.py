#!/usr/bin/env python3
"""Inspect and clean debugger remnants for an exact RIFT target after x64dbg work."""
from __future__ import annotations

import sys

from rift_live_test.x64dbg_target_recovery import main


if __name__ == "__main__":
    sys.exit(main())
