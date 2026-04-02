from __future__ import annotations

import math

import constants

_TDS_ANCHOR_LIST = [1.00, 1.20, 1.40]
_WEIGHT_TOTAL = sum(constants.WEIGHTS.values())
_CONC_FLOOR = 1e-8


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
    water_gh: float = 50,
    t_slurry: float = 90,
    temp_initial: float = 90,
    ey: float = 0.0,
    steep_sec: float = 0.0,
) -> float:

    # ── 1. 感知前處理（物理，非評分邏輯） ────────────────────────────────
    actual_abs = compute_actual_abs(actual_raw, tds)
    actual_perceived = dict(actual_abs)

    # KH 壓制酸質感知
    actual_perceived["AC"] = actual_abs["AC"] * max(0.65, math.exp(-water_kh / constants.KH_PERCEPT_DECAY))

    # 高溫 SW 香氣損失（連續，max 僅作數值保護）
    excess_temp = max(temp_initial - constants.SW_AROMA_THRESH, 0.0)
    sw_loss = min(excess_temp * constants.SW_AROMA_SLOPE, constants.SW_AROMA_CAP)
    actual_perceived["SW"] = actual_abs["SW"] * (1.0 - sw_loss)

    # 高溫焦苦放大（深焙焦化物理，焙度分支合法）
    scorch_threshold, cga_sens, mel_sens = constants.SCORCH_PARAMS[roast_code]
    if t_slurry > scorch_threshold:
        excess = t_slurry - scorch_threshold
        if cga_sens > 0:
            actual_perceived["CGA"] *= (1.0 + excess * cga_sens)
        if mel_sens > 0:
            actual_perceived["MEL"] *= (1.0 + excess * mel_sens)

    # 軟水放大苦味感知（preprocessing，取代舊的 soft_water_penalty 分數乘數）
    gh_soft_factor = max(1.0 - water_gh / constants.LOW_GH_THRESHOLD, 0.0)
    if gh_soft_factor > 0:
        for k in ("CA", "CGA", "MEL"):
            actual_perceived[k] *= (1.0 + gh_soft_factor * constants.SOFT_WATER_BITTER_AMP)

    # ── 2. 理想苦味微調 ────────────────────────────────────────────────
    ideal_adj = dict(ideal_abs)
    for k in ("CA", "CGA", "MEL"):
        ideal_adj[k] = ideal_abs[k] * constants.IDEAL_BITTER_REDUCTION

    # ── 3. 化合物品質獎勵（log-ratio Gaussian，黃金交叉在 actual = ideal） ──
    # 每個化合物：接近理想 → 貢獻滿分；偏離依 sigma 衰減
    # 非對稱 sigma：苦超標嚴懲（sigma_hi 小）、甜/醇不足嚴懲（sigma_lo 小）
    compound_loss = 0.0
    for k in constants.KEYS:
        ref = max(ideal_adj[k], _CONC_FLOOR)
        log_dev = math.log(max(actual_perceived[k], _CONC_FLOOR) / ref)
        sigma = constants.COMPOUND_SIGMA_HI[k] if log_dev > 0 else constants.COMPOUND_SIGMA_LO[k]
        compound_loss += constants.WEIGHTS[k] * (log_dev / sigma) ** 2
    compound_reward = math.exp(-compound_loss / _WEIGHT_TOTAL)

    # ── 4. TDS 品質因子（非對稱 Gaussian） ────────────────────────────
    tds_prefer = constants.TDS_PREFER[roast_code]
    diff = tds - tds_prefer
    sigma_tds = constants.TDS_GAUSS_SIGMA_LOW if diff < 0 else constants.TDS_GAUSS_SIGMA_HIGH
    tds_gauss = math.exp(-0.5 * (diff / sigma_tds) ** 2)
    w3 = constants.TDS_W3_LOW if diff < 0 else constants.TDS_W3_HIGH
    tds_factor = 1 - w3 + w3 * tds_gauss

    # ── 5. EY 底線（過程變數，極低權重） ─────────────────────────────
    ey_prefer = constants.EY_PREFER[roast_code]
    ey_diff = ey - ey_prefer
    ey_sigma = constants.EY_SIGMA_HI[roast_code] if ey_diff > 0 else constants.EY_SIGMA_LO[roast_code]
    ey_gauss = math.exp(-0.5 * (ey_diff / ey_sigma) ** 2)
    ey_factor = 1.0 - constants.EY_GAUSS_WEIGHT + constants.EY_GAUSS_WEIGHT * ey_gauss

    # ── 6. TDS 硬底線（連續，太淡無口感） ────────────────────────────
    tds_floor_factor = min(tds / constants.TDS_BROWN_WATER_FLOOR, 1.0) ** 2

    return compound_reward * tds_factor * ey_factor * tds_floor_factor


def score_to_display(raw: float, roast_code: str) -> float:
    """raw (0–1) → 顯示用分數 (0–100)。直接線性映射。"""
    return round(raw * 100, 1)
