"""Contract tests through the real CLI + lock path (Opus re-review items 1-3)."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_cli(args: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def native_lock() -> dict:
    return {
        "effective": {
            "track_id": "P",
            "aspect": "9:16",
            "status": "ok",
            "audio_output": "native",
            "duration_seconds": {"min": 4, "max": 15},
            "reference_inputs": {"image": 5},
        }
    }


class ShotQualityCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.project = {"jobs": [{"id": "J1", "aspect_ratio": "9:16", "duration_seconds": 5}]}
        self.project_path = self.dir / "project.json"
        write_json(self.project_path, self.project)
        self.prompt_path = self.dir / "prompt.md"
        self.prompt_path.write_text("9:16竖屏。对白交给后期配音。", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_submit_without_lock_fails_closed(self) -> None:
        proc = run_cli([
            "-m", "core.lib.shot_quality",
            "--job", str(self.project_path),
            "--stage", "submit",
        ])
        self.assertIn("SHOT-LOCK", proc.stdout + proc.stderr)

    def test_submit_with_native_lock_rejects_post_dub(self) -> None:
        lock_path = self.dir / "lock.json"
        write_json(lock_path, native_lock())
        proc = run_cli([
            "-m", "core.lib.shot_quality",
            "--job", str(self.project_path),
            "--prompt", str(self.prompt_path),
            "--lock", str(lock_path),
            "--stage", "submit",
        ])
        self.assertIn("SHOT-AUD-POST", proc.stdout + proc.stderr)


class ValidateProjectCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.lock_path = self.dir / "lock.json"
        write_json(self.lock_path, native_lock())

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, script: str, project: dict) -> str:
        project_path = self.dir / "project.json"
        write_json(project_path, project)
        proc = run_cli([
            str(ROOT / script), str(project_path),
            "--lock", str(self.lock_path),
        ])
        return proc.stdout + proc.stderr

    def test_sd_submit_reports_audio_post_dub(self) -> None:
        prompt = self.dir / "prompt.md"
        prompt.write_text("16:9横屏。对白交给后期配音。", encoding="utf-8")
        project = {
            "schema_version": "1.0",
            "project_id": "cli-sd",
            "title": "CLI SD",
            "pipeline": "seedance",
            "model_profile": "seedance-2.5",
            "aspect_ratio": "16:9",
            "stage": "submit",
            "generation_authorization": {
                "authorized_by_user": True,
                "job_ids": ["J1"],
                "evidence": "cli fixture",
                "budget_limit": {"amount": 1, "unit": "USD"},
            },
            "capability": {
                "provider": "test",
                "model_id": "seedance-test",
                "checked_at": "2026-10-19",
                "evidence_uri": "fixture",
                "aspect_ratios": ["16:9"],
                "supported_modes": ["text_only"],
                "supported_input_roles": [],
                "min_duration_seconds": 4,
                "max_duration_seconds": 15,
            },
            "utterances": [],
            "assets": [],
            "jobs": [
                {
                    "id": "J1",
                    "model_profile": "seedance-2.5",
                    "mode": "text_only",
                    "duration_seconds": 5,
                    "aspect_ratio": "16:9",
                    "episode_start_seconds": 0,
                    "inputs": [],
                    "prompt_version": "1",
                    "compiled_prompt_path": "prompt.md",
                    "request_record_path": "request.json",
                    "shots": [
                        {
                            "id": "S1",
                            "start_seconds": 0,
                            "end_seconds": 5,
                            "purpose": "p",
                            "main_action": "a",
                            "camera": "c",
                            "start_state": "s",
                            "end_state": "e",
                            "dialogue": [],
                        }
                    ],
                }
            ],
        }
        self.assertIn("SHOT-AUD-POST", self._run("skill-SD/scripts/validate_project.py", project))

    def test_h3_submit_reports_audio_post_dub(self) -> None:
        prompt = self.dir / "prompt.md"
        prompt.write_text("16:9横屏。对白交给后期配音。", encoding="utf-8")
        project = {
            "schema_version": "1.2",
            "project_id": "cli-h3",
            "title": "CLI H3",
            "pipeline": "minimax-h3",
            "model_profile": "minimax-h3",
            "aspect_ratio": "16:9",
            "stage": "submit",
            "generation_authorization": {
                "authorized_by_user": True,
                "job_ids": ["J1"],
                "evidence": "cli fixture",
                "budget_limit": {"amount": 1, "unit": "USD"},
            },
            "capability": {
                "provider": "test",
                "model_id": "h3-test",
                "checked_at": "2026-10-19",
                "evidence_uri": "fixture",
                "aspect_ratios": ["16:9"],
                "supported_modes": ["T2VA"],
                "supported_input_roles": [],
                "min_duration_seconds": 4,
                "max_duration_seconds": 15,
            },
            "utterances": [],
            "assets": [],
            "jobs": [
                {
                    "id": "J1",
                    "model_profile": "minimax-h3",
                    "mode": "T2VA",
                    "duration_seconds": 5,
                    "aspect_ratio": "16:9",
                    "episode_start_seconds": 0,
                    "prompt_version": "1",
                    "compiled_prompt_path": "prompt.md",
                    "request_record_path": "request.json",
                    "inputs": [],
                    "shots": [
                        {
                            "id": "S1",
                            "start_seconds": 0,
                            "end_seconds": 5,
                            "purpose": "p",
                            "main_action": "a",
                            "camera": "c",
                            "start_state": "s",
                            "end_state": "e",
                            "dialogue": [],
                        }
                    ],
                }
            ],
        }
        self.assertIn("SHOT-AUD-POST", self._run("skill-H3/scripts/validate_project.py", project))


class AdaptCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.job_path = self.dir / "job.json"
        self.lock_path = self.dir / "lock.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, duration: int, audio: object) -> tuple[subprocess.CompletedProcess[str], dict]:
        write_json(self.job_path, {"id": "J1", "duration_seconds": duration})
        lock = {
            "effective": {
                "duration_seconds": {"min": 4, "max": 15, "allowed": [5, 10, 15]},
                "reference_inputs": {"image": 5},
            }
        }
        if audio is not Ellipsis:
            lock["effective"]["audio_output"] = audio
        write_json(self.lock_path, lock)
        proc = run_cli([
            "-m", "core.lib.adapt",
            "--job", str(self.job_path),
            "--lock", str(self.lock_path),
        ])
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = {}
        return proc, payload

    def test_missing_audio_blocks_without_post_dub(self) -> None:
        proc, payload = self._run(5, Ellipsis)
        self.assertEqual(payload.get("rule"), "R-AUD-00")
        self.assertNotIn("R-AUD-01", payload.get("rules_fired") or [])
        self.assertEqual(proc.returncode, 1)

    def test_unknown_audio_token_blocks(self) -> None:
        _, payload = self._run(5, "weird")
        self.assertEqual(payload.get("rule"), "R-AUD-00")
        self.assertNotIn("R-AUD-01", payload.get("rules_fired") or [])

    def test_dialogue_and_sfx_maps_to_native(self) -> None:
        _, payload = self._run(5, "dialogue_and_sfx")
        self.assertFalse(payload.get("blocked"))
        self.assertEqual(payload.get("audio_mode"), "native_text_voice")
        self.assertNotIn("R-AUD-01", payload.get("rules_fired") or [])

    def test_7s_offers_trim_not_auto_pad(self) -> None:
        _, payload = self._run(7, "native")
        self.assertFalse(payload.get("blocked"))
        self.assertEqual([o["action"] for o in payload.get("duration_options") or []], ["trim"])
        self.assertEqual(payload.get("snapped_duration"), 5)
        self.assertNotEqual(payload.get("snapped_duration"), 10)

    def test_12s_offers_pad_to_15(self) -> None:
        _, payload = self._run(12, "native")
        self.assertEqual(payload.get("snapped_duration"), 15)
        self.assertIn("R-DUR-05", payload.get("rules_fired") or [])

    def test_16s_blocks_without_enum_composition(self) -> None:
        _, payload = self._run(16, "native")
        self.assertTrue(payload.get("blocked"))
        self.assertEqual(payload.get("rule"), "R-DUR-02")


class SharedDocDriftTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.spec_from_file_location("check_drift", ROOT / "build" / "check_drift.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_identical_shared_blocks_pass(self) -> None:
        module = self._module()
        doc = "<!-- shared:roots -->two roots<!-- /shared:roots -->"
        self.assertEqual(module.compare_shared(doc, doc), [])

    def test_changed_shared_block_reports_drift(self) -> None:
        module = self._module()
        a = "<!-- shared:roots -->two roots<!-- /shared:roots -->"
        b = "<!-- shared:roots -->two roots, edited<!-- /shared:roots -->"
        self.assertIn("DRIFT shared:roots", module.compare_shared(a, b))


if __name__ == "__main__":
    unittest.main()
