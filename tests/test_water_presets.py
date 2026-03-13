from data.water_presets import get_water_preset


def test_get_water_preset_returns_dict() -> None:
    preset = get_water_preset("aquacode_7l")
    assert isinstance(preset, dict)
    assert preset["gh"] == 65
    assert preset["kh"] == 5
    assert preset["mg_frac"] == 0.73
