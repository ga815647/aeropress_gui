from __future__ import annotations

import math

import constants

_TDS_ANCHOR_LIST = [1.00, 1.20, 1.40]
_WEIGHT_TOTAL = sum(constants.WEIGHTS.values())
_CONC_FLOOR = 1e-8
_W1 = constants.BALANCE_PENALTY_WEIGHT
_W2 = constants.BODY_BITTER_PENALTY_WEIGHT


def _huber(x: float, delta: float) -> float:
    ax = abs(x)
    return 0.5 * ax * ax if ax <= delta else delta * (ax - 0.5 * delta)


def _huber_asym(x: float, delta: float, compound: str) -> float:
    base = _huber(x, delta)
    if compound in ("CA", "CGA") and x > 0:
        return base * constants.ASYM_BITTER_MULT
    if compound == "SW" and x < 0:
        return base * constants.ASYM_SWEET_MULT
    return base


def compute_actual_abs(actual_raw: dict, tds: float) -> dict:
    total_raw = sum(actual_raw[k] for k in constants.KEYS)
    if total_raw > 0:
        actual_fraction = {k: actual_raw[k] / total_raw for k in constants.KEYS}
    else:
        actual_fraction = {k: 0.0 for k in constants.KEYS}
    return {k: actual_fraction[k] * tds for k in constants.KEYS}


def build_ideal_abs(roast_code: str, tds: float) -> dict:
    tds_c = max(0.90, min(tds, 1.50))
    if tds_c <= _TDS_ANCHOR_LIST[0]:
        prop = constants.IDEAL_FLAVOR[(roast_code, "low")]
    elif tds_c >= _TDS_ANCHOR_LIST[-1]:
        prop = constants.IDEAL_FLAVOR[(roast_code, "high")]
    else:
        if tds_c <= _TDS_ANCHOR_LIST[1]:
            t = (tds_c - 1.00) / 0.20
            p0 = constants.IDEAL_FLAVOR[(roast_code, "low")]
            p1 = constants.IDEAL_FLAVOR[(roast_code, "mid")]
        else:
            t = (tds_c - 1.20) / 0.20
            p0 = constants.IDEAL_FLAVOR[(roast_code, "mid")]
            p1 = constants.IDEAL_FLAVOR[(roast_code, "high")]
        prop = {k: p0[k] * (1 - t) + p1[k] * t for k in constants.KEYS}
    return {k: prop[k] * tds for k in constants.KEYS}


def flavor_score(
    actual_raw: dict,
    ideal_abs: dict,
    tds: float,
    roast_code: str,
    water_kh: float = 30,
    t_slurry: float = 90,
    temp_initial: float = 90,
) -> float:
    actual_abs = compute_actual_abs(actual_raw, tds)
    kh_penalty = max(0.65, math.exp(-water_kh / constants.KH_PERCEPT_DECAY))
    actual_perceived = dict(actual_abs)
    actual_perceived["AC"] = actual_abs["AC"] * kh_penalty

    if temp_initial > constants.SW_AROMA_THRESH:
        sw_loss = min(
            (temp_initial - constants.SW_AROMA_THRESH) * constants.SW_AROMA_SLOPE,
            constants.SW_AROMA_CAP,
        )
        actual_perceived["SW"] = actual_abs["SW"] * (1.0 - sw_loss)

    scorch_threshold, cga_sens, mel_sens = constants.SCORCH_PARAMS[roast_code]
    if t_slurry > scorch_threshold:
        excess = t_slurry - scorch_threshold
        if cga_sens > 0:
            actual_perceived["CGA"] = actual_abs["CGA"] * (1.0 + excess * cga_sens)
        if mel_sens > 0:
            actual_perceived["MEL"] = actual_abs["MEL"] * (1.0 + excess * mel_sens)

    dot = sum(constants.WEIGHTS[k] * actual_perceived[k] * ideal_abs[k] for k in constants.KEYS)
    norm_a = math.sqrt(sum(constants.WEIGHTS[k] * actual_perceived[k] ** 2 for k in constants.KEYS))
    norm_i = math.sqrt(sum(constants.WEIGHTS[k] * ideal_abs[k] ** 2 for k in constants.KEYS))
    cosine_sim = dot / (norm_a * norm_i) if (norm_a > 0 and norm_i > 0) else 0.0

    conc_loss = sum(
        constants.WEIGHTS[k]
        * _huber_asym(
            (actual_perceived[k] - max(ideal_abs[k], constants.CONC_SENSITIVITY_FLOOR))
            / max(ideal_abs[k], constants.CONC_SENSITIVITY_FLOOR),
            constants.CONC_HUBER_DELTA,
            k,
        )
        for k in constants.KEYS
    ) / _WEIGHT_TOTAL
    conc_score = math.exp(-conc_loss)

    i_ac_sw = ideal_abs["AC"] / max(ideal_abs["SW"], _CONC_FLOOR)
    a_ac_sw = actual_perceived["AC"] / max(actual_perceived["SW"], _CONC_FLOOR)
    b_ac_sw = math.exp(-_huber((a_ac_sw - i_ac_sw) / max(i_ac_sw, _CONC_FLOOR), constants.CONC_HUBER_DELTA))

    mel_coeff = constants.MEL_BITTER_COEFF[roast_code]
    i_bitter = max(ideal_abs["CA"] + ideal_abs["CGA"] + ideal_abs["MEL"] * mel_coeff, _CONC_FLOOR)
    a_bitter = max(
        actual_perceived["CA"] + actual_perceived["CGA"] + actual_perceived["MEL"] * mel_coeff,
        _CONC_FLOOR,
    )
    i_ps_r = ideal_abs["PS"] / i_bitter
    a_ps_r = actual_perceived["PS"] / a_bitter
    b_ps = math.exp(-_huber((a_ps_r - i_ps_r) / max(i_ps_r, _CONC_FLOOR), constants.CONC_HUBER_DELTA))

    tds_prefer = constants.TDS_PREFER[roast_code]
    diff = tds - tds_prefer
    sigma = constants.TDS_GAUSS_SIGMA_LOW if diff < 0 else constants.TDS_GAUSS_SIGMA_HIGH
    tds_gauss = math.exp(-0.5 * (diff / sigma) ** 2)
    w3 = constants.TDS_W3_LOW if diff < 0 else constants.TDS_W3_HIGH
    tds_factor = 1 - w3 + w3 * tds_gauss

    cga_anchor_ideal = build_ideal_abs(roast_code, constants.TDS_PREFER[roast_code])
    cga_ideal_anchor = max(cga_anchor_ideal["CGA"], _CONC_FLOOR)
    cga_actual = actual_perceived["CGA"]
    cga_ratio = cga_actual / cga_ideal_anchor
    cga_astringency = 1.0
    if cga_ratio > constants.CGA_ASTRINGENCY_THRESHOLD:
        excess_ratio = cga_ratio / constants.CGA_ASTRINGENCY_THRESHOLD - 1.0
        cga_astringency = math.exp(-constants.CGA_ASTRINGENCY_SLOPE * excess_ratio**2)

    ac_excess_ratio = max(actual_perceived["AC"] / max(ideal_abs["AC"], _CONC_FLOOR) - 1.0, 0)
    cga_excess_ratio = max(cga_ratio / constants.CGA_ASTRINGENCY_THRESHOLD - 1.0, 0)
    harshness_product = ac_excess_ratio * cga_excess_ratio
    harshness_penalty = math.exp(-constants.HARSHNESS_SLOPE * harshness_product) if harshness_product > 0 else 1.0

    ashy_penalty = 1.0
    if roast_code in ("MD", "D"):
        mel_excess_ratio = max(actual_perceived["MEL"] / max(ideal_abs["MEL"], _CONC_FLOOR) - 1.0, 0)
        ashy_product = mel_excess_ratio * cga_excess_ratio
        ashy_penalty = math.exp(-constants.ASHY_SLOPE * ashy_product) if ashy_product > 0 else 1.0

    final = (
        cosine_sim
        * conc_score
        * (1 - _W1 + _W1 * b_ac_sw)
        * (1 - _W2 + _W2 * b_ps)
        * tds_factor
        * cga_astringency
        * harshness_penalty
        * ashy_penalty
    )

    if tds < constants.TDS_BROWN_WATER_FLOOR:
        final *= (tds / constants.TDS_BROWN_WATER_FLOOR) ** 2

    return round(final * 100, 1)
