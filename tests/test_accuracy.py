"""Accuracy checks against closed-form BSM, identities, and a binomial American benchmark."""

import math

import pytest
import QuantLib as ql

from option_pricer.pricing.black_scholes import vollib_greeks, vollib_price
from option_pricer.pricing.engine import price_option
from option_pricer.pricing.ql_market import quantlib_session, year_fraction
from option_pricer.pricing.schemas import ModelName, OptionStyle, OptionType, PriceRequest
from option_pricer.pricing.smile import build_smile


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
        mc_paths=100000,
        mc_steps=96,
        pde_time_steps=150,
        pde_spot_steps=300,
        seed=42,
    )
    data.update(overrides)
    return PriceRequest(**data)


def _t(expiry_years: float) -> float:
    _, t = year_fraction(expiry_years)
    return t


def test_black_scholes_matches_vollib_to_machine_precision():
    cases = [
        (OptionType.call, 100, 1.0, 0.0),
        (OptionType.put, 100, 1.0, 0.0),
        (OptionType.call, 120, 0.25, 0.0),
        (OptionType.put, 110, 0.5, 0.02),
    ]
    for option_type, strike, expiry, dividend in cases:
        is_call = option_type is OptionType.call
        t = _t(expiry)
        ref = vollib_price(is_call, 100, strike, t, 0.05, 0.20, dividend)
        gref = vollib_greeks(is_call, 100, strike, t, 0.05, 0.20, dividend)
        got = price_option(
            _req(
                option_type=option_type,
                strike=strike,
                expiry_years=expiry,
                dividend=dividend,
            )
        )
        assert got.price == pytest.approx(ref, rel=1e-12, abs=1e-12)
        assert got.greeks.delta == pytest.approx(gref.delta, rel=1e-10, abs=1e-10)
        assert got.greeks.vega == pytest.approx(gref.vega, rel=1e-10, abs=1e-10)
        assert got.greeks.theta == pytest.approx(gref.theta, rel=1e-10, abs=1e-10)


def test_put_call_parity_across_tenors():
    for expiry, dividend, strike in ((1.0, 0.0, 100), (0.25, 0.01, 90), (2.0, 0.03, 110)):
        t = _t(expiry)
        call = price_option(
            _req(expiry_years=expiry, dividend=dividend, strike=strike, option_type=OptionType.call)
        )
        put = price_option(
            _req(expiry_years=expiry, dividend=dividend, strike=strike, option_type=OptionType.put)
        )
        rhs = 100 * math.exp(-dividend * t) - strike * math.exp(-0.05 * t)
        assert call.price - put.price == pytest.approx(rhs, rel=1e-12, abs=1e-12)


def test_pde_european_error_under_one_tenth_of_a_cent_atm():
    for kwargs in (
        {},
        {"strike": 120},
        {"strike": 90, "option_type": OptionType.put},
        {"expiry_years": 7 / 365},
    ):
        bs = price_option(_req(model=ModelName.black_scholes, **kwargs))
        pde = price_option(_req(model=ModelName.pde, **kwargs))
        assert pde.price == pytest.approx(bs.price, rel=2e-4, abs=1e-3)


def test_monte_carlo_european_within_three_standard_errors():
    for kwargs in (
        {},
        {"strike": 120},
        {"strike": 90, "option_type": OptionType.put},
    ):
        bs = price_option(_req(model=ModelName.black_scholes, **kwargs))
        mc = price_option(_req(model=ModelName.monte_carlo, **kwargs))
        assert mc.std_error is not None
        assert abs(mc.price - bs.price) < 3.0 * mc.std_error


@pytest.mark.parametrize(
    "kind_out,kind_in,barrier,option_type",
    [
        ("down_and_out", "down_and_in", 80, OptionType.call),
        ("up_and_out", "up_and_in", 130, OptionType.call),
        ("down_and_out", "down_and_in", 85, OptionType.put),
    ],
)
def test_barrier_in_out_parity(kind_out, kind_in, barrier, option_type):
    vanilla = price_option(_req(option_type=option_type))
    ko = price_option(
        _req(
            option_style=OptionStyle.barrier,
            barrier_type=kind_out,
            barrier=barrier,
            option_type=option_type,
        )
    )
    ki = price_option(
        _req(
            option_style=OptionStyle.barrier,
            barrier_type=kind_in,
            barrier=barrier,
            option_type=option_type,
        )
    )
    assert ko.price + ki.price == pytest.approx(vanilla.price, rel=1e-12, abs=1e-12)


def test_barrier_pde_matches_analytic_down_and_out():
    kwargs = dict(option_style=OptionStyle.barrier, barrier_type="down_and_out", barrier=80)
    bs = price_option(_req(model=ModelName.black_scholes, **kwargs))
    pde = price_option(_req(model=ModelName.pde, **kwargs))
    assert pde.price == pytest.approx(bs.price, rel=1e-6, abs=1e-5)


def test_american_put_pde_matches_binomial_better_than_bjerksund():
    pde = price_option(
        _req(option_style=OptionStyle.american, option_type=OptionType.put, model=ModelName.pde)
    )
    approx = price_option(
        _req(
            option_style=OptionStyle.american,
            option_type=OptionType.put,
            model=ModelName.black_scholes,
        )
    )
    binomial = _binomial_american_put()
    assert pde.price == pytest.approx(binomial, rel=5e-4, abs=5e-3)
    assert abs(pde.price - binomial) < abs(approx.price - binomial)
    euro = price_option(_req(option_style=OptionStyle.european, option_type=OptionType.put))
    assert pde.price > euro.price


def test_rr_bf_identities_and_skew_reprices_otm_put():
    smile = build_smile(100, 0.05, 0.01, 0.5, 0.20, -0.012, 0.004)
    assert smile.vol_25d_call - smile.vol_25d_put == pytest.approx(-0.012, abs=1e-15)
    assert 0.5 * (smile.vol_25d_call + smile.vol_25d_put) - 0.20 == pytest.approx(0.004, abs=1e-15)
    flat = price_option(_req(option_type=OptionType.put, strike=80))
    skew = price_option(_req(option_type=OptionType.put, strike=80, rr_25d=-0.04, bf_25d=0.005))
    assert skew.vol_used == pytest.approx(0.26774, rel=1e-4)
    assert skew.price > flat.price + 0.5


def _binomial_american_put() -> float:
    with quantlib_session(365) as (today, maturity):
        day_count = ql.Actual365Fixed()
        process = ql.BlackScholesMertonProcess(
            ql.QuoteHandle(ql.SimpleQuote(100.0)),
            ql.YieldTermStructureHandle(ql.FlatForward(today, 0.0, day_count)),
            ql.YieldTermStructureHandle(ql.FlatForward(today, 0.05, day_count)),
            ql.BlackVolTermStructureHandle(
                ql.BlackConstantVol(today, ql.NullCalendar(), 0.2, day_count)
            ),
        )
        option = ql.VanillaOption(
            ql.PlainVanillaPayoff(ql.Option.Put, 100.0),
            ql.AmericanExercise(today, maturity),
        )
        option.setPricingEngine(ql.BinomialCRRVanillaEngine(process, 800))
        return float(option.NPV())
