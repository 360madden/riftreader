#!/usr/bin/env python3
"""Fail-closed gate before coordinate proof/readback or movement."""
from __future__ import annotations

import sys

from rift_live_test.coordinate_proof_readiness_gate import main


if __name__ == "__main__":
    sys.exit(main())
