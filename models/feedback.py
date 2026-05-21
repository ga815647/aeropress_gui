"""Phase 10 — feedback.jsonl reader / writer.

Schema lives in docs/FEEDBACK_FORMAT.md (single source of truth).
Append-only by design — corrections are new entries that reference prior timestamp.

This module is intentionally a thin shim: no aggregation, no dedup, no DB. The
intended refine workflow is Claude in conversation reading the JSONL and
suggesting label IDEAL diffs (see Phase 8 memo).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

_FEEDBACK_PATH = Path(__file__).resolve().parents[1] / "data" / "feedback.jsonl"

ALLOWED_TAGS = {
    "acidic", "thin", "great-body", "bitter", "muted", "floral",
    "sweet", "harsh", "clean", "balanced", "fruity", "roasty",
}
ALLOWED_RATINGS = {"good", "ok", "bad"}
EDIT_WINDOW_HOURS = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def append_feedback(entry: dict) -> dict:
    """Validate & append one feedback entry to data/feedback.jsonl.

    Required fields (caller responsibility): recipe_id, label, roast, brewer, water.
    Adds timestamp server-side. Returns the canonicalised entry.

    Raises ValueError on schema violations (validates at the boundary per
    project policy — internal callers can trust the result).
    """
    required = ("recipe_id", "label", "roast", "brewer", "water")
    for key in required:
        if not entry.get(key):
            raise ValueError(f"feedback missing required field: {key}")

    water = entry["water"]
    if not isinstance(water, dict) or not all(k in water for k in ("gh", "kh", "mg_frac")):
        raise ValueError("water must be {gh, kh, mg_frac}")

    stars = entry.get("stars")
    if stars is not None:
        try:
            stars = int(stars)
        except (TypeError, ValueError):
            raise ValueError("stars must be 1-5 integer or null")
        if not 1 <= stars <= 5:
            raise ValueError("stars must be 1-5 integer or null")

    rating = entry.get("rating")
    if rating is not None and rating not in ALLOWED_RATINGS:
        raise ValueError(f"rating must be one of {ALLOWED_RATINGS} or null")

    tags = entry.get("tags") or []
    if not isinstance(tags, list):
        raise ValueError("tags must be a list")
    tags = [str(t).strip().lower() for t in tags if str(t).strip()]

    comment = str(entry.get("comment") or "").strip()
    if not comment and stars is None and not tags and rating is None:
        raise ValueError("feedback must include at least one of comment / stars / tags / rating")

    recipe = entry.get("recipe") or {}
    recipe_snapshot = None
    if recipe:
        try:
            recipe_snapshot = {
                "temp": float(recipe["temp"]),
                "dial": float(recipe["dial"]),
                "dose": float(recipe["dose"]),
                "steep_sec": int(recipe["steep_sec"]),
                "tds": float(recipe.get("tds")) if recipe.get("tds") is not None else None,
                "ey": float(recipe.get("ey")) if recipe.get("ey") is not None else None,
                "score": float(recipe.get("score")) if recipe.get("score") is not None else None,
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"recipe snapshot malformed: {exc}")

    canonical = {
        "timestamp": entry.get("timestamp") or _now_iso(),
        "recipe_id": str(entry["recipe_id"]),
        "label": str(entry["label"]),
        "rating": rating,
        "stars": stars,
        "comment": comment,
        "tags": tags,
        "roast": str(entry["roast"]),
        "brewer": str(entry["brewer"]),
        "water": {"gh": float(water["gh"]), "kh": float(water["kh"]), "mg_frac": float(water["mg_frac"])},
        "recipe": recipe_snapshot,
    }

    _FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _FEEDBACK_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(canonical, ensure_ascii=False) + "\n")
    return canonical


def read_all() -> list[dict]:
    """Read entire feedback.jsonl as list of entries. Returns [] if missing."""
    if not _FEEDBACK_PATH.exists():
        return []
    out: list[dict] = []
    with _FEEDBACK_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def read_for_recipe(recipe_id: str) -> list[dict]:
    """Return feedback entries for a single recipe_id, oldest first."""
    return [e for e in read_all() if e.get("recipe_id") == recipe_id]


def recompute_entry(entry: dict) -> dict | None:
    """Recompute an entry's derived fields (ey / tds / score / compounds) with
    the CURRENT model, from its immutable recipe inputs. Returns None if the
    entry has no recipe snapshot (legacy pre-Phase-10 — nothing to derive from).

    feedback.jsonl is append-only: the stored recipe.tds/ey/score is the
    as-submitted snapshot and is never mutated. This is the *current* projection
    — after a model recalibration the stored snapshot goes stale, so the history
    view should display this instead. The recipe inputs (temp/dial/dose/steep)
    are durable; tds/ey/score are merely a projection of them through the model.
    """
    recipe = entry.get("recipe")
    if not recipe:
        return None
    water = entry.get("water") or {}

    import constants
    import runtime
    from optimizer import score_logged_recipe  # lazy: keeps append/read light

    # feedback.jsonl stores no t_env — pin ambient to module defaults so the
    # recompute is deterministic (T_ENV is global mutable state) and matches how
    # the recipe was first scored. Save/restore so a history read has no side effect.
    saved_env = (constants.T_ENV, constants.TEMP_BOILING_POINT)
    try:
        runtime.apply_environment_settings(25.0, 0.0)
        scored = score_logged_recipe(
            roast_code=str(entry["roast"]),
            brewer_size=str(entry["brewer"]),
            temp=float(recipe["temp"]),
            dial=float(recipe["dial"]),
            steep_sec=int(recipe["steep_sec"]),
            dose=float(recipe["dose"]),
            water_gh=float(water.get("gh", 50)),
            water_kh=float(water.get("kh", 30)),
            water_mg_frac=float(water.get("mg_frac", 0.40)),
            label=str(entry["label"]),
        )
    except (KeyError, TypeError, ValueError):
        return None
    finally:
        constants.T_ENV, constants.TEMP_BOILING_POINT = saved_env
    return {
        "ey": round(scored["ey"], 3),
        "tds": round(scored["tds"], 4),
        "score": scored["score"],
        "compounds": {k: round(v, 4) for k, v in scored["compounds"].items()},
    }


def update_feedback(timestamp: str, updates: dict) -> dict:
    """In-place edit of an existing entry within EDIT_WINDOW_HOURS of creation.

    Editable fields: stars, comment, tags, rating. Other fields (recipe_id,
    label, roast, brewer, water, recipe snapshot) are immutable — they reflect
    the brewing context and must match the original recommendation.

    Violates the append-only spirit of the JSONL log, but the short window
    (EDIT_WINDOW_HOURS) confines the damage to the "misclick / UI bug" use
    case. Beyond the window the entry is frozen and corrections must be new
    entries.
    """
    if not timestamp:
        raise ValueError("timestamp required")

    entries = read_all()
    target_idx = next((i for i, e in enumerate(entries) if e.get("timestamp") == timestamp), None)
    if target_idx is None:
        raise ValueError(f"feedback entry not found: {timestamp}")
    target = entries[target_idx]

    try:
        created = datetime.fromisoformat(target["timestamp"]).astimezone(timezone.utc)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"entry timestamp malformed: {exc}")
    if datetime.now(timezone.utc) - created > timedelta(hours=EDIT_WINDOW_HOURS):
        raise ValueError(f"edit window expired ({EDIT_WINDOW_HOURS}h)")

    if "stars" in updates:
        stars = updates["stars"]
        if stars is not None:
            try:
                stars = int(stars)
            except (TypeError, ValueError):
                raise ValueError("stars must be 1-5 integer or null")
            if not 1 <= stars <= 5:
                raise ValueError("stars must be 1-5 integer or null")
        target["stars"] = stars

    if "rating" in updates:
        rating = updates["rating"]
        if rating is not None and rating not in ALLOWED_RATINGS:
            raise ValueError(f"rating must be one of {ALLOWED_RATINGS} or null")
        target["rating"] = rating

    if "tags" in updates:
        tags = updates["tags"] or []
        if not isinstance(tags, list):
            raise ValueError("tags must be a list")
        target["tags"] = [str(t).strip().lower() for t in tags if str(t).strip()]

    if "comment" in updates:
        target["comment"] = str(updates["comment"] or "").strip()

    if (not target.get("comment") and target.get("stars") is None
            and not target.get("tags") and target.get("rating") is None):
        raise ValueError("entry must retain at least one of comment / stars / tags / rating")

    with _FEEDBACK_PATH.open("w", encoding="utf-8") as handle:
        for e in entries:
            handle.write(json.dumps(e, ensure_ascii=False) + "\n")
    return target
