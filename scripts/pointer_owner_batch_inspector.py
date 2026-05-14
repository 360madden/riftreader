#!/usr/bin/env python3
"""Batch read-only owner/ref-storage inspection from a pointer-family scan."""
from __future__ import annotations

import sys

from rift_live_test.pointer_owner_batch_inspector import main


if __name__ == "__main__":
    sys.exit(main())
