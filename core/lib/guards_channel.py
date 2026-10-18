"""G-CH checks against the effective capability lock."""
from __future__ import annotations

import re
from typing import Any, Callable

# H3: At 00:03.500  = 3.5 seconds into the job (MM:SS.mmm, minutes then seconds)
AT_RE = re.compile(r"At\s+(\d{1,2}):(\d{2}(?:\.\d+)?)", re.I)
# Seedance / interval: [0s-4s] or [0.0s-4.0s]
BRACKET_RE = re.compile(r"\[(\d+(?:\.\d+)?)s-(\d+(?:\.\d+)?)s\]", re.I)
# Point: 12.0s:  or 4s:
POINT_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)s:", re.I)
# Chinese ranges used by H3 compiler: 0.00–1.60秒 or 0.00-1.60秒
ZH_RANGE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[–\-]\s*(\d+(?:\.\d+)?)\s*秒")
SILENT_AUDIO_RE = re.compile(
    r"<音效>|生成对白|配乐：|\{[^{}]*(?:dialogue|对白|台词)[^{}]*\}",
    re.I,
)
SOUNDSCAPE_NONEMPTY_RE = re.compile(
    r"overall_soundscape\s*:\s*(?!N/?A\b|无\b|none\b|n/?a\b)(\S)",
    re.I,
)
MUSIC_NONEMPTY_RE = re.compile(
    r"non_diegetic_music\s*:\s*(?!N/?A\b|无\b|none\b|n/?a\b)(\S)",
    re.I,
)
DIALOGUE_BLOCK_RE = re.compile(r"<d>\s*.+?\s*</d>", re.S)


def _max_time_in_text(text: str) -> float:
    best = 0.0
    for m in AT_RE.finditer(text or ""):
        minutes = float(m.group(1))
        seconds = float(m.group(2))
        best = max(best, minutes * 60.0 + seconds)
    for m in BRACKET_RE.finditer(text or ""):
        best = max(best, float(m.group(1)), float(m.group(2)))
    for m in POINT_RE.finditer(text or ""):
        best = max(best, float(m.group(1)))
    for m in ZH_RANGE_RE.finditer(text or ""):
        best = max(best, float(m.group(1)), float(m.group(2)))
    return best


def resolve_effective(lock: dict[str, Any], job: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pick the deliverable-track effective record for this job."""
    tracks = lock.get("tracks")
    job = job or {}
    if isinstance(tracks, dict) and tracks:
        tid = job.get("track_id")
        if isinstance(tid, str) and isinstance(tracks.get(tid), dict):
            return tracks[tid]
        aspect = job.get("aspect_ratio")
        if aspect:
            for rec in tracks.values():
                if isinstance(rec, dict) and rec.get("aspect") == aspect:
                    return rec
        first = next((v for v in tracks.values() if isinstance(v, dict)), None)
        if first:
            return first
    return lock.get("effective") or {}


def check(prompt_text: str, job: dict[str, Any], lock: dict[str, Any]) -> list[str]:
    errors, _warns = check_with_warnings(prompt_text, job, lock)
    return errors


def check_with_warnings(prompt_text: str, job: dict[str, Any], lock: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []
    eff = resolve_effective(lock, job)
    jid = job.get("id") or job.get("track_id") or "?"
    status = eff.get("status")
    conflict = eff.get("conflict") or {}
    if status == "unsupported_by_channel" or conflict.get("type") == "aspect_ratio":
        errors.append(
            f"G-CH6: job {jid} track {eff.get('track_id')} aspect {eff.get('aspect')} "
            f"unsupported by channel {conflict.get('channel') or []}; "
            "pause this track only (switch_channel/wait/derivative)"
        )
        return errors, warns

    dur = eff.get("duration_seconds") or {}
    job_dur = float(job.get("duration_seconds") or 0)
    max_s = dur.get("max")
    min_s = dur.get("min")
    if max_s is not None and job_dur > float(max_s) + 0.001:
        errors.append(f"G-CH1: job duration {job_dur}s exceeds channel max {max_s}s")
    if min_s is not None and job_dur and job_dur < float(min_s) - 0.001:
        errors.append(f"G-CH1: job duration {job_dur}s below channel min {min_s}s")
    t_max = _max_time_in_text(prompt_text)
    cap = float(max_s if max_s is not None else job_dur or 0)
    job_cap = job_dur or cap
    limit = min(cap, job_cap) if cap and job_cap else cap or job_cap
    if t_max and limit and t_max > limit + 0.05:
        errors.append(f"G-CH2: prompt timeline {t_max}s exceeds job/channel {limit}s")

    refs = job.get("references") or job.get("inputs") or []
    img_cap = (eff.get("reference_inputs") or {}).get("image")
    frame_roles = {"first_frame", "last_frame"}
    ref_roles = {"reference", "reference_image", "reference_video", "reference_audio"}
    n_ref = 0
    job_track = job.get("track_id")
    for item in refs:
        if isinstance(item, dict):
            role = str(item.get("role") or "reference")
            item_track = item.get("track_id")
            if job_track and item_track and item_track != job_track:
                errors.append(f"G-CH6: job {jid} input {item.get('asset_id')} is track {item_track}, not {job_track}")
            if role in frame_roles:
                item_aspect = item.get("aspect_ratio")
                job_aspect = job.get("aspect_ratio")
                if item_aspect and job_aspect and item_aspect != job_aspect:
                    errors.append(f"G-CH6: frame anchor aspect {item_aspect} != job {job_aspect}")
                continue
            if role in ref_roles:
                n_ref += 1
        else:
            n_ref += 1
    if isinstance(img_cap, int) and n_ref > img_cap:
        errors.append(f"G-CH3: {n_ref} refs > cap {img_cap}")

    tracks = lock.get("tracks") if isinstance(lock.get("tracks"), dict) else {}
    job_aspect = job.get("aspect_ratio")
    track_aspect = eff.get("aspect")
    if tracks and not job.get("track_id") and not job_aspect:
        errors.append(f"G-CH6: job {jid} missing track_id")
    if job.get("track_id") and tracks and job["track_id"] not in tracks:
        errors.append(f"G-CH6: job {jid} track_id {job['track_id']} not in lock.tracks")
    if job_aspect and track_aspect and job_aspect != track_aspect:
        errors.append(f"G-CH6: job aspect {job_aspect} != track {track_aspect}")
    if job_aspect == "9:16" and prompt_text and "16:9横屏" in prompt_text and "9:16竖屏" not in prompt_text:
        errors.append("G-CH6: portrait job prompt still says 16:9横屏")
    if job_aspect == "16:9" and prompt_text and "9:16竖屏" in prompt_text and "16:9横屏" not in prompt_text:
        errors.append("G-CH6: landscape job prompt still says 9:16竖屏")

    modes = set(eff.get("modes") or [])
    mode = job.get("mode")
    if modes and mode and mode not in modes:
        errors.append(f"G-CH4: mode {mode} not in {sorted(modes)}")
    max_chars = lock.get("prompt_max_chars") or eff.get("prompt_max_chars")
    if isinstance(max_chars, int) and prompt_text and len(prompt_text) > max_chars:
        errors.append(f"G-CH7: prompt {len(prompt_text)} chars > max {max_chars}")
    cap_status = eff.get("capability_status") if isinstance(eff.get("capability_status"), dict) else {}
    if cap_status:
        from .channel import gate_capabilities

        g_err, g_warn = gate_capabilities(
            {k: {"status": v} if isinstance(v, str) else v for k, v in cap_status.items()}
        )
        errors.extend(g_err)
        warns.extend(g_warn)
    audio = eff.get("audio_output")
    if audio == "none":
        if SILENT_AUDIO_RE.search(prompt_text or ""):
            errors.append("G-CH5: silent channel but prompt asks for generated audio")
        if SOUNDSCAPE_NONEMPTY_RE.search(prompt_text or "") or MUSIC_NONEMPTY_RE.search(prompt_text or ""):
            errors.append("G-CH5: silent channel requires overall_soundscape/non_diegetic_music N/A")
        if DIALOGUE_BLOCK_RE.search(prompt_text or ""):
            errors.append("G-CH5: silent channel but compiled <d> dialogue is present; move to audio_post_plan")
    return errors, warns


def apply_lock_checks(
    project: dict[str, Any],
    lock: dict[str, Any],
    prompt_for_job: Callable[[dict[str, Any]], str],
    *,
    project_hash: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if lock.get("model_profile") and project.get("model_profile") and lock["model_profile"] != project["model_profile"]:
        errors.append("G-CH8: lock model_profile does not match project; regenerate lock")
    sources = lock.get("sources") or {}
    if sources.get("project_hash") and project_hash and sources["project_hash"] != project_hash:
        errors.append("G-CH8: project hash != lock; regenerate lock")
    tracks = lock.get("tracks") if isinstance(lock.get("tracks"), dict) else {}
    if not tracks:
        conflict = (lock.get("effective") or {}).get("conflict")
        if conflict:
            errors.append(f"G-CH: aspect/capability conflict {conflict}")
    for job in project.get("jobs") or []:
        if isinstance(job, dict):
            errors.extend(check(prompt_for_job(job), job, lock))
    return errors
