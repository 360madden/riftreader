#!/usr/bin/env python3
"""Rank owner objects by module-field and coord-pointer structural signatures."""
from __future__ import annotations

import sys

from rift_live_test.owner_structural_signature_packet import main


if __name__ == "__main__":
    sys.exit(main())
