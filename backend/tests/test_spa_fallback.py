from fastapi.testclient import TestClient

from app.main import app


def test_unknown_api_returns_json_404():
    with TestClient(app) as client:
        response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
