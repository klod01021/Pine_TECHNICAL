from fastapi.testclient import TestClient
import pytest

from option_pricer.app import app

client = TestClient(app)


def test_health_and_index():
    assert client.get("/health").json()["status"] == "ok"
    home = client.get("/")
    assert home.status_code == 200
    assert "Option Pricer" in home.text


def test_price_european_call_api():
    response = client.post(
        "/api/price",
        json={
            "spot": 100,
            "strike": 100,
            "rate": 0.05,
            "dividend": 0.0,
            "atm_vol": 0.2,
            "rr_25d": 0.0,
            "bf_25d": 0.0,
            "expiry_years": 1,
            "option_style": "european",
            "option_type": "call",
            "model": "black_scholes",
            "compare_models": True,
            "mc_paths": 8000,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["price"] == pytest.approx(10.4505835721, rel=1e-8)
    labels = {row["model"] for row in body["comparison"]}
    assert labels == {"black_scholes", "pde", "monte_carlo"}
    assert len(body["smile"]["strikes"]) > 10


def test_barrier_requires_level():
    response = client.post(
        "/api/price",
        json={
            "spot": 100,
            "strike": 100,
            "rate": 0.05,
            "dividend": 0.0,
            "atm_vol": 0.2,
            "rr_25d": 0.0,
            "bf_25d": 0.0,
            "expiry_years": 0.5,
            "option_style": "barrier",
            "option_type": "call",
            "model": "black_scholes",
            "compare_models": False,
        },
    )
    assert response.status_code == 422


def test_smile_endpoint():
    response = client.post(
        "/api/smile",
        json={
            "spot": 100,
            "strike": 105,
            "rate": 0.03,
            "dividend": 0.01,
            "atm_vol": 0.18,
            "rr_25d": -0.01,
            "bf_25d": 0.003,
            "expiry_years": 0.25,
            "option_style": "european",
            "option_type": "call",
        },
    )
    assert response.status_code == 200
    assert response.json()["vol_at_strike"] > 0
