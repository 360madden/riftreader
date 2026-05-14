#!/usr/bin/env python3
"""Summarize whether existing reference artifacts are fresh enough for proof promotion."""
from __future__ import annotations

import sys

from rift_live_test.reference_freshness_watchdog import main


if __name__ == "__main__":
    sys.exit(main())
