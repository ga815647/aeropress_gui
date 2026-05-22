"""Phase 10 Step 5 — per-roast sensory IDEAL loader + recipe_id helper.

Layer 2's flavor target is ONE 6-axis sensory IDEAL per roast, stored in
`data/ideal.json` (schema v5, per-roast — see docs/PHASE10_STEP3_LABELS.md).
This module is the single read path; everything downstream imports from here.

Renamed from `models/labels.py` at Step 5: Phase 10 §0 removed the `label`
concept, so the old label loader / `ideal_abs` compound machinery is gone. What
survives is the per-roast IDEAL lookup and the `recipe_id` feedback hook.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "ideal.json"


@lru_cache(maxsize=1)
def load_ideals() -> dict[str, dict]:
    """Read data/ideal.json, drop the _schema docs entry, return {roast: spec}."""
    with _DATA_PATH.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    return {name: spec for name, spec in raw.items() if not name.startswith("_")}


def available_roasts() -> list[str]:
    """Roast keys with a defined sensory IDEAL (light / medium_light / ...)."""
    return list(load_ideals().keys())


def get_ideal_spec(roast: str) -> dict:
    """Full IDEAL spec for a roast (ideal + anchor_brew + seed + description)."""
    ideals = load_ideals()
    if roast not in ideals:
        raise KeyError(
            f"No sensory IDEAL for roast {roast!r}. Defined: {sorted(ideals)}. "
            f"Add one by editing data/ideal.json."
        )
    return ideals[roast]


def roast_ideal(roast: str) -> dict[str, float]:
    """The 6-axis sensory IDEAL for a roast — the bullseye for scoring.

    Keys follow models.sensory.SENSORY_AXES order; values are CATA detection
    frequencies (nominally [0, 1]). Raises KeyError for an undefined roast.
    """
    return get_ideal_spec(roast)["ideal"]


def recipe_id(
    roast: str,
    brewer: str,
    dial: float,
    steep_sec: int | float,
    temp: float,
    dose: float,
) -> str:
    """Deterministic 12-char hash for feedback.jsonl cross-reference (Phase 9 hook).

    Keys are rounded to the optimizer grid resolution so equivalent recipes
    collapse to the same id. Water chemistry is NOT part of the id — Phase 10
    does not model it, so two cups differing only in water ARE the same recipe.
    """
    payload = (
        f"{roast}|{brewer}|{dial:.2f}|{int(round(steep_sec))}"
        f"|{temp:.1f}|{dose:.1f}"
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
