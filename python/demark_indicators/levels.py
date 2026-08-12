"""DeMark price levels and trend tools: TDST, TD Points, TD Lines,
TD Retracements, and the qualified DeMark Trendline."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import validate_ohlc
from .sequential import td_setup


# ---------------------------------------------------------------------------
# TDST (TD Setup Trend)
# ---------------------------------------------------------------------------

def td_setup_trend(df: pd.DataFrame, setup_length: int = 9, compare: int = 4) -> pd.DataFrame:
    """TD Setup Trend support / resistance.

    When a buy setup completes (9), TDST support is set to the lowest low
    of that setup's 9 bars. When a sell setup completes, TDST resistance
    is set to the highest high of the 9 bars. Levels persist until price
    closes through them (support broken on a close below, resistance on a
    close above) or until a new setup replaces them.

    Output: ``tdst_support``, ``tdst_resistance``, plus boolean
    ``support_broken`` / ``resistance_broken`` event columns.
    """
    validate_ohlc(df)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    n = len(close)

    setups = td_setup(df, setup_length, compare)
    buy_setup = setups["buy_setup"].to_numpy()
    sell_setup = setups["sell_setup"].to_numpy()

    support = np.full(n, np.nan)
    resistance = np.full(n, np.nan)
    support_broken = np.zeros(n, dtype=bool)
    resistance_broken = np.zeros(n, dtype=bool)

    cur_support = np.nan
    cur_resistance = np.nan

    for i in range(n):
        if not np.isnan(buy_setup[i]) and buy_setup[i] == setup_length:
            start = max(0, i - setup_length + 1)
            cur_support = low[start : i + 1].min()
        if not np.isnan(sell_setup[i]) and sell_setup[i] == setup_length:
            start = max(0, i - setup_length + 1)
            cur_resistance = high[start : i + 1].max()

        if not np.isnan(cur_support) and close[i] < cur_support:
            support_broken[i] = True
            cur_support = np.nan
        if not np.isnan(cur_resistance) and close[i] > cur_resistance:
            resistance_broken[i] = True
            cur_resistance = np.nan

        support[i] = cur_support
        resistance[i] = cur_resistance

    return pd.DataFrame(
        {
            "tdst_support": support,
            "tdst_resistance": resistance,
            "support_broken": support_broken,
            "resistance_broken": resistance_broken,
        },
        index=df.index,
    )


# ---------------------------------------------------------------------------
# TD Points
# ---------------------------------------------------------------------------

def td_points(df: pd.DataFrame, left: int = 1, right: int = 1) -> pd.DataFrame:
    """Qualified TD Point highs and lows.

    A TD Point high is a high greater than the ``left`` highs before it
    and the ``right`` highs after it (default 1 each side — the classic
    definition); a TD Point low mirrors that. Because ``right`` bars must
    exist, points are only confirmed ``right`` bars later.

    Output: ``td_point_high``, ``td_point_low`` (price at the confirming
    bar, NaN elsewhere).
    """
    validate_ohlc(df)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    n = len(high)

    point_high = np.full(n, np.nan)
    point_low = np.full(n, np.nan)

    for i in range(left, n - right):
        window_high = high[i - left : i + right + 1]
        window_low = low[i - left : i + right + 1]
        if high[i] == window_high.max() and (window_high < high[i]).sum() == left + right:
            point_high[i + right] = high[i]  # confirmed on bar i+right
        if low[i] == window_low.min() and (window_low > low[i]).sum() == left + right:
            point_low[i + right] = low[i]

    return pd.DataFrame(
        {"td_point_high": point_high, "td_point_low": point_low}, index=df.index
    )


# ---------------------------------------------------------------------------
# TD Lines (Supply / Demand)
# ---------------------------------------------------------------------------

def td_lines(df: pd.DataFrame, left: int = 1, right: int = 1, max_level: int = 3) -> pd.DataFrame:
    """TD Supply and Demand lines.

    A TD Demand line connects the two most recent TD Point lows and is
    projected forward; when it breaks, the next older point takes over,
    producing level-1, level-2 and level-3 lines. TD Supply lines mirror
    this from TD Point highs. ``max_level`` caps how many break-replacments
    are tracked.

    Output columns are the current line values projected onto each bar:
    ``demand_1..N`` and ``supply_1..N`` (NaN until two points exist).
    """
    validate_ohlc(df)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    n = len(high)

    # Collect TD Point events (index = confirmation bar, value = price, and
    # the pivot bar itself so slopes use the pivot position).
    hi_pivots: list[tuple[int, float]] = []  # (pivot_bar, price)
    lo_pivots: list[tuple[int, float]] = []
    for i in range(left, n - right):
        wh = high[i - left : i + right + 1]
        wl = low[i - left : i + right + 1]
        if high[i] == wh.max() and (wh < high[i]).sum() == left + right:
            hi_pivots.append((i, high[i]))
        if low[i] == wl.min() and (wl > low[i]).sum() == left + right:
            lo_pivots.append((i, low[i]))

    out = {f"demand_{k}": np.full(n, np.nan) for k in range(1, max_level + 1)}
    out.update({f"supply_{k}": np.full(n, np.nan) for k in range(1, max_level + 1)})

    # Replay bar by bar, maintaining the active point stack per side.
    active_lo: list[tuple[int, float]] = []
    active_hi: list[tuple[int, float]] = []
    lo_i = 0
    hi_i = 0

    def project(p1: tuple[int, float], p2: tuple[int, float], bar: int) -> float:
        (x1, y1), (x2, y2) = p1, p2
        if x2 == x1:
            return y2
        return y2 + (y2 - y1) / (x2 - x1) * (bar - x2)

    for i in range(n):
        # Register any pivot confirmed by this bar (pivot at i-right).
        while lo_i < len(lo_pivots) and lo_pivots[lo_i][0] + right <= i:
            active_lo.append(lo_pivots[lo_i])
            lo_i += 1
        while hi_i < len(hi_pivots) and hi_pivots[hi_i][0] + right <= i:
            active_hi.append(hi_pivots[hi_i])
            hi_i += 1

        # Demand lines: pairs counted back from the most recent points.
        for level in range(1, max_level + 1):
            if len(active_lo) >= level + 1:
                p_new = active_lo[-level]
                p_old = active_lo[-level - 1]
                val = project(p_old, p_new, i)
                if df["close"].iat[i] < val and level < max_level and len(active_lo) >= level + 2:
                    # Broken: promote the next older pair.
                    val = project(active_lo[-level - 2], active_lo[-level - 1], i)
                out[f"demand_{level}"][i] = val

        for level in range(1, max_level + 1):
            if len(active_hi) >= level + 1:
                p_new = active_hi[-level]
                p_old = active_hi[-level - 1]
                val = project(p_old, p_new, i)
                if df["close"].iat[i] > val and level < max_level and len(active_hi) >= level + 2:
                    val = project(active_hi[-level - 2], active_hi[-level - 1], i)
                out[f"supply_{level}"][i] = val

    return pd.DataFrame(out, index=df.index)


# ---------------------------------------------------------------------------
# TD Retracements (Relative Retracement / Arc)
# ---------------------------------------------------------------------------

def td_retracements(
    df: pd.DataFrame, lookback: int = 100, levels: tuple[float, ...] = (0.382, 0.618)
) -> pd.DataFrame:
    """TD Relative Retracement magnet levels.

    Tracks the most recent significant swing high and low over
    ``lookback`` bars. From a swing low, upside magnets are
    low + range * level for each level in ``levels`` (the classic DeMark
    magnets are 38.2% and 61.8%); from a swing high, downside magnets
    mirror this. Each level also gets a qualifier flag: ``qualified_*``
    is True when the swing's final bar closed in the extreme third of its
    range, DeMark's momentum qualification for the level to hold.

    Output: ``swing_high``, ``swing_low``, ``up_<pct>``, ``down_<pct>``
    and ``qualified_up`` / ``qualified_down``.
    """
    validate_ohlc(df)
    high = df["high"]
    low = df["low"]
    close = df["close"]

    swing_high = high.rolling(lookback, min_periods=1).max()
    swing_low = low.rolling(lookback, min_periods=1).min()
    swing_range = (swing_high - swing_low).replace(0.0, np.nan)

    out = pd.DataFrame(index=df.index)
    out["swing_high"] = swing_high
    out["swing_low"] = swing_low

    for lv in levels:
        tag = f"{lv:.3f}".rstrip("0").rstrip(".").replace(".", "_")
        out[f"up_{tag}"] = swing_low + swing_range * lv
        out[f"down_{tag}"] = swing_high - swing_range * lv

    # Qualifier: close of the bar making the swing extreme sits in the
    # outer third of that bar's range.
    bar_range = (high - low).replace(0.0, np.nan)
    out["qualified_up"] = close >= low + bar_range * (2.0 / 3.0)
    out["qualified_down"] = close <= low + bar_range * (1.0 / 3.0)
    return out


# ---------------------------------------------------------------------------
# DeMark Trendline
# ---------------------------------------------------------------------------

def demark_trendline(
    df: pd.DataFrame, left: int = 1, right: int = 1, max_lines: int = 3
) -> pd.DataFrame:
    """Qualified DeMark trendlines with price projections.

    Uses the most recent two TD Point lows to draw the active demand
    (support) trendline and the most recent two TD Point highs for the
    supply (resistance) trendline — the same construction as ``td_lines``
    level 1 — but additionally emits:

    * ``demand_projection`` / ``supply_projection``: where the line sits
      one bar ahead (the classic "expected touch" level), and
    * ``demand_break`` / ``supply_break``: True on bars closing through
      the active line, which under DeMark rules invalidates it and hands
      off to the next line (``max_lines`` deep).
    """
    validate_ohlc(df)
    lines = td_lines(df, left=left, right=right, max_level=max_lines)
    close = df["close"].to_numpy(dtype=float)
    n = len(close)

    out = pd.DataFrame(index=df.index)
    demand = lines["demand_1"].to_numpy(dtype=float)
    supply = lines["supply_1"].to_numpy(dtype=float)

    out["demand_line"] = demand
    out["supply_line"] = supply

    # One-bar-ahead projection: today's value + today's slope.
    demand_slope = np.diff(demand, prepend=np.nan)
    supply_slope = np.diff(supply, prepend=np.nan)
    out["demand_projection"] = demand + demand_slope
    out["supply_projection"] = supply + supply_slope

    demand_break = np.zeros(n, dtype=bool)
    supply_break = np.zeros(n, dtype=bool)
    for i in range(1, n):
        if not np.isnan(demand[i - 1]) and close[i] < demand[i - 1]:
            demand_break[i] = True
        if not np.isnan(supply[i - 1]) and close[i] > supply[i - 1]:
            supply_break[i] = True

    out["demand_break"] = demand_break
    out["supply_break"] = supply_break
    return out
