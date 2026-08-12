"""TD Moving Average I and II."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import validate_ohlc


def _sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length).mean()


def td_moving_average(
    df: pd.DataFrame,
    fast_length: int = 5,
    slow_length: int = 13,
    confirm_bars: int = 1,
) -> pd.DataFrame:
    """TD Moving Average I and II.

    TD MA I ("short") is an SMA of the close used with a confirmation
    rule: a bullish signal needs ``confirm_bars`` consecutive closes above
    it, bearish needs consecutive closes below. TD MA II ("long") is the
    slower SMA; the pair also generates a cross signal when the fast
    average crosses the slow one, which DeMark uses to classify the
    prevailing trend regime.

    Output: ``td_ma_1``, ``td_ma_2``, ``bullish``, ``bearish``,
    ``trend_up`` (fast above slow).
    """
    validate_ohlc(df)
    close = df["close"]

    ma1 = _sma(close, fast_length)
    ma2 = _sma(close, slow_length)

    above = (close > ma1).astype(int)
    below = (close < ma1).astype(int)
    bullish = above.rolling(confirm_bars).sum() >= confirm_bars
    bearish = below.rolling(confirm_bars).sum() >= confirm_bars

    return pd.DataFrame(
        {
            "td_ma_1": ma1,
            "td_ma_2": ma2,
            "bullish": bullish.fillna(False).astype(bool),
            "bearish": bearish.fillna(False).astype(bool),
            "trend_up": (ma1 > ma2).fillna(False).astype(bool),
        },
        index=df.index,
    )
