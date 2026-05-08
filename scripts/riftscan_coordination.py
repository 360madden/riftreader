#!/usr/bin/env python3
"""Read-only RiftScan -> RiftReader coordination plan CLI."""
from __future__ import annotations

import sys

from rift_live_test.riftscan_coordination import main


if __name__ == "__main__":
    sys.exit(main())
