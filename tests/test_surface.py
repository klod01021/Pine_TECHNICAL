import math

import pytest

from option_pricer.pricing.black_scholes import vollib_price
from option_pricer.pricing.engine import price_option
from option_pricer.pricing.schemas import ModelName, OptionStyle, OptionType, PriceRequest
from option_pricer.pricing.smile import build_smile
from option_pricer.pricing.surface import build_surface


def _req(**overrides) -> PriceRequest:
    data = dict(
        spot=100,
        strike=100,
        rate=0.05,
        dividend=0.0,
        atm_vol=0.20,
        rr_25d=-0.012,
        bf_25d=0.004,
        rr_10d=-0.022,
        bf_10d=0.008,
        expiry_years=1.0,
        option_style=OptionStyle.european,
        option_type=OptionType.call,
        model=ModelName.black_scholes,
        compare_models=False,
        surface_points=21,
    )
    data.update(overrides)
    return PriceRequest(**data)


def test_surface_has_a_row_for_many_strikes_with_own_vol():
    result = price_option(_req())
    assert len(result.surface) >= 15
    selected = [row for row in result.surface if row.selected]
    assert len(selected) == 1
    assert selected[0].strike == pytest.approx(100)
    vols = {round(row.vol, 6) for row in result.surface}
    assert len(vols) > 1
    pillars = {row.pillar for row in result.surface if row.pillar}
    assert {"10Δ put", "25Δ put", "ATM", "25Δ call", "10Δ call"} <= pillars


def test_each_surface_row_matches_sticky_strike_bs():
    result = price_option(_req())
    t = result.details["time_years"]
    for row in result.surface:
        assert row.call == pytest.approx(
            vollib_price(True, 100, row.strike, t, 0.05, row.vol, 0.0), rel=1e-10
        )
        assert row.put == pytest.approx(
            vollib_price(False, 100, row.strike, t, 0.05, row.vol, 0.0), rel=1e-10
        )
        rhs = 100 - row.strike * math.exp(-0.05 * t)
        assert row.call - row.put == pytest.approx(rhs, rel=1e-8, abs=1e-8)


def test_skew_makes_low_strike_vol_higher_than_high_strike():
    smile = build_smile(100, 0.05, 0.0, 1.0, 0.20, -0.012, 0.004, -0.022, 0.008)
    rows = build_surface(
        smile, spot=100, rate=0.05, dividend=0.0, t=1.0, selected_strike=100, n=21
    )
    low = min(rows, key=lambda r: r.strike)
    high = max(rows, key=lambda r: r.strike)
    assert low.vol > high.vol
    assert low.put > 0
    assert high.call > 0


def test_selected_contract_price_matches_surface_call_at_that_strike():
    result = price_option(_req(strike=110))
    match = next(row for row in result.surface if abs(row.strike - 110) < 1e-6)
    assert result.price == pytest.approx(match.call, rel=2e-4, abs=1e-3)
    assert result.vol_used == pytest.approx(match.vol, rel=1e-10)
