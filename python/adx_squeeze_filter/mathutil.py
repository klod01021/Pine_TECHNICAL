"""Pine-matching moving averages and regressions.

These helpers reproduce TradingView Pine Script v6 ``ta.*`` behaviour so the
Python indicator can be compared bar-for-bar with ``pine/adx_squeeze_filter.pine``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, length: int) -> pd.Series:
    """Simple moving average matching ``ta.sma`` (NaN if the window is short)."""
    return series.rolling(length, min_periods=length).mean()


def stdev(series: pd.Series, length: int) -> pd.Series:
    """Population standard deviation matching ``ta.stdev`` (biased, ddof=0)."""
    return series.rolling(length, min_periods=length).std(ddof=0)


def rma(series: pd.Series, length: int) -> pd.Series:
    """Wilder moving average matching ``ta.rma``.

    Pine seeds the smoother with SMA(length) and then recursively applies
    ``(x + (length - 1) * prev) / length``. pandas ``ewm`` seeds from the
    first value instead, so it would not match TradingView.
    """
    values = series.to_numpy(dtype=float)
    n = len(values)
    out = np.full(n, np.nan)
    seed = sma(series, length).to_numpy(dtype=float)
    prev = np.nan
    for i in range(n):
        if np.isnan(prev):
            out[i] = seed[i]
            if not np.isnan(seed[i]):
                prev = seed[i]
        else:
            x = values[i]
            if np.isnan(x):
                out[i] = np.nan
                prev = np.nan
            else:
                out[i] = (x + (length - 1) * prev) / length
                prev = out[i]
    return pd.Series(out, index=series.index)


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """True range matching ``ta.tr(true)``: first bar is ``high - low``."""
    prev_close = close.shift(1)
    hl = high - low
    hc = (high - prev_close).abs()
    lc = (low - prev_close).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.where(prev_close.notna(), hl)


def highest(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).max()


def lowest(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).min()


def linreg(series: pd.Series, length: int, offset: int = 0) -> pd.Series:
    """Least-squares value matching ``ta.linreg(source, length, offset)``.

    Fits ``y ~ intercept + slope * x`` on the last ``length`` bars with
    ``x = 0 .. length-1`` (oldest to newest) and returns the fitted value at
    ``x = length - 1 - offset``.
    """
    values = series.to_numpy(dtype=float)
    n_bars = len(values)
    x = np.arange(length, dtype=float)
    sum_x = x.sum()
    sum_x2 = float(np.dot(x, x))
    denom = length * sum_x2 - sum_x * sum_x
    out = np.full(n_bars, np.nan)
    if denom == 0.0:
        return pd.Series(out, index=series.index)

    for i in range(length - 1, n_bars):
        window = values[i - length + 1 : i + 1]
        if np.isnan(window).any():
            continue
        sum_y = float(window.sum())
        sum_xy = float(np.dot(x, window))
        slope = (length * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / length
        out[i] = intercept + slope * (length - 1 - offset)
    return pd.Series(out, index=series.index)
