"""Tests for models/grind.py — grinder dial cross-conversion."""
import pytest

from models import grind


# ── Forte BG mixed-radix codec ───────────────────────────────────────────────
@pytest.mark.parametrize("label,index", [
    ("3W", 74), ("4E", 82), ("4T", 97), ("5R", 121),
    ("6H", 137), ("7E", 160), ("8S", 200),
])
def test_forte_codec_roundtrip(label, index):
    assert grind.forte_to_index(label) == index
    assert grind.forte_from_index(index) == label


def test_forte_codec_handles_lowercase_and_space():
    assert grind.forte_to_index(" 5r ") == 121


@pytest.mark.parametrize("bad", ["", "5", "R", "55", "5RR", "5@"])
def test_forte_codec_rejects_bad(bad):
    with pytest.raises(ValueError):
        grind.forte_to_index(bad)


# grinder groupings reused across parametrized tests
NUMERIC_GRINDERS = [
    "zp6", "comandante_c40", "ek43s",
    "fellow_opus", "fellow_ode_ssp", "fellow_ode_gen2",
]
ALL_GRINDERS = NUMERIC_GRINDERS + ["forte_bg"]


# ── anchor round-trips: every table cell maps to its integer level ───────────
@pytest.mark.parametrize("g", ALL_GRINDERS)
def test_anchor_settings_map_to_integer_levels(g):
    anchors = grind.GRINDERS[g].get("anchors") or grind.GRINDERS[g]["labels"]
    for i, anchor in enumerate(anchors, start=1):
        level, ok = grind.to_level(g, anchor)
        assert ok
        assert level == pytest.approx(float(i))


@pytest.mark.parametrize("g", NUMERIC_GRINDERS)
def test_levels_map_back_to_anchor_settings(g):
    anchors = grind.GRINDERS[g]["anchors"]
    for i, anchor in enumerate(anchors, start=1):
        setting, ok = grind.from_level(g, float(i))
        assert ok
        assert setting == pytest.approx(anchor, abs=0.05)


def test_forte_levels_map_back_to_labels():
    for i, label in enumerate(grind.GRINDERS["forte_bg"]["labels"], start=1):
        setting, ok = grind.from_level("forte_bg", float(i))
        assert ok
        assert setting == label


# ── cross-grinder conversion at table rows ───────────────────────────────────
def test_convert_at_anchor_rows():
    # level 3 row: ZP6 2.8 / Comandante 17 / EK43s 6.3 / Forte 4T
    assert grind.convert("comandante_c40", 17, "zp6").setting == pytest.approx(2.8)
    assert grind.convert("zp6", 2.8, "ek43s").setting == pytest.approx(6.3)
    assert grind.convert("ek43s", 8.1, "comandante_c40").setting == pytest.approx(20)
    # level 5 row -> Forte "6H"
    assert grind.convert("zp6", 4.4, "forte_bg").setting == "6H"
    assert grind.convert("forte_bg", "6H", "zp6").setting == pytest.approx(4.4)


def test_convert_fellow_at_anchor_rows():
    # level 4 row: ZP6 3.7 / Fellow Opus 4.1 / Ode SSP 4.2 / Ode Gen 2 3.1
    assert grind.convert("zp6", 3.7, "fellow_opus").setting == pytest.approx(4.1)
    assert grind.convert("fellow_ode_ssp", 4.2, "zp6").setting == pytest.approx(3.7)
    assert grind.to_zp6("fellow_ode_gen2", 3.1) == pytest.approx(3.7)
    # Fellow Opus 5.0 (level 5) -> EK43s 9.3
    assert grind.convert("fellow_opus", 5.0, "ek43s").setting == pytest.approx(9.3)


def test_identity_conversion():
    assert grind.convert("zp6", 4.0, "zp6").setting == pytest.approx(4.0)
    assert grind.to_zp6("zp6", 4.3) == pytest.approx(4.3)


def test_interpolation_midpoint():
    # Comandante 18.5 sits halfway between level 3 (17) and level 4 (20)
    conv = grind.convert("comandante_c40", 18.5, "zp6")
    assert conv.level == pytest.approx(3.5)
    # ZP6 halfway between 2.8 and 3.7 ~= 3.25 (rounded to 0.1 dial)
    assert float(conv.setting) == pytest.approx(3.25, abs=0.06)
    assert conv.in_range


def test_to_zp6_from_each_grinder():
    assert grind.to_zp6("comandante_c40", 22) == pytest.approx(4.4)
    assert grind.to_zp6("ek43s", 9.3) == pytest.approx(4.4)
    assert grind.to_zp6("forte_bg", "6H") == pytest.approx(4.4)


# ── out-of-range flagging (model searches ZP6 up to 7.5; table tops at 7.0) ──
def test_out_of_range_flagged():
    level, ok = grind.to_level("zp6", 7.5)
    assert not ok
    assert level > 7.0
    # within span stays in range
    _, ok2 = grind.to_level("zp6", 4.4)
    assert ok2


def test_format_dial():
    assert grind.format_dial("zp6", 4.0) == "4.0"
    assert grind.format_dial("comandante_c40", 2.8) == "17"
    assert grind.format_dial("ek43s", 2.8) == "6.3"
    assert grind.format_dial("forte_bg", 4.4) == "6H"


def test_format_dial_marks_extrapolation():
    out = grind.format_dial("comandante_c40", 7.5)  # ZP6 7.5 is past the table
    assert out.startswith("~")


# ── monotonicity sanity (anchors must be strictly increasing to invert) ──────
@pytest.mark.parametrize("g", ALL_GRINDERS)
def test_anchors_strictly_increasing(g):
    anchors = grind._anchors(g)
    assert list(anchors) == sorted(anchors)
    assert len(set(anchors)) == len(anchors)


# ── API surface ──────────────────────────────────────────────────────────────
def test_supported_lists_native_first():
    assert grind.supported()[0] == "zp6"
    assert set(grind.supported()) == set(grind.GRINDERS)


def test_table_payload_shape():
    p = grind.table_payload()
    assert p["native"] == "zp6"
    assert p["levels"] == [1, 2, 3, 4, 5, 6, 7]
    assert set(p["grinders"]) == set(grind.GRINDERS)
    fb = p["grinders"]["forte_bg"]
    assert fb["kind"] == "forte"
    assert fb["anchors"] == [74, 82, 97, 121, 137, 160, 200]
    assert fb["labels"][0] == "3W"


def test_unknown_grinder_raises():
    with pytest.raises(KeyError):
        grind.to_level("bunnzilla", 5)
