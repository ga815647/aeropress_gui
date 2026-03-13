from __future__ import annotations

import math

import constants


def calc_drip_volume(water_ml: float, dial: float, drip_time: float) -> float:
    if water_ml <= 0 or drip_time <= 0:
        return 0.0

    dial_c = max(dial, 0.1)
    dial_mult = (dial_c / constants.DIAL_BASE) ** constants.PRE_SEAL_DRIP_DIAL_EXP
    raw_volume = constants.PRE_SEAL_DRIP_RATE_REF * drip_time * dial_mult
    capped_volume = min(raw_volume, water_ml * constants.PRE_SEAL_DRIP_MAX_RATIO)
    return round(max(0.0, capped_volume), 3)


def calc_retention(roast_code: str, dial: float) -> float:
    base = constants.RETENTION_BASE[roast_code]
    slope = constants.RETENTION_DIAL_SLOPE[roast_code]
    value = base + (constants.DIAL_BASE - dial) * slope
    return round(max(1.60, min(value, 2.80)), 2)


def calc_tds(roast_code: str, dose: float, ey: float, dial: float, water_ml: float = 400) -> float:
    retention = calc_retention(roast_code, dial)
    extracted_solids_g = dose * (ey / 100)
    water_yield_g = water_ml - dose * retention
    yield_mass_g = water_yield_g + extracted_solids_g
    if yield_mass_g <= 0:
        return 0.0
    return round((extracted_solids_g / yield_mass_g) * 100, 4)


def calc_swirl_wait(dial: float) -> int:
    raw = constants.SWIRL_WAIT_BASE + (constants.DIAL_BASE - dial) * constants.SWIRL_WAIT_SLOPE
    return int(max(constants.SWIRL_WAIT_MIN, min(raw, constants.SWIRL_WAIT_MAX)))


def calc_press_time(dose: float, dial: float, steep_sec: float = 120) -> int:
    swirl_wait_sec = calc_swirl_wait(dial)
    effective_compaction_time = steep_sec * (1.0 - constants.SWIRL_RESET_FRACTION) + swirl_wait_sec
    compaction_mult = 1.0 + (effective_compaction_time / 240.0) * constants.BED_COMPACTION_COEFF
    dial_modifier = math.exp((constants.DIAL_BASE - dial) * constants.DARCY_PRESS_EXP) * compaction_mult
    base_time = constants.PRESS_TIME_MIN + (dose - 18) * constants.PRESS_TIME_PER_G
    raw_time = dial_modifier * base_time
    return int(min(max(raw_time, constants.PRESS_TIME_MIN_FLOOR), constants.PRESS_TIME_MAX))


def apply_channeling(ey: float, compounds: dict, press_sec: float) -> tuple[float, dict]:
    if press_sec <= constants.CHANNELING_PRESS_THRESHOLD:
        return ey, compounds

    bypass_ratio = min(
        (press_sec - constants.CHANNELING_PRESS_THRESHOLD) * constants.CHANNELING_EY_SLOPE,
        constants.CHANNELING_BYPASS_MAX,
    )
    ey_out = ey * (1.0 - bypass_ratio)
    compounds_out = dict(compounds)
    compounds_out["CGA"] = compounds["CGA"] * (1.0 + bypass_ratio * constants.CHANNELING_CGA_MULT)
    return round(ey_out, 3), compounds_out
