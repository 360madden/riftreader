#!/usr/bin/env python3
"""Sweep live memory for root-signature module-hint occurrences."""
from __future__ import annotations

import sys

from rift_live_test.root_signature_module_hint_sweep import main


if __name__ == "__main__":
    sys.exit(main())
