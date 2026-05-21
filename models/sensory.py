"""Phase 10 Layer 2 — sensory model.

`f(TDS, EY, roast, temp, dial) -> 6 sensory axis intensities`.

The model maps the system's pivot variables (TDS / EY) plus secondary inputs
to the 6 locked sensory axes (see docs/PHASE10_STEP1_SENSORY_AXES.md):

    acidity · sweetness · body · bitterness · astringency · roast

--- where the numbers come from ---

The (TDS, EY, temp) response is REGRESSED from data: the UC Davis Cotter /
Ristenpart / Guinard consumer dataset (`data/phase10_training/cotter_dataset.csv`,
Dryad 10.25338/B8993H, CC0) — a 3x3x3 TDS x EY x temp factorial, 27 brew cells
x ~118 consumers. Each axis intensity = mean CATA detection frequency of its
constituent attributes across the cell; per-axis coefficients fitted by OLS on
standardized predictors. Derivation + 27-cell table: docs/PHASE10_STEP2_LAYER2.md.

`roast` and `dial` (grind) are NOT independent factors in the cotter design
(single roast; grind was adjusted to hit each TDS/EY target). They enter as
literature-direction PRIOR offsets — cotter's roast is the `medium` reference
(offset 0) — to be refined by user feedback, not trusted as fitted values.

`temp` IS in the cotter design but its fitted coefficient is noise-level (~0)
across every axis — Batali 2020's headline is that brew temperature has no
sensory effect at fixed TDS/EY — so `b_temp` is set to exactly 0. `temp` stays
in the signature for completeness; it currently moves nothing.

--- units ---

Axis intensities are CATA detection frequencies, nominally in [0, 1]. label
IDEALs (Step 3) and scoring (Step 5) use this same scale. Outputs are a plain
polynomial + offsets — not clamped — so far-extrapolation beyond the cotter
grid (TDS 0.95-1.63, EY 16-26%) may fall slightly outside [0, 1]; that is the
model honestly signalling low confidence, and Step 5 scoring absorbs it.
"""

# Canonical axis order. Everything downstream (labels.json, scoring) follows it.
SENSORY_AXES = ("acidity", "sweetness", "body", "bitterness", "astringency", "roast")

# Which cotter CATA columns feed each axis (mean of these = the axis intensity).
# Kept for documentation / reproducibility of the fit.
AXIS_ATTRIBUTES = {
    "acidity":     ("Sour", "Citrus"),
    "sweetness":   ("Sweet", "Caramel"),
    "body":        ("Thick.viscous",),
    "bitterness":  ("Bitter",),
    "astringency": ("Astringent", "Paper.wood"),
    "roast":       ("Roasted", "Burnt"),
}

# Standardization constants — mean / sd of the predictors over the 27 cotter
# cells. Predictors are z-scored before entering the regression.
_STD = {
    "tds":  (1.2718, 0.2137),
    "ey":   (20.3631, 3.0248),
    "temp": (90.0, 2.4495),
}

# OLS coefficients fitted on the 27 cotter cells (standardized predictors):
#   intensity = base + b_tds*z + b_ey*z + b_tds2*z^2 + b_temp*z
# R^2: acidity .84  bitterness .83  sweetness .68  roast .67  body .56
#      astringency .03  (astringency is near-flat in the cotter range — its
#      real driver is grind / over-extraction outside this grid; treat the
#      astringency fit as a weak prior, lean on feedback).
#
# b_temp is set to EXACTLY 0 (not the fitted value): the raw fit gave
# |b_temp| <= 0.011 across all axes — noise around zero, consistent with
# Batali 2020's finding that brew temperature has no sensory effect at fixed
# TDS/EY. The cotter grid is 87-93C; anchors brew as low as 80C (Champion),
# so extrapolating a noise-level coefficient would amplify noise. The term is
# kept in the formula (uniform structure) but contributes nothing.
_COEF = {
    "acidity":     {"base": 0.25986, "b_tds":  0.06130, "b_ey": -0.04073, "b_tds2":  0.00019, "b_temp": 0.0},
    "sweetness":   {"base": 0.14200, "b_tds": -0.01974, "b_ey": -0.00270, "b_tds2":  0.01839, "b_temp": 0.0},
    "body":        {"base": 0.07228, "b_tds":  0.02692, "b_ey":  0.00538, "b_tds2":  0.00431, "b_temp": 0.0},
    "bitterness":  {"base": 0.33662, "b_tds":  0.08119, "b_ey":  0.00745, "b_tds2": -0.02181, "b_temp": 0.0},
    "astringency": {"base": 0.17487, "b_tds":  0.00348, "b_ey": -0.00164, "b_tds2": -0.00224, "b_temp": 0.0},
    "roast":       {"base": 0.33684, "b_tds":  0.03545, "b_ey":  0.01529, "b_tds2": -0.02171, "b_temp": 0.0},
}

# Per-roast additive offsets — LITERATURE-DIRECTION PRIORS, not fitted.
# cotter's coffee = the `medium` reference (offset 0). Guinard 2023 BCC found
# roast level is the single largest sensory effect: lighter -> brighter
# (more acidity / sweetness), less bitter / roasty. Magnitudes are seeded
# comparable to the (TDS,EY) span (~+-0.1) and are the first thing user
# feedback should refine.
_ROAST_OFFSET = {
    "light":           {"acidity":  0.070, "sweetness":  0.040, "body": -0.020, "bitterness": -0.070, "astringency": -0.020, "roast": -0.120},
    "medium_light":    {"acidity":  0.035, "sweetness":  0.020, "body": -0.010, "bitterness": -0.035, "astringency": -0.010, "roast": -0.060},
    "medium":          {"acidity":  0.000, "sweetness":  0.000, "body":  0.000, "bitterness":  0.000, "astringency":  0.000, "roast":  0.000},
    "moderately_dark": {"acidity": -0.050, "sweetness": -0.030, "body":  0.020, "bitterness":  0.050, "astringency":  0.015, "roast":  0.080},
}

# Grind (dial) — weakest term, prior only. cotter cannot train it (grind was
# the adjusted-to-target variable). Reference dial = 4.3 (medium_light anchor
# grind). Finer than ref (lower dial -> positive delta) nudges body and
# astringency up slightly; everything else 0. Skipped entirely when dial=None.
_DIAL_REF = 4.3
_GRIND_SLOPE = {
    "acidity": 0.0, "sweetness": 0.0, "body": 0.010,
    "bitterness": 0.0, "astringency": 0.008, "roast": 0.0,
}


def _z(value, key):
    """Standardize a predictor against the cotter mean/sd."""
    mu, sd = _STD[key]
    return (value - mu) / sd


def predict_axes(tds, ey, roast="medium_light", temp=90.0, dial=None):
    """Predict the 6 sensory axis intensities for a brew.

    Args:
        tds:   total dissolved solids, percent (e.g. 1.40).
        ey:    extraction yield / percent extraction (e.g. 20.5).
        roast: roast key — light / medium_light / medium / moderately_dark.
        temp:  brew temperature, degrees C. Defaults to the cotter mean (90);
               its effect is ~0 either way.
        dial:  grinder dial (lower = finer). None -> grind term skipped.

    Returns:
        dict {axis: intensity} in SENSORY_AXES order. Intensities are CATA
        detection frequencies, nominally [0, 1] (not clamped — see module doc).
    """
    z_tds = _z(tds, "tds")
    z_ey = _z(ey, "ey")
    z_temp = _z(temp, "temp")
    roast_off = _ROAST_OFFSET.get(roast, _ROAST_OFFSET["medium"])
    grind_delta = 0.0 if dial is None else (_DIAL_REF - dial)

    axes = {}
    for axis in SENSORY_AXES:
        c = _COEF[axis]
        axes[axis] = (
            c["base"]
            + c["b_tds"] * z_tds
            + c["b_ey"] * z_ey
            + c["b_tds2"] * z_tds * z_tds
            + c["b_temp"] * z_temp
            + roast_off[axis]
            + _GRIND_SLOPE[axis] * grind_delta
        )
    return axes
