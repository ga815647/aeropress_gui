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

THE THREE-CUP CYCLE  [exp1, champion, exp2]
-------------------------------------------
Each cycle is three cups, brewed in order:

  1. exp1      — a champion perturbation (one knob moved).
  2. champion  — the cycle's *entering* champion, re-brewed in the middle.
  3. exp2      — a second, different champion perturbation.

The champion is re-brewed in cup 2 (NOT a post-digest winner): this is textbook
(1+lambda) — the parent is fixed for the whole generation; selection is a
discrete between-generation step. Brewing the champion in the MIDDLE re-anchors
taste memory between the two experiments — both experiments thus get compared
(via cup-adjacent memory) to a fresh champion taste:

  cup 1 (exp1)  ── memory adjacent ──>  cup 2 (champ)  =>  exp1 vs champ direct
  cup 2 (champ) ── memory adjacent ──>  cup 3 (exp2)   =>  exp2 vs champ direct

Both experiment↔champion edges are direct in EVERY cycle (including cycle 1) —
no transitive composition. (This was the revision over blueprint §3's original
[exp1, exp2, champion] ordering, which left the cycle-1 exp1↔champion edge to
composition.)

DIGEST
------
Once all three cups carry feedback, the digest reads the two within-cycle
pairwise `overall` edges:

  cup 2's `overall` (champion vs exp1)  -- invert -->  exp1 vs champion
  cup 3's `overall` (exp2 vs champion)  ----------->   exp2 vs champion

Both edges are direct in every cycle. An experiment displaces the champion ONLY
on a clear `>` win; ties / missing edges keep the incumbent (blueprint §6
discipline 2: a single memory-based comparison is noisy, do not over-trust it).
When both experiments beat the champion, the within-cycle exp1↔exp2 edge is not
available in this ordering — `_select_winner` falls back to picking exp1
deterministically (rare case; conservative). The winner becomes the NEXT cycle's
champion (a winning experiment is re-brewed one cycle later as the next cycle's
cup 2). Step size is set by an annealing schedule, not by data (blueprint §5).

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

# ── informed-leap exp2 (Iterated Local Search "kick") ───────────────────────
# Pure single-knob coordinate descent (the original Phase 11 loop) can't escape
# saddle points where a multi-knob *joint* recipe is preferred but each
# 1-knob neighbour is worse-or-equal. So exp2 is a "leap": pulled from the
# optimizer's Top-N (the model surrogate's good candidates) but filtered to
# differ from the champion in at least LEAP_KNOB_DIFF_MIN knobs. exp1 remains
# single-knob — attribution stays clean for the local refine, the leap probes
# joint regions. Fallback to single-knob exp2 if no leap candidate qualifies
# (model thinks the entire Top-N is cup-adjacent to the champion).
LEAP_TOP_N = 30
LEAP_KNOB_DIFF_MIN = 2

# Extended Gold Cup sanity gate — don't let the surrogate's far-Top-N leap
# land at an under-extracted / over-concentrated cup just because the model
# *thinks* its predicted attributes look fine. Strict SCA is TDS 1.15–1.35
# / EY 18–22; we extend the TDS upper bound to 1.40 and the EY lower bound
# to 17.0 so the leap can move within BOTH project anchors' known-good
# regions (medium_light ⭐5 at TDS≈1.37 and light tim ⭐4 at EY≈17.1 each
# sit just outside strict SCA in a different axis). Universal sanity
# guards still hold: TDS < 1.15 (under-concentrated weak cup) / TDS > 1.40
# (over-concentrated muddy cup) / EY < 17 (severely under-extracted sour) /
# EY > 22 (over-extracted bitter/astringent) all still excluded.
GOLD_CUP_TDS_RANGE = (1.15, 1.40)   # extended Gold Cup brew strength, %
GOLD_CUP_EY_RANGE = (17.0, 22.0)    # extended Gold Cup extraction yield, %

# ── iso-(TDS,EY) exp1 (probe Layer 2's b_temp=0 + weak _GRIND_SLOPE) ─────────
# Layer 2 (`models/sensory.py`) holds b_temp=0 (Batali 2020: temp doesn't change
# flavour at fixed TDS/EY) and weak _GRIND_SLOPE (only Thick.viscous +
# Astringent have non-zero grind sensitivity). So the model says "iso-(TDS,EY)
# cups are flavour-equivalent regardless of how you got there" — which is the
# Layer 2 assumption with the LEAST training data behind it. exp1 = iso-jump
# directly probes this assumption: pick a grid recipe with the same TDS/EY as
# the champion (within ε), but structurally different (≥ LEAP_KNOB_DIFF_MIN
# knobs different). If the user tastes a difference → model's b_temp=0 / weak-
# grind assumption is wrong → high-information feedback. If not → confirms
# the iso-equivalence assumption in this region. No Gold Cup gate on iso (it
# inherits the champion's TDS/EY by construction — champion's own sanity IS
# the sanity check).
ISO_TDS_TOL = 0.05      # % — tighter than a refractometer's measurement noise
ISO_EY_TOL = 0.5        # pp — 1/8 of the Gold Cup EY width (4 pp)

# Per-roast steep upper bound for iso + leap proposals — long immersion is a
# Layer-1 extrapolation (cotter trained at ~60–240 s) where Layer 2 can't
# capture the real physics: volatile-aromatic dissipation, brewer-temperature
# decay, cooling-induced selectivity shift. Model predicts identical TDS/EY
# but two cups at the same TDS/EY don't taste the same when one is 60 s and
# the other 420 s. Light roasts are the most sensitive — Nordic-style filter
# is 60–120 s; past ~180 s the volatiles are gone. Both iso and leap candidate
# scans filter against this cap; the optimizer's grid itself stays open (the
# user's seed champion can sit wherever IDEAL puts it).
STEEP_MAX_BY_ROAST = {
    "light":           180,     # Nordic 60-120s; >180s = muddled volatiles
    "medium_light":    240,     # Hoffmann 120s, longer ~210s upper extreme
    "medium":          270,
    "moderately_dark": 300,
}
_STEEP_MAX_FALLBACK = 300

_KNOBS = ("dial", "steep_sec", "dose")
_SLOT_ROLES = ("exp1", "champion", "exp2")  # brew order — see module doc


# ── persistence ──────────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load() -> dict:
    """Read data/loop_state.json — {roast: loop}. {} when the file is absent."""
    if not _STATE_PATH.exists():
        return {}
    try:
        with _STATE_PATH.open(encoding="utf-8") as handle:
            state = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {}
    return _migrate(state)


def _migrate(state: dict) -> dict:
    """Lossless in-place migrations for pre-2026-05-23 loop_state.json files.

    1. Field rename: `last_champion_cup` -> `last_cup` (the cross-cycle anchor
       in the new [exp1, champion, exp2] ordering is prev cycle's exp2, not its
       champion-rebrew — so the old name is misleading).
    2. Slot reorder: old `[exp1, exp2, champion]` -> new `[exp1, champion, exp2]`,
       but ONLY when all three slots are still pending. A cycle whose brewed
       feedback already chained to specific neighbor cups under the old order
       is not silently rearranged (its `compared_to` edges would no longer
       match the new digest's expectations) — the user should reset that loop.
    """
    for loop in state.values():
        if "last_champion_cup" in loop and "last_cup" not in loop:
            loop["last_cup"] = loop.pop("last_champion_cup")
        cycle = loop.get("cycle") or {}
        slots = cycle.get("slots") or []
        roles = [s.get("role") for s in slots]
        if (roles == ["exp1", "exp2", "champion"]
                and all(s.get("status") == "pending" for s in slots)):
            by_role = {s["role"]: s for s in slots}
            cycle["slots"] = [by_role["exp1"], by_role["champion"], by_role["exp2"]]
    return state


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
              temp: float, kind: str | None = None) -> dict:
    """Build a cycle slot. `kind` annotates how an experiment was generated:
    "single" = local single-knob perturbation, "leap" = surrogate-guided
    multi-knob jump (informed leap), None = champion re-brew slot."""
    return {
        "role": role,
        "recipe": recipe,
        "recipe_id": compute_recipe_id(
            roast=roast, brewer=brewer_size, dial=recipe["dial"],
            steep_sec=recipe["steep_sec"], temp=temp, dose=recipe["dose"],
        ),
        "move": list(move) if move else None,
        "kind": kind,
        "status": "pending",
        "skips": 0,
        "skipped": [],
        "feedback_timestamp": None,
        "feedback_overall": None,
        "feedback_compared_to": None,
    }


def _informed_leap_candidate(loop: dict, exp1_recipe: dict,
                             extra_excluded_ids: set = frozenset()):
    """Surrogate-guided exp2 candidate — the Iterated Local Search "kick".

    Strategy: pull the optimizer's Top-N (model says it's good — close to the
    roast IDEAL), then filter to recipes that
    (a) differ from the champion in ≥ LEAP_KNOB_DIFF_MIN knobs (true multi-knob
        leap, escapes coordinate-descent saddles),
    (b) are not the exp1 recipe (don't duplicate the local-refine candidate),
    (c) have no prior feedback in the log (every brewed cup should be new info),
    (d) are not in `extra_excluded_ids` (used by skip re-roll to avoid the
        recipe the user just declined).
    Among the survivors, pick the one structurally MOST distant from the
    champion — maximize information gain per cup.

    Returns the knob recipe dict, or None when nothing qualifies (e.g. the
    model thinks the entire Top-N is cup-adjacent to the champion). The
    caller falls back to single-knob exp2 when None.
    """
    champion = loop["champion"]
    champ_knobs = _knob_recipe(champion)
    exp1_id = compute_recipe_id(
        roast=loop["roast"], brewer=loop["brewer"],
        dial=exp1_recipe["dial"], steep_sec=exp1_recipe["steep_sec"],
        temp=loop["temp"], dose=exp1_recipe["dose"],
    )

    try:
        candidates = optimize(
            roast_code=loop["roast"], brewer_size=loop["brewer"],
            temp=loop["temp"], top_n=LEAP_TOP_N,
        )
    except (KeyError, IndexError):  # bad roast / empty grid — no leap
        return None

    brewed_ids = {
        e.get("recipe_id") for e in read_all_feedback() if e.get("recipe_id")
    }
    excluded = brewed_ids | set(extra_excluded_ids) | {exp1_id}

    dose_step = 1.0 if loop["brewer"] == "xl" else 0.5

    def _normed_l1(k):
        """Distance to champion in normalised grid-steps (each knob counted in
        its own step units so dial vs steep vs dose are commensurable)."""
        return (
            abs(k["dial"] - champ_knobs["dial"]) / constants.DIAL_STEP
            + abs(k["steep_sec"] - champ_knobs["steep_sec"]) / constants.STEEP_STEP
            + abs(k["dose"] - champ_knobs["dose"]) / dose_step
        )

    steep_cap = STEEP_MAX_BY_ROAST.get(loop["roast"], _STEEP_MAX_FALLBACK)
    far = []
    for c in candidates:
        if c["recipe_id"] in excluded:
            continue
        # Per-roast steep cap — long immersion is Layer-1 extrapolation; model
        # predicts same TDS/EY at 60 s and 420 s but the cup tastes wildly
        # different (volatile-aromatic loss, temperature decay).
        if c["steep_sec"] > steep_cap:
            continue
        # SCA Gold Cup gate: a leap that lands outside the universally-good
        # box is a dud regardless of how good the model says its attributes
        # are. (The champion may itself sit slightly outside — that's its
        # business; the leap proposal must stay in the box.)
        if not (GOLD_CUP_TDS_RANGE[0] <= c["tds"] <= GOLD_CUP_TDS_RANGE[1]):
            continue
        if not (GOLD_CUP_EY_RANGE[0] <= c["ey"] <= GOLD_CUP_EY_RANGE[1]):
            continue
        c_knobs = {k: c[k] for k in _KNOBS}
        if c_knobs == champ_knobs:
            continue
        knob_diffs = sum(1 for k in _KNOBS if c_knobs[k] != champ_knobs[k])
        if knob_diffs < LEAP_KNOB_DIFF_MIN:
            continue
        far.append(c_knobs)

    if not far:
        return None
    far.sort(key=_normed_l1, reverse=True)
    return far[0]


def _iso_tds_ey_candidate(loop: dict, extra_excluded_ids: set = frozenset()):
    """Pick an iso-(TDS,EY) exp1 candidate — Layer 1 grid scan for recipes
    that match the champion's TDS and EY within ISO_TDS_TOL / ISO_EY_TOL,
    differ structurally in ≥ LEAP_KNOB_DIFF_MIN knobs, and have no prior
    feedback in the log. Returns the knob recipe dict, or None when nothing
    qualifies (caller falls back to single-knob exp1).

    Cheaper than the optimizer Top-N path because it only runs Layer 1
    (skips Layer 2 + distance). Direct iteration over the same grid the
    optimizer uses — dose values via `optimizer._dose_values` for parity.
    """
    from optimizer import _dose_values as _optimizer_dose_values
    from models.layer1 import brew as _layer1_brew

    champ_knobs = _knob_recipe(loop["champion"])
    roast = loop["roast"]
    brewer = loop["brewer"]
    temp = loop["temp"]
    water_ml = loop["water_ml"]

    # Champion's own TDS/EY via Layer 1 — the target for iso matching.
    cl1 = _layer1_brew(roast, temp, champ_knobs["dial"],
                      champ_knobs["steep_sec"], champ_knobs["dose"], water_ml)
    tds_target = cl1["tds"]
    ey_target = cl1["ey"]

    brewed_ids = {
        e.get("recipe_id") for e in read_all_feedback() if e.get("recipe_id")
    }
    excluded = brewed_ids | set(extra_excluded_ids)

    dose_step = 1.0 if brewer == "xl" else 0.5
    doses = _optimizer_dose_values(roast, brewer, water_ml, None, None, None)

    def _normed_l1(k):
        return (
            abs(k["dial"] - champ_knobs["dial"]) / constants.DIAL_STEP
            + abs(k["steep_sec"] - champ_knobs["steep_sec"]) / constants.STEEP_STEP
            + abs(k["dose"] - champ_knobs["dose"]) / dose_step
        )

    steep_cap = STEEP_MAX_BY_ROAST.get(roast, _STEEP_MAX_FALLBACK)
    candidates = []
    for dial_x10 in range(30, 76):
        dial = dial_x10 / 10
        for steep in range(30, steep_cap + 1, constants.STEEP_STEP):
            for dose in doses:
                l1 = _layer1_brew(roast, temp, dial, steep, dose, water_ml)
                if abs(l1["tds"] - tds_target) > ISO_TDS_TOL:
                    continue
                if abs(l1["ey"] - ey_target) > ISO_EY_TOL:
                    continue
                k = {"dial": dial, "steep_sec": steep, "dose": dose}
                if k == champ_knobs:
                    continue
                knob_diffs = sum(1 for x in _KNOBS if k[x] != champ_knobs[x])
                if knob_diffs < LEAP_KNOB_DIFF_MIN:
                    continue
                rid = compute_recipe_id(
                    roast=roast, brewer=brewer, dial=dial,
                    steep_sec=steep, temp=temp, dose=dose,
                )
                if rid in excluded:
                    continue
                candidates.append(k)

    if not candidates:
        return None
    candidates.sort(key=_normed_l1, reverse=True)
    return candidates[0]


def override_to_single_knob(roast: str, recipe_id: str, knob: str,
                            sign: int) -> dict:
    """User-triggered single-knob override: replace a slot's recipe with a
    single-knob perturbation of the CHAMPION along (knob, sign). Used when
    the user has a specific hypothesis ("what does dial +1 do here?") that
    the automatic iso / leap can't answer. Attribution stays clean — the
    slot's `kind` becomes "single" and `move` records the (knob, sign).

    Constraints: the slot must be pending (not yet brewed); the champion
    re-brew slot can't be overridden; the move must not be a no-op at the
    grid edge.
    """
    if knob not in _KNOBS:
        return {"overridden": False, "reason": f"unknown knob: {knob}"}
    if sign not in (-1, 1):
        return {"overridden": False, "reason": "sign must be +1 or -1"}

    state = _load()
    loop = state.get(roast)
    if loop is None:
        return {"overridden": False, "reason": "no active loop", "loop": None}

    slot = next(
        (s for s in loop["cycle"]["slots"] if s["recipe_id"] == recipe_id), None
    )
    if slot is None:
        return {"overridden": False, "reason": "recipe not in current cycle",
                "loop": loop}
    if slot["role"] == "champion":
        return {"overridden": False, "reason": "cannot override champion slot",
                "loop": loop}
    if slot["status"] == "brewed":
        return {"overridden": False, "reason": "slot already brewed",
                "loop": loop}

    new_recipe = _apply_move(
        loop["champion"], knob, sign, loop["generation"],
        loop["roast"], loop["brewer"], loop["water_ml"],
    )
    if new_recipe is None:
        return {"overridden": False,
                "reason": f"{knob} {sign:+d} is a no-op (champion at grid edge)",
                "loop": loop}

    slot["recipe"] = new_recipe
    slot["move"] = [knob, sign]
    slot["kind"] = "single"
    slot["recipe_id"] = compute_recipe_id(
        roast=loop["roast"], brewer=loop["brewer"], dial=new_recipe["dial"],
        steep_sec=new_recipe["steep_sec"], temp=loop["temp"],
        dose=new_recipe["dose"],
    )
    loop["updated_at"] = _now_iso()
    state[roast] = loop
    _save(state)
    return {"overridden": True, "loop": loop}


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

    # exp1 — iso-(TDS,EY) jump: same model-predicted TDS/EY as champion but
    # structurally different (≥ LEAP_KNOB_DIFF_MIN knobs). Probes the model's
    # weakest assumption (b_temp=0 + weak _GRIND_SLOPE). Falls back to single-
    # knob if no iso candidate qualifies (very tight grid / corner champion).
    iso_recipe = _iso_tds_ey_candidate(loop)
    if iso_recipe is not None:
        exp1_recipe = iso_recipe
        exp1_move = None        # iso has no single (knob, sign)
        exp1_kind = "iso"
    else:
        pick1 = _pick_experiment(moves, rng, set(), set())
        if pick1 is None:   # champion boxed into a corner — degenerate, re-brew
            pick1 = ((None, 0), _knob_recipe(champion))
        exp1_recipe = pick1[1]
        exp1_move = pick1[0]
        exp1_kind = "single"

    # exp2 — informed leap (Iterated Local Search "kick", multi-knob from the
    # surrogate's Top-N, gated by extended Gold Cup). Falls back to single-knob
    # when no Gold-Cup-compliant far candidate exists.
    leap_recipe = _informed_leap_candidate(loop, exp1_recipe)
    if leap_recipe is not None:
        exp2_recipe = leap_recipe
        exp2_move = None
        exp2_kind = "leap"
    else:
        excl_knob = ({exp1_move[0]} if exp1_move and exp1_move[0] else set())
        excl_move = ({tuple(exp1_move)} if exp1_move else set())
        pick2 = _pick_experiment(moves, rng, excl_knob, excl_move)
        if pick2 is None:
            pick2 = ((None, 0), _knob_recipe(champion))
        exp2_recipe = pick2[1]
        exp2_move = pick2[0]
        exp2_kind = "single"

    # Brew order [exp1, champion, exp2] — champion in the middle so BOTH
    # experiments are cup-adjacent to it (direct exp↔champion edges, every cycle).
    slots.append(_new_slot("exp1", exp1_recipe, exp1_move, roast, brewer, temp,
                           kind=exp1_kind))
    slots.append(_new_slot("champion", _knob_recipe(champion), None,
                           roast, brewer, temp))
    slots.append(_new_slot("exp2", exp2_recipe, exp2_move, roast, brewer, temp,
                           kind=exp2_kind))
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
    cycle's champion, archive the cycle, advance the generation.

    With the [exp1, champion, exp2] brew order, both experiment↔champion edges
    are direct within the cycle — no composition needed (uniform cycle 1+).
    """
    slots = {s["role"]: s for s in loop["cycle"]["slots"]}
    exp1, champ, exp2 = slots["exp1"], slots["champion"], slots["exp2"]

    # cup 2: champion compared to exp1 -> champion vs exp1 (-> invert for exp1)
    e_champ_vs_exp1 = (
        champ["feedback_overall"]
        if champ["feedback_compared_to"] == exp1["feedback_timestamp"]
        else None
    )
    # cup 3: exp2 compared to champion -> exp2 vs champion (direct)
    e_exp2_vs_champ = (
        exp2["feedback_overall"]
        if exp2["feedback_compared_to"] == champ["feedback_timestamp"]
        else None
    )
    exp1_vs_champ = _invert(e_champ_vs_exp1)
    exp2_vs_champ = e_exp2_vs_champ
    # exp1↔exp2 is not within-cycle in this ordering — _select_winner falls
    # back to "exp1 wins" deterministically when both beat the champion.
    exp1_vs_exp2 = None

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
        "exp2_kind": exp2.get("kind"),      # "leap" / "single" — trace which kicks win
        "edges": {
            "exp1_vs_champ": exp1_vs_champ,
            "exp2_vs_champ": exp2_vs_champ,
            "exp1_vs_exp2": exp1_vs_exp2,   # always None in this brew order
        },
        "champion_before": champion_before,
        "champion_after": {k: new_champion[k] for k in (*_KNOBS, "recipe_id")},
        "digested_at": _now_iso(),
    })

    loop["champion"] = new_champion
    loop["generation"] += 1
    # last_cup: the just-finished cycle's *final* cup, suggested as next cycle's
    # exp1 compared_to for taste-memory continuity. In this order that is exp2.
    loop["last_cup"] = exp2["feedback_timestamp"]
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
        "last_cup": None,           # prev cycle's final cup ts (cross-cycle anchor)
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
    cup in brew order (blueprint §4: judge vs the previous cup).

    Brew order is [exp1, champion, exp2]: cup 2 (champion) compares to cup 1
    (exp1), cup 3 (exp2) compares to cup 2 (champion). Cup 1 (exp1) compares
    cross-cycle to the prior cycle's final cup (= prev exp2) — recorded as
    bonus signal, not used in this cycle's digest.
    """
    slots = loop["cycle"]["slots"]
    role = slot["role"]
    if role == "exp1":
        return loop.get("last_cup")  # cross-cycle: prev cycle's final cup
    prev = {"champion": "exp1", "exp2": "champion"}[role]
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
    role_index = {"exp1": 1, "champion": 2, "exp2": 3}[slot["role"]]
    return {
        **evaluated,
        "role": slot["role"],
        "role_index": role_index,
        "kind": slot.get("kind"),       # "single" / "leap" / None (champion slot)
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
    slot["kind"] = "single"  # skip re-rolls via _pick_experiment (single-knob)
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
