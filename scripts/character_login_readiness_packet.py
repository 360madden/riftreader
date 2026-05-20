#!/usr/bin/env python3
"""Build an input-free readiness packet for character login/relogin automation."""
from __future__ import annotations

import sys

from rift_live_test.character_login_readiness_packet import main


if __name__ == "__main__":
    sys.exit(main())
