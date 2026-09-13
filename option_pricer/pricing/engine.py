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
from option_pricer.pricing.surface import build_surface
from option_pricer.pricing.term_surface import MarketSide, has_tenor_surface, market_from_request

MODEL_LABELS = {
    ModelName.black_scholes: "Black-Scholes",
    ModelName.pde: "PDE (finite difference)",
    ModelName.monte_carlo: "Monte Carlo",
}


def _markets(request: PriceRequest, t: float) -> tuple[MarketSide, MarketSide, MarketSide]:
    bid = market_from_request(request, t, "bid")
    offer = market_from_request(request, t, "offer")
    mid = market_from_request(request, t, "mid")
    return bid, mid, offer


def _same_market(left: MarketSide, right: MarketSide) -> bool:
    return (
        abs(left.spot - right.spot) < 1e-14
        and abs(left.rate - right.rate) < 1e-14
        and abs(left.dividend - right.dividend) < 1e-14
        and abs(left.smile.vol_at(left.smile.strike_atm) - right.smile.vol_at(right.smile.strike_atm))
        < 1e-14
        and left.smile.nodes_vol == right.smile.nodes_vol
        and left.smile.nodes_x == right.smile.nodes_x
    )


def price_option(request: PriceRequest) -> PriceResponse:
    days, t = year_fraction(request.expiry_years)
    bid_mkt, mid_mkt, offer_mkt = _markets(request, t)
    vol = mid_mkt.smile.vol_at(request.strike)
    vol_bid = bid_mkt.smile.vol_at(request.strike)
    vol_offer = offer_mkt.smile.vol_at(request.strike)
    warnings = list(mid_mkt.smile.warnings)
    is_call = request.option_type.value == "call"
    style = request.option_style.value
    barrier_kind = request.barrier_type.value if request.barrier_type else None

    if style == "american" and mid_mkt.dividend == 0 and is_call:
        warnings.append(
            "With zero dividends an American call matches a European call; early exercise is not optimal."
        )
    if style == "barrier":
        warnings.append(
            "Black-Scholes uses a continuous barrier; Monte Carlo monitors the barrier on a discrete grid."
        )
    if has_tenor_surface(request):
        warnings.append(
            "Tenor surface: 1M / 3M / 6M / 1Y vols and swap points. "
            "Other expiries interpolate total variance and swap points. "
            "Forward = spot + swap points / scale. Bid and offer are priced separately."
        )
    elif mid_mkt.smile.source == "custom":
        warnings.append(
            "Custom smile: input strikes are honored exactly; other strikes are "
            "interpolated in log-moneyness with flat wings. "
            "PDE and Monte Carlo use that smile as local vol along the spot path."
        )
    else:
        warnings.append(
            "The vol surface prices every listed strike with its own implied vol. "
            "PDE and Monte Carlo use that smile as local vol along the spot path."
        )

    primary_mid = _run_model(
        request.model,
        days=days,
        t=t,
        market=mid_mkt,
        request=request,
        vol=vol,
        is_call=is_call,
        style=style,
        barrier_kind=barrier_kind,
    )
    if _same_market(bid_mkt, offer_mkt):
        primary_bid = primary_mid
        primary_offer = primary_mid
    else:
        primary_bid = _run_model(
            request.model,
            days=days,
            t=t,
            market=bid_mkt,
            request=request,
            vol=vol_bid,
            is_call=is_call,
            style=style,
            barrier_kind=barrier_kind,
            with_greeks=False,
        )
        primary_offer = _run_model(
            request.model,
            days=days,
            t=t,
            market=offer_mkt,
            request=request,
            vol=vol_offer,
            is_call=is_call,
            style=style,
            barrier_kind=barrier_kind,
            with_greeks=False,
        )

    comparison: list[ModelQuote] = []
    if request.compare_models:
        for model in ModelName:
            try:
                if model == request.model:
                    mid_price = primary_mid["price"]
                    bid_price = primary_bid["price"]
                    offer_price = primary_offer["price"]
                    std_error = primary_mid.get("std_error")
                    greeks = primary_mid["greeks"]
                else:
                    mid_other = _run_model(
                        model,
                        days=days,
                        t=t,
                        market=mid_mkt,
                        request=request,
                        vol=vol,
                        is_call=is_call,
                        style=style,
                        barrier_kind=barrier_kind,
                        with_greeks=False,
                    )
                    if _same_market(bid_mkt, offer_mkt):
                        bid_other = mid_other
                        offer_other = mid_other
                    else:
                        bid_other = _run_model(
                            model,
                            days=days,
                            t=t,
                            market=bid_mkt,
                            request=request,
                            vol=vol_bid,
                            is_call=is_call,
                            style=style,
                            barrier_kind=barrier_kind,
                            with_greeks=False,
                        )
                        offer_other = _run_model(
                            model,
                            days=days,
                            t=t,
                            market=offer_mkt,
                            request=request,
                            vol=vol_offer,
                            is_call=is_call,
                            style=style,
                            barrier_kind=barrier_kind,
                            with_greeks=False,
                        )
                    mid_price = mid_other["price"]
                    bid_price = bid_other["price"]
                    offer_price = offer_other["price"]
                    std_error = mid_other.get("std_error")
                    greeks = mid_other["greeks"]
                comparison.append(
                    ModelQuote(
                        model=model,
                        label=MODEL_LABELS[model],
                        price=mid_price,
                        price_bid=bid_price,
                        price_offer=offer_price,
                        std_error=std_error,
                        greeks=greeks,
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
            primary_mid["price"],
            mid_mkt.spot,
            request.strike,
            t,
            mid_mkt.rate,
            mid_mkt.dividend,
            is_call,
        )

    payoff = _payoff_curve(request, mid_mkt, vol, t, is_call, style, barrier_kind)
    surface = build_surface(
        mid_mkt.smile,
        spot=mid_mkt.spot,
        rate=mid_mkt.rate,
        dividend=mid_mkt.dividend,
        t=t,
        selected_strike=request.strike,
        n=request.surface_points,
        bid_smile=None if _same_market(bid_mkt, offer_mkt) else bid_mkt.smile,
        offer_smile=None if _same_market(bid_mkt, offer_mkt) else offer_mkt.smile,
        bid_spot=bid_mkt.spot,
        offer_spot=offer_mkt.spot,
        bid_rate=bid_mkt.rate,
        offer_rate=offer_mkt.rate,
        bid_dividend=bid_mkt.dividend,
        offer_dividend=offer_mkt.dividend,
    )

    details = {
        "day_count": "Actual/365",
        "time_years": t,
        "days": days,
        "engine": primary_mid.get("engine"),
        "vol_10d_put": mid_mkt.smile.vol_10d_put,
        "vol_25d_put": mid_mkt.smile.vol_25d_put,
        "vol_25d_call": mid_mkt.smile.vol_25d_call,
        "vol_10d_call": mid_mkt.smile.vol_10d_call,
        "ten_delta_source": mid_mkt.smile.ten_delta_source,
        "smile_source": "tenors" if has_tenor_surface(request) else mid_mkt.smile.source,
        "input_points": len(mid_mkt.smile.input_nodes),
        "strike_vol": vol,
        "swap_points": mid_mkt.swap_points,
        "swap_points_bid": bid_mkt.swap_points,
        "swap_points_offer": offer_mkt.swap_points,
        "implied_dividend": mid_mkt.dividend,
        "expiry_date": request.expiry_date.isoformat() if request.expiry_date else None,
        "value_date": request.value_date.isoformat() if request.value_date else None,
        "paths": primary_mid.get("paths"),
        "steps": primary_mid.get("steps"),
        "vollib_price": primary_mid.get("vollib_price"),
    }

    return PriceResponse(
        price=primary_mid["price"],
        price_bid=primary_bid["price"],
        price_offer=primary_offer["price"],
        std_error=primary_mid.get("std_error"),
        greeks=primary_mid["greeks"],
        vol_used=vol,
        vol_bid=vol_bid,
        vol_offer=vol_offer,
        implied_vol=implied,
        forward=mid_mkt.forward,
        forward_bid=bid_mkt.forward,
        forward_offer=offer_mkt.forward,
        smile=mid_mkt.smile.curve(),
        model=request.model,
        model_label=MODEL_LABELS[request.model],
        comparison=comparison,
        warnings=warnings,
        details=details,
        payoff=payoff,
        surface=surface,
    )


def _run_model(
    model: ModelName,
    *,
    days: int,
    t: float,
    market: MarketSide,
    request: PriceRequest,
    vol: float,
    is_call: bool,
    style: str,
    barrier_kind: str | None,
    with_greeks: bool = True,
) -> dict:
    common = dict(
        spot=market.spot,
        strike=request.strike,
        rate=market.rate,
        dividend=market.dividend,
        vol=vol,
        is_call=is_call,
        style=style,
        barrier_kind=barrier_kind,
        barrier=request.barrier,
        rebate=request.rebate,
        smile=market.smile,
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


def _payoff_curve(request: PriceRequest, market: MarketSide, vol, t, is_call, style, barrier_kind) -> dict:
    import numpy as np

    from option_pricer.pricing.black_scholes import vollib_price

    spot = market.spot
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
                        market.rate,
                        vol,
                        market.dividend,
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
