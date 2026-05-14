#!/usr/bin/env python3
"""Read-only diagnostic for the RiftReaderApiProbe addon install/runtime marker state."""
from __future__ import annotations

import sys

from rift_live_test.rrapicoord_addon_state_diagnostics import main


if __name__ == "__main__":
    sys.exit(main())
