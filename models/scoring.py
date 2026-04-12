from __future__ import annotations

import math

import constants

_CONC_FLOOR = 1e-8
_WEIGHT_TOTAL = sum(constants.WEIGHTS.values())


# ── 平滑輔助函數 ──────────────────────────────────────────────────────────────

def _sigmoid(x: float) -> float:
    """Logistic sigmoid via tanh identity — numerically stable for all x."""
    return 0.5 + 0.5 * math.tanh(0.5 * x)


def _softplus(x: float, k: float = 1.0) -> float:
    """Smooth ReLU: ln(1 + exp(k·x)) / k.  Stable for all inputs."""
    kx = k * x
    abs_kx = math.fabs(kx)
    # identity: log(1+exp(t)) = max(t,0) + log(1+exp(-|t|))
    return (math.log1p(math.exp(-abs_kx)) + (kx + abs_kx) * 0.5) / k


# ── 公開 API ──────────────────────────────────────────────────────────────────

def compute_actual_abs(actual_raw: dict, tds: float) -> dict:
    total_raw = sum(actual_raw[k] for k in constants.KEYS)
    if total_raw > 0:                           # 退化輸入保護，非評分邏輯
        actual_fraction = {k: actual_raw[k] / total_raw for k in constants.KEYS}
    else:
        actual_fraction = {k: 0.0 for k in constants.KEYS}
    return {k: actual_fraction[k] * tds for k in constants.KEYS}


def build_ideal_abs(roast_code: str, tds: float) -> dict:
    """Gaussian basis interpolation — continuous, no clamp / if-else."""
    sigma = constants.IDEAL_INTERP_SIGMA
    brackets = [("low", 1.00), ("mid", 1.20), ("high", 1.40)]
    w = {b: math.exp(-0.5 * ((tds - c) / sigma) ** 2) for b, c in brackets}
    w_total = sum(w.values())
    prop = {
        k: sum(w[b] * constants.IDEAL_FLAVOR[(roast_code, b)][k] for b in w) / w_total
        for k in constants.KEYS
    }
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

    # KH 壓制酸質感知 — 漸近底線 KH_FLOOR，無 max
    kh_factor = constants.KH_FLOOR + (1.0 - constants.KH_FLOOR) * math.exp(
        -water_kh / constants.KH_PERCEPT_DECAY_SMOOTH
    )
    actual_perceived["AC"] = actual_abs["AC"] * kh_factor

    # 高溫 SW 香氣損失 — softplus onset + tanh saturation，無 max/min
    # softplus(x, k) ≈ max(0,x) smoothly; tanh(x/cap)*cap ≈ min(x, cap) smoothly
    sw_raw = constants.SW_AROMA_SLOPE * _softplus(
        temp_initial - constants.SW_AROMA_THRESH, k=constants.SW_AROMA_SIGMOID_K
    )
    sw_loss = constants.SW_AROMA_CAP * math.tanh(sw_raw / constants.SW_AROMA_CAP)
    actual_perceived["SW"] = actual_abs["SW"] * (1.0 - sw_loss)

    # 高溫焦苦放大 — softplus 平滑過渡，無 if
    scorch_threshold, cga_sens, mel_sens = constants.SCORCH_PARAMS[roast_code]
    scorch_excess = _softplus(t_slurry - scorch_threshold, k=constants.SCORCH_SOFTPLUS_K)
    actual_perceived["CGA"] *= 1.0 + scorch_excess * cga_sens
    actual_perceived["MEL"] *= 1.0 + scorch_excess * mel_sens

    # 軟水放大苦味感知 — sigmoid 平滑過渡，無 max/if
    gh_soft = _sigmoid(constants.GH_SOFT_SIGMOID_K * (constants.LOW_GH_THRESHOLD - water_gh))
    for k in ("CA", "CGA", "MEL"):
        actual_perceived[k] *= 1.0 + gh_soft * constants.SOFT_WATER_BITTER_AMP

    # ── 2. 理想苦味微調 ────────────────────────────────────────────────
    ideal_adj = dict(ideal_abs)
    for k in ("CA", "CGA", "MEL"):
        ideal_adj[k] = ideal_abs[k] * constants.IDEAL_BITTER_REDUCTION

    # ── 3. 化合物品質（log-ratio Gaussian + 平滑不對稱 sigma） ──────────
    compound_loss = 0.0
    for k in constants.KEYS:
        ref = ideal_adj[k] + _CONC_FLOOR       # 防除零
        act = actual_perceived[k] + _CONC_FLOOR
        log_dev = math.log(act / ref)
        # 平滑不對稱 sigma：sigmoid blend（取代 if-else）
        s_lo = constants.COMPOUND_SIGMA_LO[k]
        s_hi = constants.COMPOUND_SIGMA_HI[k]
        blend = _sigmoid(constants.SIGMA_BLEND_K * log_dev)
        sigma = s_lo + (s_hi - s_lo) * blend
        r_sq = (log_dev / sigma) ** 2
        # 壞處邊際遞增：超標加速懲罰（sigmoid 方向門控 + softplus 強度閾值，全程平滑）
        # excess ≈ 0 當 log_dev < 0（不足），≈ 1 當 log_dev > 0（超標）
        excess = _sigmoid(constants.ACCEL_ONSET_K * log_dev)
        accel = excess * _softplus(r_sq - constants.PENALTY_ACCEL_THRESHOLD,
                                   k=constants.PENALTY_ACCEL_K)
        r_sq = r_sq + constants.ACCEL_W_PER_COMPOUND[k] * accel
        compound_loss += constants.WEIGHTS[k] * r_sq

    # ── 3b. 化合物比值獎勵（降低 compound_loss，保持 reward ∈ [0,1]） ──
    ac_p  = actual_perceived["AC"]  + _CONC_FLOOR
    sw_p  = actual_perceived["SW"]  + _CONC_FLOOR
    ps_p  = actual_perceived["PS"]  + _CONC_FLOOR
    ca_p  = actual_perceived["CA"]  + _CONC_FLOOR
    cga_p = actual_perceived["CGA"] + _CONC_FLOOR
    mel_p = actual_perceived["MEL"] + _CONC_FLOOR

    r_ac_cga    = ac_p / cga_p                 # 純淨酸質指標
    r_sw_bitter = sw_p / (mel_p + cga_p)       # 甜感 vs 苦澀指標
    r_ps_ca     = ps_p / ca_p                  # 醇厚乾淨度指標

    r1_score = _sigmoid(constants.RATIO_SIGMOID_K * (r_ac_cga    - constants.AC_CGA_RATIO_IDEAL))
    r2_score = _sigmoid(constants.RATIO_SIGMOID_K * (r_sw_bitter  - constants.SW_BITTER_RATIO_IDEAL))
    r3_score = _sigmoid(constants.RATIO_SIGMOID_K * (r_ps_ca      - constants.PS_CA_RATIO_IDEAL))

    ratio_bonus = (
        constants.RATIO_W_AC_CGA    * r1_score
        + constants.RATIO_W_SW_BITTER * r2_score
        + constants.RATIO_W_PS_CA     * r3_score
    ) / (constants.RATIO_W_AC_CGA + constants.RATIO_W_SW_BITTER + constants.RATIO_W_PS_CA)

    # ratio bonus 降低 compound_loss → compound_reward 保持 [0, 1]
    adjusted_loss = compound_loss * (1.0 - constants.RATIO_WEIGHT * ratio_bonus)
    compound_reward = math.exp(-adjusted_loss / _WEIGHT_TOTAL)

    # ── 4. TDS 品質因子（非對稱 Super-Gaussian，平滑 sigma） ────────────
    tds_prefer = constants.TDS_PREFER[roast_code]
    delta = tds - tds_prefer
    blend_tds = _sigmoid(constants.TDS_SIGMA_BLEND_K * delta)
    sigma_tds = (
        constants.TDS_GAUSS_SIGMA_LOW
        + (constants.TDS_GAUSS_SIGMA_HIGH - constants.TDS_GAUSS_SIGMA_LOW) * blend_tds
    )
    tds_factor = math.exp(-0.5 * (delta / sigma_tds) ** constants.TDS_SUPER_GAUSS_EXP)

    # ── 5. EY 底線（過程變數，極低權重，平滑 sigma） ─────────────────
    ey_prefer = constants.EY_PREFER[roast_code]
    ey_diff = ey - ey_prefer
    blend_ey = _sigmoid(constants.EY_BLEND_K * ey_diff)
    ey_s_lo = constants.EY_SIGMA_LO[roast_code]
    ey_s_hi = constants.EY_SIGMA_HI[roast_code]
    ey_sigma = ey_s_lo + (ey_s_hi - ey_s_lo) * blend_ey
    ey_gauss = math.exp(-0.5 * (ey_diff / ey_sigma) ** 2)
    ey_factor = 1.0 - constants.EY_GAUSS_WEIGHT + constants.EY_GAUSS_WEIGHT * ey_gauss

    # ── 6. TDS 底線 — sigmoid（太淡無口感） ────────────────────────────
    tds_floor_factor = _sigmoid(constants.TDS_FLOOR_K * (tds - constants.TDS_FLOOR_MID))

    return compound_reward * tds_factor * ey_factor * tds_floor_factor


def score_to_display(raw: float, roast_code: str) -> float:
    """raw (0–1) → 顯示用分數 (0–100)。直接線性映射。"""
    return round(raw * 100, 1)
