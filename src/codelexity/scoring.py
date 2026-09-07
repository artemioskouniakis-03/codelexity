import logging
from dataclasses import dataclass

from codelexity.models import AnalysisResult, ComponentMetric, FileMetric, UnitMetric
from codelexity.thresholds import (
    COMPONENT_RISK_BANDS,
    DUPLICATION_PCT_BANDS,
    MODULE_COUPLING_BANDS,
    SEVERITY_WEIGHT,
    UNIT_COMPLEXITY_BANDS,
    UNIT_SIZE_BANDS,
    band_for,
)

logger = logging.getLogger(__name__)

BREAKPOINTS = [(0, 5.5), (5, 5.0), (25, 4.0), (50, 3.0), (75, 2.0), (95, 1.0), (100, 0.5)]

WEIGHTS = {
    "unit_complexity": 0.25,
    "duplication": 0.20,
    "module_coupling": 0.20,
    "component_independence": 0.20,
    "unit_size": 0.15,
    # "volume" is intentionally excluded - it's a size descriptor, not a risk signal.
}


@dataclass(frozen=True, slots=True)
class MetricScore:
    metric: str
    severity_pct: float  # LOC-weighted % of code in each risk band, in [0, 100]
    raw_score: float  # 0.5-5.5
    stars: int  # 1-5
    band_distribution: dict[str, float]  # band -> % of LOC in that band


def severity_index(weighted_loc_by_band: dict[str, int], total_loc: int) -> float:
    if total_loc <= 0:
        return 0.0
    weighted = sum(loc * SEVERITY_WEIGHT[band] for band, loc in weighted_loc_by_band.items())
    return 100.0 * weighted / total_loc


def band_distribution(loc_by_band: dict[str, int], total_loc: int) -> dict[str, float]:
    if total_loc <= 0:
        return dict.fromkeys(SEVERITY_WEIGHT, 0.0)
    return {band: 100.0 * loc / total_loc for band, loc in loc_by_band.items()}


def raw_score(pct_severity: float) -> float:
    pct = min(100.0, max(0.0, pct_severity))
    for (x0, y0), (x1, y1) in zip(BREAKPOINTS, BREAKPOINTS[1:]):
        if x0 <= pct <= x1:
            t = (pct - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return 0.5


def stars(raw: float) -> int:
    if raw < 1.5:
        return 1
    if raw < 2.5:
        return 2
    if raw < 3.5:
        return 3
    if raw < 4.5:
        return 4
    return 5


def _loc_by_band(items: list[tuple[float, int]], bands: tuple) -> dict[str, int]:
    """`items` is a list of (metric_value, loc_weight) pairs."""
    result: dict[str, int] = {}
    for value, weight in items:
        band = band_for(value, bands)
        result[band] = result.get(band, 0) + weight
    return result


def _metric_score(metric: str, loc_by_band: dict[str, int], total_loc: int) -> MetricScore:
    pct = severity_index(loc_by_band, total_loc)
    r = raw_score(pct)
    return MetricScore(
        metric=metric,
        severity_pct=pct,
        raw_score=r,
        stars=stars(r),
        band_distribution=band_distribution(loc_by_band, total_loc),
    )


def score_unit_size(units: list[UnitMetric]) -> MetricScore:
    items = [(u.loc, u.loc) for u in units]
    total = sum(u.loc for u in units)
    return _metric_score("unit_size", _loc_by_band(items, UNIT_SIZE_BANDS), total)


def score_unit_complexity(units: list[UnitMetric]) -> MetricScore:
    items = [(u.complexity, u.loc) for u in units]
    total = sum(u.loc for u in units)
    return _metric_score("unit_complexity", _loc_by_band(items, UNIT_COMPLEXITY_BANDS), total)


def score_module_coupling(files: list[FileMetric]) -> MetricScore:
    items = [(f.incoming_references, f.loc) for f in files]
    total = sum(f.loc for f in files)
    return _metric_score("module_coupling", _loc_by_band(items, MODULE_COUPLING_BANDS), total)


def score_duplication(files: list[FileMetric]) -> MetricScore:
    items = [(100.0 * f.duplicate_loc / f.loc if f.loc else 0.0, f.loc) for f in files]
    total = sum(f.loc for f in files)
    return _metric_score("duplication", _loc_by_band(items, DUPLICATION_PCT_BANDS), total)


def score_component_independence(components: list[ComponentMetric]) -> MetricScore:
    items = [(1.0 - c.independence_score, c.loc) for c in components]
    total = sum(c.loc for c in components)
    return _metric_score("component_independence", _loc_by_band(items, COMPONENT_RISK_BANDS), total)


@dataclass(frozen=True, slots=True)
class ScoreReport:
    unit_size: MetricScore
    unit_complexity: MetricScore
    module_coupling: MetricScore
    duplication: MetricScore
    component_independence: MetricScore
    overall_raw: float
    overall_stars: int
    total_loc: int


def score_analysis(analysis: AnalysisResult) -> ScoreReport:
    scores = {
        "unit_size": score_unit_size(list(analysis.units)),
        "unit_complexity": score_unit_complexity(list(analysis.units)),
        "module_coupling": score_module_coupling(list(analysis.files)),
        "duplication": score_duplication(list(analysis.files)),
        "component_independence": score_component_independence(list(analysis.components)),
    }
    overall_raw = sum(WEIGHTS[m] * scores[m].raw_score for m in WEIGHTS)
    return ScoreReport(
        unit_size=scores["unit_size"],
        unit_complexity=scores["unit_complexity"],
        module_coupling=scores["module_coupling"],
        duplication=scores["duplication"],
        component_independence=scores["component_independence"],
        overall_raw=overall_raw,
        overall_stars=stars(overall_raw),
        total_loc=analysis.total_loc,
    )
