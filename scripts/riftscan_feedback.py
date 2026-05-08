#!/usr/bin/env python3
"""RiftReader-owned read-only RiftScan feedback packet CLI."""
from __future__ import annotations

import sys

from rift_live_test.riftscan_feedback import main


if __name__ == "__main__":
    sys.exit(main())
