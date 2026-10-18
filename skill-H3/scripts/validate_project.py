#!/usr/bin/env python3
"""Validate a MiniMax H3 comic-drama project manifest without calling a provider."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


PIPELINE = "minimax-h3"
MODES = {"T2VA", "I2VA", "L2VA", "FL2VA", "Ref2VA"}
OFFICIAL_MIN_DURATION = 4
OFFICIAL_MAX_DURATION = 15
OFFICIAL_REF_LIMITS = {"image": 9, "video": 3, "audio": 3, "total": 12}
JOB_STATUSES = {"planned", "assets-ready", "submitted", "generated", "reviewed"}
PRODUCTION_STATUSES = {"submitted", "generated", "reviewed"}
CAMERA_PLAN_FIELDS = (
    "start_composition", "camera_position", "height_angle", "lens_intent", "movement",
    "movement_trigger", "movement_path_speed", "movement_end", "end_composition", "cut_policy",
)
PERFORMANCE_PLAN_FIELDS = (
    "objective", "concealment", "trigger", "baseline", "micro_expression_sequence",
    "body_breath", "listener_reaction", "hold_seconds", "end_expression",
)
BEAT_FIELDS = ("focus", "visible_action", "positions", "gaze", "expression", "camera", "audio", "end_state")
BEAT_FRAMING_FIELDS = ("viewpoint", "cut_reason")
DIALOGUE_FIELDS = (
    "pre_line_action", "delivery", "pause_plan", "stress", "cadence_end",
    "post_line_reaction", "listener_reaction",
)
CONTINUITY_LEDGER_FIELDS = (
    "world_axis", "focus_owner", "visible_cast", "screen_positions", "body_and_gaze",
    "hands_and_props", "costume_damage", "environment_state", "lighting_state",
    "sound_tail", "action_phase", "transition_reason", "previous_job_id",
)
DELIVERY_FIELDS = ("volume", "timbre", "pace", "emotional_intensity", "expression_strategy")
FORBIDDEN_PROMPT_PATTERNS = (
    (re.compile(r"【(?:音效|台词|配乐)：|\[SFX:", re.I), "Seedance prompt syntax found in H3 prompt"),
    (re.compile(r"【(?:画幅风格|核心人物|场景资产|站位声明|接续状态|音效|配乐)】"), "non-H3 workflow block found in H3 prompt"),
)
DIALOGUE_BLOCK_RE = re.compile(r"<d>(.*?)</d>", re.S)
LANGUAGE_MARKER_RE = re.compile(r"^\[[^\]]+\]\s*")


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _valid_screen_height_percent(value: Any) -> bool:
    """Visible subjects must occupy a meaningful, bounded share of frame height."""
    return _number(value) and 0 < value <= 100


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _require_fields(value: Any, fields: tuple[str, ...], label: str, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{label}: must be an object")
        return None
    for field in fields:
        if not _present(value.get(field)):
            errors.append(f"{label}.{field} is required")
    return value


def _readable_file(root: Path, raw: Any, label: str, errors: list[str], required: bool = True) -> Path | None:
    if raw in (None, ""):
        if required:
            errors.append(f"{label}: missing path")
        return None
    if not isinstance(raw, str):
        errors.append(f"{label}: path must be a string")
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        errors.append(f"{label}: file does not exist: {raw}")
        return None
    return path


def validate_prompt_text(prompt_text: str, mode: str) -> list[str]:
    errors: list[str] = []
    for pattern, message in FORBIDDEN_PROMPT_PATTERNS:
        if pattern.search(prompt_text):
            errors.append(message)
    fields = {
        "subject_definitions", "summary", "retention_analysis", "detailed_description",
        "integrated_multimodal_description", "overall_soundscape", "non_diegetic_music",
    }
    found_fields = []
    for line in prompt_text.splitlines():
        match = re.match(r"^\s*([a-z_]+)\s*:", line)
        if match and match.group(1) in fields:
            found_fields.append(match.group(1))
    expected_fields = (
        ["subject_definitions", "summary", "retention_analysis", "detailed_description", "overall_soundscape", "non_diegetic_music"]
        if mode == "Ref2VA"
        else ["integrated_multimodal_description", "overall_soundscape", "non_diegetic_music"]
    )
    if found_fields != expected_fields:
        errors.append(f"prompt fields/order do not match {mode}")
    first_content = prompt_text.lstrip().splitlines()[0] if prompt_text.strip() else ""
    required_prefix = {"I2VA": "I2VA:", "L2VA": "L2VA:", "FL2VA": "FL2VA:"}.get(mode)
    if required_prefix and not first_content.startswith(required_prefix):
        errors.append(f"{mode} prompt must start with its frame instruction line")
    if mode in {"T2VA", "Ref2VA"} and re.match(r"^(?:I2VA|L2VA|FL2VA):", first_content):
        errors.append(f"{mode} prompt must not start with a frame instruction line")
    return errors


def validate_prompt_dialogue(prompt_text: str, dialogue: list[dict[str, Any]]) -> list[str]:
    """Every <d> block in the compiled prompt must reproduce the frozen shot dialogue verbatim.

    The prompt is what the model actually reads, so a line mistyped here silently corrupts
    the frozen script even when project.json is internally consistent. Blocks are compared
    one-to-one in order against dialogue[].text.
    """
    errors: list[str] = []
    if not isinstance(dialogue, list):
        return errors
    blocks = [LANGUAGE_MARKER_RE.sub("", block.strip()) for block in DIALOGUE_BLOCK_RE.findall(prompt_text)]
    expected = [line.get("text") for line in dialogue if isinstance(line, dict)]
    if len(blocks) != len(expected):
        errors.append(
            f"compiled prompt has {len(blocks)} <d> dialogue block(s) but the shot has {len(expected)} frozen line(s)"
        )
    for index, (block, text) in enumerate(zip(blocks, expected)):
        if isinstance(text, str) and block != text:
            errors.append(
                f"compiled prompt dialogue[{index}] does not match the frozen utterance text"
            )
    return errors


def validate_project(data: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    schema_version = data.get("schema_version")
    if schema_version not in {"1.0", "1.1", "1.2"}:
        errors.append("schema_version: expected '1.0', '1.1', or '1.2'")
    schema_1_1 = schema_version in {"1.1", "1.2"}
    schema_1_2 = schema_version == "1.2"
    if not data.get("project_id") or not data.get("title"):
        errors.append("project_id and title are required")
    if data.get("pipeline") != PIPELINE or data.get("model_profile") != PIPELINE:
        errors.append(f"pipeline and model_profile must both be '{PIPELINE}'")
    if data.get("aspect_ratio") != "16:9":
        errors.append("aspect_ratio must be '16:9'")
    stage = data.get("stage")
    if stage not in {"draft", "submit"}:
        errors.append("stage must be 'draft' or 'submit'")
        stage = "draft"
    if stage == "submit" and not schema_1_2:
        errors.append("submit requires schema_version '1.2' with framing and viewpoint fields")

    capability = data.get("capability")
    if stage == "submit":
        authorization = data.get("generation_authorization")
        if not isinstance(authorization, dict) or authorization.get("authorized_by_user") is not True:
            errors.append("submit requires explicit user authorization for generation")
        else:
            if not isinstance(authorization.get("evidence"), str) or not authorization["evidence"].strip():
                errors.append("generation_authorization.evidence is required for submit")
            budget = authorization.get("budget_limit")
            if not isinstance(budget, dict) or not _number(budget.get("amount")) or budget["amount"] < 0 or not isinstance(budget.get("unit"), str) or not budget["unit"].strip():
                errors.append("generation_authorization.budget_limit requires a non-negative amount and unit for submit")
        if not isinstance(capability, dict):
            errors.append("submit requires a current capability record")
        else:
            for field in ("provider", "model_id", "checked_at", "evidence_uri"):
                if not capability.get(field):
                    errors.append(f"capability.{field} is required for submit")
            aspect_ratios = capability.get("aspect_ratios")
            if not isinstance(aspect_ratios, list) or "16:9" not in aspect_ratios:
                errors.append("capability must explicitly confirm 16:9")
            if not isinstance(capability.get("supported_modes"), list):
                errors.append("capability.supported_modes must be a list")
            if not isinstance(capability.get("supported_input_roles"), list):
                errors.append("capability.supported_input_roles must be a list")
            if not _number(capability.get("min_duration_seconds")) or capability["min_duration_seconds"] < 0:
                errors.append("capability.min_duration_seconds must be a non-negative number")
            if not _number(capability.get("max_duration_seconds")) or capability["max_duration_seconds"] <= 0:
                errors.append("capability.max_duration_seconds must be a positive number")
            if _number(capability.get("min_duration_seconds")) and _number(capability.get("max_duration_seconds")) and capability["min_duration_seconds"] > capability["max_duration_seconds"]:
                errors.append("capability minimum duration cannot exceed its maximum")

    assets = data.get("assets")
    if not isinstance(assets, list):
        errors.append("assets must be a list")
        assets = []
    asset_by_id: dict[str, dict[str, Any]] = {
        asset["asset_id"]: asset for asset in assets
        if isinstance(asset, dict) and isinstance(asset.get("asset_id"), str) and asset.get("asset_id")
    }
    raw_jobs = data.get("jobs") if isinstance(data.get("jobs"), list) else []
    job_by_id = {
        job.get("id"): job for job in raw_jobs
        if isinstance(job, dict) and isinstance(job.get("id"), str)
    }
    seen_asset_ids: set[str] = set()
    for i, asset in enumerate(assets):
        if not isinstance(asset, dict) or not isinstance(asset.get("asset_id"), str) or not asset.get("asset_id"):
            errors.append(f"assets[{i}]: expected an object with asset_id")
            continue
        aid = asset["asset_id"]
        if aid in seen_asset_ids:
            errors.append(f"assets: duplicate asset_id {aid}")
        seen_asset_ids.add(aid)
        asset_by_id[aid] = asset
        if asset.get("status") not in {"planned", "candidate", "approved", "stale", "rejected"}:
            errors.append(f"asset {aid}: invalid status")
        if asset.get("aspect_ratio") not in (None, "16:9"):
            errors.append(f"asset {aid}: aspect_ratio must be 16:9 when specified")
        frame_source = asset.get("frame_source")
        if asset.get("kind") == "video" and asset.get("archived") is True:
            generated_by = asset.get("generated_by_job_id")
            source_job = job_by_id.get(generated_by)
            if source_job is None or source_job.get("status") != "reviewed":
                errors.append(f"asset {aid}: archived video must point to a reviewed generated_by_job_id")
            if not _number(asset.get("duration_seconds")) or asset["duration_seconds"] <= 0:
                errors.append(f"asset {aid}: archived video must declare a positive duration_seconds")
            if stage == "submit":
                _readable_file(root, asset.get("path"), f"archived video {aid}", errors)
        if frame_source is not None:
            if asset.get("kind") != "image":
                errors.append(f"asset {aid}: video frame asset must have kind 'image'")
            if asset.get("aspect_ratio") != "16:9":
                errors.append(f"asset {aid}: extracted frame must explicitly declare 16:9")
            if asset.get("frame_role") not in {"first_frame", "last_frame"}:
                errors.append(f"asset {aid}: frame_role must be first_frame or last_frame")
            if not isinstance(frame_source, dict):
                errors.append(f"asset {aid}: frame_source must be an object")
            else:
                source_id = frame_source.get("video_asset_id")
                source_job_id = frame_source.get("source_job_id")
                source_video = asset_by_id.get(source_id)
                source_job = job_by_id.get(source_job_id)
                time_seconds = frame_source.get("time_seconds")
                if source_video is None or source_video.get("kind") != "video":
                    errors.append(f"asset {aid}: frame_source.video_asset_id must reference a declared video asset")
                else:
                    if source_video.get("archived") is not True:
                        errors.append(f"asset {aid}: frame source video must be archived")
                    if source_video.get("generated_by_job_id") != source_job_id:
                        errors.append(f"asset {aid}: frame source job does not match video generated_by_job_id")
                    if source_video.get("status") != "approved":
                        errors.append(f"asset {aid}: frame source video must be approved")
                    video_duration = source_video.get("duration_seconds")
                    if not _number(video_duration) or video_duration <= 0:
                        errors.append(f"asset {aid}: frame source video must declare a positive duration_seconds")
                    if not _number(time_seconds) or time_seconds < 0:
                        errors.append(f"asset {aid}: frame_source.time_seconds must be non-negative")
                    elif _number(video_duration) and time_seconds >= video_duration:
                        errors.append(f"asset {aid}: extracted frame time exceeds source video duration")
                if source_job is None or source_job.get("status") != "reviewed":
                    errors.append(f"asset {aid}: frame source job must exist and have status 'reviewed'")
                represented_ids = asset.get("represents_asset_ids", [])
                if not isinstance(represented_ids, list):
                    errors.append(f"asset {aid}: represents_asset_ids must be a list")
        if stage == "submit" and asset.get("status") in {"candidate", "approved"}:
            _readable_file(root, asset.get("path"), f"asset {aid}", errors)
        elif asset.get("status") == "approved" and asset.get("path"):
            _readable_file(root, asset.get("path"), f"asset {aid}", errors)

    for aid, asset in asset_by_id.items():
        represented_ids = asset.get("represents_asset_ids", [])
        if isinstance(represented_ids, list):
            for represented_id in represented_ids:
                if not isinstance(represented_id, str) or represented_id not in asset_by_id:
                    errors.append(f"asset {aid}: represents_asset_ids contains undeclared asset {represented_id!r}")

    utterances = data.get("utterances")
    if not isinstance(utterances, list):
        errors.append("utterances must be a list")
        utterances = []
    utterance_by_id: dict[str, dict[str, Any]] = {}
    for i, utterance in enumerate(utterances):
        if not isinstance(utterance, dict) or not isinstance(utterance.get("utterance_id"), str) or not utterance.get("utterance_id"):
            errors.append(f"utterances[{i}]: expected an object with utterance_id")
            continue
        uid = utterance["utterance_id"]
        if uid in utterance_by_id:
            errors.append(f"utterances: duplicate utterance_id {uid}")
        utterance_by_id[uid] = utterance
        if not isinstance(utterance.get("text"), str) or not utterance.get("speaker_id"):
            errors.append(f"utterance {uid}: text and speaker_id are required")

    jobs = data.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        errors.append("jobs must be a non-empty list")
        jobs = []
    if stage == "submit" and isinstance(data.get("generation_authorization"), dict) and data["generation_authorization"].get("authorized_by_user") is True:
        authorized_jobs = data["generation_authorization"].get("job_ids")
        project_jobs = {job.get("id") for job in jobs if isinstance(job, dict) and isinstance(job.get("id"), str)}
        if not isinstance(authorized_jobs, list) or any(not isinstance(job_id, str) or not job_id for job_id in authorized_jobs):
            errors.append("generation_authorization.job_ids must list the submitted jobs")
        elif len(authorized_jobs) != len(set(authorized_jobs)) or set(authorized_jobs) != project_jobs:
            errors.append("generation_authorization.job_ids must exactly match the submitted job IDs")
    seen_jobs: set[str] = set()
    seen_shots: set[str] = set()
    spoken_parts: dict[str, list[tuple[float, int, str]]] = defaultdict(list)
    part_order = 0

    for ji, job in enumerate(jobs):
        label = f"job[{ji}]"
        if not isinstance(job, dict):
            errors.append(f"{label}: expected an object")
            continue
        jid = job.get("id")
        if not isinstance(jid, str) or not jid or jid in seen_jobs:
            errors.append(f"{label}: id must exist and be unique")
        else:
            seen_jobs.add(jid)
        if job.get("model_profile") != PIPELINE:
            errors.append(f"job {jid}: model_profile must be '{PIPELINE}'")
        job_status = job.get("status", "planned")
        if job_status not in JOB_STATUSES:
            errors.append(f"job {jid}: invalid status")
        if stage == "draft" and job_status in PRODUCTION_STATUSES:
            errors.append(f"job {jid}: status {job_status!r} is incompatible with draft stage")
        mode = job.get("mode")
        if not isinstance(mode, str) or mode not in MODES:
            errors.append(f"job {jid}: unsupported H3 mode {mode!r}")
        duration = job.get("duration_seconds")
        offset = job.get("episode_start_seconds")
        if not _number(duration) or duration <= 0:
            errors.append(f"job {jid}: duration_seconds must be greater than 0")
            duration = 0.0
        elif duration < OFFICIAL_MIN_DURATION or duration > OFFICIAL_MAX_DURATION:
            errors.append(f"job {jid}: generated video duration must be within the official 4-15 second range")
        if not _number(offset) or offset < 0:
            errors.append(f"job {jid}: episode_start_seconds must be a non-negative number")
            offset = 0.0
        if job.get("aspect_ratio") != "16:9":
            errors.append(f"job {jid}: aspect_ratio must be '16:9'")
        if not job.get("prompt_version"):
            errors.append(f"job {jid}: prompt_version is required")
        prompt_path = _readable_file(root, job.get("compiled_prompt_path"), f"job {jid} compiled_prompt_path", errors, required=stage == "submit")
        prompt_text = None
        if stage == "submit":
            _readable_file(root, job.get("request_record_path"), f"job {jid} request_record_path", errors)
            if isinstance(capability, dict):
                supported_modes = capability.get("supported_modes")
                if isinstance(supported_modes, list) and mode not in supported_modes:
                    errors.append(f"job {jid}: mode is not in capability.supported_modes")
                supported_roles = capability.get("supported_input_roles")
                if isinstance(supported_roles, list):
                    for item in job.get("inputs", []) if isinstance(job.get("inputs"), list) else []:
                        if isinstance(item, dict) and item.get("role") not in supported_roles:
                            errors.append(f"job {jid}: input role {item.get('role')!r} is not in capability.supported_input_roles")
                if _number(duration):
                    minimum = capability.get("min_duration_seconds")
                    maximum = capability.get("max_duration_seconds")
                    effective_minimum = max(OFFICIAL_MIN_DURATION, minimum) if _number(minimum) else OFFICIAL_MIN_DURATION
                    effective_maximum = min(OFFICIAL_MAX_DURATION, maximum) if _number(maximum) else OFFICIAL_MAX_DURATION
                    if _number(duration) and duration < effective_minimum:
                        errors.append(f"job {jid}: duration is below the verified capability minimum")
                    if _number(duration) and duration > effective_maximum:
                        errors.append(f"job {jid}: duration exceeds the verified capability maximum")
                if mode == "Ref2VA":
                    limits = capability.get("input_limits")
                    if not isinstance(limits, dict) or any(not _number(limits.get(key)) for key in ("image", "video", "audio", "total")):
                        errors.append(f"job {jid}: Ref2VA submit requires verified image/video/audio/total input_limits")

        if schema_1_1:
            ledger = _require_fields(job.get("continuity_ledger"), CONTINUITY_LEDGER_FIELDS, f"job {jid} continuity_ledger", errors)
            if ledger:
                previous_job_id = ledger.get("previous_job_id")
                if previous_job_id != "none" and previous_job_id not in job_by_id:
                    errors.append(f"job {jid} continuity_ledger.previous_job_id must be 'none' or an existing job ID")
                if not isinstance(ledger.get("visible_cast"), list):
                    errors.append(f"job {jid} continuity_ledger.visible_cast must be a list")

        inputs = job.get("inputs")
        if not isinstance(inputs, list):
            errors.append(f"job {jid}: inputs must be a list")
            inputs = []
        role_counts: dict[str, int] = defaultdict(int)
        type_counts: dict[str, int] = defaultdict(int)
        seen_input_ids: set[str] = set()
        input_by_id: dict[str, dict[str, Any]] = {}
        for ii, item in enumerate(inputs):
            if not isinstance(item, dict) or not isinstance(item.get("asset_id"), str) or item.get("asset_id") not in asset_by_id:
                errors.append(f"job {jid} input[{ii}]: asset_id must refer to a declared asset")
                continue
            asset = asset_by_id[item["asset_id"]]
            input_by_id[item["asset_id"]] = item
            if item["asset_id"] in seen_input_ids:
                errors.append(f"job {jid}: duplicate input asset {item['asset_id']}")
            seen_input_ids.add(item["asset_id"])
            role = item.get("role")
            if not isinstance(role, str) or role not in {"reference", "first_frame", "last_frame"}:
                errors.append(f"job {jid} input[{ii}]: invalid H3 input role")
                continue
            role_counts[role] += 1
            kind = asset.get("kind")
            if not isinstance(kind, str) or kind not in {"image", "video", "audio"}:
                errors.append(f"asset {item['asset_id']}: kind must be image, video, or audio")
            else:
                type_counts[kind] += 1
            if role in {"first_frame", "last_frame"} and kind != "image":
                errors.append(f"job {jid} input[{ii}]: frame anchors must be image assets")
            if role in {"first_frame", "last_frame"} and asset.get("frame_role") not in (None, role):
                errors.append(f"job {jid} input[{ii}]: frame asset frame_role does not match input role")
            if not asset.get("purpose") or not asset.get("does_not_control"):
                errors.append(f"job {jid} input[{ii}]: asset purpose and does_not_control must be explicit")
            if stage == "submit":
                if asset.get("status") != "approved":
                    errors.append(f"job {jid}: referenced asset {item['asset_id']} must be approved for submit")
                _readable_file(root, asset.get("path"), f"job {jid} input asset {item['asset_id']}", errors)
                if kind == "image" and asset.get("aspect_ratio") != "16:9":
                    errors.append(f"job {jid}: referenced image {item['asset_id']} must explicitly declare 16:9")
                if asset.get("frame_source") is not None and asset.get("status") != "approved":
                    errors.append(f"job {jid}: extracted frame {item['asset_id']} must be approved before submit")
        expected_roles = {
            "T2VA": {}, "I2VA": {"first_frame": 1}, "L2VA": {"last_frame": 1},
            "FL2VA": {"first_frame": 1, "last_frame": 1}, "Ref2VA": None,
        }
        if mode in expected_roles and expected_roles[mode] is not None and dict(role_counts) != expected_roles[mode]:
            errors.append(f"job {jid}: input roles do not match {mode}")
        if mode == "Ref2VA":
            if not inputs:
                errors.append(f"job {jid}: Ref2VA requires at least one real reference input")
            if role_counts.get("first_frame", 0) or role_counts.get("last_frame", 0):
                errors.append(f"job {jid}: Ref2VA references must not be frame-anchor inputs")
            if stage == "submit" and isinstance(capability, dict) and isinstance(capability.get("input_limits"), dict):
                limits = capability["input_limits"]
                if all(_number(limits.get(key)) for key in ("image", "video", "audio", "total")):
                    if any(type_counts[k] > limits[k] for k in ("image", "video", "audio")) or len(inputs) > limits["total"]:
                        errors.append(f"job {jid}: Ref2VA inputs exceed the verified capability limits")
            if stage == "submit":
                if any(type_counts[k] > OFFICIAL_REF_LIMITS[k] for k in ("image", "video", "audio")) or len(inputs) > OFFICIAL_REF_LIMITS["total"]:
                    errors.append(f"job {jid}: Ref2VA inputs exceed the official H3 limits")
                video_durations: list[float] = []
                audio_durations: list[float] = []
                for item in inputs:
                    asset = asset_by_id.get(item.get("asset_id"), {}) if isinstance(item, dict) else {}
                    kind = asset.get("kind")
                    if kind not in {"video", "audio"}:
                        continue
                    clip_duration = asset.get("duration_seconds")
                    if not _number(clip_duration) or clip_duration < 2 or clip_duration > 15:
                        errors.append(f"job {jid}: Ref2VA {kind} input {asset.get('asset_id')} must declare duration_seconds from 2 to 15")
                    elif kind == "video":
                        video_durations.append(clip_duration)
                    else:
                        audio_durations.append(clip_duration)
                if sum(video_durations) > 15:
                    errors.append(f"job {jid}: Ref2VA reference video total duration exceeds the official 15-second limit")
                if sum(audio_durations) > 15:
                    errors.append(f"job {jid}: Ref2VA reference audio total duration exceeds the official 15-second limit")
                if type_counts.get("audio", 0) and not (type_counts.get("image", 0) or type_counts.get("video", 0)):
                    errors.append(f"job {jid}: Ref2VA audio cannot be the sole input under the official H3 standard")

        bindings = job.get("asset_bindings")
        if not isinstance(bindings, list):
            if stage == "submit" or bindings is not None:
                errors.append(f"job {jid}: asset_bindings must be a list")
            bindings = []
        bound_ids: set[str] = set()
        for bi, binding in enumerate(bindings):
            blabel = f"job {jid} asset_bindings[{bi}]"
            if not isinstance(binding, dict):
                errors.append(f"{blabel}: expected an object")
                continue
            aid = binding.get("asset_id")
            if not isinstance(aid, str) or aid not in asset_by_id:
                errors.append(f"{blabel}: asset_id must refer to a declared asset")
                continue
            if aid in bound_ids:
                errors.append(f"job {jid}: duplicate asset binding {aid}")
            bound_ids.add(aid)
            if not _present(binding.get("purpose")) or not _present(binding.get("controls")):
                errors.append(f"{blabel}: purpose and controls are required")
            method = binding.get("binding_method")
            if method not in {"attached_reference", "represented_in_frame", "frame_anchor"}:
                errors.append(f"{blabel}: invalid binding_method")
                continue
            if stage == "submit" and asset_by_id[aid].get("status") != "approved":
                errors.append(f"{blabel}: bound asset must be approved for submit")
            if method == "attached_reference":
                input_item = input_by_id.get(aid)
                if mode != "Ref2VA" or input_item is None or input_item.get("role") != "reference":
                    errors.append(f"{blabel}: attached_reference must map to a Ref2VA reference input")
            elif method == "represented_in_frame":
                matching_frames = [
                    asset_by_id[input_id]
                    for input_id, input_item in input_by_id.items()
                    if input_item.get("role") in {"first_frame", "last_frame"}
                    and aid in asset_by_id[input_id].get("represents_asset_ids", [])
                ]
                if mode not in {"I2VA", "L2VA", "FL2VA"} or not matching_frames:
                    errors.append(f"{blabel}: represented_in_frame must appear in an attached H3 frame anchor")
            else:
                input_item = input_by_id.get(aid)
                if mode not in {"I2VA", "L2VA", "FL2VA"} or input_item is None or input_item.get("role") not in {"first_frame", "last_frame"}:
                    errors.append(f"{blabel}: frame_anchor must map to an I2VA/L2VA/FL2VA frame input")

        if stage == "submit":
            for input_id in input_by_id:
                if input_id not in bound_ids:
                    errors.append(f"job {jid}: input asset {input_id} has no asset_bindings entry")

        if prompt_path:
            try:
                prompt_text = prompt_path.read_text(encoding="utf-8")
                errors.extend(f"job {jid}: {error}" for error in validate_prompt_text(prompt_text, mode))
            except OSError as exc:
                errors.append(f"job {jid}: cannot read compiled prompt: {exc}")

        shots = job.get("shots")
        if not isinstance(shots, list) or not shots:
            errors.append(f"job {jid}: shots must be a non-empty list")
            continue
        for shot in shots:
            if not isinstance(shot, dict) or "asset_ids" not in shot:
                if stage == "submit" and isinstance(shot, dict):
                    errors.append(f"job {jid} shot {shot.get('id')}: asset_ids is required for submit")
                continue
            shot_asset_ids = shot.get("asset_ids")
            if not isinstance(shot_asset_ids, list):
                errors.append(f"job {jid} shot {shot.get('id')}: asset_ids must be a list")
                continue
            for aid in shot_asset_ids:
                if aid not in bound_ids:
                    errors.append(f"job {jid} shot {shot.get('id')}: asset {aid!r} is not bound to this job")
        cursor = 0.0
        for si, shot in enumerate(shots):
            slabel = f"job {jid} shot[{si}]"
            if not isinstance(shot, dict):
                errors.append(f"{slabel}: expected an object")
                continue
            sid = shot.get("id")
            if not isinstance(sid, str) or not sid or sid in seen_shots:
                errors.append(f"{slabel}: id must exist and be globally unique")
            else:
                seen_shots.add(sid)
            start, end = shot.get("start_seconds"), shot.get("end_seconds")
            if not _number(start) or not _number(end) or start < 0 or end <= start:
                errors.append(f"{slabel}: invalid start_seconds/end_seconds")
                continue
            if abs(start - cursor) > 0.001:
                errors.append(f"{slabel}: timeline has overlap or gap at {cursor:.3f}s")
            cursor = end
            if end > duration + 0.001:
                errors.append(f"{slabel}: end exceeds job duration")
            for field in ("purpose", "main_action", "camera", "start_state", "end_state"):
                if not shot.get(field):
                    errors.append(f"{slabel}: {field} is required")

            if schema_1_1:
                entrance_order = shot.get("entrance_order")
                validated_entrances: list[dict[str, Any]] = []
                if not isinstance(entrance_order, list) or not entrance_order:
                    errors.append(f"{slabel}: entrance_order must be a non-empty list")
                else:
                    seen_actors: set[str] = set()
                    for ei, entrance in enumerate(entrance_order):
                        elabel = f"{slabel} entrance_order[{ei}]"
                        required = (
                            "actor_id", "initial_visibility", "reveal_trigger", "reveal_start_seconds",
                            "arrival_seconds", "path", "arrival_position",
                        )
                        item = _require_fields(entrance, required, elabel, errors)
                        if item is None:
                            continue
                        validated_entrances.append(item)
                        actor_id = item.get("actor_id")
                        if actor_id in seen_actors:
                            errors.append(f"{elabel}: duplicate actor_id {actor_id!r}")
                        elif isinstance(actor_id, str):
                            seen_actors.add(actor_id)
                        if item.get("initial_visibility") not in {"visible", "offscreen", "fully_occluded", "partial"}:
                            errors.append(f"{elabel}: invalid initial_visibility")
                        reveal = item.get("reveal_start_seconds")
                        arrival = item.get("arrival_seconds")
                        if not _number(reveal) or reveal < start or reveal > end:
                            errors.append(f"{elabel}: reveal_start_seconds must be inside the shot")
                        if not _number(arrival) or arrival < start or arrival > end:
                            errors.append(f"{elabel}: arrival_seconds must be inside the shot")
                        if _number(reveal) and _number(arrival) and arrival < reveal:
                            errors.append(f"{elabel}: arrival_seconds cannot precede reveal_start_seconds")

                camera_plan = _require_fields(shot.get("camera_plan"), CAMERA_PLAN_FIELDS, f"{slabel} camera_plan", errors)
                if camera_plan and camera_plan.get("movement") == "locked" and camera_plan.get("movement_trigger") != "none":
                    errors.append(f"{slabel} camera_plan: locked camera requires movement_trigger 'none'")

                performance_plan = _require_fields(
                    shot.get("performance_plan"), PERFORMANCE_PLAN_FIELDS, f"{slabel} performance_plan", errors
                )
                if performance_plan:
                    sequence = performance_plan.get("micro_expression_sequence")
                    if not isinstance(sequence, list) or not 2 <= len(sequence) <= 3 or any(not _present(item) for item in sequence):
                        errors.append(f"{slabel} performance_plan.micro_expression_sequence must contain 2 to 3 ordered visible cues")
                    hold = performance_plan.get("hold_seconds")
                    if not _number(hold) or hold < 0:
                        errors.append(f"{slabel} performance_plan.hold_seconds must be a non-negative number")

                beats = shot.get("beats")
                beat_visibility: list[tuple[float, float, set[str]]] = []
                if not isinstance(beats, list) or not beats:
                    errors.append(f"{slabel}: beats must be a non-empty list")
                else:
                    beat_cursor = start
                    for bi, beat in enumerate(beats):
                        blabel = f"{slabel} beat[{bi}]"
                        if not isinstance(beat, dict):
                            errors.append(f"{blabel}: expected an object")
                            continue
                        bstart, bend = beat.get("start_seconds"), beat.get("end_seconds")
                        if not _number(bstart) or not _number(bend) or bstart < start or bend <= bstart or bend > end:
                            errors.append(f"{blabel}: invalid start_seconds/end_seconds")
                            continue
                        if abs(bstart - beat_cursor) > 0.001:
                            errors.append(f"{blabel}: timeline has overlap or gap at {beat_cursor:.3f}s")
                        beat_cursor = bend
                        for field in BEAT_FIELDS:
                            if not _present(beat.get(field)):
                                errors.append(f"{blabel}: {field} is required")
                        if schema_1_2:
                            for field in BEAT_FRAMING_FIELDS:
                                if not _present(beat.get(field)):
                                    errors.append(f"{blabel}: {field} is required in schema 1.2")
                        positions = beat.get("positions")
                        visible_actor_ids: set[str] = set()
                        if not isinstance(positions, list) or not positions:
                            errors.append(f"{blabel}: positions must list every visible actor")
                        else:
                            for pi, position in enumerate(positions):
                                checked_position = _require_fields(
                                    position,
                                    ("actor_id", "scene_anchor", "frame_region", "body_orientation"),
                                    f"{blabel} positions[{pi}]",
                                    errors,
                                )
                                if schema_1_2 and checked_position:
                                    value = checked_position.get("screen_height_percent")
                                    if not _present(value):
                                        errors.append(f"{blabel} positions[{pi}]: screen_height_percent is required in schema 1.2")
                                    elif not _valid_screen_height_percent(value):
                                        errors.append(f"{blabel} positions[{pi}]: screen_height_percent must be greater than 0 and at most 100")
                                if checked_position and isinstance(checked_position.get("actor_id"), str):
                                    visible_actor_ids.add(checked_position["actor_id"])
                        beat_visibility.append((bstart, bend, visible_actor_ids))
                        beat_camera = _require_fields(
                            beat.get("camera"), ("framing", "movement", "trigger", "end"), f"{blabel} camera", errors
                        )
                        if beat_camera and beat_camera.get("movement") == "locked" and beat_camera.get("trigger") != "none":
                            errors.append(f"{blabel} camera: locked camera requires trigger 'none'")
                    if abs(beat_cursor - end) > 0.001:
                        errors.append(f"{slabel}: beats cover through {beat_cursor:.3f}s, expected {end:.3f}s")
                    if beat_visibility:
                        first_visible = beat_visibility[0][2]
                        beat_boundaries = {item[0] for item in beat_visibility}
                        for entrance in validated_entrances:
                            actor_id = entrance.get("actor_id")
                            reveal = entrance.get("reveal_start_seconds")
                            visibility = entrance.get("initial_visibility")
                            if not isinstance(actor_id, str) or not _number(reveal):
                                continue
                            if visibility in {"visible", "partial"} and actor_id not in first_visible:
                                errors.append(f"{slabel}: initially visible actor {actor_id!r} is missing from the first beat positions")
                            if visibility in {"offscreen", "fully_occluded"}:
                                if not any(abs(reveal - boundary) <= 0.001 for boundary in beat_boundaries):
                                    errors.append(f"{slabel}: hidden actor {actor_id!r} reveal_start_seconds must align with a beat boundary")
                                if any(actor_id in actors for bstart, _, actors in beat_visibility if bstart < reveal - 0.001):
                                    errors.append(f"{slabel}: hidden actor {actor_id!r} appears in positions before reveal_start_seconds")
                                if not any(actor_id in actors for bstart, _, actors in beat_visibility if bstart >= reveal - 0.001):
                                    errors.append(f"{slabel}: hidden actor {actor_id!r} never appears at or after reveal_start_seconds")

            dialogue = shot.get("dialogue", [])
            if not isinstance(dialogue, list):
                errors.append(f"{slabel}: dialogue must be a list")
                continue
            dialogue_cursor = start
            for di, line in enumerate(dialogue):
                dlabel = f"{slabel} dialogue[{di}]"
                if not isinstance(line, dict):
                    errors.append(f"{dlabel}: expected an object")
                    continue
                uid, text = line.get("utterance_id"), line.get("text")
                if uid not in utterance_by_id:
                    errors.append(f"{dlabel}: unknown utterance_id {uid!r}")
                    continue
                if not isinstance(text, str) or not line.get("speaker_id") or not line.get("tone"):
                    errors.append(f"{dlabel}: text, speaker_id, and tone are required")
                    continue
                if line["speaker_id"] != utterance_by_id[uid].get("speaker_id"):
                    errors.append(f"{dlabel}: speaker_id differs from the frozen utterance")
                line_start = line.get("start_seconds", start)
                line_end = line.get("end_seconds", end)
                if schema_1_1:
                    for field in DIALOGUE_FIELDS:
                        if not _present(line.get(field)):
                            errors.append(f"{dlabel}: {field} is required")
                    if not _number(line_start) or not _number(line_end) or line_start < start or line_end <= line_start or line_end > end:
                        errors.append(f"{dlabel}: start_seconds/end_seconds must be inside the shot")
                    elif line_start < dialogue_cursor - 0.001:
                        errors.append(f"{dlabel}: dialogue overlaps the previous line")
                    else:
                        dialogue_cursor = line_end
                    delivery = _require_fields(line.get("delivery"), DELIVERY_FIELDS, f"{dlabel} delivery", errors)
                    if delivery and not isinstance(delivery.get("emotional_intensity"), (str, int, float)):
                        errors.append(f"{dlabel} delivery.emotional_intensity must be a level or description")
                global_time = offset + (line_start if _number(line_start) else start) + (di * 0.000001)
                spoken_parts[uid].append((global_time, part_order, text))
                part_order += 1
        if abs(cursor - duration) > 0.001:
            errors.append(f"job {jid}: shots cover {cursor:.3f}s, expected {duration:.3f}s")

        if prompt_text is not None:
            shot_dialogue = []
            for shot in shots:
                if isinstance(shot, dict) and isinstance(shot.get("dialogue"), list):
                    shot_dialogue.extend(shot["dialogue"])
            errors.extend(f"job {jid}: {error}" for error in validate_prompt_dialogue(prompt_text, shot_dialogue))

    for uid, utterance in utterance_by_id.items():
        parts = sorted(spoken_parts.get(uid, []))
        actual = "".join(part[2] for part in parts)
        expected = utterance.get("text")
        if not parts:
            errors.append(f"utterance {uid}: no shot dialogue references it")
        elif isinstance(expected, str) and actual != expected:
            errors.append(f"utterance {uid}: shot dialogue does not exactly reconstruct the frozen text")

    return errors


def _prompt_text_for_job(root: Path, job: dict[str, Any]) -> str:
    raw = job.get("compiled_prompt_path")
    if not isinstance(raw, str) or not raw:
        return ""
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_json", type=Path, help="path to project.json")
    parser.add_argument("--lock", type=Path, default=None, help="effective-capability.lock.json")
    args = parser.parse_args()
    try:
        data = json.loads(args.project_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read project JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print("ERROR: project JSON root must be an object", file=sys.stderr)
        return 2
    root = args.project_json.resolve().parent
    errors = validate_project(data, root)
    lock_path = args.lock or root / "effective-capability.lock.json"
    if lock_path.is_file():
        skill_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(skill_root.parent))
        sys.path.insert(0, str(skill_root))
        try:
            from core.lib.guards_channel import check
        except ImportError:
            from _core.lib.guards_channel import check  # type: ignore
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        if (lock.get("effective") or {}).get("conflict"):
            errors.append(f"G-CH: aspect/capability conflict {lock['effective']['conflict']}")
        for job in data.get("jobs") or []:
            if isinstance(job, dict):
                errors.extend(check(_prompt_text_for_job(root, job), job, lock))
    elif data.get("stage") == "submit":
        errors.append("submit requires effective-capability.lock.json (run channel interview first)")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: {PIPELINE} project structure is valid (no provider request was made).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
