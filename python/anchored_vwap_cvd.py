"""Anchored VWAP + Cumulative Volume Delta.

Formulas are documented so the Pine Script port can stay 1:1 with this module.

Anchored VWAP
-------------
    src     = HLC3 | OHLC4 | HL2 | close
    pv      = src * volume
    pv2     = src * src * volume
    cum_pv  = sum(pv  from the current anchor)
    cum_v   = sum(volume from the current anchor)
    cum_pv2 = sum(pv2 from the current anchor)
    vwap    = cum_pv / cum_v
    var     = max(cum_pv2 / cum_v - vwap^2, 0)
    stdev   = sqrt(var)
    bands   = vwap ± k * stdev

CVD (bar-level approximation; TradingView has no tick tape)
----------------------------------------------------------
    CLV (default):  delta = volume * (2*close - high - low) / (high - low)
                    If high == low, fall back to close vs previous close.
    close_open:     delta = sign(close - open) * volume
    close_close:    delta = sign(close - close[1]) * volume
    cvd             = sum(delta from the current anchor)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Sequence

import numpy as np
import pandas as pd

AnchorMode = Literal["session", "week", "month", "year", "timestamp", "rolling"]
DeltaMethod = Literal["clv", "close_open", "close_close"]
PriceSource = Literal["hlc3", "ohlc4", "hl2", "close"]

_OHLCV = ("open", "high", "low", "close", "volume")


@dataclass
class VwapCvdConfig:
    """Inputs shared by the Python engine and the Pine port."""

    anchor: AnchorMode = "session"
    price_source: PriceSource = "hlc3"
    delta_method: DeltaMethod = "clv"
    stdev_mults: Sequence[float] = field(default_factory=lambda: (1.0, 2.0))
    rolling_length: int = 50
    anchor_timestamp: pd.Timestamp | None = None
    session_tz: str | None = None
    cvd_ema: int = 1
    pivot_left: int = 3
    pivot_right: int = 3
    detect_divergence: bool = True


def compute_anchored_vwap_cvd(
    ohlcv: pd.DataFrame,
    config: VwapCvdConfig | None = None,
    **overrides,
) -> pd.DataFrame:
    """Return VWAP, bands, delta, CVD, and optional divergence flags.

    ``ohlcv`` must contain open/high/low/close/volume (any case) and a
    DatetimeIndex when using calendar anchors.
    """
    cfg = config or VwapCvdConfig()
    if overrides:
        cfg = VwapCvdConfig(**{**cfg.__dict__, **overrides})

    df = _normalize_ohlcv(ohlcv)
    src = _source_price(df, cfg.price_source)
    vol = df["volume"].to_numpy(dtype=np.float64)
    src_np = src.to_numpy(dtype=np.float64)

    delta = _bar_delta(df, cfg.delta_method)
    cum_pv, cum_v, cum_pv2, cum_delta, new_anchor = _accumulate(df, src_np, vol, delta, cfg)

    with np.errstate(invalid="ignore", divide="ignore"):
        vwap = np.where(cum_v > 0.0, cum_pv / cum_v, np.nan)
        variance = np.where(cum_v > 0.0, cum_pv2 / cum_v - vwap * vwap, np.nan)
    variance = np.maximum(variance, 0.0)
    stdev = np.sqrt(variance)

    out = pd.DataFrame(index=df.index)
    out["open"] = df["open"]
    out["high"] = df["high"]
    out["low"] = df["low"]
    out["close"] = df["close"]
    out["volume"] = df["volume"]
    out["src"] = src_np
    out["new_anchor"] = new_anchor
    out["vwap"] = vwap
    out["stdev"] = stdev
    for k in cfg.stdev_mults:
        label = _band_label(k)
        out[f"vwap_upper_{label}"] = vwap + k * stdev
        out[f"vwap_lower_{label}"] = vwap - k * stdev
    out["delta"] = delta
    out["cvd"] = cum_delta
    out["cvd_smooth"] = _ema(cum_delta, cfg.cvd_ema)
    out["dist_vwap_pct"] = np.where(
        vwap != 0.0, (df["close"].to_numpy(dtype=np.float64) - vwap) / vwap * 100.0, np.nan
    )
    close_np = df["close"].to_numpy(dtype=np.float64)
    price_bias = np.sign(close_np - vwap)
    cvd_bias = np.sign(out["cvd_smooth"].to_numpy(dtype=np.float64))
    out["price_bias"] = price_bias
    out["cvd_bias"] = cvd_bias
    out["confluence"] = (price_bias == cvd_bias) & (price_bias != 0.0)

    if cfg.detect_divergence:
        div = _divergences(
            high=df["high"].to_numpy(dtype=np.float64),
            low=df["low"].to_numpy(dtype=np.float64),
            cvd=out["cvd_smooth"].to_numpy(dtype=np.float64),
            left=cfg.pivot_left,
            right=cfg.pivot_right,
        )
        for col, arr in div.items():
            out[col] = arr
    else:
        for col in ("bull_div", "bear_div", "hidden_bull_div", "hidden_bear_div"):
            out[col] = False

    return out


def generate_synthetic_ohlcv(
    n_sessions: int = 8,
    bars_per_session: int = 78,
    start: str = "2024-06-03 09:30",
    freq: str = "5min",
    seed: int = 7,
    start_price: float = 100.0,
) -> pd.DataFrame:
    """Build RTH-style OHLCV so session-anchored math can be inspected."""
    rng = np.random.default_rng(seed)
    start_ts = pd.Timestamp(start)
    index: list[pd.Timestamp] = []
    day = start_ts.normalize()
    while len(index) < n_sessions * bars_per_session:
        if day.weekday() < 5:
            session = pd.date_range(day + pd.Timedelta(hours=9, minutes=30), periods=bars_per_session, freq=freq)
            index.extend(session)
        day += pd.Timedelta(days=1)
    index = pd.DatetimeIndex(index[: n_sessions * bars_per_session], name="time")

    # Drift + mean-reverting noise, with a late-session flush that CVD will not confirm.
    n = len(index)
    session_ids = np.arange(n) // bars_per_session
    drift = np.where(session_ids % 3 == 0, 0.0004, np.where(session_ids % 3 == 1, -0.00025, 0.0001))
    shock = rng.normal(0.0, 0.0018, n)
    # Absorption-style flush into the last session: price dumps, buy volume steps in.
    last = session_ids == session_ids.max()
    shock[last] -= np.linspace(0.0, 0.004, last.sum())

    log_ret = drift + shock
    close = start_price * np.exp(np.cumsum(log_ret))
    open_ = np.concatenate([[start_price], close[:-1]])
    spread = np.abs(rng.normal(0.08, 0.04, n)) * close / 100.0
    high = np.maximum(open_, close) + spread * rng.uniform(0.2, 1.1, n)
    low = np.minimum(open_, close) - spread * rng.uniform(0.2, 1.1, n)
    body = np.abs(close - open_)
    volume = rng.lognormal(mean=9.2, sigma=0.35, size=n) * (1.0 + 8.0 * body / np.maximum(high - low, 1e-8))
    volume[last] *= 1.35

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        raise ValueError("ohlcv is empty")
    lower = {c.lower(): c for c in df.columns}
    missing = [c for c in _OHLCV if c not in lower]
    if missing:
        raise ValueError(f"ohlcv missing columns: {missing}")
    out = pd.DataFrame({c: pd.to_numeric(df[lower[c]], errors="coerce") for c in _OHLCV}, index=df.index)
    if out[list(_OHLCV)].isna().any().any():
        raise ValueError("ohlcv contains non-numeric or NaN values")
    if (out["volume"] < 0).any():
        raise ValueError("volume cannot be negative")
    if (out["high"] < out["low"]).any():
        raise ValueError("high cannot be below low")
    return out


def _source_price(df: pd.DataFrame, source: PriceSource) -> pd.Series:
    if source == "hlc3":
        return (df["high"] + df["low"] + df["close"]) / 3.0
    if source == "ohlc4":
        return (df["open"] + df["high"] + df["low"] + df["close"]) / 4.0
    if source == "hl2":
        return (df["high"] + df["low"]) / 2.0
    if source == "close":
        return df["close"].astype(float)
    raise ValueError(f"unknown price source: {source}")


def _bar_delta(df: pd.DataFrame, method: DeltaMethod) -> np.ndarray:
    high = df["high"].to_numpy(dtype=np.float64)
    low = df["low"].to_numpy(dtype=np.float64)
    close = df["close"].to_numpy(dtype=np.float64)
    open_ = df["open"].to_numpy(dtype=np.float64)
    vol = df["volume"].to_numpy(dtype=np.float64)
    bar_range = high - low

    if method == "clv":
        with np.errstate(invalid="ignore", divide="ignore"):
            clv = np.where(bar_range > 0.0, (2.0 * close - high - low) / bar_range, np.nan)
        prev = np.concatenate([[open_[0]], close[:-1]])
        fallback = np.sign(close - prev)
        clv = np.where(np.isnan(clv), fallback, clv)
        return vol * clv
    if method == "close_open":
        return vol * np.sign(close - open_)
    if method == "close_close":
        prev = np.concatenate([[open_[0]], close[:-1]])
        return vol * np.sign(close - prev)
    raise ValueError(f"unknown delta method: {method}")


def _accumulate(
    df: pd.DataFrame,
    src: np.ndarray,
    vol: np.ndarray,
    delta: np.ndarray,
    cfg: VwapCvdConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    pv = src * vol
    pv2 = src * src * vol
    n = len(df)

    if cfg.anchor == "rolling":
        length = max(int(cfg.rolling_length), 1)
        s_pv = pd.Series(pv)
        s_vol = pd.Series(vol)
        s_pv2 = pd.Series(pv2)
        s_delta = pd.Series(delta)
        cum_pv = s_pv.rolling(length, min_periods=1).sum().to_numpy()
        cum_v = s_vol.rolling(length, min_periods=1).sum().to_numpy()
        cum_pv2 = s_pv2.rolling(length, min_periods=1).sum().to_numpy()
        cum_delta = s_delta.rolling(length, min_periods=1).sum().to_numpy()
        new_anchor = np.zeros(n, dtype=bool)
        new_anchor[0] = True
        return cum_pv, cum_v, cum_pv2, cum_delta, new_anchor

    ids, valid = _anchor_ids(df.index, cfg)
    new_anchor = np.empty(n, dtype=bool)
    new_anchor[0] = True
    new_anchor[1:] = ids[1:] != ids[:-1]

    def _group_cumsum(values: np.ndarray) -> np.ndarray:
        series = pd.Series(np.where(valid, values, 0.0), index=df.index)
        out = series.groupby(ids, sort=False).cumsum().to_numpy()
        return np.where(valid, out, np.nan)

    return (
        _group_cumsum(pv),
        _group_cumsum(vol),
        _group_cumsum(pv2),
        _group_cumsum(delta),
        new_anchor & valid,
    )


def _anchor_ids(index: pd.Index, cfg: VwapCvdConfig) -> tuple[np.ndarray, np.ndarray]:
    n = len(index)
    valid = np.ones(n, dtype=bool)

    if cfg.anchor == "timestamp":
        if cfg.anchor_timestamp is None:
            raise ValueError("anchor_timestamp is required when anchor='timestamp'")
        ts = pd.Timestamp(cfg.anchor_timestamp)
        if isinstance(index, pd.DatetimeIndex):
            if index.tz is not None and ts.tzinfo is None:
                ts = ts.tz_localize(index.tz)
            elif index.tz is None and ts.tzinfo is not None:
                ts = ts.tz_localize(None)
        valid = index >= ts
        ids = np.where(valid, 1, 0)
        return ids, valid

    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError(f"anchor={cfg.anchor!r} requires a DatetimeIndex")

    idx = index
    if cfg.session_tz:
        if idx.tz is None:
            idx = idx.tz_localize(cfg.session_tz)
        else:
            idx = idx.tz_convert(cfg.session_tz)

    if cfg.anchor == "session":
        ids = np.asarray(idx.strftime("%Y-%m-%d"))
    elif cfg.anchor == "week":
        ids = np.asarray(idx.to_period("W-SUN").astype(str))
    elif cfg.anchor == "month":
        ids = np.asarray(idx.to_period("M").astype(str))
    elif cfg.anchor == "year":
        ids = np.asarray(idx.year)
    else:
        raise ValueError(f"unknown anchor: {cfg.anchor}")
    return ids, valid


def _ema(values: np.ndarray, length: int) -> np.ndarray:
    if length <= 1:
        return values.copy()
    # span=length => alpha = 2/(length+1), same coefficient as Pine ta.ema.
    # Seed is the first observation (pandas), whereas ta.ema seeds with an SMA;
    # they converge quickly. Use length=1 for an exact match.
    return pd.Series(values).ewm(span=length, adjust=False, min_periods=1).mean().to_numpy()


def _band_label(k: float) -> str:
    if float(k).is_integer():
        return str(int(k))
    return str(k).replace(".", "p")


def _divergences(
    high: np.ndarray,
    low: np.ndarray,
    cvd: np.ndarray,
    left: int,
    right: int,
) -> dict[str, np.ndarray]:
    """Pivot divergences, flagged on the confirmation bar (matches ta.pivot*)."""
    n = len(high)
    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    hid_bull = np.zeros(n, dtype=bool)
    hid_bear = np.zeros(n, dtype=bool)

    price_highs: list[tuple[int, float]] = []
    price_lows: list[tuple[int, float]] = []
    cvd_highs: list[tuple[int, float]] = []
    cvd_lows: list[tuple[int, float]] = []

    ph = _pivot_high(high, left, right)
    pl = _pivot_low(low, left, right)

    for i in range(n):
        pivot_i = i - right
        if ph[i] and pivot_i >= 0:
            price_highs.append((pivot_i, high[pivot_i]))
            cvd_highs.append((pivot_i, cvd[pivot_i]))
            if len(price_highs) >= 2:
                _, p1 = price_highs[-2]
                _, p2 = price_highs[-1]
                _, c1 = cvd_highs[-2]
                _, c2 = cvd_highs[-1]
                if p2 > p1 and c2 < c1:
                    bear[i] = True
                elif p2 < p1 and c2 > c1:
                    hid_bear[i] = True
        if pl[i] and pivot_i >= 0:
            price_lows.append((pivot_i, low[pivot_i]))
            cvd_lows.append((pivot_i, cvd[pivot_i]))
            if len(price_lows) >= 2:
                _, p1 = price_lows[-2]
                _, p2 = price_lows[-1]
                _, c1 = cvd_lows[-2]
                _, c2 = cvd_lows[-1]
                if p2 < p1 and c2 > c1:
                    bull[i] = True
                elif p2 > p1 and c2 < c1:
                    hid_bull[i] = True

    return {
        "bull_div": bull,
        "bear_div": bear,
        "hidden_bull_div": hid_bull,
        "hidden_bear_div": hid_bear,
    }


def _pivot_high(values: np.ndarray, left: int, right: int) -> np.ndarray:
    return _is_pivot(values, left, right, mode="high")


def _pivot_low(values: np.ndarray, left: int, right: int) -> np.ndarray:
    return _is_pivot(values, left, right, mode="low")


def _is_pivot(values: np.ndarray, left: int, right: int, mode: str) -> np.ndarray:
    n = len(values)
    flags = np.zeros(n, dtype=bool)
    if left < 1 or right < 1 or n < left + right + 1:
        return flags
    for confirm in range(left + right, n):
        i = confirm - right
        window = values[i - left : i + right + 1]
        if np.isnan(values[i]) or np.isnan(window).any():
            continue
        left_vals = values[i - left : i]
        right_vals = values[i + 1 : i + right + 1]
        # Strict vs both sides — same rule as Pine ta.pivothigh / ta.pivotlow.
        if mode == "high":
            flags[confirm] = (values[i] > left_vals).all() and (values[i] > right_vals).all()
        else:
            flags[confirm] = (values[i] < left_vals).all() and (values[i] < right_vals).all()
    return flags
