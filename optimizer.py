from __future__ import annotations

import math

import constants
from models.compounds import predict_compounds
from models.ey_model import calc_ey, calc_fines_ratio
from models.scoring import build_ideal_abs, flavor_score, score_to_display
from models.tds_model import apply_channeling, calc_drip_volume, calc_press_time, calc_retention, calc_swirl_wait, calc_tds


def optimize(
    roast_code: str,
    brewer_size: str = "xl",
    water_gh: float = 50,
    water_kh: float = 30,
    water_mg_frac: float = 0.40,
    top_n: int = 3,
    fixed_dose: float | None = None,
    temp_range: tuple[int, int] | None = None,
    fixed_steep: int | None = None,
    dose_min_override: float | None = None,
    dose_max_override: float | None = None,
    diversify_top: bool = True,
) -> list[dict]:
    cfg = constants.ROAST_TABLE[roast_code]
    base_temp = cfg["base_temp"]
    brewer = constants.BREWER_PRESETS[brewer_size]
    water_ml = brewer["water_ml"]
    area_cm2 = brewer.get("area_cm2", constants.DRIP_AREA_REF_CM2)
    dose_min_x2 = int(brewer["dose_min"] * 2)
    dose_max_x2 = int(brewer["dose_max"] * 2)
    # XL 採 1g 步進（dose_x2 跨 2），standard 採 0.5g（dose_x2 跨 1）
    dose_step_x2 = 2 if brewer_size == "xl" else 1

    # 各焙度豆量預設範圍（g/100ml）：收窄搜尋，省豆優先
    dose_range = cfg.get("dose_per_100ml")
    if dose_range and fixed_dose is None:
        roast_min_x2 = int(dose_range[0] * water_ml / 100 * 2)
        roast_max_x2 = int(dose_range[1] * water_ml / 100 * 2)
        dose_min_x2 = max(dose_min_x2, roast_min_x2)
        dose_max_x2 = min(dose_max_x2, roast_max_x2)

    # GUI 手動豆量區間覆蓋
    if dose_min_override is not None and fixed_dose is None:
        dose_min_x2 = max(dose_min_x2, int(dose_min_override * 2))
    if dose_max_override is not None and fixed_dose is None:
        dose_max_x2 = min(dose_max_x2, int(dose_max_override * 2))

    pour_time = water_ml / constants.POUR_RATE
    pour_offset = pour_time / 2.0
    seal_delay = constants.SEAL_DELAY_DEFAULT
    drip_time = pour_time + seal_delay
    results: list[dict] = []

    if temp_range is not None:
        temp_lo, temp_hi = temp_range
    else:
        temp_lo = base_temp - 15
        temp_hi = int(min(base_temp + 3, constants.TEMP_BOILING_POINT))

    steep_values = [fixed_steep] if fixed_steep is not None else range(30, 421, constants.STEEP_STEP)
    if fixed_dose is not None:
        dose_values: range | list = [int(fixed_dose * 2)]
    else:
        # 將起點對齊到 step 邊界（避免 XL 落在 0.5g 半階）
        remainder = dose_min_x2 % dose_step_x2
        if remainder:
            dose_min_x2 += dose_step_x2 - remainder
        dose_values = range(dose_min_x2, dose_max_x2 + 1, dose_step_x2)

    for temp in range(temp_lo, temp_hi + 1):
        for dial_x10 in range(30, 76):
            dial = dial_x10 / 10
            for steep in steep_values:
                for dose_x2 in dose_values:
                    dose = dose_x2 / 2

                    press_sec = calc_press_time(dose, dial, steep, brewer_size=brewer_size)
                    if press_sec > constants.CHANNELING_PRESS_THRESHOLD:
                        collapsed_press = (
                            constants.CHANNELING_PRESS_THRESHOLD
                            + (press_sec - constants.CHANNELING_PRESS_THRESHOLD)
                            * constants.CHANNELING_COLLAPSE_RATIO
                        )
                        display_press_sec = int(collapsed_press)
                    else:
                        collapsed_press = press_sec
                        display_press_sec = press_sec

                    press_equiv = collapsed_press * constants.PRESS_EQUIV_FRACTION
                    swirl_wait = calc_swirl_wait(brewer_size)
                    ey = calc_ey(
                        roast_code,
                        temp,
                        dial,
                        steep,
                        dose,
                        water_ml,
                        water_gh,
                        press_equiv=press_equiv,
                        pour_offset=pour_offset,
                        seal_delay=seal_delay,
                        swirl_wait_sec=swirl_wait,
                        area_cm2=area_cm2,
                    )
                    if ey < constants.EY_MIN:
                        continue

                    t_slurry_val = round(
                        (water_ml * temp + dose * constants.COFFEE_SPECIFIC_HEAT_RATIO * constants.T_ENV)
                        / (water_ml + dose * constants.COFFEE_SPECIFIC_HEAT_RATIO)
                        - constants.BREWER_TEMP_DROP,
                        1,
                    )

                    compounds_raw = predict_compounds(
                        roast_code,
                        t_slurry_val,
                        dial,
                        steep,
                        ey,
                        water_gh,
                        water_mg_frac,
                        press_equiv=press_equiv,
                        pour_offset=pour_offset,
                        water_ml=water_ml,
                        seal_delay=seal_delay,
                        dose=dose,
                        press_sec=press_sec,
                        area_cm2=area_cm2,
                    )
                    ey, compounds = apply_channeling(ey, compounds_raw, press_sec)
                    tds = calc_tds(roast_code, dose, ey, dial, water_ml)
                    ideal_abs = build_ideal_abs(roast_code, tds)
                    score_raw = flavor_score(
                        compounds, ideal_abs, tds, roast_code,
                        water_kh=water_kh, water_gh=water_gh,
                        t_slurry=t_slurry_val, temp_initial=temp,
                        ey=ey, steep_sec=steep, dial=dial,
                    )
                    dial_prefer = cfg.get("dial_prefer")
                    if dial_prefer is not None:
                        # XL 床深 ~30% 較標準版深，物理上偏好略粗（+0.10 dial）對抗深床流阻
                        effective_dial_prefer = dial_prefer + brewer.get("dial_offset", 0.0)
                        dial_dev = (dial - effective_dial_prefer) / constants.DIAL_PREFER_SIGMA
                        dial_factor = 1.0 - constants.DIAL_PREFER_WEIGHT * (1.0 - math.exp(-0.5 * dial_dev**2))
                        score_raw *= dial_factor
                    score = score_to_display(score_raw, roast_code)
                    drip_volume = calc_drip_volume(water_ml, dial, drip_time, dose, area_cm2)

                    results.append(
                        {
                            "_score_raw": score_raw,
                            "brewer": brewer["name"],
                            "water_ml": water_ml,
                            "temp": temp,
                            "dial": dial,
                            "steep_sec": steep,
                            "dose": dose,
                            "swirl_sec": constants.SWIRL_TIME_SEC,
                            "swirl_wait_sec": swirl_wait,
                            "press_sec": display_press_sec,
                            "press_sec_internal": press_sec,
                            "seal_delay": seal_delay,
                            "pre_seal_drip_sec": round(drip_time, 1),
                            "pre_seal_drip_ml": drip_volume,
                            "total_contact_sec": steep + constants.SWIRL_TIME_SEC + swirl_wait + display_press_sec,
                            "ey": ey,
                            "tds": tds,
                            "fines_ratio": calc_fines_ratio(dial),
                            "t_slurry": t_slurry_val,
                            "t_kinetic": round(
                                max(0, steep - pour_offset)
                                + constants.SWIRL_TIME_SEC
                                * (1.0 + constants.SWIRL_CONVECTION_BASE * (constants.SWIRL_DOSE_REF / dose))
                                + swirl_wait * constants.SWIRL_WAIT_EXT_MULT
                                + press_equiv,
                                1,
                            ),
                            "retention": calc_retention(roast_code, dial),
                            "compounds": compounds,
                            "score": score,
                        }
                    )

    results.sort(key=lambda item: item["_score_raw"], reverse=True)

    if not results:
        return []

    # #1 = 全域最高分（無條件）。
    # #2..N = 強制與已選方案在 (dial, steep, dose) 至少一軸有顯著差異，
    #         讓 Top 列表呈現「粗磨派、長時間派、多豆量派」等不同象限的代表，
    #         而不是全部擠在最佳解的小鄰域。
    # diagnose_anchor.py 需關閉多樣化以驗證 Top3 都在錨點鄰域。
    if not diversify_top:
        return results[:top_n]
    final: list[dict] = [results[0]]
    if top_n <= 1:
        return final

    def _diverse(candidate: dict, selected: list[dict]) -> bool:
        for s in selected:
            if (abs(candidate["dial"] - s["dial"]) < constants.TOP_DIVERSITY_DIAL_MIN
                    and abs(candidate["steep_sec"] - s["steep_sec"]) < constants.TOP_DIVERSITY_STEEP_MIN
                    and abs(candidate["dose"] - s["dose"]) < constants.TOP_DIVERSITY_DOSE_MIN):
                return False
        return True

    for item in results[1:]:
        if len(final) >= top_n:
            break
        if _diverse(item, final):
            final.append(item)

    # 若多樣化條件太嚴格使 Top N 補不滿，補回剩餘高分（仍保留排序）
    if len(final) < top_n:
        seen = {id(x) for x in final}
        for item in results[1:]:
            if len(final) >= top_n:
                break
            if id(item) not in seen:
                final.append(item)

    return final
