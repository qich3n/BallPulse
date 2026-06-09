import pytest
from fastapi.testclient import TestClient
from src.app.main import app

client = TestClient(app)


def test_compare_rejects_same_team():
    response = client.post(
        "/compare",
        json={"team1": "Lakers", "team2": "lakers", "sport": "basketball"},
    )
    assert response.status_code == 400
    assert "different teams" in response.json()["detail"].lower()


def test_compare_rejects_unsupported_sport():
    response = client.post(
        "/compare",
        json={"team1": "Lakers", "team2": "Celtics", "sport": "soccer"},
    )
    assert response.status_code == 400
    assert "not supported" in response.json()["detail"].lower()
