#!/usr/bin/env python3
"""Compare existing coordinate candidates against a fresh API reference."""
from __future__ import annotations

import sys

from rift_live_test.coordinate_candidate_compare import main


if __name__ == "__main__":
    sys.exit(main())
