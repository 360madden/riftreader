#!/usr/bin/env python3
"""Resolve an x64dbg-derived static coord chain candidate without x64dbg."""
from __future__ import annotations

import sys

from rift_live_test.x64dbg_static_chain_resolve import main


if __name__ == "__main__":
    sys.exit(main())
