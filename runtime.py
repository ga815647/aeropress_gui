from __future__ import annotations

import constants


def apply_environment_settings(t_env: float, altitude: float) -> None:
    """Set ambient temp / altitude-adjusted boiling point on the constants module.

    Phase 10 note: layer1 / sensory / distance are pure and do not read these —
    the call is currently inert. Kept for the webapp / feedback callers until
    Step 6 decides whether to drop it.
    """
    constants.T_ENV = t_env
    constants.TEMP_BOILING_POINT = 100.0 - altitude / 300.0
