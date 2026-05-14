#!/usr/bin/env python3
"""Diagnose existing RRAPICOORD scan artifacts without live actions."""
from __future__ import annotations

import sys

from rift_live_test.rrapicoord_scan_diagnostics import main


if __name__ == "__main__":
    sys.exit(main())
