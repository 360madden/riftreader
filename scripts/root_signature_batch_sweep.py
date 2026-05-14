#!/usr/bin/env python3
"""Run read-only root-signature sweeps from an owner-batch summary."""
from __future__ import annotations

import sys

from rift_live_test.root_signature_batch_sweep import main


if __name__ == "__main__":
    sys.exit(main())
