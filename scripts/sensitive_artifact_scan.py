#!/usr/bin/env python3
"""Scan staged/working RiftReader artifacts for sensitive values."""
from __future__ import annotations

import sys

from rift_live_test.sensitive_artifact_scan import main


if __name__ == "__main__":
    sys.exit(main())
