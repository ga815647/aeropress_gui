from __future__ import annotations

import math

import constants


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
) -> dict:
    effective_steep = max(0.0, steep_sec - pour_offset) + press_equiv

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
        "AC": round(ac, 4),
        "SW": round(sw, 4),
        "PS": round(ps, 4),
        "CA": round(ca, 4),
        "CGA": round(cga, 4),
        "MEL": round(mel, 4),
    }
