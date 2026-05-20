#!/usr/bin/env python3
"""Classify a RIFT character-login screenshot without sending input."""
from __future__ import annotations

import sys

from rift_live_test.character_login_screen_state import main


if __name__ == "__main__":
    sys.exit(main())
