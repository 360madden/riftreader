#!/usr/bin/env python3
"""Aggregate priority classifier windows and pointer scans into an exhaustion report."""
from __future__ import annotations

import sys

from rift_live_test.priority_scan_exhaustion_report import main


if __name__ == "__main__":
    sys.exit(main())
