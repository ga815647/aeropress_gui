"""Phase 11 — loop engine (models/loop.py) + named recipes (models/saved.py).

The loop is a (1+lambda) search over the three-cup cycle [exp1, champion, exp2];
see docs/PHASE11_LOOP_ENGINE.md. Each test redirects the loop-state and feedback
JSON paths to a tmp dir so the real files are untouched.
"""
from __future__ import annotations

import pytest

import models.feedback as feedback
import models.loop as loop
import models.saved as saved


@pytest.fixture
def lp(tmp_path, monkeypatch):
    """loop engine wired to tmp loop-state + feedback files."""
    monkeypatch.setattr(loop, "_STATE_PATH", tmp_path / "loop_state.json")
    monkeypatch.setattr(feedback, "_FEEDBACK_PATH", tmp_path / "feedback.jsonl")
    return loop


@pytest.fixture
def sv(tmp_path, monkeypatch):
    monkeypatch.setattr(saved, "_SAVED_PATH", tmp_path / "saved_recipes.json")
    return saved


# ── helpers ──────────────────────────────────────────────────────────────────
def _knob_diffs(recipe_a: dict, recipe_b: dict) -> int:
    """How many of dial / steep_sec / dose differ between two recipes."""
    return sum(recipe_a[k] != recipe_b[k] for k in ("dial", "steep_sec", "dose"))


def _brew_cup(lp, roast: str, overall: str, ts: str):
    """Brew the loop's current proposal: append feedback with `overall` against
    the loop-suggested compared-to cup, then register it. Returns (outcome, proposal)."""
    p = lp.current_proposal(roast)
    entry = feedback.append_feedback({
        "recipe_id": p["recipe_id"], "roast": roast, "brewer": "xl",
        "timestamp": ts, "overall": overall,
        "compared_to": p["suggested_compared_to"],
        "recipe": {"temp": p["temp"], "dial": p["dial"], "dose": p["dose"],
                   "steep_sec": p["steep_sec"]},
        "comment": "t",
    })
    return lp.register_feedback(roast, p["recipe_id"], entry), p


def _brew_cycle(lp, roast: str, overalls, ts_base: int):
    """Brew a full three-cup cycle; `overalls` = (exp1, exp2, champion)."""
    for i, o in enumerate(overalls):
        _brew_cup(lp, roast, o, f"2026-05-22T10:{ts_base + i:02d}:00+08:00")


# ── start / proposal / perturbation ──────────────────────────────────────────
def test_start_loop_seeds_champion_and_cycle(lp):
    L = lp.start_loop("medium_light", brewer="xl", temp=95.0)
    assert L["generation"] == 0
    assert L["cycle"]["index"] == 1
    assert L["champion"]["source"] == "seed"
    assert {s["role"] for s in L["cycle"]["slots"]} == {"exp1", "exp2", "champion"}


def test_proposal_is_first_pending_slot(lp):
    lp.start_loop("medium_light", brewer="xl", temp=95.0)
    p = lp.current_proposal("medium_light")
    assert p["role"] == "exp1" and p["role_index"] == 1
    # carries the optimizer-result shape the card consumes
    assert len(p["attributes"]) == 10 and "distance" in p


def test_exp1_is_iso_tds_ey_jump_when_available(lp):
    """exp1 is now the iso-(TDS,EY) probe (test Layer 2's b_temp=0 assumption);
    falls back to a single-knob perturbation only when no iso candidate
    qualifies. medium_light + XL has a rich enough grid that iso is essentially
    always available."""
    import constants
    from models.layer1 import brew as layer1_brew
    L = lp.start_loop("medium_light", brewer="xl", temp=95.0)
    slots = {s["role"]: s for s in L["cycle"]["slots"]}
    champ = slots["champion"]["recipe"]
    exp1 = slots["exp1"]
    assert exp1["kind"] in ("iso", "single")
    assert exp1["recipe"] != slots["exp2"]["recipe"]
    assert slots["champion"]["recipe"] == champ
    assert slots["champion"]["kind"] is None
    if exp1["kind"] == "iso":
        # iso => >= 2 knob diffs from champion AND TDS/EY within tolerance
        assert _knob_diffs(exp1["recipe"], champ) >= lp.LEAP_KNOB_DIFF_MIN
        assert exp1["move"] is None
        water = constants.BREWER_PRESETS["xl"]["water_ml"]
        ch = layer1_brew("medium_light", 95.0, champ["dial"],
                         champ["steep_sec"], champ["dose"], water)
        ex = layer1_brew("medium_light", 95.0, exp1["recipe"]["dial"],
                         exp1["recipe"]["steep_sec"], exp1["recipe"]["dose"],
                         water)
        assert abs(ex["tds"] - ch["tds"]) <= lp.ISO_TDS_TOL
        assert abs(ex["ey"] - ch["ey"]) <= lp.ISO_EY_TOL
    else:  # rare fallback: still useful, just single-knob
        assert _knob_diffs(exp1["recipe"], champ) == 1


def test_exp2_is_informed_leap_when_available(lp):
    """exp2 is the surrogate-guided 'kick' — model Top-N candidate that differs
    from the champion in >= LEAP_KNOB_DIFF_MIN knobs. medium_light + XL has a
    rich enough grid that a leap is essentially always available."""
    L = lp.start_loop("medium_light", brewer="xl", temp=95.0)
    slots = {s["role"]: s for s in L["cycle"]["slots"]}
    champ = slots["champion"]["recipe"]
    exp2 = slots["exp2"]
    assert exp2["kind"] in ("leap", "single")
    if exp2["kind"] == "leap":
        assert _knob_diffs(exp2["recipe"], champ) >= lp.LEAP_KNOB_DIFF_MIN
        assert exp2["move"] is None             # leap has no single (knob, sign)
    else:
        # graceful fallback (rare for medium_light XL — model Top-N is rich)
        assert _knob_diffs(exp2["recipe"], champ) == 1


def test_leap_respects_sca_gold_cup(lp):
    """Every leap exp2 candidate must land in the extended Gold Cup box
    (TDS 1.15–1.40%, EY 17–22% — strict SCA widened to cover both project
    anchors). Sanity filter on the surrogate's far-Top-N proposals so a
    leap never asks the user to brew a universally-dud cup just because
    predicted attributes look model-good."""
    import constants
    from models.layer1 import brew as layer1_brew
    L = lp.start_loop("medium_light", brewer="xl", temp=95.0)
    exp2 = next(s for s in L["cycle"]["slots"] if s["role"] == "exp2")
    if exp2["kind"] != "leap":
        pytest.skip("no leap candidate available in this fixture state")
    water_ml = constants.BREWER_PRESETS["xl"]["water_ml"]
    r = exp2["recipe"]
    l1 = layer1_brew("medium_light", 95.0, r["dial"], r["steep_sec"],
                     r["dose"], water_ml)
    lo_tds, hi_tds = lp.GOLD_CUP_TDS_RANGE
    lo_ey, hi_ey = lp.GOLD_CUP_EY_RANGE
    assert lo_tds <= l1["tds"] <= hi_tds, (
        f"leap TDS {l1['tds']:.3f}% outside Gold Cup [{lo_tds}, {hi_tds}]")
    assert lo_ey <= l1["ey"] <= hi_ey, (
        f"leap EY {l1['ey']:.2f}% outside Gold Cup [{lo_ey}, {hi_ey}]")


def test_iso_and_leap_respect_per_roast_steep_cap(lp):
    """Long immersion is a Layer-1 extrapolation: TDS/EY may match the
    champion but real flavour diverges (volatile loss, temp decay). Both
    iso and leap candidates must respect STEEP_MAX_BY_ROAST so the loop
    never proposes a 420-s steep just because the model says iso-equivalent.
    Light roast is the most sensitive (Nordic 60–120 s; cap at 180 s)."""
    L = lp.start_loop("light", brewer="xl", temp=98.0)
    cap = lp.STEEP_MAX_BY_ROAST["light"]
    for slot in L["cycle"]["slots"]:
        if slot["kind"] in ("iso", "leap"):
            assert slot["recipe"]["steep_sec"] <= cap, (
                f"{slot['kind']} candidate steep={slot['recipe']['steep_sec']} s "
                f"exceeds light's cap of {cap} s"
            )


def test_iso_and_leap_respect_per_roast_dial_cap(lp):
    """Coarse grind drains the AeroPress faster than the requested steep_sec
    — actual brew time decouples from the parameter, feedback becomes
    irreproducible. Both iso and leap candidates must respect
    DIAL_MAX_BY_ROAST so light never proposes a coarse-grind experiment whose
    real steep time can't be controlled. Stays parallel to the steep-cap
    contract: optimizer Top-N tab + override + single-knob keep full grid."""
    L = lp.start_loop("light", brewer="xl", temp=98.0)
    cap = lp.DIAL_MAX_BY_ROAST["light"]
    for slot in L["cycle"]["slots"]:
        if slot["kind"] in ("iso", "leap"):
            assert slot["recipe"]["dial"] <= cap, (
                f"{slot['kind']} candidate dial={slot['recipe']['dial']} "
                f"exceeds light's cap of {cap}"
            )


def _brew_champion_hold(lp, roast, ts_base):
    """Brew a cycle where the champion wins — overalls (=, >, <) means
    cup-2 (champion) > exp1 AND cup-3 (exp2) < champion → champion wins."""
    import models.feedback as feedback
    for i, o in enumerate(("=", ">", "<")):
        p = lp.current_proposal(roast)
        entry = feedback.append_feedback({
            "recipe_id": p["recipe_id"], "roast": roast, "brewer": "xl",
            "timestamp": f"2026-05-23T{ts_base:02d}:{i:02d}:00+08:00",
            "overall": o, "compared_to": p["suggested_compared_to"],
            "recipe": {"temp": p["temp"], "dial": p["dial"],
                       "dose": p["dose"], "steep_sec": p["steep_sec"]},
            "comment": "c",
        })
        lp.register_feedback(roast, p["recipe_id"], entry)


def test_stall_counter_increments_on_champion_hold(lp):
    """Each cycle where the champion holds bumps stall_counter by 1."""
    lp.start_loop("medium_light", brewer="xl", temp=95.0)
    assert lp.get_loop("medium_light")["stall_counter"] == 0
    _brew_champion_hold(lp, "medium_light", 10)
    assert lp.get_loop("medium_light")["stall_counter"] == 1
    _brew_champion_hold(lp, "medium_light", 11)
    assert lp.get_loop("medium_light")["stall_counter"] == 2


def test_stall_counter_resets_on_experiment_win(lp):
    """Any non-champion winner resets stall_counter (and rotation_idx) to 0."""
    import models.feedback as feedback
    lp.start_loop("medium_light", brewer="xl", temp=95.0)
    # First brew two champion-holds so counter = 2
    _brew_champion_hold(lp, "medium_light", 10)
    _brew_champion_hold(lp, "medium_light", 11)
    assert lp.get_loop("medium_light")["stall_counter"] == 2
    # Now brew a cycle where exp1 wins (overall pattern that makes exp1 win):
    #   cup-2 (champion vs exp1) = "<" → exp1 beats champion ;
    #   cup-3 (exp2 vs champion) = "=" → exp2 doesn't beat champion ;
    #   → exp1 wins.
    for i, o in enumerate(("=", "<", "=")):
        p = lp.current_proposal("medium_light")
        entry = feedback.append_feedback({
            "recipe_id": p["recipe_id"], "roast": "medium_light", "brewer": "xl",
            "timestamp": f"2026-05-23T12:{i:02d}:00+08:00",
            "overall": o, "compared_to": p["suggested_compared_to"],
            "recipe": {"temp": p["temp"], "dial": p["dial"],
                       "dose": p["dose"], "steep_sec": p["steep_sec"]},
            "comment": "c",
        })
        lp.register_feedback("medium_light", p["recipe_id"], entry)
    L = lp.get_loop("medium_light")
    assert L["history"][-1]["winner_role"] == "exp1"
    assert L["stall_counter"] == 0
    assert L["stall_rotation_idx"] == 0


def test_stall_trigger_fires_at_threshold_with_single_step(lp):
    """After STALL_THRESHOLD consecutive champion-holds, the next cycle's exp1
    is a kind="single" stall=True 1-step perturbation (NOT iso, NOT
    generation-aware radius)."""
    lp.start_loop("medium_light", brewer="xl", temp=95.0)
    # Three champion-holds → counter = 3 → next cycle should stall-trigger
    for i in range(lp.STALL_THRESHOLD):
        _brew_champion_hold(lp, "medium_light", 10 + i)
    L = lp.get_loop("medium_light")
    champ = L["champion"]
    assert L["stall_counter"] == lp.STALL_THRESHOLD
    exp1 = next(s for s in L["cycle"]["slots"] if s["role"] == "exp1")
    assert exp1["kind"] == "single"
    assert exp1["stall"] is True
    # exactly 1 knob different, exactly 1 grid step
    diffs = [k for k in ("dial", "steep_sec", "dose")
             if exp1["recipe"][k] != champ[k]]
    assert len(diffs) == 1
    k = diffs[0]
    grid_step = {"dial": 0.1, "steep_sec": 30, "dose": 1.0}[k]
    assert abs(exp1["recipe"][k] - champ[k]) == pytest.approx(grid_step, abs=1e-6)


def test_stall_rotates_through_six_directions_then_exhausts(lp):
    """The stall rotation covers exactly 6 (knob, sign) pairs in order; after
    they're all tried, exp1 returns to iso (rotation_idx == 6, stall disabled)."""
    lp.start_loop("medium_light", brewer="xl", temp=95.0)
    # Three champion-holds to arm the trigger
    for i in range(lp.STALL_THRESHOLD):
        _brew_champion_hold(lp, "medium_light", 10 + i)
    moves_seen = []
    # Now run 6 more champion-holds — each cycle's exp1 should be stall
    # and cycle through STALL_KNOB_ROTATION in order.
    for i in range(len(lp.STALL_KNOB_ROTATION)):
        exp1 = next(s for s in lp.get_loop("medium_light")["cycle"]["slots"]
                    if s["role"] == "exp1")
        assert exp1["stall"] is True
        moves_seen.append(tuple(exp1["move"]))
        _brew_champion_hold(lp, "medium_light", 20 + i)
    assert moves_seen == list(lp.STALL_KNOB_ROTATION)
    # After all 6 tried, rotation_idx == 6, stall disabled — next exp1 is iso
    L = lp.get_loop("medium_light")
    assert L["stall_rotation_idx"] == len(lp.STALL_KNOB_ROTATION)
    exp1 = next(s for s in L["cycle"]["slots"] if s["role"] == "exp1")
    assert exp1["kind"] != "single" or not exp1.get("stall")


def test_override_to_single_knob_replaces_slot(lp):
    """User-triggered override replaces a pending experiment slot with a
    single-knob perturbation of the champion along (knob, sign). The slot's
    kind becomes 'single', the move is recorded, and the recipe matches a
    one-grid-step shift on the chosen knob."""
    L = lp.start_loop("medium_light", brewer="xl", temp=95.0)
    exp1 = next(s for s in L["cycle"]["slots"] if s["role"] == "exp1")
    champ = next(s for s in L["cycle"]["slots"] if s["role"] == "champion")["recipe"]

    result = lp.override_to_single_knob("medium_light", exp1["recipe_id"],
                                        "dial", -1)
    assert result["overridden"] is True
    slot = next(s for s in result["loop"]["cycle"]["slots"]
                if s["role"] == "exp1")
    assert slot["kind"] == "single"
    assert slot["move"] == ["dial", -1]
    # exactly one knob differs from champion (dial), and dial moved finer
    assert slot["recipe"]["steep_sec"] == champ["steep_sec"]
    assert slot["recipe"]["dose"] == champ["dose"]
    assert slot["recipe"]["dial"] < champ["dial"]


def test_override_rejects_champion_slot(lp):
    """The champion re-brew slot can't be overridden — its purpose is to
    re-anchor taste memory at the entering champion."""
    L = lp.start_loop("medium_light", brewer="xl", temp=95.0)
    champ_slot = next(s for s in L["cycle"]["slots"] if s["role"] == "champion")
    result = lp.override_to_single_knob(
        "medium_light", champ_slot["recipe_id"], "dial", -1,
    )
    assert result["overridden"] is False
    assert "champion" in result.get("reason", "").lower()


def test_override_rejects_bad_args(lp):
    """Unknown knob / invalid sign are refused with a reason."""
    L = lp.start_loop("medium_light", brewer="xl", temp=95.0)
    exp1 = next(s for s in L["cycle"]["slots"] if s["role"] == "exp1")
    bad_knob = lp.override_to_single_knob(
        "medium_light", exp1["recipe_id"], "altitude", -1,
    )
    assert bad_knob["overridden"] is False
    bad_sign = lp.override_to_single_knob(
        "medium_light", exp1["recipe_id"], "dial", 0,
    )
    assert bad_sign["overridden"] is False


def test_leap_excludes_already_brewed_recipes(lp):
    """The leap candidate is filtered against the feedback log — a recipe the
    user has already given feedback on is not re-proposed as a leap."""
    import models.feedback as feedback
    L = lp.start_loop("medium_light", brewer="xl", temp=95.0)
    leap_slot = next(s for s in L["cycle"]["slots"] if s["role"] == "exp2")
    if leap_slot["kind"] != "leap":
        pytest.skip("no leap candidate available in this fixture state")
    leap_id = leap_slot["recipe_id"]

    # Submit feedback for the current leap recipe.
    feedback.append_feedback({
        "recipe_id": leap_id, "roast": "medium_light", "brewer": "xl",
        "recipe": {"temp": 95.0, **leap_slot["recipe"]},
        "comment": "tried it",
    })
    # Reset cycle (or trigger a rebuild) and the same leap should not reappear.
    lp.reset_loop("medium_light")
    L2 = lp.get_loop("medium_light")
    exp2 = next(s for s in L2["cycle"]["slots"] if s["role"] == "exp2")
    assert exp2["recipe_id"] != leap_id


def test_champion_slot_rebrews_the_champion(lp):
    L = lp.start_loop("medium_light", brewer="xl", temp=95.0)
    champ = L["champion"]
    champ_slot = next(s for s in L["cycle"]["slots"] if s["role"] == "champion")
    for k in ("dial", "steep_sec", "dose"):
        assert champ_slot["recipe"][k] == champ[k]


# ── digest / cycle advance ───────────────────────────────────────────────────
def test_cycle_advances_after_three_cups(lp):
    lp.start_loop("medium_light", brewer="xl", temp=95.0)
    _brew_cycle(lp, "medium_light", ("=", "=", "="), 0)
    L = lp.get_loop("medium_light")
    assert L["generation"] == 1
    assert L["cycle"]["index"] == 2
    assert len(L["history"]) == 1
    # a fresh cycle is all-pending again
    assert all(s["status"] == "pending" for s in L["cycle"]["slots"])


def test_digest_champion_holds_on_all_ties(lp):
    L0 = lp.start_loop("medium_light", brewer="xl", temp=95.0)
    champ_before = {k: L0["champion"][k] for k in ("dial", "steep_sec", "dose")}
    _brew_cycle(lp, "medium_light", ("=", "=", "="), 0)
    L = lp.get_loop("medium_light")
    assert L["history"][0]["winner_role"] == "champion"
    champ_after = {k: L["champion"][k] for k in ("dial", "steep_sec", "dose")}
    assert champ_after == champ_before  # incumbent kept — no clear win


def test_digest_promotes_a_winning_experiment(lp):
    """Brew order is [exp1, champion, exp2]. Cup 2's `overall` is champion vs
    exp1; cup 3's `overall` is exp2 vs champion. So (cup1 unused, `<`, `=`)
    means exp1 beats champion (cup 2 `<` = champ worse than exp1) and exp2
    ties champion -> exp1 is the cycle winner."""
    lp.start_loop("medium_light", brewer="xl", temp=95.0)
    L0 = lp.get_loop("medium_light")
    exp1_recipe = next(s["recipe"] for s in L0["cycle"]["slots"] if s["role"] == "exp1")
    _brew_cycle(lp, "medium_light", (">", "<", "="), 0)
    L = lp.get_loop("medium_light")
    assert L["history"][0]["winner_role"] == "exp1"
    for k in ("dial", "steep_sec", "dose"):
        assert L["champion"][k] == exp1_recipe[k]
    assert L["champion"]["source"] == "cycle"
    # exp1↔exp2 is never a within-cycle edge in [exp1, champion, exp2] order
    assert L["history"][0]["edges"]["exp1_vs_exp2"] is None


def test_two_cycles_advance_generation(lp):
    """With [exp1, champion, exp2] order, every cycle's exp1↔champion and
    exp2↔champion edges are DIRECT (no cycle-1 vs cycle-N special case).
    Brew two cycles of all ties — champion holds both times, generation
    advances each completed cycle."""
    lp.start_loop("medium_light", brewer="xl", temp=95.0)
    _brew_cycle(lp, "medium_light", ("=", "=", "="), 0)
    _brew_cycle(lp, "medium_light", ("=", "=", "="), 10)
    L = lp.get_loop("medium_light")
    assert L["generation"] == 2 and L["cycle"]["index"] == 3
    assert len(L["history"]) == 2
    # cross-cycle anchor: next cycle's exp1 suggested_compared_to == prev
    # cycle's final cup (exp2), not prev champion as in the old ordering.
    assert L["last_cup"] is not None


# ── skip ─────────────────────────────────────────────────────────────────────
def test_skip_rerolls_at_same_generation(lp):
    lp.start_loop("medium_light", brewer="xl", temp=95.0)
    before = lp.current_proposal("medium_light")
    result = lp.skip_proposal("medium_light", before["recipe_id"])
    assert result["skipped"] is True
    after = lp.current_proposal("medium_light")
    assert after["recipe_id"] != before["recipe_id"]   # a fresh proposal
    assert after["skips"] == 1                          # skip counted
    assert after["generation"] == before["generation"]  # same radius / generation
    assert after["role"] == "exp1"                      # still the same slot


def test_skip_champion_rebrew_is_rejected(lp):
    L = lp.start_loop("medium_light", brewer="xl", temp=95.0)
    champ_id = next(s["recipe_id"] for s in L["cycle"]["slots"] if s["role"] == "champion")
    result = lp.skip_proposal("medium_light", champ_id)
    assert result["skipped"] is False  # the champion re-brew is not a perturbation


# ── register_feedback robustness ─────────────────────────────────────────────
def test_register_feedback_ignores_unknown_recipe(lp):
    lp.start_loop("medium_light", brewer="xl", temp=95.0)
    outcome = lp.register_feedback("medium_light", "deadbeefcafe", {"timestamp": "x"})
    assert outcome["matched"] is False and outcome["digested"] is False


def test_register_feedback_noop_without_loop(lp):
    outcome = lp.register_feedback("medium_light", "whatever", {"timestamp": "x"})
    assert outcome == {"matched": False, "digested": False, "loop": None}


# ── reset ────────────────────────────────────────────────────────────────────
def test_reset_loop_starts_fresh(lp):
    lp.start_loop("medium_light", brewer="xl", temp=95.0)
    _brew_cycle(lp, "medium_light", (">", "<", "="), 0)
    assert lp.get_loop("medium_light")["generation"] == 1
    lp.reset_loop("medium_light")
    L = lp.get_loop("medium_light")
    assert L["generation"] == 0 and L["cycle"]["index"] == 1 and L["history"] == []


def test_migration_reorders_old_slot_layout(lp, tmp_path):
    """A loop_state.json written before the 2026-05-23 reorder has slots in
    [exp1, exp2, champion] order. _load() should reorder them in place to
    [exp1, champion, exp2] when nothing is brewed yet (lossless)."""
    import json
    old_state = {
        "medium_light": {
            "roast": "medium_light", "brewer": "xl", "temp": 95.0,
            "water_ml": 400, "generation": 0,
            "champion": {"dial": 4.5, "steep_sec": 150, "dose": 24.0,
                         "recipe_id": "x", "source": "seed"},
            "last_champion_cup": None,   # old field name
            "history": [],
            "cycle": {"index": 1, "slots": [
                {"role": "exp1", "status": "pending",
                 "recipe": {"dial": 4.4, "steep_sec": 150, "dose": 24.0},
                 "recipe_id": "a", "feedback_timestamp": None,
                 "feedback_overall": None, "feedback_compared_to": None,
                 "skips": 0, "skipped": [], "move": ["dial", -1]},
                {"role": "exp2", "status": "pending",
                 "recipe": {"dial": 4.5, "steep_sec": 120, "dose": 24.0},
                 "recipe_id": "b", "feedback_timestamp": None,
                 "feedback_overall": None, "feedback_compared_to": None,
                 "skips": 0, "skipped": [], "move": ["steep_sec", -1]},
                {"role": "champion", "status": "pending",
                 "recipe": {"dial": 4.5, "steep_sec": 150, "dose": 24.0},
                 "recipe_id": "c", "feedback_timestamp": None,
                 "feedback_overall": None, "feedback_compared_to": None,
                 "skips": 0, "skipped": [], "move": None},
            ]},
        }
    }
    lp._STATE_PATH.write_text(json.dumps(old_state), encoding="utf-8")
    L = lp.get_loop("medium_light")
    assert [s["role"] for s in L["cycle"]["slots"]] == ["exp1", "champion", "exp2"]
    assert "last_champion_cup" not in L          # renamed
    assert "last_cup" in L


def test_migration_skips_reorder_when_a_cup_is_brewed(lp):
    """Half-brewed old-order cycle: leave the slots alone — its feedback
    chained to specific neighbor cups under the old order, silent reordering
    would orphan those edges. User should reset that loop to start fresh."""
    import json
    old_state = {
        "light": {
            "roast": "light", "brewer": "xl", "temp": 98.0, "water_ml": 400,
            "generation": 0,
            "champion": {"dial": 3.7, "steep_sec": 60, "dose": 25.0,
                         "recipe_id": "x", "source": "seed"},
            "last_champion_cup": None, "history": [],
            "cycle": {"index": 1, "slots": [
                {"role": "exp1", "status": "brewed",   # already brewed
                 "recipe": {"dial": 3.6, "steep_sec": 60, "dose": 25.0},
                 "recipe_id": "a", "feedback_timestamp": "2026-05-23T08:00:00+08:00",
                 "feedback_overall": ">", "feedback_compared_to": None,
                 "skips": 0, "skipped": [], "move": ["dial", -1]},
                {"role": "exp2", "status": "pending",
                 "recipe": {"dial": 3.7, "steep_sec": 90, "dose": 25.0},
                 "recipe_id": "b", "feedback_timestamp": None,
                 "feedback_overall": None, "feedback_compared_to": None,
                 "skips": 0, "skipped": [], "move": ["steep_sec", 1]},
                {"role": "champion", "status": "pending",
                 "recipe": {"dial": 3.7, "steep_sec": 60, "dose": 25.0},
                 "recipe_id": "c", "feedback_timestamp": None,
                 "feedback_overall": None, "feedback_compared_to": None,
                 "skips": 0, "skipped": [], "move": None},
            ]},
        }
    }
    lp._STATE_PATH.write_text(json.dumps(old_state), encoding="utf-8")
    L = lp.get_loop("light")
    # left untouched because exp1 is brewed
    assert [s["role"] for s in L["cycle"]["slots"]] == ["exp1", "exp2", "champion"]


def test_loops_are_per_roast(lp):
    lp.start_loop("medium_light", brewer="xl", temp=95.0)
    lp.start_loop("light", brewer="xl", temp=98.0)
    assert set(lp.load_loops()) == {"medium_light", "light"}
    # advancing one roast's loop leaves the other untouched
    _brew_cycle(lp, "light", ("=", "=", "="), 0)
    assert lp.get_loop("light")["generation"] == 1
    assert lp.get_loop("medium_light")["generation"] == 0


# ── flag detection ───────────────────────────────────────────────────────────
def test_detect_flags_needs_repeat(lp):
    """One model/user direction contradiction is noise; it must repeat to flag."""
    base = {"roast": "medium_light", "brewer": "xl"}
    one = {**base, "recipe_id": "r1",
           "model_attributes_vs": {"bitterness": ">"},
           "attributes_vs": {"bitterness": "<"}}
    feedback.append_feedback(one)
    assert lp.detect_flags() == []          # single contradiction -> no flag
    feedback.append_feedback({**one, "recipe_id": "r2"})
    flags = lp.detect_flags()
    assert len(flags) == 1
    assert flags[0]["group"] == "bitterness"
    assert flags[0]["direction"] == "model_over"  # model said more, user said less
    assert flags[0]["count"] == 2


def test_detect_flags_skips_qmark(lp):
    """`?` on either side is an absence of signal, never a contradiction."""
    for rid in ("a", "b", "c"):
        feedback.append_feedback({
            "roast": "light", "brewer": "xl", "recipe_id": rid,
            "model_attributes_vs": {"acidity": ">"},
            "attributes_vs": {"acidity": "?"},
        })
    assert lp.detect_flags() == []


def test_detect_flags_ignores_agreement(lp):
    for rid in ("a", "b", "c"):
        feedback.append_feedback({
            "roast": "light", "brewer": "xl", "recipe_id": rid,
            "model_attributes_vs": {"sweetness": ">"},
            "attributes_vs": {"sweetness": ">"},  # model and user agree
        })
    assert lp.detect_flags() == []


# ── saved recipes ────────────────────────────────────────────────────────────
def test_save_and_list_recipe(sv):
    entry = sv.save_recipe("我的中淺焙日常", "medium_light", "xl", 95.0,
                           4.4, 150, 24.0, note="平衡")
    assert entry["name"] == "我的中淺焙日常"
    assert entry["recipe_id"] and entry["id"]
    recipes = sv.list_recipes()
    assert len(recipes) == 1 and recipes[0]["note"] == "平衡"


def test_save_recipe_requires_name(sv):
    with pytest.raises(ValueError):
        sv.save_recipe("", "light", "xl", 98.0, 4.0, 60, 25.0)


def test_delete_recipe(sv):
    entry = sv.save_recipe("tmp", "light", "xl", 98.0, 4.0, 60, 25.0)
    assert sv.delete_recipe(entry["id"]) is True
    assert sv.list_recipes() == []
    assert sv.delete_recipe(entry["id"]) is False  # already gone
