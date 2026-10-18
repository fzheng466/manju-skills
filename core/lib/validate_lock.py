"""Helpers for skill validators to consume an effective-capability lock."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def add_core_to_path(skill_root: Path) -> None:
    repo = skill_root.parent
    for cand in (skill_root / "_core", repo / "core"):
        parent = cand.parent
        if (cand / "lib").is_dir() and str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
            return


def load_lock(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def check_jobs_against_lock(jobs: list[Any], lock: dict[str, Any], prompt_reader) -> list[str]:
    from core.lib.guards_channel import check  # type: ignore
    from _core.lib.guards_channel import check as check_vendored  # type: ignore
    fn = check if "core" in sys.modules else check_vendored
    errors: list[str] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        text = ""
        try:
            text = prompt_reader(job) or ""
        except Exception:
            text = ""
        errors.extend(fn(text, job, lock))
    return errors
