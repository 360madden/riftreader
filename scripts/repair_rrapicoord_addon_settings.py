#!/usr/bin/env python3
"""Enable RiftReaderApiProbe in RIFT AddonSettings with backups."""
from __future__ import annotations

import sys

from rift_live_test.repair_rrapicoord_addon_settings import main


if __name__ == "__main__":
    sys.exit(main())
