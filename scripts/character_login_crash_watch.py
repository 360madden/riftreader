#!/usr/bin/env python3
"""Observe RIFT character-login crash/relogin state without live input."""
from __future__ import annotations

import sys

from rift_live_test.character_login_crash_watch import main


if __name__ == "__main__":
    sys.exit(main())
