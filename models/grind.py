"""Grinder dial cross-conversion — single source of truth.

The model's native grind axis is the **1Zpresso ZP6 dial** (see
`models/layer1.py:DIAL_REF` / ARCHITECTURE.md "Grinder Dial Reference"). This
module converts a grind setting on any supported grinder to/from the ZP6 axis,
so a user on another grinder can read recommendations in their own units and
enter their own settings — without the model ever leaving the ZP6 axis it was
calibrated on.

Source data: ``docs/刻度比較.xlsx`` ("刻度" sheet) — a 7-level cross-grinder
equivalence table. Each row is one **brew-taste-matched** grind across grinders
(the same bean dialed to brew comparably on each machine). Because the table is
already a taste/extraction match, **no surface-area ("Forte should be finer")
correction is layered on top** — the old µm-bridge ``EXTRACTION_MATCH_RATIO=0.9``
fudge is exactly what this empirical table replaces.

Only 7 anchor points per grinder, so between anchors we piecewise-linear
interpolate on a shared fractional "level" axis (1..7; level 1 = finest, level
7 = coarsest). A setting outside a grinder's anchor span extrapolates from the
nearest segment and is flagged ``in_range=False`` (e.g. the model searches ZP6
up to 7.5, just past the table's 7.0 coarse anchor).

Forte BG dials are alphanumeric (``<macro><micro>``, e.g. ``"5R"``). They are a
**mixed-radix single linear axis**: 1 macro step = 26 micro steps, so a label
decodes to a single integer step index ``(macro-1)*26 + micro`` that interpolates
exactly like any numeric grinder, then re-encodes for display.

The "1 macro = full A-Z micro sweep" additivity is verified, not assumed: the
Baratza/Breville Forté AP/BG manual states the full micro range equals one macro
click, and Honest Coffee Guide lists settings ``1A``..``10Z`` (AeroPress ``2A``..
``8X``). Macros 1-10, micros A-Z(26); lower = finer.

This module is brewer/model-agnostic display+input plumbing — it touches none of
the Layer 1 / Layer 2 / distance physics and is not a calibration anchor.
"""
from __future__ import annotations

import math
from typing import NamedTuple

# ── the equivalence table (docs/刻度比較.xlsx, sheet "刻度") ──────────────────
# 7 levels, finest (1) -> coarsest (7). Per-grinder anchor settings aligned to
# the levels. Numeric grinders store their dial value directly; Forte BG stores
# its raw <macro><micro> labels (decoded to a linear step index for interp).
LEVELS = (1, 2, 3, 4, 5, 6, 7)

_FORTE_MICROS = 26          # micro letters A..Z per macro step (mixed-radix base)
_FORTE_MAX_INDEX = 10 * _FORTE_MICROS - 1   # 10 macros -> 0..259


def _round_half_up(value: float, decimals: int = 0) -> int | float:
    """Round half away from zero via ``floor(x + 0.5)`` on the scaled value.

    Deliberately NOT Python's built-in ``round`` (banker's / half-to-even): the
    front-end mirrors this exact ``floor(x*10**d + 0.5)`` on a bit-identical
    IEEE-754 double, so the webapp's displayed setting is byte-identical to the
    CLI's (the "single source of truth" guarantee). Returns the scaled int when
    ``decimals == 0``, else a float rounded to ``decimals`` places.
    """
    f = 10 ** decimals
    m = math.floor(float(value) * f + 0.5)
    return m if decimals == 0 else m / f

# Display label + native unit hint per grinder; ``zp6`` is the model axis.
GRINDERS = {
    "zp6": {
        "label": "1Zpresso ZP6",
        "kind": "numeric",
        "anchors": (1.8, 2.1, 2.8, 3.7, 4.4, 5.4, 7.0),
        "decimals": 1,
        "unit": "dial",
    },
    "comandante_c40": {
        "label": "Comandante C40",
        "kind": "numeric",
        "anchors": (14.0, 15.0, 17.0, 20.0, 22.0, 25.0, 30.0),
        "decimals": 0,
        "unit": "clicks",
    },
    "ek43s": {
        "label": "Mahlkönig EK43s",
        "kind": "numeric",
        "anchors": (4.4, 5.0, 6.3, 8.1, 9.3, 11.2, 14.2),
        "decimals": 1,
        "unit": "dial",
    },
    "fellow_opus": {
        "label": "Fellow Opus",
        "kind": "numeric",
        "anchors": (2.2, 3.0, 3.2, 4.1, 5.0, 5.3, 7.1),
        "decimals": 1,
        "unit": "dial",
    },
    "fellow_ode_ssp": {
        "label": "Fellow Ode (SSP)",
        "kind": "numeric",
        "anchors": (3.0, 3.1, 3.2, 4.2, 5.1, 6.0, 7.2),
        "decimals": 1,
        "unit": "dial",
    },
    "fellow_ode_gen2": {
        "label": "Fellow Ode Gen 2",
        "kind": "numeric",
        "anchors": (1.2, 2.0, 2.2, 3.1, 4.0, 5.0, 6.1),
        "decimals": 1,
        "unit": "dial",
    },
    "forte_bg": {
        "label": "Baratza Forte BG",
        "kind": "forte",
        # raw labels; decoded indices computed below into ``anchors``
        "labels": ("3W", "4E", "4T", "5R", "6H", "7E", "8S"),
        "unit": "macro+micro",
    },
}

# the model's native axis key
NATIVE = "zp6"


class Conversion(NamedTuple):
    """Result of a grind conversion.

    setting:  the destination grinder's setting (float for numeric grinders,
              ``"<macro><micro>"`` str for Forte BG).
    level:    the fractional equivalence level (1..7) used as the pivot.
    in_range: False if the source setting fell outside the table's 7-anchor
              span and the result is an extrapolation (treat as approximate).
    """

    setting: object
    level: float
    in_range: bool


# ── Forte BG mixed-radix codec ───────────────────────────────────────────────
def forte_to_index(label: str) -> int:
    """``"5R"`` -> linear step index ``(macro-1)*26 + micro``  (e.g. 5R -> 121)."""
    s = str(label).strip().upper()
    i = 0
    while i < len(s) and s[i].isdigit():
        i += 1
    if i == 0 or i >= len(s):
        raise ValueError(f"bad Forte BG dial {label!r} (want '<macro><micro>', e.g. '5R')")
    macro = int(s[:i])
    micro_ch = s[i:].strip()
    if len(micro_ch) != 1 or not ("A" <= micro_ch <= "Z"):
        raise ValueError(f"bad Forte BG micro {label!r} (micro must be a single A-Z)")
    micro = ord(micro_ch) - ord("A")
    return (macro - 1) * _FORTE_MICROS + micro


def forte_from_index(index: float) -> str:
    """linear step index -> ``"<macro><micro>"`` (half-up, clamps to 1A..10Z)."""
    idx = max(0, min(_FORTE_MAX_INDEX, math.floor(float(index) + 0.5)))
    macro = idx // _FORTE_MICROS + 1
    micro = idx % _FORTE_MICROS
    return f"{macro}{chr(ord('A') + micro)}"


# ── per-grinder setting <-> interpolation value ──────────────────────────────
def _anchors(grinder: str) -> tuple:
    g = GRINDERS[grinder]
    if g["kind"] == "forte":
        return tuple(forte_to_index(lbl) for lbl in g["labels"])
    return g["anchors"]


def _setting_to_value(grinder: str, setting) -> float:
    """A grinder setting -> the monotone numeric value used for interpolation."""
    g = GRINDERS[grinder]
    if g["kind"] == "forte":
        return float(forte_to_index(setting))
    return float(setting)


def _value_to_setting(grinder: str, value: float):
    """Interpolated numeric value -> the grinder's displayed setting."""
    g = GRINDERS[grinder]
    if g["kind"] == "forte":
        return forte_from_index(value)
    return _round_half_up(float(value), g["decimals"])


def _interp(x: float, xs: tuple, ys: tuple) -> tuple[float, bool]:
    """Piecewise-linear map x (on xs) -> y (on ys). xs strictly increasing.

    Outside [xs[0], xs[-1]] it linearly extrapolates the nearest end segment and
    returns ``in_range=False``.
    """
    n = len(xs)
    if x <= xs[0]:
        t = (x - xs[0]) / (xs[1] - xs[0])
        return ys[0] + t * (ys[1] - ys[0]), x >= xs[0]
    if x >= xs[-1]:
        t = (x - xs[-2]) / (xs[-1] - xs[-2])
        return ys[-2] + t * (ys[-1] - ys[-2]), x <= xs[-1]
    for i in range(n - 1):
        if xs[i] <= x <= xs[i + 1]:
            t = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + t * (ys[i + 1] - ys[i]), True
    return float(ys[-1]), True  # unreachable (x within span)


# ── public conversion API ────────────────────────────────────────────────────
def to_level(grinder: str, setting) -> tuple[float, bool]:
    """A grinder's setting -> fractional equivalence level (1..7), in_range."""
    _require(grinder)
    value = _setting_to_value(grinder, setting)
    return _interp(value, _anchors(grinder), tuple(float(l) for l in LEVELS))


def from_level(grinder: str, level: float) -> tuple[object, bool]:
    """Fractional equivalence level (1..7) -> a grinder's setting, in_range."""
    _require(grinder)
    value, ok = _interp(level, tuple(float(l) for l in LEVELS), _anchors(grinder))
    return _value_to_setting(grinder, value), ok


def convert(src: str, setting, dst: str) -> Conversion:
    """Convert a setting on grinder ``src`` to grinder ``dst`` via the level axis."""
    level, ok1 = to_level(src, setting)
    out, ok2 = from_level(dst, level)
    return Conversion(setting=out, level=round(level, 3), in_range=ok1 and ok2)


def to_zp6(grinder: str, setting) -> float:
    """A grinder's setting -> ZP6 dial (the model axis). Float."""
    if grinder == NATIVE:
        return round(float(setting), GRINDERS[NATIVE]["decimals"])
    return float(convert(grinder, setting, NATIVE).setting)


def from_zp6(zp6_dial: float, grinder: str) -> Conversion:
    """A model ZP6 dial -> a grinder's setting (for display)."""
    return convert(NATIVE, zp6_dial, grinder)


def format_dial(grinder: str, zp6_dial: float) -> str:
    """Display a model ZP6 dial in ``grinder`` units (``"~"`` prefix if extrapolated)."""
    if grinder == NATIVE:
        return _fmt(NATIVE, zp6_dial)
    conv = from_zp6(zp6_dial, grinder)
    body = conv.setting if GRINDERS[grinder]["kind"] == "forte" else _fmt(grinder, conv.setting)
    return f"{'~' if not conv.in_range else ''}{body}"


def _fmt(grinder: str, value) -> str:
    """Format a setting from the half-up *integer* ``m = floor(value*10**d+0.5)``
    so the string is derived without a second (rule-divergent) rounding — the
    front-end's ``fmtSetting`` mirrors this digit-for-digit."""
    dec = GRINDERS[grinder]["decimals"]
    m = math.floor(float(value) * (10 ** dec) + 0.5)
    if dec == 0:
        return str(m)
    s = str(m).rjust(dec + 1, "0")
    return f"{s[:-dec]}.{s[-dec:]}"


def supported() -> list[str]:
    """Grinder keys, native (zp6) first."""
    return [NATIVE] + [k for k in GRINDERS if k != NATIVE]


def table_payload() -> dict:
    """JSON-serialisable table for the front-end (single source of the numbers).

    The webapp injects this so the browser interpolates the *same* anchors —
    the data lives here only; JS mirrors the trivial linear interp.
    """
    return {
        "levels": list(LEVELS),
        "native": NATIVE,
        "forte_micros": _FORTE_MICROS,
        "grinders": {
            key: {
                "label": g["label"],
                "kind": g["kind"],
                "unit": g["unit"],
                "anchors": list(_anchors(key)),
                "decimals": g.get("decimals", 0),
                "labels": list(g["labels"]) if g["kind"] == "forte" else None,
            }
            for key, g in GRINDERS.items()
        },
    }


def _require(grinder: str) -> None:
    if grinder not in GRINDERS:
        raise KeyError(f"unknown grinder {grinder!r}; supported: {supported()}")
