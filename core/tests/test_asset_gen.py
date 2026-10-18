import json
import os
import tempfile
import unittest
from pathlib import Path

from core.lib import asset_gen


class AssetGenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "manju"
        self.home.mkdir()
        os.environ["MANJU_HOME"] = str(self.home)
        self.adapter = self.home / "adapters"
        self.adapter.mkdir()
        self.calls = self.home / "calls.txt"
        (self.adapter / "fake.py").write_text(
            "from pathlib import Path\n"
            "CALLS = Path(r'''%s''')\n"
            "def generate(payload):\n"
            "    CALLS.write_text(__import__('json').dumps(payload), encoding='utf-8')\n"
            "    return {'paths': ['a.png', 'b.png'], 'n': payload.get('n')}\n" % self.calls.as_posix(),
            encoding="utf-8",
        )
        (self.home / "channels").mkdir()
        (self.home / "channels" / "local.json").write_text(
            json.dumps(
                {
                    "channel_id": "local",
                    "image_gen": {
                        "adapter": str(self.adapter / "fake.py"),
                        "price_per_image": 1.0,
                    },
                }
            ),
            encoding="utf-8",
        )
        self.project = {
            "project_id": "p1",
            "stage": "draft",
            "characters": [{"character_id": "SHEN_YAN", "name": "沈砚", "presentation_sex": "male"}],
            "assets": [
                {
                    "asset_id": "CHAR1",
                    "kind": "character",
                    "status": "planned",
                    "owner_id": "SHEN_YAN",
                    "presentation_sex": "male",
                    "aspect_ratio": "16:9",
                    "prompt": "16:9横屏男性角色四视图。正面全身、45°侧面全身、背面全身。双手空置。",
                }
            ],
        }

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_dry_run_does_not_call_adapter(self):
        code = asset_gen.cmd_next(self.project, channel_id="local", budget=5, confirm=False)
        self.assertEqual(code, 0)
        self.assertFalse(self.calls.is_file())

    def test_awaiting_review_blocks_next(self):
        asset_gen.save_queue(
            "p1",
            {"project_id": "p1", "spent": 0, "items": [{"asset_id": "CHAR1", "status": "awaiting_review"}]},
        )
        code = asset_gen.cmd_next(self.project, channel_id="local", budget=5, confirm=True)
        self.assertEqual(code, 1)

    def test_budget_blocks(self):
        code = asset_gen.cmd_next(self.project, channel_id="local", budget=0.5, confirm=True)
        self.assertEqual(code, 1)

    def test_confirm_keeps_one_image(self):
        code = asset_gen.cmd_next(self.project, channel_id="local", budget=5, confirm=True)
        self.assertEqual(code, 0)
        q = asset_gen.load_queue("p1")
        item = q["items"][0]
        self.assertEqual(item["status"], "awaiting_review")
        self.assertTrue(item.get("anomaly"))
        self.assertEqual(item.get("path"), "a.png")
        text = self.calls.read_text(encoding="utf-8")
        self.assertNotIn("http", text.lower())

    def test_accept_requires_awaiting_review(self):
        asset_gen.save_queue(
            "p1",
            {"project_id": "p1", "spent": 0, "items": [{"asset_id": "CHAR1", "status": "queued"}]},
        )
        self.assertEqual(asset_gen.cmd_accept(self.project, "CHAR1", None), 1)

    def test_unknown_blocks_next(self):
        asset_gen.save_queue(
            "p1",
            {"project_id": "p1", "spent": 0, "items": [{"asset_id": "CHAR1", "status": "unknown"}]},
        )
        self.assertEqual(asset_gen.cmd_next(self.project, channel_id="local", budget=5, confirm=True), 1)

    def test_resolve_charged_adds_spent(self):
        asset_gen.save_queue(
            "p1",
            {
                "project_id": "p1",
                "spent": 0,
                "items": [{"asset_id": "CHAR1", "status": "unknown", "charged": 1.0}],
            },
        )
        self.assertEqual(asset_gen.cmd_resolve(self.project, "CHAR1", 1), 0)
        self.assertEqual(asset_gen.load_queue("p1")["spent"], 1.0)

    def test_failed_next_records_charged_for_resolve(self):
        (self.adapter / "fake.py").write_text("def generate(payload):\n    raise RuntimeError('boom')\n", encoding="utf-8")
        code = asset_gen.cmd_next(self.project, channel_id="local", budget=5, confirm=True)
        self.assertEqual(code, 3)
        item = asset_gen.load_queue("p1")["items"][0]
        self.assertEqual(item["status"], "unknown")
        self.assertEqual(item.get("charged"), 1.0)
        self.assertEqual(asset_gen.cmd_resolve(self.project, "CHAR1", 1), 0)
        self.assertEqual(asset_gen.load_queue("p1")["spent"], 1.0)


if __name__ == "__main__":
    unittest.main()
