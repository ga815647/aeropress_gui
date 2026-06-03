"""Phase 10 optimizer (optimizer.py).

Pipeline: knobs -> layer1.brew -> sensory.predict_attributes -> attribute
distance. The optimizer searches dose x dial x steep at a fixed temperature and
ranks ascending by distance to the per-roast IDEAL.
"""
from __future__ import annotations

import constants
from optimizer import evaluate_recipe, optimize, score_logged_recipe

_RESULT_KEYS = {
    "recipe_id", "roast", "brewer", "brewer_size", "water_ml", "temp",
    "dial", "steep_sec", "dose", "ey", "tds", "attributes", "ideal", "distance",
}


def test_optimize_returns_top_n_sorted_by_distance():
    results = optimize(roast_code="medium_light", brewer_size="xl", top_n=5)
    assert len(results) == 5
    dists = [r["distance"] for r in results]
    assert dists == sorted(dists), "results must be ascending by distance"


def test_optimize_top1_reaches_the_ideal():
    top = optimize(roast_code="medium_light", brewer_size="xl", top_n=1)[0]
    assert top["distance"] < 0.005, f"Top-1 distance {top['distance']} too far from IDEAL"


def test_evaluate_recipe_has_expected_shape():
    r = evaluate_recipe("medium_light", "xl", 95.0, 4.5, 150, 24.0)
    assert _RESULT_KEYS <= set(r)
    assert set(r["attributes"]) == set(r["ideal"])
    assert r["distance"] >= 0.0


def test_score_logged_recipe_matches_evaluate_recipe():
    """The feedback recompute path must score a logged recipe identically to a
    fresh optimizer evaluation -- one code path."""
    args = ("medium_light", "xl", 95.0, 4.5, 150, 24.0)
    logged = score_logged_recipe(*args)
    fresh = evaluate_recipe(*args)
    assert logged["distance"] == fresh["distance"]
    assert logged["tds"] == fresh["tds"]
    assert logged["attributes"] == fresh["attributes"]


def test_temp_defaults_to_roast_convention():
    results = optimize(roast_code="light", brewer_size="xl", top_n=1)
    assert results[0]["temp"] == constants.DEFAULT_TEMP["light"]


def test_explicit_temp_is_used():
    results = optimize(roast_code="medium_light", brewer_size="xl", temp=92.0, top_n=1)
    assert results[0]["temp"] == 92.0


def test_fixed_dose_constrains_search():
    results = optimize(roast_code="medium_light", brewer_size="xl",
                       fixed_dose=22.0, top_n=5)
    assert all(r["dose"] == 22.0 for r in results)


def test_roast_method_emerges():
    """Not hard-coded: hitting each roast IDEAL should make light come out
    shorter than a dark roast. (The original assertion also expected light to
    grind finer; that held under the tim-anchored light IDEAL but no longer
    after the 2026-06-02 re-anchor to the Hoffman archetype, which uses
    moderate grind. Steep differentiation is the remaining roast-method signal.)
    """
    light = optimize(roast_code="light", brewer_size="xl", top_n=1)[0]
    dark = optimize(roast_code="moderately_dark", brewer_size="xl", top_n=1)[0]
    assert light["steep_sec"] < dark["steep_sec"], "light roast should steep shorter"
