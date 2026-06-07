from __future__ import annotations

import csv
import json

import constants
from models import grind
from models.sensory import ATTRIBUTES


def _result_payload(result: dict, rank: int, grinder: str = grind.NATIVE) -> dict:
    recipe = {
        "temp_c": result["temp"],
        "dial": result["dial"],
        "steep_sec": result["steep_sec"],
        "dose_g": result["dose"],
    }
    if grinder != grind.NATIVE:
        # additive, ZP6 stays the source of truth; converted unit alongside it.
        recipe["grinder"] = grinder
        recipe["dial_display"] = grind.format_dial(grinder, result["dial"])
    return {
        "rank": rank,
        "recipe_id": result.get("recipe_id"),
        "distance": round(result["distance"], 4),
        "recipe": recipe,
        "metrics": {
            "ey_pct": round(result["ey"], 3),
            "tds_pct": round(result["tds"], 4),
        },
        "attributes": {a: round(result["attributes"][a], 4) for a in ATTRIBUTES},
        "ideal": {a: round(result["ideal"][a], 4) for a in ATTRIBUTES},
    }


def export_json(
    results,
    roast_code: str,
    temp: float,
    filepath: str = "output.json",
    grinder: str = grind.NATIVE,
) -> None:
    roast_name = constants.ROAST_TABLE[roast_code]["name"]
    first = results[0] if results else None
    payload = {
        "input": {
            "roast_code": roast_code,
            "roast_name": roast_name,
            "brewer": first["brewer"] if first else None,
            "water_ml": first["water_ml"] if first else None,
            "temp_c": temp,
        },
        "ranking": "distance to the roast's 6-axis sensory IDEAL (smaller = closer)",
        "results": [_result_payload(r, i, grinder) for i, r in enumerate(results, start=1)],
    }
    with open(filepath, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def export_csv(
    results,
    roast_code: str,
    filepath: str = "output.csv",
    grinder: str = grind.NATIVE,
) -> None:
    rows = []
    for rank, result in enumerate(results, start=1):
        row = {
            "rank": rank,
            "recipe_id": result.get("recipe_id"),
            "roast": result["roast"],
            "brewer_size": result["brewer_size"],
            "temp_c": result["temp"],
            "dial": result["dial"],
            "steep_sec": result["steep_sec"],
            "dose_g": result["dose"],
            "ey_pct": round(result["ey"], 3),
            "tds_pct": round(result["tds"], 4),
            "distance": round(result["distance"], 4),
        }
        if grinder != grind.NATIVE:
            row["grinder"] = grinder
            row["dial_display"] = grind.format_dial(grinder, result["dial"])
        for attr in ATTRIBUTES:
            row[f"attr_{attr}"] = round(result["attributes"][attr], 4)
            row[f"ideal_{attr}"] = round(result["ideal"][attr], 4)
        rows.append(row)
    fieldnames = list(rows[0].keys()) if rows else []
    with open(filepath, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
