#!/usr/bin/env python3
"""Print a compact status for the current promoted actor-yaw truth."""
from __future__ import annotations

import sys

from rift_live_test.actor_yaw_current_truth_status import main


if __name__ == "__main__":
    sys.exit(main())
