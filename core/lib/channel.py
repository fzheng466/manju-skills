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


def project_tracks(project: dict[str, Any] | None) -> list[dict[str, str]]:
    if not project:
        return [{"track_id": "L", "aspect": str(project.get("aspect_ratio") if project else "16:9")}]
    dels = project.get("deliverables")
    if isinstance(dels, list) and dels:
        out = []
        for d in dels:
            if isinstance(d, dict) and d.get("aspect"):
                out.append({"track_id": str(d.get("track_id") or d["aspect"]), "aspect": str(d["aspect"])})
        if out:
            return out
    ar = project.get("aspect_ratio") or "16:9"
    return [{"track_id": "L" if ar == "16:9" else "P", "aspect": str(ar)}]


def _strictest_int(a: Any, b: Any, how: str = "min") -> int | None:
    nums = [int(x) for x in (a, b) if isinstance(x, (int, float)) and not isinstance(x, bool)]
    if not nums:
        return None
    return min(nums) if how == "min" else max(nums)


def _as_set(value: Any) -> set[str]:
    if isinstance(value, dict) and "value" in value:
        value = value["value"]
    if value in (None, "unknown"):
        return set()
    if isinstance(value, (list, set, tuple)):
        return {str(x) for x in value}
    if isinstance(value, str):
        return {value}
    return set()


def merge_effective(
    baseline: dict[str, Any],
    channel_model: dict[str, Any],
    project: dict[str, Any] | None = None,
    track: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Intersection for one deliverable track. Channel cannot exceed model baseline."""
    caps = (channel_model or {}).get("capabilities") or {}
    b_dur = baseline.get("duration_seconds") or {}
    c_dur = (caps.get("duration_seconds") or {}).get("value") or {}
    max_s = _strictest_int(b_dur.get("max"), c_dur.get("max"), "min")
    min_s = _strictest_int(b_dur.get("min"), c_dur.get("min"), "max") or b_dur.get("min") or 4

    b_ref = baseline.get("reference_inputs") or {}
    c_ref = (caps.get("reference_inputs") or {}).get("value") or {}
    images = _strictest_int(b_ref.get("image"), c_ref.get("image"), "min")
    videos = _strictest_int(b_ref.get("video"), c_ref.get("video"), "min")
    audios = _strictest_int(b_ref.get("audio"), c_ref.get("audio"), "min")
    totals = _strictest_int(b_ref.get("total"), c_ref.get("total"), "min")
    if images == 0:
        videos = 0 if videos is None else min(videos, 0)
        audios = 0 if audios is None else min(audios, 0)

    b_ar = _as_set(baseline.get("aspect_ratios"))
    c_raw = caps.get("aspect_ratios")
    channel_unknown = False
    if isinstance(c_raw, dict) and c_raw.get("status") == "unknown":
        channel_unknown = True
        c_ar = b_ar
    else:
        c_ar = _as_set(c_raw) or b_ar
    supported = sorted(b_ar & c_ar) if (b_ar and c_ar) else sorted(b_ar or c_ar)

    tr = track or (project_tracks(project)[0] if project else {"track_id": "L", "aspect": "16:9"})
    track_aspect = tr.get("aspect") or "16:9"
    conflict = None
    status = "ok"
    if channel_unknown:
        status = "unverified"
    elif track_aspect not in supported:
        status = "unsupported_by_channel"
        conflict = {
            "type": "aspect_ratio",
            "track_id": tr.get("track_id"),
            "project": track_aspect,
            "channel": supported,
        }

    audio = (caps.get("audio_output") or {}).get("value") or baseline.get("audio_output") or "unknown"
    b_modes = set(baseline.get("modes") or [])
    c_modes = _as_set(caps.get("modes")) or b_modes
    modes = sorted(b_modes & c_modes) if c_modes else sorted(b_modes)
    if (images == 0) or (totals == 0):
        modes = [m for m in modes if m not in {"Ref2VA", "reference_set", "reference_image", "multimodal_reference"}]

    return {
        "track_id": tr.get("track_id"),
        "aspect": track_aspect,
        "status": status,
        "duration_seconds": {
            "min": min_s,
            "max": max_s,
            "integer_only": bool(c_dur.get("integer_only") or b_dur.get("integer_only")),
        },
        "aspect_ratios": supported,
        "reference_inputs": {
            "image": images,
            "video": videos,
            "audio": audios,
            "total": totals,
        },
        "audio_output": audio,
        "modes": modes,
        "conflict": conflict,
    }
