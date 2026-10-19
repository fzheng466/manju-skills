"""Adaptive compile preview: duration split, ref trim, audio downgrade."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
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


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


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


def _dialogue_spans(job: dict[str, Any]) -> list[tuple[float, float, str]]:
    spans: list[tuple[float, float, str]] = []
    for shot in job.get("shots") or []:
        if not isinstance(shot, dict):
            continue
        for line in shot.get("dialogue") or []:
            if not isinstance(line, dict):
                continue
            start, end = line.get("start_seconds"), line.get("end_seconds")
            if _number(start) and _number(end) and float(end) > float(start):
                spans.append((float(start), float(end), str(line.get("utterance_id") or "")))
    return spans


def _cut_inside_dialogue(t: float, spans: list[tuple[float, float, str]]) -> bool:
    return any(s + 0.05 < t < e - 0.05 for s, e, _ in spans)


def _candidate_cuts(job: dict[str, Any], duration: float) -> list[tuple[float, int, str]]:
    """Priority: 1 dialogue end, 2 收势, 3 existing cut, 4 beat/focus handoff."""
    best: dict[float, tuple[int, str]] = {}

    def add(t: Any, prio: int, kind: str) -> None:
        if not _number(t):
            return
        tt = round(float(t), 3)
        if tt <= 0.05 or tt >= duration - 0.05:
            return
        prev = best.get(tt)
        if prev is None or prio < prev[0]:
            best[tt] = (prio, kind)

    for shot in job.get("shots") or []:
        if not isinstance(shot, dict):
            continue
        add(shot.get("end_seconds"), 3, "shot_cut")
        for line in shot.get("dialogue") or []:
            if isinstance(line, dict):
                add(line.get("end_seconds"), 1, "dialogue_end")
        for beat in shot.get("beats") or []:
            if not isinstance(beat, dict):
                continue
            end = beat.get("end_seconds")
            phase = str(beat.get("action_phase") or beat.get("end_state") or "")
            cut_reason = str(beat.get("cut_reason") or "")
            prio = 4
            kind = "beat"
            if "收势" in phase or phase.lower() in {"hold", "recover", "end"}:
                prio, kind = 2, "recover"
            if cut_reason and cut_reason.lower() not in {"none", "n/a", "无"}:
                prio, kind = min(prio, 3), "cut_reason"
            if beat.get("focus_handoff") or beat.get("focus_transfer"):
                prio, kind = min(prio, 4), "focus"
            add(end, prio, kind)
    return sorted((t, p, k) for t, (p, k) in best.items())


def _equal_splits(duration: float, min_s: float, max_s: float) -> tuple[list[dict[str, Any]], list[str], bool]:
    actions: list[str] = []
    if duration <= max_s + 0.001:
        return [{"start": 0.0, "end": duration or max_s, "fallback": "none"}], actions, False
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
        splits.append({"start": round(t, 3), "end": round(nxt, 3), "fallback": "equal"})
        t = nxt
    actions.append(
        f"R-DUR-01: {duration}s > {max_s}s, equal-split into {k} jobs of ~{piece:.2f}s (no beats; fallback=equal)"
    )
    return splits, actions, False


def _beat_splits(
    duration: float,
    min_s: float,
    max_s: float,
    job: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], bool]:
    actions: list[str] = []
    if duration <= max_s + 0.001:
        return [{"start": 0.0, "end": duration or max_s, "fallback": "none"}], actions, False

    beats = []
    for shot in job.get("shots") or []:
        if isinstance(shot, dict):
            beats.extend([b for b in (shot.get("beats") or []) if isinstance(b, dict)])
    for beat in beats:
        start, end = beat.get("start_seconds"), beat.get("end_seconds")
        if _number(start) and _number(end) and float(end) - float(start) > max_s + 0.001:
            actions.append(
                f"R-DUR-02: beat {start}-{end}s exceeds channel max {max_s}s; return to director notes"
            )
            return [{"start": 0.0, "end": duration}], actions, True

    spans = _dialogue_spans(job)
    candidates = _candidate_cuts(job, duration)
    times = [t for t, _, _ in candidates]
    cuts: list[float] = []
    start = 0.0
    while start + max_s < duration - 0.001:
        lo, hi = start + min_s, start + max_s
        legal = [t for t in times if lo - 0.001 <= t <= hi + 0.001]
        dialogue_blocked = [t for t in legal if _cut_inside_dialogue(t, spans)]
        legal = [t for t in legal if not _cut_inside_dialogue(t, spans)]
        if not legal:
            if dialogue_blocked:
                actions.append("R-DUR-03: only legal cut points fall inside a spoken line; do not split mid-utterance")
                return [{"start": 0.0, "end": duration}], actions, True
            actions.append(
                f"R-DUR-02: no beat/dialogue/cut boundary inside [{lo:.2f},{hi:.2f}] for max {max_s}s"
            )
            return [{"start": 0.0, "end": duration}], actions, True
        cut = max(legal)
        cuts.append(cut)
        start = cut
        if len(cuts) > 40:
            actions.append("R-DUR-02: too many splits")
            return [{"start": 0.0, "end": duration}], actions, True
    if duration - start < min_s - 0.001:
        actions.append(f"R-DUR-04: trailing piece {duration - start:.2f}s < min {min_s}s")
        return [{"start": 0.0, "end": duration}], actions, True
    edges = [0.0, *cuts, duration]
    splits = []
    for i in range(len(edges) - 1):
        splits.append({"start": round(edges[i], 3), "end": round(edges[i + 1], 3), "fallback": "beats"})
    actions.append(
        f"R-DUR-01: {duration}s > {max_s}s, split on beat/dialogue boundaries into {len(splits)} jobs"
    )
    return splits, actions, False


def _legal_splits(
    duration: float,
    min_s: float,
    max_s: float,
    job: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str], bool]:
    job = job or {}
    has_beats = any(
        isinstance(shot, dict) and shot.get("beats")
        for shot in (job.get("shots") or [])
    )
    if has_beats:
        return _beat_splits(duration, min_s, max_s, job)
    return _equal_splits(duration, min_s, max_s)


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
    dur_cap = effective.get("duration_seconds") or {}
    max_s = float(dur_cap.get("max") or duration or 15)
    min_s = float(dur_cap.get("min") or 4)
    allowed = [int(x) for x in (dur_cap.get("allowed") or []) if isinstance(x, (int, float))]
    splits, actions, blocked = _legal_splits(duration, min_s, max_s, job)
    snapped = None
    if allowed and not blocked:
        dur_i = int(round(duration))
        if dur_i not in allowed:
            snap = min((v for v in allowed if v >= dur_i), default=None)
            if snap is None:
                actions.append(f"R-DUR-02: {dur_i}s exceeds channel enum {allowed}; split the job")
                blocked = True
            else:
                snapped = snap
                actions.append(
                    f"R-DUR-03: {job.get('id') or 'job'} {dur_i}s → {snap}s; tell the user and pad the tail with a hold"
                )
    if blocked:
        rule = "R-DUR-02"
        if any(a.startswith("R-DUR-03") for a in actions) and snapped is None:
            rule = "R-DUR-03"
        elif any(a.startswith("R-DUR-04") for a in actions):
            rule = "R-DUR-04"
        return {"blocked": True, "rule": rule, "actions": actions, "splits": splits, "message": actions[-1]}

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
    ref_audio = effective.get("reference_audio") or job.get("reference_audio")
    audio_mode = None
    post_audio = False
    if audio == "unknown":
        actions.append("R-AUD-00: audio capability unknown; ask before compiling dialogue")
        return {
            "blocked": True,
            "rule": "R-AUD-00",
            "actions": actions,
            "splits": splits,
            "kept_references": kept,
            "dropped_references": dropped,
            "audio_post_plan": False,
            "audio_mode": None,
            "snapped_duration": snapped,
            "message": actions[-1],
            "rules_fired": [a.split(":")[0] for a in actions],
        }
    if audio in (None, ""):
        post_audio = True
        audio_mode = "post_dub"
        actions.append("R-AUD-01: strip generated dialogue/music; write audio_post_plan.json")
    if audio == "native":
        if ref_audio in ("forbidden", None, "", "unknown"):
            audio_mode = "native_text_voice"
        else:
            audio_mode = "native_with_ref_audio"
    elif audio == "none":
        audio_mode = "post_dub"
        post_audio = True
        actions.append("R-AUD-01: strip generated dialogue/music; write audio_post_plan.json")
    else:
        audio_mode = "native_text_voice"

    return {
        "blocked": False,
        "track": effective.get("track_id"),
        "actions": actions,
        "splits": splits,
        "kept_references": kept,
        "dropped_references": dropped,
        "audio_post_plan": post_audio,
        "audio_mode": audio_mode,
        "snapped_duration": snapped,
        "rules_fired": [a.split(":")[0] for a in actions],
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Preview adaptive compile for one job")
    p.add_argument("--job", type=Path, required=True, help="JSON file: a job object or {jobs:[...]}")
    p.add_argument("--lock", type=Path, required=True)
    p.add_argument("--job-id", default=None)
    args = p.parse_args()
    raw = json.loads(args.job.read_text(encoding="utf-8"))
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    job = raw
    if isinstance(raw, dict) and "jobs" in raw:
        jobs = raw.get("jobs") or []
        if args.job_id:
            job = next((j for j in jobs if isinstance(j, dict) and j.get("id") == args.job_id), None)
            if job is None:
                print(f"ERROR: job {args.job_id} not found")
                return 2
        else:
            job = jobs[0] if jobs else {}
    from .guards_channel import resolve_effective

    eff = resolve_effective(lock, job if isinstance(job, dict) else {})
    result = preview(job if isinstance(job, dict) else {}, eff)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())
