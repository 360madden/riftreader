#!/usr/bin/env python3
"""Run the no-input live visual gate before any Rift movement/input."""
from __future__ import annotations

import sys

from rift_live_test.visual_gate_status import main


if __name__ == "__main__":
    sys.exit(main())
