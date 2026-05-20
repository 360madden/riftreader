#!/usr/bin/env python3
"""Create a dry-run plan for RIFT character-select automation."""
from __future__ import annotations

import sys

from rift_live_test.character_select_automation_plan import main


if __name__ == "__main__":
    sys.exit(main())
