"""Adaptive compile preview: duration split, ref trim, audio downgrade."""
from __future__ import annotations

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


def preview(job: dict[str, Any], effective: dict[str, Any]) -> dict[str, Any]:
    duration = float(job.get("duration_seconds") or 0)
    max_s = float((effective.get("duration_seconds") or {}).get("max") or duration or 15)
    min_s = float((effective.get("duration_seconds") or {}).get("min") or 4)
    actions: list[str] = []
    splits: list[dict[str, Any]] = []

    if duration > max_s:
        n = int((duration + max_s - 0.01) // max_s)
        actions.append(f"R-DUR-01: {duration}s > {max_s}s, split into ~{n} jobs at beat/line boundaries")
        remain = duration
        start = 0.0
        while remain > max_s:
            piece = max_s
            splits.append({"start": start, "end": start + piece})
            start += piece
            remain -= piece
        if remain:
            if remain < min_s:
                actions.append("R-DUR-04: last piece shorter than min; merge or hold end-state")
            splits.append({"start": start, "end": start + remain})
    else:
        splits.append({"start": 0.0, "end": duration or max_s})

    conflict = effective.get("conflict")
    if conflict and conflict.get("type") == "aspect_ratio":
        return {
            "blocked": True,
            "rule": "R-AR-01",
            "message": f"project {conflict.get('project')} not in channel {conflict.get('channel')}",
            "choices": ["switch_channel", "reproject_aspect", "vertical_derivative"],
            "actions": actions,
            "splits": splits,
        }

    refs = list(job.get("references") or [])
    img_cap = (effective.get("reference_inputs") or {}).get("image")
    dropped: list[Any] = []
    kept = refs
    if isinstance(img_cap, int) and len(refs) > img_cap:
        kept, dropped = refs[:img_cap], refs[img_cap:]
        actions.append(f"R-REF-01: keep {img_cap} refs by asset priority, drop {len(dropped)}")

    audio = effective.get("audio_output")
    post_audio = False
    if audio in ("none", "unknown"):
        post_audio = True
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
