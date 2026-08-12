"""TD Range Projection: next-bar projected high and low."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import validate_ohlc


def td_range_projection(df: pd.DataFrame) -> pd.DataFrame:
    """TD Range Projection.

    Projects the next bar's high and low from the current bar's
    character, using the current open and the bar's close position:

    * Close > open (up bar):    projected high = 2*high - low;
                                projected low  = high - (2*(high - low))
    * Close < open (down bar):  projected high = low + 2*(high - low)... 

    In DeMark's formulation the projections are:

    * ``proj_high`` = 2 * high - low   if close >= open else 2 * high - close
    * ``proj_low``  = 2 * low - high   if close >= open else 2 * low - close

    with the alternative pair (based on the open) used when the bar
    closes unchanged. Output: ``projected_high``, ``projected_low``.
    """
    validate_ohlc(df)
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)

    up_bar = c >= o
    proj_high = np.where(up_bar, 2.0 * h - l, 2.0 * h - c)
    proj_low = np.where(up_bar, 2.0 * l - h, 2.0 * l - c)

    return pd.DataFrame(
        {"projected_high": proj_high, "projected_low": proj_low}, index=df.index
    )
