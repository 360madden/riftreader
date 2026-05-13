#!/usr/bin/env python3
"""Run read-only pointer owner/ref-storage neighborhood inspection."""
from __future__ import annotations

import sys

from rift_live_test.pointer_owner_neighborhood_inspector import main


if __name__ == "__main__":
    sys.exit(main())
