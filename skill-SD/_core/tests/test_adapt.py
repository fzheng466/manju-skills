from core.lib.adapt import preview
from core.lib.guards_channel import check


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
    assert len(p["splits"]) >= 2
    assert len(p["dropped_references"]) == 1
    assert p["audio_post_plan"] is True


def test_aspect_block():
    job = {"duration_seconds": 8}
    eff = {
        "duration_seconds": {"min": 4, "max": 15},
        "conflict": {"type": "aspect_ratio", "project": "16:9", "channel": ["9:16"]},
    }
    p = preview(job, eff)
    assert p["blocked"] is True
    assert p["rule"] == "R-AR-01"


def test_gch2_timeline():
    lock = {"effective": {"duration_seconds": {"min": 4, "max": 10}, "modes": ["T2VA"]}}
    err = check("At 00:12.000 the camera cuts", {"duration_seconds": 10, "mode": "T2VA"}, lock)
    assert any(e.startswith("G-CH2") for e in err)
