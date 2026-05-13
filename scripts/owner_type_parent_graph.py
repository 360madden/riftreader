#!/usr/bin/env python3
"""Summarize owner/type instance parent refs from offline artifacts."""
from __future__ import annotations

import sys

from rift_live_test.owner_type_parent_graph import main


if __name__ == "__main__":
    sys.exit(main())
