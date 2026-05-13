#!/usr/bin/env python3
"""Generate a fillable x64dbg manual access-event template."""
from __future__ import annotations

import sys

from rift_live_test.x64dbg_access_event_template import main


if __name__ == "__main__":
    sys.exit(main())
