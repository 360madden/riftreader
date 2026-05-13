#!/usr/bin/env python3
"""Run read-only grouped pointer-family scans for current-process coordinate leads."""
from __future__ import annotations

import sys

from rift_live_test.pointer_family_scan import main


if __name__ == "__main__":
    sys.exit(main())
