"""Black-Scholes family: analytic European, American approximation, barrier closed form."""

from __future__ import annotations

import QuantLib as ql
from vollib.black_scholes_merton import black_scholes_merton
from vollib.black_scholes_merton.greeks.analytical import (
    delta as bsm_delta,
    gamma as bsm_gamma,
    rho as bsm_rho,
    theta as bsm_theta,
    vega as bsm_vega,
)
from vollib.black_scholes_merton.implied_volatility import implied_volatility

from option_pricer.pricing.ql_market import (
    barrier_type,
    build_market,
    option_type,
    quantlib_session,
    read_greeks,
)
from option_pricer.pricing.schemas import Greeks


def vollib_price(is_call: bool, spot, strike, t, rate, vol, dividend) -> float:
    flag = "c" if is_call else "p"
    return float(black_scholes_merton(flag, spot, strike, t, rate, vol, dividend))


def vollib_greeks(is_call: bool, spot, strike, t, rate, vol, dividend) -> Greeks:
    flag = "c" if is_call else "p"
    args = (flag, spot, strike, t, rate, vol, dividend)
    return Greeks(
        delta=float(bsm_delta(*args)),
        gamma=float(bsm_gamma(*args)),
        vega=float(bsm_vega(*args)),
        theta=float(bsm_theta(*args)),
        rho=float(bsm_rho(*args)),
    )


def vollib_implied_vol(price, spot, strike, t, rate, dividend, is_call) -> float | None:
    flag = "c" if is_call else "p"
    try:
        iv = float(implied_volatility(price, spot, strike, t, rate, dividend, flag))
        if iv != iv or iv <= 0:
            return None
        return iv
    except Exception:
        return None


def price_black_scholes(
    *,
    days: int,
    t: float,
    spot: float,
    strike: float,
    rate: float,
    dividend: float,
    vol: float,
    is_call: bool,
    style: str,
    barrier_kind: str | None = None,
    barrier: float | None = None,
    rebate: float = 0.0,
) -> dict:
    with quantlib_session(days) as (today, maturity):
        market = build_market(today, maturity, spot, rate, dividend, vol)
        payoff = ql.PlainVanillaPayoff(option_type(is_call), strike)

        if style == "european":
            option = ql.VanillaOption(payoff, ql.EuropeanExercise(maturity))
            option.setPricingEngine(ql.AnalyticEuropeanEngine(market.process))
            price = float(option.NPV())
            greeks = Greeks(**read_greeks(option))
            v_price = vollib_price(is_call, spot, strike, t, rate, vol, dividend)
            v_greeks = vollib_greeks(is_call, spot, strike, t, rate, vol, dividend)
            return {
                "price": price,
                "greeks": greeks,
                "vollib_price": v_price,
                "vollib_greeks": v_greeks.model_dump(),
                "engine": "QuantLib AnalyticEuropeanEngine + vollib BSM",
            }

        if style == "american":
            option = ql.VanillaOption(payoff, ql.AmericanExercise(today, maturity))
            option.setPricingEngine(
                ql.BjerksundStenslandApproximationEngine(market.process)
            )
            price = float(option.NPV())
            greeks = Greeks(**read_greeks(option))
            if greeks.delta is None:
                greeks = _bump_greeks_quotes(market, option, vol)
            return {
                "price": price,
                "greeks": greeks,
                "engine": "QuantLib Bjerksund-Stensland (Black-Scholes American)",
            }

        option = ql.BarrierOption(
            barrier_type(barrier_kind),
            float(barrier),
            float(rebate),
            payoff,
            ql.EuropeanExercise(maturity),
        )
        option.setPricingEngine(ql.AnalyticBarrierEngine(market.process))
        price = float(option.NPV())
        greeks = Greeks(**read_greeks(option))
        if greeks.delta is None:
            greeks = _bump_greeks_quotes(market, option, vol)
        return {
            "price": price,
            "greeks": greeks,
            "engine": "QuantLib AnalyticBarrierEngine (Reiner-Rubinstein)",
        }


def _bump_greeks_quotes(market, option, vol: float) -> Greeks:
    base = float(option.NPV())
    spot0 = market.spot_quote.value()
    ds = max(1e-4 * spot0, 1e-6)
    market.spot_quote.setValue(spot0 + ds)
    up = float(option.NPV())
    market.spot_quote.setValue(spot0 - ds)
    dn = float(option.NPV())
    market.spot_quote.setValue(spot0)
    delta = (up - dn) / (2.0 * ds)
    gamma = (up - 2.0 * base + dn) / (ds * ds)

    dv = 0.0001
    market.vol_quote.setValue(vol + dv)
    v_up = float(option.NPV())
    market.vol_quote.setValue(vol - dv)
    v_dn = float(option.NPV())
    market.vol_quote.setValue(vol)
    vega = (v_up - v_dn) / (2.0 * dv) / 100.0

    r0 = market.rate_quote.value()
    dr = 1e-4
    market.rate_quote.setValue(r0 + dr)
    r_up = float(option.NPV())
    market.rate_quote.setValue(r0)
    rho = (r_up - base) / dr / 100.0

    return Greeks(delta=delta, gamma=gamma, vega=vega, theta=None, rho=rho)
