#!/usr/bin/env python3
"""Run the no-CE/read-only RiftScan coordination validation suite."""
from __future__ import annotations

import sys

from rift_live_test.riftscan_validation import main


if __name__ == "__main__":
    sys.exit(main())
