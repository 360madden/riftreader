#!/usr/bin/env python3
"""Run no-input character-login supervision checks and emit one packet."""
from __future__ import annotations

import sys

from rift_live_test.character_login_supervisor import main


if __name__ == "__main__":
    sys.exit(main())
