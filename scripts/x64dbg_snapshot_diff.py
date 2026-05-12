#!/usr/bin/env python3
"""Read-only x64dbg snapshot/diff helper with RiftReader safety gates."""
from __future__ import annotations

import sys

from rift_live_test.x64dbg_snapshot_diff import main


if __name__ == "__main__":
    sys.exit(main())
