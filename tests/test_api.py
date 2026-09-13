from fastapi.testclient import TestClient
import pytest

from option_pricer.app import app

client = TestClient(app)


def test_health_and_index():
    assert client.get("/health").json()["status"] == "ok"
    home = client.get("/")
    assert home.status_code == 200
    assert "Option Pricer" in home.text
    assert "10Δ risk reversal" in home.text
    assert "25Δ risk reversal" in home.text
    assert "Vol surface" in home.text
    assert "Custom points" in home.text
    assert "Load from RR / BF" in home.text


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
    assert len(body["surface"]) >= 11
    assert any(row["selected"] for row in body["surface"])
    assert {p["label"] for p in body["smile"]["pillars"]} >= {
        "10Δ put",
        "25Δ put",
        "ATM",
        "25Δ call",
        "10Δ call",
    }


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
            "rr_10d": -0.022,
            "bf_10d": 0.008,
            "expiry_years": 0.25,
            "option_style": "european",
            "option_type": "call",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["vol_at_strike"] > 0
    assert payload["smile"]["vol_10d_put"] > payload["smile"]["vol_25d_put"]


def test_custom_smile_api_interpolates_and_prices():
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
            "compare_models": False,
            "smile_source": "custom",
            "custom_vols": [
                {"strike": 80, "vol": 0.26},
                {"strike": 100, "vol": 0.20},
                {"strike": 120, "vol": 0.17},
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["details"]["smile_source"] == "custom"
    assert body["details"]["input_points"] == 3
    assert {p["label"] for p in body["smile"]["pillars"]} == {"Input"}
    row80 = next(row for row in body["surface"] if abs(row["strike"] - 80) < 1e-6)
    assert row80["vol"] == pytest.approx(0.26)
    assert row80["pillar"] == "Input"
    assert body["vol_used"] == pytest.approx(0.20)


def test_custom_smile_requires_two_points():
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
            "compare_models": False,
            "smile_source": "custom",
            "custom_vols": [{"strike": 100, "vol": 0.2}],
        },
    )
    assert response.status_code == 422
