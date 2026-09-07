from codelexity.models import AnalysisResult
from codelexity.thresholds import (
    COMPONENT_RISK_BANDS,
    DUPLICATION_PCT_BANDS,
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
    rows = []
    for f in analysis.files:
        pct = 100.0 * f.duplicate_loc / f.loc if f.loc else 0.0
        rows.append(
            {
                "file": f.file,
                "duplicate_loc": f.duplicate_loc,
                "loc": f.loc,
                "duplicate_pct": round(pct, 1),
                "band": band_for(pct, DUPLICATION_PCT_BANDS).value,
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
    """One entry per report metric section, in the same order they're displayed -
    consumed both for the per-section CSV download and the combined multi-sheet export."""
    return {
        "Unit Complexity": unit_complexity_findings(analysis),
        "Duplication": duplication_findings(analysis),
        "Module Coupling": module_coupling_findings(analysis),
        "Component Independence": component_independence_findings(analysis),
        "Unit Size": unit_size_findings(analysis),
        "Volume": volume_findings(analysis),
    }
