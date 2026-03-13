from webapp import create_app


def test_webapp_routes() -> None:
    app = create_app()
    client = app.test_client()

    index_response = client.get("/")
    assert index_response.status_code == 200
    assert b"AeroPress" in index_response.data

    api_response = client.post(
        "/api/optimize",
        json={
            "brewer": "xl",
            "roast": "M",
            "gh": 50,
            "kh": 30,
            "mg_frac": 0.40,
            "top": 1,
            "t_env": 25,
            "tds_floor": 0.80,
            "altitude": 0,
        },
    )
    payload = api_response.get_json()
    assert api_response.status_code == 200
    assert payload["meta"]["roast_code"] == "M"
    assert len(payload["results"]) == 1
    assert "compounds_abs" in payload["results"][0]
