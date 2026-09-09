"""Finite-difference (PDE) pricing via QuantLib Black-Scholes engines."""

from __future__ import annotations

import QuantLib as ql

from option_pricer.pricing.ql_market import (
    barrier_type,
    build_market,
    option_type,
    quantlib_session,
    read_greeks,
)
from option_pricer.pricing.black_scholes import _bump_greeks_quotes
from option_pricer.pricing.schemas import Greeks


def price_pde(
    *,
    days: int,
    spot: float,
    strike: float,
    rate: float,
    dividend: float,
    vol: float,
    is_call: bool,
    style: str,
    time_steps: int,
    spot_steps: int,
    barrier_kind: str | None = None,
    barrier: float | None = None,
    rebate: float = 0.0,
) -> dict:
    with quantlib_session(days) as (today, maturity):
        market = build_market(today, maturity, spot, rate, dividend, vol)
        payoff = ql.PlainVanillaPayoff(option_type(is_call), strike)

        if style == "american":
            exercise = ql.AmericanExercise(today, maturity)
            option = ql.VanillaOption(payoff, exercise)
            option.setPricingEngine(
                ql.FdBlackScholesVanillaEngine(market.process, time_steps, spot_steps)
            )
            engine_name = "QuantLib FdBlackScholesVanillaEngine (American)"
        elif style == "barrier":
            exercise = ql.EuropeanExercise(maturity)
            option = ql.BarrierOption(
                barrier_type(barrier_kind),
                float(barrier),
                float(rebate),
                payoff,
                exercise,
            )
            option.setPricingEngine(
                ql.FdBlackScholesBarrierEngine(market.process, time_steps, spot_steps)
            )
            engine_name = "QuantLib FdBlackScholesBarrierEngine"
        else:
            exercise = ql.EuropeanExercise(maturity)
            option = ql.VanillaOption(payoff, exercise)
            option.setPricingEngine(
                ql.FdBlackScholesVanillaEngine(market.process, time_steps, spot_steps)
            )
            engine_name = "QuantLib FdBlackScholesVanillaEngine (European)"

        price = float(option.NPV())
        greeks = Greeks(**read_greeks(option))
        if greeks.delta is None:
            greeks = _bump_greeks_quotes(market, option, vol)
        return {"price": price, "greeks": greeks, "engine": engine_name}
