from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.solver import example_materials


def test_health_and_login_and_solve():
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        bad = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert bad.status_code == 401

        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        me = client.get("/api/auth/me", headers=headers)
        assert me.json()["username"] == "admin"

        solve = client.post(
            "/api/calc/solve",
            headers=headers,
            json={"materials": example_materials(), "batch_mass": 100},
        )
        assert solve.status_code == 200
        body = solve.json()
        assert body["success"] is True
        result = body["result"]
        assert abs(result["masses"]["total"] - 100) < 1e-4
        assert abs(result["masses"]["carbide_slag"] - 6) < 1e-4
        assert result["percents"]["total"] <= 100.0001
        assert result["checks"]["al2o3_so3"]["passed"]
        assert result["checks"]["cao_ratio"]["passed"]
        assert result["checks"]["gangue_flyash"]["passed"]

        history = client.get("/api/history", headers=headers)
        assert history.status_code == 200
        assert len(history.json()) >= 1
