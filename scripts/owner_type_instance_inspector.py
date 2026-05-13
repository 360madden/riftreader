#!/usr/bin/env python3
"""Run read-only owner/type-marker instance inspection."""
from __future__ import annotations

import sys

from rift_live_test.owner_type_instance_inspector import main


if __name__ == "__main__":
    sys.exit(main())
