"""Gate asset-board prompts before image generation (character / weapon / scene)."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

VAGUE = (
    "仙气飘飘",
    "华丽高级",
    "高级感",
    "氛围感",
    "很仙",
    "神秘华丽",
    "特效拉满",
    "高级",
    "漂亮",
    "优雅",
    "帅气",
    "时尚",
    "精英感",
)
EMPTY_HANDS = ("双手空置", "空手", "不手持", "双手离开", "空置并离开")
ARMOR_STRUCT = ("肩甲", "胸甲", "护心", "裙甲", "胫甲")
ROBE_STRUCT = ("交领", "外纱", "腰封", "广袖", "飘带")
TASSEL_STRUCT = ("流苏", "插入点", "下颌", "垂直")
ARTIFACT_SIG = ("剪影", "轮廓", "炼", "灵", "握持", "导灵")
HOLD_POINT = ("握持", "柄", "持物")
SCENE_CAST = (
    "女主", "男主", "角色", "人物", "站在门口", "站在",
    "男人", "女人", "少年", "老人", "人影", "身影", "背影", "行人",
)
MASTER_KINDS = {"character", "weapon", "prop", "fx"}
FX_KIND = "fx"
FX_ALIASES = {
    "fx": None,
    "hud": "hud",
    "system": "hud",
    "array": "array",
    "trail": "trail",
    "shield": "shield",
    "infection": "infection",
    "skill_ui": "skill_ui",
}
FX_CLASSES = ("hud", "array", "trail", "shield", "infection", "skill_ui")
FX_CLASS_ANCHORS = {
    "hud": ("光点槽", "槽位", "进度环", "分栏"),
    "array": ("同心", "环", "阵眼", "阵纹"),
    "trail": ("起点", "收束", "轨迹", "路径"),
    "shield": ("厚度", "边缘", "破裂态", "曲面"),
    "infection": ("阶段", "蔓延", "纹路"),
    "skill_ui": ("槽", "冷却环", "图标框"),
}
FX_NO_TEXT = ("无字", "空面板", "不出现可读文字", "假字", "不可读符号", "乱码条", "空白条", "无可读汉字")
FX_LIGHT_RE = re.compile(
    r"((从|沿).{0,12}(边框|边缘|光点槽|槽|阵纹|阵眼|刃口|核心|环|裂纹).{0,10}(发光|亮|流)|光源)"
)
FX_NEON = ("整块霓虹", "通体发光", "整体发光", "全屏光", "满屏光", "整片光雾")
FX_CAST = ("人物", "角色", "人影", "身影", "背影", "手指", "手掌", "人脸", "男主", "女主", "男人", "女人")
NEG_RE = re.compile(r"(禁止|不出现|不要|不得|避免|无|不画|不加入)[^。；;\n]{0,10}$")
QUOTED_CJK = re.compile(r"[「“\"]([\u4e00-\u9fff]{4,})[」”\"]")
COUNT_RE = re.compile(
    r"(?:(肩甲|裙甲|流苏|飘带|甲片).{0,16}(\d+|[一二三四五六七八九十两]+)\s*(片|股|条)"
    r"|(\d+|[一二三四五六七八九十两]+)\s*(片|股|条).{0,8}(肩甲|裙甲|流苏|飘带|甲片|披帛))"
)
GLOW_OK_RE = re.compile(r"(从.{1,12}(刃|槽|核|心|尖|纹).{0,8}(发光|亮)|发光.{0,8}从.{1,12}(刃|槽|核|心|尖|纹))")


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def normalize_kind(kind: str, fx_class: str | None = None) -> tuple[str, str | None]:
    if kind in FX_ALIASES:
        return FX_KIND, fx_class or FX_ALIASES[kind]
    return kind, fx_class


def _unnegated(text: str, word: str) -> bool:
    for m in re.finditer(re.escape(word), text):
        start = m.start()
        prefix = text[max(0, start - 8): start]
        line_start = text.rfind("\n", 0, start)
        line = text[line_start + 1: m.end()] if line_start >= 0 else text[: m.end()]
        if "【禁用】" in line or line.lstrip().startswith("【禁用】"):
            continue
        if re.search(r"(禁止|不出现|不要|不得|避免|不画|不加入)$", prefix.rstrip("的了，, ")):
            continue
        if NEG_RE.search(prefix):
            continue
        return True
    return False


def check_fx(body: str, aspect: str, fx_class: str | None, owner_id: str | None) -> list[str]:
    errors: list[str] = []
    if fx_class not in FX_CLASSES:
        errors.append(f"ASSET-FX: fx board needs --fx-class one of {FX_CLASSES}")
    if not owner_id:
        errors.append("ID-OWN: fx template must bind owner_id (trigger character) via --owner-id")
    if aspect == "9:16":
        return errors
    if not _has_any(body, FX_NO_TEXT):
        errors.append("ASSET-FX-TEXT: declare 空面板/无字/假字; readable copy is a post overlay")
    for m in QUOTED_CJK.finditer(body):
        if not NEG_RE.search(body[max(0, m.start() - 16): m.start()]):
            errors.append(f"ASSET-FX-TEXT: readable Chinese {m.group(1)!r} on board; move to post overlay")
            break
    if not FX_LIGHT_RE.search(body):
        errors.append("ASSET-FX-LIGHT: name the light path (从边框/光点槽/阵纹…发光), not a glow blob")
    for w in FX_NEON:
        if _unnegated(body, w):
            errors.append(f"ASSET-FX-NEON: {w!r} drifts across shots; light only from named structures")
            break
    if "左" not in body or "主图" not in body or "细节" not in body:
        errors.append("ASSET-FX-LAYOUT: 16:9 fx board must be 左主图 + 右细节窗")
    for w in FX_CAST:
        if _unnegated(body, w):
            errors.append(f"ASSET-FX-CAST: template board must be empty of people ({w!r}); bind owner in metadata")
            break
    if fx_class in FX_CLASS_ANCHORS and not _has_any(body, FX_CLASS_ANCHORS[fx_class]):
        errors.append(f"ASSET-FX-{fx_class.upper()}: missing structure anchor {FX_CLASS_ANCHORS[fx_class]}")
    return errors


def check_text(
    kind: str,
    text: str,
    aspect: str = "16:9",
    *,
    sex: str | None = None,
    character_id: str = "CHAR",
    derivative_of: str | None = None,
    characters: dict | None = None,
    fx_class: str | None = None,
    owner_id: str | None = None,
) -> list[str]:
    errors: list[str] = []
    body = text or ""
    kind, fx_class = normalize_kind(kind, fx_class)
    if kind in MASTER_KINDS and aspect == "9:16":
        errors.append("ASSET-AR: identity/prop masters are 16:9; derive portrait crops instead")
    if kind == "scene" and aspect == "9:16" and not derivative_of:
        errors.append("ASSET-AR: 9:16 scene board requires --derivative-of <SCENE_ID>")
    if aspect == "16:9" and "9:16竖屏" in body and "16:9" not in body:
        errors.append("ASSET-AR: landscape board prompt is written as 9:16竖屏")
    if aspect == "9:16" and "16:9横屏" in body and "9:16" not in body:
        errors.append("ASSET-AR: portrait board prompt is written as 16:9横屏")
    if aspect == "16:9" and "16:9" not in body and "横屏" not in body:
        errors.append("ASSET-AR: prompt must declare 16:9 / 横屏")
    if aspect == "9:16" and kind not in MASTER_KINDS and "9:16" not in body and "竖屏" not in body:
        errors.append("ASSET-AR: prompt must declare 9:16 / 竖屏")
    for word in VAGUE:
        if word in body and kind in {"character", "weapon", FX_KIND}:
            errors.append(f"ASSET-VAGUE: replace {word!r} with structure/material/color")
            break

    if kind == "character":
        if "正面全身" not in body or "背面全身" not in body or ("45" not in body and "侧面全身" not in body):
            errors.append("ASSET-CHAR: four-view board must list 正面全身、45°/侧面全身、背面全身")
        if not _has_any(body, EMPTY_HANDS):
            errors.append("ASSET-CHAR: identity board must state empty hands (双手空置)")
        if any(k in body for k in ("战甲", "甲胄", "护甲")) and not _has_any(body, ARMOR_STRUCT):
            errors.append("ASSET-CHAR: armor board missing structure anchors (肩甲/胸甲/裙甲…); read anime-3d-asset-lexicon")
        if any(k in body for k in ("仙袍", "外袍", "广袖")) and not _has_any(body, ROBE_STRUCT):
            errors.append("ASSET-CHAR: robe board missing layer/sash/ribbon anchors; read anime-3d-asset-lexicon")
        if "流苏" in body and not _has_any(body, TASSEL_STRUCT):
            errors.append("ASSET-CHAR: tassel board must count strands, insertion point, hang length")
        if _has_any(body, ("战甲", "肩甲", "流苏", "飘带")) and not COUNT_RE.search(body):
            errors.append("ASSET-CHAR: 结构计数 must include a number (e.g. 肩甲4片 / 流苏3股 / 飘带2条)")
        inferred = sex
        if not inferred:
            if re.search(r"(女性|女主|女将|女修|female)", body, re.I):
                inferred = "female"
            elif re.search(r"(男性|男主|男将|男修|male)", body, re.I):
                inferred = "male"
        if inferred:
            from .identity import check_prompt_for_sex, check_signature_cross

            errors.extend(check_prompt_for_sex(body, inferred, character_id=character_id, kind="character"))
            if characters:
                errors.extend(check_signature_cross(body, character_id, characters))
        elif kind == "character":
            errors.append("ID-SEX: character board must declare 男性/女性 (or pass --sex)")

    if kind in {"weapon", "prop"}:
        score = 0
        if _has_any(body, ("剪影", "轮廓")):
            score += 1
        if re.search(r"炼|锻|铸|淬|材", body):
            score += 1
        if re.search(r"握持.{0,10}(手|指|掌)|单手|双手|握持点", body):
            score += 1
        if score < 2:
            errors.append("ASSET-WPN: need at least two of 剪影/轮廓, 炼制/材质来源, 握持方式")
        if aspect == "16:9" and "左侧" not in body and "主图" not in body:
            errors.append("ASSET-WPN: 16:9 weapon board should be 左主图 + 右细节窗")
        if aspect == "9:16" and "上" not in body and "主图" not in body:
            errors.append("ASSET-WPN: 9:16 weapon board should be 上主图 + 下细节窗")
        if re.search(r"发光|仙气", body) and not GLOW_OK_RE.search(body) and "光源" not in body:
            errors.append("ASSET-WPN: glow must name a structural source path (刃/槽/核/心), not wrap the whole object")
        inferred = sex
        if not inferred:
            if re.search(r"(女性|女主|女将|女修|female)", body, re.I):
                inferred = "female"
            elif re.search(r"(男性|男主|男将|男修|male)", body, re.I):
                inferred = "male"
        if inferred:
            from .identity import check_prompt_for_sex, check_signature_cross

            errors.extend(check_prompt_for_sex(body, inferred, character_id=character_id, kind="weapon"))
            if characters:
                errors.extend(check_signature_cross(body, character_id, characters))
        else:
            errors.append("ID-SEX: weapon board must name owner sex or pass --sex")

    if kind == FX_KIND:
        errors.extend(check_fx(body, aspect, fx_class, owner_id))

    if kind == "scene":
        if not _has_any(body, ("四向", "正向", "反向", "左侧向")) and not derivative_of:
            errors.append("ASSET-SCN: scene board should be a four-direction structure plate")
        for n in SCENE_CAST:
            if n not in body:
                continue
            if n in {"人物", "角色"} and any(p in body for p in ("不加入人物", "不加入角色", "禁止人物")):
                continue
            if n in {"人影", "身影", "背影"} and any(p in body for p in ("不出现人影", "不出现任何人影", "不出现身影")):
                continue
            errors.append(f"ASSET-SCN: structure plate contains a person ({n!r})")
            break
    return errors


def main() -> int:
    p = argparse.ArgumentParser(description="Validate one asset-board prompt before generation")
    p.add_argument(
        "--kind",
        required=True,
        choices=["character", "weapon", "scene", "prop", "frame", *FX_ALIASES],
    )
    p.add_argument("--aspect", default="16:9", choices=["16:9", "9:16"])
    p.add_argument("--file", type=Path, required=True)
    p.add_argument("--sex", default=None, help="male|female — required for character/weapon identity lock")
    p.add_argument("--character-id", default="CHAR")
    p.add_argument("--fx-class", default=None, choices=list(FX_CLASSES))
    p.add_argument("--owner-id", default=None, help="fx: trigger character_id")
    p.add_argument("--derivative-of", default=None, help="parent SCENE_ID when aspect is a 9:16 crop")
    p.add_argument("--project", type=Path, default=None, help="project.json for ID-SIG signature table")
    args = p.parse_args()
    text = args.file.read_text(encoding="utf-8")
    characters = None
    if args.project:
        import json
        from .identity import characters_from_project

        characters = characters_from_project(json.loads(args.project.read_text(encoding="utf-8")))
    errors = check_text(
        args.kind,
        text,
        args.aspect,
        sex=args.sex,
        character_id=args.character_id,
        derivative_of=args.derivative_of,
        characters=characters,
        fx_class=args.fx_class,
        owner_id=args.owner_id,
    )
    if args.kind in {"character", "weapon", "prop"} and not args.sex:
        errors.append("ID-SEX: pass --sex male|female before generating this board")
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print(f"PASS: {args.kind} asset prompt ({args.aspect})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
