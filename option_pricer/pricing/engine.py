"""Dispatch pricing across Black-Scholes, PDE and Monte Carlo."""

from __future__ import annotations

from option_pricer.pricing.black_scholes import price_black_scholes, vollib_implied_vol
from option_pricer.pricing.monte_carlo import price_monte_carlo
from option_pricer.pricing.pde import price_pde
from option_pricer.pricing.ql_market import year_fraction
from option_pricer.pricing.schemas import (
    Greeks,
    ModelName,
    ModelQuote,
    PriceRequest,
    PriceResponse,
)
from option_pricer.pricing.smile import build_smile

MODEL_LABELS = {
    ModelName.black_scholes: "Black-Scholes",
    ModelName.pde: "PDE (finite difference)",
    ModelName.monte_carlo: "Monte Carlo",
}


def price_option(request: PriceRequest) -> PriceResponse:
    days, t = year_fraction(request.expiry_years)
    smile = build_smile(
        spot=request.spot,
        rate=request.rate,
        dividend=request.dividend,
        t=t,
        atm_vol=request.atm_vol,
        rr_25d=request.rr_25d,
        bf_25d=request.bf_25d,
    )
    vol = smile.vol_at(request.strike)
    warnings = list(smile.warnings)
    is_call = request.option_type.value == "call"
    style = request.option_style.value
    barrier_kind = request.barrier_type.value if request.barrier_type else None

    if style == "american" and request.dividend == 0 and is_call:
        warnings.append(
            "With zero dividends an American call matches a European call; early exercise is not optimal."
        )
    if style == "barrier":
        warnings.append(
            "Black-Scholes uses a continuous barrier; Monte Carlo monitors the barrier on a discrete grid."
        )

    primary = _run_model(
        request.model,
        days=days,
        t=t,
        request=request,
        vol=vol,
        is_call=is_call,
        style=style,
        barrier_kind=barrier_kind,
    )

    comparison: list[ModelQuote] = []
    if request.compare_models:
        for model in ModelName:
            if model == request.model:
                comparison.append(
                    ModelQuote(
                        model=model,
                        label=MODEL_LABELS[model],
                        price=primary["price"],
                        std_error=primary.get("std_error"),
                        greeks=primary["greeks"],
                    )
                )
                continue
            try:
                other = _run_model(
                    model,
                    days=days,
                    t=t,
                    request=request,
                    vol=vol,
                    is_call=is_call,
                    style=style,
                    barrier_kind=barrier_kind,
                    with_greeks=False,
                )
                comparison.append(
                    ModelQuote(
                        model=model,
                        label=MODEL_LABELS[model],
                        price=other["price"],
                        std_error=other.get("std_error"),
                        greeks=other["greeks"],
                    )
                )
            except Exception as exc:
                comparison.append(
                    ModelQuote(
                        model=model,
                        label=MODEL_LABELS[model],
                        price=float("nan"),
                        error=str(exc),
                    )
                )

    implied = None
    if style == "european":
        implied = vollib_implied_vol(
            primary["price"],
            request.spot,
            request.strike,
            t,
            request.rate,
            request.dividend,
            is_call,
        )

    payoff = _payoff_curve(request, vol, t, is_call, style, barrier_kind)

    details = {
        "day_count": "Actual/365",
        "time_years": t,
        "days": days,
        "engine": primary.get("engine"),
        "vol_25d_put": smile.vol_25d_put,
        "vol_25d_call": smile.vol_25d_call,
        "strike_vol": vol,
        "paths": primary.get("paths"),
        "steps": primary.get("steps"),
        "vollib_price": primary.get("vollib_price"),
    }

    return PriceResponse(
        price=primary["price"],
        std_error=primary.get("std_error"),
        greeks=primary["greeks"],
        vol_used=vol,
        implied_vol=implied,
        smile=smile.curve(),
        model=request.model,
        model_label=MODEL_LABELS[request.model],
        comparison=comparison,
        warnings=warnings,
        details=details,
        payoff=payoff,
    )


def _run_model(
    model: ModelName,
    *,
    days: int,
    t: float,
    request: PriceRequest,
    vol: float,
    is_call: bool,
    style: str,
    barrier_kind: str | None,
    with_greeks: bool = True,
) -> dict:
    common = dict(
        spot=request.spot,
        strike=request.strike,
        rate=request.rate,
        dividend=request.dividend,
        vol=vol,
        is_call=is_call,
        style=style,
        barrier_kind=barrier_kind,
        barrier=request.barrier,
        rebate=request.rebate,
    )
    if model is ModelName.black_scholes:
        result = price_black_scholes(days=days, t=t, **common)
    elif model is ModelName.pde:
        result = price_pde(
            days=days,
            time_steps=request.pde_time_steps,
            spot_steps=request.pde_spot_steps,
            **common,
        )
    else:
        result = price_monte_carlo(
            t=t,
            paths=request.mc_paths,
            steps=request.mc_steps,
            seed=request.seed,
            with_greeks=with_greeks,
            **common,
        )
    result.setdefault("greeks", Greeks())
    return result


def _payoff_curve(request: PriceRequest, vol, t, is_call, style, barrier_kind) -> dict:
    import numpy as np

    from option_pricer.pricing.black_scholes import vollib_price

    spot = request.spot
    strike = request.strike
    spots = np.linspace(spot * 0.6, spot * 1.4, 80)
    intrinsic = []
    theoretical = []
    for s in spots:
        if is_call:
            payoff = max(s - strike, 0.0)
        else:
            payoff = max(strike - s, 0.0)
        if style == "barrier" and request.barrier is not None:
            hit_up = barrier_kind.startswith("up") and s >= request.barrier
            hit_dn = barrier_kind.startswith("down") and s <= request.barrier
            hit = hit_up or hit_dn
            if barrier_kind.endswith("out") and hit:
                payoff = request.rebate
            if barrier_kind.endswith("in") and not hit:
                # At expiry, a knock-in that never hit is worthless (spot path unknown).
                # Chart shows vanilla intrinsic only; keep terminal KI as vanilla.
                pass
        intrinsic.append(float(payoff))
        try:
            theoretical.append(
                float(
                    vollib_price(
                        is_call,
                        float(s),
                        strike,
                        t,
                        request.rate,
                        vol,
                        request.dividend,
                    )
                )
            )
        except Exception:
            theoretical.append(None)
    return {
        "spots": spots.tolist(),
        "intrinsic": intrinsic,
        "black_scholes": theoretical,
        "barrier": request.barrier,
    }
