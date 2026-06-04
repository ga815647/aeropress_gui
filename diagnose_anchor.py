"""Phase 10 Step 7 -- model diagnostics.

Validates the Phase 10 pipeline after an edit to constants / layer1 / sensory /
distance / ideal. Two layers, kept independently checkable (CLAUDE.md #5):

  Layer 1 (physics, models/layer1.py): the ONE plain-immersion calibration
    anchor -- Hoffman 98C/4.3/120s/11g/200ml -- must reproduce its measured
    TDS 1.23. EY sane; extraction monotone in temp/grind/time. April &
    Champion are NOT Layer-1 anchors (technique brews -- Step 4 section 8 #6).

  Layer 2 (sensory, models/sensory.py + distance.py + data/ideal.json): each
    roast's anchor_brew must round-trip to ~zero distance (ideal.json stays in
    sync with predict_attributes); the optimizer can reach each roast IDEAL;
    distance discriminates good << over-extract << under-extract; the tim
    feedback bracket ranks star4 < star3 < star2.

Exit code: 0 = all pass, 1 = a check failed (or the script raised). The
.claude/hooks/anchor_check.py hook keys on the exit code. Output is ASCII-only
so it survives any console / pipe encoding (cp950, UTF-8, ...).
"""
from __future__ import annotations

import sys

from models.distance import attribute_distance
from models.ideal import available_roasts, get_ideal_spec, roast_ideal
from models.layer1 import brew
from models.sensory import predict_attributes
from optimizer import optimize

# -- tolerances ---------------------------------------------------------------
HOFFMAN_TDS = 1.23           # measured (Hoffman "Brewing for Balance", El Tambo)
TDS_TOL = 0.05               # predicted TDS must land within this of measured
HOFFMAN_EY_BAND = (17.0, 23.0)
SELF_DIST_MAX = 0.002        # anchor_brew round-trip distance (rounding only)
# optimizer Top-1 distance ceiling per roast -- moderately_dark is a known
# placeholder gap (Step 5 section 5.1: E_MAX_ROAST_FACTOR makes its IDEAL
# unreachable; medium / light are well within reach).
OPT_DIST_MAX = {"light": 0.010, "medium_light": 0.005,
                "medium": 0.010, "moderately_dark": 0.025}

_results: list[tuple[str, bool, str]] = []


def _check(name: str, ok: bool, detail: str) -> None:
    _results.append((name, ok, detail))
    print(f"  [ {'OK  ' if ok else 'FAIL'} ]  {name}")
    print(f"             {detail}")


def _dist(roast, temp, dial, steep, dose, water_ml):
    """knobs -> Layer 1 -> Layer 2 -> distance to the roast IDEAL."""
    l1 = brew(roast, temp, dial, steep, dose, water_ml)
    attrs = predict_attributes(l1["tds"], l1["ey"], roast=roast, temp=temp, dial=dial)
    return attribute_distance(attrs, roast_ideal(roast)), l1


def check_layer1() -> None:
    print("-- Layer 1 -- physics calibration ------------------------------")

    # the single plain-immersion calibration anchor
    h = brew("medium_light", 98.0, 4.3, 120.0, 11.0, 200.0)
    _check(
        "Hoffman anchor TDS",
        abs(h["tds"] - HOFFMAN_TDS) <= TDS_TOL,
        f"predicted {h['tds']:.3f}% vs measured {HOFFMAN_TDS}% "
        f"(|diff|={abs(h['tds'] - HOFFMAN_TDS):.3f} <= {TDS_TOL})",
    )
    _check(
        "Hoffman anchor EY sane",
        HOFFMAN_EY_BAND[0] <= h["ey"] <= HOFFMAN_EY_BAND[1],
        f"predicted EY {h['ey']:.2f}% in {HOFFMAN_EY_BAND}",
    )

    # extraction rises with temp / fineness / time (pure exp() structure)
    cool_coarse_short = brew("medium_light", 90.0, 5.5, 60.0, 11.0, 200.0)
    hot_fine_long = brew("medium_light", 98.0, 3.5, 240.0, 11.0, 200.0)
    _check(
        "extraction monotone (temp/grind/time)",
        hot_fine_long["ey"] > cool_coarse_short["ey"],
        f"hot+fine+long EY {hot_fine_long['ey']:.2f}% > "
        f"cool+coarse+short EY {cool_coarse_short['ey']:.2f}%",
    )
    print()


def check_layer2_consistency() -> None:
    print("-- Layer 2 -- ideal.json vs predict_attributes consistency -----")
    for roast in available_roasts():
        ab = get_ideal_spec(roast)["anchor_brew"]
        pred = predict_attributes(ab["tds"], ab["ey"], roast=ab["roast"], dial=ab["dial"])
        d = attribute_distance(pred, roast_ideal(roast))
        _check(
            f"{roast} anchor_brew round-trips to IDEAL",
            d <= SELF_DIST_MAX,
            f"distance {d:.6f} <= {SELF_DIST_MAX} "
            f"(predict_attributes(anchor_brew) vs data/ideal.json)",
        )
    print()


def check_optimizer_reach() -> None:
    print("-- Layer 2 -- optimizer reaches each roast IDEAL ---------------")
    for roast in available_roasts():
        top = optimize(roast_code=roast, brewer_size="xl", top_n=1)[0]
        ceiling = OPT_DIST_MAX[roast]
        note = " (known placeholder gap)" if roast == "moderately_dark" else ""
        _check(
            f"{roast} optimizer Top-1 near IDEAL",
            top["distance"] <= ceiling,
            f"dist {top['distance']:.4f} <= {ceiling}{note}  "
            f"[dial {top['dial']} / {top['steep_sec']}s / {top['dose']}g]",
        )
    print()


def check_discrimination() -> None:
    print("-- Layer 2 -- distance discriminates good / over / under -------")
    # medium_light, XL 400 ml
    good, gl = _dist("medium_light", 95.0, 4.4, 150.0, 24.0, 400.0)
    over, ol = _dist("medium_light", 99.0, 3.0, 420.0, 28.0, 400.0)
    under, ul = _dist("medium_light", 93.0, 7.4, 30.0, 16.0, 400.0)
    _check(
        "good << over-extract << under-extract",
        good < over < under and good < 0.01 and under > 0.1,
        f"good {good:.4f} (TDS {gl['tds']:.2f}) < "
        f"over {over:.4f} (TDS {ol['tds']:.2f}) < "
        f"under {under:.4f} (TDS {ul['tds']:.2f})",
    )

    # light good / over / under -- the user's star-4 archetype is the reference
    # good (light IDEAL re-anchored 2026-06-04 to the 2026-05-27 star-4 cup
    # 98C / 4.8 / 26g / 90s, chosen after recomputing every logged cup on one
    # model scale; the Hoffman 4.3/120/23 it replaced was a star-2 cup).
    good_l, gl_l = _dist("light", 98.0, 4.8, 90.0, 26.0, 400.0)
    over_l, ol_l = _dist("light", 99.0, 3.0, 360.0, 28.0, 400.0)
    under_l, ul_l = _dist("light", 93.0, 7.0, 30.0, 16.0, 400.0)
    _check(
        "light good << over-extract << under-extract",
        good_l < over_l < under_l and good_l < 0.01 and under_l > 0.1,
        f"good {good_l:.4f} (TDS {gl_l['tds']:.2f}) < "
        f"over {over_l:.4f} (TDS {ol_l['tds']:.2f}) < "
        f"under {under_l:.4f} (TDS {ul_l['tds']:.2f})",
    )
    print()


def main() -> int:
    print("=" * 64)
    print(" Phase 10 model diagnostics -- Layer 1 physics + Layer 2 sensory")
    print("=" * 64)
    print()
    try:
        check_layer1()
        check_layer2_consistency()
        check_optimizer_reach()
        check_discrimination()
    except Exception as exc:  # a crash is itself a failure the hook must catch
        print(f"\n[ FAIL ]  diagnostics raised: {exc!r}")
        return 1

    print("=" * 64)
    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    for name, ok, _ in _results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    all_ok = passed == total
    print()
    print(f"{'[ ALL PASS ]' if all_ok else '[ FAIL ]'}  {passed}/{total} checks")
    print("=" * 64)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
