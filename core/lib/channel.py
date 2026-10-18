"""Channel profiles, TTL, and three-layer capability merge."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def manju_home() -> Path:
    return Path(os.environ.get("MANJU_HOME") or (Path.home() / ".manju"))


def channels_dir() -> Path:
    d = manju_home() / "channels"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_channel(channel_id: str) -> dict[str, Any] | None:
    p = channels_dir() / f"{channel_id}.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_channel(profile: dict[str, Any]) -> Path:
    cid = profile["channel_id"]
    dest = channels_dir() / f"{cid}.json"
    hist = channels_dir() / "_history" / cid
    hist.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if dest.exists():
        (hist / f"{stamp}.json").write_text(dest.read_text(encoding="utf-8"), encoding="utf-8")
    profile["updated_at"] = datetime.now(timezone.utc).isoformat()
    dest.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return dest


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strictest_int(a: int | None, b: int | None, how: str = "min") -> int | None:
    nums = [x for x in (a, b) if isinstance(x, int)]
    if not nums:
        return None
    return min(nums) if how == "min" else max(nums)


def merge_effective(
    baseline: dict[str, Any],
    channel_model: dict[str, Any],
    project: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Intersection: channel cannot exceed model baseline."""
    caps = (channel_model or {}).get("capabilities") or {}
    b_dur = baseline.get("duration_seconds") or {}
    c_dur = (caps.get("duration_seconds") or {}).get("value") or {}
    max_s = _strictest_int(b_dur.get("max"), c_dur.get("max"), "min")
    min_s = _strictest_int(b_dur.get("min"), c_dur.get("min"), "max") or b_dur.get("min") or 4

    b_ref = baseline.get("reference_inputs") or {}
    c_ref = (caps.get("reference_inputs") or {}).get("value") or {}
    images = _strictest_int(b_ref.get("image"), c_ref.get("image"), "min")

    b_ar = set(baseline.get("aspect_ratios") or [])
    c_ar = set((caps.get("aspect_ratios") or {}).get("value") or caps.get("aspect_ratios") or b_ar)
    if isinstance(c_ar, list):
        c_ar = set(c_ar)
    aspects = sorted(b_ar & c_ar) if c_ar else sorted(b_ar)
    proj_ar = (project or {}).get("aspect_ratio")
    if proj_ar and aspects and proj_ar not in aspects:
        conflict = {"type": "aspect_ratio", "project": proj_ar, "channel": aspects}

    else:
        conflict = None

    audio = (caps.get("audio_output") or {}).get("value") or baseline.get("audio_output") or "unknown"

    return {
        "duration_seconds": {"min": min_s, "max": max_s, "integer_only": bool(c_dur.get("integer_only") or b_dur.get("integer_only"))},
        "aspect_ratios": aspects,
        "reference_inputs": {
            "image": images,
            "video": _strictest_int(b_ref.get("video"), c_ref.get("video"), "min"),
            "audio": _strictest_int(b_ref.get("audio"), c_ref.get("audio"), "min"),
        },
        "audio_output": audio,
        "modes": sorted(set(baseline.get("modes") or []) & set((caps.get("modes") or {}).get("value") or baseline.get("modes") or [])),
        "conflict": conflict,
    }
