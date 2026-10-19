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
    eff = {"duration_seconds": {"min": 4, "max": 10}, "audio_output": "none"}
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
    p = preview(job, {"duration_seconds": {"min": 4, "max": 10}, "audio_output": "none"})
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
    p = preview(job, {"duration_seconds": {"min": 4, "max": 10}, "audio_output": "none"})
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
                    "suppression": "把惊讶压回嘴唇闭合",
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


def test_portrait_near_gate():
    from core.lib.shot_quality import check_prompt, PORTRAIT_BOILERPLATE

    old = (
        "9:16竖屏。齐胸高机位。0.00–2.00秒，<Subject 1> 从巷子中段沿纵深走向镜头，约占画面高度60%。"
        "镜头缓慢推近到中近景，约占画面高度75%。"
    )
    err = check_prompt(old, {"aspect_ratio": "9:16"})
    assert any("walk-toward-camera" in e for e in err)
    assert any("中近景" in e or "face-in-lens" in e for e in err)
    assert any("SHOT-REF" in e for e in err)
    fixed = (
        PORTRAIT_BOILERPLATE
        + "9:16竖屏。齐腰高平视，略长焦。0.00–2.00秒，<Subject 1> 从巷子深处沿纵深走来，约占画面高度40%，"
        "走到离镜头约3米处停住，约占画面高度56%。头顶上方留出约12%的空间。"
        "参考图只锁定身份，不决定构图。"
    )
    assert check_prompt(fixed, {"aspect_ratio": "9:16"}) == []
    peaky = (
        PORTRAIT_BOILERPLATE
        + "9:16竖屏。参考图只锁定身份，不决定构图。头顶上方留出约12%的空间。"
        "起步约占画面高度40%，停步约占画面高度62%，结尾约占画面高度56%。"
    )
    err_peak = check_prompt(peaky, {"aspect_ratio": "9:16"})
    assert any("peaks" in e for e in err_peak)


def test_onscreen_text_facing_hud_and_fourview():
    from core.lib.shot_quality import check_prompt

    long_txt = (
        "16:9横屏。手机屏幕上清楚显示："
        "\"兄弟，钱的事过阵子一定给你说法。尊敬的客户余额很多很多字。\""
    )
    assert any("SHOT-TEXT" in e for e in check_prompt(long_txt, {"aspect_ratio": "16:9"}))
    overlay = long_txt.replace("清楚显示", "文字内容后期叠加，屏幕只需亮度与排版清楚。清楚显示")
    overlay = (
        "16:9横屏。屏幕亮起两行消息的版式，文字内容后期叠加；画面中屏幕只需亮度与排版清楚。"
        "\"兄弟，钱的事过阵子一定给你说法。尊敬的客户余额很多很多字。\""
    )
    assert not any("SHOT-TEXT" in e for e in check_prompt(overlay, {"aspect_ratio": "16:9"}))
    away = "16:9横屏。沈砚三分之二背对镜头，表情从茫然变成哭笑不得，嘴角扯开。"
    assert any("SHOT-PERF" in e for e in check_prompt(away, {"aspect_ratio": "16:9"}))
    reverse = away + " At 00:02.000, the camera cuts to 中近景反打。"
    assert not any("SHOT-PERF" in e for e in check_prompt(reverse, {"aspect_ratio": "16:9"}))
    four = "16:9横屏。由沈砚16:9四视图主板锁定身份。"
    assert any("画面中只出现一个沈砚" in e for e in check_prompt(four, {"aspect_ratio": "16:9"}))
    four_ok = four + "画面中只出现一个沈砚。"
    assert not any("SHOT-REF: four-view" in e for e in check_prompt(four_ok, {"aspect_ratio": "16:9"}))
    hud = "16:9横屏。透过半透明界面看沈砚的脸。"
    assert any("SHOT-HUD" in e for e in check_prompt(hud, {"aspect_ratio": "16:9"}))
    hud_ok = "16:9横屏。从界面背面只看到发光边框，文字不可见，透过半透明界面看沈砚的脸。"
    assert not any("SHOT-HUD" in e for e in check_prompt(hud_ok, {"aspect_ratio": "16:9"}))
    dist = "9:16竖屏。人物停步离镜头约3米。机位在右肩后方约1.5米。"
    # not a compiled portrait job (no height / Shot) so SHOT-REF boilerplate skipped; distance still fires
    from core.lib.shot_quality import check_boilerplate_distance_conflict

    assert any("3m conflicts" in e for e in check_boilerplate_distance_conflict(dist))


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
    missing = compile_prompt(job, profile="seedance-2.5", characters=[], lexicon=None)
    assert any(e.startswith("G-TR") for e in missing["errors"])
    missing_id = compile_prompt(job, profile="seedance-2.5", characters=[], lexicon=[("x", "y")])
    assert any("G-TR4" in e for e in missing_id["errors"])
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


def test_weapon_silhouette_only_fails():
    err = check_text("weapon", "16:9横屏 左侧主图 剪影 柄", "16:9")
    assert any("ASSET-WPN" in e for e in err)


def test_master_assets_reject_portrait_aspect():
    board = (
        "9:16竖屏男性角色四视图。正面全身、45°侧面全身、背面全身。双手空置。喉结可见。"
    )
    err = check_text("character", board, "9:16", sex="male", character_id="OWNER_A")
    assert any("identity/prop masters are 16:9" in e for e in err)
    scene = "9:16竖屏场景四向结构板。【四向】正向。"
    assert any("derivative-of" in e for e in check_text("scene", scene, "9:16"))
    crop = "9:16竖屏场景裁切说明。【四向】正向。不加入人物。"
    assert not any("derivative-of" in e for e in check_text("scene", crop, "9:16", derivative_of="SCENE_ALLEY"))


def test_scene_cast_catches_man_without_zhan_zai():
    scene = "16:9横屏场景四向结构板。【四向】正向。一个瘦男人提着酒瓶。"
    err = check_text("scene", scene, "16:9")
    assert any("男人" in e for e in err)
    empty = "16:9横屏场景四向结构板。【结构板规则】不加入人物，不出现任何人影。【四向】正向。"
    assert check_text("scene", empty, "16:9") == []


def test_identity_signature_cross():
    from core.lib.identity import check_signature_cross, check_project

    characters = {
        "OWNER_A": {
            "character_id": "OWNER_A",
            "name": "角色A",
            "presentation_sex": "male",
            "prompt": "【识别点】①黑框方形眼镜，左侧镜腿中段用白色医用胶布缠了三圈。深橄榄绿旧夹克。",
        },
        "NON_OWNER_B": {
            "character_id": "NON_OWNER_B",
            "name": "角色B",
            "presentation_sex": "female",
            "prompt": "【识别点】①指甲缝花土。藏青围裙。",
        },
    }
    mixed = "16:9横屏女性，角色B，深橄榄绿旧夹克，黑框眼镜胶布。正面全身、45°侧面全身、背面全身。双手空置。"
    err = check_signature_cross(mixed, "NON_OWNER_B", characters)
    assert any("ID-SIG" in e and "OWNER_A" in e for e in err)
    project = {
        "stage": "draft",
        "characters": [
            {**characters["OWNER_A"]},
            {**characters["NON_OWNER_B"], "prompt": mixed},
        ],
    }
    assert any("ID-SIG" in e for e in check_project(project))


def test_urban_xianxia_fx_and_speaker_order():
    from core.lib.shot_quality import check_prompt, check_speaker_order
    from core.lib.aspect_sync import compare_pair

    urban = "16:9横屏，当代北方工业城市。一层灵力法阵在眼前展开，符文流转。"
    err = check_prompt(urban, {"aspect_ratio": "16:9", "genre": "urban"})
    assert any("SHOT-GENRE" in e for e in err)
    hud = "16:9横屏，当代北方工业城市。淡蓝色半透明扁平矩形界面，像手机全息投影。"
    assert not any("SHOT-GENRE" in e for e in check_prompt(hud, {"aspect_ratio": "16:9", "genre": "urban"}))
    bad_sx = "角色B (S2)，<d>[Chinese] 怎么了？</d> 角色A (S1)，<d>[Chinese] 我没事。</d>"
    assert any("H3-SX" in e for e in check_speaker_order(bad_sx))
    good_sx = "角色B (S1)，<d>[Chinese] 怎么了？</d> 角色A (S2)，<d>[Chinese] 我没事。</d>"
    assert check_speaker_order(good_sx) == []
    l = "巷口左侧一根锈蚀的铁皮路灯杆"
    p = "画面中轴一根锈蚀的铁皮路灯杆"
    assert any("ASPECT-SYNC" in e for e in compare_pair(l, p, scene_id="ALLEY"))
    p2 = "巷口左侧一根锈蚀的铁皮路灯杆，裁窗向左偏移"
    assert compare_pair(l, p2, scene_id="ALLEY") == []


import unittest as _unittest


class TestAll(_unittest.TestCase):
    pass


for _name, _fn in list(globals().items()):
    if _name.startswith("test_") and callable(_fn) and _name != "TestAll":
        setattr(TestAll, _name, staticmethod(_fn))
