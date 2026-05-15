"""Layer 2 — sensory label scoring only.

Each label's bullseye anchor scores above its threshold on its own label.
Bad recipes (under / over extraction) score low on every label — no label
should "rescue" an objectively bad brew.

Pure scoring tests — no compound physics assertions. Pairs with
test_compound_calibration.py per CLAUDE.md principle #5.
"""
from __future__ import annotations

import pytest

import constants
import runtime
from models.compounds import predict_compounds
from models.ey_model import calc_ey
from models.labels import label_names
from models.scoring import flavor_score, score_to_display
from models.tds_model import calc_press_time, calc_tds


ANCHOR_TO_LABEL = {
    "Hoffman": ("balanced", 80.0),
    "April": ("acid-forward", 60.0),
    "Championship": ("sweet-body", 55.0),
    "Hedrick": ("coarse-modern", 55.0),
}

ANCHOR_RECIPES = {
    "Hoffman": dict(
        roast="medium_light", brewer="standard",
        temp=98.0, dial=4.3, dose=11.0, steep=120.0, water=200.0,
    ),
    "April": dict(
        roast="medium_light", brewer="standard",
        temp=85.0, dial=5.0, dose=13.0, steep=90.0, water=200.0, press_s=30.0,
        extra_ey={"pre_pour_ml": 50.0, "pre_pour_sec": 30.0,
                  "partial_seal_sec": 25.0, "partial_seal_water_ml": 50.0},
        extra_cpd={"partial_seal_sec": 25.0, "partial_seal_water_ml": 50.0},
    ),
    "Championship": dict(
        roast="medium_light", brewer="standard",
        temp=80.0, dial=5.0, dose=17.0, steep=100.0, water=200.0, press_s=20.0,
        extra_ey={"inverted": True, "n_swirls": 2},
        extra_cpd={"inverted": True, "n_swirls": 2},
    ),
    "Hedrick": dict(
        roast="medium_light", brewer="standard",
        temp=95.0, dial=6.0, dose=14.0, steep=240.0, water=200.0,
    ),
}


def _brew_and_score(spec, label):
    runtime.apply_environment_settings(20.0, 0)
    area = constants.BREWER_PRESETS[spec["brewer"]]["area_cm2"]
    press_s = spec.get("press_s") or calc_press_time(
        spec["dose"], spec["dial"], spec["steep"], brewer_size=spec["brewer"])
    press_eq = min(press_s, constants.CHANNELING_PRESS_THRESHOLD) * constants.PRESS_EQUIV_FRACTION
    pour_offset = (spec["water"] / constants.POUR_RATE) / 2.0
    ey = calc_ey(
        roast_code=spec["roast"], temp_initial=spec["temp"], dial=spec["dial"],
        steep_sec=spec["steep"], dose=spec["dose"], water_ml=spec["water"],
        water_gh=50, press_equiv=press_eq, pour_offset=pour_offset, area_cm2=area,
        **spec.get("extra_ey", {}),
    )
    tds = calc_tds(spec["roast"], spec["dose"], ey, spec["dial"], water_ml=spec["water"])
    cpd = predict_compounds(
        roast_code=spec["roast"], temp=spec["temp"], dial=spec["dial"],
        steep_sec=spec["steep"], ey=ey,
        water_gh=50, water_mg_frac=0.40,
        press_equiv=press_eq, pour_offset=pour_offset,
        water_ml=spec["water"], dose=spec["dose"], press_sec=press_s, area_cm2=area,
        **spec.get("extra_cpd", {}),
    )
    raw = flavor_score(
        cpd, tds, spec["roast"], label,
        water_kh=30, water_gh=50,
        t_slurry=spec["temp"] - 2.0, temp_initial=spec["temp"],
        ey=ey, steep_sec=spec["steep"], dial=spec["dial"],
    )
    return score_to_display(raw)


@pytest.mark.parametrize("anchor", list(ANCHOR_TO_LABEL))
def test_anchor_scores_high_on_bullseye_label(anchor):
    spec = ANCHOR_RECIPES[anchor]
    label, threshold = ANCHOR_TO_LABEL[anchor]
    score = _brew_and_score(spec, label)
    assert score >= threshold, (
        f"{anchor} on '{label}' label: {score} < {threshold}. "
        f"Adjust data/labels.json IDEAL or compound model."
    )


def test_under_extract_low_on_every_label():
    spec = dict(roast="medium_light", brewer="standard",
                temp=93.0, dial=6.5, dose=11.0, steep=60.0, water=200.0)
    for label in label_names():
        score = _brew_and_score(spec, label)
        assert score < 40.0, f"under-extract scored {score} on '{label}' (should be <40 everywhere)"


def test_over_extract_low_on_every_label():
    spec = dict(roast="medium_light", brewer="standard",
                temp=99.0, dial=3.5, dose=11.0, steep=240.0, water=200.0)
    for label in label_names():
        score = _brew_and_score(spec, label)
        assert score < 50.0, f"over-extract scored {score} on '{label}' (should be <50 everywhere)"


def test_acid_forward_prefers_april_over_balanced():
    """An acid-forward recipe (April) scores higher on acid-forward than balanced."""
    spec = ANCHOR_RECIPES["April"]
    on_acid = _brew_and_score(spec, "acid-forward")
    on_balanced = _brew_and_score(spec, "balanced")
    assert on_acid > on_balanced, (
        f"April on acid-forward ({on_acid}) should beat April on balanced ({on_balanced})"
    )


def test_sweet_body_prefers_championship_over_balanced():
    spec = ANCHOR_RECIPES["Championship"]
    on_sweet = _brew_and_score(spec, "sweet-body")
    on_balanced = _brew_and_score(spec, "balanced")
    assert on_sweet > on_balanced
