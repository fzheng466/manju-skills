#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT))
try:
    from core.lib.identity import main
except ImportError:
    from _core.lib.identity import main  # type: ignore

if __name__ == "__main__":
    raise SystemExit(main())
