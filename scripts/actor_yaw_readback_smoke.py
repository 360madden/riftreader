#!/usr/bin/env python3
"""Run a no-input live readback smoke for promoted actor-yaw truth."""
from __future__ import annotations

import sys

from rift_live_test.actor_yaw_readback_smoke import main


if __name__ == "__main__":
    sys.exit(main())
