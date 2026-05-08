#!/usr/bin/env python3
"""Validate the current promoted actor-yaw disambiguation truth packet."""
from __future__ import annotations

import sys

from rift_live_test.actor_yaw_disambiguation_validation import main


if __name__ == "__main__":
    sys.exit(main())
