"""External asset synchronization CLI."""

import sys

if sys.version_info < (3, 11):
    sys.exit(
        "agents: Python 3.11 以降が必要です（現在 "
        f"{sys.version_info.major}.{sys.version_info.minor}）"
    )

from .core import main

__all__ = ["main"]
