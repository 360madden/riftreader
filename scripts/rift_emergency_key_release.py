#!/usr/bin/env python3
"""CLI wrapper for the emergency key-release helper."""
from __future__ import annotations

import sys

from rift_live_test.emergency_key_release import main


if __name__ == "__main__":
    sys.exit(main())
