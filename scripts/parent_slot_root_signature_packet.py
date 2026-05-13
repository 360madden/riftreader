#!/usr/bin/env python3
"""Build a root-search signature packet from parent-slot/container evidence."""
from __future__ import annotations

import sys

from rift_live_test.parent_slot_root_signature_packet import main


if __name__ == "__main__":
    sys.exit(main())
