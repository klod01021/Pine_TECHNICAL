"""TD Sequential family: TD Setup, TD Countdown, TD Combo, Ultimate.

These indicators are stateful — a count on bar *i* depends on whether the
sequence survived bars ``0..i-1`` — so the implementations iterate bar by
bar, exactly like the Pine Script v6 versions in ``/pine``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import validate_ohlc


# ---------------------------------------------------------------------------
# TD Setup (1-9)
# ---------------------------------------------------------------------------

def td_setup(df: pd.DataFrame, setup_length: int = 9, compare: int = 4) -> pd.DataFrame:
    """TD Buy/Sell Setup.

    A buy setup counts consecutive bars with close < close[compare];
    a sell setup counts consecutive bars with close > close[compare].
    Reaching ``setup_length`` (9) completes the setup and the count
    restarts. Output columns: ``buy_setup`` and ``sell_setup``.
    """
    validate_ohlc(df)
    close = df["close"].to_numpy(dtype=float)
    n = len(close)

    buy = np.zeros(n, dtype=float)
    sell = np.zeros(n, dtype=float)

    for i in range(n):
        if i < compare:
            buy[i] = np.nan
            sell[i] = np.nan
            continue

        if close[i] < close[i - compare]:
            prev = buy[i - 1]
            buy[i] = (prev + 1) if not np.isnan(prev) else 1
        elif close[i] > close[i - compare]:
            buy[i] = np.nan
        else:
            buy[i] = buy[i - 1]  # unchanged close keeps the count alive

        if close[i] > close[i - compare]:
            prev = sell[i - 1]
            sell[i] = (prev + 1) if not np.isnan(prev) else 1
        elif close[i] < close[i - compare]:
            sell[i] = np.nan
        else:
            sell[i] = sell[i - 1]

    # Completed 9s recycle: once a setup reaches 9 the next qualifying bar
    # starts a fresh count. (The loop above already restarts automatically
    # because a completed buy count is reset when the condition breaks.)
    buy = np.where(buy > setup_length, np.mod(buy - 1, setup_length) + 1, buy)
    sell = np.where(sell > setup_length, np.mod(sell - 1, setup_length) + 1, sell)

    return pd.DataFrame(
        {"buy_setup": pd.Series(buy, index=df.index), "sell_setup": pd.Series(sell, index=df.index)}
    )


# ---------------------------------------------------------------------------
# TD Countdown (classic 1-13)
# ---------------------------------------------------------------------------

def td_countdown(
    df: pd.DataFrame, setup_length: int = 9, countdown_length: int = 13, compare: int = 4
) -> pd.DataFrame:
    """Classic TD Countdown.

    Starts from the bar of a completed TD Setup (9) and counts bars whose
    close <= low[2] (buy) / close >= high[2] (sell). Unlike the setup,
    countdown bars do not need to be consecutive. A countdown completes
    at ``countdown_length`` (13).

    Output columns: ``buy_setup``, ``sell_setup``, ``buy_countdown``,
    ``sell_countdown``, ``buy_signal`` (buy 13 bar), ``sell_signal``.
    """
    validate_ohlc(df)
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    n = len(close)

    setups = td_setup(df, setup_length, compare)
    buy_setup = setups["buy_setup"].to_numpy()
    sell_setup = setups["sell_setup"].to_numpy()

    buy_cd = np.full(n, np.nan)
    sell_cd = np.full(n, np.nan)
    buy_sig = np.zeros(n, dtype=bool)
    sell_sig = np.zeros(n, dtype=bool)

    buy_cd_count = 0
    sell_cd_count = 0
    buy_active = False
    sell_active = False

    for i in range(n):
        if not np.isnan(buy_setup[i]) and buy_setup[i] == setup_length:
            buy_active = True
            buy_cd_count = 0
        if not np.isnan(sell_setup[i]) and sell_setup[i] == setup_length:
            sell_active = True
            sell_cd_count = 0

        if buy_active and i >= 2 and close[i] <= low[i - 2]:
            buy_cd_count += 1
            buy_cd[i] = buy_cd_count
            if buy_cd_count == countdown_length:
                buy_sig[i] = True
                buy_active = False
        if sell_active and i >= 2 and close[i] >= high[i - 2]:
            sell_cd_count += 1
            sell_cd[i] = sell_cd_count
            if sell_cd_count == countdown_length:
                sell_sig[i] = True
                sell_active = False

    return pd.DataFrame(
        {
            "buy_setup": setups["buy_setup"],
            "sell_setup": setups["sell_setup"],
            "buy_countdown": buy_cd,
            "sell_countdown": sell_cd,
            "buy_signal": buy_sig,
            "sell_signal": sell_sig,
        },
        index=df.index,
    )


# ---------------------------------------------------------------------------
# TD Combo Countdown
# ---------------------------------------------------------------------------

def td_combo(
    df: pd.DataFrame, setup_length: int = 9, countdown_length: int = 13, compare: int = 4
) -> pd.DataFrame:
    """TD Combo Countdown.

    Runs from the same setup but uses stricter counting: a combo buy bar
    requires close <= low[2] *and* the bar's low must be lower than the
    prior combo bar's low (marching lows). Because every bar must qualify,
    combo 13s arrive later than classic countdown 13s and are considered
    stronger signals.
    """
    validate_ohlc(df)
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    n = len(close)

    setups = td_setup(df, setup_length, compare)
    buy_setup = setups["buy_setup"].to_numpy()
    sell_setup = setups["sell_setup"].to_numpy()

    buy_cd = np.full(n, np.nan)
    sell_cd = np.full(n, np.nan)
    buy_sig = np.zeros(n, dtype=bool)
    sell_sig = np.zeros(n, dtype=bool)

    buy_cd_count = 0
    sell_cd_count = 0
    buy_active = False
    sell_active = False
    last_buy_low = np.inf
    last_sell_high = -np.inf

    for i in range(n):
        if not np.isnan(buy_setup[i]) and buy_setup[i] == setup_length:
            buy_active = True
            buy_cd_count = 0
            last_buy_low = np.inf
        if not np.isnan(sell_setup[i]) and sell_setup[i] == setup_length:
            sell_active = True
            sell_cd_count = 0
            last_sell_high = -np.inf

        if buy_active and i >= 2 and close[i] <= low[i - 2] and low[i] < last_buy_low:
            buy_cd_count += 1
            buy_cd[i] = buy_cd_count
            last_buy_low = low[i]
            if buy_cd_count == countdown_length:
                buy_sig[i] = True
                buy_active = False
        if sell_active and i >= 2 and close[i] >= high[i - 2] and high[i] > last_sell_high:
            sell_cd_count += 1
            sell_cd[i] = sell_cd_count
            last_sell_high = high[i]
            if sell_cd_count == countdown_length:
                sell_sig[i] = True
                sell_active = False

    return pd.DataFrame(
        {
            "buy_setup": setups["buy_setup"],
            "sell_setup": setups["sell_setup"],
            "buy_combo": buy_cd,
            "sell_combo": sell_cd,
            "buy_signal": buy_sig,
            "sell_signal": sell_sig,
        },
        index=df.index,
    )


# ---------------------------------------------------------------------------
# TD Sequential Ultimate
# ---------------------------------------------------------------------------

def td_sequential_ultimate(
    df: pd.DataFrame, setup_length: int = 9, countdown_length: int = 13, compare: int = 4
) -> pd.DataFrame:
    """TD Sequential with DeMark's qualifier rules ("Ultimate").

    Adds the standard filters on top of the classic count:

    * The setup's bar 8 or 9 must extend the setup's extreme
      (``qualified_setup``).
    * An *aggressive* 13 is a completed countdown whose bar 13 close is
      beyond the bar 8 close of the countdown.
    * A *conservative* 13 additionally requires the countdown to complete
      with the setup-perfected rule and no intervening opposite setup
      (recycle check). Here the conservative flag is a completed
      countdown whose bar 13 low (buy) / high (sell) beats every prior
      countdown bar's extreme.

    Output adds ``buy_aggressive``, ``sell_aggressive``,
    ``buy_conservative``, ``sell_conservative``.
    """
    base = td_countdown(df, setup_length, countdown_length, compare)
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    n = len(close)

    buy_cd = base["buy_countdown"].to_numpy()
    sell_cd = base["sell_countdown"].to_numpy()

    buy_aggr = np.zeros(n, dtype=bool)
    sell_aggr = np.zeros(n, dtype=bool)
    buy_cons = np.zeros(n, dtype=bool)
    sell_cons = np.zeros(n, dtype=bool)

    for i in range(n):
        if not np.isnan(buy_cd[i]) and buy_cd[i] == countdown_length:
            # Aggressive: bar 13 closes below countdown bar 8's close.
            cd8_bars = np.where(buy_cd[: i + 1] == 8)[0]
            aggressive = len(cd8_bars) > 0 and close[i] <= close[cd8_bars[-1]]
            # Conservative: bar 13 makes the lowest low of the countdown.
            start = np.where(buy_cd[: i + 1] == 1)[0]
            conservative = len(start) > 0 and low[i] <= low[start[-1] : i + 1].min()
            buy_aggr[i] = aggressive
            buy_cons[i] = conservative
        if not np.isnan(sell_cd[i]) and sell_cd[i] == countdown_length:
            cd8_bars = np.where(sell_cd[: i + 1] == 8)[0]
            aggressive = len(cd8_bars) > 0 and close[i] >= close[cd8_bars[-1]]
            start = np.where(sell_cd[: i + 1] == 1)[0]
            conservative = len(start) > 0 and high[i] >= high[start[-1] : i + 1].max()
            sell_aggr[i] = aggressive
            sell_cons[i] = conservative

    base["buy_aggressive"] = buy_aggr
    base["sell_aggressive"] = sell_aggr
    base["buy_conservative"] = buy_cons
    base["sell_conservative"] = sell_cons
    return base
