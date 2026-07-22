from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_is_public(monkeypatch):
    monkeypatch.setenv("STE_API_KEY", "secret")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_key_is_enforced(monkeypatch):
    monkeypatch.setenv("STE_API_KEY", "secret")
    denied = client.post("/v1/analyze", json={"text": "Remove the panel."})
    assert denied.status_code == 401

    allowed = client.post(
        "/v1/analyze",
        headers={"Authorization": "Bearer secret"},
        json={"text": "Remove the panel."},
    )
    assert allowed.status_code == 200


def test_rewrite_and_compare_preserve_literal(monkeypatch):
    monkeypatch.delenv("STE_API_KEY", raising=False)
    rewrite = client.post(
        "/v1/rewrite",
        json={
            "text": "Prior to the test, utilize UNIT-42.",
            "document_type": "procedure",
            "strategy": "direct",
        },
    )
    assert rewrite.status_code == 200
    body = rewrite.json()
    assert "Before" in body["revised"]
    assert "use UNIT-42" in body["revised"]
    assert body["protected_literals"]["missing_from_revised"] == []

    comparison = client.post(
        "/v1/compare",
        json={
            "original": "Set the pressure to 120 kPa.",
            "revised": "Set the pressure to 100 kPa.",
        },
    )
    assert comparison.status_code == 200
    assert "120 kPa" in comparison.json()["preserved_literals"]["missing_from_revised"]
