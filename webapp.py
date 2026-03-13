from __future__ import annotations

import argparse

from flask import Flask, jsonify, render_template, request

import constants
from data.water_presets import WATER_PRESETS
from optimizer import optimize
from runtime import apply_environment_settings, resolve_water_profile
from models.scoring import build_ideal_abs, compute_actual_abs


def _serialize_result(result: dict, roast_code: str) -> dict:
    actual_abs = compute_actual_abs(result["compounds"], result["tds"])
    ideal_abs = build_ideal_abs(roast_code, result["tds"])
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
    return {
        **result,
        "compounds_abs": {key: round(actual_abs[key], 4) for key in constants.KEYS},
        "ratios": {
            "ac_sw_actual": round(actual_ac_sw, 3),
            "ac_sw_ideal": round(ideal_ac_sw, 3),
            "ps_bitter_actual": round(actual_ps_bitter, 3),
            "ps_bitter_ideal": round(ideal_ps_bitter, 3),
        },
    }


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            roast_codes=list(constants.ROAST_TABLE.keys()),
            brewer_options=list(constants.BREWER_PRESETS.keys()),
            presets=WATER_PRESETS,
        )

    @app.get("/api/config")
    def config():
        return jsonify(
            {
                "roast_codes": list(constants.ROAST_TABLE.keys()),
                "brewers": constants.BREWER_PRESETS,
                "presets": WATER_PRESETS,
                "defaults": {
                    "brewer": "xl",
                    "roast": "M",
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
        roast_code = str(payload.get("roast", "M"))
        results = optimize(
            roast_code=roast_code,
            brewer_size=payload.get("brewer", "xl"),
            water_gh=water_gh,
            water_kh=water_kh,
            water_mg_frac=water_mg_frac,
            top_n=int(payload.get("top", 3)),
        )
        return jsonify(
            {
                "meta": {
                    "roast_code": roast_code,
                    "roast_name": constants.ROAST_TABLE[roast_code]["name"],
                    "water_gh": water_gh,
                    "water_kh": water_kh,
                    "water_mg_frac": water_mg_frac,
                    "water_source": water_source,
                },
                "results": [_serialize_result(item, roast_code) for item in results],
            }
        )

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
