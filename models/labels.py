"""Phase 8 — label loader + recipe_id helper.

Layer 2 sensory label islands live in `data/labels.json` (not Python).
This module is the single read path; everything else imports from here.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import constants

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "labels.json"


@lru_cache(maxsize=1)
def load_labels() -> dict[str, dict]:
    """Read data/labels.json, drop the _schema docs entry, return label map."""
    with _DATA_PATH.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    return {name: spec for name, spec in raw.items() if not name.startswith("_")}


def label_names() -> list[str]:
    return list(load_labels().keys())


def get_label(name: str) -> dict:
    labels = load_labels()
    if name not in labels:
        raise KeyError(
            f"Unknown label {name!r}. Available: {sorted(labels)}. "
            f"Add a new label by editing data/labels.json (Channel A discovery)."
        )
    return labels[name]


def ideal_abs(label_name: str, tds: float) -> dict[str, float]:
    """label IDEAL fractions × TDS → absolute compound targets used by scoring.

    Replaces the deprecated build_ideal_abs() Gaussian-bracket interpolation.
    """
    spec = get_label(label_name)
    ideal = spec["ideal"]
    return {k: ideal[k] * tds for k in constants.KEYS}


def recipe_id(
    roast: str,
    brewer: str,
    dial: float,
    steep_sec: int | float,
    temp: float,
    dose: float,
    water_gh: float,
    water_kh: float,
    water_mg_frac: float,
) -> str:
    """Deterministic 12-char hash for feedback.jsonl cross-reference (Phase 9 hook).

    Keys are rounded to the optimizer grid resolution so equivalent recipes
    collapse to the same id.
    """
    payload = (
        f"{roast}|{brewer}|{dial:.2f}|{int(round(steep_sec))}"
        f"|{temp:.1f}|{dose:.1f}|{water_gh:g}|{water_kh:g}|{water_mg_frac:.2f}"
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
