"""Phase 10 Step 6a — feedback.jsonl reader / writer.

Schema lives in docs/FEEDBACK_FORMAT.md (single source of truth). The Step 6
schema is pairwise + ordinal — every cup is judged against the previous one,
every answer is `>` / `=` / `<` (see PHASE10_STEP6_FEEDBACK_LOOP.md §4).

Append-only by design — corrections are new entries (a fresh comparison), not
in-place edits. This module is intentionally a thin shim: validate at the
boundary, append, read. No aggregation, no dedup, no DB — the refine workflow
is Claude in conversation reading the JSONL (see docs/FEEDBACK_FORMAT.md).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from models.sensory import AXIS_VIEW

_FEEDBACK_PATH = Path(__file__).resolve().parents[1] / "data" / "feedback.jsonl"

# Overall-preference answer — this cup vs the previous one (§4: no magnitude).
ORDINAL = {">", "=", "<"}
# Per-attribute answer — a direction, or "?" = noticed no difference / unsure.
# There is deliberately NO "=" here: fuzzy 2-cup taste memory cannot support a
# confident "this attribute is exactly equal", so the middle option is honestly
# "no directional signal". Phase 11 EXCLUDES "?" from model-error flagging and
# from calibration — only a clear ">" vs "<" disagreement is a real signal (§4).
ATTR_ORDINAL = {">", "?", "<"}
# The occasional absolute-anchor answer (§4 / §6) — independent of any comparison.
ALLOWED_ABSOLUTE = {"good", "ok", "bad"}
# Questionnaire groups: the 7 AXIS_VIEW roll-ups of the 10 model attributes.
QUESTIONNAIRE_GROUPS = tuple(AXIS_VIEW.keys())

# Optional legacy quick-chips. Kept permissive — tags are not the loop's signal.
ALLOWED_TAGS = {
    "acidic", "thin", "great-body", "bitter", "muted", "floral",
    "sweet", "harsh", "clean", "balanced", "fruity", "roasty",
}
EDIT_WINDOW_HOURS = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _clean_ordinal_map(value, field: str) -> dict | None:
    """Validate a per-attribute `{group: >/?/<}` map (attributes_vs /
    model_attributes_vs).

    Returns a canonical dict (unknown groups dropped) or None when empty.
    Raises ValueError on a malformed shape or a bad token. The vocabulary is
    ATTR_ORDINAL — `?` ("noticed no difference / unsure"), not `=`.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object of group -> >/?/<")
    out: dict[str, str] = {}
    for group, sign in value.items():
        if group not in QUESTIONNAIRE_GROUPS:
            continue  # tolerate stale group names — drop, don't fail
        if sign is None:
            continue
        if sign not in ATTR_ORDINAL:
            raise ValueError(f"{field}[{group}] must be one of {sorted(ATTR_ORDINAL)}")
        out[str(group)] = sign
    return out or None


def _clean_stars(value) -> int | None:
    if value is None:
        return None
    try:
        stars = int(value)
    except (TypeError, ValueError):
        raise ValueError("stars must be a 1-5 integer or null")
    if not 1 <= stars <= 5:
        raise ValueError("stars must be a 1-5 integer or null")
    return stars


def _clean_recipe(recipe) -> dict | None:
    """Canonicalise the brew snapshot. tds/ey/distance are optional and
    stale-able (recompute_entry refreshes them); temp/dial/dose/steep are the
    durable inputs."""
    if not recipe:
        return None
    try:
        snapshot = {
            "temp": float(recipe["temp"]),
            "dial": float(recipe["dial"]),
            "dose": float(recipe["dose"]),
            "steep_sec": int(recipe["steep_sec"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"recipe snapshot malformed: {exc}")
    for opt in ("tds", "ey", "distance"):
        raw = recipe.get(opt)
        snapshot[opt] = float(raw) if raw is not None else None
    return snapshot


def append_feedback(entry: dict) -> dict:
    """Validate & append one feedback entry to data/feedback.jsonl.

    Required (caller responsibility): recipe_id, roast, brewer. Adds the
    timestamp server-side. Returns the canonicalised entry.

    Raises ValueError on schema violations — validation happens here at the
    boundary so internal callers can trust a stored entry.
    """
    for key in ("recipe_id", "roast", "brewer"):
        if not entry.get(key):
            raise ValueError(f"feedback missing required field: {key}")

    overall = entry.get("overall")
    if overall is not None and overall not in ORDINAL:
        raise ValueError(f"overall must be one of {sorted(ORDINAL)} or null")

    absolute = entry.get("absolute")
    if absolute is not None and absolute not in ALLOWED_ABSOLUTE:
        raise ValueError(f"absolute must be one of {sorted(ALLOWED_ABSOLUTE)} or null")

    attributes_vs = _clean_ordinal_map(entry.get("attributes_vs"), "attributes_vs")
    model_attributes_vs = _clean_ordinal_map(
        entry.get("model_attributes_vs"), "model_attributes_vs"
    )

    stars = _clean_stars(entry.get("stars"))

    tags = entry.get("tags") or []
    if not isinstance(tags, list):
        raise ValueError("tags must be a list")
    tags = [str(t).strip().lower() for t in tags if str(t).strip()]

    comment = str(entry.get("comment") or "").strip()
    water_note = str(entry.get("water_note") or "").strip()

    compared_to = entry.get("compared_to")
    compared_to = str(compared_to) if compared_to else None

    if not (comment or overall or attributes_vs or absolute or stars or tags):
        raise ValueError(
            "feedback must include at least one of "
            "comment / overall / attributes_vs / absolute / stars / tags"
        )

    canonical = {
        "timestamp": entry.get("timestamp") or _now_iso(),
        "recipe_id": str(entry["recipe_id"]),
        "roast": str(entry["roast"]),
        "brewer": str(entry["brewer"]),
        "recipe": _clean_recipe(entry.get("recipe")),
        "compared_to": compared_to,
        "overall": overall,
        "attributes_vs": attributes_vs,
        "model_attributes_vs": model_attributes_vs,
        "absolute": absolute,
        "comment": comment,
        "stars": stars,
        "tags": tags,
        "water_note": water_note,
    }

    _FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _FEEDBACK_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(canonical, ensure_ascii=False) + "\n")
    return canonical


def read_all() -> list[dict]:
    """Read entire feedback.jsonl as a list of entries. Returns [] if missing.

    Tolerates legacy pre-Step-6 entries (label / water / rating fields) — they
    are returned verbatim; only their absent new fields differ."""
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
    """Recompute an entry's derived fields with the CURRENT model, from its
    immutable recipe inputs. Returns None when the entry has no recipe snapshot
    (legacy entry with nothing to derive from).

    feedback.jsonl is append-only: the stored recipe.tds/ey/distance is the
    as-submitted snapshot and is never mutated. This is the *current* projection
    — after a model recalibration the stored snapshot goes stale, so the history
    view should display this instead. temp/dial/dose/steep are durable; the rest
    are merely a projection of them through Layer 1 + Layer 2.
    """
    recipe = entry.get("recipe")
    if not recipe:
        return None

    from optimizer import score_logged_recipe  # lazy: keeps append/read light

    try:
        scored = score_logged_recipe(
            roast_code=str(entry["roast"]),
            brewer_size=str(entry["brewer"]),
            temp=float(recipe["temp"]),
            dial=float(recipe["dial"]),
            steep_sec=int(recipe["steep_sec"]),
            dose=float(recipe["dose"]),
        )
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "ey": round(scored["ey"], 3),
        "tds": round(scored["tds"], 4),
        "distance": round(scored["distance"], 4),
        "attributes": {k: round(v, 4) for k, v in scored["attributes"].items()},
    }


def update_feedback(timestamp: str, updates: dict) -> dict:
    """In-place edit of an existing entry within EDIT_WINDOW_HOURS of creation.

    Editable: comment, stars, tags, absolute, overall, attributes_vs — the
    answer fields. Immutable: recipe_id, roast, brewer, recipe snapshot,
    compared_to, model_attributes_vs — these reflect the brewing context and the
    model's as-rendered prediction and must not drift.

    Violates the append-only spirit of the JSONL log, but the short window
    confines the damage to the "misclick / UI bug" case. Beyond the window the
    entry is frozen; corrections must be new entries.
    """
    if not timestamp:
        raise ValueError("timestamp required")

    entries = read_all()
    target_idx = next(
        (i for i, e in enumerate(entries) if e.get("timestamp") == timestamp), None
    )
    if target_idx is None:
        raise ValueError(f"feedback entry not found: {timestamp}")
    target = entries[target_idx]

    try:
        created = datetime.fromisoformat(target["timestamp"]).astimezone(timezone.utc)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"entry timestamp malformed: {exc}")
    if datetime.now(timezone.utc) - created > timedelta(hours=EDIT_WINDOW_HOURS):
        raise ValueError(f"edit window expired ({EDIT_WINDOW_HOURS}h)")

    if "comment" in updates:
        target["comment"] = str(updates["comment"] or "").strip()

    if "stars" in updates:
        target["stars"] = _clean_stars(updates["stars"])

    if "tags" in updates:
        tags = updates["tags"] or []
        if not isinstance(tags, list):
            raise ValueError("tags must be a list")
        target["tags"] = [str(t).strip().lower() for t in tags if str(t).strip()]

    if "absolute" in updates:
        absolute = updates["absolute"]
        if absolute is not None and absolute not in ALLOWED_ABSOLUTE:
            raise ValueError(
                f"absolute must be one of {sorted(ALLOWED_ABSOLUTE)} or null"
            )
        target["absolute"] = absolute

    if "overall" in updates:
        overall = updates["overall"]
        if overall is not None and overall not in ORDINAL:
            raise ValueError(f"overall must be one of {sorted(ORDINAL)} or null")
        target["overall"] = overall

    if "attributes_vs" in updates:
        target["attributes_vs"] = _clean_ordinal_map(
            updates["attributes_vs"], "attributes_vs"
        )

    has_signal = any((
        target.get("comment"), target.get("overall"), target.get("attributes_vs"),
        target.get("absolute"), target.get("stars"), target.get("tags"),
    ))
    if not has_signal:
        raise ValueError(
            "entry must retain at least one of "
            "comment / overall / attributes_vs / absolute / stars / tags"
        )

    with _FEEDBACK_PATH.open("w", encoding="utf-8") as handle:
        for e in entries:
            handle.write(json.dumps(e, ensure_ascii=False) + "\n")
    return target
