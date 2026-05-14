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


def _arrhenius(temp_c: float, ea_kj_per_mol: float) -> float:
    """Arrhenius rate ratio k(T) / k(T_ref). Returns 1.0 at T=T_ref.

    k(T) = k_ref · exp(Ea/R · (1/T_ref − 1/T))
    Global monotone, no threshold, no inflection — pure physics structure.
    """
    T_K = temp_c + 273.15
    T_ref_K = constants.ARRHENIUS_T_REF_C + 273.15
    return math.exp(
        ea_kj_per_mol * 1000.0 / constants.GAS_CONSTANT_R
        * (1.0 / T_ref_K - 1.0 / T_K)
    )


def _predict_closed_compounds(
    roast_code: str,
    temp: float,
    dial: float,
    effective_steep: float,
    water_mg_frac: float,
    water_gh: float = 50.0,
) -> dict:
    """Phase 6: pure Arrhenius × first-order kinetics.

    Every compound follows `base × (1 − exp(−k·t))` with `k = K_ref · arr(T) · grind`.
    AC adds a degradation term `× exp(−k_deg·t)`. No onset gates, no time floors,
    no tent functions, no temperature-threshold softplus — all temperature
    sensitivity flows through Arrhenius rate ratios. Perceptual thresholds
    (SW_AROMA high-T loss, SCORCH) live in scoring.py per CLAUDE.md principle #4.
    """
    mg_ppm = water_gh * water_mg_frac
    ca_ppm = water_gh * (1.0 - water_mg_frac)
    mg_delta = (mg_ppm - constants.MG_PPM_REF) / (constants.MG_PPM_REF * 2.0)
    ca_delta = (ca_ppm - constants.CA_PPM_REF) / (constants.CA_PPM_REF * 2.0)
    ac_sw_mult = 1.0 + mg_delta * constants.MG_FRAC_AC_SW_MULT
    ps_cga_mult = 1.0 + ca_delta * constants.MG_FRAC_PS_CGA_MULT

    base_profile = constants.COMPOUND_BASE[roast_code]

    # 研磨表面積耦合：粗磨擴散慢，rate ∝ exp(coeff × (base − dial))（連續、無閾值）
    grind_kinetics = math.exp(constants.GRIND_KINETICS_COEFF * (constants.DIAL_BASE - dial))

    t = effective_steep

    # ── AC (acidity): fast extraction × slow degradation (both Arrhenius) ─
    arr_ac_ext = _arrhenius(temp, constants.AC_EXT_EA)
    arr_ac_deg = _arrhenius(temp, constants.AC_DEG_EA)
    k_ac_ext = constants.K_AC_EXTRACT * arr_ac_ext * grind_kinetics
    k_ac_deg = constants.K_AC_DEG * arr_ac_deg
    ac = base_profile["AC"] * (1.0 - math.exp(-k_ac_ext * t)) * math.exp(-k_ac_deg * t)
    ac *= ac_sw_mult

    # ── SW (sweetness): pure first-order. SW_AROMA in scoring.py handles >97°C loss ─
    arr_sw = _arrhenius(temp, constants.SW_EA)
    k_sw_eff = constants.K_SW * arr_sw
    sw = base_profile["SW"] * (1.0 - math.exp(-k_sw_eff * t))
    sw *= ac_sw_mult
    sw *= math.exp(constants.SW_DIAL_COEFF * (constants.DIAL_BASE - dial))

    # ── PS (polysaccharides): pure first-order; exponential dial coupling ─
    arr_ps = _arrhenius(temp, constants.PS_EA)
    k_ps_eff = constants.K_PS * arr_ps
    ps = base_profile["PS"] * (1.0 - math.exp(-k_ps_eff * t))
    ps *= math.exp(constants.PS_DIAL_COEFF * (constants.DIAL_BASE - dial))
    ps *= ps_cga_mult
    ps = _soft_cap(ps, 1.0, k=10.0)

    # ── CA (caffeic acid): pure first-order with Arrhenius ─
    arr_ca = _arrhenius(temp, constants.CA_EA)
    k_ca_eff = constants.K_CA * arr_ca
    ca = base_profile["CA"] * (1.0 - math.exp(-k_ca_eff * t))

    # ── CGA (chlorogenic acid): pure first-order, Arrhenius + grind coupling ─
    arr_cga = _arrhenius(temp, constants.CGA_EA)
    k_cga_eff = constants.K_CGA_TIME * arr_cga * grind_kinetics
    cga = base_profile["CGA"] * (1.0 - math.exp(-k_cga_eff * t))
    cga *= ps_cga_mult

    # ── MEL (melanoidins): pure first-order with Arrhenius ─
    arr_mel = _arrhenius(temp, constants.MEL_EA)
    k_mel_eff = constants.K_MEL_TIME * arr_mel
    mel = base_profile["MEL"] * (1.0 - math.exp(-k_mel_eff * t))

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

    # ── EY 冪律修正（保留：大分子溶出需萃取能量，非口感偏好） ────
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
