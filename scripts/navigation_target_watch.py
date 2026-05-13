#!/usr/bin/env python3
"""Passively watch for the RIFT navigation target without sending input."""
from __future__ import annotations

import sys

from rift_live_test.navigation_target_watch import main


if __name__ == "__main__":
    sys.exit(main())
