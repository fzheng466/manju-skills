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
_FX_NEG = re.compile(r"(禁止|不出现|不要|不得|避免|无|不是|而非)[^。；;\n]{0,10}$")
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
        hits = []
        for w in XIANXIA_FX:
            for m in re.finditer(re.escape(w), body):
                prefix = body[max(0, m.start() - 16): m.start()]
                if _FX_NEG.search(prefix) or re.search(r"(禁止|不是|而非|不要)", prefix):
                    continue
                hits.append(w)
                break
        if hits:
            errors.append(f"SHOT-GENRE: urban project prompt contains xianxia FX {hits}")
    errors.extend(check_speaker_order(body))
    errors.extend(check_onscreen_text(body, job))
    errors.extend(check_facing_away_performance(body))
    errors.extend(check_four_view_singleton(body))
    errors.extend(check_hud_rear(body))
    errors.extend(check_boilerplate_distance_conflict(body))
    if aspect == "9:16":
        errors.extend(check_portrait_near(body, job))
    return errors


_QUOTED_CN = re.compile(r"[「\"“]([^」\"”]{1,80})[」\"”]")
_SCALE_NEAR_QUOTE = re.compile(
    r"(特写|插入镜头|后期叠加|后期逐行叠加|后期以特写)"
)
_FACE_AWAY = re.compile(r"三分之二背对|背对镜头|后脑勺")
_FACE_PERF = re.compile(r"哭笑不得|微表情|眉毛|嘴角|瞳孔|眼珠")
_FOUR_VIEW = re.compile(r"四视图")
_ONE_PERSON = re.compile(r"画面中只出现一个([\u4e00-\u9fffA-Za-z0-9_]+)")
_HUD_REAR = re.compile(r"界面背面|界面背后|透过半透明界面")
_HUD_HIDE = re.compile(r"只见发光边框|文字不可见|发光边框，文字不可见")
_STOP_3M = re.compile(r"停步离镜头约\s*3\s*米|离镜头约3米")
_SHOULDER_M = re.compile(r"肩后方约\s*(\d+(?:\.\d+)?)\s*米")


def check_onscreen_text(text: str, job: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    body = text or ""
    frozen = []
    job = job or {}
    for shot in job.get("shots") or []:
        if not isinstance(shot, dict):
            continue
        for line in shot.get("dialogue") or []:
            if isinstance(line, dict) and line.get("kind") == "onscreen_text":
                frozen.append(str(line.get("text") or ""))
    for u in job.get("utterances") or []:
        if isinstance(u, dict) and u.get("kind") == "onscreen_text":
            frozen.append(str(u.get("text") or ""))
    for match in _QUOTED_CN.finditer(body):
        quoted = match.group(1).strip()
        cn = re.sub(r"[^\u4e00-\u9fff]", "", quoted)
        if len(cn) <= 12:
            continue
        window = body[max(0, match.start() - 80): match.end() + 40]
        if _SCALE_NEAR_QUOTE.search(window):
            continue
        errors.append(
            f"SHOT-TEXT: onscreen text ({len(cn)} chars) at 中景 will not render; use 特写 insert or post overlay"
        )
        break
    if frozen:
        for line in frozen:
            if line and line not in body:
                errors.append("SHOT-TEXT: onscreen_text differs from frozen script")
                break
    return errors


def check_facing_away_performance(text: str) -> list[str]:
    body = text or ""
    if _FACE_AWAY.search(body) and _FACE_PERF.search(body) and "反打" not in body:
        return ["SHOT-PERF: expression beat on subject while facing away from camera"]
    return []


def check_four_view_singleton(text: str) -> list[str]:
    body = text or ""
    if not _FOUR_VIEW.search(body):
        return []
    names = re.findall(r"(?:由|参考图[一二三四五1-5]?（?)([\u4e00-\u9fff]{2,4})(?:16:9)?四视图", body)
    if not names:
        names = re.findall(r"([\u4e00-\u9fff]{2,4})(?:16:9)?四视图", body)
    skip = {"由", "参考", "锁定", "身份", "主板", "角色", "人物"}
    names = [n for n in names if n not in skip and not n.startswith("由")]
    errors: list[str] = []
    for name in dict.fromkeys(names):
        if f"画面中只出现一个{name}" not in body:
            errors.append(f"SHOT-REF: four-view ref for {name} without '画面中只出现一个{name}'")
    return errors


def check_hud_rear(text: str) -> list[str]:
    body = text or ""
    if _HUD_REAR.search(body) and not _HUD_HIDE.search(body):
        return ["SHOT-HUD: rear view of HUD must hide text (mirror risk)"]
    return []


FX_TRIGGERS = {
    "hud": ("系统面板", "系统提示", "光幕", "HUD", "全息", "回收系统"),
    "array": ("法阵", "阵纹", "阵眼"),
    "trail": ("刃光", "剑气", "剑光", "刀光"),
    "shield": ("护盾", "护体", "灵罩", "光罩"),
    "infection": ("感染纹", "尸斑纹", "感染蔓延"),
    "skill_ui": ("技能槽", "冷却环"),
}
FX_FACE = re.compile(r"(法阵|面板|光幕|护盾|灵罩|刃光|剑气).{0,12}(挡住|遮住|盖住|覆盖).{0,4}(脸|面部)")


def _fx_hits(text: str) -> set[str]:
    hits: set[str] = set()
    for cls, words in FX_TRIGGERS.items():
        for w in words:
            for m in re.finditer(re.escape(w), text):
                if not _FX_NEG.search(text[max(0, m.start() - 16): m.start()]):
                    hits.add(cls)
                    break
    return hits


def _is_fx(asset: dict[str, Any]) -> bool:
    return asset.get("kind") == "fx" or asset.get("asset_role") == "fx"


def check_fx_bindings(
    job: dict[str, Any],
    text: str,
    assets_by_id: dict[str, dict[str, Any]] | None,
) -> list[str]:
    errors: list[str] = []
    assets_by_id = assets_by_id or {}
    text = text or ""
    shot_text = " ".join(
        str(b.get("visible_action") or "") + str(b.get("fx") or "")
        for sh in (job.get("shots") or [])
        if isinstance(sh, dict)
        for b in (sh.get("beats") or [])
        if isinstance(b, dict)
    )
    needed = _fx_hits(text + " " + shot_text)
    face = FX_FACE.search(text)
    if face and not _FX_NEG.search(text[max(0, face.start() - 16): face.start()]):
        errors.append("SHOT-FX-FACE: FX layer covers the face; keep it behind/beside the face plane")
    if not needed:
        return errors
    if not (job.get("asset_bindings") or assets_by_id):
        # Prompt-only lint without a project still flags missing template intent.
        errors.append(
            "SHOT-FX-ASSET: prompt describes "
            + "/".join(sorted(needed))
            + " FX but asset_bindings has no fx template"
        )
        return errors
    ledger = job.get("continuity_ledger") if isinstance(job.get("continuity_ledger"), dict) else {}
    visible = [str(x) for x in ledger.get("visible_cast") or []]
    covered: set[str] = set()
    for b in job.get("asset_bindings") or []:
        if not isinstance(b, dict):
            continue
        a = assets_by_id.get(str(b.get("asset_id")), {})
        if not (_is_fx(a) or b.get("fx_class") or b.get("asset_role") == "fx"):
            continue
        cls = a.get("fx_class") or b.get("fx_class")
        if cls:
            covered.add(cls)
        else:
            covered.update(needed)
        owner = str(a.get("owner_id") or b.get("owner_id") or "")
        if not owner:
            errors.append(f"SHOT-FX-OWNER: {b.get('asset_id')} has no owner_id")
        elif visible and owner not in visible:
            errors.append(f"SHOT-FX-OWNER: {b.get('asset_id')} owned by off-screen {owner}")
    for cls in sorted(needed - covered):
        errors.append(f"SHOT-FX-ASSET: prompt describes {cls} FX but asset_bindings has no fx/{cls} template")
    return errors


def check_boilerplate_distance_conflict(text: str) -> list[str]:
    body = text or ""
    if not _STOP_3M.search(body):
        return []
    if "过肩" in body:
        return []
    m = _SHOULDER_M.search(body)
    if m and float(m.group(1)) < 3:
        return [f"SHOT-REF: boilerplate 3m conflicts with over-shoulder {m.group(1)}m"]
    return []


def check_portrait_near(text: str, job: dict[str, Any] | None = None) -> list[str]:
    """Fail-closed when 9:16 prompts put the subject too close to lens."""
    errors: list[str] = []
    body = text or ""
    heights = [float(x) for x in HEIGHT_IN_PROMPT.findall(body)]
    if WALK_TO_CAM.search(body) and heights and heights[0] > 45:
        errors.append(f"SHOT-NEAR: walk-toward-camera must start ≤45%, got {heights[0]:g}%")
    if heights:
        peak = max(heights)
        first = heights[0]
        delta = peak - first
        if delta > 18:
            errors.append(
                f"SHOT-NEAR: approach peaks {delta:g} points ({first:g}→{peak:g}) in one job"
            )
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


def check_job(
    job: dict[str, Any],
    prompt_text: str = "",
    assets_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    errors: list[str] = []
    errors.extend(check_prompt(prompt_text, job))
    errors.extend(check_fx_bindings(job, prompt_text, assets_by_id))
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
    assets_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(raw, dict):
        assets_by_id = {
            str(a.get("asset_id")): a for a in (raw.get("assets") or []) if isinstance(a, dict)
        }
    errors: list[str] = []
    for job in jobs:
        errors.extend(check_job(job, prompt, assets_by_id))
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print("PASS: shot/performance gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
