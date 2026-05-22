"""Phase 10 Step 5.5 — Layer 2 sensory model (all-attribute re-fit).

`predict_attributes(tds, ey, roast, temp, dial) -> {attribute: intensity}`.

Supersedes the Step 2 six-axis model. Step 2 grouped 10 cotter CATA columns
into 6 averaged axes; Step 5.5 drops the averaging and predicts each cotter
attribute on its own. Why: cotter's attribute values are already
consumer-perceived (any cross-attribute masking — e.g. thick body damping
floral — is baked into the data), so regressing every attribute directly on the
brew coordinates captures those interactions for free, with no hand-built
interaction model. Averaging into axes actively destroyed signal — the Step 2
`astringency` axis (R² 0.03) looked untrainable only because Astringent
(b_tds +0.019) and Paper.wood (b_tds -0.012) have OPPOSITE TDS responses that
cancelled in the mean; Astringent on its own fits at R² 0.44. Full rationale:
docs/PHASE10_STEP5_5_ALL_ATTRIBUTES.md.

--- which attributes ---

All 17 cotter CATA attributes were fitted; the 10 here are the ones with a real
linear relationship to (TDS, EY) — R² >= 0.44. The other 7 (R² <= 0.32) were
dropped: each is either a weak twin of a kept attribute (Roasted~Burnt,
Caramel~Sweet, Paper.wood~Astringent, Fruit~Tea.floral, Nutty~Dark.chocolate)
or near-zero-signal noise (Rubber, Green.veg) — so no flavor family is lost.

--- the fit ---

Each attribute's intensity = mean CATA detection frequency across a cotter cell
(27 cells x 118 consumers). OLS on standardized predictors:

    intensity = base + b_tds·z(TDS) + b_ey·z(EY) + b_tds2·z(TDS)²

`b_temp` is held at 0 (Step 2 / Batali 2020: temperature has no sensory effect
at fixed TDS/EY). `roast` and `dial` enter as literature-direction priors, not
fitted — cotter is single-roast and grind was its adjusted-to-target variable.
Coefficients fitted 2026-05-22; derivation in docs/PHASE10_STEP5_5_ALL_ATTRIBUTES.md.

--- units ---

Intensities are CATA detection frequencies, nominally [0, 1] — not clamped, so
far-extrapolation beyond the cotter grid (TDS 0.95-1.63, EY 16-26%) may fall
slightly outside [0, 1]; that is the model honestly signalling low confidence.
"""

# Canonical attribute order — the model's representation. Everything downstream
# (ideal.json, distance.py) follows it. Ordered by flavor family for readable
# output: bright · sweet/grain · body · bitter/astringent · roast.
ATTRIBUTES = (
    "Sour",
    "Citrus",
    "Tea.floral",
    "Sweet",
    "Cereal",
    "Thick.viscous",
    "Bitter",
    "Astringent",
    "Burnt",
    "Dark.chocolate",
)

# R² of each attribute's (TDS,EY) fit over the 27 cotter cells. All >= 0.44 —
# the gate that selected this set. Kept for documentation / Step 7 reference.
ATTR_R2 = {
    "Sour": 0.88, "Citrus": 0.62, "Tea.floral": 0.67, "Sweet": 0.69,
    "Cereal": 0.61, "Thick.viscous": 0.55, "Bitter": 0.82, "Astringent": 0.44,
    "Burnt": 0.80, "Dark.chocolate": 0.82,
}

# 6-axis grouping — a DISPLAY / questionnaire view (Step 6), NOT the model's
# representation. The model predicts the 10 attributes; these groups just
# summarize them for a human. `character` holds aroma notes that are not an
# intensity axis. (Caramel/Paper.wood/Roasted were dropped — their families are
# still covered by Sweet/Astringent/Burnt.)
AXIS_VIEW = {
    "acidity":     ("Sour", "Citrus"),
    "sweetness":   ("Sweet",),
    "body":        ("Thick.viscous",),
    "bitterness":  ("Bitter",),
    "astringency": ("Astringent",),
    "roast":       ("Burnt",),
    "character":   ("Tea.floral", "Cereal", "Dark.chocolate"),
}

# Standardization constants — mean / sd of the predictors over the 27 cotter
# cells (recomputed 2026-05-22; identical to Step 2). Predictors are z-scored.
_STD = {
    "tds":  (1.2718, 0.2137),
    "ey":   (20.3631, 3.0248),
    "temp": (90.0, 2.4495),
}

# OLS coefficients, fitted per attribute on the 27 cotter cells (standardized
# predictors). b_temp held at exactly 0 — see module doc.
_COEF = {
    "Sour":           {"base": 0.34244, "b_tds":  0.09407, "b_ey": -0.04745, "b_tds2": -0.00345, "b_temp": 0.0},
    "Citrus":         {"base": 0.17550, "b_tds":  0.02920, "b_ey": -0.03375, "b_tds2":  0.00561, "b_temp": 0.0},
    "Tea.floral":     {"base": 0.19194, "b_tds": -0.04357, "b_ey":  0.00080, "b_tds2":  0.00423, "b_temp": 0.0},
    "Sweet":          {"base": 0.17136, "b_tds": -0.04030, "b_ey": -0.00107, "b_tds2":  0.01979, "b_temp": 0.0},
    "Cereal":         {"base": 0.11260, "b_tds": -0.02941, "b_ey":  0.00897, "b_tds2": -0.00306, "b_temp": 0.0},
    "Thick.viscous":  {"base": 0.07132, "b_tds":  0.02727, "b_ey":  0.00552, "b_tds2":  0.00526, "b_temp": 0.0},
    "Bitter":         {"base": 0.33552, "b_tds":  0.08160, "b_ey":  0.00762, "b_tds2": -0.02070, "b_temp": 0.0},
    "Astringent":     {"base": 0.12133, "b_tds":  0.01875, "b_ey": -0.01047, "b_tds2": -0.00802, "b_temp": 0.0},
    "Burnt":          {"base": 0.19200, "b_tds":  0.05320, "b_ey":  0.01112, "b_tds2": -0.01184, "b_temp": 0.0},
    "Dark.chocolate": {"base": 0.23688, "b_tds":  0.03844, "b_ey":  0.01364, "b_tds2": -0.02376, "b_temp": 0.0},
}

# Per-roast additive offsets — LITERATURE-DIRECTION PRIORS, not fitted (cotter
# is single-roast). Keyed by flavor family; each attribute inherits its family's
# offset via _ATTR_FAMILY. cotter's roast = the `medium` reference (0); lighter
# roasts read brighter (acidity/character up) and less bitter/roasty.
# NOTE: within a single roast this offset is identical on the prediction and on
# the IDEAL, so it CANCELS in the distance — it never moves a within-roast
# recommendation. It only sets the absolute IDEAL numbers and the medium /
# moderately_dark placeholders. Unvalidated; first thing user feedback refines.
_ROAST_OFFSET = {
    "light":           {"acidity":  0.070, "sweetness":  0.040, "body": -0.020, "bitterness": -0.070, "astringency": -0.020, "roast": -0.120, "character":  0.030},
    "medium_light":    {"acidity":  0.035, "sweetness":  0.020, "body": -0.010, "bitterness": -0.035, "astringency": -0.010, "roast": -0.060, "character":  0.015},
    "medium":          {"acidity":  0.000, "sweetness":  0.000, "body":  0.000, "bitterness":  0.000, "astringency":  0.000, "roast":  0.000, "character":  0.000},
    "moderately_dark": {"acidity": -0.050, "sweetness": -0.030, "body":  0.020, "bitterness":  0.050, "astringency":  0.015, "roast":  0.080, "character": -0.020},
}
_ATTR_FAMILY = {
    "Sour": "acidity", "Citrus": "acidity", "Tea.floral": "acidity",
    "Sweet": "sweetness", "Cereal": "character", "Thick.viscous": "body",
    "Bitter": "bitterness", "Astringent": "astringency",
    "Burnt": "roast", "Dark.chocolate": "roast",
}

# Grind (dial) — weakest term, prior only (cotter cannot train it). Reference
# dial 4.3; finer than ref (lower dial) nudges body / astringency up slightly.
_DIAL_REF = 4.3
_GRIND_SLOPE = {a: 0.0 for a in ATTRIBUTES}
_GRIND_SLOPE["Thick.viscous"] = 0.010
_GRIND_SLOPE["Astringent"] = 0.008


def _z(value, key):
    """Standardize a predictor against the cotter mean/sd."""
    mu, sd = _STD[key]
    return (value - mu) / sd


def predict_attributes(tds, ey, roast="medium_light", temp=90.0, dial=None):
    """Predict the 10 sensory attribute intensities for a brew.

    Args:
        tds:   total dissolved solids, percent (e.g. 1.35).
        ey:    extraction yield / percent extraction (e.g. 20.0).
        roast: roast key — light / medium_light / medium / moderately_dark.
        temp:  brew temperature, degrees C. Effect is 0 (b_temp held at 0).
        dial:  grinder dial (lower = finer). None -> grind term skipped.

    Returns:
        dict {attribute: intensity} in ATTRIBUTES order. Intensities are CATA
        detection frequencies, nominally [0, 1] (not clamped — see module doc).
    """
    z_tds = _z(tds, "tds")
    z_ey = _z(ey, "ey")
    z_temp = _z(temp, "temp")
    roast_off = _ROAST_OFFSET.get(roast, _ROAST_OFFSET["medium"])
    grind_delta = 0.0 if dial is None else (_DIAL_REF - dial)

    out = {}
    for attr in ATTRIBUTES:
        c = _COEF[attr]
        out[attr] = (
            c["base"]
            + c["b_tds"] * z_tds
            + c["b_ey"] * z_ey
            + c["b_tds2"] * z_tds * z_tds
            + c["b_temp"] * z_temp
            + roast_off[_ATTR_FAMILY[attr]]
            + _GRIND_SLOPE[attr] * grind_delta
        )
    return out
