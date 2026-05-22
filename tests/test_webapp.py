"""Phase 10 Step 6 web UI (webapp.py).

Routes over the sensory pipeline: no label, no water chemistry; /api/optimize
returns 10 attributes + distance; /api/feedback reads/writes the pairwise +
ordinal log.
"""
from __future__ import annotations

import pytest

from webapp import build_parser, create_app
from models.sensory import ATTRIBUTES


@pytest.fixture
def client():
    return create_app().test_client()


def test_index_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"AeroPress" in resp.data
    assert b"data-controls-panel" in resp.data


def test_config_route(client):
    payload = client.get("/api/config").get_json()
    for key in ("roast_options", "brewers", "default_temps", "attributes", "axis_view"):
        assert key in payload
    assert set(payload["attributes"]) == set(ATTRIBUTES)


def test_optimize_route_returns_attributes_and_distance(client):
    resp = client.post("/api/optimize", json={
        "roast": "medium_light", "brewer": "xl", "temp": 95, "top": 3,
    })
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["meta"]["roast_code"] == "medium_light"
    assert payload["meta"]["temp"] == 95
    results = payload["results"]
    assert isinstance(results, list) and len(results) == 3
    top = results[0]
    assert set(top["attributes"]) == set(ATTRIBUTES)
    assert "distance" in top and "ideal" in top and "deltas" in top
    assert "recipe_id" in top
    # the compound / label / score era is gone
    assert "compounds" not in top and "score" not in top and "label" not in top
    # ascending by distance
    assert [r["distance"] for r in results] == sorted(r["distance"] for r in results)


def test_optimize_temp_defaults_when_omitted(client):
    payload = client.post("/api/optimize", json={
        "roast": "light", "brewer": "xl", "top": 1,
    }).get_json()
    import constants
    assert payload["meta"]["temp"] == constants.DEFAULT_TEMP["light"]


def test_optimize_unknown_roast_is_400(client):
    resp = client.post("/api/optimize", json={"roast": "nonsense", "brewer": "xl"})
    assert resp.status_code == 400


def test_feedback_list_route(client):
    payload = client.get("/api/feedback").get_json()
    assert "entries" in payload
    assert "questionnaire_groups" in payload
    assert isinstance(payload["entries"], list)


def test_feedback_post_round_trip(tmp_path, monkeypatch):
    import models.feedback as feedback
    monkeypatch.setattr(feedback, "_FEEDBACK_PATH", tmp_path / "feedback.jsonl")
    client = create_app().test_client()

    ok = client.post("/api/feedback", json={
        "recipe_id": "abc123", "roast": "medium_light", "brewer": "xl",
        "overall": ">", "attributes_vs": {"sweetness": ">", "body": "?"},
        "comment": "webapp round trip",
    })
    assert ok.status_code == 200 and ok.get_json()["ok"] is True

    bad = client.post("/api/feedback", json={
        "recipe_id": "x", "roast": "light", "brewer": "xl", "overall": "huh",
    })
    assert bad.status_code == 400

    listed = client.get("/api/feedback").get_json()["entries"]
    assert any(e["recipe_id"] == "abc123" for e in listed)


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.host == "0.0.0.0"
    assert args.port == 8000
    assert args.debug is True
