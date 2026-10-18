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
SCENE_CAST = ("女主", "男主", "角色", "人物", "站在门口", "站在")
COUNT_RE = re.compile(
    r"(?:(肩甲|裙甲|流苏|飘带|甲片).{0,16}(\d+|[一二三四五六七八九十两]+)\s*(片|股|条)"
    r"|(\d+|[一二三四五六七八九十两]+)\s*(片|股|条).{0,8}(肩甲|裙甲|流苏|飘带|甲片|披帛))"
)
GLOW_OK_RE = re.compile(r"(从.{1,12}(刃|槽|核|心|尖|纹).{0,8}(发光|亮)|发光.{0,8}从.{1,12}(刃|槽|核|心|尖|纹))")


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def check_text(kind: str, text: str, aspect: str = "16:9") -> list[str]:
    errors: list[str] = []
    body = text or ""
    if aspect == "16:9" and "9:16竖屏" in body and "16:9" not in body:
        errors.append("ASSET-AR: landscape board prompt is written as 9:16竖屏")
    if aspect == "9:16" and "16:9横屏" in body and "9:16" not in body:
        errors.append("ASSET-AR: portrait board prompt is written as 16:9横屏")
    if aspect == "16:9" and "16:9" not in body and "横屏" not in body:
        errors.append("ASSET-AR: prompt must declare 16:9 / 横屏")
    if aspect == "9:16" and "9:16" not in body and "竖屏" not in body:
        errors.append("ASSET-AR: prompt must declare 9:16 / 竖屏")
    for word in VAGUE:
        if word in body and kind in {"character", "weapon"}:
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

    if kind == "weapon":
        if not _has_any(body, ARTIFACT_SIG):
            errors.append("ASSET-WPN: xianxia/prop board needs silhouette + forge/spirit signature (xianxia-hero-artifacts)")
        if not _has_any(body, HOLD_POINT):
            errors.append("ASSET-WPN: missing 握持/柄点")
        if aspect == "16:9" and "左侧" not in body and "主图" not in body:
            errors.append("ASSET-WPN: 16:9 weapon board should be 左主图 + 右细节窗")
        if aspect == "9:16" and "上" not in body and "主图" not in body:
            errors.append("ASSET-WPN: 9:16 weapon board should be 上主图 + 下细节窗")
        if re.search(r"发光|仙气", body) and not GLOW_OK_RE.search(body) and "光源" not in body:
            errors.append("ASSET-WPN: glow must name a structural source path (刃/槽/核/心), not wrap the whole object")

    if kind == "scene":
        if not _has_any(body, ("四向", "正向", "反向", "左侧向")):
            errors.append("ASSET-SCN: scene board should be a four-direction structure plate")
        if _has_any(body, SCENE_CAST) and "禁止人物" not in body and "不加入角色" not in body and "不加入人物" not in body:
            errors.append("ASSET-SCN: structure plate must not bake characters into the master")
    return errors


def main() -> int:
    p = argparse.ArgumentParser(description="Validate one asset-board prompt before generation")
    p.add_argument("--kind", required=True, choices=["character", "weapon", "scene"])
    p.add_argument("--aspect", default="16:9", choices=["16:9", "9:16"])
    p.add_argument("--file", type=Path, required=True)
    args = p.parse_args()
    text = args.file.read_text(encoding="utf-8")
    errors = check_text(args.kind, text, args.aspect)
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print(f"PASS: {args.kind} asset prompt ({args.aspect})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
