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


def test_exp1_is_single_knob_perturbation(lp):
    """exp1 is always a single-knob local refine (attribution stays clean)."""
    L = lp.start_loop("medium_light", brewer="xl", temp=95.0)
    slots = {s["role"]: s for s in L["cycle"]["slots"]}
    champ = slots["champion"]["recipe"]
    assert _knob_diffs(slots["exp1"]["recipe"], champ) == 1
    assert slots["exp1"]["kind"] == "single"
    assert slots["exp1"]["recipe"] != slots["exp2"]["recipe"]
    assert slots["champion"]["recipe"] == champ
    assert slots["champion"]["kind"] is None    # champion re-brew, not an experiment


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
