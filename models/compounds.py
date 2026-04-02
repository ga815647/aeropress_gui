from __future__ import annotations

import math

import constants
from models.tds_model import calc_drip_volume


# ── 平滑輔助函數（取代所有 min/max 硬斷點） ──────────────────────────────

def _softplus(x: float, k: float = 1.0) -> float:
    """Smooth max(x, 0): ln(1 + exp(k*x)) / k.  k controls sharpness."""
    kx = k * x
    if kx > 20.0:
        return x
    if kx < -20.0:
        return 0.0
    return math.log1p(math.exp(kx)) / k


def _sigmoid(x: float, center: float = 0.0, k: float = 1.0) -> float:
    """Logistic sigmoid: smooth 0-to-1 transition centered at *center*."""
    z = k * (x - center)
    if z > 20.0:
        return 1.0
    if z < -20.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


def _soft_cap(x: float, cap: float, k: float = 10.0) -> float:
    """Smooth min(x, cap): x - softplus(x - cap, k)."""
    return x - _softplus(x - cap, k)


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

    base_profile = constants.COMPOUND_BASE[roast_code]

    # ── AC (acidity) ──────────────────────────────────────────────
    ac = base_profile["AC"]
    ac *= 1 + (temp - 90) * 0.02
    # 酸質衰減：softplus 取代 max，在 AC_DECAY_START 附近平滑過渡
    ac *= math.exp(-constants.K_AC_DECAY * _softplus(
        effective_steep - constants.AC_DECAY_START, k=0.10))
    # 高溫揮發性有機酸降解（>95°C 時揮發/熱分解加速）
    ac *= 1.0 - _softplus(
        temp - constants.AC_HIGH_TEMP_THRESH, k=0.5) * constants.AC_HIGH_TEMP_DECAY
    ac *= ac_sw_mult

    # ── SW (sweetness / aroma) ───────────────────────────────────
    sw = base_profile["SW"]
    optimal_sw_temp = constants.ROAST_TABLE[roast_code]["base_temp"] - 2
    sw *= 1 - abs(temp - optimal_sw_temp) * 0.01
    sw += constants.SW_TIME_MAX * (1.0 - math.exp(-constants.K_SW * effective_steep))
    sw *= ac_sw_mult

    # ── PS (polysaccharides / body) ──────────────────────────────
    ps = base_profile["PS"] * (1.0 + _softplus(constants.DIAL_BASE - dial, k=3.0) * 0.20)
    ps += constants.PS_TIME_MAX * (1.0 - math.exp(-constants.K_PS * effective_steep))
    ps *= _softplus(1.0 + (temp - 90) * 0.015, k=10.0)
    ps *= ps_cga_mult
    ps = _soft_cap(ps, 1.0, k=10.0)

    # ── CA (caffeic acid) ────────────────────────────────────────
    ca = base_profile["CA"] * (1.0 - math.exp(-constants.K_CA * effective_steep))

    # ── CGA (chlorogenic acid / astringency) ─────────────────────
    cga = base_profile["CGA"]
    cga *= 1 + _softplus(temp - 92, k=2.0) * 0.03
    cga *= 1.0 + constants.CGA_TIME_MAX * (
        1.0 - math.exp(-constants.K_CGA_TIME * _softplus(
            effective_steep - constants.CGA_TIME_ONSET, k=0.10))
    )
    cga *= ps_cga_mult

    # ── MEL (melanoidins / roasty bitterness) ────────────────────
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
    water_mg_frac: float = 0.40,
    press_equiv: float = 0,
    pour_offset: float = 0,
    water_ml: float = 400,
    seal_delay: float = constants.SEAL_DELAY_DEFAULT,
    dose: float = 18.0,
    press_sec: float = 30.0,
    area_cm2: float = 43.0,
    inverted: bool = False,
    n_swirls: int = 1,
    partial_seal_sec: float = 0.0,
    partial_seal_water_ml: float = 0.0,
) -> dict:
    # n_swirls: 離散整數邏輯，max 保留（規則豁免）
    extra_swirl_time = constants.SWIRL_TIME_SEC * max(n_swirls - 1, 0)
    effective_steep = _softplus(steep_sec - pour_offset, k=5.0) + press_equiv + extra_swirl_time
    main_profile = _predict_closed_compounds(
        roast_code, temp, dial, effective_steep, water_mg_frac, water_gh
    )

    # 倒置法：無預密封漏水 → drip_ratio = 0（離散選擇，非物理閾值）
    if inverted:
        drip_ratio = 0.0
    else:
        drip_time = water_ml / constants.POUR_RATE + seal_delay
        drip_volume = calc_drip_volume(
            water_ml, dial, drip_time, dose, area_cm2=area_cm2,
            partial_seal_sec=partial_seal_sec,
            partial_seal_water_ml=partial_seal_water_ml,
        )
        drip_ratio_raw = drip_volume / max(water_ml, 1e-6)
        drip_ratio = _soft_cap(_softplus(drip_ratio_raw, k=10.0), 0.35, k=10.0)

    if drip_ratio > 0:
        drip_contact = 1.0 + _softplus(
            drip_time * constants.PRE_SEAL_CONTACT_FRACTION - 1.0, k=5.0)
        drip_profile = _predict_closed_compounds(
            roast_code,
            temp,
            dial,
            drip_contact,
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

    # ── EY 感知修正 ───────────────────────────────────────────────
    ey_prefer = constants.EY_PREFER[roast_code]

    # SW + PS：sigmoid 發展門控（糖類/香氣/多醣需萃取才能充分釋放）
    # 設計：center = EY_PREFER × 0.62 → under-extract(EY<center) 強抑制；
    #        Championship(EY>center) 幾乎不受影響
    ey_center = ey_prefer * constants.EY_DEV_GATE_CENTER_FRAC
    dev_gate = constants.EY_DEV_GATE_FLOOR + (
        1.0 - constants.EY_DEV_GATE_FLOOR
    ) * _sigmoid(ey, center=ey_center, k=constants.EY_DEV_GATE_K)
    profile["SW"] *= dev_gate
    profile["PS"] *= dev_gate

    # CGA / AC / MEL / CA：冪律修正（無硬截斷，ey_ratio 不設上限）
    ey_ratio = ey / max(ey_prefer, 1e-6)
    profile["CGA"] *= ey_ratio ** constants.EY_CGA_EXP
    profile["AC"]  *= ey_ratio ** constants.EY_AC_EXP
    profile["MEL"] *= ey_ratio ** constants.EY_MEL_EXP
    profile["CA"]  *= ey_ratio ** constants.EY_CA_EXP

    # ── 下壓滲流選擇性 ──────────────────────────────────────────
    press_frac = _soft_cap(press_sec / constants.PRESS_PERC_REF_SEC, 2.0, k=5.0)
    profile["CGA"] = _soft_cap(
        profile["CGA"] * (1.0 + constants.PRESS_PERC_CGA_DIFF * press_frac), 1.0, k=10.0)
    profile["MEL"] = _soft_cap(
        profile["MEL"] * (1.0 + constants.PRESS_PERC_MEL_DIFF * press_frac), 1.0, k=10.0)
    profile["CA"] = _soft_cap(
        profile["CA"] * (1.0 + constants.PRESS_PERC_CA_DIFF * press_frac), 1.0, k=10.0)
    profile["SW"] = _softplus(
        profile["SW"] * (1.0 - constants.PRESS_PERC_SW_LOSS * press_frac), k=10.0)

    return {key: round(profile[key], 4) for key in constants.KEYS}
