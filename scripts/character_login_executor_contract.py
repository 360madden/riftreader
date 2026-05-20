#!/usr/bin/env python3
"""Validate the gated contract for a future character-login executor."""
from __future__ import annotations

import sys

from rift_live_test.character_login_executor_contract import main


if __name__ == "__main__":
    sys.exit(main())
