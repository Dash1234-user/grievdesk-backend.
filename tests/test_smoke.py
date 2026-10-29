from app import create_app


def test_app_starts():
    app = create_app()
    assert app is not None


def test_unknown_route_returns_404():
    client = create_app().test_client()
    assert client.get("/this-route-does-not-exist").status_code == 404
