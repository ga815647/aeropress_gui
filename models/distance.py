"""Phase 10 Step 5 — sensory-space distance to the roast IDEAL.

A brew is ranked purely by how far its predicted sensory attributes sit from
the roast's IDEAL (`data/ideal.json`, via models.ideal):

    distance = sqrt( mean over attributes of (predicted − ideal)² )

A plain RMS of the per-attribute deviations, in CATA-frequency units — the same
units the attributes and the per-attribute deltas are displayed in. 0.0 =
predicted equals the IDEAL; larger = farther. Smaller is better; the optimizer
ranks ascending.

--- no score, no weights ---

There is deliberately NO 0–100 score: a score implies an objective grade, and
cotter's hedonic data shows there is no objective "best" cup. The optimizer
reports the plain thing — how far a recipe lands from *your* target. The number
ranked by is the number displayed.

And no per-attribute weights. Step 5.5 selected the 10 model attributes by an
R² >= 0.44 gate (models/sensory.py) — the un-fittable attributes were dropped
outright, not kept-and-down-weighted. The survivors all carry real signal, so
they enter the distance equally. (If feedback later shows a kept attribute's
prediction is unreliable, weights can be reintroduced — Step 7.)

--- no separate TDS / EY term ---

TDS's effect on flavor is already fully carried by the attributes (Layer 2 /
models/sensory.py regresses every attribute on TDS/EY). A standalone TDS factor
would double-count it. Bad cups (under/over-extraction) self-differentiate by
attribute distance — no TDS/EY floor needed (CLAUDE.md principle #3).
"""
from __future__ import annotations

import math

from models.sensory import ATTRIBUTES


def attribute_distance(predicted: dict, ideal: dict) -> float:
    """RMS distance (CATA-frequency units) from predicted attributes to IDEAL.

    Args:
        predicted: attribute intensities from models.sensory.predict_attributes().
        ideal:     the roast's IDEAL from models.ideal.roast_ideal().

    Returns:
        0.0 when predicted == ideal; larger = farther. The optimizer ranks
        ascending. Smooth everywhere (CLAUDE.md principle #1).
    """
    loss = 0.0
    for attr in ATTRIBUTES:
        delta = predicted[attr] - ideal[attr]
        loss += delta * delta
    return math.sqrt(loss / len(ATTRIBUTES))
