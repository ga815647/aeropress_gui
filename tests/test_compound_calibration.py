"""Layer 1 — physics calibration only. No scoring, no labels.

Each anchor with a published TDS must predict within ±TDS_TOL of it — TDS is the
Layer 1 calibration anchor (2026-05-21: switched from self-referential predicted
bands to measured-TDS assertions). EY is a derived sanity band. Splitting from
test_label_scoring keeps Layer 1 (compound model) and Layer 2 (sensory labels)
independently verifiable — CLAUDE.md principle #5.
"""
from __future__ import annotations

import pytest

import constants
import runtime
from models.compounds import predict_compounds
from models.ey_model import calc_ey
from models.tds_model import calc_press_time, calc_tds


# predicted TDS must land within this of the measured anchor value
TDS_TOL = 0.05


ANCHOR_RECIPES = {
    "Hoffman": dict(
        roast="medium_light", brewer="standard",
        temp=98.0, dial=4.3, dose=11.0, steep=120.0, water=200.0,
        measured_tds=1.23, ey_band=(17.0, 22.0),
    ),
    "April": dict(
        roast="medium_light", brewer="standard",
        temp=85.0, dial=5.0, dose=13.0, steep=90.0, water=200.0,
        press_s=30.0,
        extra_ey={"pre_pour_ml": 50.0, "pre_pour_sec": 30.0,
                  "partial_seal_sec": 25.0, "partial_seal_water_ml": 50.0},
        extra_cpd={"partial_seal_sec": 25.0, "partial_seal_water_ml": 50.0},
        measured_tds=1.17, ey_band=(14.0, 18.0),
    ),
    "Championship": dict(
        roast="medium_light", brewer="standard",
        temp=80.0, dial=5.0, dose=17.0, steep=100.0, water=200.0,
        press_s=20.0,
        extra_ey={"inverted": True, "n_swirls": 2},
        extra_cpd={"inverted": True, "n_swirls": 2},
        measured_tds=1.56, ey_band=(13.0, 18.0),
    ),
    "Hedrick": dict(
        roast="medium_light", brewer="standard",
        temp=95.0, dial=6.0, dose=14.0, steep=240.0, water=200.0,
        measured_tds=None, tds_band=(1.20, 1.45), ey_band=(13.0, 18.0),
    ),
}


def _brew(spec):
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
    compounds = predict_compounds(
        roast_code=spec["roast"], temp=spec["temp"], dial=spec["dial"],
        steep_sec=spec["steep"], ey=ey,
        water_gh=50, water_mg_frac=0.40,
        press_equiv=press_eq, pour_offset=pour_offset,
        water_ml=spec["water"], dose=spec["dose"], press_sec=press_s, area_cm2=area,
        **spec.get("extra_cpd", {}),
    )
    return ey, tds, compounds


@pytest.mark.parametrize("name", list(ANCHOR_RECIPES))
def test_anchor_physics_within_band(name):
    spec = ANCHOR_RECIPES[name]
    ey, tds, _ = _brew(spec)
    ey_lo, ey_hi = spec["ey_band"]
    measured = spec.get("measured_tds")
    if measured is not None:
        assert abs(tds - measured) <= TDS_TOL, \
            f"{name}: predicted TDS {tds:.3f} vs measured {measured} exceeds tol {TDS_TOL}"
    else:
        tds_lo, tds_hi = spec["tds_band"]
        assert tds_lo <= tds <= tds_hi, f"{name}: predicted TDS {tds:.3f} outside [{tds_lo}, {tds_hi}]"
    assert ey_lo <= ey <= ey_hi, f"{name}: predicted EY {ey:.2f} outside [{ey_lo}, {ey_hi}]"


def test_under_extract_physics_low_ey():
    ey, tds, _ = _brew(dict(
        roast="medium_light", brewer="standard",
        temp=93.0, dial=6.5, dose=11.0, steep=60.0, water=200.0,
    ))
    assert ey < 15.0, f"under-extract should yield EY<15%, got {ey}"
    assert tds < 0.85, f"under-extract should yield TDS<0.85%, got {tds}"


def test_over_extract_physics_high_cga():
    """Over-extracted (fine + long + hot) yields markedly higher CGA than Hoffman."""
    _, _, over_cpd = _brew(dict(
        roast="medium_light", brewer="standard",
        temp=99.0, dial=3.5, dose=11.0, steep=240.0, water=200.0,
    ))
    _, _, hoffman_cpd = _brew(ANCHOR_RECIPES["Hoffman"])
    # raw absolute CGA: over-extract well above Hoffman
    assert over_cpd["CGA"] > hoffman_cpd["CGA"] * 1.2, \
        f"over-extract CGA {over_cpd['CGA']:.4f} should be >1.2× Hoffman {hoffman_cpd['CGA']:.4f}"


def test_april_acidity_dominant():
    """Layer 1 sanity: April recipe predicts AC > CGA (clean acidity, not astringent)."""
    _, _, cpd = _brew(ANCHOR_RECIPES["April"])
    assert cpd["AC"] > cpd["CGA"]
    assert cpd["AC"] > cpd["MEL"]


def test_hedrick_coarse_long_not_astringent():
    """Layer 1: coarse + long must give AC > CGA (grind_kinetics suppresses CGA accumulation)."""
    _, _, cpd = _brew(ANCHOR_RECIPES["Hedrick"])
    assert cpd["AC"] > cpd["CGA"]
