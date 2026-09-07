from enum import StrEnum


class ProjectType(StrEnum):
    ORGANIC = "organic"
    SEMI_DETACHED = "semi_detached"
    EMBEDDED = "embedded"


# Basic COCOMO, Boehm 1981 - standard published coefficients.
EFFORT_COEFFICIENTS = {
    ProjectType.ORGANIC: (2.4, 1.05),
    ProjectType.SEMI_DETACHED: (3.0, 1.12),
    ProjectType.EMBEDDED: (3.6, 1.20),
}
SCHEDULE_COEFFICIENTS = {
    ProjectType.ORGANIC: (2.5, 0.38),
    ProjectType.SEMI_DETACHED: (2.5, 0.35),
    ProjectType.EMBEDDED: (2.5, 0.32),
}


def effort_person_months(kloc: float, project_type: ProjectType) -> float:
    a, b = EFFORT_COEFFICIENTS[project_type]
    return a * (kloc**b)


def schedule_months(effort_pm: float, project_type: ProjectType) -> float:
    c, d = SCHEDULE_COEFFICIENTS[project_type]
    return c * (effort_pm**d)


def estimate(kloc: float, project_type: ProjectType) -> dict:
    effort_pm = effort_person_months(kloc, project_type)
    schedule = schedule_months(effort_pm, project_type)
    headcount = round(effort_pm / schedule) if schedule else 0
    return {
        "project_type": project_type.value,
        "kloc": kloc,
        "effort_pm": round(effort_pm, 1),
        "schedule_months": round(schedule, 1),
        "headcount": headcount,
    }
