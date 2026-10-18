"""Focused regression tests for the Seedance manifest validator."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from validate_project import validate_project


HERE = Path(__file__).resolve().parent
EXAMPLE = HERE.parent / "examples" / "project.json"


class ValidateProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        self.root = EXAMPLE.parent

    def test_complete_draft_example_passes(self) -> None:
        self.assertEqual(validate_project(self.data, self.root), [])

    def test_25_draft_does_not_enforce_stale_duration_snapshot(self) -> None:
        data = copy.deepcopy(self.data)
        data["jobs"][0]["duration_seconds"] = 31
        data["jobs"][0]["shots"][0]["end_seconds"] = 31
        self.assertEqual(validate_project(data, self.root), [])

    def test_25_draft_does_not_enforce_stale_reference_count_snapshot(self) -> None:
        data = copy.deepcopy(self.data)
        job = data["jobs"][0]
        job["mode"] = "reference_set"
        data["assets"] = [
            {
                "asset_id": f"IMG{i:02d}",
                "kind": "image",
                "status": "planned",
                "aspect_ratio": "16:9",
                "purpose": "测试引用额度草案",
                "does_not_control": "实际镜头构图",
            }
            for i in range(51)
        ]
        job["inputs"] = [{"asset_id": asset["asset_id"], "role": "reference_image"} for asset in data["assets"]]
        self.assertEqual(validate_project(data, self.root), [])

    def test_submit_requires_explicit_generation_authorization(self) -> None:
        data = copy.deepcopy(self.data)
        data["stage"] = "submit"
        self.assertTrue(any("explicit user authorization" in error for error in validate_project(data, self.root)))

    def test_submit_enforces_current_capability_duration_range(self) -> None:
        data = copy.deepcopy(self.data)
        data["stage"] = "submit"
        data["generation_authorization"] = {
            "authorized_by_user": True,
            "job_ids": ["JOB001"],
            "evidence": "用户明确要求提交 JOB001，最高预算 1 USD",
            "budget_limit": {"amount": 1, "unit": "USD"},
        }
        data["capability"] = {
            "provider": "test-provider",
            "model_id": "seedance-test-2.5",
            "checked_at": "2026-10-09",
            "evidence_uri": "test fixture",
            "aspect_ratios": ["16:9"],
            "supported_modes": ["text_only"],
            "supported_input_roles": [],
            "min_duration_seconds": 4,
            "max_duration_seconds": 30,
        }
        job = data["jobs"][0]
        job["duration_seconds"] = 31
        job["shots"][0]["end_seconds"] = 31
        job["request_record_path"] = "seedance-prompt.md"
        errors = validate_project(data, self.root)
        self.assertTrue(any("verified capability maximum" in error for error in errors))
        self.assertFalse(any("explicit user authorization" in error for error in errors))

    def test_submit_authorized_job_ids_must_match_manifest(self) -> None:
        data = copy.deepcopy(self.data)
        data["stage"] = "submit"
        data["generation_authorization"] = {
            "authorized_by_user": True,
            "job_ids": ["JOB002"],
            "evidence": "用户只授权 JOB002",
            "budget_limit": {"amount": 1, "unit": "USD"},
        }
        self.assertTrue(any("exactly match the submitted job IDs" in error for error in validate_project(data, self.root)))

    def test_rejects_other_model_profile(self) -> None:
        data = copy.deepcopy(self.data)
        data["jobs"][0]["model_profile"] = "seedance-2.0"
        self.assertTrue(any("model_profile" in error for error in validate_project(data, self.root)))

    def test_rejects_h3_mode(self) -> None:
        data = copy.deepcopy(self.data)
        data["jobs"][0]["mode"] = "Ref2VA"
        self.assertTrue(any("not allowed" in error for error in validate_project(data, self.root)))

    def test_rejects_timeline_gap(self) -> None:
        data = copy.deepcopy(self.data)
        data["jobs"][0]["shots"][0]["start_seconds"] = 0.5
        self.assertTrue(any("overlap or gap" in error for error in validate_project(data, self.root)))

    def test_rejects_changed_frozen_dialogue(self) -> None:
        data = copy.deepcopy(self.data)
        data["jobs"][0]["shots"][0]["dialogue"][0]["text"] = "阵眼不在，别碰那盏灯。"
        self.assertTrue(any("exactly reconstruct" in error for error in validate_project(data, self.root)))

    def test_20_cannot_mix_reference_audio(self) -> None:
        data = copy.deepcopy(self.data)
        data["model_profile"] = "seedance-2.0"
        job = data["jobs"][0]
        job["model_profile"] = "seedance-2.0"
        job["mode"] = "reference_image"
        data["assets"] = [{"asset_id": "AUD1", "kind": "audio", "status": "planned", "aspect_ratio": None, "purpose": "参考说话者音色", "does_not_control": "台词措辞和画面动作"}]
        job["inputs"] = [{"asset_id": "AUD1", "role": "reference_audio"}]
        errors = validate_project(data, self.root)
        self.assertTrue(any("reference_image" in error or "input roles" in error for error in errors))

    def test_20_single_reference_image_is_valid(self) -> None:
        data = copy.deepcopy(self.data)
        data["model_profile"] = "seedance-2.0"
        job = data["jobs"][0]
        job["model_profile"] = "seedance-2.0"
        job["mode"] = "reference_image"
        data["assets"] = [{"asset_id": "IMG1", "kind": "image", "status": "planned", "aspect_ratio": "16:9", "purpose": "锁定沈砚身份与服装", "does_not_control": "镜头构图和动作"}]
        job["inputs"] = [{"asset_id": "IMG1", "role": "reference_image"}]
        self.assertEqual(validate_project(data, self.root), [])

    def test_20_multimodal_reference_is_explicitly_versioned(self) -> None:
        data = copy.deepcopy(self.data)
        data["model_profile"] = "seedance-2.0"
        job = data["jobs"][0]
        job["model_profile"] = "seedance-2.0"
        job["mode"] = "multimodal_reference"
        data["assets"] = [{"asset_id": "AUD1", "kind": "audio", "status": "planned", "aspect_ratio": None, "purpose": "参考声音", "does_not_control": "画面动作和台词内容"}]
        job["inputs"] = [{"asset_id": "AUD1", "role": "reference_audio"}]
        self.assertEqual(validate_project(data, self.root), [])

    def test_20_cannot_use_seedance_25_modes(self) -> None:
        data = copy.deepcopy(self.data)
        data["model_profile"] = "seedance-2.0"
        data["jobs"][0]["model_profile"] = "seedance-2.0"
        data["jobs"][0]["mode"] = "reference_set"
        self.assertTrue(any("not allowed for seedance-2.0" in error for error in validate_project(data, self.root)))

    def test_20_frame_anchored_pair_is_its_own_mode(self) -> None:
        data = copy.deepcopy(self.data)
        data["model_profile"] = "seedance-2.0"
        job = data["jobs"][0]
        job["model_profile"] = "seedance-2.0"
        job["mode"] = "frame_anchored"
        data["assets"] = [
            {"asset_id": "FIRST", "kind": "image", "status": "planned", "aspect_ratio": "16:9", "purpose": "2.0片段起始画面", "does_not_control": "后续剧情安排"},
            {"asset_id": "LAST", "kind": "image", "status": "planned", "aspect_ratio": "16:9", "purpose": "2.0片段结束画面", "does_not_control": "未指定的中间动作"},
        ]
        job["inputs"] = [{"asset_id": "FIRST", "role": "first_frame"}, {"asset_id": "LAST", "role": "last_frame"}]
        self.assertEqual(validate_project(data, self.root), [])

    def test_25_first_last_requires_a_pair(self) -> None:
        data = copy.deepcopy(self.data)
        data["jobs"][0]["mode"] = "first_last_frame"
        data["assets"] = [{"asset_id": "FIRST", "kind": "image", "status": "planned", "aspect_ratio": "16:9", "purpose": "锁定片段起始构图", "does_not_control": "角色身份参考"}]
        data["jobs"][0]["inputs"] = [{"asset_id": "FIRST", "role": "first_frame"}]
        self.assertTrue(any("input roles do not match" in error for error in validate_project(data, self.root)))

    def test_25_reference_set_allows_audio_only_when_declared(self) -> None:
        data = copy.deepcopy(self.data)
        data["jobs"][0]["mode"] = "reference_set"
        data["assets"] = [{"asset_id": "AUDIO1", "kind": "audio", "status": "planned", "aspect_ratio": None, "purpose": "声音参考", "does_not_control": "画面构图和对白内容"}]
        data["jobs"][0]["inputs"] = [{"asset_id": "AUDIO1", "role": "reference_audio"}]
        self.assertEqual(validate_project(data, self.root), [])

    def test_20_draft_does_not_enforce_stale_duration_snapshot(self) -> None:
        data = copy.deepcopy(self.data)
        data["model_profile"] = "seedance-2.0"
        job = data["jobs"][0]
        job["model_profile"] = "seedance-2.0"
        job["duration_seconds"] = 16
        job["shots"][0]["end_seconds"] = 16
        self.assertEqual(validate_project(data, self.root), [])

    def test_20_submit_enforces_current_capability_maximum(self) -> None:
        data = copy.deepcopy(self.data)
        data["model_profile"] = "seedance-2.0"
        data["stage"] = "submit"
        data["generation_authorization"] = {
            "authorized_by_user": True,
            "job_ids": ["JOB001"],
            "evidence": "用户明确要求提交 JOB001，最高预算 1 USD",
            "budget_limit": {"amount": 1, "unit": "USD"},
        }
        data["capability"] = {
            "provider": "test-provider",
            "model_id": "seedance-test-2.0",
            "checked_at": "2026-10-09",
            "evidence_uri": "test fixture",
            "aspect_ratios": ["16:9"],
            "supported_modes": ["text_only"],
            "supported_input_roles": [],
            "min_duration_seconds": 4,
            "max_duration_seconds": 15,
        }
        job = data["jobs"][0]
        job["model_profile"] = "seedance-2.0"
        job["duration_seconds"] = 16
        job["shots"][0]["end_seconds"] = 16
        job["request_record_path"] = "seedance-prompt.md"
        errors = validate_project(data, self.root)
        self.assertTrue(any("verified capability maximum" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
