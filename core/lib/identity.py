"""Strict per-character identity isolation for assets and compiled shots.

Prevents the production failure where a male character inherits a female
wardrobe, jewelry, or prop — and the reverse. Presentation sex is a locked
field on the character card; garments and props bind through owner_id.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SEXES = {"male", "female"}

FEMALE_WARDROBE = (
    "抹胸", "齐胸", "襦裙", "凤冠", "步摇", "钗", "簪花", "耳坠", "耳钉",
    "项链垂胸", "细腰封", "高开衩", "超短裙", "文胸", "胸罩", "吊带裙",
    "高跟鞋", "细跟", "丝袜", "连裤袜", "腿环", "足环",
)
MALE_WARDROBE = (
    "护心镜", "胸甲", "肩甲", "胫甲", "战靴", "束冠", "发冠中", "官帽",
    "阔肩", "喉结",
)
FEMALE_BODY = ("丰胸", "乳沟", "细腰", "圆臀", "长睫毛", "红唇", "柳叶眉")
MALE_BODY = ("喉结", "宽肩", "胸肌", "胡茬", "短茬胡", "方下颌")
SHARED_OK = (
    "外袍", "广袖", "交领", "腰封", "飘带", "披帛", "玉佩", "长靴", "软靴",
    "发冠", "玉簪", "耳环", "耳饰",
)


def _text(*parts: Any) -> str:
    chunks: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, dict):
            chunks.append(json.dumps(part, ensure_ascii=False))
        else:
            chunks.append(str(part))
    return "\n".join(chunks)


NEG_PREFIX = ("无", "没有", "不含", "不出现", "禁止", "勿")


def _hits(text: str, needles: tuple[str, ...]) -> list[str]:
    body = text or ""
    found: list[str] = []
    for n in needles:
        if not n or n not in body:
            continue
        idx = 0
        while True:
            pos = body.find(n, idx)
            if pos < 0:
                break
            window = body[max(0, pos - 4):pos]
            if not any(window.endswith(p) or p in window[-3:] for p in NEG_PREFIX):
                found.append(n)
                break
            idx = pos + len(n)
    return found


def normalize_sex(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip().lower()
    table = {
        "male": "male",
        "m": "male",
        "man": "male",
        "男": "male",
        "男性": "male",
        "男主": "male",
        "男角色": "male",
        "female": "female",
        "f": "female",
        "woman": "female",
        "女": "female",
        "女性": "female",
        "女主": "female",
        "女角色": "female",
    }
    return table.get(raw)


def characters_from_project(project: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key in ("characters", "cast"):
        rows = project.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            cid = str(row.get("character_id") or row.get("id") or "")
            if not cid:
                continue
            out[cid] = row
    for asset in project.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        if asset.get("kind") == "character" or asset.get("asset_role") == "identity":
            cid = str(asset.get("character_id") or asset.get("owner_id") or asset.get("asset_id") or "")
            if cid and cid not in out:
                out[cid] = asset
    return out


def check_character_card(card: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    cid = card.get("character_id") or card.get("id") or card.get("asset_id") or "?"
    sex = normalize_sex(card.get("presentation_sex") or card.get("sex") or card.get("gender"))
    if sex not in SEXES:
        errors.append(f"ID-SEX: character {cid} must lock presentation_sex male|female")
        return errors
    body = _text(card.get("prompt"), card.get("description"), card, card.get("character_design_record"))
    if sex == "male":
        bad = _hits(body, FEMALE_WARDROBE) + _hits(body, FEMALE_BODY)
        if bad:
            errors.append(f"ID-MIX: male {cid} prompt contains female-coded items {sorted(set(bad))}")
    if sex == "female":
        armor_ok = any(k in body for k in ("女战甲", "女将", "女修战甲"))
        bad = _hits(body, MALE_BODY)
        if "喉结" in bad:
            errors.append(f"ID-MIX: female {cid} prompt contains 喉结")
        if (not armor_ok) and _hits(body, ("护心镜", "胸甲", "肩甲", "胫甲")) and "女" not in body[:40]:
            # female armor is allowed when explicitly a woman warrior; generic copy-paste of male armor is not
            if _hits(body, ("阔肩战甲", "男将", "将领战甲")):
                errors.append(f"ID-MIX: female {cid} inherited a male-general armor kit")
    other = card.get("forbidden_transfer_from") or card.get("do_not_inherit")
    if isinstance(other, list) and other:
        for item in other:
            if isinstance(item, str) and item and item in body:
                errors.append(f"ID-MIX: character {cid} still contains forbidden transfer {item!r}")
    return errors


def check_prompt_for_sex(text: str, sex: str, *, character_id: str = "?", kind: str = "character") -> list[str]:
    errors: list[str] = []
    sex_n = normalize_sex(sex)
    if sex_n not in SEXES:
        errors.append(f"ID-SEX: {character_id} missing presentation_sex")
        return errors
    body = text or ""
    if not re.search(r"(男性|女性|male|female|男角色|女角色|男主|女主)", body, re.I):
        errors.append(f"ID-SEX: {character_id} prompt must declare 男性/女性 (or male/female) in the identity line")
    if sex_n == "male":
        bad = _hits(body, FEMALE_WARDROBE) + _hits(body, FEMALE_BODY)
        if bad:
            errors.append(f"ID-MIX: male {character_id} {kind} contains female-coded items {sorted(set(bad))}")
        if kind == "character" and not _hits(body, ("喉结", "男性", "男", "male")):
            errors.append(f"ID-SEX: male {character_id} board should name 男性 and keep male body landmarks")
    if sex_n == "female":
        if _hits(body, ("喉结", "胸肌", "胡茬")):
            errors.append(f"ID-MIX: female {character_id} {kind} contains male body landmarks")
        copied = _hits(body, ("将领战甲", "男将", "护心镜叠甲"))
        if copied:
            errors.append(f"ID-MIX: female {character_id} inherited male kit {copied}")
    return errors


def check_asset_binding(asset: dict[str, Any], characters: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    aid = asset.get("asset_id") or "?"
    kind = asset.get("kind") or asset.get("asset_role")
    owner = asset.get("owner_id") or asset.get("character_id")
    sex = normalize_sex(asset.get("presentation_sex") or asset.get("sex"))
    if kind in {"character", "identity"} or asset.get("asset_role") == "identity":
        card = characters.get(str(owner or aid), asset)
        errors.extend(check_character_card({**card, **asset, "character_id": owner or aid}))
        prompt = str(asset.get("prompt") or asset.get("description") or "")
        if prompt:
            errors.extend(check_prompt_for_sex(prompt, sex or normalize_sex(card.get("presentation_sex")), character_id=str(owner or aid), kind="character"))
        return errors
    if kind in {"costume", "wardrobe", "prop", "weapon", "artifact", "image"} and asset.get("asset_role") in {None, "wardrobe", "prop", "weapon"}:
        if not owner:
            if kind in {"prop", "weapon", "artifact"} or asset.get("asset_role") in {"prop", "weapon", "wardrobe"}:
                errors.append(f"ID-OWN: asset {aid} ({kind}) must set owner_id to a character")
            return errors
        card = characters.get(str(owner))
        if card is None:
            errors.append(f"ID-OWN: asset {aid} owner_id {owner} is not a declared character")
            return errors
        owner_sex = normalize_sex(card.get("presentation_sex") or card.get("sex"))
        if sex and owner_sex and sex != owner_sex:
            errors.append(f"ID-OWN: asset {aid} sex {sex} != owner {owner} sex {owner_sex}")
        body = _text(asset.get("prompt"), asset.get("description"), asset)
        if owner_sex == "male":
            bad = _hits(body, FEMALE_WARDROBE)
            if bad:
                errors.append(f"ID-MIX: male-owned asset {aid} contains female-coded items {sorted(set(bad))}")
        if owner_sex == "female":
            if _hits(body, ("喉结", "胸肌", "胡茬")):
                errors.append(f"ID-MIX: female-owned asset {aid} contains male body landmarks")
    return errors


def check_job_identity(job: dict[str, Any], characters: dict[str, dict[str, Any]], assets_by_id: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    jid = job.get("id") or "?"
    visible = []
    ledger = job.get("continuity_ledger") if isinstance(job.get("continuity_ledger"), dict) else {}
    if isinstance(ledger.get("visible_cast"), list):
        visible = [str(x) for x in ledger["visible_cast"]]
    bindings = job.get("asset_bindings") if isinstance(job.get("asset_bindings"), list) else []
    used_owners: set[str] = set()
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        aid = binding.get("asset_id")
        asset = assets_by_id.get(str(aid), {}) if aid else {}
        owner = str(asset.get("owner_id") or asset.get("character_id") or binding.get("character_id") or "")
        if owner:
            used_owners.add(owner)
        if owner and visible and owner not in visible and asset.get("kind") in {"costume", "wardrobe", "prop", "weapon"}:
            errors.append(f"ID-OWN: job {jid} binds {aid} owned by off-screen {owner}")
        other = str(asset.get("owner_id") or "")
        for cid, card in characters.items():
            if other and other != cid and asset.get("kind") in {"costume", "wardrobe"}:
                # wardrobe of A appearing as B
                if cid in visible and other != cid and aid and str(binding.get("purpose") or "").find(cid) >= 0:
                    errors.append(f"ID-OWN: job {jid} uses {other}'s wardrobe {aid} on {cid}")
    prompt = str(job.get("prompt") or "")
    if prompt and len(characters) >= 2:
        for cid, card in characters.items():
            sex = normalize_sex(card.get("presentation_sex") or card.get("sex"))
            name = str(card.get("name") or cid)
            if name and name in prompt and sex:
                window = prompt
                # if a female-coded item appears near a male name, flag
                if sex == "male":
                    bad = _hits(window, FEMALE_WARDROBE)
                    if bad and name in window:
                        errors.append(f"ID-MIX: job {jid} prompt may put female-coded {sorted(set(bad))[:4]} on male {name}")
    return errors


def check_project(project: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    characters = characters_from_project(project)
    assets = [a for a in (project.get("assets") or []) if isinstance(a, dict)]
    assets_by_id = {str(a.get("asset_id")): a for a in assets if a.get("asset_id")}
    if not characters and any(a.get("kind") in {"character", "costume", "wardrobe"} or a.get("asset_role") == "identity" for a in assets):
        errors.append("ID-SEX: project has character/wardrobe assets but no characters[] with presentation_sex")
    for card in characters.values():
        errors.extend(check_character_card(card))
    for asset in assets:
        errors.extend(check_asset_binding(asset, characters))
    if project.get("stage") == "submit":
        for job in project.get("jobs") or []:
            if isinstance(job, dict):
                errors.extend(check_job_identity(job, characters, assets_by_id))
    return errors


def main() -> int:
    p = argparse.ArgumentParser(description="Check per-character identity isolation")
    p.add_argument("--project", type=Path, default=None)
    p.add_argument("--prompt", type=Path, default=None)
    p.add_argument("--sex", default=None, help="male|female when checking a standalone prompt")
    p.add_argument("--character-id", default="CHAR")
    p.add_argument("--kind", default="character", choices=["character", "weapon", "costume", "prop"])
    args = p.parse_args()
    errors: list[str] = []
    if args.project:
        data = json.loads(args.project.read_text(encoding="utf-8"))
        errors.extend(check_project(data))
    if args.prompt:
        text = args.prompt.read_text(encoding="utf-8")
        errors.extend(check_prompt_for_sex(text, args.sex or "", character_id=args.character_id, kind=args.kind))
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print("PASS: identity isolation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
