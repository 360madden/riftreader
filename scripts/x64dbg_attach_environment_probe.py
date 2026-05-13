#!/usr/bin/env python3
"""No-attach x64dbg environment probe for RIFT attach readiness."""
from __future__ import annotations

import sys

from rift_live_test.x64dbg_attach_environment_probe import main


if __name__ == "__main__":
    sys.exit(main())
