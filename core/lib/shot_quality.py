"""Shot reasonableness and performance-detail gates (director notes / compiled prompt)."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
from pathlib import Path
from typing import Any

from .channel import manju_home, normalize_audio_output

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


def check_prompt(
    text: str,
    job: dict[str, Any] | None = None,
    assets_by_id: dict[str, dict[str, Any]] | None = None,
    lock: dict[str, Any] | None = None,
    project: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    body = text or ""
    raw_job = job or {}
    ctx = _ctx(raw_job, lock, project)
    job = _with_ctx(raw_job, ctx)
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
    errors.extend(check_fx_ui(body, aspect, job))
    errors.extend(check_onscreen_text(body, job))
    errors.extend(check_facing_away_performance(body))
    errors.extend(check_four_view_singleton(body))
    errors.extend(check_hud_rear(body))
    errors.extend(check_boilerplate_distance_conflict(body))
    errors.extend(check_audio_policy(body, job, ctx))
    errors.extend(check_duration_enum(job, ctx, body))
    errors.extend(check_ref_roles(job, assets_by_id, ctx, project))
    errors.extend(check_fx_visibility(body, job, assets_by_id))
    errors.extend(check_fx_body_and_dialogue(body, job))
    errors.extend(check_fx_tier(body, job))
    errors.extend(check_fx_lookdev(job, project, assets_by_id))
    errors.extend(check_prop_state(body, job, project, assets_by_id))
    errors.extend(check_production_path(job, ctx))
    if aspect == "9:16":
        errors.extend(check_portrait_near(body, job))
    return errors


_SEG_SPLIT = re.compile(r"\[Shot\s*\d+\]|\[\d+(?:\.\d+)?s\s*[-–]\s*\d+(?:\.\d+)?s\]")
_UI_H = re.compile(r"(面板|界面|UI)[^。；]{0,16}高度约为画面高度的\s*(\d+(?:\.\d+)?)\s*%")
_FULL_UI = re.compile(r"标题框|标题环|六边形|地台")
_NO_CAST = re.compile(r"人物不入画|不出现人物")
_LR_HEX = re.compile(r"左右(两侧)?各(竖排)?\s*[3三]枚")


def _expand_path(raw: Any) -> str:
    """$MANJU_HOME defaults to ~/.manju even when the env var is unset."""
    text = str(raw or "")
    home = manju_home().as_posix()
    text = text.replace("${MANJU_HOME}", home).replace("$MANJU_HOME", home)
    return os.path.expanduser(os.path.expandvars(text))


def _ctx(job: dict[str, Any], lock: dict[str, Any] | None, project: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read-only view: lock track wins over job fields; project supplies roots/policy."""
    eff: dict[str, Any] = {}
    if lock:
        from .guards_channel import resolve_effective

        eff = resolve_effective(lock, job) or {}
    project = project or {}
    if lock:
        audio = eff.get("audio_output")
        if audio in (None, ""):
            audio = job.get("audio_output")
    else:
        audio = job.get("audio_output") or (job.get("effective") or {}).get("audio_output")
    return {
        "audio_output": normalize_audio_output(audio),
        "duration_allowed": (eff.get("duration_seconds") or {}).get("allowed") or job.get("duration_allowed"),
        "realperson": bool(project.get("realperson") or job.get("realperson") or job.get("live_action")),
        "realperson_policy": eff.get("realperson_policy") or {},
        "reference_transport": eff.get("reference_transport"),
        "production_root": project.get("production_root") or job.get("production_root"),
        "test_root": _expand_path(project.get("test_root") or job.get("test_root") or ""),
        "lock_present": bool(lock),
        "effective": eff,
    }


def _with_ctx(job: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Overlay derived capability values so legacy checks agree with lock-aware ones."""
    merged = dict(job)
    for key in ("audio_output", "duration_allowed", "production_root", "test_root"):
        value = ctx.get(key)
        if value not in (None, "", []):
            merged[key] = value
    if ctx.get("realperson"):
        merged["realperson"] = True
    return merged


def _confirmed_ui_cap(job: dict[str, Any] | None, aspect: str | None) -> float:
    job = job or {}
    confirmed = job.get("fx_tier_confirmed")
    if isinstance(confirmed, dict) and isinstance(confirmed.get("max_fx_percent"), (int, float)):
        return float(confirmed["max_fx_percent"])
    state = str(job.get("fx_state") or job.get("fx_state_in") or "")
    portrait = aspect == "9:16"
    defaults = {
        "off": 0,
        "presence": 10,
        "collapsed": 12,
        "readable": 45 if portrait else 50,
        "fullscreen": 90,
    }
    if state in defaults:
        return float(defaults[state])
    return 10.0


def check_fx_ui(text: str, aspect: str | None, job: dict[str, Any] | None = None) -> list[str]:
    """HUD size uses confirmed look-dev; otherwise a safe default. Full chrome still needs an insert."""
    errors: list[str] = []
    body = text or ""
    job = job or {}
    cap = _confirmed_ui_cap(job, aspect)
    parts = _SEG_SPLIT.split(body)
    parts = parts[1:] if len(parts) > 1 else [body]
    for i, seg in enumerate(parts, 1):
        ph = [float(x) for x in HEIGHT_IN_PROMPT.findall(seg)]
        uh = [float(m.group(2)) for m in _UI_H.finditer(seg)]
        person = bool(ph) and not _NO_CAST.search(seg)
        if person and uh and max(uh) > cap:
            errors.append(
                f"SHOT-FX-TIER: segment {i} UI {max(uh):g}% exceeds confirmed/safe cap {cap:g}%"
            )
        if person and uh and max(ph) > 50 and max(uh) > 40 and not job.get("fx_tier_confirmed"):
            errors.append(
                f"SHOT-FX-UI: segment {i} person {max(ph):g}% + UI {max(uh):g}% without look-dev; confirm readable tier or cut to insert"
            )
        if person and len(set(_FULL_UI.findall(seg))) >= 2:
            errors.append(
                f"SHOT-FX-UI: segment {i} puts full UI chrome beside a character; move it to an insert shot"
            )
        if aspect == "9:16" and _NO_CAST.search(seg) and _LR_HEX.search(seg):
            errors.append(
                f"SHOT-FX-UI: segment {i} 9:16 insert reuses 16:9 left/right 3+3 hex columns; stack vertically"
            )
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


POST_DUB = re.compile(r"后期配音|后期配|配音替换|post[- ]?dub", re.I)
TURN = re.compile(r"转身|侧身|回头|半转|过肩|背对|三分之二背")
FX_MOVE = re.compile(r"(移到|退到|缩到|收到|收至).{0,8}(余光|画面边缘|身后|侧后)|收起|消失|收束")
FX_BETWEEN = re.compile(r"(面板|光幕|界面|法阵|护盾).{0,12}(两人之间|中间|挡在)")
FORBIDDEN_SCENE_ROLES = {"scene_master"}
FACE_ROLES = {"fx_lookdev", "fx_text_frame"}


def _job_has_dialogue(job: dict[str, Any]) -> bool:
    for shot in job.get("shots") or []:
        if isinstance(shot, dict) and shot.get("dialogue"):
            return True
    if job.get("utterances"):
        return True
    return False


def _dialogue_speakers(job: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for shot in job.get("shots") or []:
        if not isinstance(shot, dict):
            continue
        for line in shot.get("dialogue") or []:
            if isinstance(line, dict) and line.get("speaker_id"):
                out.add(str(line["speaker_id"]))
    for u in job.get("utterances") or []:
        if isinstance(u, dict) and u.get("speaker_id"):
            out.add(str(u["speaker_id"]))
    return out


def _visible_cast(job: dict[str, Any]) -> list[str]:
    ledger = job.get("continuity_ledger") if isinstance(job.get("continuity_ledger"), dict) else {}
    return [str(x) for x in (ledger.get("visible_cast") or job.get("visible_cast") or [])]


def _bound_fx(job: dict[str, Any], assets_by_id: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Merge each binding with its asset record; asset-level visibility/owner must count."""
    assets_by_id = assets_by_id or {}
    out = []
    for b in job.get("asset_bindings") or []:
        if not isinstance(b, dict):
            continue
        asset = assets_by_id.get(str(b.get("asset_id")), {})
        merged = {**asset, **{k: v for k, v in b.items() if v is not None}}
        if (merged.get("kind") == "fx" or merged.get("asset_role") == "fx"
                or merged.get("fx_class") or merged.get("visibility")
                or str(merged.get("ref_role") or "").startswith("fx_")):
            out.append(merged)
    return out


def _utterances(job: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for shot in job.get("shots") or []:
        if not isinstance(shot, dict):
            continue
        for line in shot.get("dialogue") or []:
            if isinstance(line, dict):
                out.append(line)
    for u in job.get("utterances") or []:
        if isinstance(u, dict):
            out.append(u)
    return out


def _beats(job: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for shot in job.get("shots") or []:
        if not isinstance(shot, dict):
            continue
        for beat in shot.get("beats") or []:
            if isinstance(beat, dict):
                out.append(beat)
    return out


def _addressees(job: dict[str, Any]) -> set[str]:
    return {str(u.get("addressee_id")) for u in _utterances(job) if u.get("addressee_id")}


def check_audio_policy(text: str, job: dict[str, Any], ctx: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    raw = (ctx or {}).get("audio_output") or job.get("audio_output") or (job.get("effective") or {}).get("audio_output")
    audio = normalize_audio_output(raw) if raw is not None else "unknown"
    if audio == "native" and POST_DUB.search(text or ""):
        errors.append("SHOT-AUD-POST: channel has native audio; do not hand dialogue to post-dub")
    if audio == "native" and _job_has_dialogue(job):
        has_voice = bool(job.get("voice_profile_id"))
        for shot in job.get("shots") or []:
            if not isinstance(shot, dict):
                continue
            for line in shot.get("dialogue") or []:
                if isinstance(line, dict) and line.get("voice_profile_id"):
                    has_voice = True
        for utterance in job.get("utterances") or []:
            if isinstance(utterance, dict) and utterance.get("voice_profile_id"):
                has_voice = True
        if not has_voice:
            errors.append("SHOT-AUD-VOICE: dialogue without voice_profile_id identity layer")
    return errors


def check_duration_enum(job: dict[str, Any], ctx: dict[str, Any] | None = None, prompt_text: str = "") -> list[str]:
    from .guards_channel import _max_time_in_text

    errors: list[str] = []
    allowed = (ctx or {}).get("duration_allowed") or job.get("duration_allowed") or (
        (job.get("effective") or {}).get("duration_seconds") or {}
    ).get("allowed")
    dur = job.get("duration_seconds")
    if allowed and isinstance(dur, (int, float)) and int(round(dur)) not in {int(x) for x in allowed}:
        errors.append(f"SHOT-DUR-ENUM: duration {dur} not in channel enum {list(allowed)}; run adapt snap")
    if job.get("duration_snapped_from") and not job.get("duration_user_ack"):
        errors.append("SHOT-DUR-ACK: snapped duration not acknowledged by user")
    if job.get("duration_snapped_from") and isinstance(dur, (int, float)) and prompt_text:
        last = _max_time_in_text(prompt_text)
        if last and last < float(dur) - 0.5:
            errors.append(f"SHOT-DUR-TC: prompt timecodes end at {last:g}s but job duration is {dur:g}s")
    return errors


REF_ROLES = {
    "identity_board", "scene_master", "scene_view", "prop_board", "prop_state",
    "fx_shell", "fx_lookdev", "fx_text_frame", "tail_frame",
}
FORBIDDEN_SCENE_ROLES = {"scene_master"}
FACE_ROLES = {"fx_lookdev", "fx_text_frame"}


def _prev_job_had_fx(job: dict[str, Any], project: dict[str, Any] | None) -> bool:
    if "previous_job_had_fx" in job:
        return bool(job.get("previous_job_had_fx"))
    ledger = job.get("continuity_ledger") if isinstance(job.get("continuity_ledger"), dict) else {}
    prev_id = str(ledger.get("previous_job_id") or job.get("previous_job_id") or "")
    if project and prev_id and prev_id not in {"none", ""}:
        for candidate in project.get("jobs") or []:
            if isinstance(candidate, dict) and str(candidate.get("id")) == prev_id:
                return bool(
                    _bound_fx(candidate)
                    or candidate.get("fx_state")
                    or candidate.get("fx_state_out")
                )
    state_in = str(job.get("fx_state_in") or "")
    return bool(state_in) and state_in not in {"off", "none"}


def check_ref_roles(
    job: dict[str, Any],
    assets_by_id: dict[str, dict[str, Any]] | None = None,
    ctx: dict[str, Any] | None = None,
    project: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    ctx = ctx or {}
    assets_by_id = assets_by_id or {}
    realperson = bool(ctx.get("realperson") or job.get("realperson") or job.get("live_action"))
    policy = ctx.get("realperson_policy") or {}
    transport = str(ctx.get("reference_transport") or "")
    for b in job.get("asset_bindings") or []:
        if not isinstance(b, dict):
            continue
        role = b.get("ref_role")
        method = str(b.get("binding_method") or "")
        asset = assets_by_id.get(str(b.get("asset_id")), {})
        if not role:
            errors.append("SHOT-REF-ROLE: binding without ref_role")
            continue
        if role not in REF_ROLES:
            errors.append(f"SHOT-REF-ROLE: unknown ref_role {role!r}")
            continue
        if role in FORBIDDEN_SCENE_ROLES and method in {"attached_reference", "reference"}:
            errors.append("SHOT-REF-GRID: 2×2 scene master attached; bind a scene_view crop")
        face = b.get("contains_face", asset.get("contains_face"))
        if realperson and role in FACE_ROLES and face is not False and policy.get("face_composite", "reject") != "ok":
            errors.append("SHOT-REF-FACE: face composite on real-person channel (contains_face unknown counts as true)")
        if role == "tail_frame":
            carried = b.get("fx_state") or asset.get("fx_state")
            want = job.get("fx_state_in") or job.get("fx_state")
            if _prev_job_had_fx(job, project) and not carried:
                errors.append("SHOT-REF-INHERIT: tail_frame must declare fx_state when the previous job had FX")
            elif carried and want and carried != want:
                errors.append("SHOT-REF-INHERIT: tail frame carries FX state this job must drop")
        if transport == "uploaded" and str(b.get("source") or "").startswith("http"):
            errors.append("SHOT-REF-UPLOAD: channel requires uploaded assets, got bare URL")
    return errors


def check_fx_visibility(
    text: str,
    job: dict[str, Any],
    assets_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    errors: list[str] = []
    owner_fx = [a for a in _bound_fx(job, assets_by_id) if a.get("visibility") == "owner_only"]
    if not owner_fx:
        return errors
    owners = {str(a.get("owner_id")) for a in owner_fx if a.get("owner_id")}
    others = [c for c in _visible_cast(job) if c not in owners]
    speakers = _dialogue_speakers(job)
    addressees = _addressees(job)
    talking_to_other = bool(others) and bool((speakers | addressees) & set(others))
    state = str(job.get("fx_state") or job.get("fx_state_in") or "")
    if talking_to_other and state in {"readable", "fullscreen"}:
        errors.append(
            "SHOT-FX-VIS: owner_only FX stays readable while a non-owner is addressed or speaking; collapse or drop"
        )
    if others and _job_has_dialogue(job) and not addressees and speakers and speakers <= owners:
        errors.append(
            "SHOT-FX-ADDR: owner speaks with a non-owner on screen; set utterance.addressee_id"
        )
    fx_ids = {str(a.get("asset_id")) for a in owner_fx if a.get("asset_id")}
    for beat in _beats(job):
        actor = str(beat.get("actor_id") or "")
        target = str(beat.get("look_target") or "")
        if actor in others and target in fx_ids:
            errors.append("SHOT-FX-VIS: non-owner reacts to owner_only FX")
            break
    return errors


def check_fx_body_and_dialogue(text: str, job: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    body = text or ""
    if not _bound_fx(job) and not re.search(r"光幕|面板|界面|法阵|护盾", body):
        return errors
    if TURN.search(body) and not FX_MOVE.search(body):
        errors.append(
            "SHOT-FX-BODY: FX stays at chest/front while subject turns; move to periphery, shrink, or collapse"
        )
    if len(_visible_cast(job)) >= 2 and _job_has_dialogue(job) and FX_BETWEEN.search(body):
        errors.append("SHOT-FX-DIALOGUE: FX sits between speakers")
    return errors


def check_fx_tier(text: str, job: dict[str, Any]) -> list[str]:
    uh = [float(m.group(2)) for m in _UI_H.finditer(text or "")]
    if not uh:
        return []
    cap = _confirmed_ui_cap(job, job.get("aspect_ratio"))
    if max(uh) > cap:
        return [f"SHOT-FX-TIER: FX/person size exceeds confirmed (or safe-default) tier {cap:g}%"]
    return []


def _first_fx_jobs(project: dict[str, Any], assets_by_id: dict[str, dict[str, Any]] | None = None) -> set[str]:
    """Derive first FX look-dev from job order instead of a hand-maintained flag."""
    first: set[str] = set()
    seen_ids: set[str] = set()
    seen_states: set[tuple[str, str]] = set()
    jobs = [j for j in project.get("jobs") or [] if isinstance(j, dict)]
    for j in sorted(jobs, key=lambda item: (item.get("episode_start_seconds", 0), str(item.get("id")))):
        jid = str(j.get("id") or "")
        state = str(j.get("fx_state") or j.get("fx_state_in") or "")
        for fx in _bound_fx(j, assets_by_id):
            aid = str(fx.get("asset_id") or "")
            if aid and aid not in seen_ids:
                first.add(jid)
            seen_ids.add(aid)
            if state in {"readable", "fullscreen"} and (aid, state) not in seen_states:
                first.add(jid)
            seen_states.add((aid, state))
            if fx.get("visibility") == "owner_only":
                owners = {str(fx.get("owner_id"))} if fx.get("owner_id") else set()
                if set(_visible_cast(j)) - owners:
                    first.add(jid)
    return first


def check_fx_lookdev(
    job: dict[str, Any],
    project: dict[str, Any] | None = None,
    assets_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    if job.get("fx_tier_confirmed"):
        return []
    is_first = bool(job.get("fx_first_appearance"))
    if project:
        is_first = is_first or str(job.get("id")) in _first_fx_jobs(project, assets_by_id)
    if not is_first:
        return []
    return ["SHOT-FX-LOOKDEV: first FX appearance without fx_tier_confirmed"]


STATE_LEXICON: dict[str, tuple[str, ...]] = {
    "open": ("开着", "敞开", "打开"),
    "closed": ("关着", "关上", "紧闭"),
    "covered": ("盖着", "罩着"),
    "uncovered": ("揭开", "掀开", "未盖", "盖子打开"),
    "lit_steady": ("灯光稳定", "常亮"),
    "flicker": ("闪烁", "忽明忽暗", "乱闪"),
    "intact": ("完好",),
    "broken": ("碎", "断裂", "破损"),
}
OPPOSITE = {
    "open": "closed", "closed": "open",
    "covered": "uncovered", "uncovered": "covered",
    "lit_steady": "flicker", "flicker": "lit_steady",
    "intact": "broken", "broken": "intact",
}
_GENERIC_PROP_NAMES = {
    "door": "门", "window": "窗", "lamp": "灯", "bowl": "碗", "cover": "罩",
    "lid": "盖", "cup": "杯", "glass": "杯", "bottle": "瓶", "phone": "手机",
    "box": "盒", "key": "钥匙",
}


def _prop_mentioned(text: str, prop_id: str, assets_by_id: dict[str, dict[str, Any]] | None) -> bool:
    if not prop_id or prop_id == "*":
        return True
    asset = (assets_by_id or {}).get(prop_id, {})
    names = [prop_id, asset.get("name"), asset.get("label"), *(asset.get("aliases") or [])]
    for part in str(prop_id).split("_"):
        names.append(part)
        if part.lower() in _GENERIC_PROP_NAMES:
            names.append(_GENERIC_PROP_NAMES[part.lower()])
    return any(str(n) and str(n) in text for n in names)


def check_prop_state(
    text: str,
    job: dict[str, Any],
    project: dict[str, Any] | None = None,
    assets_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    body = text or ""
    ledger = job.get("continuity_ledger") if isinstance(job.get("continuity_ledger"), dict) else {}
    states = ledger.get("prop_state")
    if states is None:
        states = job.get("prop_state")
    if states is None:
        states = ledger.get("environment_state")
    lexicon = dict(STATE_LEXICON)
    extra = (project or {}).get("state_lexicon") or job.get("state_lexicon")
    if isinstance(extra, dict):
        lexicon.update({str(k): tuple(v) if isinstance(v, (list, tuple)) else (str(v),) for k, v in extra.items()})
    errors: list[str] = []

    def check_one(prop_id: str, state: str) -> None:
        opposite = OPPOSITE.get(state)
        if not opposite:
            return
        words = lexicon.get(opposite, ())
        if not any(w in body for w in words):
            return
        if not _prop_mentioned(body, prop_id, assets_by_id):
            return
        errors.append(
            f"SHOT-PROP-STATE: {prop_id} is {state} in the ledger but the prompt says {opposite}"
        )

    if isinstance(states, dict):
        for pid, state in states.items():
            check_one(str(pid), str(state))
    elif isinstance(states, str) and states.strip():
        for state in OPPOSITE:
            if state in states:
                check_one("*", state)
    return errors


def _norm_path(raw: Any) -> str:
    value = _expand_path(raw)
    try:
        return Path(value).resolve().as_posix().lower()
    except OSError:
        return Path(value).as_posix().lower()


def check_production_path(job: dict[str, Any], ctx: dict[str, Any] | None = None) -> list[str]:
    media = str(job.get("media_path") or "")
    if not media:
        return []
    ctx = ctx or {}
    prod = str(ctx.get("production_root") or job.get("production_root") or "")
    test = str(ctx.get("test_root") or job.get("test_root") or "")
    if not prod:
        return ["PATH-PROD: production_root not set; refuse to write generated media"]
    m = _norm_path(media)
    if test:
        t = _norm_path(test)
        if m == t or m.startswith(t + "/"):
            return ["PATH-PROD: media path is under test_root"]
    pr = _norm_path(prod)
    if not (m == pr or m.startswith(pr + "/")):
        return ["PATH-PROD: media outside production_root"]
    return []


def check_job(
    job: dict[str, Any],
    prompt_text: str = "",
    assets_by_id: dict[str, dict[str, Any]] | None = None,
    lock: dict[str, Any] | None = None,
    project: dict[str, Any] | None = None,
    stage: str = "draft",
) -> list[str]:
    errors: list[str] = []
    ctx = _ctx(job, lock, project)
    if stage == "submit" and not ctx["lock_present"]:
        errors.append("SHOT-LOCK: submit-stage gates require --lock")
    if stage == "submit" and not ctx.get("production_root") and not job.get("media_path"):
        errors.append("PATH-PROD: production_root not set for submit; refuse to place generated media")
    errors.extend(check_prompt(prompt_text, job, assets_by_id, lock, project))
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
    p.add_argument("--lock", type=Path, default=None, help="effective-capability.lock.json")
    p.add_argument("--stage", choices=["draft", "submit"], default=None)
    args = p.parse_args()
    raw = json.loads(args.job.read_text(encoding="utf-8"))
    jobs = [raw]
    project = None
    if isinstance(raw, dict) and "jobs" in raw:
        project = raw
        jobs = [j for j in (raw.get("jobs") or []) if isinstance(j, dict)]
        if args.job_id:
            jobs = [j for j in jobs if j.get("id") == args.job_id]
    prompt = args.prompt.read_text(encoding="utf-8") if args.prompt else ""
    assets_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(raw, dict):
        assets_by_id = {
            str(a.get("asset_id")): a for a in (raw.get("assets") or []) if isinstance(a, dict)
        }
    lock = json.loads(args.lock.read_text(encoding="utf-8")) if args.lock else None
    stage = args.stage or (str(project.get("stage")) if isinstance(project, dict) else "draft") or "draft"
    errors: list[str] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        text = prompt
        if not text and job.get("compiled_prompt_path"):
            candidate = Path(str(job["compiled_prompt_path"]))
            if not candidate.is_absolute():
                candidate = args.job.resolve().parent / candidate
            if candidate.is_file():
                text = candidate.read_text(encoding="utf-8")
        errors.extend(check_job(job, text, assets_by_id, lock=lock, project=project, stage=stage))
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print("PASS: shot/performance gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
