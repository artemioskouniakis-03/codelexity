import unittest

from codelexity.fte_calculations import COCOMO_MODES, maintenance_effort_ftes


class TestMaintenanceEffortFtes(unittest.TestCase):
    def test_matches_organic_and_embedded_formulas(self):
        total_lines = 20_000
        act = 0.1
        kloc = total_lines / 1000
        a_opt, b_opt = COCOMO_MODES["organic"]
        a_pess, b_pess = COCOMO_MODES["embedded"]
        expected_low = round(act * (a_opt * kloc**b_opt) / 12, 1)
        expected_high = round(act * (a_pess * kloc**b_pess) / 12, 1)

        low, point, high = maintenance_effort_ftes(total_lines, act=act)

        self.assertEqual(low, expected_low)
        self.assertEqual(high, expected_high)
        self.assertEqual(point, low)

    def test_act_scales_the_effort_not_the_kloc(self):
        # act applied to the effort output must never flip organic (low) above embedded (high),
        # unlike scaling KLOC before exponentiating, which does for small enough inputs.
        low, _, high = maintenance_effort_ftes(500, act=0.1)
        self.assertLessEqual(low, high)

    def test_full_score_lands_on_pessimistic_end(self):
        low, point, high = maintenance_effort_ftes(20_000, score=1.0)
        self.assertEqual(point, high)

    def test_low_is_never_above_high(self):
        low, _, high = maintenance_effort_ftes(20_000)
        self.assertLessEqual(low, high)

    def test_zero_lines_returns_zero(self):
        self.assertEqual(maintenance_effort_ftes(0), (0.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
