#!/usr/bin/env python3
"""Build the current pre-restart baseline packet for actor-yaw Phase 2."""
from __future__ import annotations

import sys

from rift_live_test.actor_yaw_phase2_baseline import main


if __name__ == "__main__":
    sys.exit(main())
