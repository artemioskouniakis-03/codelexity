from codelexity.models import AnalysisResult
from codelexity.thresholds import (
    COMPONENT_RISK_BANDS,
    MODULE_COUPLING_BANDS,
    UNIT_COMPLEXITY_BANDS,
    UNIT_SIZE_BANDS,
    band_for,
)


def unit_size_findings(analysis: AnalysisResult) -> list[dict]:
    return [
        {"file": u.file, "unit": u.qualified_name, "loc": u.loc, "band": band_for(u.loc, UNIT_SIZE_BANDS).value}
        for u in analysis.units
    ]


def unit_complexity_findings(analysis: AnalysisResult) -> list[dict]:
    return [
        {
            "file": u.file,
            "unit": u.qualified_name,
            "mccabe_complexity": u.complexity,
            "loc": u.loc,
            "band": band_for(u.complexity, UNIT_COMPLEXITY_BANDS).value,
        }
        for u in analysis.units
    ]


def module_coupling_findings(analysis: AnalysisResult) -> list[dict]:
    return [
        {
            "file": f.file,
            "incoming_references": f.incoming_references,
            "band": band_for(f.incoming_references, MODULE_COUPLING_BANDS).value,
        }
        for f in analysis.files
    ]


def duplication_findings(analysis: AnalysisResult) -> list[dict]:
    """Two rows per detected clone (one per side), sharing a `clone_id` - sort/filter by
    that id to see the two locations that make up one duplicate pair. A block found
    between three or more files still only ever produces pairs (file_a, file_b), so the
    same clone_id can appear on more than two rows if a passage is duplicated in several
    places at once - they all belong to the same reported clone."""
    rows = []
    for clone_id, b in enumerate(analysis.duplicate_blocks, start=1):
        rows.append(
            {
                "clone_id": clone_id,
                "file": b.file_a,
                "start_line": b.lines_a[0],
                "end_line": b.lines_a[1],
                "line_length": b.line_length,
            }
        )
        rows.append(
            {
                "clone_id": clone_id,
                "file": b.file_b,
                "start_line": b.lines_b[0],
                "end_line": b.lines_b[1],
                "line_length": b.line_length,
            }
        )
    return rows


def component_independence_findings(analysis: AnalysisResult) -> list[dict]:
    return [
        {
            "component": c.name,
            "depth": c.depth,
            "file_count": c.file_count,
            "efferent": c.efferent,
            "afferent": c.afferent,
            "independence_score": round(c.independence_score, 3),
            "band": band_for(1.0 - c.independence_score, COMPONENT_RISK_BANDS).value,
        }
        for c in analysis.components
    ]


def volume_findings(analysis: AnalysisResult) -> list[dict]:
    return [{"file": f.file, "loc": f.loc} for f in analysis.files]


def all_findings(analysis: AnalysisResult) -> dict[str, list[dict]]:
    """One entry per report metric section, in the same System/Unit/Architecture Level
    order they're displayed - consumed both for the per-section CSV download and the
    combined multi-sheet export."""
    return {
        # System Level
        "Volume": volume_findings(analysis),
        "Duplication": duplication_findings(analysis),
        # Unit Level
        "Unit Size": unit_size_findings(analysis),
        "Unit Complexity": unit_complexity_findings(analysis),
        # Architecture Level
        "Module Coupling": module_coupling_findings(analysis),
        "Component Independence": component_independence_findings(analysis),
    }
