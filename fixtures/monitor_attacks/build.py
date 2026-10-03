"""Regenerate this directory from results/v2_* (same as `python -m eval.monitor_attacks --build`)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from eval.monitor_attacks import build  # noqa: E402

if __name__ == "__main__":
    for name in build():
        print(name)
