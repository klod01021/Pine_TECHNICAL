"""Shared QuantLib market objects. QuantLib evaluation date is process-global."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass

import QuantLib as ql

_QL_LOCK = threading.Lock()


@contextmanager
def quantlib_session(days: int):
    """Serialize QuantLib access and pin a deterministic evaluation date."""
    days = max(int(days), 1)
    with _QL_LOCK:
        today = ql.Date(1, 1, 2026)
        previous = ql.Settings.instance().evaluationDate
        ql.Settings.instance().evaluationDate = today
        try:
            yield today, today + ql.Period(days, ql.Days)
        finally:
            ql.Settings.instance().evaluationDate = previous


@dataclass
class QlMarket:
    process: ql.BlackScholesMertonProcess
    spot_quote: ql.SimpleQuote
    rate_quote: ql.SimpleQuote
    div_quote: ql.SimpleQuote
    vol_quote: ql.SimpleQuote
    today: ql.Date
    maturity: ql.Date
    day_count: ql.DayCounter


def year_fraction(expiry_years: float) -> tuple[int, float]:
    days = max(1, int(round(float(expiry_years) * 365.0)))
    return days, days / 365.0


def build_market(
    today: ql.Date,
    maturity: ql.Date,
    spot: float,
    rate: float,
    dividend: float,
    vol: float,
) -> QlMarket:
    day_count = ql.Actual365Fixed()
    calendar = ql.NullCalendar()
    spot_quote = ql.SimpleQuote(float(spot))
    rate_quote = ql.SimpleQuote(float(rate))
    div_quote = ql.SimpleQuote(float(dividend))
    vol_quote = ql.SimpleQuote(float(vol))

    rate_ts = ql.YieldTermStructureHandle(
        ql.FlatForward(today, ql.QuoteHandle(rate_quote), day_count)
    )
    div_ts = ql.YieldTermStructureHandle(
        ql.FlatForward(today, ql.QuoteHandle(div_quote), day_count)
    )
    vol_ts = ql.BlackVolTermStructureHandle(
        ql.BlackConstantVol(today, calendar, ql.QuoteHandle(vol_quote), day_count)
    )
    process = ql.BlackScholesMertonProcess(
        ql.QuoteHandle(spot_quote), div_ts, rate_ts, vol_ts
    )
    return QlMarket(
        process=process,
        spot_quote=spot_quote,
        rate_quote=rate_quote,
        div_quote=div_quote,
        vol_quote=vol_quote,
        today=today,
        maturity=maturity,
        day_count=day_count,
    )


def option_type(is_call: bool) -> ql.Option.Type:
    return ql.Option.Call if is_call else ql.Option.Put


def barrier_type(kind: str) -> ql.Barrier.Type:
    mapping = {
        "up_and_out": ql.Barrier.UpOut,
        "up_and_in": ql.Barrier.UpIn,
        "down_and_out": ql.Barrier.DownOut,
        "down_and_in": ql.Barrier.DownIn,
    }
    return mapping[kind]


def read_greeks(instrument) -> dict[str, float | None]:
    def _try(name: str):
        try:
            value = getattr(instrument, name)()
            if value is None:
                return None
            if abs(value) > 1e12:
                return None
            return float(value)
        except Exception:
            return None

    vega = _try("vega")
    theta_day = _try("thetaPerDay")
    if theta_day is None:
        theta_year = _try("theta")
        theta_day = None if theta_year is None else theta_year / 365.0
    rho = _try("rho")
    return {
        "delta": _try("delta"),
        "gamma": _try("gamma"),
        "vega": None if vega is None else vega / 100.0,
        "theta": theta_day,
        "rho": None if rho is None else rho / 100.0,
    }
