from __future__ import annotations

import math

import constants
from models.tds_model import calc_drip_volume


def _predict_closed_compounds(
    roast_code: str,
    temp: float,
    dial: float,
    effective_steep: float,
    water_mg_frac: float,
) -> dict:
    mg_delta = water_mg_frac - 0.50
    ac_sw_mult = 1.0 + mg_delta * constants.MG_FRAC_AC_SW_MULT
    ps_cga_mult = 1.0 + (-mg_delta) * constants.MG_FRAC_PS_CGA_MULT

    base_profile = constants.IDEAL_FLAVOR[(roast_code, "mid")]

    ac = base_profile["AC"]
    ac *= 1 + (temp - 90) * 0.02
    ac *= math.exp(-constants.K_AC_DECAY * max(effective_steep - 150, 0))
    ac *= ac_sw_mult

    sw = base_profile["SW"]
    optimal_sw_temp = constants.ROAST_TABLE[roast_code]["base_temp"] - 2
    sw *= 1 - abs(temp - optimal_sw_temp) * 0.01
    sw *= 1 + max(min(effective_steep - 120, 60), 0) * 0.002
    sw *= ac_sw_mult

    ps = base_profile["PS"] * (1.0 + max(4.5 - dial, 0) * 0.45)
    if effective_steep > 120:
        extra_time = effective_steep - 120
        ps += constants.PS_TIME_MAX * (1.0 - math.exp(-constants.K_PS * extra_time))
    ps *= max(0.0, 1.0 + (temp - 90) * 0.015)
    ps *= ps_cga_mult
    ps = min(ps, 1.0)

    ca = base_profile["CA"] * (1.0 - math.exp(-constants.K_CA * effective_steep))

    cga = base_profile["CGA"]
    cga *= 1 + max(temp - 92, 0) * 0.03
    cga *= 1.0 + constants.CGA_TIME_MAX * (
        1.0 - math.exp(-constants.K_CGA_TIME * max(effective_steep - 150, 0))
    )
    cga *= ps_cga_mult

    mel = base_profile["MEL"] * (1 + (temp - 90) * 0.01)

    return {
        "AC": ac,
        "SW": sw,
        "PS": ps,
        "CA": ca,
        "CGA": cga,
        "MEL": mel,
    }


def predict_compounds(
    roast_code: str,
    temp: float,
    dial: float,
    steep_sec: float,
    ey: float,
    water_kh: float = 30,
    water_mg_frac: float = 0.40,
    press_equiv: float = 0,
    pour_offset: float = 0,
    water_ml: float = 400,
    seal_delay: float = constants.SEAL_DELAY_DEFAULT,
) -> dict:
    effective_steep = max(0.0, steep_sec - pour_offset) + press_equiv
    main_profile = _predict_closed_compounds(roast_code, temp, dial, effective_steep, water_mg_frac)

    drip_time = water_ml / constants.POUR_RATE + seal_delay
    drip_volume = calc_drip_volume(water_ml, dial, drip_time)
    drip_ratio = min(max(drip_volume / max(water_ml, 1e-6), 0.0), 0.35)

    if drip_ratio > 0:
        drip_profile = _predict_closed_compounds(
            roast_code,
            temp,
            dial,
            max(1.0, drip_time * constants.PRE_SEAL_CONTACT_FRACTION),
            water_mg_frac,
        )
        drip_profile["AC"] *= constants.PRE_SEAL_AC_MULT
        drip_profile["SW"] *= constants.PRE_SEAL_SW_MULT
        drip_profile["PS"] *= constants.PRE_SEAL_PS_MULT
        drip_profile["CA"] *= constants.PRE_SEAL_CA_MULT
        drip_profile["CGA"] *= constants.PRE_SEAL_CGA_MULT
        drip_profile["MEL"] *= constants.PRE_SEAL_MEL_MULT
        profile = {
            key: main_profile[key] * (1.0 - drip_ratio) + drip_profile[key] * drip_ratio
            for key in constants.KEYS
        }
    else:
        profile = main_profile

    return {key: round(profile[key], 4) for key in constants.KEYS}
