"""Phase 10 Layer 1 -- thin knob -> TDS/EY converter (models/layer1.py).

Pure physics: the single plain-immersion calibration anchor (Hoffman) plus the
monotonicity / saturation / brewer-agnosticism the equilibrium-desorption form
guarantees. No scoring, no sensory -- CLAUDE.md principle #5.
"""
from __future__ import annotations

from models.layer1 import brew


def test_hoffman_anchor_reproduces_measured_tds():
    """E_MAX_REF is solved so the Hoffman plain-immersion recipe hits TDS 1.23."""
    out = brew("medium_light", 98.0, 4.3, 120.0, 11.0, 200.0)
    assert abs(out["tds"] - 1.23) <= 0.01, f"Hoffman TDS {out['tds']:.3f} != 1.23"
    assert 17.0 <= out["ey"] <= 23.0, f"Hoffman EY {out['ey']:.2f} out of sane band"


def test_ey_rises_with_temperature():
    cool = brew("medium_light", 88.0, 4.3, 150.0, 11.0, 200.0)
    hot = brew("medium_light", 98.0, 4.3, 150.0, 11.0, 200.0)
    assert hot["ey"] > cool["ey"]


def test_ey_rises_with_fineness():
    coarse = brew("medium_light", 95.0, 6.5, 150.0, 11.0, 200.0)
    fine = brew("medium_light", 95.0, 3.5, 150.0, 11.0, 200.0)
    assert fine["ey"] > coarse["ey"]


def test_ey_rises_with_steep_time():
    short = brew("medium_light", 95.0, 4.3, 45.0, 11.0, 200.0)
    long = brew("medium_light", 95.0, 4.3, 300.0, 11.0, 200.0)
    assert long["ey"] > short["ey"]


def test_ey_saturates():
    """First-order approach to a ceiling -> diminishing returns: the 60->180s
    gain must exceed the 180->300s gain."""
    e60 = brew("medium_light", 95.0, 4.3, 60.0, 11.0, 200.0)["ey"]
    e180 = brew("medium_light", 95.0, 4.3, 180.0, 11.0, 200.0)["ey"]
    e300 = brew("medium_light", 95.0, 4.3, 300.0, 11.0, 200.0)["ey"]
    assert (e180 - e60) > (e300 - e180) > 0


def test_higher_brew_ratio_lowers_ey():
    """f_ratio: more coffee per unit water saturates the slurry sooner."""
    lean = brew("medium_light", 95.0, 4.3, 150.0, 11.0, 200.0)
    rich = brew("medium_light", 95.0, 4.3, 150.0, 18.0, 200.0)
    assert rich["ey"] < lean["ey"]


def test_tds_rises_with_dose():
    light_dose = brew("medium_light", 95.0, 4.3, 150.0, 11.0, 200.0)
    heavy_dose = brew("medium_light", 95.0, 4.3, 150.0, 16.0, 200.0)
    assert heavy_dose["tds"] > light_dose["tds"]


def test_brewer_agnostic_at_equal_ratio():
    """Layer 1 sees only water_ml + dose: same brew ratio -> identical TDS/EY,
    so XL is exactly 'standard scaled by water' (constants.py note)."""
    standard = brew("medium_light", 95.0, 4.3, 150.0, 11.0, 200.0)
    xl = brew("medium_light", 95.0, 4.3, 150.0, 22.0, 400.0)
    assert abs(standard["ey"] - xl["ey"]) < 1e-9
    assert abs(standard["tds"] - xl["tds"]) < 1e-9


def test_darker_roast_has_higher_ceiling():
    """E_MAX_ROAST_FACTOR: darker = more soluble = higher EY at the same knobs."""
    light = brew("light", 95.0, 4.3, 150.0, 11.0, 200.0)
    dark = brew("moderately_dark", 95.0, 4.3, 150.0, 11.0, 200.0)
    assert dark["ey"] > light["ey"]


def test_outputs_are_positive_floats():
    out = brew("medium", 92.0, 4.5, 120.0, 12.0, 200.0)
    assert isinstance(out["ey"], float) and isinstance(out["tds"], float)
    assert out["ey"] > 0 and out["tds"] > 0
