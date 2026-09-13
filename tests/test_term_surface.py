import math
from datetime import date

import pytest

from option_pricer.pricing.engine import price_option
from option_pricer.pricing.schemas import (
    ModelName,
    OptionStyle,
    OptionType,
    PriceRequest,
    TenorSlice,
    TenorVolPoint,
    TwoSided,
)
from option_pricer.pricing.term_surface import (
    forward_from_swap,
    implied_dividend,
    interpolate_vol,
    market_from_request,
)


def _tenor(tenor, swap_bid, swap_offer, vols):
    return TenorSlice(
        tenor=tenor,
        swap_points=TwoSided(bid=swap_bid, offer=swap_offer),
        vols=[TenorVolPoint(strike=k, bid=b, offer=o) for k, b, o in vols],
    )


def _surface_req(**overrides) -> PriceRequest:
    data = dict(
        spot=100,
        spot_bid=100,
        spot_offer=100,
        strike=100,
        rate=0.05,
        rate_bid=0.05,
        rate_offer=0.05,
        dividend=0.0,
        expiry_years=90 / 365,
        option_style=OptionStyle.european,
        option_type=OptionType.call,
        model=ModelName.black_scholes,
        compare_models=False,
        swap_point_scale=1.0,
        tenors=[
            _tenor(
                "1M",
                0.3,
                0.4,
                [(80, 0.242, 0.248), (100, 0.208, 0.212), (120, 0.188, 0.192)],
            ),
            _tenor(
                "3M",
                0.9,
                1.1,
                [(80, 0.232, 0.238), (100, 0.198, 0.202), (120, 0.178, 0.182)],
            ),
            _tenor(
                "6M",
                1.8,
                2.2,
                [(80, 0.226, 0.232), (100, 0.193, 0.197), (120, 0.173, 0.177)],
            ),
            _tenor(
                "1Y",
                3.8,
                4.4,
                [(80, 0.218, 0.224), (100, 0.188, 0.192), (120, 0.168, 0.172)],
            ),
        ],
    )
    data.update(overrides)
    return PriceRequest(**data)


def test_swap_points_set_the_forward():
    assert forward_from_swap(100, 40, 10000) == pytest.approx(100.004)
    assert forward_from_swap(100, 1.0, 1.0) == pytest.approx(101.0)
    q = implied_dividend(100, 101, 0.05, 1.0)
    assert 100 * math.exp((0.05 - q) * 1.0) == pytest.approx(101)


def test_three_month_expiry_uses_three_month_vol():
    market = market_from_request(_surface_req(), 90 / 365, "mid")
    assert market.smile.vol_at(100) == pytest.approx(0.200)
    assert market.forward == pytest.approx(101.0)


def test_variance_interpolation_between_tenors():
    import numpy as np

    times = np.array([90 / 365, 180 / 365])
    vols = np.array([0.20, 0.24])
    mid_t = 135 / 365
    got = interpolate_vol(times, vols, mid_t)
    w1 = 0.20**2 * times[0]
    w2 = 0.24**2 * times[1]
    expected = math.sqrt((0.5 * (w1 + w2)) / mid_t)
    assert got == pytest.approx(expected)


def test_bid_call_is_cheaper_than_offer_when_offer_vol_is_higher():
    result = price_option(_surface_req())
    assert result.vol_bid < result.vol_offer
    assert result.price_bid < result.price_offer
    assert result.price == pytest.approx(0.5 * (result.price_bid + result.price_offer), abs=0.15)


def test_expiry_date_matches_day_count():
    result = price_option(
        _surface_req(expiry_years=None, value_date=date(2026, 1, 1), expiry_date=date(2026, 4, 1))
    )
    assert result.details["days"] == 90
    assert result.details["expiry_date"] == "2026-04-01"


def test_legacy_request_still_has_equal_bid_and_offer():
    result = price_option(
        PriceRequest(
            spot=100,
            strike=100,
            rate=0.05,
            dividend=0.0,
            atm_vol=0.20,
            rr_25d=0.0,
            bf_25d=0.0,
            expiry_years=1.0,
            option_style=OptionStyle.european,
            option_type=OptionType.call,
            model=ModelName.black_scholes,
            compare_models=False,
        )
    )
    assert result.price_bid == pytest.approx(result.price)
    assert result.price_offer == pytest.approx(result.price)
    assert result.price == pytest.approx(10.4505835721, rel=1e-8)
