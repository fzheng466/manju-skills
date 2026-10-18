"""Shot reasonableness and performance-detail gates (director notes / compiled prompt)."""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

VAGUE_PERF = re.compile(r"眼神复杂|气场强|表情微妙|很有戏|情绪饱满|眼神深邃|杀气很重|表情很冷|气场全开")
MOVE_TOKEN = r"(推轨|拉轨|推近|拉远|横移|横摇|竖摇|摇摄|升降|环绕|变焦)"
MULTI_MOVE = re.compile(MOVE_TOKEN + r".{0,24}" + MOVE_TOKEN)
MID_ONLY = ("中景",)
XIANXIA_FX = ("法阵", "符文", "灵力", "仙气", "阵眼")
URBAN_MARKERS = ("urban", "modern", "当代", "都市", "现代都市", "industrial-city")
SPEAKER_BEFORE_D = re.compile(r"\(S(\d+)\)\s*[，,]?\s*<d>", re.I)
HEIGHT_IN_PROMPT = re.compile(r"约占画面高度\s*(\d+(?:\.\d+)?)\s*%")
WALK_TO_CAM = re.compile(r"走向镜头|朝镜头走来|沿纵深走向镜头|沿巷子纵深走来")
CLOSE_FACE = re.compile(r"大头|脸部占满|怼脸|贴脸")
HEADROOM = re.compile(r"头顶.{0,8}(12%|约12%)|留出约12%|头顶上方留")
REF_NOT_COMP = re.compile(r"只锁(定)?身份|不(决定|锁)构图|不要模仿身份板")
PORTRAIT_MIN = {"全身": 60, "中近景": 52, "中景": 42, "近景": 62, "特写": 78, "大远景": 8, "远景": 18}
PORTRAIT_MAX = {"大远景": 22, "远景": 40, "全身": 76, "中景": 60, "中近景": 68, "近景": 78, "特写": 100}
LANDSCAPE_MIN = {"全身": 65, "中近景": 45, "中景": 35, "近景": 55, "特写": 70, "大远景": 3, "远景": 10}
LANDSCAPE_MAX = {"大远景": 18, "远景": 35, "全身": 90, "中景": 70, "中近景": 80, "近景": 90, "特写": 100}
PORTRAIT_BOILERPLATE = (
    "输出画幅9:16竖屏（请求参数同为9:16）。参考图均为16:9资产图，只锁定人物身份、服装、场景结构与道具外形，"
    "不决定构图与景别，不要模仿身份板里的大胸像尺寸。主体不要顶满画幅：头顶上方留出约12%的空间"
    "（含上沿8%字幕安全区），脚下或画面下沿留出约8%地面或安全区。每个时间段写明人物约占画面高度N%"
    "（从头顶到画面可见最低身体部位）。人物停步离镜头约3米，略长焦，不出现大头特写。"
)


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
    genre = " ".join(
        str(job.get(k) or "") for k in ("genre", "setting", "world", "project_genre")
    ).lower()
    urban = any(m.lower() in genre or m in body[:80] for m in URBAN_MARKERS)
    if urban:
        hits = [w for w in XIANXIA_FX if w in body]
        if hits:
            errors.append(f"SHOT-GENRE: urban project prompt contains xianxia FX {hits}")
    errors.extend(check_speaker_order(body))
    if aspect == "9:16":
        errors.extend(check_portrait_near(body, job))
    return errors


def check_portrait_near(text: str, job: dict[str, Any] | None = None) -> list[str]:
    """Fail-closed when 9:16 prompts put the subject too close to lens."""
    errors: list[str] = []
    body = text or ""
    heights = [float(x) for x in HEIGHT_IN_PROMPT.findall(body)]
    if WALK_TO_CAM.search(body) and heights and heights[0] > 45:
        errors.append(f"SHOT-NEAR: walk-toward-camera must start ≤45%, got {heights[0]:g}%")
    if len(heights) >= 2:
        delta = heights[-1] - heights[0]
        if delta > 18:
            errors.append(f"SHOT-NEAR: push/approach grows {delta:g} points (>18) in one job")
        # scale-tagged heights in prose
        for scale, cap in (("中景", 60), ("全身", 76), ("中近景", 68), ("近景", 78)):
            for m in re.finditer(scale + r".{0,24}约占画面高度\s*(\d+(?:\.\d+)?)\s*%", body):
                h = float(m.group(1))
                if h > cap:
                    extra = " (collides with 8% safe areas)" if scale == "全身" else ""
                    errors.append(f"SHOT-NEAR: 9:16 {scale} {h:g}% > {cap}{extra}")
        if "齐胸高" in body:
            for m in re.finditer(r"中近景.{0,24}约占画面高度\s*(\d+(?:\.\d+)?)\s*%", body):
                h = float(m.group(1))
                if h > 66:
                    errors.append(f"SHOT-NEAR: chest-height camera + 中近景 {h:g}% reads as face-in-lens")
            if not re.search(r"中近景.{0,24}约占画面高度", body):
                for h in heights:
                    if h > 66:
                        errors.append(f"SHOT-NEAR: chest-height camera + 中近景 {h:g}% reads as face-in-lens")
                        break
    if CLOSE_FACE.search(body) and "特写" not in body:
        errors.append("SHOT-NEAR: close-up face fill without 特写 beat")
    compiled = bool(heights) or "subject_definitions" in body or "[Shot" in body
    if compiled and (not HEADROOM.search(body) or not REF_NOT_COMP.search(body)):
        errors.append("SHOT-REF: 9:16 job with 16:9 refs missing headroom/ref-composition boilerplate")
    return errors


def check_speaker_order(text: str) -> list[str]:
    tags = [int(n) for n in SPEAKER_BEFORE_D.findall(text or "")]
    if not tags:
        return []
    expected = list(range(1, len(tags) + 1))
    if tags != expected:
        return [f"H3-SX: first speaker must be (S1) then increment; got {tags}"]
    return []


def check_job(job: dict[str, Any], prompt_text: str = "") -> list[str]:
    errors: list[str] = []
    errors.extend(check_prompt(prompt_text, job))
    scales: list[str] = []
    REGION = ("眉", "眼", "睑", "嘴", "唇", "颌", "呼吸", "肩", "喉")
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
            for field in ("trigger", "end_expression"):
                v = str(plan.get(field) or "")
                if v and (len(v) < 4 or (field == "end_expression" and not any(r in v for r in REGION))):
                    errors.append(f"SHOT-PERF: shot[{si}] {field} must be a concrete visible event/region")
            if plan.get("concealment") and not plan.get("suppression"):
                errors.append(f"SHOT-PERF: shot[{si}] concealment set but no 压回 (suppression) cue")
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
            table_min = PORTRAIT_MIN if job.get("aspect_ratio") == "9:16" else LANDSCAPE_MIN
            table_max = PORTRAIT_MAX if job.get("aspect_ratio") == "9:16" else LANDSCAPE_MAX
            matched_key = next((key for key in sorted(table_min, key=len, reverse=True) if key in framing), None)
            for pos in beat.get("positions") or []:
                if not isinstance(pos, dict):
                    continue
                h = pos.get("screen_height_percent")
                if not _number(h) or not matched_key:
                    continue
                lo = table_min[matched_key]
                hi = table_max[matched_key]
                slack = 0 if job.get("aspect_ratio") == "9:16" else 10
                if h < lo - slack:
                    errors.append(f"SHOT-AR: {framing} height {h}% too small for {job.get('aspect_ratio')} ({matched_key} min {lo})")
                if h > hi + slack:
                    tag = "SHOT-NEAR" if job.get("aspect_ratio") == "9:16" else "SHOT-AR"
                    extra = " (collides with 8% safe areas)" if matched_key == "全身" and job.get("aspect_ratio") == "9:16" else ""
                    errors.append(f"{tag}: {framing} height {h}% too large for {job.get('aspect_ratio')} ({matched_key} max {hi}){extra}")
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
