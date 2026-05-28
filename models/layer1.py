"""Phase 10 Layer 1 — thin knob -> TDS / EY converter.

`brew(roast, temp, dial, steep_sec, dose, water_ml) -> {ey, tds}`.

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
              with hotter water, finer grind.
      f_ratio brew-ratio capacity: a higher coffee:water ratio saturates the
              slurry sooner -> slightly lower EY. Gentle (kinetic-regime dose term).

    tau   = TAU_REF · exp(-ALPHA·(temp-T_REF)) · exp(-GAMMA·(DIAL_REF-dial))
    f_ratio = water / (water + K_RATIO · dose)
    t_eff = steep_sec + T_PRESS_OFFSET   (small swirl + press-contact offset)

    TDS%  = extracted_solids / cup_mass · 100,  extracted = dose·EY/100,
            cup_mass = (water - dose·retention) + extracted.

Every term is exp()-structured: globally monotone, saturating, no thresholds —
EY rises smoothly with temp / fineness / time and falls smoothly with brew ratio,
exactly the "monotone + saturating" black box the blueprint §6 asks for.

--- no brewer term ---

There is no XL-vs-standard extraction term (Phase 10 Step 5). "Brewer" differs
only in water volume — passed in as `water_ml` — and dose capacity. The old
`BREWER_TAU_MULT` ("XL's deeper bed extracts slower") was an uncalibrated prior
and, more to the point, a percolation intuition: bed depth drives flow-path
extraction, but this model is plain IMMERSION, where extraction is diffusion-
limited per particle and ~independent of bed geometry. At the same brew ratio,
XL and standard now produce identical TDS/EY by construction.

--- where the numbers come from ---

This thin Layer 1 models PLAIN IMMERSION — its only knobs are temp / grind /
dose / water / time. It has no technique knobs.

It is calibrated to exactly ONE anchor: Hoffmann's "balanced" recipe
(98C / dial 4.3 / 120s / 11g / 200ml -> measured TDS 1.23, El Tambo washed) —
the one plain-immersion brew among the literature anchors. `E_MAX` is solved so
the model reproduces that TDS exactly; it is the single fitted number.

The other published-TDS anchors, April (1.17) and Champion (1.56), are
deliberately NOT used. April is a partial-seal + two-stage pour; Champion is
inverted + agitated — technique brews, a different process than this
technique-blind model. (Rationale in docs/PHASE10_STEP4_LAYER1.md.)

The remaining parameters started as PHYSICAL PRIORS; GAMMA has since been
re-grounded by user cup feedback (the relative response is exactly what the
NOTE below says feedback should fix):

  TAU_REF  AeroPress immersion reaches ~93% of equilibrium by 120s. (prior)
  ALPHA    temperature -> rate, an Arrhenius linearization of Ea~30 kJ/mol
           (diffusion-controlled extraction) around 98C -> 0.026/degC, Q10~1.3. (prior)
  GAMMA    grind -> rate (finer = faster). Feedback-calibrated 0.32->0.5 (2026-05-28).
  K_RATIO  brew-ratio capacity (a gentle dose term). (prior)

NOTE on calibration (2026-05-22): with one anchor, `E_MAX` and `tau` are not
separately identifiable — they trade off along a curve, any (E_MAX, tau) pair
on it reproduces Hoffman. `TAU_REF=50` is the asserted degree of freedom, not a
confidently-known physical constant. This barely matters: the system is
anchored end-to-end, so a uniform rescale of the EY/TDS *absolute* scale cancels
in every recommendation (Top-1 exactly; the rest near-exactly). What is NOT
free — and what governs off-anchor behavior — is the *relative* response
(ALPHA / GAMMA / K_RATIO, and tau's time shape); those are the genuine priors,
to be grounded by user feedback, not by more calibration of this module.

Only `medium_light` is anchored. Per-roast `E_MAX` (via E_MAX_ROAST_FACTOR) and
`RETENTION` are literature-direction priors — darker roasts are more soluble
(higher ceiling) and hold more water.

--- units ---

EY is percent extraction; TDS is percent. Outputs are coarse estimates by design
(blueprint §6: "only a coarse estimate is needed") and are NOT clamped.
"""
from __future__ import annotations

import math

# ── calibrated parameter (the single fitted number) ─────────────────────────
# E_MAX is solved so the model reproduces the one plain-immersion anchor with a
# published TDS — Hoffman (98C / 4.3 / 120s / 11g / 200ml -> measured TDS 1.23).
E_MAX_REF = 23.346     # %  — medium_light equilibrium ceiling

# ── prior parameters (fixed by physical reasoning, not fitted) ───────────────
TAU_REF = 50.0         # s  — rate constant at T_REF / DIAL_REF.
                       #      AeroPress immersion reaches ~93% of equilibrium by 120s.
ALPHA = 0.026          # /degC — temperature -> rate. Arrhenius linearization of
                       #      Ea~30 kJ/mol (diffusion-controlled extraction) at 98C.
GAMMA = 0.5            # /dial-unit — grind -> rate (finer = faster). Raised from
                       #      the 0.32 prior (2026-05-28) after user cup feedback:
                       #      the model under-rated grind, letting a long steep on a
                       #      coarse grind "catch up" to a fine one. Calibrated so the
                       #      body ordering of four logged light cups matches taste
                       #      (fine+short thickest, coarse+long thinnest). Anchor-safe:
                       #      DIAL_REF term is exp(0) so Hoffman TDS 1.23 is untouched.
K_RATIO = 1.5          # brew-ratio (dose) capacity coefficient — gentle dose term

# ── reference points / fixed offsets ────────────────────────────────────────
T_REF = 98.0           # degC  — Hoffman anchor temp; tau temperature term = 1 here
DIAL_REF = 4.3         # dial  — Hoffman anchor grind; tau grind term = 1 here
T_PRESS_OFFSET = 10.0  # s     — swirl + partial press-contact added to steep time

# ── per-roast priors (only medium_light is anchored) ─────────────────────────
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


def _tau(roast_temp: float, dial: float) -> float:
    """Rate constant tau (s) — the e-folding time of the approach to E_MAX.

    Smaller tau = faster extraction. Hotter water and finer grind both shrink it.
    Pure exp() structure: globally monotone, no thresholds.
    """
    return (
        TAU_REF
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
) -> float:
    """Predict extraction yield (percent) for a brew.

    Args:
        roast:     roast key (E_MAX_ROAST_FACTOR / RETENTION key).
        temp:      brew water temperature, degrees C.
        dial:      grinder dial — lower = finer.
        steep_sec: immersion time, seconds.
        dose:      coffee dose, grams.
        water_ml:  brew water, millilitres.

    Returns:
        EY as a percentage. A coarse estimate, not clamped (see module doc).
    """
    e_max = E_MAX_REF * E_MAX_ROAST_FACTOR.get(roast, 1.0)
    tau = _tau(temp, dial)
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
) -> dict:
    """Full thin Layer 1 pass: knobs -> {"ey", "tds"}.

    The single entry point for Phase 10's pipeline — its output feeds
    models.sensory.predict_attributes (Layer 2). EY and TDS are internal latent
    variables (the user has no refractometer); see blueprint §3.
    """
    ey = predict_ey(roast, temp, dial, steep_sec, dose, water_ml)
    tds = predict_tds(roast, dose, ey, water_ml)
    return {"ey": ey, "tds": tds}
