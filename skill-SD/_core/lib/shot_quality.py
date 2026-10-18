"""Shot reasonableness and performance-detail gates (director notes / compiled prompt)."""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

VAGUE_PERF = re.compile(r"眼神复杂|气场强|表情微妙|很有戏|情绪饱满|眼神深邃")
MULTI_MOVE = re.compile(r"(推轨|横移|摇|升降|环绕).{0,12}(推轨|横移|摇|升降|环绕)")
MID_ONLY = ("中景",)


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def check_prompt(text: str, job: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    body = text or ""
    job = job or {}
    if VAGUE_PERF.search(body):
        errors.append("SHOT-PERF: vague acting words (眼神复杂/气场强/表情微妙); write brow/lid/mouth/breath sequence")
    aspect = job.get("aspect_ratio")
    if aspect == "9:16" and "并排" in body and "纵深" not in body and "上下" not in body:
        errors.append("SHOT-AR: 9:16 dual-subject still uses 并排; switch to depth or stacked staging")
    if aspect == "16:9" and "16:9横屏" not in body and "横屏" not in body and "16:9" not in body:
        errors.append("SHOT-AR: landscape prompt missing 16:9横屏 opener")
    if aspect == "9:16" and "9:16竖屏" not in body and "竖屏" not in body and "9:16" not in body:
        errors.append("SHOT-AR: portrait prompt missing 9:16竖屏 opener")
    if MULTI_MOVE.search(body):
        errors.append("SHOT-CAM: more than one primary camera move in the same window; split beats")
    return errors


def check_job(job: dict[str, Any], prompt_text: str = "") -> list[str]:
    errors: list[str] = []
    errors.extend(check_prompt(prompt_text, job))
    scales: list[str] = []
    for si, shot in enumerate(job.get("shots") or []):
        if not isinstance(shot, dict):
            continue
        plan = shot.get("performance_plan")
        if isinstance(plan, dict):
            seq = plan.get("micro_expression_sequence")
            if not isinstance(seq, list) or not 2 <= len(seq) <= 3:
                errors.append(f"SHOT-PERF: shot[{si}] micro_expression_sequence must have 2–3 ordered cues")
            for field in ("trigger", "baseline", "end_expression"):
                if not plan.get(field):
                    errors.append(f"SHOT-PERF: shot[{si}] performance_plan.{field} required")
            hold = plan.get("hold_seconds")
            if _number(hold) and hold < 0.15:
                errors.append(f"SHOT-PERF: shot[{si}] hold_seconds too short to read the reaction")
        cam = shot.get("camera_plan")
        if isinstance(cam, dict):
            move = str(cam.get("movement") or "")
            if "且" in move or "然后" in move or "+" in move:
                errors.append(f"SHOT-CAM: shot[{si}] camera_plan.movement must be a single primary move")
        for beat in shot.get("beats") or []:
            if not isinstance(beat, dict):
                continue
            expr = str(beat.get("expression") or "")
            if expr and not any(k in expr for k in ("眉", "眼", "嘴", "唇", "颌", "呼吸", "肩")):
                errors.append(f"SHOT-PERF: beat expression must name a visible region (眉/眼/嘴/呼吸)")
            cam_b = beat.get("camera") if isinstance(beat.get("camera"), dict) else {}
            framing = str(beat.get("viewpoint") or (cam_b or {}).get("framing") or beat.get("camera") or "")
            if framing:
                scales.append(framing)
            action = str(beat.get("visible_action") or "")
            if action and "然后又" in action and "收势" not in action:
                errors.append("SHOT-ACT: one beat packs two primary actions; split")
    if scales and all("中景" in s for s in scales) and len(scales) >= 3:
        errors.append("SHOT-SCALE: entire job stays 中景; vary establish / full-body / reaction")
    return errors


def main() -> int:
    p = argparse.ArgumentParser(description="Check shot blocking and performance detail")
    p.add_argument("--job", type=Path, required=True, help="job JSON or project.json")
    p.add_argument("--job-id", default=None)
    p.add_argument("--prompt", type=Path, default=None)
    args = p.parse_args()
    raw = json.loads(args.job.read_text(encoding="utf-8"))
    jobs = [raw]
    if isinstance(raw, dict) and "jobs" in raw:
        jobs = [j for j in (raw.get("jobs") or []) if isinstance(j, dict)]
        if args.job_id:
            jobs = [j for j in jobs if j.get("id") == args.job_id]
    prompt = args.prompt.read_text(encoding="utf-8") if args.prompt else ""
    errors: list[str] = []
    for job in jobs:
        errors.extend(check_job(job, prompt))
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print("PASS: shot/performance gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
