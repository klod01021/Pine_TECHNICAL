"""Simplified Monte Carlo: GBM paths, discrete barriers, Longstaff-Schwartz American."""

from __future__ import annotations

import numpy as np

from option_pricer.pricing.schemas import Greeks


def _intrinsic(spots: np.ndarray, strike: float, is_call: bool) -> np.ndarray:
    if is_call:
        return np.maximum(spots - strike, 0.0)
    return np.maximum(strike - spots, 0.0)


def price_monte_carlo(
    *,
    t: float,
    spot: float,
    strike: float,
    rate: float,
    dividend: float,
    vol: float,
    is_call: bool,
    style: str,
    paths: int,
    steps: int,
    seed: int,
    barrier_kind: str | None = None,
    barrier: float | None = None,
    rebate: float = 0.0,
    with_greeks: bool = True,
) -> dict:
    rng = np.random.default_rng(seed)
    price, stderr = _price_once(
        rng,
        t,
        spot,
        strike,
        rate,
        dividend,
        vol,
        is_call,
        style,
        paths,
        steps,
        barrier_kind,
        barrier,
        rebate,
    )
    greeks = (
        _mc_greeks(
            seed,
            t,
            spot,
            strike,
            rate,
            dividend,
            vol,
            is_call,
            style,
            paths,
            steps,
            barrier_kind,
            barrier,
            rebate,
            price,
        )
        if with_greeks
        else Greeks()
    )
    engine = {
        "european": "Simplified Monte Carlo (terminal GBM)",
        "american": "Simplified Monte Carlo (Longstaff-Schwartz)",
        "barrier": "Simplified Monte Carlo (discrete barrier monitoring)",
    }[style]
    return {
        "price": float(price),
        "std_error": float(stderr),
        "greeks": greeks,
        "engine": engine,
        "paths": paths,
        "steps": steps,
    }


def _price_once(
    rng: np.random.Generator,
    t,
    spot,
    strike,
    rate,
    dividend,
    vol,
    is_call,
    style,
    paths,
    steps,
    barrier_kind,
    barrier,
    rebate,
) -> tuple[float, float]:
    if style == "european":
        return _european(rng, t, spot, strike, rate, dividend, vol, is_call, paths)
    if style == "american":
        return _american_lsm(
            rng, t, spot, strike, rate, dividend, vol, is_call, paths, steps
        )
    return _barrier(
        rng,
        t,
        spot,
        strike,
        rate,
        dividend,
        vol,
        is_call,
        paths,
        steps,
        barrier_kind,
        barrier,
        rebate,
    )


def _european(rng, t, spot, strike, rate, dividend, vol, is_call, paths):
    z = rng.standard_normal(paths)
    st = spot * np.exp((rate - dividend - 0.5 * vol * vol) * t + vol * np.sqrt(t) * z)
    payoff = _intrinsic(st, strike, is_call) * np.exp(-rate * t)
    return float(payoff.mean()), float(payoff.std(ddof=1) / np.sqrt(paths))


def _simulate_paths(rng, t, spot, rate, dividend, vol, paths, steps) -> np.ndarray:
    dt = t / steps
    drift = (rate - dividend - 0.5 * vol * vol) * dt
    shock = vol * np.sqrt(dt)
    log_s = np.empty((steps + 1, paths))
    log_s[0] = np.log(spot)
    z = rng.standard_normal((steps, paths))
    for i in range(steps):
        log_s[i + 1] = log_s[i] + drift + shock * z[i]
    return np.exp(log_s)


def _american_lsm(rng, t, spot, strike, rate, dividend, vol, is_call, paths, steps):
    spots = _simulate_paths(rng, t, spot, rate, dividend, vol, paths, steps)
    dt = t / steps
    df = np.exp(-rate * dt)
    cash = _intrinsic(spots[-1], strike, is_call)
    for i in range(steps - 1, 0, -1):
        s = spots[i]
        itm = _intrinsic(s, strike, is_call)
        mask = itm > 0
        continuation = cash * df
        if mask.sum() > 20:
            x = s[mask]
            y = continuation[mask]
            basis = np.column_stack([np.ones_like(x), x, x * x])
            try:
                beta, *_ = np.linalg.lstsq(basis, y, rcond=None)
                fitted = beta[0] + beta[1] * x + beta[2] * x * x
            except np.linalg.LinAlgError:
                fitted = y
            exercise = itm[mask] > fitted
            chosen = np.where(exercise, itm[mask], y)
            continuation[mask] = chosen
        cash = continuation
    cash = cash * df
    # Compare with immediate exercise at t=0
    cash = np.maximum(cash, _intrinsic(np.full(paths, spot), strike, is_call))
    return float(cash.mean()), float(cash.std(ddof=1) / np.sqrt(paths))


def _barrier(
    rng,
    t,
    spot,
    strike,
    rate,
    dividend,
    vol,
    is_call,
    paths,
    steps,
    barrier_kind,
    barrier,
    rebate,
):
    spots = _simulate_paths(rng, t, spot, rate, dividend, vol, paths, steps)
    if barrier_kind.startswith("up"):
        hit = np.any(spots >= barrier, axis=0)
    else:
        hit = np.any(spots <= barrier, axis=0)
    vanilla = _intrinsic(spots[-1], strike, is_call)
    is_out = barrier_kind.endswith("out")
    if is_out:
        payoff = np.where(hit, rebate, vanilla)
    else:
        payoff = np.where(hit, vanilla, rebate)
    discounted = payoff * np.exp(-rate * t)
    return float(discounted.mean()), float(discounted.std(ddof=1) / np.sqrt(paths))


def _mc_greeks(
    seed,
    t,
    spot,
    strike,
    rate,
    dividend,
    vol,
    is_call,
    style,
    paths,
    steps,
    barrier_kind,
    barrier,
    rebate,
    base_price,
) -> Greeks:
    def run(**overrides):
        rng = np.random.default_rng(seed)
        kwargs = dict(
            t=t,
            spot=spot,
            strike=strike,
            rate=rate,
            dividend=dividend,
            vol=vol,
            is_call=is_call,
            style=style,
            paths=paths,
            steps=steps,
            barrier_kind=barrier_kind,
            barrier=barrier,
            rebate=rebate,
        )
        kwargs.update(overrides)
        price, _ = _price_once(rng, **kwargs)
        return price

    ds = max(spot * 1e-3, 1e-6)
    up = run(spot=spot + ds)
    dn = run(spot=spot - ds)
    delta = (up - dn) / (2.0 * ds)
    gamma = (up - 2.0 * base_price + dn) / (ds * ds)

    dv = 0.01
    v_up = run(vol=vol + dv)
    vega = v_up - base_price  # vol bumped by 1 point → trader vega

    dt = min(1.0 / 365.0, t * 0.05)
    if t - dt > 1e-6:
        t_dn = run(t=t - dt)
        theta = (t_dn - base_price) / (dt * 365.0)
    else:
        theta = None

    dr = 0.0001
    r_up = run(rate=rate + dr)
    rho = (r_up - base_price) / dr / 100.0

    return Greeks(delta=delta, gamma=gamma, vega=vega, theta=theta, rho=rho)
