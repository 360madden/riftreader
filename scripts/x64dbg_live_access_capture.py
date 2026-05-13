#!/usr/bin/env python3
"""Run a bounded live x64dbg capture for a top-ranked coordinate candidate."""
from __future__ import annotations

import sys

from rift_live_test.x64dbg_live_access_capture import main


if __name__ == "__main__":
    sys.exit(main())
