#!/usr/bin/env python3
"""Check baseline/displaced coordinate reference readiness."""

from __future__ import annotations

import sys

from rift_live_test.coordinate_displaced_reference_readiness import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
