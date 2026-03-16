from __future__ import annotations

import csv
import json

import constants
from models.scoring import build_ideal_abs, compute_actual_abs


def export_json(
    results: list[dict],
    roast_code: str,
    water_gh: float,
    water_kh: float,
    filepath: str = "output.json",
) -> None:
    roast_name = constants.ROAST_TABLE[roast_code]["name"]
    first = results[0] if results else None
    payload = {
        "input": {
            "roast_code": roast_code,
            "roast_name": roast_name,
            "water_gh_ppm": water_gh,
            "water_kh_ppm": water_kh,
        },
        "hoffman_constants": {
            "water_ml": first["water_ml"] if first else None,
            "position": "standard",
            "swirl_time_sec": constants.SWIRL_TIME_SEC,
            "swirl_convection_mult": "dynamic: 1.0 + SWIRL_CONVECTION_BASE × (18/dose)",
            "swirl_wait_sec": first["swirl_wait_sec"] if first else None,
            "press_time_note": "dynamic, 30–60s, f(dose, dial)",
            "press_style": "all_the_way_through_hiss",
            "filter_rinsing": False,
            "preheating": False,
        },
        "results": [],
    }

    for rank, result in enumerate(results, start=1):
        actual_abs = compute_actual_abs(result["compounds"], result["tds"])
        ideal_abs = build_ideal_abs(roast_code, result["tds"])
        payload["results"].append(
            {
                "rank": rank,
                "score": result["score"],
                "vectors": {
                    "temp_c": result["temp"],
                    "dial": result["dial"],
                    "steep_sec": result["steep_sec"],
                    "dose_g": result["dose"],
                },
                "derived": {
                    "fines_ratio_pct": round(result["fines_ratio"] * 100, 2),
                    "t_slurry_c": result["t_slurry"],
                    "t_kinetic_sec": result["t_kinetic"],
                    "mel_bitter_coeff": constants.MEL_BITTER_COEFF[roast_code],
                },
                "hoffman_flow": {
                    "steep_sec": result["steep_sec"],
                    "swirl_sec": result["swirl_sec"],
                    "swirl_wait_sec": result["swirl_wait_sec"],
                    "press_sec": result["press_sec"],
                    "total_contact_sec": result["total_contact_sec"],
                },
                "metrics": {
                    "ey_pct": result["ey"],
                    "tds_pct": result["tds"],
                    "retention_g_per_g": result["retention"],
                    "pre_seal_drip_ml": result["pre_seal_drip_ml"],
                },
                "compounds_abs": {
                    **{k: round(actual_abs[k], 4) for k in constants.KEYS},
                    "ac_sw_ratio_actual": round(actual_abs["AC"] / max(actual_abs["SW"], 1e-8), 4),
                    "ac_sw_ratio_ideal": round(ideal_abs["AC"] / max(ideal_abs["SW"], 1e-8), 4),
                    "ps_bitter_ratio_actual": round(
                        actual_abs["PS"]
                        / max(
                            actual_abs["CA"] + actual_abs["CGA"] + actual_abs["MEL"] * constants.MEL_BITTER_COEFF[roast_code],
                            1e-8,
                        ),
                        4,
                    ),
                    "ps_bitter_ratio_ideal": round(
                        ideal_abs["PS"]
                        / max(
                            ideal_abs["CA"] + ideal_abs["CGA"] + ideal_abs["MEL"] * constants.MEL_BITTER_COEFF[roast_code],
                            1e-8,
                        ),
                        4,
                    ),
                },
            }
        )

    with open(filepath, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def export_csv(results: list[dict], roast_code: str, filepath: str = "output.csv") -> None:
    rows = []
    for result in results:
        row = {k: v for k, v in result.items() if k != "compounds"}
        for key, value in result["compounds"].items():
            row[f"compounds_{key}"] = value
        rows.append(row)

    fieldnames = list(rows[0].keys()) if rows else []
    with open(filepath, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
