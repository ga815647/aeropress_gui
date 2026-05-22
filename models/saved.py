"""Phase 11 — named saved-recipe library (data/saved_recipes.json).

A manual companion to the loop's automatic champion. The loop tracks ONE
champion per roast and moves it by feedback; this is where the user pins and
NAMES recipes worth keeping — an optimizer Top-N result, the current champion,
anything. The user asked for this alongside the loop engine (2026-05-22): "只紀錄
唯一好喝 或是使用者手動存的參數，並且可以命名這組參數".

A flat JSON list — no scoring, no dedup, no model logic. Validate at the
boundary, append, read, delete. The temp/dial/dose/steep_sec are durable
inputs; nothing derived is stored (recompute through the model if needed).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from models.ideal import recipe_id as compute_recipe_id

_SAVED_PATH = Path(__file__).resolve().parents[1] / "data" / "saved_recipes.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load() -> list[dict]:
    """The saved-recipe list. [] when the file is absent or unreadable."""
    if not _SAVED_PATH.exists():
        return []
    try:
        with _SAVED_PATH.open(encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(recipes: list[dict]) -> None:
    _SAVED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _SAVED_PATH.open("w", encoding="utf-8") as handle:
        json.dump(recipes, handle, ensure_ascii=False, indent=2)


def list_recipes() -> list[dict]:
    """All saved recipes, newest first."""
    return sorted(_load(), key=lambda r: r.get("saved_at", ""), reverse=True)


def save_recipe(name: str, roast: str, brewer: str, temp, dial,
                steep_sec, dose, note: str = "") -> dict:
    """Validate and append one named recipe. Returns the stored entry.

    Raises ValueError on a missing name / roast / brewer or non-numeric knobs —
    validation lives here so any caller can trust a stored entry.
    """
    name = str(name or "").strip()
    if not name:
        raise ValueError("a saved recipe needs a name")
    if not roast or not brewer:
        raise ValueError("saved recipe missing roast / brewer")
    try:
        temp = float(temp)
        dial = round(float(dial), 1)
        steep_sec = int(steep_sec)
        dose = round(float(dose), 1)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"saved recipe knobs malformed: {exc}")

    saved_at = _now_iso()
    entry = {
        "id": hashlib.sha1(f"{name}|{saved_at}".encode("utf-8")).hexdigest()[:12],
        "name": name,
        "roast": str(roast),
        "brewer": str(brewer),
        "temp": temp,
        "dial": dial,
        "steep_sec": steep_sec,
        "dose": dose,
        "recipe_id": compute_recipe_id(
            roast=str(roast), brewer=str(brewer), dial=dial,
            steep_sec=steep_sec, temp=temp, dose=dose,
        ),
        "note": str(note or "").strip(),
        "saved_at": saved_at,
    }
    recipes = _load()
    recipes.append(entry)
    _save(recipes)
    return entry


def delete_recipe(saved_id: str) -> bool:
    """Remove a saved recipe by its id. True when something was removed."""
    recipes = _load()
    kept = [r for r in recipes if r.get("id") != saved_id]
    if len(kept) == len(recipes):
        return False
    _save(kept)
    return True
