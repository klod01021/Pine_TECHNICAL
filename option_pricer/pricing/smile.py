"""Build a 25-delta FX-style vol smile from ATM, risk reversal and butterfly."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

from option_pricer.pricing.schemas import SmileCurve, SmilePillar


MIN_VOL = 1e-4
MAX_VOL = 5.0


@dataclass(frozen=True)
class VolSmile:
    spot: float
    forward: float
    t: float
    atm_vol: float
    vol_25d_put: float
    vol_25d_call: float
    strike_25d_put: float
    strike_atm: float
    strike_25d_call: float
    coeffs: tuple[float, float, float]
    warnings: tuple[str, ...] = ()

    def vol_at(self, strike: float) -> float:
        strike = float(strike)
        if strike <= 0:
            raise ValueError("strike must be positive")
        x = np.log(strike / self.forward)
        a, b, c = self.coeffs
        vol = float(a + b * x + c * x * x)
        return float(np.clip(vol, MIN_VOL, MAX_VOL))

    def curve(self, n: int = 61) -> SmileCurve:
        lo = min(self.strike_25d_put, self.spot * 0.6, self.strike_atm * 0.7)
        hi = max(self.strike_25d_call, self.spot * 1.4, self.strike_atm * 1.3)
        lo = max(lo, self.spot * 0.4)
        hi = max(hi, lo * 1.05)
        strikes = np.linspace(lo, hi, n)
        vols = [self.vol_at(k) for k in strikes]
        pillars = [
            SmilePillar(
                label="25Δ put",
                delta=-0.25,
                strike=self.strike_25d_put,
                vol=self.vol_25d_put,
            ),
            SmilePillar(
                label="ATM",
                delta=0.50,
                strike=self.strike_atm,
                vol=self.atm_vol,
            ),
            SmilePillar(
                label="25Δ call",
                delta=0.25,
                strike=self.strike_25d_call,
                vol=self.vol_25d_call,
            ),
        ]
        return SmileCurve(
            strikes=strikes.tolist(),
            vols=vols,
            pillars=pillars,
            vol_25d_put=self.vol_25d_put,
            vol_atm=self.atm_vol,
            vol_25d_call=self.vol_25d_call,
            forward=self.forward,
        )


def _forward_delta_strike(forward: float, vol: float, t: float, target_delta: float) -> float:
    """Invert forward delta N(d1) = target_delta for a call (put uses 1+put_delta)."""
    vol = max(vol, MIN_VOL)
    sqrt_t = np.sqrt(t)
    d1 = float(norm.ppf(target_delta))
    return float(forward * np.exp(-d1 * vol * sqrt_t + 0.5 * vol * vol * t))


def build_smile(
    spot: float,
    rate: float,
    dividend: float,
    t: float,
    atm_vol: float,
    rr_25d: float,
    bf_25d: float,
) -> VolSmile:
    """
    Market quoting convention (25-delta):

        RR = σ_25c − σ_25p
        BF = 0.5 (σ_25c + σ_25p) − σ_ATM

    so σ_25c = ATM + BF + RR/2 and σ_25p = ATM + BF − RR/2.

    Wing vols are mapped to strikes with *forward* delta, then a unique
    quadratic in log-moneyness x = ln(K/F) is fitted through the three pillars.
    """
    warnings: list[str] = []
    t = max(float(t), 1.0 / 365.0)
    atm_vol = float(np.clip(atm_vol, MIN_VOL, MAX_VOL))
    vol_25c = atm_vol + bf_25d + 0.5 * rr_25d
    vol_25p = atm_vol + bf_25d - 0.5 * rr_25d

    if vol_25c < MIN_VOL or vol_25p < MIN_VOL:
        warnings.append("25-delta wing vol was clamped to a positive floor.")
    vol_25c = float(np.clip(vol_25c, MIN_VOL, MAX_VOL))
    vol_25p = float(np.clip(vol_25p, MIN_VOL, MAX_VOL))

    forward = float(spot * np.exp((rate - dividend) * t))
    # ATM-forward strike (K = F). Wings use 25-delta forward call deltas.
    strike_atm = forward
    strike_25c = _forward_delta_strike(forward, vol_25c, t, 0.25)
    strike_25p = _forward_delta_strike(forward, vol_25p, t, 0.75)

    xs = np.array(
        [
            np.log(strike_25p / forward),
            0.0,
            np.log(strike_25c / forward),
        ],
        dtype=float,
    )
    ys = np.array([vol_25p, atm_vol, vol_25c], dtype=float)
    matrix = np.column_stack([np.ones(3), xs, xs * xs])
    try:
        if abs(np.linalg.det(matrix)) < 1e-14:
            raise np.linalg.LinAlgError("degenerate smile nodes")
        coeffs = tuple(float(v) for v in np.linalg.solve(matrix, ys))
    except np.linalg.LinAlgError:
        coeffs = (atm_vol, 0.0, 0.0)
        warnings.append("Smile nodes were degenerate; using a flat ATM vol.")

    return VolSmile(
        spot=float(spot),
        forward=forward,
        t=t,
        atm_vol=atm_vol,
        vol_25d_put=vol_25p,
        vol_25d_call=vol_25c,
        strike_25d_put=float(strike_25p),
        strike_atm=float(strike_atm),
        strike_25d_call=float(strike_25c),
        coeffs=coeffs,
        warnings=tuple(warnings),
    )
