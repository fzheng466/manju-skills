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


def test_duration_enum_offers_pad_12_to_15():
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
    assert {o["action"] for o in p["duration_options"]} == {"pad_action", "trim"}
    assert any(str(a).startswith("R-DUR-05") for a in p["actions"])
    err = check_job({**job, "duration_allowed": [5, 10, 15], "aspect_ratio": "9:16"}, "9:16竖屏。")
    assert any("SHOT-DUR-ENUM" in e for e in err)


def test_duration_enum_7s_offers_trim_not_auto_pad():
    job = {"id": "J07", "duration_seconds": 7}
    eff = {
        "duration_seconds": {"min": 4, "max": 15, "allowed": [5, 10, 15]},
        "reference_inputs": {"image": 5},
        "audio_output": "native",
    }
    p = preview(job, eff)
    assert p["blocked"] is False
    assert p["duration_options"] == [{"action": "trim", "duration": 5, "delta_seconds": 2}]


def test_duration_enum_16s_blocks_without_enum_composition():
    job = {"id": "J08", "duration_seconds": 16}
    eff = {
        "duration_seconds": {"min": 4, "max": 15, "allowed": [5, 10, 15]},
        "reference_inputs": {"image": 5},
        "audio_output": "native",
    }
    p = preview(job, eff)
    assert p["blocked"] is True
    assert p["rule"] == "R-DUR-02"
    assert not any(s.get("fallback") == "equal" for s in p["splits"])


def test_audio_alias_dialogue_and_sfx_is_native():
    eff = {
        "duration_seconds": {"min": 4, "max": 15},
        "reference_inputs": {"image": 5},
        "audio_output": "dialogue_and_sfx",
    }
    p = preview({"duration_seconds": 5}, eff)
    assert p["audio_mode"] == "native_text_voice"
    assert not any(str(a).startswith("R-AUD-01") for a in p["actions"])


def test_audio_missing_blocks_without_post_dub_fallback():
    eff = {"duration_seconds": {"min": 4, "max": 15}, "reference_inputs": {"image": 5}}
    p = preview({"duration_seconds": 5}, eff)
    assert p["blocked"] is True
    assert p["rule"] == "R-AUD-00"
    assert not any(str(a).startswith("R-AUD-01") for a in p["actions"])


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


def test_owner_only_readable_with_non_owner_dialogue_fails():
    job = {
        "aspect_ratio": "9:16",
        "fx_state": "readable",
        "visible_cast": ["OWNER_A", "NON_OWNER_B"],
        "continuity_ledger": {"visible_cast": ["OWNER_A", "NON_OWNER_B"]},
        "utterances": [{"speaker_id": "NON_OWNER_B", "text": "怎么了？"}],
        "asset_bindings": [
            {"asset_id": "FX_A", "kind": "fx", "fx_class": "hud", "visibility": "owner_only", "owner_id": "OWNER_A", "ref_role": "fx_shell"}
        ],
    }
    err = check_job(job, "9:16竖屏。OWNER_A 面向 NON_OWNER_B，胸前光幕仍在。")
    assert any("SHOT-FX-VIS" in e for e in err)


def test_owner_only_readable_owner_speaks_without_addressee_fails():
    job = {
        "aspect_ratio": "9:16",
        "fx_state": "readable",
        "visible_cast": ["OWNER_A", "NON_OWNER_B"],
        "utterances": [{"speaker_id": "OWNER_A", "text": "我没事。"}],
        "asset_bindings": [
            {"asset_id": "FX_A", "kind": "fx", "fx_class": "hud", "visibility": "owner_only", "owner_id": "OWNER_A", "ref_role": "fx_shell"}
        ],
    }
    err = check_job(job, "9:16竖屏。")
    assert any("SHOT-FX-ADDR" in e for e in err)


def test_fx_visibility_read_from_asset_record():
    job = {
        "aspect_ratio": "9:16",
        "fx_state": "readable",
        "visible_cast": ["OWNER_A", "NON_OWNER_B"],
        "utterances": [{"speaker_id": "NON_OWNER_B", "addressee_id": "OWNER_A", "text": "怎么了？"}],
        "asset_bindings": [{"asset_id": "FX_A", "ref_role": "fx_shell"}],
    }
    assets = {"FX_A": {"asset_id": "FX_A", "kind": "fx", "visibility": "owner_only", "owner_id": "OWNER_A"}}
    err = check_job(job, "9:16竖屏。", assets)
    assert any("SHOT-FX-VIS" in e for e in err)


def test_owner_looking_at_panel_is_not_a_non_owner_reaction():
    job = {
        "aspect_ratio": "9:16",
        "fx_state": "readable",
        "visible_cast": ["OWNER_A"],
        "asset_bindings": [
            {"asset_id": "FX_A", "kind": "fx", "fx_class": "hud", "visibility": "owner_only", "owner_id": "OWNER_A", "ref_role": "fx_shell"}
        ],
        "shots": [{"beats": [{"actor_id": "OWNER_A", "look_target": "FX_A"}]}],
    }
    err = check_job(job, "9:16竖屏。他看向面板。")
    assert not any("SHOT-FX-VIS" in e for e in err)


def test_owner_only_off_with_non_owner_passes_visibility():
    job = {
        "aspect_ratio": "9:16",
        "fx_state": "off",
        "visible_cast": ["OWNER_A", "NON_OWNER_B"],
        "continuity_ledger": {"visible_cast": ["OWNER_A", "NON_OWNER_B"]},
        "utterances": [{"speaker_id": "NON_OWNER_B", "text": "怎么了？"}],
        "asset_bindings": [
            {"asset_id": "FX_A", "kind": "fx", "fx_class": "hud", "visibility": "owner_only", "owner_id": "OWNER_A", "ref_role": "fx_shell"}
        ],
    }
    err = check_job(job, "9:16竖屏。画面没有光幕。")
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


def test_prop_state_conflict_closed_door():
    job = {
        "aspect_ratio": "9:16",
        "continuity_ledger": {"prop_state": {"PROP_DOOR": "closed"}},
    }
    assets = {"PROP_DOOR": {"asset_id": "PROP_DOOR", "name": "单元门"}}
    err = check_job(job, "9:16竖屏。门开着。", assets)
    assert any("SHOT-PROP-STATE" in e for e in err)


def test_prop_state_legacy_environment_state_covered():
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


def test_first_fx_lookdev_derived_from_project_order():
    project = {
        "jobs": [
            {
                "id": "J1", "episode_start_seconds": 0, "fx_state": "presence",
                "asset_bindings": [{"asset_id": "FX_A", "ref_role": "fx_shell"}],
            },
            {
                "id": "J2", "episode_start_seconds": 10, "fx_state": "readable",
                "asset_bindings": [{"asset_id": "FX_A", "ref_role": "fx_shell"}],
            },
        ]
    }
    err = check_job(project["jobs"][1], "9:16竖屏。", project=project)
    assert any("SHOT-FX-LOOKDEV" in e for e in err)


def test_first_fx_manual_flag_still_blocks():
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


def test_submit_without_lock_is_blocked():
    err = check_job({"aspect_ratio": "9:16"}, "9:16竖屏。", stage="submit")
    assert any("SHOT-LOCK" in e for e in err)


def test_native_audio_from_lock_rejects_post_dub():
    lock = {
        "effective": {
            "audio_output": "native",
            "duration_seconds": {"min": 4, "max": 15},
        }
    }
    err = check_job({"aspect_ratio": "9:16"}, "9:16竖屏。对白交给后期配音。", lock=lock, stage="submit")
    assert any("SHOT-AUD-POST" in e for e in err)


def test_unknown_ref_role_is_rejected():
    job = {
        "aspect_ratio": "9:16",
        "asset_bindings": [{"asset_id": "A", "ref_role": "whatever"}],
    }
    err = check_job(job, "9:16竖屏。")
    assert any("SHOT-REF-ROLE" in e for e in err)


def test_face_unknown_counts_as_true_on_realperson():
    job = {
        "aspect_ratio": "9:16",
        "realperson": True,
        "asset_bindings": [{"asset_id": "FX_A", "ref_role": "fx_lookdev"}],
    }
    err = check_job(job, "9:16竖屏。")
    assert any("SHOT-REF-FACE" in e for e in err)


def test_tail_frame_must_declare_state_when_previous_had_fx():
    project = {
        "jobs": [
            {
                "id": "J1", "episode_start_seconds": 0, "fx_state": "readable",
                "asset_bindings": [{"asset_id": "FX_A", "ref_role": "fx_shell"}],
            },
            {
                "id": "J2", "episode_start_seconds": 10, "fx_state_in": "readable",
                "continuity_ledger": {"previous_job_id": "J1"},
                "asset_bindings": [{"asset_id": "TAIL_A", "ref_role": "tail_frame"}],
            },
        ]
    }
    err = check_job(project["jobs"][1], "9:16竖屏。", project=project)
    assert any("SHOT-REF-INHERIT" in e for e in err)


def test_bare_url_rejected_when_channel_requires_upload():
    lock = {
        "effective": {
            "audio_output": "native",
            "duration_seconds": {"min": 4, "max": 15},
            "reference_transport": "uploaded",
        }
    }
    job = {
        "aspect_ratio": "9:16",
        "asset_bindings": [
            {"asset_id": "FX_A", "ref_role": "fx_shell", "source": "https://example.invalid/fx.png"}
        ],
    }
    err = check_job(job, "9:16竖屏。", lock=lock, stage="submit")
    assert any("SHOT-REF-UPLOAD" in e for e in err)


def test_path_variable_expansion_is_under_test_root():
    import os

    previous = os.environ.get("MANJU_HOME")
    os.environ["MANJU_HOME"] = str(Path.home() / ".manju")
    try:
        job = {
            "aspect_ratio": "9:16",
            "media_path": str(Path.home() / ".manju" / "test-runs" / "x.mp4"),
            "production_root": r"D:\最新版本视频优化skill\cases",
            "test_root": "$MANJU_HOME/test-runs",
        }
        err = check_job(job, "9:16竖屏。")
        assert any("PATH-PROD" in e for e in err)
    finally:
        if previous is None:
            os.environ.pop("MANJU_HOME", None)
        else:
            os.environ["MANJU_HOME"] = previous


def test_missing_production_root_is_blocked():
    job = {"aspect_ratio": "9:16", "media_path": "D:/somewhere/clip.mp4", "test_root": "D:/test-runs"}
    err = check_job(job, "9:16竖屏。")
    assert any("PATH-PROD" in e for e in err)


def test_snapped_duration_needs_user_ack_and_timecodes():
    job = {
        "aspect_ratio": "9:16",
        "duration_seconds": 15,
        "duration_snapped_from": 12,
    }
    err = check_job(job, "9:16竖屏。0.00–12.00秒完成动作。")
    assert any("SHOT-DUR-ACK" in e for e in err)
    acked = {**job, "duration_user_ack": True}
    err2 = check_job(acked, "9:16竖屏。0.00–12.00秒完成动作。")
    assert any("SHOT-DUR-TC" in e for e in err2)


import unittest as _unittest


class TestProductionContract(_unittest.TestCase):
    pass


for _name, _fn in list(globals().items()):
    if _name.startswith("test_") and callable(_fn) and _name != "TestProductionContract":
        setattr(TestProductionContract, _name, staticmethod(_fn))
