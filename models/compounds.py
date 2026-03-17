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
    water_gh: float = 50.0,
) -> dict:
    mg_ppm = water_gh * water_mg_frac
    ca_ppm = water_gh * (1.0 - water_mg_frac)
    mg_delta = (mg_ppm - constants.MG_PPM_REF) / (constants.MG_PPM_REF * 2.0)
    ca_delta = (ca_ppm - constants.CA_PPM_REF) / (constants.CA_PPM_REF * 2.0)
    ac_sw_mult = 1.0 + mg_delta * constants.MG_FRAC_AC_SW_MULT
    ps_cga_mult = 1.0 + ca_delta * constants.MG_FRAC_PS_CGA_MULT

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
    water_gh: float = 50.0,
    water_kh: float = 30,
    water_mg_frac: float = 0.40,
    press_equiv: float = 0,
    pour_offset: float = 0,
    water_ml: float = 400,
    seal_delay: float = constants.SEAL_DELAY_DEFAULT,
    dose: float = 18.0,
    press_sec: float = 30.0,
) -> dict:
    effective_steep = max(0.0, steep_sec - pour_offset) + press_equiv
    main_profile = _predict_closed_compounds(
        roast_code, temp, dial, effective_steep, water_mg_frac, water_gh
    )

    drip_time = water_ml / constants.POUR_RATE + seal_delay
    drip_volume = calc_drip_volume(water_ml, dial, drip_time, dose)
    drip_ratio = min(max(drip_volume / max(water_ml, 1e-6), 0.0), 0.35)

    if drip_ratio > 0:
        drip_profile = _predict_closed_compounds(
            roast_code,
            temp,
            dial,
            max(1.0, drip_time * constants.PRE_SEAL_CONTACT_FRACTION),
            water_mg_frac,
            water_gh,
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

    # EY 感知修正：以理想 EY 為基準，實際 EY 偏低時壓低慢萃物質
    ey_prefer = constants.EY_PREFER[roast_code]
    ey_ratio = min(ey / ey_prefer, 1.0)  # 超過理想值不額外獎勵，夾緊至 1.0

    profile["PS"] *= (ey_ratio ** constants.EY_PS_EXP)
    profile["CGA"] *= (ey_ratio ** constants.EY_CGA_EXP)
    profile["AC"] *= (ey_ratio ** constants.EY_AC_EXP)

    # 下壓滲流選擇性：壓力驅動水流與靜態浸泡的化合物萃出差異
    press_frac = min(press_sec / constants.PRESS_PERC_REF_SEC, 2.0)
    profile["CGA"] = min(profile["CGA"] * (1.0 + constants.PRESS_PERC_CGA_DIFF * press_frac), 1.0)
    profile["MEL"] = min(profile["MEL"] * (1.0 + constants.PRESS_PERC_MEL_DIFF * press_frac), 1.0)
    profile["CA"]  = min(profile["CA"]  * (1.0 + constants.PRESS_PERC_CA_DIFF  * press_frac), 1.0)
    profile["SW"]  = max(profile["SW"]  * (1.0 - constants.PRESS_PERC_SW_LOSS  * press_frac), 0.0)

    return {key: round(profile[key], 4) for key in constants.KEYS}
