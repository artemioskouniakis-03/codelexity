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

VOLUME_KLOC_BANDS = (
    (50, "Small"),
    (300, "Medium"),
    (1000, "Large"),
    (float("inf"), "Very Large"),
)


def band_for(value: float, bands: tuple) -> RiskBand:
    for upper, band in bands:
        if value <= upper:
            return band
    return bands[-1][1]


def volume_label(kloc: float) -> str:
    for upper, label in VOLUME_KLOC_BANDS:
        if kloc <= upper:
            return label
    return VOLUME_KLOC_BANDS[-1][1]
