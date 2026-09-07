import unittest

from codelexity.main import check_thresholds


class TestCheckThresholds(unittest.TestCase):
    def setUp(self):
        self.analytics = {"total_lines": 100, "maintainability_index": 42.0}

    def test_no_bounds_passes(self):
        self.assertEqual(check_thresholds(self.analytics, [], []), "")

    def test_within_bounds_passes(self):
        error = check_thresholds(self.analytics, [["total_lines", "500"]], [["maintainability_index", "40"]])
        self.assertEqual(error, "")

    def test_max_exceeded_fails(self):
        error = check_thresholds(self.analytics, [["total_lines", "50"]], [])
        self.assertIn("total_lines 100 exceeds the maximum allowed value of 50", error)

    def test_min_not_met_fails(self):
        error = check_thresholds(self.analytics, [], [["maintainability_index", "90"]])
        self.assertIn("maintainability_index 42.0 is below the minimum allowed value of 90", error)

    def test_hyphenated_key_is_normalized(self):
        error = check_thresholds(self.analytics, [["total-lines", "50"]], [])
        self.assertIn("total-lines 100 exceeds", error)

    def test_unknown_key_is_skipped_not_raised(self):
        error = check_thresholds(self.analytics, [["not_a_metric", "1"]], [])
        self.assertEqual(error, "")


if __name__ == "__main__":
    unittest.main()
