#!/usr/bin/env python3
"""Compare candidate readback summaries offline for repeat-stable families."""
from __future__ import annotations

import sys

from rift_live_test.candidate_readback_stability import main


if __name__ == "__main__":
    sys.exit(main())
