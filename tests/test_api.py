import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["dataset"]["row_count"] == 500


def test_anomalies_all_and_week():
    with TestClient(app) as client:
        response = client.get("/api/anomalies")
        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "all"
        assert data["resolution_time_outliers"]["threshold_hours"] > 0

        week_response = client.get("/api/anomalies?period=week")
        assert week_response.status_code == 200
        week_data = week_response.json()
        assert week_data["period"] == "week"
        assert week_data["window_start"] is not None


def test_query_fallback_common_question(monkeypatch):
    import app.query as query_module

    def fail_llm(question, latest_created_at):
        raise RuntimeError("offline")

    monkeypatch.setattr(query_module, "generate_sql", fail_llm)

    with TestClient(app) as client:
        response = client.post("/api/query", json={"question": "How many tickets are currently open?"})
        assert response.status_code == 200
        data = response.json()
        assert data["rows"][0]["open_tickets"] == 111
        assert data["llm_used"] is False


def test_ui_is_available_without_javascript():
    with TestClient(app) as client:
        response = client.get("/?question=How%20many%20tickets%20are%20currently%20open%3F")
        assert response.status_code == 200
        assert "111" in response.text


def test_invalid_anomaly_period_returns_400():
    with TestClient(app) as client:
        response = client.get("/api/anomalies?period=year")
        assert response.status_code == 400
        assert "period must be one of" in response.json()["detail"]


def test_query_validation_rejects_empty_question():
    with TestClient(app) as client:
        response = client.post("/api/query", json={"question": ""})
        assert response.status_code == 422
