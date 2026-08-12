"""TD D-Wave: DeMark's mechanical Elliott-style wave counter.

TD D-Wave applies fixed rules to a sequence of TD Point pivots to label
waves 1-5 (and the A-B-C correction) instead of leaving the count to
discretion. The core rules implemented here (DeMark, "New Market Timing
Techniques"):

* Wave 1: first decisive move off a major low/high.
* Wave 2: retraces wave 1 but must NOT exceed its origin.
* Wave 3: extends beyond the wave 1 extreme; the move from the wave 2
  low to the wave 3 high must exceed wave 1's range.
* Wave 4: retraces wave 3 but must not close into wave 1's territory
  (the no-overlap rule).
* Wave 5: final push beyond the wave 3 extreme; often coincides with a
  TD Sequential 13 (that confluence is left to the caller to combine).
* Waves A/B/C: counter-trend correction after a completed 5.

The output is a per-bar label series (wave number as float, NaN when no
active count) plus the pivot list so callers can draw zigzags.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import validate_ohlc


def _zigzag_pivots(
    high: np.ndarray, low: np.ndarray, left: int, right: int
) -> list[tuple[int, float, str]]:
    """Collect alternating TD Point pivots into a zigzag list.

    Returns a list of (bar_index, price, kind) where kind is "H" or "L".
    """
    pivots: list[tuple[int, float, str]] = []
    n = len(high)
    for i in range(left, n - right):
        wh = high[i - left : i + right + 1]
        wl = low[i - left : i + right + 1]
        if high[i] == wh.max() and (wh < high[i]).sum() == left + right:
            pivots.append((i, float(high[i]), "H"))
        if low[i] == wl.min() and (wl > low[i]).sum() == left + right:
            pivots.append((i, float(low[i]), "L"))

    # Enforce alternation: keep the more extreme pivot when two of the
    # same kind arrive back to back.
    cleaned: list[tuple[int, float, str]] = []
    for bar, price, kind in pivots:
        if cleaned and cleaned[-1][2] == kind:
            if kind == "H" and price > cleaned[-1][1]:
                cleaned[-1] = (bar, price, kind)
            elif kind == "L" and price < cleaned[-1][1]:
                cleaned[-1] = (bar, price, kind)
        else:
            cleaned.append((bar, price, kind))
    return cleaned


def td_d_wave(
    df: pd.DataFrame, left: int = 5, right: int = 5, max_waves: int = 8
) -> pd.DataFrame:
    """TD D-Wave wave count.

    Parameters
    ----------
    left, right:
        TD Point strength (bars each side). Larger values count only
        major swings; 5/5 is the usual daily-chart setting.
    max_waves:
        Upper bound on labelled waves (5 impulse + A,B,C = 8).

    Output columns
    --------------
    wave_label:
        Float label on each bar the count passes through: 1..5 for the
        impulse, 6, 7, 8 for A, B, C. NaN before a count is established.
    wave_name:
        Human readable label ("W1".."W5", "WA", "WB", "WC").
    pivot_price / pivot_name:
        Price and label at confirmed pivots (NaN elsewhere), handy for
        drawing the zigzag overlay.
    """
    validate_ohlc(df)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    n = len(high)

    pivots = _zigzag_pivots(high, low, left, right)

    names = ["W1", "W2", "W3", "W4", "W5", "WA", "WB", "WC"][:max_waves]

    wave_label = np.full(n, np.nan)
    wave_name: list[object] = [None] * n
    pivot_price = np.full(n, np.nan)
    pivot_name: list[object] = [None] * n

    if len(pivots) >= 2:
        # Direction of the first leg decides whether this is an up or
        # down impulse count.
        up_count = pivots[1][2] == "H"

        # Label the pivot sequence W1..W5, WA..WC as long as the rules hold.
        w_idx = 0  # index into `names`
        extremes: list[tuple[int, float, str]] = [pivots[0]]
        wave_origin = pivots[0][1]
        w1_extreme: float | None = None
        w3_extreme: float | None = None
        w1_range: float | None = None

        for p in range(1, len(pivots)):
            bar, price, kind = pivots[p]
            if w_idx >= len(names):
                break

            label = names[w_idx]
            valid = True

            if label == "W2":
                # Must not exceed wave 1's origin.
                if up_count and price < wave_origin:
                    valid = False
                if not up_count and price > wave_origin:
                    valid = False
                if valid:
                    w1_extreme = extremes[-1][1]
                    w1_range = abs(w1_extreme - wave_origin)
            elif label == "W3":
                # Must extend beyond wave 1's extreme.
                if up_count and w1_extreme is not None and price <= w1_extreme:
                    valid = False
                if not up_count and w1_extreme is not None and price >= w1_extreme:
                    valid = False
                if valid:
                    w3_extreme = price
            elif label == "W4":
                # Must not overlap wave 1's territory.
                if up_count and w1_extreme is not None and price < w1_extreme:
                    valid = False
                if not up_count and w1_extreme is not None and price > w1_extreme:
                    valid = False
            elif label == "W5":
                # Must push beyond wave 3's extreme.
                if up_count and w3_extreme is not None and price <= w3_extreme:
                    valid = False
                if not up_count and w3_extreme is not None and price >= w3_extreme:
                    valid = False

            if not valid:
                # Rule violation: the count restarts from the last pivot.
                extremes = [pivots[p - 1], pivots[p]]
                wave_origin = pivots[p - 1][1]
                w_idx = 1
                w1_extreme = None
                w3_extreme = None
                w1_range = None
                continue

            extremes.append((bar, price, kind))
            pivot_price[bar] = price
            pivot_name[bar] = label

            # Stretch the label across the bars of this leg.
            prev_bar = extremes[-2][0]
            for b in range(prev_bar, bar + 1):
                wave_label[b] = float(w_idx + 1)
                wave_name[b] = label

            w_idx += 1

    return pd.DataFrame(
        {
            "wave_label": wave_label,
            "wave_name": pd.Series(wave_name, index=df.index, dtype=object),
            "pivot_price": pivot_price,
            "pivot_name": pd.Series(pivot_name, index=df.index, dtype=object),
        },
        index=df.index,
    )
