"""Compile a frozen director-notes job into a Seedance prompt (never from H3 finished text)."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

H3_LEAK = re.compile(
    r"<Subject\s+\d+>|<Picture\s+\d+>|<Video\s+\d+>|<Audio\s+\d+>|<d>\s*\[|\(S\d+\)|"
    r"\b(?:subject_definitions|retention_analysis|T2VA|I2VA|L2VA|FL2VA|Ref2VA)\b",
    re.I,
)
MODE_MAP = {
    "T2VA": "text_only",
    "I2VA": "frame_anchored",
    "L2VA": "text_only",
    "FL2VA": "first_last_frame",
    "Ref2VA": "reference_set",
    "text_only": "text_only",
    "reference_image": "reference_image",
    "reference_set": "reference_set",
    "first_last_frame": "first_last_frame",
    "frame_anchored": "frame_anchored",
    "multimodal_reference": "multimodal_reference",
}


def _lines(job: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for shot in job.get("shots") or []:
        if isinstance(shot, dict):
            for line in shot.get("dialogue") or []:
                if isinstance(line, dict):
                    out.append(line)
    return out


def reconstruct_dialogue(job: dict[str, Any]) -> str:
    return "".join(str(line.get("text") or "") for line in _lines(job))


def map_mode(h3_mode: str, profile: str) -> tuple[str, str | None]:
    mapped = MODE_MAP.get(h3_mode, "text_only")
    note = None
    if h3_mode == "L2VA":
        note = "L2VA degraded to text_only; describe end_state in prose"
        mapped = "text_only"
    if h3_mode == "I2VA" and profile.endswith("2.5"):
        note = "I2VA on 2.5 needs a last frame for first_last_frame; otherwise frame_anchored/text"
    if h3_mode == "Ref2VA" and profile.endswith("2.0"):
        mapped = "multimodal_reference"
    return mapped, note


def compile_prompt(job: dict[str, Any], *, profile: str = "seedance-2.5", aspect: str | None = None) -> dict[str, Any]:
    aspect = aspect or str(job.get("aspect_ratio") or "16:9")
    opener = "16:9横屏" if aspect == "16:9" else "9:16竖屏"
    mapped, note = map_mode(str(job.get("mode") or "T2VA"), profile)
    blocks: list[str] = [
        f"Seedance {profile} | {opener} | 内部模式：{mapped} | 时长：{job.get('duration_seconds')}s",
        "",
        f"成片基准：{opener}，沿用项目视觉圣经；身份参考只锁人物不锁构图。",
    ]
    if note:
        blocks.append(f"模式说明：{note}。")
    id_points = job.get("identification_points") or []
    if isinstance(id_points, list) and id_points:
        blocks.append("识别点复述：" + "；".join(str(x) for x in id_points[:4]))

    for shot in job.get("shots") or []:
        if not isinstance(shot, dict):
            continue
        sid = shot.get("id") or shot.get("shot_id")
        blocks.append("")
        blocks.append(f"镜头 {sid} {shot.get('start_seconds')}–{shot.get('end_seconds')}s：{shot.get('purpose') or shot.get('main_action') or ''}")
        if shot.get("camera"):
            blocks.append(f"摄影：{shot.get('camera')}")
        cam = shot.get("camera_plan") if isinstance(shot.get("camera_plan"), dict) else {}
        if cam:
            blocks.append(
                f"机位：{cam.get('start_composition')} → {cam.get('movement')}（触发 {cam.get('movement_trigger')}）→ {cam.get('end_composition')}"
            )
        perf = shot.get("performance_plan") if isinstance(shot.get("performance_plan"), dict) else {}
        if perf:
            seq = perf.get("micro_expression_sequence") or []
            blocks.append("表演：" + " → ".join(str(x) for x in seq) + f"；听者：{perf.get('listener_reaction')}")
        for beat in shot.get("beats") or []:
            if not isinstance(beat, dict):
                continue
            blocks.append(
                f"  {beat.get('start_seconds')}–{beat.get('end_seconds')}s 焦点{beat.get('focus')}："
                f"{beat.get('visible_action')}；表情 {beat.get('expression')}"
            )
        for line in shot.get("dialogue") or []:
            if not isinstance(line, dict):
                continue
            delivery = line.get("delivery") if isinstance(line.get("delivery"), dict) else {}
            audible = "，".join(
                str(delivery.get(k) or "")
                for k in ("volume", "pace", "timbre")
                if delivery.get(k)
            ) or str(line.get("tone") or "原语气")
            pre = line.get("pre_line_action") or "开口前完成视线"
            post = line.get("listener_reaction") or line.get("post_line_reaction") or "句末听者微反应"
            speaker = line.get("speaker_id") or ""
            text = line.get("text") or ""
            blocks.append(f"{speaker}以{audible}说：「{text}」")
            blocks.append(f"可见：{pre}；听者 {post}")

    prompt = "\n".join(blocks).strip() + "\n"
    errors = check_transpile(job, prompt)
    return {"prompt": prompt, "mode": mapped, "aspect": aspect, "errors": errors}


def check_transpile(job: dict[str, Any], prompt: str) -> list[str]:
    errors: list[str] = []
    if H3_LEAK.search(prompt or ""):
        errors.append("G-TR2: Seedance prompt still contains H3 syntax")
    expected = reconstruct_dialogue(job)
    if expected:
        for line in _lines(job):
            text = line.get("text")
            if isinstance(text, str) and text and text not in (prompt or ""):
                errors.append(f"G-TR1: frozen line missing from Seedance prompt: {text[:24]}")
                break
    for point in job.get("identification_points") or []:
        if isinstance(point, str) and point and point not in (prompt or ""):
            errors.append(f"G-TR3: identification point not restated: {point}")
    for shot in job.get("shots") or []:
        if not isinstance(shot, dict):
            continue
        for ent in shot.get("entrance_order") or []:
            if not isinstance(ent, dict):
                continue
            if ent.get("initial_visibility") in {"offscreen", "fully_occluded"}:
                name = str(ent.get("actor_id") or "")
                reveal = ent.get("reveal_start_seconds")
                if name and name in prompt.split("首次可见")[0] and reveal:
                    head = prompt[: prompt.find(str(reveal))] if str(reveal) in prompt else prompt
                    if name in head and "完全画外" not in head:
                        errors.append(f"G-TR4: hidden {name} named before reveal")
    return errors


def main() -> int:
    p = argparse.ArgumentParser(description="Transpile a frozen job to Seedance prompt")
    p.add_argument("--project", type=Path, required=True)
    p.add_argument("--job-id", default=None)
    p.add_argument("--profile", default="seedance-2.5")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()
    data = json.loads(args.project.read_text(encoding="utf-8"))
    jobs = data.get("jobs") if isinstance(data.get("jobs"), list) else [data]
    job = jobs[0]
    if args.job_id:
        job = next((j for j in jobs if isinstance(j, dict) and j.get("id") == args.job_id), None)
        if job is None:
            print(f"ERROR: job {args.job_id} not found")
            return 2
    result = compile_prompt(job, profile=args.profile, aspect=job.get("aspect_ratio"))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(result["prompt"], encoding="utf-8")
        print(f"wrote {args.out} mode={result['mode']}")
    else:
        print(result["prompt"])
    for e in result["errors"]:
        print(f"FAIL: {e}")
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
