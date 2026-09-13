"""Build a 10-delta / 25-delta FX-style vol smile from ATM, RR and butterfly."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.stats import norm

from option_pricer.pricing.schemas import SmileCurve, SmilePillar


MIN_VOL = 1e-4
MAX_VOL = 5.0


def _clip_vol(vol: float) -> float:
    return float(np.clip(vol, MIN_VOL, MAX_VOL))


def _wing_vols(atm_vol: float, butterfly: float, risk_reversal: float) -> tuple[float, float]:
    """Return (put vol, call vol) from ATM + BF + RR quotes."""
    call = atm_vol + butterfly + 0.5 * risk_reversal
    put = atm_vol + butterfly - 0.5 * risk_reversal
    return put, call


def _forward_delta_strike(forward: float, vol: float, t: float, target_delta: float) -> float:
    """Invert forward delta N(d1) = target_delta for a call (put uses 1 + put_delta)."""
    vol = max(vol, MIN_VOL)
    sqrt_t = np.sqrt(t)
    d1 = float(norm.ppf(target_delta))
    return float(forward * np.exp(-d1 * vol * sqrt_t + 0.5 * vol * vol * t))


def _quadratic_through_25d(
    forward: float,
    strike_25p: float,
    strike_25c: float,
    vol_25p: float,
    atm_vol: float,
    vol_25c: float,
) -> tuple[tuple[float, float, float], bool]:
    xs = np.array(
        [np.log(strike_25p / forward), 0.0, np.log(strike_25c / forward)],
        dtype=float,
    )
    ys = np.array([vol_25p, atm_vol, vol_25c], dtype=float)
    matrix = np.column_stack([np.ones(3), xs, xs * xs])
    try:
        if abs(np.linalg.det(matrix)) < 1e-14:
            raise np.linalg.LinAlgError("degenerate smile nodes")
        coeffs = tuple(float(v) for v in np.linalg.solve(matrix, ys))
        return coeffs, True
    except np.linalg.LinAlgError:
        return (atm_vol, 0.0, 0.0), False


def _quad_vol(coeffs: tuple[float, float, float], forward: float, strike: float) -> float:
    x = np.log(strike / forward)
    a, b, c = coeffs
    return _clip_vol(a + b * x + c * x * x)


def _unique_nodes(xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]
    keep_x = [float(xs[0])]
    keep_y = [float(ys[0])]
    for x, y in zip(xs[1:], ys[1:]):
        if x - keep_x[-1] > 1e-10:
            keep_x.append(float(x))
            keep_y.append(float(y))
        else:
            keep_y[-1] = 0.5 * (keep_y[-1] + float(y))
    return np.array(keep_x), np.array(keep_y)


@dataclass(frozen=True)
class VolSmile:
    spot: float
    forward: float
    t: float
    atm_vol: float
    vol_10d_put: float
    vol_25d_put: float
    vol_25d_call: float
    vol_10d_call: float
    strike_10d_put: float
    strike_25d_put: float
    strike_atm: float
    strike_25d_call: float
    strike_10d_call: float
    nodes_x: tuple[float, ...]
    nodes_vol: tuple[float, ...]
    coeffs: tuple[float, float, float]
    ten_delta_source: str
    warnings: tuple[str, ...] = ()

    def vol_at(self, strike: float) -> float:
        strike = float(strike)
        if strike <= 0:
            raise ValueError("strike must be positive")
        x = float(np.log(strike / self.forward))
        xs = np.asarray(self.nodes_x, dtype=float)
        ys = np.asarray(self.nodes_vol, dtype=float)
        if x <= xs[0]:
            return _clip_vol(ys[0])
        if x >= xs[-1]:
            return _clip_vol(ys[-1])
        if len(xs) == 1:
            return _clip_vol(ys[0])
        if len(xs) == 2:
            return _clip_vol(float(np.interp(x, xs, ys)))
        interpolator = PchipInterpolator(xs, ys, extrapolate=False)
        return _clip_vol(float(interpolator(x)))

    def curve(self, n: int = 61) -> SmileCurve:
        lo = min(self.strike_10d_put, self.spot * 0.55, self.strike_atm * 0.65)
        hi = max(self.strike_10d_call, self.spot * 1.45, self.strike_atm * 1.35)
        lo = max(lo, self.spot * 0.35)
        hi = max(hi, lo * 1.05)
        strikes = np.linspace(lo, hi, n)
        vols = [self.vol_at(k) for k in strikes]
        pillars = [
            SmilePillar(label="10Δ put", delta=-0.10, strike=self.strike_10d_put, vol=self.vol_10d_put),
            SmilePillar(label="25Δ put", delta=-0.25, strike=self.strike_25d_put, vol=self.vol_25d_put),
            SmilePillar(label="ATM", delta=0.50, strike=self.strike_atm, vol=self.atm_vol),
            SmilePillar(label="25Δ call", delta=0.25, strike=self.strike_25d_call, vol=self.vol_25d_call),
            SmilePillar(label="10Δ call", delta=0.10, strike=self.strike_10d_call, vol=self.vol_10d_call),
        ]
        return SmileCurve(
            strikes=strikes.tolist(),
            vols=vols,
            pillars=pillars,
            vol_10d_put=self.vol_10d_put,
            vol_25d_put=self.vol_25d_put,
            vol_atm=self.atm_vol,
            vol_25d_call=self.vol_25d_call,
            vol_10d_call=self.vol_10d_call,
            forward=self.forward,
        )


def build_smile(
    spot: float,
    rate: float,
    dividend: float,
    t: float,
    atm_vol: float,
    rr_25d: float,
    bf_25d: float,
    rr_10d: float | None = None,
    bf_10d: float | None = None,
) -> VolSmile:
    """
    Market quoting convention (same for 10-delta and 25-delta):

        RR = σ_call − σ_put
        BF = 0.5 (σ_call + σ_put) − σ_ATM

    so σ_call = ATM + BF + RR/2 and σ_put = ATM + BF − RR/2.

    25-delta pillars are always quoted. If 10-delta RR/BF are omitted, 10-delta
    vols are read off the 25-delta quadratic. Quoted 10-delta points are then
    interpolated with the 25-delta / ATM pillars in log-moneyness (PCHIP),
    with flat extrapolation outside the 10-delta wings.
    """
    warnings: list[str] = []
    t = max(float(t), 1.0 / 365.0)
    atm_vol = _clip_vol(float(atm_vol))

    vol_25p, vol_25c = _wing_vols(atm_vol, bf_25d, rr_25d)
    if vol_25c < MIN_VOL or vol_25p < MIN_VOL:
        warnings.append("25-delta wing vol was clamped to a positive floor.")
    vol_25c = _clip_vol(vol_25c)
    vol_25p = _clip_vol(vol_25p)

    forward = float(spot * np.exp((rate - dividend) * t))
    strike_atm = forward
    strike_25c = _forward_delta_strike(forward, vol_25c, t, 0.25)
    strike_25p = _forward_delta_strike(forward, vol_25p, t, 0.75)

    coeffs, ok = _quadratic_through_25d(
        forward, strike_25p, strike_25c, vol_25p, atm_vol, vol_25c
    )
    if not ok:
        warnings.append("25-delta smile nodes were degenerate; using a flat ATM vol.")

    quoted_10d = rr_10d is not None or bf_10d is not None
    if quoted_10d:
        rr_10 = 0.0 if rr_10d is None else float(rr_10d)
        bf_10 = 0.0 if bf_10d is None else float(bf_10d)
        vol_10p, vol_10c = _wing_vols(atm_vol, bf_10, rr_10)
        if vol_10c < MIN_VOL or vol_10p < MIN_VOL:
            warnings.append("10-delta wing vol was clamped to a positive floor.")
        vol_10c = _clip_vol(vol_10c)
        vol_10p = _clip_vol(vol_10p)
        strike_10c = _forward_delta_strike(forward, vol_10c, t, 0.10)
        strike_10p = _forward_delta_strike(forward, vol_10p, t, 0.90)
        ten_delta_source = "quoted"
    else:
        strike_10c = _forward_delta_strike(forward, atm_vol, t, 0.10)
        strike_10p = _forward_delta_strike(forward, atm_vol, t, 0.90)
        vol_10c = _quad_vol(coeffs, forward, strike_10c)
        vol_10p = _quad_vol(coeffs, forward, strike_10p)
        strike_10c = _forward_delta_strike(forward, vol_10c, t, 0.10)
        strike_10p = _forward_delta_strike(forward, vol_10p, t, 0.90)
        vol_10c = _quad_vol(coeffs, forward, strike_10c)
        vol_10p = _quad_vol(coeffs, forward, strike_10p)
        ten_delta_source = "implied_from_25d"

    xs, ys = _unique_nodes(
        np.array(
            [
                np.log(strike_10p / forward),
                np.log(strike_25p / forward),
                0.0,
                np.log(strike_25c / forward),
                np.log(strike_10c / forward),
            ],
            dtype=float,
        ),
        np.array([vol_10p, vol_25p, atm_vol, vol_25c, vol_10c], dtype=float),
    )
    if len(xs) < 3:
        warnings.append("Some smile strikes collapsed; interpolation used fewer pillars.")

    return VolSmile(
        spot=float(spot),
        forward=forward,
        t=t,
        atm_vol=atm_vol,
        vol_10d_put=float(vol_10p),
        vol_25d_put=float(vol_25p),
        vol_25d_call=float(vol_25c),
        vol_10d_call=float(vol_10c),
        strike_10d_put=float(strike_10p),
        strike_25d_put=float(strike_25p),
        strike_atm=float(strike_atm),
        strike_25d_call=float(strike_25c),
        strike_10d_call=float(strike_10c),
        nodes_x=tuple(float(v) for v in xs),
        nodes_vol=tuple(float(v) for v in ys),
        coeffs=coeffs,
        ten_delta_source=ten_delta_source,
        warnings=tuple(warnings),
    )
