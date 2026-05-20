#!/usr/bin/env python3
"""Build a character-select automation environment summary from a fresh screenshot."""
from __future__ import annotations

import sys

from rift_live_test.character_select_environment_capture import main


if __name__ == "__main__":
    sys.exit(main())
