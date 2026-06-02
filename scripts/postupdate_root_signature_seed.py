#!/usr/bin/env python3
"""Build a candidate-only post-update root-signature seed from owner-batch evidence."""
from __future__ import annotations

import sys

from rift_live_test.postupdate_root_signature_seed import main


if __name__ == "__main__":
    sys.exit(main())
