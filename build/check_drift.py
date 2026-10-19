#!/usr/bin/env python3
"""Fail if skill-*/_core or core.lock drifted from core/."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"


def shared_blocks(text: str) -> dict[str, str]:
    return {
        m.group(1): m.group(2)
        for m in re.finditer(r"<!-- shared:(\w+) -->(.*?)<!-- /shared:\1 -->", text, re.S)
    }


def compare_shared(a_text: str, b_text: str) -> list[str]:
    """Both SKILL.md files must carry byte-identical shared blocks."""
    a, b = shared_blocks(a_text), shared_blocks(b_text)
    errors = []
    for key in sorted(set(a) | set(b)):
        if key not in a:
            errors.append(f"DRIFT shared:{key} missing in skill-H3")
        elif key not in b:
            errors.append(f"DRIFT shared:{key} missing in skill-SD")
        elif a[key].strip() != b[key].strip():
            errors.append(f"DRIFT shared:{key}")
    return errors


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
    for message in compare_shared(
        (ROOT / "skill-H3" / "SKILL.md").read_text(encoding="utf-8"),
        (ROOT / "skill-SD" / "SKILL.md").read_text(encoding="utf-8"),
    ):
        print(message)
        errors += 1
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
