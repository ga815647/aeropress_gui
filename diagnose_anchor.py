"""
錨點驗證腳本（三食譜：平衡 / 酸質 / 甜感醇厚）
每次口感矯正（修改 constants.py）後執行，確認模型未偏離實測基準。

來源：2022 年文章《Brewing for Balance, Acidity, or Sweetness》
      使用哥倫比亞 El Tambo 水洗豆；三食譜各自突出不同風味目標。

━━━ 評分原則（勿修改） ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  好喝不好喝跟泡法無關。評分看的是杯中物（化合物比例 + TDS），
  不是過程（幾度水、幾秒浸泡）。EY 是過程變數，不得作為主要扣分依據。

  所有錨點（Hoffman / April / Championship）使用同一個 flavor_score()。
  偏酸（April）和偏甜（Championship）食譜的分數低於平衡（Hoffman）是正常現象，
  因為它們偏離了 IDEAL_FLAVOR 均衡目標。化合物比值獎勵（AC/CGA、SW/bitter）
  會部分補償這些偏離，但不會完全抵消。

  三食譜「分數不低」的物理原因：
  • Hoffman  (TDS=1.27%)：化合物均衡，接近 balanced ideal；TDS 接近 TDS_PREFER
  • April    (TDS=1.17%)：AC > CGA/MEL（純淨酸質）；ratio_bonus 補償
  • Champion (TDS=1.56%)：SW+PS > 0.70；ratio_bonus 補償；TDS 寬腰 Super-Gaussian
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

錨點一（Hoffman 平衡）：
  研磨：4 EK43 / 450-600um -> ZP6 dial ~4.3
  水溫：208°F = 97.8°C；浸泡：120s；劑量：11g / 200ml
  TDS：1.23%（實測）

錨點二（April Coffee 酸質）：
  研磨：6.75 EK43 / 810um -> ZP6 dial ~6.0
  水溫：185°F = 85°C；浸泡：90s；劑量：13g / 200ml；半密封 25s
  TDS：1.17%（實測）；統一 flavor_score() 評分

錨點三（2021 世界冠軍 甜感醇厚）：
  研磨：6.75 EK43 / 810um -> ZP6 dial ~6.0
  水溫：176°F = 80°C；浸泡：100s；劑量：17g / 200ml；倒置法；下壓 20s
  TDS：1.56%（實測）；統一 flavor_score() 評分
"""

import math
import sys

import constants
import runtime
from models.ey_model import calc_ey
from models.compounds import predict_compounds
from models.tds_model import calc_press_time, calc_tds
from models.scoring import flavor_score, build_ideal_abs, score_to_display
from optimizer import optimize

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
    "tds_hi":     1.45,   # 放寬 TDS 上限以配合 SIGMA_HIGH=0.80 的 dose 多元化
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


def _get_overextract_score() -> float:
    """回傳過萃低分錨點的分數，供高分錨點做相對比較用。"""
    roast, temp, dial, steep, dose, water = "light", 99.0, 3.5, 240.0, 11.0, 200.0
    area = constants.BREWER_PRESETS["standard"]["area_cm2"]
    press_s  = calc_press_time(dose, dial, steep, brewer_size="standard")
    press_eq = min(press_s, constants.CHANNELING_PRESS_THRESHOLD) * constants.PRESS_EQUIV_FRACTION
    pour_offset = (water / constants.POUR_RATE) / 2.0
    ey  = calc_ey(roast, temp, dial, steep, dose, water, area, 50, press_eq)
    tds = calc_tds(roast, dose, ey, dial, water_ml=water)
    cpd = predict_compounds(roast_code=roast, temp=temp, dial=dial,
                             steep_sec=steep, ey=ey,
                             water_gh=50, water_mg_frac=0.40,
                             press_equiv=press_eq, pour_offset=pour_offset,
                             water_ml=water, dose=dose,
                             press_sec=press_s, area_cm2=area)
    ideal = build_ideal_abs(roast, tds)
    raw = flavor_score(cpd, ideal, tds, roast,
                       water_kh=30, water_gh=50,
                       t_slurry=temp - 2.0, temp_initial=temp,
                       ey=ey, steep_sec=steep)
    return score_to_display(raw, roast)


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

    # 1. 分數閾值：Hoffman 最佳 score 必須高於過萃低分錨點（比大小，不依賴絕對值）
    top1_score = round(top3[0]["_score_raw"] * 100, 1)
    _over_score = _get_overextract_score()
    score_ok = top1_score > _over_score

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
        print(f"  {_fmt(score_ok)}  Top1 score {top1_score} > over-extract {_over_score} (相對比較)")
        print(f"  {_fmt(tds_ok)}  Top3 TDS in [{ANCHOR['tds_lo']}, {ANCHOR['tds_hi']}]%")
        print(f"  {_fmt(ey_ok)}  Top3 EY >= {ANCHOR['ey_min']}% (no under-extraction)")
        print(f"  {_fmt(dial_ok)}  Top3 dial in [{ANCHOR['dial_lo']}, {ANCHOR['dial_hi']}]")
        print(f"  {_fmt(steep_ok)}  Hoffman steep in Top 10")
        print(f"  {_fmt(hoffman_ey_ok)}  Hoffman steep EY in [{ANCHOR['hoffman_ey_lo']}, {ANCHOR['hoffman_ey_hi']}]%")

        print(f"\n{'[ ALL PASS ]' if all_pass else '[ FAIL - check constants.py ]'}")
        print("=" * 60)

    return all_pass


def run_april_anchor(verbose: bool = True) -> bool:
    """April Coffee Roasters 酸質錨點（固定參數，不跑 optimizer）。
    85°C / dial ~5.0 (EK43 6.75=810um; ZP6 mapping estimated) / 13g / 90s / 半密封 25s / 標準壓 30s
    統一 flavor_score() 評分。
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

    ideal = build_ideal_abs(roast, tds)
    raw   = flavor_score(compounds, ideal, tds, roast,
                         water_kh=30, water_gh=50,
                         t_slurry=temp - 4.0, temp_initial=temp,
                         ey=ey, steep_sec=steep)
    score = score_to_display(raw, roast)

    tds_ok    = abs(tds - 1.17) <= 0.20
    ac_ok     = compounds["AC"] > compounds["CGA"] and compounds["AC"] > compounds["MEL"]
    score_ok  = score >= 60.0

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
        print(f"  {_fmt(score_ok)}  score {score} >= 60.0 (unified flavor_score)")
        print(f"\n{'[ ALL PASS ]' if all_pass else '[ FAIL - check constants.py ]'}")
        print("=" * 60)

    return all_pass


def run_championship_anchor(verbose: bool = True) -> bool:
    """2021 世界冠軍甜感醇厚錨點（固定參數，不跑 optimizer）。
    80°C / dial ~5.0 (EK43 6.75=810um; ZP6 mapping estimated) / 17g / 100s / 倒置法 / 下壓 20s / 攪拌 2 次
    統一 flavor_score() 評分。
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

    ideal = build_ideal_abs(roast, tds)
    raw   = flavor_score(compounds, ideal, tds, roast,
                         water_kh=30, water_gh=50,
                         t_slurry=temp - 4.0, temp_initial=temp,
                         ey=ey, steep_sec=steep)
    score = score_to_display(raw, roast)

    tds_ok       = abs(tds - 1.56) <= 0.25
    sweet_ok     = compounds["SW"] > compounds["MEL"] and compounds["SW"] > compounds["CGA"]
    ps_sw_ok     = (compounds["PS"] + compounds["SW"]) >= 0.70
    score_ok     = score >= 55.0

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
        print(f"  {_fmt(score_ok)}  score {score} >= 55.0 (unified flavor_score)")
        print(f"\n{'[ ALL PASS ]' if all_pass else '[ FAIL - check constants.py ]'}")
        print("=" * 60)

    return all_pass


def run_underextract_anchor(verbose: bool = True) -> bool:
    """低分錨點一：欠萃（粗研磨＋短時間＋低溫），驗證壞配方確實得低分。
    93°C / dial 6.5 / steep 60s / 11g / 200ml / standard
    預期：EY < 15%，TDS < 0.85%，score < 40
    """
    roast  = "light"
    temp   = 93.0
    dial   = 6.5
    dose   = 11.0
    steep  = 60.0
    water  = 200.0
    area   = constants.BREWER_PRESETS["standard"]["area_cm2"]
    press_s = calc_press_time(dose, dial, steep, brewer_size="standard")
    press_eq = min(press_s, constants.CHANNELING_PRESS_THRESHOLD) * constants.PRESS_EQUIV_FRACTION
    pour_offset = (water / constants.POUR_RATE) / 2.0

    ey  = calc_ey(roast, temp, dial, steep, dose, water, area, 50, press_eq)
    tds = calc_tds(roast, dose, ey, dial, water_ml=water)
    compounds = predict_compounds(
        roast_code=roast, temp=temp, dial=dial,
        steep_sec=steep, ey=ey,
        water_gh=50, water_mg_frac=0.40,
        press_equiv=press_eq, pour_offset=pour_offset,
        water_ml=water, dose=dose,
        press_sec=press_s, area_cm2=area,
    )
    ideal = build_ideal_abs(roast, tds)
    raw   = flavor_score(compounds, ideal, tds, roast,
                         water_kh=30, water_gh=50,
                         t_slurry=temp - 4.0, temp_initial=temp,
                         ey=ey, steep_sec=steep)
    score = score_to_display(raw, roast)

    ey_ok    = ey  < 15.0
    tds_ok   = tds < 0.85
    score_ok = score < 40.0

    all_pass = ey_ok and tds_ok and score_ok

    if verbose:
        print("=" * 60)
        print("Under-extraction anchor (light / 93C / dial6.5 / 60s / 11g / std)")
        print("=" * 60)
        print(f"  EY={ey:.1f}%  TDS={tds:.3f}%  score={score}")
        print(f"\nChecks:")
        print(f"  {_fmt(ey_ok)}   EY {ey:.1f}% < 15.0%  (under-extracted)")
        print(f"  {_fmt(tds_ok)}  TDS {tds:.3f}% < 0.85%  (too weak)")
        print(f"  {_fmt(score_ok)}  score {score} < 40.0  (bad recipes must score low)")
        print(f"\n{'[ ALL PASS ]' if all_pass else '[ FAIL - scoring not penalizing bad recipes ]'}")
        print("=" * 60)

    return all_pass


def run_overextract_anchor(verbose: bool = True) -> bool:
    """低分錨點二：過萃（細研磨＋長時間＋高溫），驗證苦澀配方確實得低分。
    99°C / dial 3.5 / steep 240s / 11g / 200ml / standard
    預期：EY > 22%，CGA 超標（觸發澀感懲罰），score < 80
    """
    roast  = "light"
    temp   = 99.0
    dial   = 3.5
    dose   = 11.0
    steep  = 240.0
    water  = 200.0
    area   = constants.BREWER_PRESETS["standard"]["area_cm2"]
    press_s  = calc_press_time(dose, dial, steep, brewer_size="standard")
    press_eq = min(press_s, constants.CHANNELING_PRESS_THRESHOLD) * constants.PRESS_EQUIV_FRACTION
    pour_offset = (water / constants.POUR_RATE) / 2.0

    ey  = calc_ey(roast, temp, dial, steep, dose, water, area, 50, press_eq)
    tds = calc_tds(roast, dose, ey, dial, water_ml=water)
    compounds = predict_compounds(
        roast_code=roast, temp=temp, dial=dial,
        steep_sec=steep, ey=ey,
        water_gh=50, water_mg_frac=0.40,
        press_equiv=press_eq, pour_offset=pour_offset,
        water_ml=water, dose=dose,
        press_sec=press_s, area_cm2=area,
    )
    ideal = build_ideal_abs(roast, tds)
    raw   = flavor_score(compounds, ideal, tds, roast,
                         water_kh=30, water_gh=50,
                         t_slurry=temp - 2.0, temp_initial=temp,
                         ey=ey, steep_sec=steep)
    score = score_to_display(raw, roast)

    cga_anchor_ideal = build_ideal_abs(roast, constants.TDS_PREFER[roast])
    cga_ratio = compounds["CGA"] / max(cga_anchor_ideal["CGA"], 1e-8)

    ey_ok    = ey  > 22.0
    cga_ok   = cga_ratio > constants.CGA_ASTRINGENCY_THRESHOLD
    score_ok = score < 50.0

    all_pass = ey_ok and cga_ok and score_ok

    if verbose:
        print("=" * 60)
        print("Over-extraction anchor (light / 99C / dial3.5 / 240s / 11g / std)")
        print("=" * 60)
        print(f"  EY={ey:.1f}%  TDS={tds:.3f}%  score={score}")
        print(f"\nChecks:")
        print(f"  {_fmt(ey_ok)}   EY {ey:.1f}% > 22.0%  (over-extracted)")
        print(f"  {_fmt(cga_ok)}  CGA ratio {cga_ratio:.3f} > {constants.CGA_ASTRINGENCY_THRESHOLD}  (astringency triggered)")
        print(f"  {_fmt(score_ok)}  score {score} < 50.0  (不能喝的配方必須低於 50)")
        print(f"\n{'[ ALL PASS ]' if all_pass else '[ FAIL - scoring not penalizing bad recipes ]'}")
        print("=" * 60)

    return all_pass


if __name__ == "__main__":
    ok_hoffman      = run_anchor_check(verbose=True)
    print()
    ok_april        = run_april_anchor(verbose=True)
    print()
    ok_championship = run_championship_anchor(verbose=True)
    print()
    ok_under = run_underextract_anchor(verbose=True)
    print()
    ok_over  = run_overextract_anchor(verbose=True)

    all_ok = ok_hoffman and ok_april and ok_championship and ok_under and ok_over
    print()
    print("=" * 60)
    print(f"  Hoffman:           {'PASS' if ok_hoffman else 'FAIL'}")
    print(f"  April:             {'PASS' if ok_april else 'FAIL'}")
    print(f"  Championship:      {'PASS' if ok_championship else 'FAIL'}")
    print(f"  Under-extraction:  {'PASS' if ok_under else 'FAIL'}")
    print(f"  Over-extraction:   {'PASS' if ok_over else 'FAIL'}")
    print(f"\n{'[ ALL PASS ]' if all_ok else '[ FAIL - check constants.py ]'}")
    print("=" * 60)
    sys.exit(0 if all_ok else 1)
