"""H3 prompt format checks independent of story examples."""

import unittest

from validate_project import (
    BEAT_FIELDS,
    BEAT_FRAMING_FIELDS,
    _valid_screen_height_percent,
    validate_prompt_dialogue,
    validate_prompt_text,
)


class PromptValidationTests(unittest.TestCase):
    def test_ref2va_field_order(self):
        prompt = (
            "subject_definitions:\nsummary:\nretention_analysis:\n"
            "detailed_description:\noverall_soundscape:\nnon_diegetic_music:\n"
        )
        self.assertEqual(validate_prompt_text(prompt, "Ref2VA"), [])
        reordered = prompt.replace(
            "retention_analysis:\ndetailed_description:",
            "detailed_description:\nretention_analysis:",
        )
        self.assertTrue(any("fields/order" in e for e in validate_prompt_text(reordered, "Ref2VA")))

    def test_frame_mode_instruction(self):
        prompt = (
            "integrated_multimodal_description:\nbody\n"
            "overall_soundscape:\nsound\nnon_diegetic_music:\nmusic"
        )
        self.assertTrue(any("FL2VA prompt must start" in e for e in validate_prompt_text(prompt, "FL2VA")))


class PromptDialogueTests(unittest.TestCase):
    DIALOGUE = [
        {"utterance_id": "U1", "text": "沈砚，你终于来了。"},
        {"utterance_id": "U2", "text": "我答应过你，就一定到。"},
    ]

    def test_matching_dialogue_blocks_pass(self):
        prompt = (
            "她说：林晚 (S1)，<d>[Chinese] 沈砚，你终于来了。</d> 然后他说：沈砚 (S2)，"
            "<d>[Chinese] 我答应过你，就一定到。</d>"
        )
        self.assertEqual(validate_prompt_dialogue(prompt, self.DIALOGUE), [])

    def test_mistyped_dialogue_in_prompt_is_rejected(self):
        prompt = (
            "<d>[Chinese] 沈砚，你可算来了啊。</d>\n<d>[Chinese] 我答应过你，就一定到。</d>"
        )
        self.assertTrue(any("does not match the frozen utterance" in e for e in validate_prompt_dialogue(prompt, self.DIALOGUE)))

    def test_dialogue_block_count_must_match_shot(self):
        prompt = "<d>[Chinese] 沈砚，你终于来了。</d>"
        self.assertTrue(any("dialogue block(s)" in e for e in validate_prompt_dialogue(prompt, self.DIALOGUE)))

    def test_reordered_dialogue_blocks_are_rejected(self):
        prompt = (
            "<d>[Chinese] 我答应过你，就一定到。</d>\n<d>[Chinese] 沈砚，你终于来了。</d>"
        )
        self.assertTrue(validate_prompt_dialogue(prompt, self.DIALOGUE))

    def test_language_marker_and_whitespace_are_ignored(self):
        prompt = "<d>  [Chinese] 沈砚，你终于来了。  </d>\n<d>[Chinese] 我答应过你，就一定到。</d>"
        self.assertEqual(validate_prompt_dialogue(prompt, self.DIALOGUE), [])


class FramingValidationTests(unittest.TestCase):
    def test_screen_height_percent_accepts_framing_range(self):
        for value in (0.1, 3, 25, 65, 100):
            with self.subTest(value=value):
                self.assertTrue(_valid_screen_height_percent(value))

    def test_screen_height_percent_rejects_missing_or_out_of_range_values(self):
        for value in (None, 0, -1, 100.1, "65", True):
            with self.subTest(value=value):
                self.assertFalse(_valid_screen_height_percent(value))

    def test_new_framing_requirements_are_schema_versioned(self):
        self.assertIn("positions", BEAT_FIELDS)
        self.assertEqual(BEAT_FRAMING_FIELDS, ("viewpoint", "cut_reason"))


if __name__ == "__main__":
    unittest.main()
