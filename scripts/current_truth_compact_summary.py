#!/usr/bin/env python3
"""Write a timestamped compact RiftReader current-truth summary."""
from __future__ import annotations

import sys

from rift_live_test.current_truth_compact_summary import main


if __name__ == "__main__":
    sys.exit(main())
