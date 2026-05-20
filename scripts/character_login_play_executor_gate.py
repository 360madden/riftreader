#!/usr/bin/env python3
"""Validate a future approved Play-click MCP executor packet without sending input."""
from __future__ import annotations

import sys

from rift_live_test.character_login_play_executor_gate import main


if __name__ == "__main__":
    sys.exit(main())
