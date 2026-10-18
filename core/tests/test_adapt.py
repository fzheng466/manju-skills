from pathlib import Path

from core.lib.adapt import preview
from core.lib.asset_prompt import check_text
from core.lib.channel import merge_effective
from core.lib.guards_channel import check, _max_time_in_text
from core.lib.shot_quality import check_job, check_prompt
from core.lib.identity import check_project, check_prompt_for_sex
from core.lib.transpile import compile_prompt, reconstruct_dialogue


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


def test_split_on_dialogue_end_not_mid_line():
    job = {
        "duration_seconds": 18,
        "shots": [
            {
                "id": "S1",
                "start_seconds": 0,
                "end_seconds": 18,
                "beats": [
                    {"start_seconds": 0, "end_seconds": 6, "action_phase": "起手", "cut_reason": "none"},
                    {"start_seconds": 6, "end_seconds": 10, "action_phase": "收势", "cut_reason": "none"},
                    {"start_seconds": 10, "end_seconds": 18, "action_phase": "反应", "cut_reason": "none"},
                ],
                "dialogue": [
                    {"utterance_id": "U1", "text": "阵眼还在。", "start_seconds": 7.0, "end_seconds": 11.0},
                ],
            }
        ],
    }
    p = preview(job, {"duration_seconds": {"min": 4, "max": 10}})
    assert p["blocked"] is False
    assert all(s.get("fallback") == "beats" for s in p["splits"])
    edges = [s["end"] for s in p["splits"][:-1]]
    assert 11.0 in edges
    assert not any(7.0 < t < 11.0 for t in edges)


def test_split_blocks_when_only_cut_is_inside_line():
    job = {
        "duration_seconds": 18,
        "shots": [
            {
                "beats": [
                    {"start_seconds": 0, "end_seconds": 8, "visible_action": "开口"},
                    {"start_seconds": 8, "end_seconds": 18, "visible_action": "说完"},
                ],
                "dialogue": [
                    {"text": "一句很长的台词", "start_seconds": 1, "end_seconds": 17},
                ],
            }
        ],
    }
    p = preview(job, {"duration_seconds": {"min": 4, "max": 10}})
    assert p["blocked"] is True
    assert p["rule"] == "R-DUR-03"


def test_asset_character_requires_empty_hands_and_structure():
    bad = "生成一张人物图，仙气飘飘，高级感。"
    err = check_text("character", bad, "16:9")
    assert any("ASSET" in e for e in err)
    stuffed = "16:9横屏 四视 肩甲 双手空置 结构计数 战甲很好看"
    assert any("结构计数" in e or "ASSET-CHAR" in e for e in check_text("character", stuffed, "16:9"))
    lexicon = Path(__file__).resolve().parents[1] / "references" / "assets" / "anime-3d-asset-lexicon.md"
    sample = lexicon.read_text(encoding="utf-8")
    armor = sample.split("## 示例 1")[1].split("## 示例 2")[0]
    robe = sample.split("## 示例 2")[1].split("## 示例 3")[0]
    assert check_text("character", armor, "16:9") == []
    assert check_text("character", robe, "16:9") == []
    good = (
        "16:9横屏男性角色四视图设定板。左侧超大正面胸像，右侧正面全身、45°侧面全身、背面全身。"
        "双手空置并离开身体。战甲：胸甲上下两片、肩甲4片、裙甲4片、胫甲。"
    )
    assert check_text("character", good, "16:9") == []


def test_asset_weapon_xianxia_needs_silhouette():
    err = check_text("weapon", "16:9横屏一把发光仙剑，很华丽。", "16:9")
    assert any("ASSET-WPN" in e or "ASSET-VAGUE" in e for e in err)
    wrapped = "16:9横屏 左侧主图 剪影 柄 通体发光，从剑柄流出"
    assert any("ASSET-WPN" in e for e in check_text("weapon", wrapped, "16:9"))
    good = (
        "16:9横屏男性持有者武器资产板，左侧主图完整展示三叉戟剪影，右侧两个细节窗。"
        "握持点在中段缠柄。炼制：寒铁夹层嵌青玉导灵槽，灵力从戟心沿主刃到叉尖发光。"
    )
    assert check_text("weapon", good, "16:9") == []
    scene_cast = "16:9 四向 场景，女主站在门口"
    assert any("ASSET-SCN" in e for e in check_text("scene", scene_cast, "16:9"))


def test_identity_blocks_female_wardrobe_on_male():
    male_ok = (
        "16:9横屏男性角色四视图。正面全身、45°侧面全身、背面全身。双手空置。"
        "成年男性剑修，喉结可见，束冠，胸甲上下两片、肩甲4片。"
    )
    assert check_prompt_for_sex(male_ok, "male", character_id="SHEN") == []
    mixed = male_ok + "抹胸高开衩，细跟高跟鞋与步摇。"
    err = check_prompt_for_sex(mixed, "male", character_id="SHEN")
    assert any("ID-MIX" in e for e in err)
    female_ok = (
        "16:9横屏女性角色四视图。正面全身、45°侧面全身、背面全身。双手空置。"
        "成年女性宗门圣女，无喉结，广袖外袍与腰封。"
    )
    assert check_prompt_for_sex(female_ok, "female", character_id="LIN") == []
    female_bad = female_ok + "喉结明显，胸肌块面。"
    assert any("ID-MIX" in e for e in check_prompt_for_sex(female_bad, "female", character_id="LIN"))
    project = {
        "stage": "draft",
        "characters": [
            {"character_id": "SHEN_YAN", "name": "沈砚", "presentation_sex": "male"},
            {"character_id": "LIN_WAN", "name": "林晚", "presentation_sex": "female"},
        ],
        "assets": [
            {"asset_id": "WPN1", "kind": "weapon", "owner_id": "SHEN_YAN", "presentation_sex": "male", "prompt": "三叉戟剪影 握持点在缠柄"},
            {"asset_id": "COS_BAD", "kind": "costume", "owner_id": "SHEN_YAN", "prompt": "抹胸高开衩步摇细跟"},
        ],
    }
    perr = check_project(project)
    assert any("ID-MIX" in e and "COS_BAD" in e for e in perr)
    orphan = {"stage": "draft", "characters": [{"character_id": "SHEN_YAN", "presentation_sex": "male"}], "assets": [{"asset_id": "WPN2", "kind": "weapon", "prompt": "剑"}]}
    assert any("ID-OWN" in e for e in check_project(orphan))
    earring = check_prompt_for_sex(male_ok + "左耳一枚银耳钉。", "male", character_id="SHEN")
    assert not any("耳钉" in e for e in earring)
    slit = check_prompt_for_sex(male_ok + "外袍下摆高开衩便于跨步。", "male", character_id="SHEN")
    assert not any("高开衩" in e or "ID-MIX" in e for e in slit)
    denied = check_prompt_for_sex(male_ok + "不穿抹胸。", "male", character_id="SHEN")
    assert denied == []
    general = check_prompt_for_sex(
        "16:9横屏女将四视图。正面全身、45°侧面全身、背面全身。双手空置。女将，胸甲上下两片。",
        "female",
        character_id="JIANG",
    )
    assert not any("ID-SEX" in e for e in general)
    costume = {"stage": "draft", "characters": [{"character_id": "SHEN_YAN", "presentation_sex": "male"}], "assets": [{"asset_id": "COS1", "kind": "costume", "prompt": "外袍"}]}
    assert any("ID-OWN" in e for e in check_project(costume))


def test_shot_rejects_vague_acting_and_stacked_moves():
    err = check_prompt("眼神复杂，气场强，镜头推轨然后横移环绕", {"aspect_ratio": "16:9"})
    assert any("SHOT-PERF" in e for e in err)
    assert any("SHOT-CAM" in e for e in err)
    job = {
        "aspect_ratio": "9:16",
        "shots": [
            {
                "performance_plan": {
                    "objective": "压住对方",
                    "concealment": "害怕",
                    "trigger": "刀被按住",
                    "baseline": "唇线闭合",
                    "micro_expression_sequence": ["手指先停", "上眼睑轻抬"],
                    "body_breath": "吸气压回",
                    "listener_reaction": "对方肩一沉",
                    "hold_seconds": 0.4,
                    "end_expression": "眉心仍紧嘴唇闭合",
                },
                "camera_plan": {"movement": "locked", "movement_trigger": "none"},
                "beats": [
                    {
                        "expression": "眉心收紧后上眼睑轻抬",
                        "visible_action": "按住刀脊",
                        "camera": {"framing": "近景"},
                    }
                ],
            }
        ],
    }
    assert check_job(job, "9:16竖屏，两人前后纵深") == []


def test_transpile_keeps_frozen_line_and_strips_h3():
    job = {
        "mode": "T2VA",
        "aspect_ratio": "16:9",
        "duration_seconds": 8,
        "identification_points": ["左眉浅疤", "青玉护心镜"],
        "shots": [
            {
                "id": "S1",
                "start_seconds": 0,
                "end_seconds": 8,
                "purpose": "对峙",
                "camera": "中近景稳定",
                "dialogue": [
                    {
                        "speaker_id": "沈砚",
                        "text": "阵眼还在，别碰那盏灯。",
                        "tone": "压低",
                        "delivery": {"volume": "低", "pace": "慢", "timbre": "压喉"},
                        "pre_line_action": "视线锁灯",
                        "listener_reaction": "林晚手指停在灯侧",
                    }
                ],
            }
        ],
    }
    result = compile_prompt(job, profile="seedance-2.5")
    assert "阵眼还在，别碰那盏灯。" in result["prompt"]
    assert "<d>" not in result["prompt"]
    assert "T2VA" not in result["prompt"]
    assert reconstruct_dialogue(job) == "阵眼还在，别碰那盏灯。"
    assert result["errors"] == []
    leaky = dict(job)
    leaky["shots"] = [
        {
            **job["shots"][0],
            "beats": [{"start_seconds": 0, "end_seconds": 3, "visible_action": "At 00:03.500 举刀", "expression": "眉心收紧"}],
        }
    ]
    leaked = compile_prompt(leaky, profile="seedance-2.5")
    assert "At 00:03.500" not in leaked["prompt"]


def test_gch8_model_mismatch():
    from core.lib.guards_channel import apply_lock_checks

    err = apply_lock_checks(
        {"model_profile": "seedance-2.0", "jobs": []},
        {"model_profile": "minimax-h3", "tracks": {}},
        lambda job: "",
    )
    assert any(e.startswith("G-CH8") for e in err)


def test_transpile_uses_character_name_not_speaker_id():
    job = {
        "mode": "T2VA",
        "aspect_ratio": "16:9",
        "duration_seconds": 8,
        "shots": [
            {
                "id": "S1",
                "start_seconds": 0,
                "end_seconds": 8,
                "purpose": "对峙",
                "dialogue": [{"speaker_id": "shen", "text": "别碰。", "tone": "低"}],
            }
        ],
    }
    named = compile_prompt(
        job,
        profile="seedance-2.5",
        characters=[{"character_id": "SHEN_YAN", "speaker_id": "shen", "name": "沈砚"}],
        lexicon=[],
    )
    assert "沈砚以" in named["prompt"]
    assert "shen以" not in named["prompt"]
    missing = compile_prompt(job, profile="seedance-2.5", characters=[], lexicon=[])
    assert any("G-TR4" in e for e in missing["errors"])
    styled = compile_prompt(
        {**job, "shots": [{**job["shots"][0], "camera": "3D半写实国漫CG PBR材质"}]},
        profile="seedance-2.5",
        characters=[{"speaker_id": "shen", "name": "沈砚"}],
    )
    assert "3D国风动画电影质感" in styled["prompt"]
    assert styled.get("lexicon_applied")


def test_weapon_without_sex_still_identity_checked():
    err = check_text("weapon", "16:9横屏 左侧主图 剪影 握持 柄 步摇", "16:9")
    assert any("ID-SEX" in e or "ID-MIX" in e for e in err)


def test_identity_compiled_prompt_window():
    from core.lib.identity import check_job_identity

    characters = {
        "SHEN_YAN": {"character_id": "SHEN_YAN", "name": "沈砚", "presentation_sex": "male"},
        "LIN_WAN": {"character_id": "LIN_WAN", "name": "林晚", "presentation_sex": "female"},
    }
    bad = check_job_identity({"id": "J1", "prompt": "沈砚戴步摇立于灯前"}, characters, {})
    assert any("ID-MIX" in e for e in bad)
    ok = check_job_identity({"id": "J1", "prompt": "沈砚身旁的林晚戴步摇"}, characters, {})
    assert not any("ID-MIX" in e for e in ok)


def test_identity_negation_but_clause_still_flags():
    mixed = check_prompt_for_sex(
        "16:9横屏男性角色。正面全身、45°侧面全身、背面全身。双手空置。男主，不是抹胸而是抹胸式内衬。",
        "male",
        character_id="SHEN",
    )
    assert any("ID-MIX" in e for e in mixed)


import unittest as _unittest


class TestAll(_unittest.TestCase):
    pass


for _name, _fn in list(globals().items()):
    if _name.startswith("test_") and callable(_fn) and _name != "TestAll":
        setattr(TestAll, _name, staticmethod(_fn))
