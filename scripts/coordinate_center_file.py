#!/usr/bin/env python3
"""Generate coordinate scan centers from existing candidate evidence."""
from __future__ import annotations

import sys

from rift_live_test.coordinate_center_file import main


if __name__ == "__main__":
    sys.exit(main())
