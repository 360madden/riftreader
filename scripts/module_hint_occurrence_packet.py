#!/usr/bin/env python3
"""Build an offline occurrence packet for module-pointer RVA hints."""
from __future__ import annotations

import sys

from rift_live_test.module_hint_occurrence_packet import main


if __name__ == "__main__":
    sys.exit(main())
