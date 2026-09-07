"""Verifies the confirmed star-scoring anchor points and bucket boundaries exactly."""

import unittest

from codelexity.scoring import raw_score, stars


class TestRawScoreAnchors(unittest.TestCase):
    def test_confirmed_anchor_points(self):
        self.assertAlmostEqual(raw_score(0), 5.5)
        self.assertAlmostEqual(raw_score(5), 5.0)
        self.assertAlmostEqual(raw_score(25), 4.0)
        self.assertAlmostEqual(raw_score(50), 3.0)
        self.assertAlmostEqual(raw_score(75), 2.0)
        self.assertAlmostEqual(raw_score(95), 1.0)
        self.assertAlmostEqual(raw_score(100), 0.5)

    def test_monotonically_decreasing(self):
        pcts = [0, 5, 10, 25, 40, 50, 60, 75, 85, 95, 100]
        scores = [raw_score(p) for p in pcts]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_clamps_out_of_range_inputs(self):
        self.assertAlmostEqual(raw_score(-10), 5.5)
        self.assertAlmostEqual(raw_score(150), 0.5)


class TestStarBuckets(unittest.TestCase):
    def test_confirmed_bucket_boundaries(self):
        self.assertEqual(stars(0.5), 1)
        self.assertEqual(stars(1.49), 1)
        self.assertEqual(stars(1.5), 2)
        self.assertEqual(stars(2.49), 2)
        self.assertEqual(stars(2.5), 3)
        self.assertEqual(stars(3.49), 3)
        self.assertEqual(stars(3.5), 4)
        self.assertEqual(stars(4.49), 4)
        self.assertEqual(stars(4.5), 5)
        self.assertEqual(stars(5.5), 5)


if __name__ == "__main__":
    unittest.main()
