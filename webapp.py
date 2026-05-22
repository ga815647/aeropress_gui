"""Phase 10 Step 6b — web UI over the sensory pipeline.

The optimizer searches dose x dial x steep at a fixed (roast, brewer, temp) and
ranks recipes by attribute-distance to the roast's 10-attribute sensory IDEAL.
There is no label and no water chemistry (Phase 10 §0 / Step 5). The feedback
form is the §4 pairwise + ordinal questionnaire — every cup judged against the
previous one. See docs/PHASE10_STEP6_FEEDBACK_LOOP.md.
"""
from __future__ import annotations

import argparse

from flask import Flask, jsonify, render_template, request

import constants
from models.feedback import (
    ALLOWED_ABSOLUTE,
    ALLOWED_TAGS,
    EDIT_WINDOW_HOURS,
    QUESTIONNAIRE_GROUPS,
    append_feedback,
    read_all as read_all_feedback,
    read_for_recipe,
    recompute_entry,
    update_feedback,
)
from models.ideal import available_roasts, roast_ideal
from models.sensory import ATTRIBUTES, AXIS_VIEW
from optimizer import optimize

# Group means with |delta| below this read as "=" in the model prefill of the
# §4 questionnaire. CATA-frequency units; tunable. Mirrored to the client.
ORDINAL_DEADBAND = 0.01


def _serialize_result(result: dict, feedback_index: dict[str, list[dict]] | None = None) -> dict:
    """One optimizer candidate -> the JSON the result card consumes."""
    attrs = result["attributes"]
    ideal = result["ideal"]
    rid = result.get("recipe_id")
    feedback = feedback_index.get(rid, []) if (feedback_index and rid) else []
    return {
        "recipe_id": rid,
        "roast": result["roast"],
        "brewer": result["brewer"],
        "brewer_size": result["brewer_size"],
        "water_ml": result["water_ml"],
        "temp": result["temp"],
        "dial": result["dial"],
        "steep_sec": result["steep_sec"],
        "dose": result["dose"],
        "ey": round(result["ey"], 2),
        "tds": round(result["tds"], 3),
        "distance": round(result["distance"], 4),
        "attributes": {a: round(attrs[a], 4) for a in ATTRIBUTES},
        "ideal": {a: round(ideal[a], 4) for a in ATTRIBUTES},
        "deltas": {a: round(attrs[a] - ideal[a], 4) for a in ATTRIBUTES},
        "feedback": feedback,
    }


def _with_current_derived(entry: dict) -> dict:
    """Feedback entry with recipe.tds/ey/distance/attributes refreshed by the
    current model. The recipe *inputs* (temp/dial/dose/steep) are durable;
    tds/ey/distance/attributes are a stale-able projection. The on-disk JSONL
    stays append-only — this is display-only. Falls back to the entry as-is
    when there is no recipe snapshot (legacy entry)."""
    current = recompute_entry(entry)
    if current is None:
        return entry
    out = dict(entry)
    recipe = dict(out.get("recipe") or {})
    recipe["tds"] = current["tds"]
    recipe["ey"] = current["ey"]
    recipe["distance"] = current["distance"]
    recipe["attributes"] = current["attributes"]
    out["recipe"] = recipe
    return out


def _build_feedback_index() -> dict[str, list[dict]]:
    """One JSONL scan per /api/optimize call -> dict[recipe_id] -> entries."""
    index: dict[str, list[dict]] = {}
    for entry in read_all_feedback():
        rid = entry.get("recipe_id")
        if rid:
            index.setdefault(rid, []).append(_with_current_derived(entry))
    return index


def _axis_view_payload() -> dict[str, list[str]]:
    """AXIS_VIEW as plain lists — the questionnaire grouping for the client."""
    return {group: list(members) for group, members in AXIS_VIEW.items()}


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        roast_options = [
            {"code": code, "name": constants.ROAST_TABLE[code]["name"],
             "note": constants.ROAST_TABLE[code]["note"]}
            for code in available_roasts()
        ]
        return render_template(
            "index.html",
            roast_options=roast_options,
            brewer_options=list(constants.BREWER_PRESETS.keys()),
            brewer_presets=constants.BREWER_PRESETS,
            default_temps=constants.DEFAULT_TEMP,
            attributes=list(ATTRIBUTES),
            axis_view=_axis_view_payload(),
            ordinal_deadband=ORDINAL_DEADBAND,
        )

    @app.get("/api/config")
    def config():
        return jsonify({
            "roast_options": [
                {"code": code, "name": constants.ROAST_TABLE[code]["name"]}
                for code in available_roasts()
            ],
            "brewers": constants.BREWER_PRESETS,
            "default_temps": constants.DEFAULT_TEMP,
            "attributes": list(ATTRIBUTES),
            "axis_view": _axis_view_payload(),
            "ordinal_deadband": ORDINAL_DEADBAND,
            "defaults": {"brewer": "xl", "roast": "medium_light", "top": 3},
        })

    @app.post("/api/optimize")
    def optimize_route():
        payload = request.get_json(silent=True) or {}
        roast_code = str(payload.get("roast", "medium_light"))
        brewer_size = str(payload.get("brewer", "xl"))

        def _num(key):
            val = payload.get(key)
            return float(val) if val not in (None, "") else None

        temp = _num("temp")
        dose_min = _num("dose_min")
        dose_max = _num("dose_max")
        top_n = int(payload.get("top") or 3)

        try:
            results = optimize(
                roast_code=roast_code,
                brewer_size=brewer_size,
                temp=temp,
                top_n=top_n,
                dose_min_override=dose_min,
                dose_max_override=dose_max,
            )
        except KeyError as exc:
            return jsonify({"error": f"unknown roast / brewer: {exc}"}), 400

        fb_index = _build_feedback_index()
        results_serialized = [_serialize_result(r, fb_index) for r in results]
        used_temp = (
            results[0]["temp"] if results
            else (temp if temp is not None else constants.DEFAULT_TEMP[roast_code])
        )
        ideal = roast_ideal(roast_code)
        return jsonify({
            "meta": {
                "roast_code": roast_code,
                "roast_name": constants.ROAST_TABLE[roast_code]["name"],
                "brewer": brewer_size,
                "temp": used_temp,
                "ideal": {a: round(ideal[a], 4) for a in ATTRIBUTES},
            },
            "results": results_serialized,
        })

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
        try:
            entry = update_feedback(payload.get("timestamp"), payload)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "entry": entry, "edit_window_hours": EDIT_WINDOW_HOURS})

    @app.get("/api/feedback/<recipe_id>")
    def feedback_for_recipe(recipe_id: str):
        entries = [_with_current_derived(e) for e in read_for_recipe(recipe_id)]
        return jsonify({"recipe_id": recipe_id, "entries": entries})

    @app.get("/api/feedback")
    def feedback_list():
        entries = [_with_current_derived(e) for e in read_all_feedback()]
        return jsonify({
            "entries": entries,
            "questionnaire_groups": list(QUESTIONNAIRE_GROUPS),
            "allowed_absolute": sorted(ALLOWED_ABSOLUTE),
            "allowed_tags": sorted(ALLOWED_TAGS),
        })

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
