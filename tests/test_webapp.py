from webapp import build_parser, create_app


def test_webapp_routes() -> None:
    app = create_app()
    client = app.test_client()

    index_response = client.get("/")
    assert index_response.status_code == 200
    assert b"AeroPress" in index_response.data
    assert b"data-controls-toggle" in index_response.data

    # single-label mode (label specified)
    api_response = client.post(
        "/api/optimize",
        json={
            "brewer": "xl",
            "roast": "medium_light",
            "label": "balanced",
            "gh": 50, "kh": 30, "mg_frac": 0.40,
            "top": 1, "t_env": 25, "altitude": 0,
        },
    )
    payload = api_response.get_json()
    assert api_response.status_code == 200
    assert payload["meta"]["roast_code"] == "medium_light"
    assert payload["meta"]["label"] == "balanced"
    assert isinstance(payload["results"], list)
    assert len(payload["results"]) == 1
    assert "compounds_abs" in payload["results"][0]
    assert "swirl_wait_sec" in payload["results"][0]
    assert payload["results"][0]["label"] == "balanced"
    assert "recipe_id" in payload["results"][0]

    # Channel B mode (no label → parallel Top-1 per label)
    api_b = client.post(
        "/api/optimize",
        json={
            "brewer": "xl",
            "roast": "medium_light",
            "gh": 50, "kh": 30, "mg_frac": 0.40,
            "top": 1, "t_env": 25, "altitude": 0,
        },
    )
    payload_b = api_b.get_json()
    assert payload_b["meta"]["label"] == "__all__"
    assert isinstance(payload_b["results"], dict)
    # Match whatever labels are currently in data/labels.json (append-only file).
    from models.labels import label_names
    assert set(payload_b["results"].keys()) == set(label_names())
    # All currently-shipped core labels must always be present.
    assert {"balanced", "acid-forward", "sweet-body", "coarse-modern"} <= set(payload_b["results"].keys())


def test_webapp_parser_exposes_lan_by_default() -> None:
    args = build_parser().parse_args([])
    assert args.host == "0.0.0.0"
    assert args.port == 8000
    assert args.debug is True
