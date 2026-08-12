"""DeMark oscillator family.

All functions accept an OHLC DataFrame and return a DataFrame indexed the
same way, with one column per output series. The calculations mirror the
Pine Script v6 scripts in ``/pine`` bar-for-bar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import validate_ohlc


def _ema(series: pd.Series, length: int) -> pd.Series:
    """Exponential moving average matching ta.ema in Pine (alpha = 2/(n+1))."""
    return series.ewm(alpha=2.0 / (length + 1.0), adjust=False).mean()


def _sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length).mean()


def _rma(series: pd.Series, length: int) -> pd.Series:
    """Wilder-smoothed moving average matching ta.rma in Pine."""
    return series.ewm(alpha=1.0 / length, adjust=False).mean()


# ---------------------------------------------------------------------------
# DeMarker (DeM)
# ---------------------------------------------------------------------------

def demarker(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """DeMarker oscillator (0-100).

    DeMHigh = max(high - high[1], 0); DeMLow = max(low[1] - low, 0).
    DeM = 100 * SMA(DeMHigh, n) / (SMA(DeMHigh, n) + SMA(DeMLow, n)).
    """
    validate_ohlc(df)
    high, low = df["high"], df["low"]

    dem_high = (high - high.shift(1)).clip(lower=0.0)
    dem_low = (low.shift(1) - low).clip(lower=0.0)

    sum_high = _sma(dem_high, length)
    sum_low = _sma(dem_low, length)

    denom = sum_high + sum_low
    dem = np.where(denom == 0.0, 0.0, 100.0 * sum_high / denom)
    return pd.DataFrame({"dem": dem}, index=df.index)


# ---------------------------------------------------------------------------
# DeMarker II
# ---------------------------------------------------------------------------

def demarker_ii(df: pd.DataFrame, length: int = 8) -> pd.DataFrame:
    """DeMarker II oscillator (0-100).

    Uses bar midpoints (high+low)/2 and the close: upside captures the
    distance from close to the bar's upper half, downside the distance
    from the lower half to the close. Default length 8.
    """
    validate_ohlc(df)
    high, low, close = df["high"], df["low"], df["close"]

    midpoint = (high + low) / 2.0
    upside = (high - midpoint).clip(lower=0.0) * (close >= midpoint).astype(float)
    downside = (midpoint - low).clip(lower=0.0) * (close < midpoint).astype(float)

    sum_up = _sma(upside, length)
    sum_down = _sma(downside, length)

    denom = sum_up + sum_down
    dem2 = np.where(denom == 0.0, 0.0, 100.0 * sum_up / denom)
    return pd.DataFrame({"demarker_ii": dem2}, index=df.index)


# ---------------------------------------------------------------------------
# TD Pressure Ratio
# ---------------------------------------------------------------------------

def td_pressure_ratio(df: pd.DataFrame, length: int = 13) -> pd.DataFrame:
    """TD Pressure Ratio (0-100).

    Buying pressure measures how far the close sits above the bar low
    (weighted by true range); selling pressure how far it sits below the
    bar high. Ratio = 100 * sum(buying, n) / sum(buying + selling, n).
    """
    validate_ohlc(df)
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)

    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)

    buying = ((close - low).clip(lower=0.0)) * true_range
    selling = ((high - close).clip(lower=0.0)) * true_range

    sum_buy = _sma(buying, length)
    sum_sell = _sma(selling, length)

    denom = sum_buy + sum_sell
    ratio = np.where(denom == 0.0, 0.0, 100.0 * sum_buy / denom)
    return pd.DataFrame({"pressure_ratio": ratio}, index=df.index)


# ---------------------------------------------------------------------------
# TD Range Expansion Index (TDREI)
# ---------------------------------------------------------------------------

def td_range_expansion_index(df: pd.DataFrame, length: int = 5) -> pd.DataFrame:
    """TD Range Expansion Index (-100 to +100).

    DeMark's published formula. Each bar contributes
    ``(high - high[2]) + (low - low[2])`` only when one of two qualifying
    filters holds; otherwise the bar contributes zero to both the numerator
    and the denominator:

    * Filter A: ``(high >= low[5] or high >= low[6])`` and
      ``(low <= high[5] or low <= high[6])``
    * Filter B: ``(high[2] >= close[7] or high[2] >= close[8])`` and
      ``(low[2] <= close[7] or low[2] <= close[8])``

    ``REI = 100 * sum(value, n) / sum(|dh| + |dl|, n)`` over qualified bars.
    Readings beyond +45 / -45 are the standard overbought / oversold
    thresholds; DeMark treats readings that persist beyond six bars as a
    trending rather than exhausted market.
    """
    validate_ohlc(df)
    high, low, close = df["high"], df["low"], df["close"]

    cond_a = ((high >= low.shift(5)) | (high >= low.shift(6))) & (
        (low <= high.shift(5)) | (low <= high.shift(6))
    )
    cond_b = ((high.shift(2) >= close.shift(7)) | (high.shift(2) >= close.shift(8))) & (
        (low.shift(2) <= close.shift(7)) | (low.shift(2) <= close.shift(8))
    )
    # The filters reference closes 8 bars back, so the indicator is undefined
    # until that much history exists; those bars contribute nothing.
    enough_history = close.shift(8).notna()
    qualified = (cond_a | cond_b) & enough_history

    dh = high - high.shift(2)
    dl = low - low.shift(2)

    value = (dh + dl).where(qualified, 0.0)
    abs_value = (dh.abs() + dl.abs()).where(qualified, 0.0)

    numerator = value.rolling(length).sum()
    denominator = abs_value.rolling(length).sum()

    rei = np.where(
        (denominator == 0.0) | denominator.isna(), 0.0, 100.0 * numerator / denominator
    )
    return pd.DataFrame({"rei": rei}, index=df.index)


# ---------------------------------------------------------------------------
# TD POQ (Price Oscillator Qualifier)
# ---------------------------------------------------------------------------

def td_poq(df: pd.DataFrame, fast: int = 3, slow: int = 8) -> pd.DataFrame:
    """TD Price Oscillator Qualifier.

    Difference of two EMAs expressed as a percentage of the slow EMA.
    Used to qualify TD Line / TDST breakouts: POQ above zero confirms an
    upside breakout, below zero a downside one.
    """
    validate_ohlc(df)
    close = df["close"]

    fast_ema = _ema(close, fast)
    slow_ema = _ema(close, slow)

    poq = np.where(slow_ema == 0.0, 0.0, 100.0 * (fast_ema - slow_ema) / slow_ema)
    return pd.DataFrame({"poq": poq}, index=df.index)


# ---------------------------------------------------------------------------
# TD Alignment Oscillator
# ---------------------------------------------------------------------------

def td_alignment(
    df: pd.DataFrame, fast: int = 5, slow: int = 13, signal: int = 8
) -> pd.DataFrame:
    """TD Alignment Oscillator.

    Percentage spread between a fast and slow SMA of the close, with a
    signal EMA of the spread. Crosses of the spread over its signal line
    mark alignment (agreement) of short- and long-term momentum.
    """
    validate_ohlc(df)
    close = df["close"]

    fast_ma = _sma(close, fast)
    slow_ma = _sma(close, slow)

    spread = np.where(slow_ma == 0.0, 0.0, 100.0 * (fast_ma - slow_ma) / slow_ma)
    spread = pd.Series(spread, index=df.index)
    sig = _ema(spread, signal)

    return pd.DataFrame({"alignment": spread, "signal": sig}, index=df.index)


# ---------------------------------------------------------------------------
# TD Rate of Change
# ---------------------------------------------------------------------------

def td_roc(df: pd.DataFrame, length: int = 5, signal: int = 8) -> pd.DataFrame:
    """TD Rate of Change.

    100 * (close - close[n]) / close[n], with an EMA signal line. DeMark
    watches for divergences between the ROC and price at TD Sequential
    completion zones.
    """
    validate_ohlc(df)
    close = df["close"]
    shifted = close.shift(length)

    roc = np.where(shifted == 0.0, 0.0, 100.0 * (close - shifted) / shifted)
    roc = pd.Series(roc, index=df.index)
    sig = _ema(roc, signal)

    return pd.DataFrame({"roc": roc, "signal": sig}, index=df.index)


# ---------------------------------------------------------------------------
# TD Oscillator
# ---------------------------------------------------------------------------

def td_oscillator(
    df: pd.DataFrame, short: int = 3, long: int = 9
) -> pd.DataFrame:
    """TD Oscillator.

    100 * (SMA(close, short) - SMA(close, long)) / SMA(close, long), the
    generalized DeMark momentum spread. Positive readings mean short-term
    momentum leads long-term; zero-line crosses are the trading signal.
    """
    validate_ohlc(df)
    close = df["close"]

    fast = _sma(close, short)
    slow = _sma(close, long)

    osc = np.where(slow == 0.0, 0.0, 100.0 * (fast - slow) / slow)
    return pd.DataFrame({"td_oscillator": osc}, index=df.index)
