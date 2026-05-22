"""Phase 10 Layer 2 + targets -- predict_attributes, attribute_distance, ideal.

models/sensory.py (cotter regression, 10 CATA attributes), models/distance.py
(plain RMS, no score), models/ideal.py (per-roast IDEAL loader). Verifies the
fitted directions match literature and that data/ideal.json stays in sync with
the model that generated it.
"""
from __future__ import annotations

import pytest

from models.distance import attribute_distance
from models.ideal import (
    available_roasts,
    get_ideal_spec,
    recipe_id,
    roast_ideal,
)
from models.sensory import ATTRIBUTES, AXIS_VIEW, predict_attributes


# ── predict_attributes ───────────────────────────────────────────────────────

def test_predict_returns_all_ten_attributes():
    attrs = predict_attributes(1.30, 20.0, roast="medium_light")
    assert set(attrs) == set(ATTRIBUTES)
    assert len(ATTRIBUTES) == 10


def test_higher_tds_raises_bitter_lowers_sweet_and_floral():
    """Cotter fit + literature: more concentrated -> more bitter, less sweet,
    less tea/floral (high TDS masks delicate aromatics)."""
    lo = predict_attributes(1.05, 20.0, roast="medium_light")
    hi = predict_attributes(1.55, 20.0, roast="medium_light")
    assert hi["Bitter"] > lo["Bitter"]
    assert hi["Sour"] > lo["Sour"]
    assert hi["Sweet"] < lo["Sweet"]
    assert hi["Tea.floral"] < lo["Tea.floral"]


def test_roast_offset_lighter_is_brighter_less_roasty():
    """_ROAST_OFFSET: lighter roast reads brighter (acidity up) and less
    burnt/roasty than a darker one at the same brew coordinates."""
    light = predict_attributes(1.30, 20.0, roast="light")
    dark = predict_attributes(1.30, 20.0, roast="moderately_dark")
    assert light["Sour"] > dark["Sour"]
    assert light["Burnt"] < dark["Burnt"]
    assert light["Dark.chocolate"] < dark["Dark.chocolate"]


def test_axis_view_groups_only_real_attributes():
    for members in AXIS_VIEW.values():
        for attr in members:
            assert attr in ATTRIBUTES


# ── attribute_distance ───────────────────────────────────────────────────────

def test_distance_zero_when_equal():
    a = predict_attributes(1.30, 20.0, roast="medium_light")
    assert attribute_distance(a, a) == 0.0


def test_distance_is_plain_rms():
    """A uniform 0.1 offset on every attribute -> RMS distance exactly 0.1."""
    ideal = {a: 0.20 for a in ATTRIBUTES}
    pred = {a: 0.30 for a in ATTRIBUTES}
    assert attribute_distance(pred, ideal) == pytest.approx(0.10, abs=1e-9)


def test_distance_symmetric():
    a = predict_attributes(1.20, 18.0, roast="light")
    b = predict_attributes(1.45, 21.0, roast="light")
    assert attribute_distance(a, b) == pytest.approx(attribute_distance(b, a))


def test_distance_grows_with_deviation():
    ideal = roast_ideal("medium_light")
    near = predict_attributes(1.36, 20.0, roast="medium_light")
    far = predict_attributes(1.75, 24.0, roast="medium_light")
    assert attribute_distance(near, ideal) < attribute_distance(far, ideal)


# ── models/ideal.py ──────────────────────────────────────────────────────────

def test_roast_ideal_has_ten_attributes_for_every_roast():
    for roast in available_roasts():
        ideal = roast_ideal(roast)
        assert set(ideal) == set(ATTRIBUTES)


@pytest.mark.parametrize("roast", available_roasts())
def test_ideal_json_in_sync_with_model(roast):
    """data/ideal.json IDEAL == predict_attributes(anchor_brew) -- the IDEAL is
    derived from the model, so it must round-trip (rounding only)."""
    ab = get_ideal_spec(roast)["anchor_brew"]
    pred = predict_attributes(ab["tds"], ab["ey"], roast=ab["roast"], dial=ab["dial"])
    assert attribute_distance(pred, roast_ideal(roast)) < 0.002


def test_recipe_id_deterministic_and_water_free():
    a = recipe_id(roast="medium_light", brewer="xl", dial=4.4,
                  steep_sec=150, temp=95.0, dose=24.0)
    b = recipe_id(roast="medium_light", brewer="xl", dial=4.4,
                  steep_sec=150, temp=95.0, dose=24.0)
    assert a == b and len(a) == 12
    # a different knob -> a different id
    c = recipe_id(roast="medium_light", brewer="xl", dial=4.5,
                  steep_sec=150, temp=95.0, dose=24.0)
    assert c != a
