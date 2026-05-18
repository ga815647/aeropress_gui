from __future__ import annotations

import argparse

from flask import Flask, jsonify, render_template, request

import constants
from data.water_presets import WATER_PRESETS
from models.feedback import (
    ALLOWED_RATINGS,
    ALLOWED_TAGS,
    EDIT_WINDOW_HOURS,
    append_feedback,
    read_all as read_all_feedback,
    read_for_recipe,
    update_feedback,
)
from models.labels import get_label, ideal_abs as label_ideal_abs, label_names
from models.scoring import compute_actual_abs
from optimizer import optimize, optimize_parallel
from runtime import apply_environment_settings, resolve_water_profile


def _serialize_result(result: dict, roast_code: str, feedback_index: dict[str, list[dict]] | None = None) -> dict:
    label = result.get("label", "balanced")
    actual_abs = compute_actual_abs(result["compounds"], result["tds"])
    ideal_abs = label_ideal_abs(label, result["tds"])
    mel_coeff = constants.MEL_BITTER_COEFF[roast_code]
    actual_ac_sw = actual_abs["AC"] / max(actual_abs["SW"], 1e-8)
    ideal_ac_sw = ideal_abs["AC"] / max(ideal_abs["SW"], 1e-8)
    actual_ps_bitter = actual_abs["PS"] / max(
        actual_abs["CA"] + actual_abs["CGA"] + actual_abs["MEL"] * mel_coeff,
        1e-8,
    )
    ideal_ps_bitter = ideal_abs["PS"] / max(
        ideal_abs["CA"] + ideal_abs["CGA"] + ideal_abs["MEL"] * mel_coeff,
        1e-8,
    )
    rid = result.get("recipe_id")
    feedback = feedback_index.get(rid, []) if (feedback_index and rid) else []
    return {
        **result,
        "label": label,
        "compounds_abs": {key: round(actual_abs[key], 4) for key in constants.KEYS},
        "ratios": {
            "ac_sw_actual": round(actual_ac_sw, 3),
            "ac_sw_ideal": round(ideal_ac_sw, 3),
            "ps_bitter_actual": round(actual_ps_bitter, 3),
            "ps_bitter_ideal": round(ideal_ps_bitter, 3),
        },
        "feedback": feedback,
    }


def _build_feedback_index() -> dict[str, list[dict]]:
    """One JSONL scan per /api/optimize call → dict[recipe_id] → entries."""
    index: dict[str, list[dict]] = {}
    for entry in read_all_feedback():
        rid = entry.get("recipe_id")
        if rid:
            index.setdefault(rid, []).append(entry)
    return index


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        roast_options = [
            {"code": k, "name": v["name"], "note": v["note"], "dose_per_100ml": list(v["dose_per_100ml"])}
            for k, v in constants.ROAST_TABLE.items()
        ]
        labels = [
            {"name": name, **get_label(name)} for name in label_names()
        ]
        return render_template(
            "index.html",
            roast_codes=list(constants.ROAST_TABLE.keys()),
            roast_options=roast_options,
            brewer_options=list(constants.BREWER_PRESETS.keys()),
            brewer_presets=constants.BREWER_PRESETS,
            presets=WATER_PRESETS,
            labels=labels,
        )

    @app.get("/api/config")
    def config():
        return jsonify(
            {
                "roast_codes": list(constants.ROAST_TABLE.keys()),
                "roast_options": [
                    {"code": k, "name": v["name"]}
                    for k, v in constants.ROAST_TABLE.items()
                ],
                "brewers": constants.BREWER_PRESETS,
                "presets": WATER_PRESETS,
                "labels": [
                    {"name": name, **get_label(name)} for name in label_names()
                ],
                "defaults": {
                    "brewer": "xl",
                    "roast": "medium",
                    "label": "balanced",
                    "top": 3,
                    "t_env": 25.0,
                    "altitude": 0.0,
                    "gh": 50.0,
                    "kh": 30.0,
                    "mg_frac": 0.40,
                },
            }
        )

    @app.post("/api/optimize")
    def optimize_route():
        payload = request.get_json(silent=True) or {}
        apply_environment_settings(
            float(payload.get("t_env", 25.0)),
            float(payload.get("altitude", 0.0)),
        )
        water_gh, water_kh, water_mg_frac, water_source = resolve_water_profile(
            gh=payload.get("gh"),
            kh=payload.get("kh"),
            mg_frac=payload.get("mg_frac"),
            preset=payload.get("preset"),
        )
        roast_code = str(payload.get("roast", "medium"))
        dose_min = payload.get("dose_min")
        dose_max = payload.get("dose_max")
        dose_min = float(dose_min) if dose_min is not None else None
        dose_max = float(dose_max) if dose_max is not None else None

        requested_label = payload.get("label")
        common = dict(
            roast_code=roast_code,
            brewer_size=payload.get("brewer", "xl"),
            water_gh=water_gh,
            water_kh=water_kh,
            water_mg_frac=water_mg_frac,
            dose_min_override=dose_min,
            dose_max_override=dose_max,
        )

        fb_index = _build_feedback_index()

        if requested_label and requested_label != "__all__":
            results = optimize(
                top_n=int(payload.get("top", 3)),
                label=requested_label,
                **common,
            )
            results_serialized = [_serialize_result(item, roast_code, fb_index) for item in results]
            label_used = requested_label
            top_tds = results[0]["tds"] if results else 1.25
        else:
            parallel = optimize_parallel(
                top_n=int(payload.get("top", 1)),
                **common,
            )
            results_serialized = {
                lbl: [_serialize_result(item, roast_code, fb_index) for item in items]
                for lbl, items in parallel.items()
            }
            label_used = "__all__"
            first_tds = next(
                (items[0]["tds"] for items in parallel.values() if items),
                1.25,
            )
            top_tds = first_tds

        # 顯示用 flavor_max（progress bar 上限）— 取 label 的 ideal × (tds + 0.2)
        ref_label = requested_label if (requested_label and requested_label != "__all__") else "balanced"
        max_tds = top_tds + 0.2
        flavor_max_raw = label_ideal_abs(ref_label, max_tds)
        flavor_max = {k: round(v, 4) for k, v in flavor_max_raw.items()}

        return jsonify(
            {
                "meta": {
                    "roast_code": roast_code,
                    "roast_name": constants.ROAST_TABLE[roast_code]["name"],
                    "water_gh": water_gh,
                    "water_kh": water_kh,
                    "water_mg_frac": water_mg_frac,
                    "water_source": water_source,
                    "label": label_used,
                    "flavor_max": flavor_max,
                },
                "results": results_serialized,
            }
        )

    @app.post("/api/feedback")
    def feedback_route():
        payload = request.get_json(silent=True) or {}
        try:
            entry = append_feedback(payload)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "entry": entry})

    @app.post("/api/feedback/update")
    def feedback_update_route():
        payload = request.get_json(silent=True) or {}
        ts = payload.get("timestamp")
        try:
            entry = update_feedback(ts, payload)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "entry": entry, "edit_window_hours": EDIT_WINDOW_HOURS})

    @app.get("/api/feedback/<recipe_id>")
    def feedback_for_recipe(recipe_id: str):
        return jsonify({"recipe_id": recipe_id, "entries": read_for_recipe(recipe_id)})

    @app.get("/api/feedback")
    def feedback_list():
        return jsonify({"entries": read_all_feedback()})

    return app


app = create_app()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AeroPress Web UI")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--debug", dest="debug", action="store_true")
    parser.add_argument("--no-debug", dest="debug", action="store_false")
    parser.set_defaults(debug=True)
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=True)
