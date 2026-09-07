import unittest

from codelexity.cocomo import ProjectType, effort_person_months, estimate, schedule_months


class TestCocomo(unittest.TestCase):
    def test_organic_effort_matches_basic_cocomo_reference(self):
        # Boehm 1981 Basic COCOMO: organic, 100 KLOC -> 2.4 * 100^1.05 ~= 302.1 person-months.
        self.assertAlmostEqual(effort_person_months(100, ProjectType.ORGANIC), 302.1, places=0)

    def test_embedded_costs_more_than_organic_for_the_same_size(self):
        organic = effort_person_months(100, ProjectType.ORGANIC)
        embedded = effort_person_months(100, ProjectType.EMBEDDED)
        self.assertGreater(embedded, organic)

    def test_schedule_grows_slower_than_effort(self):
        effort = effort_person_months(200, ProjectType.ORGANIC)
        schedule = schedule_months(effort, ProjectType.ORGANIC)
        self.assertGreater(schedule, 0)
        self.assertLess(schedule, effort)

    def test_estimate_returns_expected_keys(self):
        result = estimate(50, ProjectType.SEMI_DETACHED)
        for key in ("project_type", "kloc", "effort_pm", "schedule_months", "headcount"):
            self.assertIn(key, result)
        self.assertGreater(result["headcount"], 0)


if __name__ == "__main__":
    unittest.main()
