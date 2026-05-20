#!/usr/bin/env python3
"""Build a defensive dry-run plan for character login/relogin automation."""
from __future__ import annotations

import sys

from rift_live_test.character_login_resilience_plan import main


if __name__ == "__main__":
    sys.exit(main())
