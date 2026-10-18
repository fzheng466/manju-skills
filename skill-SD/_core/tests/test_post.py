import unittest
from datetime import datetime, timedelta, timezone

from core.lib.channel import capability_status, gate_capabilities
from core.lib.post import audio_plan, edl_text, srt_text
from core.lib.shot_quality import check_job


class PostTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = {
            "utterances": [{"utterance_id": "U1", "text": "阵眼还在。", "speaker_id": "SHEN"}],
            "jobs": [
                {
                    "id": "J1",
                    "status": "reviewed",
                    "track_id": "L",
                    "episode_start_seconds": 0,
                    "duration_seconds": 8,
                    "shots": [
                        {
                            "start_seconds": 0,
                            "end_seconds": 8,
                            "dialogue": [
                                {
                                    "utterance_id": "U1",
                                    "speaker_id": "SHEN",
                                    "speaker_name": "沈砚",
                                    "start_seconds": 1,
                                    "end_seconds": 3,
                                    "text": "阵眼还在。",
                                }
                            ],
                        }
                    ],
                },
                {
                    "id": "J2",
                    "status": "planned",
                    "track_id": "L",
                    "episode_start_seconds": 8,
                    "duration_seconds": 8,
                    "shots": [{"start_seconds": 0, "end_seconds": 8, "dialogue": []}],
                },
            ],
        }

    def test_srt_times(self):
        srt = srt_text(self.project, "L")
        self.assertIn("00:00:01,000 --> 00:00:03,000", srt)
        self.assertIn("阵眼还在。", srt)

    def test_edl_skips_unreviewed(self):
        text, warns = edl_text(self.project, "L")
        self.assertIn("001", text)
        self.assertTrue(any("J2" in w for w in warns))

    def test_audio_plan_reconstruct(self):
        plan = audio_plan(self.project)
        self.assertEqual("".join(i["text"] for i in plan["items"]), "阵眼还在。")


class TtlTests(unittest.TestCase):
    def test_expired_and_failed(self):
        old = (datetime.now(timezone.utc) - timedelta(days=40)).date().isoformat()
        self.assertEqual(capability_status({"status": "verified", "last_verified": old, "ttl_days": 30}), "expired")
        errs, warns = gate_capabilities({"duration_seconds": "failed"})
        self.assertTrue(any("G-CH9" in e for e in errs))
        _, warns = gate_capabilities({"duration_seconds": {"status": "declared"}})
        self.assertTrue(any("probe" in w for w in warns))


class ShotQualityTightenTests(unittest.TestCase):
    def test_portrait_height_and_suppression(self):
        job = {
            "aspect_ratio": "9:16",
            "shots": [
                {
                    "performance_plan": {
                        "objective": "压住对方",
                        "concealment": "害怕",
                        "trigger": "x",
                        "baseline": "唇线闭合",
                        "micro_expression_sequence": ["手指先停", "上眼睑轻抬"],
                        "body_breath": "吸气压回",
                        "listener_reaction": "对方肩一沉",
                        "hold_seconds": 0.4,
                        "end_expression": "ok",
                    },
                    "beats": [
                        {
                            "expression": "眉心收紧",
                            "visible_action": "按住刀脊",
                            "camera": {"framing": "全身"},
                            "positions": [{"actor_id": "A", "screen_height_percent": 50}],
                        }
                    ],
                }
            ],
        }
        err = check_job(job, "9:16竖屏，两人前后纵深")
        self.assertTrue(any("SHOT-AR" in e for e in err))
        self.assertTrue(any("trigger" in e for e in err))
        self.assertTrue(any("suppression" in e or "压回" in e for e in err))


if __name__ == "__main__":
    unittest.main()
