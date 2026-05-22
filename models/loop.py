"""Phase 11 — recipe-generator loop engine.

Design + rationale: docs/PHASE11_LOOP_ENGINE.md.
Upstream blueprint: docs/PHASE10_STEP6_FEEDBACK_LOOP.md §3 (three-cup cycle),
§5 (search algorithm), §6 (Claude intervention), §7 (Phase 11 scope).

WHAT THIS IS
------------
A (1+lambda) evolutionary search, one independent loop per roast. The loop holds
ONE champion recipe and, each generation, proposes lambda=2 perturbed experiments.
The user brews them, answers the §4 pairwise questionnaire, and the loop advances
the champion toward whatever the user actually prefers — the per-roast IDEAL is a
moving target the loop is searching for (blueprint §1), not a fixed bullseye.

THE THREE-CUP CYCLE  [exp1, exp2, champion]
-------------------------------------------
Each cycle is three cups, brewed in order:

  1. exp1      — a champion perturbation (one knob moved).
  2. exp2      — a second, different champion perturbation.
  3. champion  — the cycle's *entering* champion, re-brewed.

Cup 3 is always the entering champion re-brewed (NOT a post-digest winner): this
is textbook (1+lambda) — the parent is fixed for the whole generation, selection
is a discrete between-generation step. It re-anchors taste memory (blueprint §3
"重泡冠軍取代記住冠軍"), gives a good cup to drink, and an absolute-anchor check.

DIGEST
------
Once all three cups carry feedback, the digest reads the pairwise `overall` edges
and picks the winner of {champion, exp1, exp2}. That winner becomes the NEXT
cycle's champion (a winning experiment is re-brewed one cycle later, as the next
cycle's cup 3). An experiment displaces the champion ONLY on a clear `>` win —
ties / missing edges keep the incumbent (blueprint §6 discipline 2: a single
memory-based comparison is noisy, do not over-trust it). Step size is set by an
annealing schedule, not by the data (blueprint §5).

SKIP
----
Skipping a proposal is *logistical* — "can't brew this cup" (out of beans, no
time). It re-rolls the slot with a fresh perturbation at the SAME radius
(blueprint §7) so the user cannot drift toward safe cups by skipping. It is NOT
taste feedback; only the skip count is recorded.

FLAGS
-----
detect_flags() is a pure scan of feedback.jsonl — it never touches loop state.
It finds groups where the model's prefilled direction (`model_attributes_vs`) and
the user's answer (`attributes_vs`) are clear-and-opposite, and reports a flag
when the same contradiction repeats. The loop never auto-edits the model; a flag
just invites a Claude conversation (blueprint §6 tier 2/3).
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

import constants
from models.feedback import read_all as read_all_feedback
from models.ideal import recipe_id as compute_recipe_id
from optimizer import evaluate_recipe, optimize

_STATE_PATH = Path(__file__).resolve().parents[1] / "data" / "loop_state.json"

# ── perturbation schedule (blueprint §5: step from a schedule, early bold) ────
# Each knob's perturbation radius decays geometrically per generation — bold
# early, fine late, like an annealing schedule. Floored at one grid step so a
# late-generation experiment is still a real, distinguishable change.
GENERATION_DECAY = 0.78        # radius multiplier per generation
DIAL_RADIUS_0 = 0.6            # dial units, generation 0
STEEP_RADIUS_0 = 90.0          # seconds, generation 0
DOSE_RADIUS_0_XL = 3.0         # grams, generation 0 (XL)
DOSE_RADIUS_0_STD = 1.5        # grams, generation 0 (standard)

# A contradiction must repeat this many times (same roast + group + direction)
# before it is surfaced as a flag — blueprint §6 discipline 2, one is noise.
FLAG_REPEAT_THRESHOLD = 2

_KNOBS = ("dial", "steep_sec", "dose")
_SLOT_ROLES = ("exp1", "exp2", "champion")


# ── persistence ──────────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load() -> dict:
    """Read data/loop_state.json — {roast: loop}. {} when the file is absent."""
    if not _STATE_PATH.exists():
        return {}
    try:
        with _STATE_PATH.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(state: dict) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _STATE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)


# ── knob grids ───────────────────────────────────────────────────────────────
def _dose_grid(roast: str, brewer_size: str, water_ml: float) -> tuple[float, float, float]:
    """(min, max, step) for dose — brewer capacity intersected with the roast's
    dose_per_100ml band, so a perturbation never proposes an impossible dose."""
    brewer = constants.BREWER_PRESETS[brewer_size]
    lo, hi = brewer["dose_min"], brewer["dose_max"]
    band = constants.ROAST_TABLE.get(roast, {}).get("dose_per_100ml")
    if band:
        lo = max(lo, band[0] * water_ml / 100.0)
        hi = min(hi, band[1] * water_ml / 100.0)
    step = 1.0 if brewer_size == "xl" else 0.5
    return lo, hi, step


def _grid(knob: str, roast: str, brewer_size: str, water_ml: float) -> tuple[float, float, float]:
    if knob == "dial":
        return 3.0, 7.5, constants.DIAL_STEP
    if knob == "steep_sec":
        return 30.0, 420.0, float(constants.STEEP_STEP)
    return _dose_grid(roast, brewer_size, water_ml)


def _snap(knob: str, value: float, grid: tuple[float, float, float]):
    """Round `value` onto the knob's grid and clamp into range."""
    lo, hi, step = grid
    snapped = round(value / step) * step
    snapped = min(max(snapped, lo), hi)
    if knob == "steep_sec":
        return int(round(snapped))
    return round(snapped, 1)


def _radius(knob: str, generation: int, brewer_size: str, grid: tuple[float, float, float]) -> float:
    """Perturbation radius for a knob at a generation — geometric decay, floored
    at one grid step (an experiment must always be a real, brewable change)."""
    decay = GENERATION_DECAY ** generation
    if knob == "dial":
        base = DIAL_RADIUS_0
    elif knob == "steep_sec":
        base = STEEP_RADIUS_0
    else:
        base = DOSE_RADIUS_0_XL if brewer_size == "xl" else DOSE_RADIUS_0_STD
    return max(base * decay, grid[2])


# ── perturbation ─────────────────────────────────────────────────────────────
def _knob_recipe(champion: dict) -> dict:
    """The bare {dial, steep_sec, dose} of a champion / recipe dict."""
    return {k: champion[k] for k in _KNOBS}


def _apply_move(champion: dict, knob: str, sign: int, generation: int,
                roast: str, brewer_size: str, water_ml: float) -> dict | None:
    """Champion recipe with one knob moved by `sign` * radius, snapped to grid.

    Returns None when the move is a no-op (the champion already sits at that
    edge of the grid, so the snapped result equals the champion).
    """
    grid = _grid(knob, roast, brewer_size, water_ml)
    radius = _radius(knob, generation, brewer_size, grid)
    moved = _snap(knob, champion[knob] + sign * radius, grid)
    if moved == _snap(knob, champion[knob], grid):
        return None
    recipe = _knob_recipe(champion)
    recipe[knob] = moved
    return recipe


def _valid_moves(champion: dict, generation: int, roast: str,
                 brewer_size: str, water_ml: float) -> list[tuple[tuple[str, int], dict]]:
    """Every single-knob move that produces a recipe different from the champion."""
    moves: list[tuple[tuple[str, int], dict]] = []
    for knob in _KNOBS:
        for sign in (1, -1):
            recipe = _apply_move(champion, knob, sign, generation,
                                 roast, brewer_size, water_ml)
            if recipe is not None:
                moves.append(((knob, sign), recipe))
    return moves


def _pick_experiment(moves: list, rng: random.Random,
                     exclude_knobs: set[str], exclude_moves: set[tuple[str, int]]):
    """Pick one move, preferring a knob not in `exclude_knobs` (so the cycle's
    two experiments perturb different knobs — clean attribution, blueprint §8).
    `exclude_moves` are moves already tried (a skipped slot must not re-roll the
    same recipe). Returns (move, recipe) or None when nothing is left."""
    pool = [m for m in moves if m[0] not in exclude_moves]
    if not pool:
        return None
    fresh = [m for m in pool if m[0][0] not in exclude_knobs]
    chosen_from = fresh or pool
    return rng.choice(chosen_from)


def _cycle_rng(roast: str, generation: int, cycle_index: int, salt: int = 0) -> random.Random:
    """Deterministic RNG for a (roast, generation, cycle, salt) — reproducible
    perturbations; `salt` advances on every skip re-roll."""
    return random.Random(f"{roast}|{generation}|{cycle_index}|{salt}")


def _new_slot(role: str, recipe: dict, move, roast: str, brewer_size: str,
              temp: float) -> dict:
    return {
        "role": role,
        "recipe": recipe,
        "recipe_id": compute_recipe_id(
            roast=roast, brewer=brewer_size, dial=recipe["dial"],
            steep_sec=recipe["steep_sec"], temp=temp, dose=recipe["dose"],
        ),
        "move": list(move) if move else None,
        "status": "pending",
        "skips": 0,
        "skipped": [],
        "feedback_timestamp": None,
        "feedback_overall": None,
        "feedback_compared_to": None,
    }


def _build_cycle(loop: dict, cycle_index: int) -> dict:
    """Build a fresh three-slot cycle: two champion perturbations + a champion
    re-brew. exp1 / exp2 perturb different knobs where possible."""
    champion = loop["champion"]
    generation = loop["generation"]
    roast, brewer, temp = loop["roast"], loop["brewer"], loop["temp"]
    water_ml = loop["water_ml"]
    rng = _cycle_rng(roast, generation, cycle_index)

    moves = _valid_moves(champion, generation, roast, brewer, water_ml)
    slots: list[dict] = []

    pick1 = _pick_experiment(moves, rng, set(), set())
    if pick1 is None:  # champion boxed into a corner — degenerate, re-brew it
        pick1 = ((None, 0), _knob_recipe(champion))
    slots.append(_new_slot("exp1", pick1[1], pick1[0], roast, brewer, temp))

    pick2 = _pick_experiment(
        moves, rng, {pick1[0][0]} if pick1[0][0] else set(), {pick1[0]},
    )
    if pick2 is None:
        pick2 = pick1
    slots.append(_new_slot("exp2", pick2[1], pick2[0], roast, brewer, temp))

    slots.append(_new_slot("champion", _knob_recipe(champion), None,
                           roast, brewer, temp))
    return {"index": cycle_index, "slots": slots}


# ── ordinal algebra (digest) ─────────────────────────────────────────────────
_INVERT = {">": "<", "<": ">", "=": "="}


def _invert(edge):
    """Flip an A-vs-B verdict to B-vs-A. None stays None."""
    return _INVERT.get(edge) if edge else None


def _compose(a_vs_b, b_vs_c):
    """Transitively chain A-vs-B and B-vs-C into A-vs-C. Returns None when the
    two edges point opposite ways (the chain is genuinely ambiguous)."""
    if a_vs_b is None or b_vs_c is None:
        return None
    if a_vs_b == "=" and b_vs_c == "=":
        return "="
    if a_vs_b in (">", "=") and b_vs_c in (">", "="):
        return ">"
    if a_vs_b in ("<", "=") and b_vs_c in ("<", "="):
        return "<"
    return None  # (>, <) or (<, >) — ambiguous


def _select_winner(exp1_vs_champ, exp2_vs_champ, exp1_vs_exp2) -> str:
    """Pick the cycle winner. An experiment takes the crown only on a clear `>`
    over the champion; ties / unknown edges keep the incumbent (blueprint §6)."""
    exp1_beats = exp1_vs_champ == ">"
    exp2_beats = exp2_vs_champ == ">"
    if exp1_beats and exp2_beats:
        return "exp2" if exp1_vs_exp2 == "<" else "exp1"
    if exp1_beats:
        return "exp1"
    if exp2_beats:
        return "exp2"
    return "champion"


def _digest(loop: dict) -> dict:
    """Resolve a fully-brewed cycle: pick the winner, promote it to the next
    cycle's champion, archive the cycle, advance the generation."""
    slots = {s["role"]: s for s in loop["cycle"]["slots"]}
    exp1, exp2, champ = slots["exp1"], slots["exp2"], slots["champion"]

    # exp1 vs exp2 — from exp2's feedback, compared to exp1
    e_exp2_vs_exp1 = (
        exp2["feedback_overall"]
        if exp2["feedback_compared_to"] == exp1["feedback_timestamp"]
        else None
    )
    # champion vs exp2 — from the champion slot's feedback, compared to exp2
    e_champ_vs_exp2 = (
        champ["feedback_overall"]
        if champ["feedback_compared_to"] == exp2["feedback_timestamp"]
        else None
    )
    # exp1 vs champion — DIRECT when exp1 was compared to the prior champion cup
    e_exp1_vs_champ = (
        exp1["feedback_overall"]
        if exp1["feedback_compared_to"]
        and exp1["feedback_compared_to"] == loop.get("last_champion_cup")
        else None
    )

    exp1_vs_exp2 = _invert(e_exp2_vs_exp1)
    exp2_vs_champ = _invert(e_champ_vs_exp2)
    if e_exp1_vs_champ is not None:
        exp1_vs_champ = e_exp1_vs_champ
    else:  # no direct edge (e.g. cycle 1) — chain exp1 -> exp2 -> champion
        exp1_vs_champ = _compose(exp1_vs_exp2, exp2_vs_champ)

    winner_role = _select_winner(exp1_vs_champ, exp2_vs_champ, exp1_vs_exp2)
    winner_slot = slots[winner_role]

    champion_before = dict(loop["champion"])
    if winner_role == "champion":
        new_champion = dict(loop["champion"])
        new_champion["source"] = "cycle"
    else:
        recipe = winner_slot["recipe"]
        new_champion = {
            **recipe,
            "recipe_id": winner_slot["recipe_id"],
            "source": "cycle",
        }

    loop.setdefault("history", []).append({
        "cycle_index": loop["cycle"]["index"],
        "generation": loop["generation"],
        "winner_role": winner_role,
        "edges": {
            "exp1_vs_champ": exp1_vs_champ,
            "exp2_vs_champ": exp2_vs_champ,
            "exp1_vs_exp2": exp1_vs_exp2,
        },
        "champion_before": champion_before,
        "champion_after": {k: new_champion[k] for k in (*_KNOBS, "recipe_id")},
        "digested_at": _now_iso(),
    })

    loop["champion"] = new_champion
    loop["generation"] += 1
    loop["last_champion_cup"] = champ["feedback_timestamp"]
    loop["cycle"] = _build_cycle(loop, loop["cycle"]["index"] + 1)
    loop["updated_at"] = _now_iso()
    return loop


# ── public API ───────────────────────────────────────────────────────────────
def load_loops() -> dict:
    """All per-roast loops keyed by roast (raw stored state)."""
    return _load()


def get_loop(roast: str) -> dict | None:
    """The loop for one roast, or None when no loop has been started."""
    return _load().get(roast)


def start_loop(roast: str, brewer: str = "xl", temp: float | None = None) -> dict:
    """Start (or hard-reset) the loop for a roast.

    Generation 0's champion is the optimizer's Top-1 for (roast, brewer, temp) —
    model-seeded, not random (blueprint §2). Any existing loop for the roast is
    discarded — this doubles as the reset path.
    """
    if temp is None:
        temp = constants.DEFAULT_TEMP[roast]
    water_ml = constants.BREWER_PRESETS[brewer]["water_ml"]

    seed = optimize(roast_code=roast, brewer_size=brewer, temp=temp, top_n=1)[0]
    champion = {
        "dial": seed["dial"],
        "steep_sec": seed["steep_sec"],
        "dose": seed["dose"],
        "recipe_id": seed["recipe_id"],
        "source": "seed",
    }
    loop = {
        "roast": roast,
        "brewer": brewer,
        "temp": float(temp),
        "water_ml": water_ml,
        "generation": 0,
        "champion": champion,
        "last_champion_cup": None,
        "history": [],
        "started_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    loop["cycle"] = _build_cycle(loop, 1)

    state = _load()
    state[roast] = loop
    _save(state)
    return loop


def reset_loop(roast: str, brewer: str | None = None,
               temp: float | None = None) -> dict:
    """Discard a roast's loop and start a fresh one. Reuses the existing loop's
    brewer / temp unless overridden — the webapp 'reset' button (blueprint §7)."""
    existing = get_loop(roast)
    if existing:
        brewer = brewer or existing["brewer"]
        temp = temp if temp is not None else existing["temp"]
    return start_loop(roast, brewer=brewer or "xl", temp=temp)


def _current_slot(loop: dict) -> dict | None:
    """The first slot of the current cycle still awaiting a brew."""
    for slot in loop["cycle"]["slots"]:
        if slot["status"] == "pending":
            return slot
    return None


def _suggested_compared_to(loop: dict, slot: dict) -> str | None:
    """Timestamp of the cup this slot should be tasted against — the previous
    cup in brew order (blueprint §4: judge vs the previous cup)."""
    slots = loop["cycle"]["slots"]
    role = slot["role"]
    if role == "exp1":
        return loop.get("last_champion_cup")  # cross-cycle: prior champion cup
    prev = {"exp2": "exp1", "champion": "exp2"}[role]
    prev_slot = next(s for s in slots if s["role"] == prev)
    return prev_slot["feedback_timestamp"]


def current_proposal(roast: str) -> dict | None:
    """The cup the loop is asking the user to brew next, fully evaluated.

    Returns None when there is no loop. The returned dict carries the same
    `attributes` / `ideal` / `distance` shape an optimizer result does, plus the
    loop context (cycle index, role, generation, skip count, champion).
    """
    loop = get_loop(roast)
    if loop is None:
        return None
    slot = _current_slot(loop)
    if slot is None:  # unreachable — a digest always builds a fresh cycle
        return None

    evaluated = evaluate_recipe(
        roast_code=loop["roast"], brewer_size=loop["brewer"], temp=loop["temp"],
        dial=slot["recipe"]["dial"], steep_sec=slot["recipe"]["steep_sec"],
        dose=slot["recipe"]["dose"],
    )
    role_index = {"exp1": 1, "exp2": 2, "champion": 3}[slot["role"]]
    return {
        **evaluated,
        "role": slot["role"],
        "role_index": role_index,
        "cycle_index": loop["cycle"]["index"],
        "generation": loop["generation"],
        "skips": slot["skips"],
        "suggested_compared_to": _suggested_compared_to(loop, slot),
        "is_champion_rebrew": slot["role"] == "champion",
        "champion": loop["champion"],
    }


def register_feedback(roast: str, recipe_id: str, entry: dict) -> dict:
    """Record a feedback entry against the matching cycle slot; digest + advance
    when all three cups of the cycle are in.

    Called by the webapp right after models.feedback.append_feedback. A recipe_id
    that is not in the current cycle (e.g. feedback on an optimizer Top-N card,
    or a stale cycle) is a no-op. Returns {matched, digested, loop}.
    """
    state = _load()
    loop = state.get(roast)
    if loop is None:
        return {"matched": False, "digested": False, "loop": None}

    slot = next(
        (s for s in loop["cycle"]["slots"] if s["recipe_id"] == recipe_id), None
    )
    if slot is None:
        return {"matched": False, "digested": False, "loop": loop}

    slot["status"] = "brewed"
    slot["feedback_timestamp"] = entry.get("timestamp")
    slot["feedback_overall"] = entry.get("overall")
    slot["feedback_compared_to"] = entry.get("compared_to")
    loop["updated_at"] = _now_iso()

    digested = all(s["status"] == "brewed" for s in loop["cycle"]["slots"])
    if digested:
        loop = _digest(loop)

    state[roast] = loop
    _save(state)
    return {"matched": True, "digested": digested, "loop": loop}


def skip_proposal(roast: str, recipe_id: str) -> dict:
    """Skip the current proposal — re-roll the slot at the SAME radius.

    Skip is logistical, never taste feedback (blueprint §7): re-rolling at the
    same exploration radius keeps the user from drifting toward safe cups by
    skipping. The champion re-brew slot cannot be skipped (it is not a
    perturbation). Returns {skipped, loop}.
    """
    state = _load()
    loop = state.get(roast)
    if loop is None:
        return {"skipped": False, "loop": None}

    slot = next(
        (s for s in loop["cycle"]["slots"]
         if s["recipe_id"] == recipe_id and s["status"] == "pending"), None
    )
    if slot is None or slot["role"] == "champion":
        return {"skipped": False, "loop": loop}

    cycle = loop["cycle"]
    sibling = next(
        s for s in cycle["slots"]
        if s["role"] in ("exp1", "exp2") and s is not slot
    )
    moves = _valid_moves(loop["champion"], loop["generation"],
                         loop["roast"], loop["brewer"], loop["water_ml"])
    exclude = {tuple(m) for m in slot.get("tried_moves", [])}
    if slot["move"]:
        exclude.add(tuple(slot["move"]))
    if sibling["move"]:
        exclude.add(tuple(sibling["move"]))

    rng = _cycle_rng(loop["roast"], loop["generation"], cycle["index"],
                     salt=slot["skips"] + 1)
    pick = _pick_experiment(
        moves, rng,
        {sibling["move"][0]} if sibling.get("move") else set(),
        exclude,
    )
    if pick is None:  # nothing distinct left — re-roll ignoring the sibling
        pick = _pick_experiment(moves, rng, set(), exclude) \
            or _pick_experiment(moves, rng, set(), set())
    if pick is None:
        return {"skipped": False, "loop": loop}

    slot.setdefault("tried_moves", [])
    if slot["move"]:
        slot["tried_moves"].append(slot["move"])
    slot["skipped"].append(slot["recipe_id"])
    slot["skips"] += 1

    move, recipe = pick
    slot["recipe"] = recipe
    slot["move"] = list(move)
    slot["recipe_id"] = compute_recipe_id(
        roast=loop["roast"], brewer=loop["brewer"], dial=recipe["dial"],
        steep_sec=recipe["steep_sec"], temp=loop["temp"], dose=recipe["dose"],
    )
    loop["updated_at"] = _now_iso()
    state[roast] = loop
    _save(state)
    return {"skipped": True, "loop": loop}


# ── flag detection (blueprint §6 tier 2) ─────────────────────────────────────
def detect_flags() -> list[dict]:
    """Scan feedback.jsonl for repeated model direction-errors.

    A flag = a (roast, questionnaire-group) where the model's prefilled direction
    (`model_attributes_vs`) and the user's answer (`attributes_vs`) are
    clear-and-OPPOSITE (`>` vs `<`), and that same contradiction has happened at
    least FLAG_REPEAT_THRESHOLD times. `?` on either side is skipped — it is an
    absence of signal, not a contradiction (docs/FEEDBACK_FORMAT.md). The loop
    only records flags; acting on them is a Claude conversation (§6 tier 3).
    """
    buckets: dict[tuple[str, str, str], list[dict]] = {}
    for entry in read_all_feedback():
        model = entry.get("model_attributes_vs")
        user = entry.get("attributes_vs")
        if not model or not user:
            continue
        roast = entry.get("roast", "?")
        for group, user_sign in user.items():
            model_sign = model.get(group)
            if model_sign not in (">", "<") or user_sign not in (">", "<"):
                continue
            if model_sign == user_sign:
                continue
            # model said "more", user said "less" -> model OVER-predicts the rise
            direction = "model_over" if model_sign == ">" else "model_under"
            buckets.setdefault((roast, group, direction), []).append(entry)

    flags: list[dict] = []
    for (roast, group, direction), entries in sorted(buckets.items()):
        if len(entries) < FLAG_REPEAT_THRESHOLD:
            continue
        flags.append({
            "roast": roast,
            "group": group,
            "direction": direction,
            "count": len(entries),
            "samples": [
                {"timestamp": e.get("timestamp"), "comment": e.get("comment", "")}
                for e in entries[-3:]
            ],
        })
    return flags
