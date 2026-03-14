from webapp import build_parser, create_app


def test_webapp_routes() -> None:
    app = create_app()
    client = app.test_client()

    index_response = client.get("/")
    assert index_response.status_code == 200
    assert b"AeroPress" in index_response.data
    assert b"data-controls-toggle" in index_response.data

    api_response = client.post(
        "/api/optimize",
        json={
            "brewer": "xl",
            "roast": "medium",
            "gh": 50,
            "kh": 30,
            "mg_frac": 0.40,
            "top": 1,
            "t_env": 25,
            "altitude": 0,
        },
    )
    payload = api_response.get_json()
    assert api_response.status_code == 200
    assert payload["meta"]["roast_code"] == "medium"
    assert len(payload["results"]) == 1
    assert "compounds_abs" in payload["results"][0]
    assert "swirl_wait_sec" in payload["results"][0]


def test_webapp_parser_exposes_lan_by_default() -> None:
    args = build_parser().parse_args([])
    assert args.host == "0.0.0.0"
    assert args.port == 8000
    assert args.debug is True
