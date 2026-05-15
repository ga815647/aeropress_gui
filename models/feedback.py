"""Phase 10 — feedback.jsonl reader / writer.

Schema lives in docs/FEEDBACK_FORMAT.md (single source of truth).
Append-only by design — corrections are new entries that reference prior timestamp.

This module is intentionally a thin shim: no aggregation, no dedup, no DB. The
intended refine workflow is Claude in conversation reading the JSONL and
suggesting label IDEAL diffs (see Phase 8 memo).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_FEEDBACK_PATH = Path(__file__).resolve().parents[1] / "data" / "feedback.jsonl"

ALLOWED_TAGS = {
    "acidic", "thin", "great-body", "bitter", "muted", "floral",
    "sweet", "harsh", "clean", "balanced", "fruity", "roasty",
}
ALLOWED_RATINGS = {"good", "ok", "bad"}


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
