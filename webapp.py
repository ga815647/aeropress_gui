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
from models import loop as loop_engine
from models import saved as saved_recipes

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


def _serialize_proposal(proposal: dict,
                        feedback_index: dict[str, list[dict]] | None = None) -> dict:
    """A loop proposal -> the JSON the loop card consumes. Same 10-attribute /
    distance shape as an optimizer result, plus the loop context."""
    card = _serialize_result(proposal, feedback_index)
    for key in ("role", "role_index", "cycle_index", "generation", "skips",
                "suggested_compared_to", "is_champion_rebrew", "champion"):
        card[key] = proposal.get(key)
    return card


def _serialize_loop(loop: dict) -> dict:
    """Loop state -> a compact summary for the loop panel."""
    return {
        "roast": loop["roast"],
        "brewer": loop["brewer"],
        "temp": loop["temp"],
        "generation": loop["generation"],
        "champion": loop["champion"],
        "cycle_index": loop["cycle"]["index"],
        "slots": [
            {"role": s["role"], "status": s["status"], "skips": s["skips"]}
            for s in loop["cycle"]["slots"]
        ],
        "history": loop.get("history", []),
        "started_at": loop.get("started_at"),
        "updated_at": loop.get("updated_at"),
    }


def _loop_payload(roast_code: str) -> dict:
    """The /api/loop response for one roast — loop summary, the next proposal
    (evaluated), and any flags raised against this roast."""
    loop = loop_engine.get_loop(roast_code)
    proposal = loop_engine.current_proposal(roast_code) if loop else None
    fb_index = _build_feedback_index()
    flags = [f for f in loop_engine.detect_flags() if f["roast"] == roast_code]
    return {
        "roast": roast_code,
        "loop": _serialize_loop(loop) if loop else None,
        "proposal": _serialize_proposal(proposal, fb_index) if proposal else None,
        "flags": flags,
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
        # Hand the entry to the loop engine: if its recipe_id is a current cycle
        # slot, the loop marks it brewed and (when the cycle completes) digests.
        # A loop fault must never block feedback persistence — the entry is
        # already on disk; swallow and report no advance.
        loop_result = {"matched": False, "digested": False}
        try:
            outcome = loop_engine.register_feedback(
                entry["roast"], entry["recipe_id"], entry
            )
            loop_result = {"matched": outcome["matched"],
                           "digested": outcome["digested"]}
        except Exception:  # noqa: BLE001 — deliberate: feedback is already saved
            pass
        return jsonify({"ok": True, "entry": entry, "loop": loop_result})

    @app.get("/api/loop")
    def loop_state():
        roast_code = str(request.args.get("roast", "medium_light"))
        return jsonify(_loop_payload(roast_code))

    @app.post("/api/loop/start")
    def loop_start():
        payload = request.get_json(silent=True) or {}
        roast_code = str(payload.get("roast", "medium_light"))
        brewer_size = str(payload.get("brewer", "xl"))
        temp = payload.get("temp")
        try:
            loop_engine.start_loop(
                roast_code, brewer=brewer_size,
                temp=float(temp) if temp not in (None, "") else None,
            )
        except (KeyError, IndexError) as exc:
            return jsonify({"error": f"cannot start loop: {exc}"}), 400
        return jsonify(_loop_payload(roast_code))

    @app.post("/api/loop/reset")
    def loop_reset():
        payload = request.get_json(silent=True) or {}
        roast_code = str(payload.get("roast", "medium_light"))
        brewer = payload.get("brewer")
        temp = payload.get("temp")
        try:
            loop_engine.reset_loop(
                roast_code,
                brewer=str(brewer) if brewer else None,
                temp=float(temp) if temp not in (None, "") else None,
            )
        except (KeyError, IndexError) as exc:
            return jsonify({"error": f"cannot reset loop: {exc}"}), 400
        return jsonify(_loop_payload(roast_code))

    @app.post("/api/loop/skip")
    def loop_skip():
        payload = request.get_json(silent=True) or {}
        roast_code = str(payload.get("roast", ""))
        recipe_id = str(payload.get("recipe_id", ""))
        result = loop_engine.skip_proposal(roast_code, recipe_id)
        if not result["skipped"]:
            return jsonify(
                {"error": "nothing to skip (champion re-brew or unknown id)"}
            ), 400
        return jsonify(_loop_payload(roast_code))

    @app.get("/api/recipes")
    def recipes_list():
        return jsonify({"recipes": saved_recipes.list_recipes()})

    @app.post("/api/recipes")
    def recipes_save():
        payload = request.get_json(silent=True) or {}
        try:
            entry = saved_recipes.save_recipe(
                name=payload.get("name"), roast=payload.get("roast"),
                brewer=payload.get("brewer"), temp=payload.get("temp"),
                dial=payload.get("dial"), steep_sec=payload.get("steep_sec"),
                dose=payload.get("dose"), note=payload.get("note", ""),
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "recipe": entry})

    @app.delete("/api/recipes/<saved_id>")
    def recipes_delete(saved_id: str):
        return jsonify({"ok": saved_recipes.delete_recipe(saved_id)})

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
