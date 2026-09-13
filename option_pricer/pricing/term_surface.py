"""Multi-tenor vol surface with swap points and bid / offer sides."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from option_pricer.pricing.smile import MIN_VOL, VolSmile, build_smile_from_points

TENORS = ("1M", "3M", "6M", "1Y")
TENOR_DAYS = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365}


def tenor_year_fraction(tenor: str, override: float | None = None) -> float:
    if override is not None and override > 0:
        return float(override)
    if tenor not in TENOR_DAYS:
        raise ValueError(f"Unsupported tenor {tenor!r}; use 1M, 3M, 6M or 1Y")
    return TENOR_DAYS[tenor] / 365.0


def forward_from_swap(spot: float, swap_points: float, scale: float = 1.0) -> float:
    scale = 1.0 if scale == 0 else float(scale)
    forward = float(spot) + float(swap_points) / scale
    if forward <= 0:
        raise ValueError("Forward must stay positive; check spot and swap points")
    return forward


def implied_dividend(spot: float, forward: float, rate: float, t: float) -> float:
    t = max(float(t), 1.0 / 365.0)
    return float(rate) - math.log(float(forward) / float(spot)) / t


def interpolate_level(times: np.ndarray, values: np.ndarray, t: float) -> float:
    times = np.asarray(times, dtype=float)
    values = np.asarray(values, dtype=float)
    if t <= times[0]:
        return float(values[0])
    if t >= times[-1]:
        return float(values[-1])
    return float(np.interp(t, times, values))


def interpolate_vol(times: np.ndarray, vols: np.ndarray, t: float) -> float:
    """Flat vol outside the quoted tenors; linear total variance between them."""
    times = np.asarray(times, dtype=float)
    vols = np.clip(np.asarray(vols, dtype=float), MIN_VOL, None)
    t = max(float(t), 1.0 / 365.0)
    if t <= times[0]:
        return float(vols[0])
    if t >= times[-1]:
        return float(vols[-1])
    total_var = vols * vols * times
    blended = float(np.interp(t, times, total_var))
    return float(math.sqrt(max(blended, MIN_VOL * MIN_VOL * t) / t))


def two_sided(bid: float | None, offer: float | None, mid: float | None, side: str) -> float:
    if bid is None and offer is None:
        if mid is None:
            raise ValueError("Missing bid/offer value")
        return float(mid)
    if bid is None:
        bid = offer if offer is not None else mid
    if offer is None:
        offer = bid if bid is not None else mid
    if side == "bid":
        return float(bid)
    if side == "offer":
        return float(offer)
    return 0.5 * (float(bid) + float(offer))


@dataclass(frozen=True)
class MarketSide:
    spot: float
    rate: float
    dividend: float
    forward: float
    swap_points: float
    smile: VolSmile
    side: str


@dataclass
class _TenorPillar:
    tenor: str
    t: float
    swap_bid: float
    swap_offer: float
    points_bid: list[tuple[float, float]]
    points_offer: list[tuple[float, float]]


def _request_tenors(request) -> list:
    return list(getattr(request, "tenors", None) or [])


def has_tenor_surface(request) -> bool:
    return bool(_request_tenors(request))


def _pillars_from_request(request) -> list[_TenorPillar]:
    pillars: list[_TenorPillar] = []
    seen: set[str] = set()
    for slice_ in _request_tenors(request):
        tenor = slice_.tenor.value if hasattr(slice_.tenor, "value") else str(slice_.tenor)
        if tenor in seen:
            raise ValueError(f"Duplicate tenor {tenor}")
        seen.add(tenor)
        t = tenor_year_fraction(tenor, getattr(slice_, "expiry_years", None))
        swap = slice_.swap_points
        points_bid = [(p.strike, p.bid) for p in slice_.vols]
        points_offer = [(p.strike, p.offer) for p in slice_.vols]
        if len({round(k, 8) for k, _ in points_bid}) < 2:
            raise ValueError(f"{tenor} needs at least two strike/vol points")
        pillars.append(
            _TenorPillar(
                tenor=tenor,
                t=t,
                swap_bid=float(swap.bid),
                swap_offer=float(swap.offer),
                points_bid=points_bid,
                points_offer=points_offer,
            )
        )
    pillars.sort(key=lambda item: item.t)
    if len(pillars) < 1:
        raise ValueError("Tenor surface is empty")
    return pillars


def _spot_rate(request, side: str) -> tuple[float, float]:
    spot = two_sided(
        getattr(request, "spot_bid", None),
        getattr(request, "spot_offer", None),
        request.spot,
        side,
    )
    rate = two_sided(
        getattr(request, "rate_bid", None),
        getattr(request, "rate_offer", None),
        request.rate,
        side,
    )
    return spot, rate


def _swap_at(pillars: list[_TenorPillar], t: float, side: str) -> float:
    times = np.array([p.t for p in pillars], dtype=float)
    values = np.array(
        [p.swap_bid if side == "bid" else p.swap_offer if side == "offer" else 0.5 * (p.swap_bid + p.swap_offer) for p in pillars],
        dtype=float,
    )
    return interpolate_level(times, values, t)


def _points_for_side(pillar: _TenorPillar, side: str) -> list[tuple[float, float]]:
    if side == "bid":
        return pillar.points_bid
    if side == "offer":
        return pillar.points_offer
    merged: dict[float, tuple[float, float]] = {}
    for strike, vol in pillar.points_bid:
        merged[round(strike, 8)] = (strike, vol)
    for strike, vol in pillar.points_offer:
        key = round(strike, 8)
        if key in merged:
            merged[key] = (merged[key][0], 0.5 * (merged[key][1] + vol))
        else:
            merged[key] = (strike, vol)
    return list(merged.values())


def _smile_for_pillar(pillar: _TenorPillar, spot: float, rate: float, scale: float, side: str) -> VolSmile:
    swap = pillar.swap_bid if side == "bid" else pillar.swap_offer if side == "offer" else 0.5 * (
        pillar.swap_bid + pillar.swap_offer
    )
    forward = forward_from_swap(spot, swap, scale)
    dividend = implied_dividend(spot, forward, rate, pillar.t)
    return build_smile_from_points(spot, rate, dividend, pillar.t, _points_for_side(pillar, side))


def market_from_request(request, t: float, side: str = "mid") -> MarketSide:
    """Build spot / carry / smile for one bid, mid or offer side."""
    t = max(float(t), 1.0 / 365.0)
    scale = float(getattr(request, "swap_point_scale", 1.0) or 1.0)
    spot, rate = _spot_rate(request, side)
    if not has_tenor_surface(request):
        from option_pricer.pricing.smile import smile_from_request

        smile = smile_from_request(request, t)
        dividend = two_sided(
            getattr(request, "dividend_bid", None),
            getattr(request, "dividend_offer", None),
            request.dividend,
            side,
        )
        forward = float(spot * math.exp((rate - dividend) * t))
        return MarketSide(
            spot=spot,
            rate=rate,
            dividend=dividend,
            forward=forward,
            swap_points=(forward - spot) * scale,
            smile=smile,
            side=side,
        )

    pillars = _pillars_from_request(request)
    swap = _swap_at(pillars, t, side)
    forward = forward_from_swap(spot, swap, scale)
    dividend = implied_dividend(spot, forward, rate, t)
    times = np.array([p.t for p in pillars], dtype=float)
    smiles = [_smile_for_pillar(p, spot, rate, scale, side) for p in pillars]
    strikes: dict[float, float] = {}
    for smile in smiles:
        for strike, _vol in smile.input_nodes:
            strikes[round(strike, 8)] = float(strike)
    if len(strikes) < 2:
        raise ValueError("Tenor surface needs at least two distinct strikes")
    points = []
    for strike in sorted(strikes.values()):
        vols = np.array([smile.vol_at(strike) for smile in smiles], dtype=float)
        points.append((strike, interpolate_vol(times, vols, t)))
    smile = build_smile_from_points(spot, rate, dividend, t, points)
    return MarketSide(
        spot=spot,
        rate=rate,
        dividend=dividend,
        forward=forward,
        swap_points=swap,
        smile=smile,
        side=side,
    )
