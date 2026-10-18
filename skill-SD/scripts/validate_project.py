#!/usr/bin/env python3
"""Validate a Seedance comic-drama project manifest without calling a provider."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


PIPELINE = "seedance"
PROFILES = {"seedance-2.0", "seedance-2.5"}
MODES = {
    "seedance-2.0": {"text_only", "reference_image", "multimodal_reference", "frame_anchored"},
    "seedance-2.5": {"text_only", "reference_set", "first_last_frame"},
}
FORBIDDEN_PROMPT_PATTERNS = (
    (re.compile(r"<Subject\s+\d+>|<Picture\s+\d+>|<Video\s+\d+>|<Audio\s+\d+>|<d>\s*\[", re.I), "MiniMax H3 prompt syntax found in Seedance prompt"),
    (re.compile(r"\b(?:subject_definitions|retention_analysis|detailed_description|overall_soundscape|non_diegetic_music|T2VA|I2VA|L2VA|FL2VA|Ref2VA)\b"), "MiniMax H3 field or mode found in Seedance prompt"),
)


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


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


def validate_project(data: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != "1.0":
        errors.append("schema_version: expected '1.0'")
    if not data.get("project_id") or not data.get("title"):
        errors.append("project_id and title are required")
    project_profile = data.get("model_profile")
    if data.get("pipeline") != PIPELINE or not isinstance(project_profile, str) or project_profile not in PROFILES:
        errors.append("pipeline must be 'seedance' and model_profile must be exactly 'seedance-2.0' or 'seedance-2.5'")
    allowed = {"16:9", "9:16"}
    deliverables = data.get("deliverables")
    if isinstance(deliverables, list) and deliverables:
        aspects = {d.get("aspect") for d in deliverables if isinstance(d, dict)}
        if not aspects <= allowed:
            errors.append("deliverables.aspect must be 16:9 or 9:16")
    elif data.get("aspect_ratio") not in allowed:
        errors.append("aspect_ratio must be '16:9' or '9:16'")
    stage = data.get("stage")
    if stage not in {"draft", "submit"}:
        errors.append("stage must be 'draft' or 'submit'")
        stage = "draft"

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
            if not isinstance(aspect_ratios, list) or not (set(aspect_ratios) & {"16:9", "9:16"}):
                errors.append("capability must confirm 16:9 and/or 9:16")
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
    asset_by_id: dict[str, dict[str, Any]] = {}
    for i, asset in enumerate(assets):
        if not isinstance(asset, dict) or not isinstance(asset.get("asset_id"), str) or not asset.get("asset_id"):
            errors.append(f"assets[{i}]: expected an object with asset_id")
            continue
        aid = asset["asset_id"]
        if aid in asset_by_id:
            errors.append(f"assets: duplicate asset_id {aid}")
        asset_by_id[aid] = asset
        if asset.get("status") not in {"planned", "candidate", "approved", "stale", "rejected"}:
            errors.append(f"asset {aid}: invalid status")
        if asset.get("aspect_ratio") not in (None, "16:9", "9:16"):
            errors.append(f"asset {aid}: aspect_ratio must be 16:9 or 9:16 when specified")
        if asset.get("kind") in {"character"} or asset.get("asset_role") == "identity":
            if not (asset.get("presentation_sex") or asset.get("sex")):
                errors.append(f"asset {aid}: identity board must lock presentation_sex male|female")
        if asset.get("kind") in {"costume", "wardrobe", "prop", "weapon", "artifact"} or asset.get("asset_role") in {"wardrobe", "prop", "weapon"}:
            if not asset.get("owner_id") and not asset.get("character_id"):
                errors.append(f"asset {aid}: wardrobe/prop must set owner_id (never share across sexes)")
        if stage == "submit" and asset.get("status") in {"candidate", "approved"}:
            _readable_file(root, asset.get("path"), f"asset {aid}", errors)
        elif asset.get("status") == "approved" and asset.get("path"):
            _readable_file(root, asset.get("path"), f"asset {aid}", errors)

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
        if job.get("model_profile") != project_profile:
            errors.append(f"job {jid}: model_profile must match the locked project profile")
        mode = job.get("mode")
        if project_profile in MODES and (not isinstance(mode, str) or mode not in MODES[project_profile]):
            errors.append(f"job {jid}: mode {mode!r} is not allowed for {project_profile}")
        duration = job.get("duration_seconds")
        offset = job.get("episode_start_seconds")
        if not _number(duration) or duration <= 0:
            errors.append(f"job {jid}: duration_seconds must be greater than 0")
            duration = 0.0
        if not _number(offset) or offset < 0:
            errors.append(f"job {jid}: episode_start_seconds must be a non-negative number")
            offset = 0.0
        if job.get("aspect_ratio") not in {"16:9", "9:16"}:
            errors.append(f"job {jid}: aspect_ratio must be '16:9' or '9:16'")
        if not job.get("prompt_version"):
            errors.append(f"job {jid}: prompt_version is required")
        prompt_path = _readable_file(root, job.get("compiled_prompt_path"), f"job {jid} compiled_prompt_path", errors, required=stage == "submit")
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
                    if _number(minimum) and duration < minimum:
                        errors.append(f"job {jid}: duration is below the verified capability minimum")
                    if _number(maximum) and duration > maximum:
                        errors.append(f"job {jid}: duration exceeds the verified capability maximum")
                if mode in {"reference_set", "multimodal_reference"}:
                    limits = capability.get("input_limits")
                    if not isinstance(limits, dict) or any(not _number(limits.get(key)) for key in ("image", "video", "audio", "total")):
                        errors.append(f"job {jid}: {mode} submit requires verified image/video/audio/total input_limits")

        inputs = job.get("inputs")
        if not isinstance(inputs, list):
            errors.append(f"job {jid}: inputs must be a list")
            inputs = []
        role_counts: dict[str, int] = defaultdict(int)
        type_counts: dict[str, int] = defaultdict(int)
        for ii, item in enumerate(inputs):
            if not isinstance(item, dict) or not isinstance(item.get("asset_id"), str) or item.get("asset_id") not in asset_by_id:
                errors.append(f"job {jid} input[{ii}]: asset_id must refer to a declared asset")
                continue
            asset = asset_by_id[item["asset_id"]]
            role = item.get("role")
            if not isinstance(role, str) or role not in {"reference_image", "reference_video", "reference_audio", "first_frame", "last_frame"}:
                errors.append(f"job {jid} input[{ii}]: invalid Seedance input role")
                continue
            role_counts[role] += 1
            kind = asset.get("kind")
            if not isinstance(kind, str) or kind not in {"image", "video", "audio"}:
                errors.append(f"asset {item['asset_id']}: kind must be image, video, or audio")
            else:
                type_counts[kind] += 1
            if not asset.get("purpose") or not asset.get("does_not_control"):
                errors.append(f"job {jid} input[{ii}]: asset purpose and does_not_control must be explicit")
            if stage == "submit":
                if asset.get("status") != "approved":
                    errors.append(f"job {jid}: referenced asset {item['asset_id']} must be approved for submit")
                _readable_file(root, asset.get("path"), f"job {jid} input asset {item['asset_id']}", errors)
                if kind == "image" and asset.get("asset_role") != "identity" and asset.get("aspect_ratio") not in (None, "16:9", "9:16"):
                    errors.append(f"job {jid}: referenced image {item['asset_id']} must declare 16:9 or 9:16")
        expected_roles: dict[str, dict[str, int] | None] = {
            "text_only": {}, "reference_image": {"reference_image": 1},
            "frame_anchored": {"first_frame": 1, "last_frame": 1},
            "multimodal_reference": None,
            "reference_set": None, "first_last_frame": {"first_frame": 1, "last_frame": 1},
        }
        if mode in expected_roles and expected_roles[mode] is not None and dict(role_counts) != expected_roles[mode]:
            errors.append(f"job {jid}: input roles do not match {mode}")
        if mode == "reference_image" and (len(inputs) != 1 or any(asset_by_id.get(item.get("asset_id"), {}).get("kind") != "image" for item in inputs if isinstance(item, dict))):
            errors.append(f"job {jid}: Seedance 2.0 reference_image takes exactly one image asset")
        if mode == "reference_image" and any(isinstance(item, dict) and item.get("role") != "reference_image" for item in inputs):
            errors.append(f"job {jid}: Seedance 2.0 reference_image cannot include audio, video, or frame anchors")
        if mode in {"reference_set", "multimodal_reference"}:
            if not inputs:
                errors.append(f"job {jid}: {mode} requires at least one real reference input")
            kind_for_role = {"reference_image": "image", "reference_video": "video", "reference_audio": "audio"}
            for item in inputs:
                if isinstance(item, dict) and item.get("role") in kind_for_role and asset_by_id.get(item.get("asset_id"), {}).get("kind") != kind_for_role[item["role"]]:
                    errors.append(f"job {jid}: {item['role']} role does not match the asset kind")
            if any(role_counts.get(role, 0) for role in ("first_frame", "last_frame")):
                errors.append(f"job {jid}: reference_set cannot be combined with first/last frame inputs")
            if stage == "submit" and isinstance(capability, dict) and isinstance(capability.get("input_limits"), dict):
                limits = capability["input_limits"]
                for kind in ("image", "video", "audio"):
                    if _number(limits.get(kind)) and type_counts[kind] > limits[kind]:
                        errors.append(f"job {jid}: {kind} references exceed the verified capability limit")
                if _number(limits.get("total")) and len(inputs) > limits["total"]:
                    errors.append(f"job {jid}: total references exceed the verified capability limit")
        if mode in {"first_last_frame", "frame_anchored"}:
            if any(isinstance(item, dict) and asset_by_id.get(item.get("asset_id"), {}).get("kind") != "image" for item in inputs):
                errors.append(f"job {jid}: first_last_frame inputs must both be images")
            for item in inputs:
                if isinstance(item, dict) and item.get("role") in {"first_frame", "last_frame"}:
                    asset = asset_by_id.get(item.get("asset_id"), {})
                    if asset.get("aspect_ratio") not in {"16:9", "9:16"}:
                        errors.append(f"job {jid}: first_last_frame assets must declare 16:9 or 9:16")
                    elif job.get("aspect_ratio") in {"16:9", "9:16"} and asset.get("aspect_ratio") != job.get("aspect_ratio"):
                        errors.append(f"job {jid}: first_last_frame asset {item.get('asset_id')} aspect must match job {job.get('aspect_ratio')}")
            if any(role_counts.get(role, 0) for role in ("reference_image", "reference_video", "reference_audio")):
                errors.append(f"job {jid}: first_last_frame is exclusive with reference_set inputs")

        if prompt_path:
            try:
                prompt_text = prompt_path.read_text(encoding="utf-8")
                for pattern, message in FORBIDDEN_PROMPT_PATTERNS:
                    if pattern.search(prompt_text):
                        errors.append(f"job {jid}: {message}")
                if project_profile == "seedance-2.0" and re.search(r"<(?:SFX|BGM|VO|Dialogue)\b|\{[^{}]*(?:dialogue|对白|台词)[^{}]*\}|【(?:字幕|subtitles?)[:：]", prompt_text, re.I):
                    errors.append(f"job {jid}: Seedance 2.5 sound-channel markers are not allowed in Seedance 2.0")
            except OSError as exc:
                errors.append(f"job {jid}: cannot read compiled prompt: {exc}")

        shots = job.get("shots")
        if not isinstance(shots, list) or not shots:
            errors.append(f"job {jid}: shots must be a non-empty list")
            continue
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
            dialogue = shot.get("dialogue", [])
            if not isinstance(dialogue, list):
                errors.append(f"{slabel}: dialogue must be a list")
                continue
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
                global_time = offset + start + (di * 0.000001)
                spoken_parts[uid].append((global_time, part_order, text))
                part_order += 1
        if abs(cursor - duration) > 0.001:
            errors.append(f"job {jid}: shots cover {cursor:.3f}s, expected {duration:.3f}s")

    for uid, utterance in utterance_by_id.items():
        parts = sorted(spoken_parts.get(uid, []))
        actual = "".join(part[2] for part in parts)
        expected = utterance.get("text")
        if not parts:
            errors.append(f"utterance {uid}: no shot dialogue references it")
        elif isinstance(expected, str) and actual != expected:
            errors.append(f"utterance {uid}: shot dialogue does not exactly reconstruct the frozen text")

    if stage == "submit":
        skill_root = Path(__file__).resolve().parents[1]
        if str(skill_root.parent) not in sys.path:
            sys.path.insert(0, str(skill_root.parent))
        if str(skill_root) not in sys.path:
            sys.path.insert(0, str(skill_root))
        try:
            from core.lib.identity import check_project as check_identity
            from core.lib.shot_quality import check_job
        except ImportError:
            from _core.lib.identity import check_project as check_identity  # type: ignore
            from _core.lib.shot_quality import check_job  # type: ignore
        errors.extend(check_identity(data))
        for job in jobs:
            if isinstance(job, dict):
                errors.extend(check_job(job, _prompt_text_for_job(root, job)))

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
            from core.lib.channel import file_hash
            from core.lib.guards_channel import apply_lock_checks
        except ImportError:
            from _core.lib.channel import file_hash  # type: ignore
            from _core.lib.guards_channel import apply_lock_checks  # type: ignore
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        errors.extend(
            apply_lock_checks(
                data,
                lock,
                lambda job: _prompt_text_for_job(root, job),
                project_hash=file_hash(args.project_json),
            )
        )
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
