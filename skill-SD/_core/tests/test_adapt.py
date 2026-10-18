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
    p = preview(job, eff)
    assert p["blocked"] is True
    assert p["rule"] == "R-AR-01"


def test_merge_aspect_conflict_when_intersection_empty():
    baseline = {
        "aspect_ratios": ["16:9"],
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
    eff = merge_effective(baseline, channel, {"aspect_ratio": "16:9"})
    assert eff["conflict"] and eff["conflict"]["type"] == "aspect_ratio"
    assert eff["reference_inputs"]["image"] == 0
    assert "Ref2VA" not in eff["modes"]


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
