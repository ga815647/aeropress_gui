from __future__ import annotations

import math

import constants
from models.tds_model import calc_drip_volume, calc_retention


def calc_fines_ratio(dial: float) -> float:
    ratio = constants.FINES_RATIO_BASE + (constants.DIAL_BASE - dial) * constants.FINES_RATIO_DIAL_SLOPE
    return max(0.05, min(ratio, 0.35))


def _calc_t_eff(temp_slurry: float, k: float, r: float, t: float) -> float:
    kt = k * t
    if kt < 1e-9:
        return temp_slurry
    return constants.T_ENV + (temp_slurry - constants.T_ENV) * (k / (r + k)) * (
        (1 - math.exp(-(r + k) * t)) / (1 - math.exp(-kt))
    )


def _calc_phase_ey(
    roast_code: str,
    temp_slurry: float,
    dial: float,
    t_kinetic: float,
    dose: float,
    free_water: float,
) -> float:
    cfg = constants.ROAST_TABLE[roast_code]
    r = constants.COOL_RATE
    fines_ratio = calc_fines_ratio(dial)

    rt = r * t_kinetic
    if rt > 1e-9:
        t_avg = constants.T_ENV + (temp_slurry - constants.T_ENV) / rt * (1.0 - math.exp(-rt))
    else:
        t_avg = temp_slurry

    k_base_dynamic = constants.K_BASE * math.exp((t_avg - 90) * constants.ARRHENIUS_COEFF)
    k_b = k_base_dynamic * constants.K_BOULDERS_MULT * (1.8 ** ((constants.DIAL_BASE - dial) / 0.5))
    k_b = max(constants.K_MIN, min(k_b, constants.K_MAX))
    k_f = min(k_b * constants.K_FINES_MULT, constants.K_MAX * constants.K_FINES_MULT)

    t_eff_f = _calc_t_eff(temp_slurry, k_f, r, t_kinetic)
    t_eff_b = _calc_t_eff(temp_slurry, k_b, r, t_kinetic)

    base_temp = cfg["base_temp"]
    # 新（非線性：以平方根修正大豆量場景）
    # 物理依據：溶劑稀釋效應隨豆量增加呈遞減邊際（大豆量時每增加 1g 的影響小於小豆量時）
    # 係數 0.5 為保守估算，待折射儀實測不同豆量的 EY 後校正
    effective_dose_pressure = dose * constants.CONC_GRADIENT_COEFF * (constants.SWIRL_DOSE_REF / dose) ** 0.15
    brew_capacity = free_water / (free_water + effective_dose_pressure)

    def _ey_max(t_eff: float) -> float:
        return min((cfg["base_ey"] + 8.0) + (t_eff - base_temp) / 5 * 1.5, constants.EY_ABSOLUTE_MAX) * brew_capacity

    return (
        fines_ratio * _ey_max(t_eff_f) * (1 - math.exp(-k_f * t_kinetic))
        + (1 - fines_ratio) * _ey_max(t_eff_b) * (1 - math.exp(-k_b * t_kinetic))
    )


def calc_ey(
    roast_code: str,
    temp_initial: float,
    dial: float,
    steep_sec: float,
    dose: float,
    water_ml: float = 400,
    water_gh: float = 50,
    water_kh: float = 30,
    press_equiv: float = 0,
    pour_offset: float = 0,
    seal_delay: float = constants.SEAL_DELAY_DEFAULT,
) -> float:
    heat_water = water_ml
    heat_coffee = dose * constants.COFFEE_SPECIFIC_HEAT_RATIO
    t_mix = (heat_water * temp_initial + heat_coffee * constants.T_ENV) / (heat_water + heat_coffee)
    t_slurry = t_mix - constants.BREWER_TEMP_DROP

    swirl_mult = 1.0 + constants.SWIRL_CONVECTION_BASE * (constants.SWIRL_DOSE_REF / dose)
    t_kinetic = max(0.0, steep_sec - pour_offset) + constants.SWIRL_TIME_SEC * swirl_mult + press_equiv

    retention_water = dose * calc_retention(roast_code, dial)
    drip_time = water_ml / constants.POUR_RATE + seal_delay
    drip_volume = calc_drip_volume(water_ml, dial, drip_time, dose)
    main_free_water = max(water_ml - drip_volume - retention_water, 1.0)
    main_ey = _calc_phase_ey(roast_code, t_slurry, dial, t_kinetic, dose, main_free_water)

    drip_contact_time = drip_time * constants.PRE_SEAL_CONTACT_FRACTION
    drip_ey = _calc_phase_ey(
        roast_code,
        t_slurry,
        dial,
        drip_contact_time,
        dose,
        max(drip_volume, 1.0),
    )
    ey = main_ey + drip_ey * constants.PRE_SEAL_PERCOLATION_EFFICIENCY

    if water_gh < 20:
        ey *= 0.94
    elif water_gh <= 100:
        ey *= 1.0 + (water_gh - 20) / 800
    else:
        ey *= max(0.97, 1.10 - (water_gh - 100) / 1000)

    return round(min(ey, constants.EY_ABSOLUTE_MAX), 3)
