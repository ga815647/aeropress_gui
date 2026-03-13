from __future__ import annotations

import constants
from data.water_presets import get_water_preset


def apply_environment_settings(t_env: float, altitude: float) -> None:
    constants.T_ENV = t_env
    constants.TEMP_BOILING_POINT = 100.0 - altitude / 300.0


def resolve_water_profile(
    *,
    gh: float | None,
    kh: float | None,
    mg_frac: float | None,
    preset: str | None,
) -> tuple[float, float, float, str]:
    if gh is not None and kh is not None:
        return gh, kh, (mg_frac if mg_frac is not None else 0.40), "manual"
    if preset is not None:
        item = get_water_preset(preset)
        return item["gh"], item["kh"], item.get("mg_frac", 0.40), preset
    return 50.0, 30.0, 0.40, "default"
