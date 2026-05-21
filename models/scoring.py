from __future__ import annotations

import math

import constants
from models.labels import get_label, ideal_abs as label_ideal_abs

_CONC_FLOOR = 1e-8
_WEIGHT_TOTAL = sum(constants.WEIGHTS.values())


def _sigmoid(x: float) -> float:
    """Logistic sigmoid via tanh identity — numerically stable for all x."""
    return 0.5 + 0.5 * math.tanh(0.5 * x)


def _softplus(x: float, k: float = 1.0) -> float:
    """Smooth ReLU: ln(1 + exp(k·x)) / k.  Stable for all inputs."""
    kx = k * x
    abs_kx = math.fabs(kx)
    return (math.log1p(math.exp(-abs_kx)) + (kx + abs_kx) * 0.5) / k


def compute_actual_abs(actual_raw: dict, tds: float) -> dict:
    """Normalize raw compound predictions into TDS-weighted absolute amounts."""
    total_raw = sum(actual_raw[k] for k in constants.KEYS)
    if total_raw > 0:
        fraction = {k: actual_raw[k] / total_raw for k in constants.KEYS}
    else:
        fraction = {k: 0.0 for k in constants.KEYS}
    return {k: fraction[k] * tds for k in constants.KEYS}


def flavor_score(
    actual_raw: dict,
    tds: float,
    roast_code: str,
    label: str,
    water_kh: float = 30,
    water_gh: float = 50,
    t_slurry: float = 90,
    temp_initial: float = 90,
    ey: float = 0.0,
    steep_sec: float = 0.0,
    dial: float = 4.5,
) -> float:
    """Phase 8 — label-parameterized flavor score.

    Scoring structure (log-ratio Gaussian × TDS Super-Gaussian × perceptual gates)
    is identical for every label per principle #2; only `IDEAL` and `TDS_PREFER`
    differ by label (loaded from data/labels.json). Labels are zero-coupled —
    editing one label cannot move another label's scores.
    """
    label_spec = get_label(label)
    ideal_abs = label_ideal_abs(label, tds, roast_code)
    tds_prefer = label_spec["tds_prefer"]

    # ── 1. perception preprocessing (physical, not scoring) ─────────────
    actual_abs = compute_actual_abs(actual_raw, tds)
    actual_perceived = dict(actual_abs)

    kh_factor = constants.KH_FLOOR + (1.0 - constants.KH_FLOOR) * math.exp(
        -water_kh / constants.KH_PERCEPT_DECAY_SMOOTH
    )
    actual_perceived["AC"] = actual_abs["AC"] * kh_factor

    sw_raw = constants.SW_AROMA_SLOPE * _softplus(
        temp_initial - constants.SW_AROMA_THRESH, k=constants.SW_AROMA_SIGMOID_K
    )
    sw_loss = constants.SW_AROMA_CAP * math.tanh(sw_raw / constants.SW_AROMA_CAP)
    actual_perceived["SW"] = actual_abs["SW"] * (1.0 - sw_loss)

    scorch_threshold, cga_sens, mel_sens = constants.SCORCH_PARAMS[roast_code]
    scorch_excess = _softplus(t_slurry - scorch_threshold, k=constants.SCORCH_SOFTPLUS_K)
    actual_perceived["CGA"] *= 1.0 + scorch_excess * cga_sens
    actual_perceived["MEL"] *= 1.0 + scorch_excess * mel_sens

    gh_soft = _sigmoid(constants.GH_SOFT_SIGMOID_K * (constants.LOW_GH_THRESHOLD - water_gh))
    for k in ("CA", "CGA", "MEL"):
        actual_perceived[k] *= 1.0 + gh_soft * constants.SOFT_WATER_BITTER_AMP

    # ── 2. ideal bitterness micro-adjust ───────────────────────────────
    ideal_adj = dict(ideal_abs)
    for k in ("CA", "CGA", "MEL"):
        ideal_adj[k] = ideal_abs[k] * constants.IDEAL_BITTER_REDUCTION

    # ── 3. compound quality (log-ratio Gaussian, smooth asymmetric σ) ──
    compound_loss = 0.0
    for k in constants.KEYS:
        ref = ideal_adj[k] + _CONC_FLOOR
        act = actual_perceived[k] + _CONC_FLOOR
        log_dev = math.log(act / ref)
        s_lo = constants.COMPOUND_SIGMA_LO[k]
        s_hi = constants.COMPOUND_SIGMA_HI[k]
        blend = _sigmoid(constants.SIGMA_BLEND_K * log_dev)
        sigma = s_lo + (s_hi - s_lo) * blend
        r_sq = (log_dev / sigma) ** 2
        excess = _sigmoid(constants.ACCEL_ONSET_K * log_dev)
        accel = excess * _softplus(r_sq - constants.PENALTY_ACCEL_THRESHOLD,
                                   k=constants.PENALTY_ACCEL_K)
        r_sq = r_sq + constants.ACCEL_W_PER_COMPOUND[k] * accel
        compound_loss += constants.WEIGHTS[k] * r_sq

    compound_reward = math.exp(-compound_loss / _WEIGHT_TOTAL)

    # ── 4. TDS quality factor (label-specific Super-Gaussian) ─────────
    delta = tds - tds_prefer
    blend_tds = _sigmoid(constants.TDS_SIGMA_BLEND_K * delta)
    sigma_tds = (
        constants.TDS_GAUSS_SIGMA_LOW
        + (constants.TDS_GAUSS_SIGMA_HIGH - constants.TDS_GAUSS_SIGMA_LOW) * blend_tds
    )
    tds_factor = math.exp(-0.5 * (delta / sigma_tds) ** constants.TDS_SUPER_GAUSS_EXP)

    # ── 5. EY contribution (off by default; perceptual EY guards below) ─
    ey_prefer = constants.EY_PREFER[roast_code]
    ey_diff = ey - ey_prefer
    blend_ey = _sigmoid(constants.EY_BLEND_K * ey_diff)
    ey_s_lo = constants.EY_SIGMA_LO[roast_code]
    ey_s_hi = constants.EY_SIGMA_HI[roast_code]
    ey_sigma = ey_s_lo + (ey_s_hi - ey_s_lo) * blend_ey
    ey_gauss = math.exp(-0.5 * (ey_diff / ey_sigma) ** 2)
    ey_factor = 1.0 - constants.EY_GAUSS_WEIGHT + constants.EY_GAUSS_WEIGHT * ey_gauss

    # ── 6. TDS floor (太淡無口感) ─────────────────────────────────────
    tds_floor_factor = _sigmoid(constants.TDS_FLOOR_K * (tds - constants.TDS_FLOOR_MID))

    # ── 7. TDS-EY mismatch (低 TDS + 高 EY 過萃補濃) ──────────────────
    ey_surplus = _softplus(ey - ey_prefer, k=constants.TDS_EY_MISMATCH_K)
    tds_deficit = _softplus(tds_prefer - tds, k=constants.TDS_EY_MISMATCH_K)
    mismatch = ey_surplus * tds_deficit
    mismatch_factor = math.exp(-constants.TDS_EY_MISMATCH_WEIGHT * mismatch)

    return (
        compound_reward
        * tds_factor
        * ey_factor
        * tds_floor_factor
        * mismatch_factor
    )


def score_to_display(raw: float, roast_code: str = None) -> float:
    """raw (0–1) → 顯示用分數 (0–100)，線性映射。"""
    return round(raw * 100, 1)
