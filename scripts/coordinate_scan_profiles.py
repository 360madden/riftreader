#!/usr/bin/env python3
"""Run repeatable no-input coordinate family scan profiles."""
from __future__ import annotations

import sys

from rift_live_test.coordinate_scan_profiles import main


if __name__ == "__main__":
    sys.exit(main())
