"""G-CH checks against the effective capability lock."""
from __future__ import annotations

import re
from typing import Any


TIME_RE = re.compile(
    r"(?:At\s+\d{2}:\d{2}\.\d{3}|\[(\d+(?:\.\d+)?)s-(\d+(?:\.\d+)?)s\]|(\d+(?:\.\d+)?)s:)"
)


def _max_time_in_text(text: str) -> float:
    best = 0.0
    for m in TIME_RE.finditer(text or ""):
        nums = [float(x) for x in m.groups() if x]
        if nums:
            best = max(best, max(nums))
        else:
            # At HH:MM.mmm
            raw = m.group(0)
            if raw.startswith("At"):
                try:
                    mm, rest = raw.split(":")[1], raw.split(":")[-1]
                    best = max(best, float(mm) * 60 + float(rest))
                except Exception:
                    pass
    return best


def check(prompt_text: str, job: dict[str, Any], lock: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    eff = lock.get("effective") or {}
    dur = eff.get("duration_seconds") or {}
    job_dur = float(job.get("duration_seconds") or 0)
    max_s = dur.get("max")
    min_s = dur.get("min")
    if max_s is not None and job_dur > float(max_s):
        errors.append(f"G-CH1: job duration {job_dur}s exceeds channel max {max_s}s")
    if min_s is not None and job_dur and job_dur < float(min_s):
        errors.append(f"G-CH1: job duration {job_dur}s below channel min {min_s}s")
    t_max = _max_time_in_text(prompt_text)
    cap = float(max_s or job_dur or 0)
    if t_max and cap and t_max > cap + 0.05:
        errors.append(f"G-CH2: prompt timeline {t_max}s exceeds job/channel {cap}s")
    img_cap = (eff.get("reference_inputs") or {}).get("image")
    n_ref = len(job.get("references") or [])
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
