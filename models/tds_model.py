from __future__ import annotations

import constants


def calc_drip_volume(
    water_ml: float,
    dial: float,
    drip_time: float,
    dose: float = 18.0,
    area_cm2: float = 43.0,
    partial_seal_sec: float = 0.0,
    partial_seal_water_ml: float = 0.0,
) -> float:
    if water_ml <= 0 or drip_time <= 0:
        return 0.0

    dial_c = max(dial, 0.1)
    dial_mult = (dial_c / constants.DIAL_BASE) ** constants.PRE_SEAL_DRIP_DIAL_EXP
    # 豆量阻力修正：豆量越多粉床越厚，漏水越少
    # 以 DOSE_DRIP_REF 為基準，指數 0.3 為保守估算（待實測校正）
    dose_resist_mult = (constants.DOSE_DRIP_REF / max(dose, 1.0)) ** 0.3
    # 達西定律截面積修正：Q ∝ A（截面積越大流量正比增加）
    # XL 內徑 90mm vs Standard 74mm → area_mult = 63.6/43.0 ≈ 1.48
    area_mult = area_cm2 / constants.DRIP_AREA_REF_CM2
    raw_volume = constants.PRE_SEAL_DRIP_RATE_REF * drip_time * dial_mult * dose_resist_mult * area_mult

    # 半密封補正（April 式：活塞插入 ~1cm，產生額外受控滲流）
    # 物理：半密封允許約 PARTIAL_SEAL_FLOW_FACTOR 倍的全開流量，
    #       但腔內僅 partial_seal_water_ml 產生靜水壓
    if partial_seal_sec > 0 and partial_seal_water_ml > 0:
        hydrostatic_ratio = min(partial_seal_water_ml / max(water_ml, 1.0), 1.0)
        ps_drip = (constants.PRE_SEAL_DRIP_RATE_REF
                   * constants.PARTIAL_SEAL_FLOW_FACTOR
                   * partial_seal_sec
                   * dial_mult
                   * dose_resist_mult
                   * area_mult
                   * hydrostatic_ratio)
        raw_volume += ps_drip

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
    clamped = max(constants.SWIRL_WAIT_MIN, min(raw, constants.SWIRL_WAIT_MAX))
    return int(round(clamped / 10) * 10)


def calc_press_time(dose: float, dial: float, steep_sec: float = 120, brewer_size: str = "xl") -> int:
    """返回固定的下壓時間，根據 brewer 型號"""
    return constants.BREWER_PRESETS[brewer_size]["fixed_press_sec"]


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
