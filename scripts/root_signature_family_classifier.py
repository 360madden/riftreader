#!/usr/bin/env python3
"""Classify root-signature module-hint sweep hits into structural families."""
from __future__ import annotations

import sys

from rift_live_test.root_signature_family_classifier import main


if __name__ == "__main__":
    sys.exit(main())
