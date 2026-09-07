import unittest

from codelexity.models import AnalysisResult, ComponentMetric, FileMetric, Language, UnitMetric
from codelexity.report import build_report
from codelexity.scoring import score_analysis


def _analysis() -> AnalysisResult:
    units = (
        UnitMetric(
            file="a.py",
            qualified_name="f",
            kind="function",
            language=Language.PYTHON,
            start_line=1,
            end_line=5,
            loc=5,
            complexity=2,
        ),
    )
    files = (
        FileMetric(file="a.py", language=Language.PYTHON, loc=5, incoming_references=0, duplicate_loc=0, component="."),
    )
    components = (
        ComponentMetric(
            name=".", depth=0, loc=5, file_count=1, efferent=0, afferent=0, independence_score=1.0, files=("a.py",)
        ),
    )
    return AnalysisResult(
        total_loc=5,
        units=units,
        files=files,
        components=components,
        duplicate_blocks=(),
        edges=(),
        unparsed_files=(),
        unsupported_files=(),
    )


class TestBuildReport(unittest.TestCase):
    def test_report_contains_findings_export_and_embedded_graph(self):
        analysis = _analysis()
        scores = score_analysis(analysis)
        cocomo = {"project_type": "organic", "kloc": 0.005, "effort_pm": 0.1, "schedule_months": 0.5, "headcount": 1}

        html = build_report(
            analysis, scores, cocomo, "<html><body>graph</body></html>", "2026-01-01T00:00:00Z", "/repo"
        )

        self.assertIn("downloadFindingsCSV", html)
        self.assertIn("downloadAllFindingsXlsx", html)
        self.assertIn("xlsx.full.min.js", html)
        self.assertIn("srcdoc=", html)
        self.assertIn('"Unit Complexity"', html)  # findings JSON embedded
        self.assertNotIn("</script>graph", html)  # embedded graph HTML doesn't break out of srcdoc


if __name__ == "__main__":
    unittest.main()
