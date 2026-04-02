"""
錨點驗證腳本（三食譜：平衡 / 酸質 / 甜感醇厚）
每次口感矯正（修改 constants.py）後執行，確認模型未偏離實測基準。

錨點一（Hoffman 平衡）：
  研磨：4 EK43 / 450-600um -> ZP6 dial ~4.3
  水溫：208°F = 97.8°C；浸泡：120s；劑量：11g / 200ml
  TDS：1.23%（實測）；門檻：score >= 84

錨點二（April Coffee 酸質）：
  研磨：6.75 EK43 / 810um -> ZP6 dial ~6.0
  水溫：185°F = 85°C；浸泡：90s；劑量：13g / 200ml；半密封 25s
  TDS：1.17%（實測）；門檻：score >= 82（原文最熱情：high-quality acidity / mouthwatering）

錨點三（2021 世界冠軍 甜感醇厚）：
  研磨：6.75 EK43 / 810um -> ZP6 dial ~6.0
  水溫：176°F = 80°C；浸泡：100s；劑量：17g / 200ml；倒置法；下壓 20s
  TDS：1.56%（實測）；門檻：score >= 78（冠軍食譜，模型最不確定區間）
"""

import math
import sys

import constants
import runtime
from models.ey_model import calc_ey
from models.compounds import predict_compounds
from models.tds_model import calc_tds
from optimizer import optimize

# ── 錨點二：April Coffee 酸質 ideal profile ────────────────────────────────
ACIDITY_IDEAL = {
    "AC": 0.22, "SW": 0.35, "PS": 0.25,
    "CA": 0.08, "CGA": 0.06, "MEL": 0.04,
}
ACIDITY_TDS_PREFER = 1.17

# ── 錨點三：2021 世界冠軍 甜感醇厚 ideal profile ───────────────────────────
SWEETNESS_IDEAL = {
    "AC": 0.09, "SW": 0.40, "PS": 0.38,
    "CA": 0.07, "CGA": 0.04, "MEL": 0.02,
}
SWEETNESS_TDS_PREFER = 1.56

# ── 錨點定義 ──────────────────────────────────────────────────────────────────
ANCHOR = {
    "roast":        "light",
    "brewer":       "standard",       # Hoffman 原版：11g / 200ml
    "water_gh":     50,
    "water_kh":     30,
    "water_mg_frac": 0.40,
    "t_env":        20.0,             # 錨點專用室溫（不改全域預設值 25°C）
    "fixed_dose":   11.0,             # Hoffman 原版劑量
    "temp_range":   (98, 99),         # ~97.8°C / 208°F
    "fixed_steep":  120,              # 注水→swirl 前 120s
    # Top 3 整體驗證範圍（standard 11g/200ml）
    "tds_lo":     1.05,
    "tds_hi":     1.36,
    "ey_min":     16.0,   # 防欠萃底線
    "dial_lo":    3.8,
    "dial_hi":    4.8,
    "score_min":  96.0,   # raw×100 口徑（不走 CDF）；與 April/Championship 同標準
    # Hoffman 浸泡特定驗證
    "steep_ok":   {120},
    "hoffman_ey_lo":  18.0,
    "hoffman_ey_hi":  24.0,   # standard 11g/120s 部分組合可達 23%，放寬上限
}


def _fmt(ok: bool) -> str:
    return "OK  " if ok else "FAIL"


def run_anchor_check(verbose: bool = True) -> bool:
    _t_env_orig = constants.T_ENV
    runtime.apply_environment_settings(ANCHOR["t_env"], 0)
    try:
        results = optimize(
            ANCHOR["roast"],
            brewer_size=ANCHOR["brewer"],
            water_gh=ANCHOR["water_gh"],
            water_kh=ANCHOR["water_kh"],
            water_mg_frac=ANCHOR["water_mg_frac"],
            top_n=10,
            fixed_dose=ANCHOR["fixed_dose"],
            temp_range=ANCHOR["temp_range"],
            fixed_steep=ANCHOR["fixed_steep"],
        )
    finally:
        runtime.apply_environment_settings(_t_env_orig, 0)

    if not results:
        print("FAIL: optimizer 返回空結果")
        return False

    top3 = results[:3]
    top10 = results[:10]

    # 1. 分數閾值（用 _score_raw × 100，不走 CDF，與 April/Championship 計量口徑一致）
    top1_score = round(top3[0]["_score_raw"] * 100, 1)
    score_ok = top1_score >= ANCHOR["score_min"]

    # 2. TDS 範圍（Top 3 都必須在範圍內）
    tds_ok = all(ANCHOR["tds_lo"] <= r["tds"] <= ANCHOR["tds_hi"] for r in top3)

    # 3. EY 最低底線（Top 3 不得低於 16%，防止模型推薦欠萃配方）
    ey_ok = all(r["ey"] >= ANCHOR["ey_min"] for r in top3)

    # 4. Dial 範圍（Top 3）
    dial_ok = all(ANCHOR["dial_lo"] <= r["dial"] <= ANCHOR["dial_hi"] for r in top3)

    # 5. Hoffman steep（120s 必須在 Top 10 內，且 EY 需在合理範圍）
    top10_steeps = {r["steep_sec"] for r in top10}
    hoffman_results = [r for r in top10 if r["steep_sec"] in ANCHOR["steep_ok"]]
    steep_ok = bool(hoffman_results)
    hoffman_ey_ok = all(
        ANCHOR["hoffman_ey_lo"] <= r["ey"] <= ANCHOR["hoffman_ey_hi"]
        for r in hoffman_results
    ) if hoffman_results else False

    all_pass = score_ok and tds_ok and ey_ok and dial_ok and steep_ok and hoffman_ey_ok

    if verbose:
        print("=" * 60)
        print("Hoffman anchor check (light / standard / 11g / 98-99°C / steep=120s / GH50 KH30 / T_env=20)")
        print("=" * 60)
        print("\nTop 3:")
        for i, r in enumerate(top3):
            print(f"  #{i+1}: dial={r['dial']}, steep={r['steep_sec']}s, "
                  f"temp={r['temp']}C, TDS={r['tds']:.3f}%, "
                  f"EY={r['ey']:.1f}%, score={r['score']}")

        hoffman_steep_found = sorted(top10_steeps & ANCHOR["steep_ok"])
        print(f"\nHoffman steep ({sorted(ANCHOR['steep_ok'])}s) in Top 10: "
              f"{hoffman_steep_found if hoffman_steep_found else 'NONE'}")
        if hoffman_results:
            for r in hoffman_results:
                print(f"  steep={r['steep_sec']}s: EY={r['ey']:.1f}%, TDS={r['tds']:.3f}%")

        print(f"\nChecks:")
        print(f"  {_fmt(score_ok)}  Top1 score {top1_score} >= {ANCHOR['score_min']}")
        print(f"  {_fmt(tds_ok)}  Top3 TDS in [{ANCHOR['tds_lo']}, {ANCHOR['tds_hi']}]%")
        print(f"  {_fmt(ey_ok)}  Top3 EY >= {ANCHOR['ey_min']}% (no under-extraction)")
        print(f"  {_fmt(dial_ok)}  Top3 dial in [{ANCHOR['dial_lo']}, {ANCHOR['dial_hi']}]")
        print(f"  {_fmt(steep_ok)}  Hoffman steep in Top 10")
        print(f"  {_fmt(hoffman_ey_ok)}  Hoffman steep EY in [{ANCHOR['hoffman_ey_lo']}, {ANCHOR['hoffman_ey_hi']}]%")

        print(f"\n{'[ ALL PASS ]' if all_pass else '[ FAIL - check constants.py ]'}")
        print("=" * 60)

    return all_pass


def _anchor_cosine_score(compounds: dict, ideal: dict, tds: float, tds_prefer: float) -> float:
    """加權 cosine 相似度 × TDS Gaussian → 0–100 分。
    供 April / Championship 錨點使用（不依賴 scoring.py）。
    """
    keys = constants.KEYS
    actual_sum = sum(compounds[k] for k in keys)
    ideal_sum  = sum(ideal[k]     for k in keys)
    if actual_sum <= 0 or ideal_sum <= 0:
        return 0.0
    a = [compounds[k] / actual_sum for k in keys]
    b = [ideal[k]     / ideal_sum  for k in keys]
    dot   = sum(a[i] * b[i] for i in range(len(keys)))
    mag_a = math.sqrt(sum(x ** 2 for x in a))
    mag_b = math.sqrt(sum(x ** 2 for x in b))
    cos_sim = dot / (mag_a * mag_b) if (mag_a > 0 and mag_b > 0) else 0.0
    tds_factor = math.exp(-0.5 * ((tds - tds_prefer) / 0.15) ** 2)
    return round(cos_sim * tds_factor * 100, 1)


def run_april_anchor(verbose: bool = True) -> bool:
    """April Coffee Roasters 酸質錨點（固定參數，不跑 optimizer）。
    85°C / dial ~5.0 (EK43 6.75=810um; ZP6 mapping estimated) / 13g / 90s / 半密封 25s / 標準壓 30s
    """
    roast   = "light"
    temp    = 85.0
    dial    = 5.0
    dose    = 13.0
    steep   = 90.0
    water   = 200.0
    area    = constants.BREWER_PRESETS["standard"]["area_cm2"]
    press_s = 30.0
    press_equiv = press_s * constants.PRESS_EQUIV_FRACTION

    ey = calc_ey(
        roast_code="light", temp_initial=temp, dial=dial,
        steep_sec=steep, dose=dose, water_ml=water,
        area_cm2=area, water_gh=50,
        press_equiv=press_equiv,
        pre_pour_ml=50.0, pre_pour_sec=30.0,
        partial_seal_sec=25.0, partial_seal_water_ml=50.0,
    )
    tds = calc_tds(roast, dose, ey, dial, water_ml=water)
    compounds = predict_compounds(
        roast_code=roast, temp=temp, dial=dial,
        steep_sec=steep, ey=ey,
        water_ml=water, area_cm2=area,
        dose=dose, press_sec=press_s,
        press_equiv=press_equiv,
        partial_seal_sec=25.0, partial_seal_water_ml=50.0,
    )

    score = _anchor_cosine_score(compounds, ACIDITY_IDEAL, tds, ACIDITY_TDS_PREFER)

    tds_ok    = abs(tds - 1.17) <= 0.20
    ac_ok     = compounds["AC"] > compounds["CGA"] and compounds["AC"] > compounds["MEL"]
    score_ok  = score >= 82.0

    all_pass = tds_ok and ac_ok and score_ok

    if verbose:
        print("=" * 60)
        print("April anchor check (light / standard / 13g / 85C / 90s / dial ~5.0 / partial-seal 25s)")
        print("=" * 60)
        cstr = "  ".join(f"{k}={v:.4f}" for k, v in compounds.items())
        print(f"  EY={ey:.1f}%  TDS={tds:.3f}%  score={score}")
        print(f"  compounds: {cstr}")
        print(f"\nChecks:")
        print(f"  {_fmt(tds_ok)}  |TDS - 1.17| = {abs(tds-1.17):.3f} <= 0.20")
        print(f"  {_fmt(ac_ok)}  AC ({compounds['AC']:.4f}) > CGA ({compounds['CGA']:.4f}) & MEL ({compounds['MEL']:.4f})")
        print(f"  {_fmt(score_ok)}  score {score} >= 82.0 (vs ACIDITY_IDEAL)")
        print(f"\n{'[ ALL PASS ]' if all_pass else '[ FAIL - check constants.py ]'}")
        print("=" * 60)

    return all_pass


def run_championship_anchor(verbose: bool = True) -> bool:
    """2021 世界冠軍甜感醇厚錨點（固定參數，不跑 optimizer）。
    80°C / dial ~5.0 (EK43 6.75=810um; ZP6 mapping estimated) / 17g / 100s / 倒置法 / 下壓 20s / 攪拌 2 次
    """
    roast   = "light"
    temp    = 80.0
    dial    = 5.0
    dose    = 17.0
    steep   = 100.0
    water   = 200.0
    area    = constants.BREWER_PRESETS["standard"]["area_cm2"]
    press_s = 20.0
    press_equiv = press_s * constants.PRESS_EQUIV_FRACTION

    ey = calc_ey(
        roast_code="light", temp_initial=temp, dial=dial,
        steep_sec=steep, dose=dose, water_ml=water,
        area_cm2=area, water_gh=50,
        press_equiv=press_equiv,
        inverted=True, n_swirls=2,
    )
    tds = calc_tds(roast, dose, ey, dial, water_ml=water)
    compounds = predict_compounds(
        roast_code=roast, temp=temp, dial=dial,
        steep_sec=steep, ey=ey,
        water_ml=water, area_cm2=area,
        dose=dose, press_sec=press_s,
        press_equiv=press_equiv,
        inverted=True, n_swirls=2,
    )

    score = _anchor_cosine_score(compounds, SWEETNESS_IDEAL, tds, SWEETNESS_TDS_PREFER)

    tds_ok       = abs(tds - 1.56) <= 0.25
    sweet_ok     = compounds["SW"] > compounds["MEL"] and compounds["SW"] > compounds["CGA"]
    ps_sw_ok     = (compounds["PS"] + compounds["SW"]) >= 0.70
    score_ok     = score >= 78.0

    all_pass = tds_ok and sweet_ok and ps_sw_ok and score_ok

    if verbose:
        print("=" * 60)
        print("Championship anchor check (light / standard / 17g / 80C / 100s / dial ~5.0 / inverted / press 20s)")
        print("=" * 60)
        cstr = "  ".join(f"{k}={v:.4f}" for k, v in compounds.items())
        print(f"  EY={ey:.1f}%  TDS={tds:.3f}%  score={score}")
        print(f"  compounds: {cstr}")
        print(f"\nChecks:")
        print(f"  {_fmt(tds_ok)}  |TDS - 1.56| = {abs(tds-1.56):.3f} <= 0.25")
        print(f"  {_fmt(sweet_ok)}  SW ({compounds['SW']:.4f}) > MEL ({compounds['MEL']:.4f}) & CGA ({compounds['CGA']:.4f})")
        ps_sw = compounds["PS"] + compounds["SW"]
        print(f"  {_fmt(ps_sw_ok)}  PS+SW = {ps_sw:.4f} >= 0.70")
        print(f"  {_fmt(score_ok)}  score {score} >= 78.0 (vs SWEETNESS_IDEAL)")
        print(f"\n{'[ ALL PASS ]' if all_pass else '[ FAIL - check constants.py ]'}")
        print("=" * 60)

    return all_pass


if __name__ == "__main__":
    ok_hoffman      = run_anchor_check(verbose=True)
    print()
    ok_april        = run_april_anchor(verbose=True)
    print()
    ok_championship = run_championship_anchor(verbose=True)

    all_ok = ok_hoffman and ok_april and ok_championship
    print()
    print("=" * 60)
    print(f"  Hoffman:      {'PASS' if ok_hoffman else 'FAIL'}")
    print(f"  April:        {'PASS' if ok_april else 'FAIL'}")
    print(f"  Championship: {'PASS' if ok_championship else 'FAIL'}")
    print(f"\n{'[ ALL PASS ]' if all_ok else '[ FAIL - check constants.py ]'}")
    print("=" * 60)
    sys.exit(0 if all_ok else 1)
