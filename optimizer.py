"""Phase 10 Step 5 — optimizer over the sensory pipeline.

Pipeline (blueprint §3):

    knobs → models.layer1.brew → {tds, ey}
          → models.sensory.predict_attributes → 10 sensory attributes
          → models.distance.attribute_distance vs the roast's IDEAL

Inputs the user fixes:  roast, brewer (→ water_ml), temperature.
Outputs the optimizer searches:  dose × dial × steep — the recipe whose 10
sensory attributes land closest to the roast's IDEAL (`data/ideal.json`).
Recipes are ranked by attribute distance (smaller = closer); there is no score.

Temperature is NOT searched. It acts on flavor only through Layer 1's EY/TDS
(Layer 2 has b_temp=0); for any (tds,ey,dial) target a different temperature is
absorbed by a different steep, so optimizing it yields only tie-break noise —
see docs/PHASE10_STEP4_LAYER1.md §8. The label / Channel-B machinery is gone
with the `label` concept (blueprint §0): a fixed roast has ONE sensory IDEAL.
Water chemistry is gone too — Phase 10's Layer 1/2 do not model it.
"""
from __future__ import annotations

import constants
from models.distance import attribute_distance
from models.ideal import recipe_id, roast_ideal
from models.layer1 import brew as layer1_brew
from models.sensory import predict_attributes


def evaluate_recipe(
    roast_code: str,
    brewer_size: str,
    temp: float,
    dial: float,
    steep_sec: int,
    dose: float,
    ideal: dict | None = None,
) -> dict:
    """Full Phase 10 pass for one recipe → candidate dict.

    Shared by the optimizer grid and out-of-grid evaluation (e.g. rescoring a
    logged feedback recipe with the current model) — one code path means a
    logged recipe re-evaluates identically to a fresh run. Pass `ideal` to reuse
    a cached roast IDEAL across a grid sweep; omitted → looked up per call.
    """
    brewer = constants.BREWER_PRESETS[brewer_size]
    water_ml = brewer["water_ml"]
    if ideal is None:
        ideal = roast_ideal(roast_code)

    l1 = layer1_brew(roast_code, temp, dial, steep_sec, dose, water_ml)
    attrs = predict_attributes(l1["tds"], l1["ey"], roast=roast_code, temp=temp, dial=dial)
    dist = attribute_distance(attrs, ideal)

    rid = recipe_id(
        roast=roast_code, brewer=brewer_size, dial=dial,
        steep_sec=steep_sec, temp=temp, dose=dose,
    )
    return {
        "recipe_id": rid,
        "roast": roast_code,
        "brewer": brewer["name"],
        "brewer_size": brewer_size,
        "water_ml": water_ml,
        "temp": temp,
        "dial": dial,
        "steep_sec": steep_sec,
        "dose": dose,
        "ey": l1["ey"],
        "tds": l1["tds"],
        "attributes": attrs,
        "ideal": ideal,
        "distance": dist,
    }


def _dose_values(
    roast_code: str,
    brewer_size: str,
    water_ml: float,
    fixed_dose: float | None,
    dose_min_override: float | None,
    dose_max_override: float | None,
) -> list[float]:
    """Doses (g) to sweep — roast `dose_per_100ml` ∩ brewer dose range.

    Resolution: 1.0 g on the XL (deep bed), 0.5 g on the standard brewer.
    """
    if fixed_dose is not None:
        return [round(fixed_dose, 1)]

    brewer = constants.BREWER_PRESETS[brewer_size]
    cfg = constants.ROAST_TABLE[roast_code]
    step_x2 = 2 if brewer_size == "xl" else 1
    lo_x2 = int(brewer["dose_min"] * 2)
    hi_x2 = int(brewer["dose_max"] * 2)

    dose_range = cfg.get("dose_per_100ml")
    if dose_range:
        lo_x2 = max(lo_x2, int(dose_range[0] * water_ml / 100 * 2))
        hi_x2 = min(hi_x2, int(dose_range[1] * water_ml / 100 * 2))
    if dose_min_override is not None:
        lo_x2 = max(lo_x2, int(dose_min_override * 2))
    if dose_max_override is not None:
        hi_x2 = min(hi_x2, int(dose_max_override * 2))

    remainder = lo_x2 % step_x2
    if remainder:
        lo_x2 += step_x2 - remainder
    return [x2 / 2 for x2 in range(lo_x2, hi_x2 + 1, step_x2)]


def optimize(
    roast_code: str,
    brewer_size: str = "xl",
    temp: float | None = None,
    top_n: int = 3,
    fixed_dose: float | None = None,
    fixed_steep: int | None = None,
    dose_min_override: float | None = None,
    dose_max_override: float | None = None,
) -> list[dict]:
    """Search dose × dial × steep at a fixed temperature.

    Returns the Top-N recipes closest to the roast's 10-attribute sensory IDEAL,
    nearest first (ascending `distance`). `temp` omitted → the roast's
    convention default (constants.DEFAULT_TEMP).
    """
    if temp is None:
        temp = constants.DEFAULT_TEMP[roast_code]
    ideal = roast_ideal(roast_code)
    water_ml = constants.BREWER_PRESETS[brewer_size]["water_ml"]

    doses = _dose_values(
        roast_code, brewer_size, water_ml, fixed_dose,
        dose_min_override, dose_max_override,
    )
    steeps = (
        [fixed_steep] if fixed_steep is not None
        else list(range(30, 421, constants.STEEP_STEP))
    )

    candidates: list[dict] = []
    for dial_x10 in range(30, 76):
        dial = dial_x10 / 10
        for steep in steeps:
            for dose in doses:
                candidates.append(evaluate_recipe(
                    roast_code, brewer_size, temp, dial, steep, dose, ideal=ideal,
                ))
    candidates.sort(key=lambda c: c["distance"])
    return candidates[:top_n]


def score_logged_recipe(
    roast_code: str,
    brewer_size: str,
    temp: float,
    dial: float,
    steep_sec: int,
    dose: float,
) -> dict:
    """Re-evaluate one known recipe with the current model.

    The feedback recompute path (models/feedback.py): a logged recipe's inputs
    are durable, its derived ey/tds/attributes/distance are a projection that must
    track model recalibration. Same code path as the optimizer grid.
    """
    return evaluate_recipe(roast_code, brewer_size, temp, dial, steep_sec, dose)
