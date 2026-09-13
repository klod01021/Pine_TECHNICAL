"""Build a strike-by-strike vol/price slice from the fitted smile."""

from __future__ import annotations

import numpy as np

from option_pricer.pricing.black_scholes import vollib_greeks, vollib_price
from option_pricer.pricing.schemas import SurfaceRow
from option_pricer.pricing.smile import VolSmile


def _pillar_label(smile: VolSmile, strike: float) -> str | None:
    marks = (
        (smile.strike_10d_put, "10Δ put"),
        (smile.strike_25d_put, "25Δ put"),
        (smile.strike_atm, "ATM"),
        (smile.strike_25d_call, "25Δ call"),
        (smile.strike_10d_call, "10Δ call"),
    )
    for node, label in marks:
        if abs(strike - node) <= max(0.01, 0.0005 * smile.spot):
            return label
    return None


def strike_grid(smile: VolSmile, selected_strike: float, n: int = 23) -> list[float]:
    lo = min(smile.strike_10d_put, smile.spot * 0.7, selected_strike)
    hi = max(smile.strike_10d_call, smile.spot * 1.3, selected_strike)
    lo = max(lo * 0.97, smile.spot * 0.45)
    hi = max(hi * 1.03, lo * 1.05)
    grid = np.linspace(lo, hi, n).tolist()
    extras = [
        selected_strike,
        smile.strike_10d_put,
        smile.strike_25d_put,
        smile.strike_atm,
        smile.strike_25d_call,
        smile.strike_10d_call,
    ]
    strikes = sorted({round(float(k), 6) for k in grid + extras if k > 0})
    return strikes


def build_surface(
    smile: VolSmile,
    *,
    spot: float,
    rate: float,
    dividend: float,
    t: float,
    selected_strike: float,
    n: int = 23,
) -> list[SurfaceRow]:
    """Price a European call and put on every strike with that strike's smile vol."""
    rows: list[SurfaceRow] = []
    for strike in strike_grid(smile, selected_strike, n):
        vol = smile.vol_at(strike)
        call = vollib_price(True, spot, strike, t, rate, vol, dividend)
        put = vollib_price(False, spot, strike, t, rate, vol, dividend)
        call_g = vollib_greeks(True, spot, strike, t, rate, vol, dividend)
        put_g = vollib_greeks(False, spot, strike, t, rate, vol, dividend)
        rows.append(
            SurfaceRow(
                strike=strike,
                vol=vol,
                call=call,
                put=put,
                call_delta=call_g.delta,
                put_delta=put_g.delta,
                pillar=_pillar_label(smile, strike),
                selected=abs(strike - selected_strike) <= 1e-6,
            )
        )
    return rows
