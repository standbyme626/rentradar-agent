from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app
from app.models import User


def test_protected_route_requires_login():
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        assert client.get("/api/agent/stats").status_code == 401
        assert client.get("/api/admin/overview").status_code == 401


def test_viewer_cannot_open_admin_routes():
    app.dependency_overrides[get_current_user] = lambda: User(
        id=99, username="viewer", role="viewer", is_active=True
    )
    try:
        with TestClient(app) as client:
            assert client.get("/api/admin/overview").status_code == 403
    finally:
        app.dependency_overrides.clear()
