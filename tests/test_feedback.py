"""Phase 10 Step 6 feedback log (models/feedback.py).

Pairwise + ordinal schema: compared_to / overall / attributes_vs /
model_attributes_vs / absolute. overall is >/=/< ; per-attribute is >/?/< (no
"=" -- "?" = noticed no difference). Legacy pre-Step-6 entries still read.
Each test redirects the JSONL path to a tmp file so the real log is untouched.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture
def fb(tmp_path, monkeypatch):
    import models.feedback as feedback
    monkeypatch.setattr(feedback, "_FEEDBACK_PATH", tmp_path / "feedback.jsonl")
    return feedback


def _recipe():
    return {"temp": 95, "dial": 4.5, "dose": 24.0, "steep_sec": 150,
            "tds": 1.36, "ey": 20.1, "distance": 0.0005}


def test_append_and_read_round_trip(fb):
    entry = fb.append_feedback({
        "recipe_id": "abc123", "roast": "medium_light", "brewer": "xl",
        "recipe": _recipe(), "comment": "round trip",
    })
    assert entry["timestamp"]
    all_entries = fb.read_all()
    assert len(all_entries) == 1
    assert all_entries[0]["recipe_id"] == "abc123"
    assert all_entries[0]["comment"] == "round trip"


def test_required_fields_enforced(fb):
    for missing in ("recipe_id", "roast", "brewer"):
        payload = {"recipe_id": "x", "roast": "light", "brewer": "xl", "comment": "c"}
        del payload[missing]
        with pytest.raises(ValueError):
            fb.append_feedback(payload)


def test_empty_submission_rejected(fb):
    with pytest.raises(ValueError):
        fb.append_feedback({"recipe_id": "x", "roast": "light", "brewer": "xl"})


def test_overall_accepts_ordinal_rejects_garbage(fb):
    fb.append_feedback({"recipe_id": "x", "roast": "light", "brewer": "xl",
                        "overall": "="})  # "=" is valid for overall
    with pytest.raises(ValueError):
        fb.append_feedback({"recipe_id": "x", "roast": "light", "brewer": "xl",
                            "overall": "better"})


def test_attributes_vs_uses_qmark_not_equals(fb):
    """Per-attribute vocabulary is >/?/< -- '=' must be rejected (Step 6a §4)."""
    entry = fb.append_feedback({
        "recipe_id": "x", "roast": "light", "brewer": "xl",
        "attributes_vs": {"acidity": "?", "sweetness": ">", "body": "<"},
    })
    assert entry["attributes_vs"] == {"acidity": "?", "sweetness": ">", "body": "<"}
    with pytest.raises(ValueError):
        fb.append_feedback({"recipe_id": "x", "roast": "light", "brewer": "xl",
                            "attributes_vs": {"acidity": "="}})


def test_attributes_vs_drops_unknown_groups(fb):
    entry = fb.append_feedback({
        "recipe_id": "x", "roast": "light", "brewer": "xl",
        "attributes_vs": {"sweetness": ">", "not_a_group": "<"},
    })
    assert entry["attributes_vs"] == {"sweetness": ">"}


def test_absolute_validation(fb):
    fb.append_feedback({"recipe_id": "x", "roast": "light", "brewer": "xl",
                        "absolute": "good"})
    with pytest.raises(ValueError):
        fb.append_feedback({"recipe_id": "x", "roast": "light", "brewer": "xl",
                            "absolute": "amazing"})


def test_stars_validation(fb):
    fb.append_feedback({"recipe_id": "x", "roast": "light", "brewer": "xl", "stars": 5})
    with pytest.raises(ValueError):
        fb.append_feedback({"recipe_id": "x", "roast": "light", "brewer": "xl", "stars": 7})


def test_recompute_entry_from_snapshot(fb):
    entry = fb.append_feedback({
        "recipe_id": "abc", "roast": "medium_light", "brewer": "xl",
        "recipe": _recipe(), "comment": "c",
    })
    current = fb.recompute_entry(entry)
    assert current is not None
    assert set(current) == {"ey", "tds", "distance", "attributes"}
    assert len(current["attributes"]) == 10
    assert current["distance"] >= 0.0


def test_recompute_entry_none_without_snapshot(fb):
    entry = fb.append_feedback({"recipe_id": "x", "roast": "light",
                                "brewer": "xl", "comment": "no recipe"})
    assert fb.recompute_entry(entry) is None


def test_update_feedback_within_window(fb):
    entry = fb.append_feedback({"recipe_id": "x", "roast": "light",
                                "brewer": "xl", "comment": "first"})
    fb.update_feedback(entry["timestamp"], {"comment": "edited", "stars": 4})
    updated = fb.read_all()[0]
    assert updated["comment"] == "edited"
    assert updated["stars"] == 4


def test_legacy_entry_still_reads(fb):
    """Pre-Step-6 entries carry label / water / rating / recipe.score -- they
    must still parse (read_all tolerates them as history)."""
    legacy = {
        "timestamp": "2026-05-15T13:07:00+08:00", "recipe_id": "1ee482d3c5e6",
        "label": "balanced", "rating": None, "stars": 5, "comment": "old",
        "tags": ["acidic"], "roast": "medium_light", "brewer": "xl",
        "water": {"gh": 50.0, "kh": 30.0, "mg_frac": 0.4},
        "recipe": {"temp": 93.0, "dial": 4.3, "dose": 24.0, "steep_sec": 150,
                   "tds": 1.41, "ey": 20.8, "score": 95.8},
    }
    fb._FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fb._FEEDBACK_PATH.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
    entries = fb.read_all()
    assert len(entries) == 1 and entries[0]["label"] == "balanced"
    # a legacy recipe snapshot still recomputes (label / water are ignored)
    current = fb.recompute_entry(entries[0])
    assert current is not None and len(current["attributes"]) == 10
