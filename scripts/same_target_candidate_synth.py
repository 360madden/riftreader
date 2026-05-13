#!/usr/bin/env python3
"""Synthesize importable same-target candidate files from current-PID readback evidence."""
from __future__ import annotations

import sys

from rift_live_test.same_target_candidate_synth import main


if __name__ == "__main__":
    sys.exit(main())
