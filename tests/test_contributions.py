from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from refresh_contributions import START, END, needs_refresh, replace_block, text_block


class ContributionSummaryTests(unittest.TestCase):
    def test_total_is_text_with_a_link_to_the_native_graph(self):
        block = text_block("bhargavm-iiits", 566, "26 Oct 2026, 20:30 IST")
        self.assertIn("## 566 contributions in the last year", block)
        self.assertIn("#js-contribution-activity-description", block)
        self.assertNotIn("![", block)
        self.assertNotIn("<img", block)

    def test_initial_summary_is_created(self):
        self.assertTrue(needs_refresh({}, 566, 0))

    def test_automation_does_not_create_a_counting_loop(self):
        state = {"total": 566, "real_activity": 566}
        self.assertFalse(needs_refresh(state, 567, 1))

    def test_real_new_contribution_updates_the_summary(self):
        state = {"total": 566, "real_activity": 566}
        self.assertTrue(needs_refresh(state, 568, 1))

    def test_delayed_github_index_does_not_write_an_identical_total(self):
        state = {"total": 566, "real_activity": 566}
        self.assertFalse(needs_refresh(state, 566, 1))

    def test_refresh_preserves_the_project_directory(self):
        old = f"{START}\nold\n{END}\n\n# Technology directory\nProjects"
        new = replace_block(old, text_block("bhargavm-iiits", 566, "checked"))
        self.assertTrue(new.endswith("# Technology directory\nProjects"))

    def test_missing_markers_preserve_existing_content(self):
        with self.assertRaises(ValueError):
            replace_block("My profile", "replacement")


if __name__ == "__main__":
    unittest.main()
