# COCOMO Basic (Boehm, 1981): Effort (person-months) = a * KLOC^b
COCOMO_MODES = {
    "organic": (2.4, 1.05),
    "semi-detached": (3.0, 1.12),
    "embedded": (3.6, 1.20),
}


def maintenance_effort_ftes(total_lines: int, act=0.1, score: float = 0.0):
    kloc = act * total_lines / 1000
    a_opt, b_opt = COCOMO_MODES["organic"]
    a_pess, b_pess = COCOMO_MODES["embedded"]
    low, high = round((a_opt * kloc**b_opt) / 12, 1), round((a_pess * kloc**b_pess) / 12, 1)
    return (low, low + score * (high - low), high)
