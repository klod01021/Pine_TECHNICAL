"""TD Sequential family: TD Setup, TD Countdown, TD Combo, Ultimate.

These indicators are stateful — a count on bar *i* depends on whether the
sequence survived bars ``0..i-1`` — so the implementations iterate bar by
bar, exactly like the Pine Script v6 versions in ``/pine``.

Rules follow DeMark's published specification:

* **Setup** — 9 consecutive closes below (buy) / above (sell) the close
  ``compare`` bars earlier. A bar that fails the strict comparison, including
  an *equal* close, resets the count to zero.
* **Setup perfection** — a buy setup is "perfected" when the low of bar 8 or
  bar 9 is at or below the lows of bars 6 and 7 (mirrored for sells).
* **Countdown** — from setup completion, count bars closing at or below the
  low two bars earlier (buy) / at or above the high two bars earlier (sell).
  Bars need not be consecutive.
* **13 vs 8 deferral** — the 13th countdown bar only qualifies if its low is
  at or below the close of countdown bar 8 (buy), or its high at or above
  that close (sell). Otherwise the 13 is *deferred* and the count waits for
  a later bar that satisfies both conditions.
* **Cancellation** — a countdown is cancelled when a setup completes in the
  opposite direction, or when price closes through the TDST level of the
  setup that generated it.
* **Combo** — counts 1-10 require four conditions; counts 11-13 only require
  a close beyond the previous counted close.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import validate_ohlc


# ---------------------------------------------------------------------------
# TD Setup (1-9) with perfection
# ---------------------------------------------------------------------------

def td_setup(df: pd.DataFrame, setup_length: int = 9, compare: int = 4) -> pd.DataFrame:
    """TD Buy/Sell Setup with perfection flags.

    A count of ``0`` means no setup is active on that bar (matching the Pine
    version). Reaching ``setup_length`` completes the setup; if the next bar
    also qualifies the count recycles to 1.

    Output columns
    --------------
    buy_setup, sell_setup:
        The running count (0 when inactive).
    buy_setup_complete, sell_setup_complete:
        True on the bar the setup reaches ``setup_length``.
    buy_setup_perfected, sell_setup_perfected:
        True on a completion bar that also satisfies DeMark's perfection rule.
    """
    validate_ohlc(df)
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    n = len(close)

    buy = np.zeros(n, dtype=int)
    sell = np.zeros(n, dtype=int)
    buy_done = np.zeros(n, dtype=bool)
    sell_done = np.zeros(n, dtype=bool)
    buy_perfect = np.zeros(n, dtype=bool)
    sell_perfect = np.zeros(n, dtype=bool)

    b = 0
    s = 0
    for i in range(n):
        if i < compare:
            continue

        if close[i] < close[i - compare]:
            b += 1
            s = 0
        elif close[i] > close[i - compare]:
            s += 1
            b = 0
        else:
            # An equal close fails the strict comparison and breaks both counts.
            b = 0
            s = 0

        if b > setup_length:
            b = 1
        if s > setup_length:
            s = 1

        buy[i] = b
        sell[i] = s

        if b == setup_length:
            buy_done[i] = True
            # Perfection: min(low of bars 8, 9) <= min(low of bars 6, 7).
            if i >= 3:
                bar8, bar9 = low[i - 1], low[i]
                bar6, bar7 = low[i - 3], low[i - 2]
                buy_perfect[i] = min(bar8, bar9) <= min(bar6, bar7)
        if s == setup_length:
            sell_done[i] = True
            if i >= 3:
                bar8, bar9 = high[i - 1], high[i]
                bar6, bar7 = high[i - 3], high[i - 2]
                sell_perfect[i] = max(bar8, bar9) >= max(bar6, bar7)

    return pd.DataFrame(
        {
            "buy_setup": buy,
            "sell_setup": sell,
            "buy_setup_complete": buy_done,
            "sell_setup_complete": sell_done,
            "buy_setup_perfected": buy_perfect,
            "sell_setup_perfected": sell_perfect,
        },
        index=df.index,
    )


# ---------------------------------------------------------------------------
# TD Countdown (classic 1-13)
# ---------------------------------------------------------------------------

def td_countdown(
    df: pd.DataFrame,
    setup_length: int = 9,
    countdown_length: int = 13,
    compare: int = 4,
    use_deferral: bool = True,
    cancel_on_opposite_setup: bool = True,
    cancel_on_tdst: bool = True,
) -> pd.DataFrame:
    """TD Countdown with DeMark's deferral and cancellation rules.

    Parameters
    ----------
    use_deferral:
        Apply the 13-vs-8 rule. The 13th bar must have its low at or below
        (buy) / high at or above (sell) the close of countdown bar 8. When the
        rule is not met the 13 is deferred, not cancelled.
    cancel_on_opposite_setup:
        Kill an active countdown when a setup completes the other way.
    cancel_on_tdst:
        Kill an active buy countdown when price closes above the TDST
        resistance of its generating setup (mirrored for sells).

    Output columns
    --------------
    buy_setup, sell_setup, buy_countdown, sell_countdown,
    buy_signal / sell_signal (a qualified 13),
    buy_deferred / sell_deferred (a 13 postponed by the 13-vs-8 rule),
    buy_cancelled / sell_cancelled.
    """
    validate_ohlc(df)
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    n = len(close)

    setups = td_setup(df, setup_length, compare)
    buy_done = setups["buy_setup_complete"].to_numpy()
    sell_done = setups["sell_setup_complete"].to_numpy()

    buy_cd = np.zeros(n, dtype=int)
    sell_cd = np.zeros(n, dtype=int)
    buy_sig = np.zeros(n, dtype=bool)
    sell_sig = np.zeros(n, dtype=bool)
    buy_def = np.zeros(n, dtype=bool)
    sell_def = np.zeros(n, dtype=bool)
    buy_cancel = np.zeros(n, dtype=bool)
    sell_cancel = np.zeros(n, dtype=bool)

    b_count = 0
    s_count = 0
    b_active = False
    s_active = False
    b_cd8_close = np.nan
    s_cd8_close = np.nan
    # TDST level of the setup that generated the active countdown.
    b_tdst_resistance = np.nan
    s_tdst_support = np.nan

    for i in range(n):
        # A completed setup starts (or restarts) the countdown on that side and
        # cancels any countdown running the other way.
        if buy_done[i]:
            b_active = True
            b_count = 0
            b_cd8_close = np.nan
            start = max(0, i - setup_length + 1)
            b_tdst_resistance = high[start : i + 1].max()
            if cancel_on_opposite_setup and s_active:
                s_active = False
                sell_cancel[i] = True
        if sell_done[i]:
            s_active = True
            s_count = 0
            s_cd8_close = np.nan
            start = max(0, i - setup_length + 1)
            s_tdst_support = low[start : i + 1].min()
            if cancel_on_opposite_setup and b_active:
                b_active = False
                buy_cancel[i] = True

        # TDST violation cancels the countdown it belongs to.
        if cancel_on_tdst and b_active and not np.isnan(b_tdst_resistance):
            if close[i] > b_tdst_resistance:
                b_active = False
                buy_cancel[i] = True
        if cancel_on_tdst and s_active and not np.isnan(s_tdst_support):
            if close[i] < s_tdst_support:
                s_active = False
                sell_cancel[i] = True

        # Buy countdown.
        if b_active and i >= 2 and close[i] <= low[i - 2]:
            if b_count == countdown_length - 1:
                qualified = (not use_deferral) or np.isnan(b_cd8_close) or (low[i] <= b_cd8_close)
                if qualified:
                    b_count += 1
                    buy_cd[i] = b_count
                    buy_sig[i] = True
                    b_active = False
                else:
                    buy_def[i] = True
            else:
                b_count += 1
                buy_cd[i] = b_count
                if b_count == 8:
                    b_cd8_close = close[i]

        # Sell countdown.
        if s_active and i >= 2 and close[i] >= high[i - 2]:
            if s_count == countdown_length - 1:
                qualified = (not use_deferral) or np.isnan(s_cd8_close) or (high[i] >= s_cd8_close)
                if qualified:
                    s_count += 1
                    sell_cd[i] = s_count
                    sell_sig[i] = True
                    s_active = False
                else:
                    sell_def[i] = True
            else:
                s_count += 1
                sell_cd[i] = s_count
                if s_count == 8:
                    s_cd8_close = close[i]

    return pd.DataFrame(
        {
            "buy_setup": setups["buy_setup"],
            "sell_setup": setups["sell_setup"],
            "buy_setup_perfected": setups["buy_setup_perfected"],
            "sell_setup_perfected": setups["sell_setup_perfected"],
            "buy_countdown": buy_cd,
            "sell_countdown": sell_cd,
            "buy_signal": buy_sig,
            "sell_signal": sell_sig,
            "buy_deferred": buy_def,
            "sell_deferred": sell_def,
            "buy_cancelled": buy_cancel,
            "sell_cancelled": sell_cancel,
        },
        index=df.index,
    )


# ---------------------------------------------------------------------------
# TD Combo Countdown
# ---------------------------------------------------------------------------

def td_combo(
    df: pd.DataFrame,
    setup_length: int = 9,
    countdown_length: int = 13,
    compare: int = 4,
    strict_through: int = 10,
    cancel_on_opposite_setup: bool = True,
) -> pd.DataFrame:
    """TD Combo Countdown.

    For counts 1..``strict_through`` (10 by default) a buy combo bar must
    satisfy all four DeMark conditions:

    1. ``close <= low[2]``
    2. ``low <= low[1]``
    3. ``close < close[1]``
    4. ``close <`` the previous counted combo close

    For counts above ``strict_through`` only condition 4 applies. Sell combo
    bars mirror this with highs. Set ``strict_through=countdown_length`` for
    the fully conservative version that applies all four rules to every bar.
    """
    validate_ohlc(df)
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    n = len(close)

    setups = td_setup(df, setup_length, compare)
    buy_done = setups["buy_setup_complete"].to_numpy()
    sell_done = setups["sell_setup_complete"].to_numpy()

    buy_cd = np.zeros(n, dtype=int)
    sell_cd = np.zeros(n, dtype=int)
    buy_sig = np.zeros(n, dtype=bool)
    sell_sig = np.zeros(n, dtype=bool)

    b_count = 0
    s_count = 0
    b_active = False
    s_active = False
    b_prev_close = np.nan  # close of the previous counted combo bar
    s_prev_close = np.nan

    for i in range(n):
        if buy_done[i]:
            b_active = True
            b_count = 0
            b_prev_close = np.nan
            if cancel_on_opposite_setup:
                s_active = False
        if sell_done[i]:
            s_active = True
            s_count = 0
            s_prev_close = np.nan
            if cancel_on_opposite_setup:
                b_active = False

        if b_active and i >= 2:
            below_prev_counted = np.isnan(b_prev_close) or close[i] < b_prev_close
            if b_count < strict_through:
                ok = (
                    close[i] <= low[i - 2]
                    and low[i] <= low[i - 1]
                    and close[i] < close[i - 1]
                    and below_prev_counted
                )
            else:
                ok = below_prev_counted
            if ok:
                b_count += 1
                buy_cd[i] = b_count
                b_prev_close = close[i]
                if b_count == countdown_length:
                    buy_sig[i] = True
                    b_active = False

        if s_active and i >= 2:
            above_prev_counted = np.isnan(s_prev_close) or close[i] > s_prev_close
            if s_count < strict_through:
                ok = (
                    close[i] >= high[i - 2]
                    and high[i] >= high[i - 1]
                    and close[i] > close[i - 1]
                    and above_prev_counted
                )
            else:
                ok = above_prev_counted
            if ok:
                s_count += 1
                sell_cd[i] = s_count
                s_prev_close = close[i]
                if s_count == countdown_length:
                    sell_sig[i] = True
                    s_active = False

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
    """TD Sequential with every qualifier switched on, plus the Combo count.

    This is the "everything" view: the classic countdown with the 13-vs-8
    deferral and both cancellation rules active, setup perfection flags, and
    the Combo countdown alongside it so the two can be compared. Bars where
    both a Sequential 13 and a Combo 13 land are flagged in
    ``buy_confluence`` / ``sell_confluence``, which DeMark traders treat as
    the highest-conviction reading.
    """
    base = td_countdown(
        df,
        setup_length=setup_length,
        countdown_length=countdown_length,
        compare=compare,
        use_deferral=True,
        cancel_on_opposite_setup=True,
        cancel_on_tdst=True,
    )
    combo = td_combo(
        df, setup_length=setup_length, countdown_length=countdown_length, compare=compare
    )

    out = base.copy()
    out["buy_combo"] = combo["buy_combo"]
    out["sell_combo"] = combo["sell_combo"]
    out["buy_combo_signal"] = combo["buy_signal"]
    out["sell_combo_signal"] = combo["sell_signal"]
    out["buy_confluence"] = base["buy_signal"] & combo["buy_signal"]
    out["sell_confluence"] = base["sell_signal"] & combo["sell_signal"]
    return out
