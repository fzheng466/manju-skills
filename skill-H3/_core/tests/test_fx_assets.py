"""FX / HUD template gates (kind=fx, SHOT-FX-*, ID-OWN on templates)."""
from __future__ import annotations

import unittest

from core.lib.asset_prompt import check_text
from core.lib.identity import check_job_identity
from core.lib.shot_quality import check_fx_bindings, check_job


HUD_OK = (
    "16:9横屏道具结构板。左侧约60%为主图，右侧细节窗。"
    "空面板无字，不出现可读文字。光源从边框与光点槽发出。"
    "不加入人物。禁止整块霓虹。"
)


def test_hud_board_passes():
    err = check_text("hud", HUD_OK, "16:9", owner_id="SHEN_YAN", fx_class="hud")
    assert err == [], err


def test_system_alias_maps_to_hud():
    err = check_text("system", HUD_OK, "16:9", owner_id="SHEN_YAN")
    assert err == [], err


def test_fx_master_rejects_portrait():
    err = check_text("hud", HUD_OK, "9:16", owner_id="SHEN_YAN")
    assert any("identity/prop masters are 16:9" in e for e in err)


def test_fx_rejects_quoted_chinese():
    body = HUD_OK + '面板写着「身份核验完成玩家」'
    err = check_text("hud", body, "16:9", owner_id="SHEN_YAN")
    assert any("ASSET-FX-TEXT" in e for e in err)


def test_fx_requires_owner():
    err = check_text("hud", HUD_OK, "16:9")
    assert any("ID-OWN" in e for e in err)


def test_fx_rejects_neon_and_missing_light():
    neon = "16:9横屏。左侧主图右侧细节。空面板无字。整块霓虹。不加入人物。光点槽。"
    err = check_text("hud", neon, "16:9", owner_id="SHEN_YAN")
    assert any("ASSET-FX-NEON" in e or "ASSET-FX-LIGHT" in e for e in err)
    blob = "16:9横屏。左侧主图右侧细节。空面板无字。很亮。不加入人物。光点槽。"
    err2 = check_text("hud", blob, "16:9", owner_id="SHEN_YAN")
    assert any("ASSET-FX-LIGHT" in e for e in err2)


def test_fx_rejects_people_on_board():
    body = (
        "16:9横屏道具结构板。左侧约60%为主图，右侧细节窗。"
        "空面板无字，不出现可读文字。光源从边框与光点槽发出。"
        "主图里站着一个男人。"
    )
    err = check_text("hud", body, "16:9", owner_id="SHEN_YAN")
    assert any("ASSET-FX-CAST" in e for e in err), err


def test_array_requires_ring_anchor():
    body = (
        "16:9横屏。左侧主图右侧细节。空面板无字。光源从边框发出。不加入人物。"
    )
    err = check_text("array", body, "16:9", owner_id="LIN_WAN", fx_class="array")
    assert any("ASSET-FX-ARRAY" in e for e in err)


def test_shot_fx_asset_missing_and_bound():
    prompt = "16:9横屏。淡蓝色光幕在沈砚眼前展开。"
    job = {"id": "J08", "aspect_ratio": "16:9"}
    err = check_fx_bindings(job, prompt, {})
    assert any("SHOT-FX-ASSET" in e for e in err)
    job2 = {
        "id": "J08",
        "aspect_ratio": "16:9",
        "asset_bindings": [
            {
                "asset_id": "HUD_OWNER_SYSTEM",
                "fx_class": "hud",
                "owner_id": "SHEN_YAN",
                "purpose": "SHEN_YAN 系统面板",
            }
        ],
        "continuity_ledger": {"visible_cast": ["SHEN_YAN"]},
    }
    assets = {
        "HUD_OWNER_SYSTEM": {
            "asset_id": "HUD_OWNER_SYSTEM",
            "kind": "image",
            "asset_role": "fx",
            "fx_class": "hud",
            "owner_id": "SHEN_YAN",
        }
    }
    assert check_fx_bindings(job2, prompt, assets) == []


def test_shot_fx_negation_does_not_trigger():
    prompt = "16:9横屏。不出现系统面板。沈砚低头看积水。"
    assert check_fx_bindings({"id": "J01", "aspect_ratio": "16:9"}, prompt, {}) == []


def test_shot_fx_owner_offscreen():
    prompt = "16:9横屏。光幕展开。"
    job = {
        "id": "J10",
        "aspect_ratio": "16:9",
        "asset_bindings": [
            {"asset_id": "HUD_OWNER_SYSTEM", "fx_class": "hud", "owner_id": "SHEN_YAN"}
        ],
        "continuity_ledger": {"visible_cast": ["LIN_WAN"]},
    }
    assets = {
        "HUD_OWNER_SYSTEM": {
            "kind": "fx",
            "fx_class": "hud",
            "owner_id": "SHEN_YAN",
        }
    }
    err = check_fx_bindings(job, prompt, assets)
    assert any("SHOT-FX-OWNER" in e for e in err)


def test_shot_fx_face():
    prompt = "16:9横屏。光幕挡住脸。"
    job = {
        "id": "J08",
        "aspect_ratio": "16:9",
        "asset_bindings": [
            {"asset_id": "HUD_OWNER_SYSTEM", "fx_class": "hud", "owner_id": "SHEN_YAN"}
        ],
        "continuity_ledger": {"visible_cast": ["SHEN_YAN"]},
    }
    assets = {
        "HUD_OWNER_SYSTEM": {"kind": "fx", "fx_class": "hud", "owner_id": "SHEN_YAN"}
    }
    err = check_job(job, prompt, assets)
    assert any("SHOT-FX-FACE" in e for e in err)


def test_id_own_fx_applied_to_other_character():
    job = {
        "id": "J10",
        "asset_bindings": [
            {
                "asset_id": "HUD_OWNER_SYSTEM",
                "purpose": "挂到 LIN_WAN 身上",
            }
        ],
        "continuity_ledger": {"visible_cast": ["SHEN_YAN", "LIN_WAN"]},
    }
    characters = {
        "SHEN_YAN": {"character_id": "SHEN_YAN", "name": "沈砚", "presentation_sex": "male"},
        "LIN_WAN": {"character_id": "LIN_WAN", "name": "林晚", "presentation_sex": "female"},
    }
    assets = {
        "HUD_OWNER_SYSTEM": {
            "asset_id": "HUD_OWNER_SYSTEM",
            "kind": "fx",
            "fx_class": "hud",
            "owner_id": "SHEN_YAN",
        }
    }
    err = check_job_identity(job, characters, assets)
    assert any("ID-OWN" in e and "LIN_WAN" in e for e in err)


class TestFxAssets(unittest.TestCase):
    pass


for _name, _fn in list(globals().items()):
    if _name.startswith("test_") and callable(_fn) and _name != "TestFxAssets":
        setattr(TestFxAssets, _name, staticmethod(_fn))
