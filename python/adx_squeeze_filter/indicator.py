"""ADX / Squeeze Filter.

Combines Wilder's Average Directional Index with a TTM-style squeeze
(Bollinger Bands inside Keltner Channels) into a single regime filter.

The calculations are written to match the Pine Script v6 port in
``pine/adx_squeeze_filter.pine`` bar-for-bar.

Typical use
-----------
* **Compression** — squeeze is on *and* ADX is below the coil threshold.
  Volatility is coiled and there is no trend. Stand aside, or fade.
* **Fire** — the combined squeeze just released and ADX is turning up.
  Direction comes from squeeze momentum and +DI vs -DI.
* **Expansion** — squeeze is off and ADX is above the trend threshold.
  Trend-following is allowed.

Filter modes (``mode``)
-----------------------
``"both"``
    In squeeze when TTM squeeze is on AND ADX < coil. Strictest, default.
``"either"``
    In squeeze when TTM squeeze is on OR ADX < coil.
``"ttm"``
    Classic Bollinger-inside-Keltner squeeze only.
``"adx"``
    ADX coil only (low ADX treated as the squeeze).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import validate_ohlc
from .mathutil import highest, linreg, lowest, rma, sma, stdev, true_range

VALID_MODES = ("both", "either", "ttm", "adx")

# Integer regime codes (NaN during warmup).
REGIME_COMPRESSION = 1
REGIME_FIRE = 2
REGIME_DEVELOPING = 3
REGIME_EXPANSION = 4


def directional_movement(
    df: pd.DataFrame,
    di_length: int = 14,
    adx_smoothing: int = 14,
) -> pd.DataFrame:
    """Wilder +DI / -DI / ADX matching ``ta.dmi(diLength, adxSmoothing)``."""
    validate_ohlc(df)
    high, low, close = df["high"], df["low"], df["close"]

    up = high.diff()
    down = low.shift(1) - low

    plus_dm = pd.Series(
        np.where((up > down) & (up > 0), up, 0.0),
        index=df.index,
        dtype=float,
    )
    minus_dm = pd.Series(
        np.where((down > up) & (down > 0), down, 0.0),
        index=df.index,
        dtype=float,
    )
    valid = up.notna() & down.notna()
    plus_dm = plus_dm.where(valid)
    minus_dm = minus_dm.where(valid)

    tr = true_range(high, low, close)
    trur = rma(tr, di_length)
    plus_di = 100.0 * rma(plus_dm, di_length) / trur
    minus_di = 100.0 * rma(minus_dm, di_length) / trur
    plus_di = plus_di.replace([np.inf, -np.inf], np.nan).ffill()
    minus_di = minus_di.replace([np.inf, -np.inf], np.nan).ffill()

    di_sum = plus_di + minus_di
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum.mask(di_sum == 0.0, 1.0)
    adx = rma(dx, adx_smoothing)

    return pd.DataFrame(
        {"plus_di": plus_di, "minus_di": minus_di, "adx": adx},
        index=df.index,
    )


def ttm_squeeze(
    df: pd.DataFrame,
    bb_length: int = 20,
    bb_mult: float = 2.0,
    kc_length: int = 20,
    kc_mult: float = 1.5,
    use_true_range: bool = True,
    source: pd.Series | None = None,
) -> pd.DataFrame:
    """TTM squeeze: Bollinger Bands vs Keltner Channels, plus linreg momentum.

    Squeeze is **on** when the entire Bollinger Band sits inside the Keltner
    Channel (volatility compression). Momentum is LazyBear's linear-regression
    of price versus the midpoint of Donchian and SMA.
    """
    validate_ohlc(df)
    src = df["close"] if source is None else source

    bb_basis = sma(src, bb_length)
    bb_dev = bb_mult * stdev(src, bb_length)
    upper_bb = bb_basis + bb_dev
    lower_bb = bb_basis - bb_dev

    kc_basis = sma(src, kc_length)
    bar_range = (
        true_range(df["high"], df["low"], df["close"])
        if use_true_range
        else (df["high"] - df["low"])
    )
    kc_range = sma(bar_range, kc_length)
    upper_kc = kc_basis + kc_range * kc_mult
    lower_kc = kc_basis - kc_range * kc_mult

    squeeze_on = (lower_bb > lower_kc) & (upper_bb < upper_kc)
    squeeze_off = (lower_bb < lower_kc) & (upper_bb > upper_kc)
    no_squeeze = ~squeeze_on & ~squeeze_off

    donchian_mid = (highest(df["high"], kc_length) + lowest(df["low"], kc_length)) / 2.0
    sma_close = sma(df["close"], kc_length)
    mid = (donchian_mid + sma_close) / 2.0
    momentum = linreg(src - mid, kc_length, offset=0)

    return pd.DataFrame(
        {
            "upper_bb": upper_bb,
            "lower_bb": lower_bb,
            "upper_kc": upper_kc,
            "lower_kc": lower_kc,
            "squeeze_on": squeeze_on,
            "squeeze_off": squeeze_off,
            "no_squeeze": no_squeeze,
            "momentum": momentum,
        },
        index=df.index,
    )


def _in_squeeze(
    squeeze_on: pd.Series,
    adx_coil: pd.Series,
    mode: str,
) -> pd.Series:
    if mode == "both":
        return squeeze_on & adx_coil
    if mode == "either":
        return squeeze_on | adx_coil
    if mode == "ttm":
        return squeeze_on
    if mode == "adx":
        return adx_coil
    raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")


def adx_squeeze_filter(
    df: pd.DataFrame,
    *,
    di_length: int = 14,
    adx_smoothing: int = 14,
    adx_coil: float = 20.0,
    adx_trend: float = 25.0,
    bb_length: int = 20,
    bb_mult: float = 2.0,
    kc_length: int = 20,
    kc_mult: float = 1.5,
    use_true_range: bool = True,
    mode: str = "both",
    require_adx_rising: bool = True,
) -> pd.DataFrame:
    """Combined ADX / squeeze regime filter.

    Parameters
    ----------
    di_length, adx_smoothing
        Wilder DI length and ADX smoothing (Pine ``ta.dmi`` defaults: 14, 14).
    adx_coil
        ADX below this is "no trend" / coil (default 20).
    adx_trend
        ADX at or above this is a confirmed trend (default 25).
    bb_length, bb_mult, kc_length, kc_mult, use_true_range
        TTM squeeze parameters (LazyBear / Carter defaults).
    mode
        How TTM squeeze and ADX coil combine. See module docstring.
    require_adx_rising
        Fire signals also require ADX to be higher than the previous bar.

    Returns
    -------
    DataFrame
        One row per input bar. Boolean columns are False during warmup
        rather than NaN so they can be used directly as masks. Numeric
        columns stay NaN until their lookback is filled.
    """
    validate_ohlc(df)
    mode = mode.lower()
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")

    dmi = directional_movement(df, di_length=di_length, adx_smoothing=adx_smoothing)
    sqz = ttm_squeeze(
        df,
        bb_length=bb_length,
        bb_mult=bb_mult,
        kc_length=kc_length,
        kc_mult=kc_mult,
        use_true_range=use_true_range,
    )

    adx = dmi["adx"]
    plus_di = dmi["plus_di"]
    minus_di = dmi["minus_di"]
    ready = adx.notna() & sqz["momentum"].notna()

    adx_is_coil = ready & (adx < adx_coil)
    adx_is_strong = ready & (adx >= adx_trend)
    adx_rising = ready & (adx > adx.shift(1))

    squeeze_on = ready & sqz["squeeze_on"].fillna(False)
    in_squeeze = _in_squeeze(squeeze_on, adx_is_coil, mode) & ready
    squeeze_release = ready & in_squeeze.shift(1, fill_value=False) & ~in_squeeze

    bullish = (plus_di > minus_di) & (sqz["momentum"] > 0)
    bearish = (minus_di > plus_di) & (sqz["momentum"] < 0)
    adx_ok = adx_rising if require_adx_rising else pd.Series(True, index=df.index)

    long_fire = squeeze_release & bullish & adx_ok
    short_fire = squeeze_release & bearish & adx_ok

    allow_long = ready & ~in_squeeze & adx_is_strong & bullish
    allow_short = ready & ~in_squeeze & adx_is_strong & bearish

    regime = pd.Series(np.nan, index=df.index, dtype=float)
    regime = regime.mask(ready & in_squeeze, float(REGIME_COMPRESSION))
    regime = regime.mask(ready & squeeze_release, float(REGIME_FIRE))
    regime = regime.mask(
        ready & ~in_squeeze & ~squeeze_release & adx_is_strong,
        float(REGIME_EXPANSION),
    )
    regime = regime.mask(
        ready & ~in_squeeze & ~squeeze_release & ~adx_is_strong,
        float(REGIME_DEVELOPING),
    )

    out = pd.DataFrame(index=df.index)
    out["plus_di"] = plus_di
    out["minus_di"] = minus_di
    out["adx"] = adx
    out["upper_bb"] = sqz["upper_bb"]
    out["lower_bb"] = sqz["lower_bb"]
    out["upper_kc"] = sqz["upper_kc"]
    out["lower_kc"] = sqz["lower_kc"]
    out["squeeze_on"] = squeeze_on
    out["squeeze_off"] = ready & sqz["squeeze_off"].fillna(False)
    out["no_squeeze"] = ready & sqz["no_squeeze"].fillna(False)
    out["momentum"] = sqz["momentum"]
    out["adx_coil"] = adx_is_coil
    out["adx_strong"] = adx_is_strong
    out["adx_rising"] = adx_rising
    out["in_squeeze"] = in_squeeze
    out["squeeze_release"] = squeeze_release
    out["long_fire"] = long_fire.fillna(False)
    out["short_fire"] = short_fire.fillna(False)
    out["allow_long"] = allow_long.fillna(False)
    out["allow_short"] = allow_short.fillna(False)
    out["regime"] = regime
    return out
