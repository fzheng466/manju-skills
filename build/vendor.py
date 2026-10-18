#!/usr/bin/env python3
"""Copy core/ into each skill as _core and write core.lock (sha256 per file)."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
SKILLS = [ROOT / "skill-H3", ROOT / "skill-SD"]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    files = [p for p in CORE.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    lock = {
        "core_version": (CORE / "VERSION").read_text(encoding="utf-8").strip(),
        "files": {str(p.relative_to(CORE)).replace("\\", "/"): sha256(p) for p in files},
    }
    for skill in SKILLS:
        dest = skill / "_core"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(CORE, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (skill / "core.lock").write_text(json.dumps(lock, indent=2), encoding="utf-8")
        print(f"vendored {len(files)} files -> {dest}")


if __name__ == "__main__":
    main()
