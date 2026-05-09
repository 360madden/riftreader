#!/usr/bin/env python3
"""Build a current-session waypoint route from observed forward movement."""
from __future__ import annotations

import sys

from rift_live_test.observed_forward_route import main


if __name__ == "__main__":
    sys.exit(main())
