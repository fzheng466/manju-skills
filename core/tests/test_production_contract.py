"""Gates from the 2026-10-19 live-action production audit (Opus skill-audit)."""
from __future__ import annotations

from pathlib import Path

from core.lib.adapt import preview
from core.lib.channel import merge_effective
from core.lib.shot_quality import check_job, check_prompt


def test_native_audio_rejects_post_dub():
    job = {"audio_output": "native", "aspect_ratio": "9:16"}
    err = check_prompt("9:16竖屏。对白交给后期配音。", job)
    assert any("SHOT-AUD-POST" in e for e in err)


def test_unknown_audio_blocks_instead_of_stripping():
    baseline = {
        "aspect_ratios": ["9:16"],
        "duration_seconds": {"min": 4, "max": 15},
        "audio_output": "none",
        "reference_inputs": {"image": 5},
        "modes": ["T2VA"],
    }
    channel = {"capabilities": {}}
    eff = merge_effective(baseline, channel, {"aspect_ratio": "9:16"}, {"track_id": "P", "aspect": "9:16"})
    assert eff["audio_output"] == "unknown"
    p = preview({"duration_seconds": 10, "id": "J08"}, eff)
    assert p["blocked"] is True
    assert p["rule"] == "R-AUD-00"
    assert not any(str(a).startswith("R-AUD-01") for a in p.get("actions") or [])


def test_duration_enum_snaps_12_to_15():
    job = {"id": "J06", "duration_seconds": 12}
    eff = {
        "duration_seconds": {"min": 4, "max": 15, "allowed": [5, 10, 15]},
        "reference_inputs": {"image": 5},
        "audio_output": "native",
        "aspect": "9:16",
    }
    p = preview(job, eff)
    assert p["blocked"] is False
    assert p.get("snapped_duration") == 15
    assert any(str(a).startswith("R-DUR-03") for a in p["actions"])
    err = check_job({**job, "duration_allowed": [5, 10, 15], "aspect_ratio": "9:16"}, "9:16竖屏。")
    assert any("SHOT-DUR-ENUM" in e for e in err)


def test_scene_master_binding_rejected():
    job = {
        "aspect_ratio": "9:16",
        "asset_bindings": [{"asset_id": "BALCONY", "ref_role": "scene_master", "binding_method": "attached_reference"}],
    }
    err = check_job(job, "9:16竖屏。")
    assert any("SHOT-REF-GRID" in e for e in err)


def test_face_composite_rejected_on_realperson():
    job = {
        "aspect_ratio": "9:16",
        "realperson": True,
        "asset_bindings": [
            {"asset_id": "HUD_B", "ref_role": "fx_lookdev", "contains_face": True, "binding_method": "attached_reference"}
        ],
    }
    err = check_job(job, "9:16竖屏。")
    assert any("SHOT-REF-FACE" in e for e in err)


def test_owner_only_readable_with_mother_dialogue_fails():
    job = {
        "aspect_ratio": "9:16",
        "fx_state": "readable",
        "visible_cast": ["CHEN_HAN", "LIU_GUIFANG"],
        "continuity_ledger": {"visible_cast": ["CHEN_HAN", "LIU_GUIFANG"]},
        "utterances": [{"speaker_id": "LIU_GUIFANG", "text": "咋了？"}],
        "asset_bindings": [
            {"asset_id": "HUD", "kind": "fx", "fx_class": "hud", "visibility": "owner_only", "owner_id": "CHEN_HAN", "ref_role": "fx_shell"}
        ],
    }
    err = check_job(job, "9:16竖屏。陈汉对着母亲说话，胸前光幕仍在。")
    assert any("SHOT-FX-VIS" in e for e in err)


def test_owner_only_off_with_mother_passes_visibility():
    job = {
        "aspect_ratio": "9:16",
        "fx_state": "off",
        "visible_cast": ["CHEN_HAN", "LIU_GUIFANG"],
        "continuity_ledger": {"visible_cast": ["CHEN_HAN", "LIU_GUIFANG"]},
        "utterances": [{"speaker_id": "LIU_GUIFANG", "text": "咋了？"}],
        "asset_bindings": [
            {"asset_id": "HUD", "kind": "fx", "fx_class": "hud", "visibility": "owner_only", "owner_id": "CHEN_HAN", "ref_role": "fx_shell"}
        ],
    }
    err = check_job(job, "9:16竖屏。陈汉对着母亲说话，画面没有光幕。")
    assert not any("SHOT-FX-VIS" in e for e in err)


def test_confirmed_readable_tier_allows_large_panel():
    job = {
        "aspect_ratio": "9:16",
        "fx_state": "readable",
        "fx_tier_confirmed": {"max_fx_percent": 45, "max_person_percent": 58},
        "visible_cast": ["CHEN_HAN"],
    }
    prompt = (
        "9:16竖屏。陈汉约占画面高度54%。"
        "面板高度约为画面高度的42%，位于下巴以下。"
    )
    err = check_prompt(prompt, job)
    assert not any("SHOT-FX-TIER" in e or "SHOT-FX-UI" in e for e in err)


def test_unconfirmed_portrait_panel_40_fails_tier():
    job = {"aspect_ratio": "9:16"}
    prompt = (
        "9:16竖屏。陈汉约占画面高度54%。"
        "面板高度约为画面高度的40%，位于下巴以下。"
    )
    err = check_prompt(prompt, job)
    assert any("SHOT-FX-TIER" in e or "SHOT-FX-UI" in e for e in err)


def test_turn_without_collapse_fails_body_gate():
    job = {
        "aspect_ratio": "9:16",
        "asset_bindings": [{"asset_id": "HUD", "kind": "fx", "fx_class": "hud", "ref_role": "fx_shell"}],
    }
    fail = check_prompt("9:16竖屏。陈汉转身回头，胸前光幕仍在。", job)
    assert any("SHOT-FX-BODY" in e for e in fail)
    ok = check_prompt("9:16竖屏。陈汉转身回头，光幕收到余光。", job)
    assert not any("SHOT-FX-BODY" in e for e in ok)


def test_tail_frame_inherit_mismatch():
    job = {
        "aspect_ratio": "9:16",
        "fx_state_in": "off",
        "asset_bindings": [{"asset_id": "TAIL", "ref_role": "tail_frame", "fx_state": "readable"}],
    }
    err = check_job(job, "9:16竖屏。")
    assert any("SHOT-REF-INHERIT" in e for e in err)


def test_prop_state_conflict_inverted_bowl():
    job = {
        "aspect_ratio": "9:16",
        "continuity_ledger": {"environment_state": "covered"},
    }
    err = check_job(job, "9:16竖屏。桌上倒扣着一只空碗。")
    assert any("SHOT-PROP-STATE" in e for e in err)


def test_home_media_path_outside_production_root():
    home = Path.home()
    job = {
        "aspect_ratio": "9:16",
        "media_path": str(home / ".manju" / "test-runs" / "clip.mp4"),
        "production_root": r"D:\最新版本视频优化skill\cases",
        "test_root": str(home / ".manju" / "test-runs"),
    }
    err = check_job(job, "9:16竖屏。")
    assert any("PATH-PROD" in e for e in err)


def test_first_fx_without_lookdev_blocked():
    job = {"aspect_ratio": "9:16", "fx_first_appearance": True}
    err = check_job(job, "9:16竖屏。")
    assert any("SHOT-FX-LOOKDEV" in e for e in err)


def test_dialogue_needs_voice_profile_when_native():
    job = {
        "aspect_ratio": "9:16",
        "audio_output": "native",
        "utterances": [{"speaker_id": "CHEN_HAN", "text": "妈——"}],
    }
    err = check_job(job, "9:16竖屏。陈汉说话。")
    assert any("SHOT-AUD-VOICE" in e for e in err)
