from __future__ import annotations

import constants
from models.compounds import predict_compounds
from models.ey_model import calc_ey, calc_fines_ratio
from models.scoring import build_ideal_abs, flavor_score
from models.tds_model import apply_channeling, calc_drip_volume, calc_press_time, calc_retention, calc_swirl_wait, calc_tds


def optimize(
    roast_code: str,
    brewer_size: str = "xl",
    water_gh: float = 50,
    water_kh: float = 30,
    water_mg_frac: float = 0.40,
    top_n: int = 3,
) -> list[dict]:
    cfg = constants.ROAST_TABLE[roast_code]
    base_temp = cfg["base_temp"]
    brewer = constants.BREWER_PRESETS[brewer_size]
    water_ml = brewer["water_ml"]
    dose_min_x2 = int(brewer["dose_min"] * 2)
    dose_max_x2 = int(brewer["dose_max"] * 2)

    pour_time = water_ml / constants.POUR_RATE
    pour_offset = pour_time / 2.0
    seal_delay = constants.SEAL_DELAY_DEFAULT
    drip_time = pour_time + seal_delay
    results: list[dict] = []

    max_temp = min(base_temp + 3, constants.TEMP_BOILING_POINT)

    for temp in range(base_temp - 3, int(max_temp) + 1):
        for dial_x10 in range(35, 66):
            dial = dial_x10 / 10
            for steep in range(60, 241, constants.STEEP_STEP):
                for dose_x2 in range(dose_min_x2, dose_max_x2 + 1):
                    dose = dose_x2 / 2

                    press_sec = calc_press_time(dose, dial, steep)
                    if press_sec > constants.CHANNELING_PRESS_THRESHOLD:
                        display_press_sec = int(
                            constants.CHANNELING_PRESS_THRESHOLD
                            + (press_sec - constants.CHANNELING_PRESS_THRESHOLD)
                            * constants.CHANNELING_COLLAPSE_RATIO
                        )
                    else:
                        display_press_sec = press_sec

                    press_equiv = display_press_sec * constants.PRESS_EQUIV_FRACTION
                    ey = calc_ey(
                        roast_code,
                        temp,
                        dial,
                        steep,
                        dose,
                        water_ml,
                        water_gh,
                        water_kh,
                        press_equiv=press_equiv,
                        pour_offset=pour_offset,
                        seal_delay=seal_delay,
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
                        water_kh,
                        water_mg_frac,
                        press_equiv=press_equiv,
                        pour_offset=pour_offset,
                        water_ml=water_ml,
                        seal_delay=seal_delay,
                    )
                    ey, compounds = apply_channeling(ey, compounds_raw, press_sec)
                    tds = calc_tds(roast_code, dose, ey, dial, water_ml)
                    ideal_abs = build_ideal_abs(roast_code, tds)
                    score = flavor_score(
                        compounds, ideal_abs, tds, roast_code,
                        water_kh=water_kh, water_gh=water_gh,
                        t_slurry=t_slurry_val, temp_initial=temp,
                    )
                    swirl_wait = calc_swirl_wait(dial)
                    drip_volume = calc_drip_volume(water_ml, dial, drip_time)

                    results.append(
                        {
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
                                + press_equiv,
                                1,
                            ),
                            "retention": calc_retention(roast_code, dial),
                            "compounds": compounds,
                            "score": score,
                        }
                    )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_n]
