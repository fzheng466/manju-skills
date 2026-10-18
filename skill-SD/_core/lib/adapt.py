"""Adaptive compile preview: duration split, ref trim, audio downgrade."""
from __future__ import annotations

import math
from typing import Any

REF_PRIORITY = (
    "frame_anchor",
    "primary_speaker_board",
    "other_visible_board",
    "held_prop",
    "scene_board",
    "idle_prop",
    "style_ref",
)


def _priority_index(ref: Any) -> int:
    if isinstance(ref, dict):
        role = str(ref.get("role") or ref.get("priority") or "")
        if role in REF_PRIORITY:
            return REF_PRIORITY.index(role)
        kind = str(ref.get("kind") or "")
        if kind == "character":
            return 1
        if kind == "scene":
            return 4
        if kind == "prop":
            return 5
    return 99


def _legal_splits(duration: float, min_s: float, max_s: float) -> tuple[list[dict[str, Any]], list[str], bool]:
    actions: list[str] = []
    if duration <= max_s + 0.001:
        return [{"start": 0.0, "end": duration or max_s}], actions, False
    k_min = int(math.ceil(duration / max_s - 1e-9))
    k_max = int(math.floor(duration / min_s + 1e-9)) if min_s else k_min
    if k_min > k_max or k_min < 1:
        actions.append(f"R-DUR-02: {duration}s cannot be split into pieces inside [{min_s},{max_s}]")
        return [{"start": 0.0, "end": duration}], actions, True
    k = k_min
    piece = duration / k
    splits = []
    t = 0.0
    for i in range(k):
        nxt = duration if i == k - 1 else t + piece
        splits.append({"start": round(t, 3), "end": round(nxt, 3)})
        t = nxt
    actions.append(f"R-DUR-01: {duration}s > {max_s}s, split into {k} jobs of ~{piece:.2f}s (legal [{min_s},{max_s}])")
    return splits, actions, False


def preview(job: dict[str, Any], effective: dict[str, Any]) -> dict[str, Any]:
    conflict = effective.get("conflict")
    status = effective.get("status")
    if status == "unsupported_by_channel" or (conflict and conflict.get("type") == "aspect_ratio"):
        return {
            "blocked": True,
            "track": effective.get("track_id"),
            "rule": "R-AR-01",
            "message": f"track {effective.get('track_id')} aspect {effective.get('aspect')} not in channel {conflict.get('channel') if conflict else []}",
            "choices": ["switch_channel", "wait", "derivative"],
            "actions": ["R-AR-01: pause this track only; other tracks continue"],
            "splits": [],
        }

    duration = float(job.get("duration_seconds") or 0)
    max_s = float((effective.get("duration_seconds") or {}).get("max") or duration or 15)
    min_s = float((effective.get("duration_seconds") or {}).get("min") or 4)
    splits, actions, blocked = _legal_splits(duration, min_s, max_s)
    if blocked:
        return {"blocked": True, "rule": "R-DUR-02", "actions": actions, "splits": splits, "message": actions[-1]}

    refs = list(job.get("references") or [])
    img_cap = (effective.get("reference_inputs") or {}).get("image")
    dropped: list[Any] = []
    kept = refs
    if isinstance(img_cap, int) and len(refs) > img_cap:
        ordered = sorted(range(len(refs)), key=lambda i: (_priority_index(refs[i]), i))
        keep_idx = set(ordered[:img_cap])
        kept = [refs[i] for i in range(len(refs)) if i in keep_idx]
        dropped = [refs[i] for i in range(len(refs)) if i not in keep_idx]
        actions.append(f"R-REF-01: keep {img_cap} refs by REF_PRIORITY, drop {len(dropped)}")

    audio = effective.get("audio_output")
    post_audio = audio in ("none", "unknown")
    if post_audio:
        actions.append("R-AUD-01: strip generated dialogue/music; write audio_post_plan.json")

    return {
        "blocked": False,
        "actions": actions,
        "splits": splits,
        "kept_references": kept,
        "dropped_references": dropped,
        "audio_post_plan": post_audio,
        "rules_fired": [a.split(":")[0] for a in actions],
    }
