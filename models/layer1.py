"""Phase 10 Layer 1 — thin knob -> TDS / EY converter.

`brew(roast, temp, dial, steep_sec, dose, water_ml, brewer) -> {ey, tds}`.

This module replaces the entire pre-Phase-10 Layer 1 machinery — `ey_model.py`
(multi-phase cooling / fines Arrhenius EY model), `tds_model.py`, and the
`compounds.py` 6-compound kinetics. Those are retired; the legacy versions are
preserved on git branch `compound-model-legacy`.

--- the model ---

A single first-order approach to an equilibrium ceiling — the coarse shape an
equilibrium-desorption full-immersion model takes (Sci Rep 2021, PMC7994670):

    EY% = E_MAX · (1 - exp(-t_eff / tau)) · f_ratio

      E_MAX   equilibrium ceiling (the EY a brew tends to given infinite time,
              infinitely dilute) — per-roast.
      tau     rate constant: how fast the brew approaches E_MAX. Shrinks (faster)
              with hotter water, finer grind; grows with a deeper XL bed.
      f_ratio brew-ratio capacity: a higher coffee:water ratio saturates the
              slurry sooner -> slightly lower EY. Gentle (kinetic-regime dose term).

    tau   = TAU_REF · brewer · exp(-ALPHA·(temp-T_REF)) · exp(-GAMMA·(DIAL_REF-dial))
    f_ratio = water / (water + K_RATIO · dose)
    t_eff = steep_sec + T_PRESS_OFFSET   (small swirl + press-contact offset)

    TDS%  = extracted_solids / cup_mass · 100,  extracted = dose·EY/100,
            cup_mass = (water - dose·retention) + extracted.

Every term is exp()-structured: globally monotone, saturating, no thresholds —
EY rises smoothly with temp / fineness / time and falls smoothly with brew ratio,
exactly the "monotone + saturating" black box the blueprint §6 asks for.

--- where the numbers come from ---

5 free parameters, calibrated to the three medium_light Layer 1 anchors whose
TDS is published (Hoffmann "Brewing for Balance" article, El Tambo washed):

    Hoffman   98C / dial 4.3 / 120s / 11g / 200ml  -> measured TDS 1.23
    April     85C / dial 5.0 /  90s / 13g / 200ml  -> measured TDS 1.17
    Champion  80C / dial 5.0 / 100s / 17g / 200ml  -> measured TDS 1.56

K_RATIO and GAMMA are fixed by physical prior (a gentle brew-ratio effect, a
moderate grind effect); E_MAX, TAU_REF and ALPHA are then solved so the model
reproduces all three measured TDS exactly. The structure (monotone + saturating)
substitutes for the data the system cannot collect — the user has no
refractometer, so there are no (knob -> measured TDS) training pairs beyond the
literature anchors (blueprint §6). The fit is sanity-checked against Hedrick,
under- and over-extraction recipes; derivation detail: docs/PHASE10_STEP4_LAYER1.md.

ALPHA fits to ~0.019/degC — temperature is a gentle lever, not a strong one
(tau varies ~40% across 80-98C). This matches the blueprint §13 expectation that
the equilibrium-desorption literature finds temperature only weakly tied to
TDS/EY; the April/Champion EY deficit is mostly grind + brew-ratio + steep time,
not their low brew temperature.

Only `medium_light` is anchored. Per-roast `E_MAX` (via E_MAX_ROAST_FACTOR) and
`RETENTION` are literature-direction priors — darker roasts are more soluble
(higher ceiling) and hold more water — to be refined by user feedback. The XL
`brewer` term is likewise an uncalibrated prior (no XL extraction data).

--- units ---

EY is percent extraction; TDS is percent. Outputs are coarse estimates by design
(blueprint §6: "only a coarse estimate is needed") and are NOT clamped — far
out-of-grid knobs may produce values outside normal brewing ranges; that is the
model honestly extrapolating its monotone curve.
"""
from __future__ import annotations

import math

# ── calibrated parameters ───────────────────────────────────────────────────
# Solved so the model reproduces the 3 measured medium_light anchor TDS exactly
# (Hoffman/April/Champion); see module doc + docs/PHASE10_STEP4_LAYER1.md.
E_MAX_REF = 22.84      # %  — medium_light equilibrium ceiling
TAU_REF = 44.4         # s  — rate constant at T_REF / DIAL_REF / standard brewer
ALPHA = 0.0194         # /degC      — temperature -> rate (gentle; see doc)

# ── prior parameters (fixed by physical reasoning, not fitted) ───────────────
GAMMA = 0.32           # /dial-unit — grind -> rate (finer = faster)
K_RATIO = 1.5          # brew-ratio (dose) capacity coefficient — gentle dose term

# ── reference points / fixed offsets ────────────────────────────────────────
T_REF = 98.0           # degC  — Hoffman anchor temp; tau temperature term = 1 here
DIAL_REF = 4.3         # dial  — Hoffman anchor grind; tau grind term = 1 here
T_PRESS_OFFSET = 10.0  # s     — swirl + partial press-contact added to steep time

# ── per-roast / per-brewer priors (only medium_light is anchored) ────────────
# Equilibrium ceiling scales with roast: darker = more soluble cell structure =
# higher accessible EY. Literature-direction prior; medium_light = 1.00 anchored.
E_MAX_ROAST_FACTOR = {
    "very_light": 0.92, "light": 0.96, "medium_light": 1.00, "medium": 1.05,
    "moderately_dark": 1.09, "dark": 1.12, "very_dark": 1.14,
}

# Water held back by the spent puck, g per g grounds. Literature values; darker
# roasts are more porous and retain more. Used only for the TDS cup-mass term.
RETENTION = {
    "very_light": 1.95, "light": 2.05, "medium_light": 2.15, "medium": 2.25,
    "moderately_dark": 2.35, "dark": 2.45, "very_dark": 2.55,
}

# Brewer geometry -> tau. XL's deeper bed extracts marginally slower. Uncalibrated
# prior (no XL refractometer data); kept small per blueprint §6 ("a small offset").
BREWER_TAU_MULT = {"standard": 1.0, "xl": 1.05}


def _tau(roast_temp: float, dial: float, brewer: str) -> float:
    """Rate constant tau (s) — the e-folding time of the approach to E_MAX.

    Smaller tau = faster extraction. Hotter water and finer grind both shrink it;
    the deeper XL bed grows it slightly. Pure exp() structure: globally monotone,
    no thresholds.
    """
    return (
        TAU_REF
        * BREWER_TAU_MULT.get(brewer, 1.0)
        * math.exp(-ALPHA * (roast_temp - T_REF))
        * math.exp(-GAMMA * (DIAL_REF - dial))
    )


def predict_ey(
    roast: str,
    temp: float,
    dial: float,
    steep_sec: float,
    dose: float,
    water_ml: float,
    brewer: str = "standard",
) -> float:
    """Predict extraction yield (percent) for a brew.

    Args:
        roast:     roast key (E_MAX_ROAST_FACTOR / RETENTION key).
        temp:      brew water temperature, degrees C.
        dial:      grinder dial — lower = finer.
        steep_sec: immersion time, seconds.
        dose:      coffee dose, grams.
        water_ml:  brew water, millilitres.
        brewer:    "standard" or "xl" — selects the geometry tau prior.

    Returns:
        EY as a percentage. A coarse estimate, not clamped (see module doc).
    """
    e_max = E_MAX_REF * E_MAX_ROAST_FACTOR.get(roast, 1.0)
    tau = _tau(temp, dial, brewer)
    f_time = 1.0 - math.exp(-(steep_sec + T_PRESS_OFFSET) / tau)
    f_ratio = water_ml / (water_ml + K_RATIO * dose)
    return e_max * f_time * f_ratio


def predict_tds(roast: str, dose: float, ey: float, water_ml: float) -> float:
    """Predict total dissolved solids (percent) from EY, dose and water.

    TDS = extracted solids / cup mass. Cup mass = water minus what the spent
    puck retains, plus the extracted solids themselves.
    """
    retention = RETENTION.get(roast, 2.15)
    extracted_g = dose * ey / 100.0
    cup_mass_g = (water_ml - dose * retention) + extracted_g
    if cup_mass_g <= 0:
        return 0.0
    return extracted_g / cup_mass_g * 100.0


def brew(
    roast: str,
    temp: float,
    dial: float,
    steep_sec: float,
    dose: float,
    water_ml: float,
    brewer: str = "standard",
) -> dict:
    """Full thin Layer 1 pass: knobs -> {"ey", "tds"}.

    The single entry point for Phase 10's pipeline — its output feeds
    models.sensory.predict_axes (Layer 2). EY and TDS are internal latent
    variables (the user has no refractometer); see blueprint §3.
    """
    ey = predict_ey(roast, temp, dial, steep_sec, dose, water_ml, brewer)
    tds = predict_tds(roast, dose, ey, water_ml)
    return {"ey": ey, "tds": tds}
