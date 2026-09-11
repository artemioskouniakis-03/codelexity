from enum import StrEnum


class RiskBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


SEVERITY_WEIGHT = {
    RiskBand.LOW: 0.0,
    RiskBand.MEDIUM: 1 / 3,
    RiskBand.HIGH: 2 / 3,
    RiskBand.VERY_HIGH: 1.0,
}

# (upper_bound_inclusive, band) pairs, checked in order; the last entry's upper bound is
# effectively infinite. Confirmed by the user.
UNIT_SIZE_BANDS = ((15, RiskBand.LOW), (30, RiskBand.MEDIUM), (60, RiskBand.HIGH), (float("inf"), RiskBand.VERY_HIGH))
UNIT_COMPLEXITY_BANDS = (
    (5, RiskBand.LOW),
    (10, RiskBand.MEDIUM),
    (25, RiskBand.HIGH),
    (float("inf"), RiskBand.VERY_HIGH),
)
MODULE_COUPLING_BANDS = (
    (10, RiskBand.LOW),
    (20, RiskBand.MEDIUM),
    (50, RiskBand.HIGH),
    (float("inf"), RiskBand.VERY_HIGH),
)

# Proposed (not specified by the user) - see report methodology footnote for justification.
DUPLICATION_PCT_BANDS = (
    (3.0, RiskBand.LOW),
    (10.0, RiskBand.MEDIUM),
    (20.0, RiskBand.HIGH),
    (float("inf"), RiskBand.VERY_HIGH),
)
COMPONENT_RISK_BANDS = (  # risk = 1 - independence_score
    (0.20, RiskBand.LOW),
    (0.40, RiskBand.MEDIUM),
    (0.65, RiskBand.HIGH),
    (float("inf"), RiskBand.VERY_HIGH),
)

# Confirmed by the user: Volume gets an actual star rating (not just a size label),
# derived directly from KLOC - bigger codebases score lower, informed by COCOMO's premise
# that effort scales super-linearly with size (see cocomo.project_type_for_kloc, which
# derives the COCOMO project type from the same KLOC value, replacing a manual selector).
VOLUME_STAR_BANDS = (
    (10, 5, "Very Small"),
    (50, 4, "Small"),
    (300, 3, "Medium"),
    (1000, 2, "Large"),
    (float("inf"), 1, "Very Large"),
)


def band_for(value: float, bands: tuple) -> RiskBand:
    for upper, band in bands:
        if value <= upper:
            return band
    return bands[-1][1]


def volume_stars(kloc: float) -> tuple[int, str]:
    """(stars, size label) for a KLOC value, per VOLUME_STAR_BANDS."""
    for upper, stars, label in VOLUME_STAR_BANDS:
        if kloc <= upper:
            return stars, label
    return VOLUME_STAR_BANDS[-1][1], VOLUME_STAR_BANDS[-1][2]


def volume_raw_score(kloc: float) -> float:
    """Volume's raw score (0.5-5.5) for the weighted overall score. VOLUME_STAR_BANDS is
    a direct star assignment (not a continuous formula like the other metrics), so this
    uses the star count itself as the raw score - consistent with every other metric's
    own star buckets, whose boundaries (raw_score.stars()) already center on whole
    numbers: stars(4.0) == 4, stars(3.0) == 3, etc."""
    stars, _ = volume_stars(kloc)
    return float(stars)
