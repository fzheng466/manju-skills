"""Write and load effective-capability.lock.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .channel import file_hash, merge_effective


def compute_lock(
    *,
    channel_id: str,
    model_profile: str,
    baseline: dict[str, Any],
    channel_model: dict[str, Any],
    project: dict[str, Any] | None = None,
    baseline_path: Path | None = None,
    channel_path: Path | None = None,
    project_path: Path | None = None,
) -> dict[str, Any]:
    effective = merge_effective(baseline, channel_model, project)
    return {
        "channel_id": channel_id,
        "model_profile": model_profile,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "effective": effective,
        "sources": {
            "baseline_hash": file_hash(baseline_path) if baseline_path and baseline_path.is_file() else None,
            "channel_hash": file_hash(channel_path) if channel_path and channel_path.is_file() else None,
            "project_hash": file_hash(project_path) if project_path and project_path.is_file() else None,
        },
    }


def write_lock(path: Path, lock: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_lock(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
