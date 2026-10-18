#!/usr/bin/env python3
"""Fail if skill-*/_core or core.lock drifted from core/."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def core_files() -> dict[str, str]:
    out = {}
    for p in CORE.rglob("*"):
        if not p.is_file():
            continue
        if "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        out[str(p.relative_to(CORE)).replace("\\", "/")] = sha(p)
    return out


def main() -> int:
    files = core_files()
    errors = 0
    for skill in (ROOT / "skill-H3", ROOT / "skill-SD"):
        lock = json.loads((skill / "core.lock").read_text(encoding="utf-8"))
        locked = lock.get("files") or {}
        if locked != files:
            print(f"DRIFT: {skill.name}/core.lock does not match core/")
            errors += 1
        dest = skill / "_core"
        for rel, digest in files.items():
            p = dest / rel
            if not p.is_file():
                print(f"MISSING: {skill.name}/_core/{rel}")
                errors += 1
                continue
            if sha(p) != digest:
                print(f"DRIFT: {skill.name}/_core/{rel}")
                errors += 1
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
