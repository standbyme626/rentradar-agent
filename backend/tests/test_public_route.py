from fastapi.testclient import TestClient

from app.main import app
from app.services import share_service


def test_public_dashboard_rejects_unknown_token(monkeypatch):
    async def fake_resolve(db, token):
        return None

    monkeypatch.setattr(share_service, "resolve_token", fake_resolve)
    with TestClient(app) as client:
        response = client.get("/api/public/dashboard/rr_share_unknown")
    assert response.status_code == 404
    assert response.headers.get("x-robots-tag") is None


def test_public_dashboard_returns_noindex_aggregates(monkeypatch):
    async def fake_resolve(db, token):
        return object()

    async def fake_dashboard(db):
        return {
            "totals": {"active_listings": 10},
            "districts": [],
            "source": {"url": "https://sz.zu.ke.com/"},
        }

    monkeypatch.setattr(share_service, "resolve_token", fake_resolve)
    monkeypatch.setattr(share_service, "public_dashboard", fake_dashboard)
    with TestClient(app) as client:
        response = client.get("/api/public/dashboard/rr_share_demo")
    assert response.status_code == 200
    assert response.headers["x-robots-tag"].startswith("noindex")
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["totals"]["active_listings"] == 10
