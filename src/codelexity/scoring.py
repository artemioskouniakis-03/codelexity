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
    volume_raw_score,
    volume_stars,
)

logger = logging.getLogger(__name__)

BREAKPOINTS = [(0, 5.5), (5, 5.0), (25, 4.0), (50, 3.0), (75, 2.0), (95, 1.0), (100, 0.5)]

# Three levels, two metrics each, equal weight per level and equal weight within a level:
#   System Level:       Volume, Duplication
#   Unit Level:          Unit Size, Unit Complexity
#   Architecture Level:   Module Coupling, Component Independence
# 1/3 per level / 2 metrics per level = 1/6 each. Confirmed by the user: Volume now
# participates in the overall score (previously excluded as size-only context).
WEIGHTS = {
    "volume": 1 / 6,
    "duplication": 1 / 6,
    "unit_size": 1 / 6,
    "unit_complexity": 1 / 6,
    "module_coupling": 1 / 6,
    "component_independence": 1 / 6,
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
    """Always returns all four bands in canonical Low/Medium/High/Very-High order
    (SEVERITY_WEIGHT's own definition order), each present even at 0% - `_loc_by_band`
    only ever inserts a band once it sees a matching item, so relying on its insertion
    order here would put bands in a data-dependent order and skip any band nothing
    landed in. The report's band-distribution bar assumes this fixed green/yellow/
    orange/red order to render as a real severity gradient, not a color jumble."""
    if total_loc <= 0:
        return dict.fromkeys(SEVERITY_WEIGHT, 0.0)
    return {band: 100.0 * loc_by_band.get(band, 0) / total_loc for band in SEVERITY_WEIGHT}


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
    volume_raw: float  # star count (1-5) as a float - see thresholds.volume_raw_score
    volume_stars: int
    overall_raw: float
    overall_stars: int
    total_loc: int


# Component Independence is excluded here - a component (a folder-depth group of files)
# can straddle multiple languages, so its risk doesn't decompose cleanly per language.
# The remaining 5 metrics' weights are renormalized to sum to 1 (each was 1/6 of 1;
# scaled up by 6/5 they're 1/5 = 0.2 each).
LANGUAGE_WEIGHTS = {
    "volume": 0.2,
    "duplication": 0.2,
    "unit_size": 0.2,
    "unit_complexity": 0.2,
    "module_coupling": 0.2,
}


@dataclass(frozen=True, slots=True)
class LanguageScoreReport:
    language: str
    total_loc: int
    unit_size: MetricScore
    unit_complexity: MetricScore
    module_coupling: MetricScore
    duplication: MetricScore
    volume_raw: float
    volume_stars: int
    overall_raw: float
    overall_stars: int


def score_by_language(analysis: AnalysisResult) -> dict[str, LanguageScoreReport]:
    """One ScoreReport-like breakdown per language present in the analysis, using only
    that language's own units/files - lets a polyglot repo see e.g. "our Python is in
    good shape but the TypeScript is not" instead of only one blended number."""
    languages = sorted({f.language.value for f in analysis.files})
    result: dict[str, LanguageScoreReport] = {}
    for lang in languages:
        units = [u for u in analysis.units if u.language.value == lang]
        files = [f for f in analysis.files if f.language.value == lang]
        total_loc = sum(f.loc for f in files)
        kloc = total_loc / 1000
        v_raw = volume_raw_score(kloc)
        v_stars, _ = volume_stars(kloc)
        unit_size = score_unit_size(units)
        unit_complexity = score_unit_complexity(units)
        module_coupling = score_module_coupling(files)
        duplication = score_duplication(files)
        raw_by_metric = {
            "volume": v_raw,
            "duplication": duplication.raw_score,
            "unit_size": unit_size.raw_score,
            "unit_complexity": unit_complexity.raw_score,
            "module_coupling": module_coupling.raw_score,
        }
        overall_raw = sum(LANGUAGE_WEIGHTS[m] * raw_by_metric[m] for m in LANGUAGE_WEIGHTS)
        result[lang] = LanguageScoreReport(
            language=lang,
            total_loc=total_loc,
            unit_size=unit_size,
            unit_complexity=unit_complexity,
            module_coupling=module_coupling,
            duplication=duplication,
            volume_raw=v_raw,
            volume_stars=v_stars,
            overall_raw=overall_raw,
            overall_stars=stars(overall_raw),
        )
    return result


def score_analysis(analysis: AnalysisResult) -> ScoreReport:
    kloc = analysis.total_loc / 1000
    v_raw = volume_raw_score(kloc)
    v_stars, _ = volume_stars(kloc)
    scores = {
        "unit_size": score_unit_size(list(analysis.units)),
        "unit_complexity": score_unit_complexity(list(analysis.units)),
        "module_coupling": score_module_coupling(list(analysis.files)),
        "duplication": score_duplication(list(analysis.files)),
        "component_independence": score_component_independence(list(analysis.components)),
    }
    raw_by_metric = {name: s.raw_score for name, s in scores.items()} | {"volume": v_raw}
    overall_raw = sum(WEIGHTS[m] * raw_by_metric[m] for m in WEIGHTS)
    return ScoreReport(
        unit_size=scores["unit_size"],
        unit_complexity=scores["unit_complexity"],
        module_coupling=scores["module_coupling"],
        duplication=scores["duplication"],
        component_independence=scores["component_independence"],
        volume_raw=v_raw,
        volume_stars=v_stars,
        overall_raw=overall_raw,
        overall_stars=stars(overall_raw),
        total_loc=analysis.total_loc,
    )
