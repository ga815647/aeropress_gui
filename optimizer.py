from __future__ import annotations

import math

import constants
from models.compounds import predict_compounds
from models.ey_model import calc_ey, calc_fines_ratio
from models.labels import label_names, recipe_id
from models.scoring import flavor_score, score_to_display
from models.tds_model import apply_channeling, calc_drip_volume, calc_press_time, calc_retention, calc_swirl_wait, calc_tds


def evaluate_recipe(
    roast_code: str,
    brewer_size: str,
    temp: float,
    dial: float,
    steep_sec: int,
    dose: float,
    water_gh: float = 50,
    water_kh: float = 30,
    water_mg_frac: float = 0.40,
    ey_floor: float | None = None,
) -> dict | None:
    """Full physics for one recipe -> candidate dict (ey / tds / compounds / ...).

    The per-recipe core shared by the optimizer grid (_grid_candidates) and any
    out-of-grid evaluation — e.g. recomputing a logged feedback recipe with the
    current model. One code path means a logged recipe re-scores identically to
    a fresh optimizer run; no parallel pipeline that can silently drift.

    `ey_floor`: optional perf fast-path for the grid — if the (pre-channeling) EY
    is below it, return None before the expensive predict_compounds. Physics is
    unaffected; the skipped candidate would have been discarded anyway. Leave it
    None (default) to always get a full evaluation (feedback recompute path).
    """
    brewer = constants.BREWER_PRESETS[brewer_size]
    water_ml = brewer["water_ml"]
    area_cm2 = brewer.get("area_cm2", constants.DRIP_AREA_REF_CM2)
    pour_offset = (water_ml / constants.POUR_RATE) / 2.0
    seal_delay = constants.SEAL_DELAY_DEFAULT
    drip_time = water_ml / constants.POUR_RATE + seal_delay

    press_sec = calc_press_time(dose, dial, steep_sec, brewer_size=brewer_size)
    if press_sec > constants.CHANNELING_PRESS_THRESHOLD:
        collapsed_press = (
            constants.CHANNELING_PRESS_THRESHOLD
            + (press_sec - constants.CHANNELING_PRESS_THRESHOLD)
            * constants.CHANNELING_COLLAPSE_RATIO
        )
        display_press_sec = int(collapsed_press)
    else:
        collapsed_press = press_sec
        display_press_sec = press_sec

    press_equiv = collapsed_press * constants.PRESS_EQUIV_FRACTION
    swirl_wait = calc_swirl_wait(brewer_size)
    ey = calc_ey(
        roast_code, temp, dial, steep_sec, dose, water_ml,
        water_gh=water_gh,
        press_equiv=press_equiv,
        pour_offset=pour_offset,
        seal_delay=seal_delay,
        swirl_wait_sec=swirl_wait,
        area_cm2=area_cm2,
    )
    if ey_floor is not None and ey < ey_floor:
        return None

    t_slurry_val = round(
        (water_ml * temp + dose * constants.COFFEE_SPECIFIC_HEAT_RATIO * constants.T_ENV)
        / (water_ml + dose * constants.COFFEE_SPECIFIC_HEAT_RATIO)
        - constants.BREWER_TEMP_DROP,
        1,
    )

    compounds_raw = predict_compounds(
        roast_code,
        t_slurry_val,
        dial,
        steep_sec,
        ey,
        water_gh,
        water_mg_frac,
        press_equiv=press_equiv,
        pour_offset=pour_offset,
        water_ml=water_ml,
        seal_delay=seal_delay,
        dose=dose,
        press_sec=press_sec,
        area_cm2=area_cm2,
    )
    ey, compounds = apply_channeling(ey, compounds_raw, press_sec)
    tds = calc_tds(roast_code, dose, ey, dial, water_ml)
    drip_volume = calc_drip_volume(water_ml, dial, drip_time, dose, area_cm2)

    rid = recipe_id(
        roast=roast_code,
        brewer=brewer_size,
        dial=dial,
        steep_sec=steep_sec,
        temp=temp,
        dose=dose,
        water_gh=water_gh,
        water_kh=water_kh,
        water_mg_frac=water_mg_frac,
    )

    return {
        "recipe_id": rid,
        "brewer": brewer["name"],
        "water_ml": water_ml,
        "temp": temp,
        "dial": dial,
        "steep_sec": steep_sec,
        "dose": dose,
        "swirl_sec": constants.SWIRL_TIME_SEC,
        "swirl_wait_sec": swirl_wait,
        "press_sec": display_press_sec,
        "press_sec_internal": press_sec,
        "seal_delay": seal_delay,
        "pre_seal_drip_sec": round(drip_time, 1),
        "pre_seal_drip_ml": drip_volume,
        "total_contact_sec": steep_sec + constants.SWIRL_TIME_SEC + swirl_wait + display_press_sec,
        "ey": ey,
        "tds": tds,
        "fines_ratio": calc_fines_ratio(dial),
        "t_slurry": t_slurry_val,
        "t_kinetic": round(
            max(0, steep_sec - pour_offset)
            + constants.SWIRL_TIME_SEC
            * (1.0 + constants.SWIRL_CONVECTION_BASE * (constants.SWIRL_DOSE_REF / dose))
            + swirl_wait * constants.SWIRL_WAIT_EXT_MULT
            + press_equiv,
            1,
        ),
        "retention": calc_retention(roast_code, dial),
        "compounds": compounds,
    }


def _grid_candidates(
    roast_code: str,
    brewer_size: str,
    water_gh: float,
    water_kh: float,
    water_mg_frac: float,
    fixed_dose: float | None,
    temp_range: tuple[int, int] | None,
    fixed_steep: int | None,
    dose_min_override: float | None,
    dose_max_override: float | None,
) -> list[dict]:
    """Single label-independent pass: compute all physical quantities once.

    Channel B (multi-label parallel) scores these candidates against each label,
    so the expensive predict_compounds / calc_ey / calc_tds work only happens once.
    """
    cfg = constants.ROAST_TABLE[roast_code]
    base_temp = cfg["base_temp"]
    brewer = constants.BREWER_PRESETS[brewer_size]
    water_ml = brewer["water_ml"]
    dose_min_x2 = int(brewer["dose_min"] * 2)
    dose_max_x2 = int(brewer["dose_max"] * 2)
    dose_step_x2 = 2 if brewer_size == "xl" else 1

    dose_range = cfg.get("dose_per_100ml")
    if dose_range and fixed_dose is None:
        roast_min_x2 = int(dose_range[0] * water_ml / 100 * 2)
        roast_max_x2 = int(dose_range[1] * water_ml / 100 * 2)
        dose_min_x2 = max(dose_min_x2, roast_min_x2)
        dose_max_x2 = min(dose_max_x2, roast_max_x2)

    if dose_min_override is not None and fixed_dose is None:
        dose_min_x2 = max(dose_min_x2, int(dose_min_override * 2))
    if dose_max_override is not None and fixed_dose is None:
        dose_max_x2 = min(dose_max_x2, int(dose_max_override * 2))

    if temp_range is not None:
        temp_lo, temp_hi = temp_range
    else:
        temp_lo = base_temp - 15
        temp_hi = int(min(base_temp + 3, constants.TEMP_BOILING_POINT))

    steep_values = [fixed_steep] if fixed_steep is not None else range(30, 421, constants.STEEP_STEP)
    if fixed_dose is not None:
        dose_values: range | list = [int(fixed_dose * 2)]
    else:
        remainder = dose_min_x2 % dose_step_x2
        if remainder:
            dose_min_x2 += dose_step_x2 - remainder
        dose_values = range(dose_min_x2, dose_max_x2 + 1, dose_step_x2)

    candidates: list[dict] = []
    for temp in range(temp_lo, temp_hi + 1):
        for dial_x10 in range(30, 76):
            dial = dial_x10 / 10
            for steep in steep_values:
                for dose_x2 in dose_values:
                    candidate = evaluate_recipe(
                        roast_code, brewer_size, temp, dial, steep, dose_x2 / 2,
                        water_gh=water_gh, water_kh=water_kh, water_mg_frac=water_mg_frac,
                        ey_floor=constants.EY_MIN,
                    )
                    if candidate is not None:
                        candidates.append(candidate)

    return candidates


def _score_against_label(
    candidate: dict,
    label: str,
    roast_code: str,
    water_kh: float,
    water_gh: float,
) -> dict:
    """Score a single physical candidate against one sensory label.

    dial_prefer fallback: label override (data/labels.json) → roast default
    (constants.ROAST_TABLE[roast].dial_prefer). The label-level prefer encodes
    each label's archetypal grind style (Hedrick 6.0 coarse vs Hoffman 4.3 fine).
    """
    from models.labels import get_label
    cfg = constants.ROAST_TABLE[roast_code]
    brewer = constants.BREWER_PRESETS.get(_brewer_key_from_name(candidate["brewer"]), {})
    raw = flavor_score(
        candidate["compounds"],
        candidate["tds"],
        roast_code,
        label,
        water_kh=water_kh,
        water_gh=water_gh,
        t_slurry=candidate["t_slurry"],
        temp_initial=candidate["temp"],
        ey=candidate["ey"],
        steep_sec=candidate["steep_sec"],
        dial=candidate["dial"],
    )
    label_spec = get_label(label)
    dial_prefer = label_spec.get("dial_prefer", cfg.get("dial_prefer"))
    if dial_prefer is not None:
        effective_dial_prefer = dial_prefer + brewer.get("dial_offset", 0.0)
        dial_dev = (candidate["dial"] - effective_dial_prefer) / constants.DIAL_PREFER_SIGMA
        dial_factor = 1.0 - constants.DIAL_PREFER_WEIGHT * (1.0 - math.exp(-0.5 * dial_dev**2))
        raw *= dial_factor
    scored = dict(candidate)
    scored["label"] = label
    scored["_score_raw"] = raw
    scored["score"] = score_to_display(raw, roast_code)
    return scored


def _brewer_key_from_name(name: str) -> str:
    for key, spec in constants.BREWER_PRESETS.items():
        if spec["name"] == name:
            return key
    return "standard"


def score_logged_recipe(
    roast_code: str,
    brewer_size: str,
    temp: float,
    dial: float,
    steep_sec: int,
    dose: float,
    water_gh: float,
    water_kh: float,
    water_mg_frac: float,
    label: str,
) -> dict:
    """Re-evaluate one known recipe against a label with the CURRENT model.

    Refreshes the stale-able derived fields (ey / tds / score / compounds) of a
    logged feedback recipe: the recipe inputs are durable, the derived numbers
    are a projection that must track model recalibration. Reuses the optimizer's
    own pipeline (evaluate_recipe + _score_against_label), so the refreshed
    score matches what a fresh optimizer run would give for that recipe.
    """
    candidate = evaluate_recipe(
        roast_code, brewer_size, temp, dial, steep_sec, dose,
        water_gh=water_gh, water_kh=water_kh, water_mg_frac=water_mg_frac,
    )
    return _score_against_label(candidate, label, roast_code, water_kh, water_gh)


def optimize(
    roast_code: str,
    brewer_size: str = "xl",
    water_gh: float = 50,
    water_kh: float = 30,
    water_mg_frac: float = 0.40,
    top_n: int = 3,
    fixed_dose: float | None = None,
    temp_range: tuple[int, int] | None = None,
    fixed_steep: int | None = None,
    dose_min_override: float | None = None,
    dose_max_override: float | None = None,
    label: str | None = None,
) -> list[dict]:
    """Single-label mode: return Top-N for that label.

    Use optimize_parallel() for Channel B (Top-1 per label, no label specified).
    For backward compat when `label=None`, defaults to 'balanced'.
    """
    if label is None:
        label = "balanced"

    candidates = _grid_candidates(
        roast_code, brewer_size, water_gh, water_kh, water_mg_frac,
        fixed_dose, temp_range, fixed_steep, dose_min_override, dose_max_override,
    )
    scored = [_score_against_label(c, label, roast_code, water_kh, water_gh) for c in candidates]
    scored.sort(key=lambda item: item["_score_raw"], reverse=True)
    return scored[:top_n]


def optimize_parallel(
    roast_code: str,
    brewer_size: str = "xl",
    water_gh: float = 50,
    water_kh: float = 30,
    water_mg_frac: float = 0.40,
    top_n: int = 1,
    fixed_dose: float | None = None,
    temp_range: tuple[int, int] | None = None,
    fixed_steep: int | None = None,
    dose_min_override: float | None = None,
    dose_max_override: float | None = None,
    labels: list[str] | None = None,
) -> dict[str, list[dict]]:
    """Channel B — score the same grid against every label, return Top-N per label.

    Shares one physical pass across all labels (no recomputation of EY/TDS/compounds).
    Default `top_n=1` matches the cupping comparison use case.
    """
    if labels is None:
        labels = label_names()

    candidates = _grid_candidates(
        roast_code, brewer_size, water_gh, water_kh, water_mg_frac,
        fixed_dose, temp_range, fixed_steep, dose_min_override, dose_max_override,
    )
    out: dict[str, list[dict]] = {}
    for label in labels:
        scored = [_score_against_label(c, label, roast_code, water_kh, water_gh) for c in candidates]
        scored.sort(key=lambda item: item["_score_raw"], reverse=True)
        out[label] = scored[:top_n]
    return out


# Exploration-bracket offsets — how far each variant is nudged off the optimum.
EXPLORE_TEMP_OFFSET = 4      # °C, temperature axis
EXPLORE_DOSE_OFFSET = 3.0    # g, dose (strength / TDS) axis


def explore_bracket(
    roast_code: str,
    brewer_size: str = "xl",
    water_gh: float = 50,
    water_kh: float = 30,
    water_mg_frac: float = 0.40,
    label: str = "balanced",
) -> list[dict]:
    """Calibration-exploration set for one label.

    Returns the optimizer's best recipe ('optimum') plus single-axis offsets —
    temperature ± and dose ± — a controlled bracket. Brewing and rating the set
    gives feedback a usable *gradient*: two 5-star cups at the same point teach
    nothing about where the preference peak sits or how wide it is; a deliberate
    spread does. Each variant moves exactly ONE axis off the optimum (controlled
    experiment), and is scored through the same pipeline as a normal run
    (score_logged_recipe), so the model score shown is directly comparable.
    """
    top = optimize(
        roast_code, brewer_size,
        water_gh=water_gh, water_kh=water_kh, water_mg_frac=water_mg_frac,
        top_n=1, label=label,
    )
    if not top:
        return []
    best = top[0]
    c_temp, c_dial, c_steep, c_dose = (
        best["temp"], best["dial"], best["steep_sec"], best["dose"],
    )

    brewer = constants.BREWER_PRESETS[brewer_size]
    temp_cap = int(constants.TEMP_BOILING_POINT)
    dose_lo, dose_hi = brewer["dose_min"], brewer["dose_max"]

    # (tag, temp, dose) — each variant nudges exactly one axis off the optimum
    plan: list[tuple[str, float, float]] = [("optimum", c_temp, c_dose)]
    for d in (-EXPLORE_TEMP_OFFSET, EXPLORE_TEMP_OFFSET):
        temp = min(c_temp + d, temp_cap)
        if temp != c_temp:
            plan.append((f"{'cooler' if d < 0 else 'hotter'} {d:+d}°C", temp, c_dose))
    for d in (-EXPLORE_DOSE_OFFSET, EXPLORE_DOSE_OFFSET):
        dose = round(min(max(c_dose + d, dose_lo), dose_hi), 1)
        if dose != c_dose:
            plan.append((f"{'lighter' if d < 0 else 'stronger'} {d:+g}g", c_temp, dose))

    out: list[dict] = []
    for tag, temp, dose in plan:
        scored = score_logged_recipe(
            roast_code, brewer_size, temp, c_dial, c_steep, dose,
            water_gh, water_kh, water_mg_frac, label,
        )
        scored["bracket"] = tag
        out.append(scored)
    return out
