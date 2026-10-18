"""Fail closed when a 9:16 scene derivative moves world anchors off the 16:9 master."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

_OBJECTS = r"(路灯杆|茶几|藤椅|编织袋|父母房门|房门|垃圾桶|月季)"
_SIDES = r"(左侧|右侧|中轴|中央|左下|右下|上半|下半|左三分之一|右三分之一)"
ANCHOR_RE = re.compile(rf"{_OBJECTS}.{{0,32}}{_SIDES}|{_SIDES}.{{0,24}}{_OBJECTS}")


def anchors(text: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for match in ANCHOR_RE.finditer(text or ""):
        obj = match.group(1) or match.group(4)
        side = match.group(2) or match.group(3)
        if obj and side:
            out.setdefault(obj, set()).add(side)
    return out


def compare_pair(landscape: str, portrait: str, *, scene_id: str = "SCENE") -> list[str]:
    errors: list[str] = []
    left = anchors(landscape)
    right = anchors(portrait)
    for name, sides in left.items():
        other = right.get(name)
        if not other:
            continue
        if sides.isdisjoint(other) and other:
            errors.append(
                f"ASPECT-SYNC: {scene_id} anchor {name!r} L={sorted(sides)} P={sorted(other)}"
            )
    return errors


def main() -> int:
    p = argparse.ArgumentParser(description="Compare 16:9 / 9:16 scene anchor sides")
    p.add_argument("--landscape", type=Path, required=True)
    p.add_argument("--portrait", type=Path, required=True)
    p.add_argument("--scene-id", default="SCENE")
    args = p.parse_args()
    errors = compare_pair(
        args.landscape.read_text(encoding="utf-8"),
        args.portrait.read_text(encoding="utf-8"),
        scene_id=args.scene_id,
    )
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print("PASS: aspect anchors aligned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
