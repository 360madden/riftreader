#!/usr/bin/env python3
"""Capture and gate a no-input proof pose after the operator manually moved the player."""
from __future__ import annotations

import sys

from rift_live_test.manual_displacement_capture import main


if __name__ == "__main__":
    sys.exit(main())
