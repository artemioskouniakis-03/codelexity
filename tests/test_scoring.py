"""Verifies the confirmed star-scoring anchor points and bucket boundaries exactly."""

import unittest

from codelexity.models import AnalysisResult, ComponentMetric, FileMetric, Language, UnitMetric
from codelexity.scoring import WEIGHTS, band_distribution, raw_score, score_analysis, score_by_language, stars
from codelexity.thresholds import RiskBand


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


class TestBandDistribution(unittest.TestCase):
    def test_always_returns_all_four_bands_in_canonical_order(self):
        # Only HIGH has any LOC - LOW/MEDIUM/VERY_HIGH must still appear, at 0%, and in
        # green/yellow/orange/red order regardless of which band the data happened to hit.
        dist = band_distribution({RiskBand.HIGH: 100}, total_loc=100)
        self.assertEqual(list(dist), [RiskBand.LOW, RiskBand.MEDIUM, RiskBand.HIGH, RiskBand.VERY_HIGH])
        self.assertEqual(dist[RiskBand.LOW], 0.0)
        self.assertEqual(dist[RiskBand.HIGH], 100.0)

    def test_zero_total_loc_still_returns_all_bands(self):
        dist = band_distribution({}, total_loc=0)
        self.assertEqual(list(dist), [RiskBand.LOW, RiskBand.MEDIUM, RiskBand.HIGH, RiskBand.VERY_HIGH])


def _polyglot_analysis() -> AnalysisResult:
    units = (
        UnitMetric(
            file="a.py",
            qualified_name="f",
            kind="function",
            language=Language.PYTHON,
            start_line=1,
            end_line=3,
            loc=3,
            complexity=1,
        ),
        UnitMetric(
            file="b.ts",
            qualified_name="g",
            kind="function",
            language=Language.TYPESCRIPT,
            start_line=1,
            end_line=70,
            loc=65,
            complexity=30,
        ),
    )
    files = (
        FileMetric(file="a.py", language=Language.PYTHON, loc=3, incoming_references=0, duplicate_loc=0, component="."),
        FileMetric(
            file="b.ts", language=Language.TYPESCRIPT, loc=65, incoming_references=0, duplicate_loc=0, component="."
        ),
    )
    components = (
        ComponentMetric(
            name=".",
            depth=0,
            loc=68,
            file_count=2,
            efferent=0,
            afferent=0,
            independence_score=1.0,
            files=("a.py", "b.ts"),
        ),
    )
    return AnalysisResult(
        total_loc=68,
        units=units,
        files=files,
        components=components,
        duplicate_blocks=(),
        edges=(),
        unparsed_files=(),
        unsupported_files=(),
    )


class TestVolumeWeight(unittest.TestCase):
    def test_volume_participates_in_overall_score(self):
        self.assertIn("volume", WEIGHTS)
        self.assertAlmostEqual(sum(WEIGHTS.values()), 1.0)

    def test_a_very_large_codebase_pulls_the_overall_score_down_via_volume(self):
        analysis = _polyglot_analysis()
        small = score_analysis(analysis)
        huge = score_analysis(
            AnalysisResult(
                total_loc=2_000_000,
                units=analysis.units,
                files=analysis.files,
                components=analysis.components,
                duplicate_blocks=(),
                edges=(),
                unparsed_files=(),
                unsupported_files=(),
            )
        )
        self.assertLess(huge.overall_raw, small.overall_raw)


class TestScoreByLanguage(unittest.TestCase):
    def test_one_entry_per_language_present(self):
        result = score_by_language(_polyglot_analysis())
        self.assertEqual(set(result), {"python", "typescript"})

    def test_each_language_only_sees_its_own_units_and_files(self):
        result = score_by_language(_polyglot_analysis())
        self.assertEqual(result["python"].total_loc, 3)
        self.assertEqual(result["typescript"].total_loc, 65)
        # The TS unit is Very High complexity (30), the Python one is Low (1) - a
        # polyglot repo's blended score would hide this; per-language shouldn't.
        self.assertGreater(result["python"].unit_complexity.stars, result["typescript"].unit_complexity.stars)


if __name__ == "__main__":
    unittest.main()
