import math

import pytest

from option_pricer.pricing.black_scholes import vollib_price
from option_pricer.pricing.engine import price_option
from option_pricer.pricing.schemas import ModelName, OptionStyle, OptionType, PriceRequest


def _req(**overrides) -> PriceRequest:
    data = dict(
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
        mc_paths=80000,
        mc_steps=64,
        pde_time_steps=120,
        pde_spot_steps=240,
    )
    data.update(overrides)
    return PriceRequest(**data)


def test_european_call_matches_known_bs_value():
    result = price_option(_req())
    expected = vollib_price(True, 100, 100, 1.0, 0.05, 0.20, 0.0)
    assert result.price == pytest.approx(expected, rel=1e-10)
    assert result.details["vollib_price"] == pytest.approx(expected, rel=1e-12)
    assert result.greeks.delta == pytest.approx(0.636830651, rel=1e-6)


def test_put_call_parity():
    call = price_option(_req(option_type=OptionType.call))
    put = price_option(_req(option_type=OptionType.put))
    forward_value = 100 - 100 * math.exp(-0.05)
    assert call.price - put.price == pytest.approx(forward_value, rel=1e-8)


def test_pde_european_close_to_black_scholes():
    bs = price_option(_req(model=ModelName.black_scholes))
    pde = price_option(_req(model=ModelName.pde))
    assert pde.price == pytest.approx(bs.price, rel=2e-3, abs=0.03)


def test_monte_carlo_european_close_to_black_scholes():
    bs = price_option(_req(model=ModelName.black_scholes))
    mc = price_option(_req(model=ModelName.monte_carlo, mc_paths=120000))
    assert mc.price == pytest.approx(bs.price, abs=0.25)
    assert mc.std_error is not None
    assert mc.std_error < 0.08


def test_american_put_worth_at_least_european_put():
    euro = price_option(_req(option_type=OptionType.put, option_style=OptionStyle.european))
    amer = price_option(_req(option_type=OptionType.put, option_style=OptionStyle.american))
    assert amer.price >= euro.price - 1e-8


def test_american_call_equals_european_when_no_dividend():
    euro = price_option(_req(option_style=OptionStyle.european))
    amer = price_option(_req(option_style=OptionStyle.american))
    assert amer.price == pytest.approx(euro.price, rel=2e-3, abs=0.02)


def test_down_and_out_call_cheaper_than_vanilla():
    vanilla = price_option(_req())
    ko = price_option(
        _req(
            option_style=OptionStyle.barrier,
            barrier_type="down_and_out",
            barrier=80,
        )
    )
    assert ko.price < vanilla.price
    assert ko.price > 0


def test_knock_in_plus_knock_out_matches_vanilla():
    vanilla = price_option(_req())
    ko = price_option(
        _req(option_style=OptionStyle.barrier, barrier_type="down_and_out", barrier=80)
    )
    ki = price_option(
        _req(option_style=OptionStyle.barrier, barrier_type="down_and_in", barrier=80)
    )
    assert ko.price + ki.price == pytest.approx(vanilla.price, rel=1e-6, abs=1e-4)


def test_smile_changes_otm_put_price():
    flat = price_option(_req(option_type=OptionType.put, strike=80, rr_25d=0.0, bf_25d=0.0))
    skewed = price_option(
        _req(option_type=OptionType.put, strike=80, rr_25d=-0.04, bf_25d=0.005)
    )
    assert skewed.vol_used > flat.vol_used
    assert skewed.price > flat.price
