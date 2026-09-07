import unittest

from codelexity.findings import all_findings, duplication_findings, unit_complexity_findings, unit_size_findings
from codelexity.models import AnalysisResult, ComponentMetric, DuplicateBlock, FileMetric, Language, UnitMetric


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
        UnitMetric(
            file="a.py",
            qualified_name="g",
            kind="function",
            language=Language.PYTHON,
            start_line=6,
            end_line=70,
            loc=65,
            complexity=30,
        ),
    )
    files = (
        FileMetric(
            file="a.py", language=Language.PYTHON, loc=70, incoming_references=3, duplicate_loc=7, component="."
        ),
    )
    components = (
        ComponentMetric(
            name=".", depth=0, loc=70, file_count=1, efferent=0, afferent=0, independence_score=1.0, files=("a.py",)
        ),
    )
    duplicate_blocks = (
        DuplicateBlock(file_a="a.py", lines_a=(1, 5), file_b="b.py", lines_b=(10, 14), token_length=60),
    )
    return AnalysisResult(
        total_loc=70,
        units=units,
        files=files,
        components=components,
        duplicate_blocks=duplicate_blocks,
        edges=(),
        unparsed_files=(),
        unsupported_files=(),
    )


class TestFindings(unittest.TestCase):
    def test_unit_size_bands(self):
        rows = unit_size_findings(_analysis())
        self.assertEqual({r["unit"]: r["band"] for r in rows}, {"f": "low", "g": "very_high"})

    def test_unit_complexity_fields_match_requested_shape(self):
        rows = unit_complexity_findings(_analysis())
        row = next(r for r in rows if r["unit"] == "g")
        self.assertEqual(row["file"], "a.py")
        self.assertEqual(row["mccabe_complexity"], 30)
        self.assertEqual(row["loc"], 65)
        self.assertEqual(row["band"], "very_high")

    def test_all_findings_covers_every_report_metric(self):
        findings = all_findings(_analysis())
        self.assertEqual(
            set(findings),
            {"Unit Complexity", "Duplication", "Module Coupling", "Component Independence", "Unit Size", "Volume"},
        )
        self.assertEqual(len(findings["Unit Size"]), 2)
        self.assertEqual(len(findings["Module Coupling"]), 1)
        # System/Unit/Architecture Level order, confirmed by the user.
        self.assertEqual(
            list(findings),
            ["Volume", "Duplication", "Unit Size", "Unit Complexity", "Module Coupling", "Component Independence"],
        )

    def test_duplication_findings_share_a_clone_id_per_pair(self):
        rows = duplication_findings(_analysis())
        self.assertEqual(len(rows), 2)  # one row per side of the one clone block
        self.assertEqual(rows[0]["clone_id"], rows[1]["clone_id"])
        self.assertEqual({r["file"] for r in rows}, {"a.py", "b.py"})
        self.assertEqual(rows[0]["token_length"], 60)


if __name__ == "__main__":
    unittest.main()
