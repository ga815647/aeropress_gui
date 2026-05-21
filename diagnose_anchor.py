"""Phase 8 — Two-layer anchor validation.

Layer 1 (physics): each anchor's predicted EY / TDS / compound profile must
match measured values (or sensible bands). Independent of any label / scoring.

Layer 2 (sensory): each anchor scores highly on its bullseye label and lower
on labels it doesn't belong to; bad anchors (Under / Over) score low on ALL
labels. Uses unified `flavor_score(..., label=...)`.

See CLAUDE.md principle #5. Replaces the pre-Phase-8 mixed-assertion version.
"""
from __future__ import annotations

import sys

import constants
import runtime
from models.compounds import predict_compounds
from models.ey_model import calc_ey
from models.labels import label_names
from models.scoring import flavor_score, score_to_display
from models.tds_model import calc_press_time, calc_tds


# TDS-anchor 校準容忍（2026-05-21）：有實測 TDS 的錨點，predicted 必須落在
# measured ± TDS_ANCHOR_TOL 之內。取代舊的「繞 predicted 自設 band」自證式檢查
# （舊 band 不含 measured 值 → 只驗模型重現自己，沒驗對上現實）。
TDS_ANCHOR_TOL = 0.05


# ── anchor recipes (Layer 1 inputs + Layer 2 bullseye assignments) ──────────
ANCHORS = {
    "Hoffman": {
        "label": "balanced",
        "roast": "medium_light", "brewer": "standard",
        "temp": 98.0, "dial": 4.3, "dose": 11.0, "steep": 120.0, "water": 200.0,
        "t_env": 20.0,
        "measured_tds": 1.23,            # Hoffman article（使用者選定：忠於唯一實測值）
        "predicted_tds_band": (1.25, 1.45),   # 未用（measured 走 ±TOL）；留作歷史紀錄
        "predicted_ey_band": (17.0, 22.0),    # 2026-05-21 TDS-anchor 校準後 EY≈20.0%（sanity band）
        "score_min": 80.0,
    },
    "April": {
        "label": "acid-forward",
        "roast": "medium_light", "brewer": "standard",
        "temp": 85.0, "dial": 5.0, "dose": 13.0, "steep": 90.0, "water": 200.0,
        "press_s": 30.0,
        "extra_ey": {"pre_pour_ml": 50.0, "pre_pour_sec": 30.0,
                     "partial_seal_sec": 25.0, "partial_seal_water_ml": 50.0},
        "extra_cpd": {"partial_seal_sec": 25.0, "partial_seal_water_ml": 50.0},
        "measured_tds": 1.17,
        "predicted_tds_band": (1.05, 1.30),
        "predicted_ey_band": (14.0, 18.0),
        "score_min": 60.0,
    },
    "Championship": {
        "label": "sweet-body",
        "roast": "medium_light", "brewer": "standard",
        "temp": 80.0, "dial": 5.0, "dose": 17.0, "steep": 100.0, "water": 200.0,
        "press_s": 20.0,
        "extra_ey": {"inverted": True, "n_swirls": 2},
        "extra_cpd": {"inverted": True, "n_swirls": 2},
        "measured_tds": 1.56,
        "predicted_tds_band": (1.40, 1.70),
        "predicted_ey_band": (13.0, 18.0),
        "score_min": 55.0,
    },
    "Hedrick": {
        "label": "coarse-modern",
        "roast": "medium_light", "brewer": "standard",
        "temp": 95.0, "dial": 6.0, "dose": 14.0, "steep": 240.0, "water": 200.0,
        "measured_tds": None,            # no published TDS
        "predicted_tds_band": (1.20, 1.45),   # 無實測 → 維持寬 sanity band
        "predicted_ey_band": (13.0, 18.0),    # 2026-05-21 TDS-anchor 校準後 EY≈15.7%（sanity band）
        "score_min": 55.0,
    },
}

BAD_RECIPES = {
    "Under-extraction": {
        "roast": "medium_light", "brewer": "standard",
        "temp": 93.0, "dial": 6.5, "dose": 11.0, "steep": 60.0, "water": 200.0,
        "ey_must": ("<", 15.0),
        "tds_must": ("<", 0.85),
        "score_max": 40.0,
    },
    "Over-extraction": {
        "roast": "medium_light", "brewer": "standard",
        "temp": 99.0, "dial": 3.5, "dose": 11.0, "steep": 240.0, "water": 200.0,
        "ey_must": (">", 21.0),          # 2026-05-21：base_ey 校準後整體 EY 下移 ~2.8pp，
                                         # over-extract EY≈22% vs Hoffman 20%（相對過萃 +2pp 不變）
        "tds_must": (">", 1.20),
        "score_max": 50.0,
    },
}


def _fmt(ok: bool) -> str:
    return "OK  " if ok else "FAIL"


def _brew(*, roast, temp, dial, dose, steep, water, brewer, press_s=None,
          extra_ey=None, extra_cpd=None, t_env=20.0):
    runtime.apply_environment_settings(t_env, 0)
    area = constants.BREWER_PRESETS[brewer]["area_cm2"]
    if press_s is None:
        press_s = calc_press_time(dose, dial, steep, brewer_size=brewer)
    press_eq = min(press_s, constants.CHANNELING_PRESS_THRESHOLD) * constants.PRESS_EQUIV_FRACTION
    pour_offset = (water / constants.POUR_RATE) / 2.0

    ey = calc_ey(
        roast_code=roast, temp_initial=temp, dial=dial,
        steep_sec=steep, dose=dose, water_ml=water,
        water_gh=50, press_equiv=press_eq, pour_offset=pour_offset,
        area_cm2=area,
        **(extra_ey or {}),
    )
    tds = calc_tds(roast, dose, ey, dial, water_ml=water)
    compounds = predict_compounds(
        roast_code=roast, temp=temp, dial=dial,
        steep_sec=steep, ey=ey,
        water_gh=50, water_mg_frac=0.40,
        press_equiv=press_eq, pour_offset=pour_offset,
        water_ml=water, dose=dose, press_sec=press_s, area_cm2=area,
        **(extra_cpd or {}),
    )
    return ey, tds, compounds


def _score(compounds, tds, ey, *, roast, temp, dial, steep, label):
    raw = flavor_score(
        compounds, tds, roast, label,
        water_kh=30, water_gh=50,
        t_slurry=temp - 2.0, temp_initial=temp,
        ey=ey, steep_sec=steep, dial=dial,
    )
    # 不在這裡乘 dial_factor（diagnose 看純 scoring；optimizer 自己加 dial_prefer 偏好）
    return score_to_display(raw)


def check_anchor(name: str, verbose: bool = True) -> bool:
    spec = ANCHORS[name]
    ey, tds, compounds = _brew(
        roast=spec["roast"], temp=spec["temp"], dial=spec["dial"],
        dose=spec["dose"], steep=spec["steep"], water=spec["water"],
        brewer=spec["brewer"],
        press_s=spec.get("press_s"),
        extra_ey=spec.get("extra_ey"), extra_cpd=spec.get("extra_cpd"),
    )
    score_on_label = _score(compounds, tds, ey,
                            roast=spec["roast"], temp=spec["temp"], dial=spec["dial"],
                            steep=spec["steep"], label=spec["label"])

    cross_scores = {}
    for other in label_names():
        if other == spec["label"]:
            continue
        cross_scores[other] = _score(compounds, tds, ey,
                                     roast=spec["roast"], temp=spec["temp"],
                                     dial=spec["dial"], steep=spec["steep"],
                                     label=other)

    ey_lo, ey_hi = spec["predicted_ey_band"]
    measured = spec["measured_tds"]
    if measured is not None:
        # TDS 是 Layer 1 硬錨點：predicted 必須對上 measured ± TOL
        tds_ok = abs(tds - measured) <= TDS_ANCHOR_TOL
    else:
        # 無實測 → 退回寬 sanity band
        tds_lo, tds_hi = spec["predicted_tds_band"]
        tds_ok = tds_lo <= tds <= tds_hi
    ey_ok = ey_lo <= ey <= ey_hi
    score_ok = score_on_label >= spec["score_min"]

    if verbose:
        print(f"── {name} → label '{spec['label']}' ──────────────────────")
        print(f"  recipe: dial={spec['dial']} dose={spec['dose']}g "
              f"temp={spec['temp']}°C steep={spec['steep']}s ({spec['brewer']})")
        print(f"  predicted EY={ey:.2f}%  TDS={tds:.3f}%  "
              + (f"(measured TDS={spec['measured_tds']:.2f})" if spec["measured_tds"] else "(no measurement)"))
        cstr = "  ".join(f"{k}={compounds[k]:.4f}" for k in constants.KEYS)
        print(f"  compounds: {cstr}")
        print(f"  score on '{spec['label']}': {score_on_label}")
        cs = "  ".join(f"{lbl}={sc}" for lbl, sc in cross_scores.items())
        print(f"  cross-label: {cs}")
        if measured is not None:
            print(f"  {_fmt(tds_ok)}  TDS {tds:.3f}% vs measured {measured:.2f}% "
                  f"(|diff|={abs(tds - measured):.3f} <= {TDS_ANCHOR_TOL})")
        else:
            print(f"  {_fmt(tds_ok)}  TDS {tds:.3f}% in [{tds_lo}, {tds_hi}] (no measurement)")
        print(f"  {_fmt(ey_ok)}  EY {ey:.2f}% in [{ey_lo}, {ey_hi}]")
        print(f"  {_fmt(score_ok)}  score {score_on_label} >= {spec['score_min']}")
        print()
    return tds_ok and ey_ok and score_ok


def check_bad(name: str, verbose: bool = True) -> bool:
    spec = BAD_RECIPES[name]
    ey, tds, compounds = _brew(
        roast=spec["roast"], temp=spec["temp"], dial=spec["dial"],
        dose=spec["dose"], steep=spec["steep"], water=spec["water"],
        brewer=spec["brewer"],
    )
    scores = {}
    for lbl in label_names():
        scores[lbl] = _score(compounds, tds, ey,
                             roast=spec["roast"], temp=spec["temp"],
                             dial=spec["dial"], steep=spec["steep"], label=lbl)
    max_score = max(scores.values())

    op_ey, val_ey = spec["ey_must"]
    op_tds, val_tds = spec["tds_must"]
    ey_ok = (ey < val_ey) if op_ey == "<" else (ey > val_ey)
    tds_ok = (tds < val_tds) if op_tds == "<" else (tds > val_tds)
    score_ok = max_score < spec["score_max"]

    if verbose:
        print(f"── {name} (must score low across ALL labels) ────────────────")
        print(f"  recipe: dial={spec['dial']} dose={spec['dose']}g "
              f"temp={spec['temp']}°C steep={spec['steep']}s")
        print(f"  predicted EY={ey:.2f}%  TDS={tds:.3f}%")
        cs = "  ".join(f"{lbl}={sc}" for lbl, sc in scores.items())
        print(f"  scores: {cs}  (max={max_score})")
        print(f"  {_fmt(ey_ok)}  EY {ey:.2f}% {op_ey} {val_ey}")
        print(f"  {_fmt(tds_ok)}  TDS {tds:.3f}% {op_tds} {val_tds}")
        print(f"  {_fmt(score_ok)}  max score {max_score} < {spec['score_max']} (no label rewards this brew)")
        print()
    return ey_ok and tds_ok and score_ok


def main() -> int:
    print("=" * 68)
    print(" Phase 8 anchor diagnostics — Layer 1 physics + Layer 2 label scoring")
    print("=" * 68)
    print()

    results = {}
    for name in ANCHORS:
        results[name] = check_anchor(name)
    for name in BAD_RECIPES:
        results[name] = check_bad(name)

    print("=" * 68)
    for name, ok in results.items():
        print(f"  {name:20s}  {'PASS' if ok else 'FAIL'}")
    all_ok = all(results.values())
    print(f"\n{'[ ALL PASS ]' if all_ok else '[ FAIL — adjust labels.json / constants.py ]'}")
    print("=" * 68)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
