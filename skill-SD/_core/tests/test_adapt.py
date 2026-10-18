from core.lib.adapt import preview
from core.lib.channel import merge_effective
from core.lib.guards_channel import check, _max_time_in_text


def test_split_10s_channel():
    job = {"duration_seconds": 18, "references": ["a", "b", "c"], "mode": "T2VA"}
    eff = {
        "duration_seconds": {"min": 4, "max": 10},
        "reference_inputs": {"image": 2},
        "audio_output": "none",
        "modes": ["T2VA"],
    }
    p = preview(job, eff)
    assert p["blocked"] is False
    assert len(p["splits"]) == 2
    assert all(s["end"] - s["start"] >= 4 for s in p["splits"])
    assert len(p["dropped_references"]) == 1
    assert p["audio_post_plan"] is True


def test_split_does_not_emit_illegal_short_piece():
    job = {"duration_seconds": 10.5}
    eff = {"duration_seconds": {"min": 4, "max": 10}}
    p = preview(job, eff)
    assert p["blocked"] is False
    assert all(4 <= s["end"] - s["start"] <= 10.001 for s in p["splits"])


def test_aspect_block():
    job = {"duration_seconds": 8}
    eff = {
        "duration_seconds": {"min": 4, "max": 15},
        "conflict": {"type": "aspect_ratio", "project": "16:9", "channel": ["9:16"]},
    }
    p = preview(job, {**eff, "track_id": "L", "aspect": "16:9", "status": "unsupported_by_channel"})
    assert p["blocked"] is True
    assert p["rule"] == "R-AR-01"
    assert "derivative" in p["choices"]


def test_merge_aspect_conflict_when_intersection_empty():
    baseline = {
        "aspect_ratios": ["16:9", "9:16"],
        "duration_seconds": {"min": 4, "max": 15},
        "reference_inputs": {"image": 9, "video": 3, "audio": 3, "total": 12},
        "modes": ["T2VA", "Ref2VA"],
        "audio_output": "dialogue_and_sfx",
    }
    channel = {
        "capabilities": {
            "aspect_ratios": {"value": ["9:16"]},
            "duration_seconds": {"value": {"min": 4, "max": 10}},
            "reference_inputs": {"value": {"image": 0}},
        }
    }
    landscape = merge_effective(baseline, channel, {"aspect_ratio": "16:9"}, {"track_id": "L", "aspect": "16:9"})
    portrait = merge_effective(baseline, channel, {"aspect_ratio": "9:16"}, {"track_id": "P", "aspect": "9:16"})
    assert landscape["status"] == "unsupported_by_channel"
    assert landscape["conflict"] and landscape["conflict"]["type"] == "aspect_ratio"
    assert portrait["status"] == "ok"
    assert portrait["aspect"] == "9:16"
    assert "Ref2VA" not in landscape["modes"]


def test_gch3_ignores_frame_anchors():
    lock = {"effective": {"duration_seconds": {"min": 4, "max": 10}, "reference_inputs": {"image": 1}, "modes": ["FL2VA"]}}
    job = {
        "duration_seconds": 8,
        "mode": "FL2VA",
        "inputs": [
            {"role": "first_frame", "asset_id": "a"},
            {"role": "last_frame", "asset_id": "b"},
        ],
    }
    err = check("", job, lock)
    assert not any(e.startswith("G-CH3") for e in err)


def test_gch2_real_h3_timestamp_not_false_positive():
    assert _max_time_in_text("At 00:03.500") == 3.5
    assert _max_time_in_text("0.00–1.60秒") == 1.6
    lock = {"effective": {"duration_seconds": {"min": 4, "max": 10}, "modes": ["T2VA"]}}
    err = check("At 00:03.500 the camera cuts", {"duration_seconds": 8, "mode": "T2VA"}, lock)
    assert not any(e.startswith("G-CH2") for e in err)


def test_gch2_timeline_true_overrun():
    lock = {"effective": {"duration_seconds": {"min": 4, "max": 10}, "modes": ["T2VA"]}}
    err = check("At 00:12.000 the camera cuts", {"duration_seconds": 10, "mode": "T2VA"}, lock)
    assert any(e.startswith("G-CH2") for e in err)


def test_gch6_portrait_prompt_cannot_say_landscape():
    lock = {
        "tracks": {
            "P": {"track_id": "P", "aspect": "9:16", "status": "ok", "duration_seconds": {"min": 4, "max": 10}, "modes": ["T2VA"]},
        }
    }
    job = {"id": "J1", "track_id": "P", "aspect_ratio": "9:16", "duration_seconds": 8, "mode": "T2VA"}
    err = check("16:9横屏，两人并排", job, lock)
    assert any("G-CH6" in e for e in err)
    err_ok = check("9:16竖屏，两人前后纵深", job, lock)
    assert not any("G-CH6" in e for e in err_ok)


def test_lock_tracks_pause_only_unsupported_line():
    from core.lib.guards_channel import apply_lock_checks

    lock = {
        "model_profile": "minimax-h3",
        "tracks": {
            "L": {
                "track_id": "L",
                "aspect": "16:9",
                "status": "unsupported_by_channel",
                "conflict": {"type": "aspect_ratio", "channel": ["9:16"]},
            },
            "P": {
                "track_id": "P",
                "aspect": "9:16",
                "status": "ok",
                "duration_seconds": {"min": 4, "max": 10},
                "modes": ["T2VA"],
            },
        },
    }
    project = {
        "model_profile": "minimax-h3",
        "jobs": [
            {"id": "JL", "track_id": "L", "aspect_ratio": "16:9", "duration_seconds": 8, "mode": "T2VA"},
            {"id": "JP", "track_id": "P", "aspect_ratio": "9:16", "duration_seconds": 8, "mode": "T2VA"},
        ],
    }
    err = apply_lock_checks(project, lock, lambda job: "9:16竖屏" if job["id"] == "JP" else "16:9横屏")
    assert any("JL" in e and "G-CH6" in e for e in err)
    assert not any("JP" in e for e in err)


def test_gch5_silent_channel_blocks_h3_sound_fields():
    lock = {"effective": {"audio_output": "none", "duration_seconds": {"min": 4, "max": 10}, "modes": ["T2VA"]}}
    prompt = "overall_soundscape: 石室滴水\nnon_diegetic_music: 低弦\n<d>[Chinese] 别碰那盏灯。</d>"
    err = check(prompt, {"duration_seconds": 8, "mode": "T2VA"}, lock)
    assert any(e.startswith("G-CH5") for e in err)


def test_gch8_model_mismatch():
    from core.lib.guards_channel import apply_lock_checks

    err = apply_lock_checks(
        {"model_profile": "seedance-2.0", "jobs": []},
        {"model_profile": "minimax-h3", "tracks": {}},
        lambda job: "",
    )
    assert any(e.startswith("G-CH8") for e in err)
