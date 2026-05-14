#!/usr/bin/env python3
"""Validate RiftReader's compact current-truth JSON contract."""
from __future__ import annotations

import sys

from rift_live_test.current_truth_validator import main


if __name__ == "__main__":
    sys.exit(main())
