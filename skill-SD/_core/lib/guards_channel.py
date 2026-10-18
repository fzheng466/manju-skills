"""G-CH checks against the effective capability lock."""
from __future__ import annotations

import re
from typing import Any

# H3: At 00:03.500  = 3.5 seconds into the job (MM:SS.mmm, minutes then seconds)
AT_RE = re.compile(r"At\s+(\d{1,2}):(\d{2}(?:\.\d+)?)", re.I)
# Seedance / interval: [0s-4s] or [0.0s-4.0s]
BRACKET_RE = re.compile(r"\[(\d+(?:\.\d+)?)s-(\d+(?:\.\d+)?)s\]", re.I)
# Point: 12.0s:  or 4s:
POINT_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)s:", re.I)
# Chinese ranges used by H3 compiler: 0.00–1.60秒 or 0.00-1.60秒
ZH_RANGE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[–\-]\s*(\d+(?:\.\d+)?)\s*秒")


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


def check(prompt_text: str, job: dict[str, Any], lock: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    eff = lock.get("effective") or {}
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
    n_ref = len(refs)
    if isinstance(img_cap, int) and n_ref > img_cap:
        errors.append(f"G-CH3: {n_ref} refs > cap {img_cap}")
    modes = set(eff.get("modes") or [])
    mode = job.get("mode")
    if modes and mode and mode not in modes:
        errors.append(f"G-CH4: mode {mode} not in {sorted(modes)}")
    audio = eff.get("audio_output")
    if audio == "none" and re.search(r"<音效>|生成对白|配乐：", prompt_text or ""):
        errors.append("G-CH5: silent channel but prompt asks for generated audio")
    return errors
