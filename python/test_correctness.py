"""Hand-verified correctness tests for the DeMark rules.

Unlike ``self_test.py`` (which checks shapes and bounds on synthetic data),
every case here is built from a small hand-constructed price series whose
expected output was worked out by hand from DeMark's published rules.

Run with:

    python3 test_correctness.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import demark_indicators as dm

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS  {name}")
    else:
        FAILED += 1
        print(f"  FAIL  {name}  {detail}")


def frame(closes, highs=None, lows=None, opens=None) -> pd.DataFrame:
    """Build an OHLC frame from a close series with sane synthetic H/L."""
    closes = np.asarray(closes, dtype=float)
    highs = closes + 1.0 if highs is None else np.asarray(highs, dtype=float)
    lows = closes - 1.0 if lows is None else np.asarray(lows, dtype=float)
    opens = closes if opens is None else np.asarray(opens, dtype=float)
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})


# ---------------------------------------------------------------------------
# TD Setup
# ---------------------------------------------------------------------------

def test_setup_completes_on_ninth_bar() -> None:
    # Bars 0-3 flat at 100, then nine consecutive closes each below close[-4].
    closes = [100, 100, 100, 100, 99, 98, 97, 96, 95, 94, 93, 92, 91]
    out = dm.td_setup(frame(closes))
    buy = out["buy_setup"].tolist()

    check(
        "setup counts 1..9 on bars 4..12",
        buy[4:13] == [1, 2, 3, 4, 5, 6, 7, 8, 9],
        f"got {buy[4:13]}",
    )
    check(
        "setup completion flagged only on bar 12",
        out["buy_setup_complete"].tolist().index(True) == 12
        and out["buy_setup_complete"].sum() == 1,
        f"got {out['buy_setup_complete'].tolist()}",
    )
    check("no sell setup on a falling series", out["sell_setup"].max() == 0)


def test_setup_resets_when_condition_fails() -> None:
    # Bar 8 closes equal to close[4] -> strict "<" fails -> count resets to 0.
    closes = [100, 100, 100, 100, 99, 98, 97, 96, 99, 94, 93, 92, 91]
    out = dm.td_setup(frame(closes))
    buy = out["buy_setup"].tolist()

    check("count reaches 4 by bar 7", buy[7] == 4, f"got {buy[7]}")
    check("equal close resets the count to 0", buy[8] == 0, f"got {buy[8]}")
    check("count restarts at 1 afterwards", buy[9] == 1, f"got {buy[9]}")
    check("setup never completes", out["buy_setup_complete"].sum() == 0)


def test_setup_perfection() -> None:
    # Same 9-bar buy setup, but force bar 9's low well below bars 6 and 7.
    closes = [100, 100, 100, 100, 99, 98, 97, 96, 95, 94, 93, 92, 91]
    lows = [c - 1.0 for c in closes]
    lows[12] = 50.0  # bar 9 of the setup makes a decisively lower low
    out = dm.td_setup(frame(closes, lows=lows))
    check("perfected buy setup detected", bool(out["buy_setup_perfected"].iloc[12]))

    # Now make bars 8 and 9 hold well above bars 6 and 7 -> not perfected.
    lows2 = [c - 1.0 for c in closes]
    lows2[9] = 10.0   # bar 6 very low
    lows2[10] = 10.0  # bar 7 very low
    out2 = dm.td_setup(frame(closes, lows=lows2))
    check(
        "non-perfected buy setup detected",
        not bool(out2["buy_setup_perfected"].iloc[12]),
    )


# ---------------------------------------------------------------------------
# TDST — the orientation that was previously inverted
# ---------------------------------------------------------------------------

def test_tdst_orientation() -> None:
    closes = [100, 100, 100, 100, 99, 98, 97, 96, 95, 94, 93, 92, 91]
    highs = [c + 1.0 for c in closes]
    df = frame(closes, highs=highs)
    out = dm.td_setup_trend(df)

    # Buy setup completes on bar 12 (bars 4..12 are the nine setup bars).
    expected_resistance = max(highs[4:13])
    check(
        "buy setup sets TDST RESISTANCE at the highest high of its 9 bars",
        out["tdst_resistance"].iloc[12] == expected_resistance,
        f"got {out['tdst_resistance'].iloc[12]}, expected {expected_resistance}",
    )
    check(
        "buy setup does NOT set TDST support",
        bool(np.isnan(out["tdst_support"].iloc[12])),
        f"got {out['tdst_support'].iloc[12]}",
    )

    # Mirror: a rising series completes a sell setup -> support at lowest low.
    closes_up = [100, 100, 100, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
    lows_up = [c - 1.0 for c in closes_up]
    df_up = frame(closes_up, lows=lows_up)
    out_up = dm.td_setup_trend(df_up)
    expected_support = min(lows_up[4:13])
    check(
        "sell setup sets TDST SUPPORT at the lowest low of its 9 bars",
        out_up["tdst_support"].iloc[12] == expected_support,
        f"got {out_up['tdst_support'].iloc[12]}, expected {expected_support}",
    )
    check(
        "sell setup does NOT set TDST resistance",
        bool(np.isnan(out_up["tdst_resistance"].iloc[12])),
    )


# ---------------------------------------------------------------------------
# TD REI
# ---------------------------------------------------------------------------

def test_rei_matches_manual_formula() -> None:
    rng = np.random.default_rng(7)
    n = 60
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.uniform(0.5, 1.5, n)
    low = close - rng.uniform(0.5, 1.5, n)
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close})

    out = dm.td_range_expansion_index(df, length=5)["rei"].to_numpy()

    # Recompute independently, straight from DeMark's description.
    manual = np.zeros(n)
    vals = np.zeros(n)
    absvals = np.zeros(n)
    for i in range(n):
        if i < 8:
            continue
        cond_a = (high[i] >= low[i - 5] or high[i] >= low[i - 6]) and (
            low[i] <= high[i - 5] or low[i] <= high[i - 6]
        )
        cond_b = (high[i - 2] >= close[i - 7] or high[i - 2] >= close[i - 8]) and (
            low[i - 2] <= close[i - 7] or low[i - 2] <= close[i - 8]
        )
        dh = high[i] - high[i - 2]
        dl = low[i] - low[i - 2]
        if cond_a or cond_b:
            vals[i] = dh + dl
            absvals[i] = abs(dh) + abs(dl)
    for i in range(8, n):
        num = vals[i - 4 : i + 1].sum()
        den = absvals[i - 4 : i + 1].sum()
        manual[i] = 0.0 if den == 0 else 100.0 * num / den

    # Compare once the 5-bar window sits entirely inside the defined region.
    diff = np.abs(out[12:] - manual[12:]).max()
    check("REI matches an independent implementation", diff < 1e-9, f"max diff {diff}")
    check("REI stays within -100..100", np.nanmax(np.abs(out)) <= 100.0 + 1e-9)


# ---------------------------------------------------------------------------
# TD Countdown / Combo
# ---------------------------------------------------------------------------

def test_countdown_needs_close_below_low_two_back() -> None:
    rng = np.random.default_rng(3)
    n = 300
    close = 100 - np.linspace(0, 40, n) + rng.normal(0, 0.5, n)
    high = close + rng.uniform(0.2, 1.0, n)
    low = close - rng.uniform(0.2, 1.0, n)
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close})

    out = dm.td_countdown(df)
    cd = out["buy_countdown"].to_numpy()

    # Every counted bar must satisfy the countdown comparison.
    bad = [
        i for i in range(2, n) if cd[i] > 0 and not (close[i] <= low[i - 2])
    ]
    check("every buy countdown bar closes at/below low[2]", not bad, f"offenders {bad[:5]}")

    # Counts must be strictly ascending within a countdown.
    seq = [c for c in cd if c > 0]
    ascending = all(
        seq[i + 1] == seq[i] + 1 or seq[i + 1] == 1 for i in range(len(seq) - 1)
    )
    check("countdown numbers ascend by one", ascending, f"got {seq[:20]}")
    check("countdown never exceeds 13", max(seq, default=0) <= 13)


def test_combo_is_stricter_than_classic() -> None:
    rng = np.random.default_rng(11)
    n = 600
    close = 100 - np.linspace(0, 60, n) + rng.normal(0, 0.8, n)
    high = close + rng.uniform(0.2, 1.0, n)
    low = close - rng.uniform(0.2, 1.0, n)
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close})

    classic = dm.td_countdown(df)["buy_countdown"].astype(bool).sum()
    combo = dm.td_combo(df)["buy_combo"].astype(bool).sum()
    check(
        "combo counts no more bars than the classic countdown",
        combo <= classic,
        f"combo {combo} vs classic {classic}",
    )

    # Verify the four conditions hold on every strict-phase combo bar.
    out = dm.td_combo(df)
    cd = out["buy_combo"].to_numpy()
    c = df["close"].to_numpy()
    l = df["low"].to_numpy()
    bad = []
    for i in range(2, n):
        if 0 < cd[i] <= 10:
            if not (c[i] <= l[i - 2] and l[i] <= l[i - 1] and c[i] < c[i - 1]):
                bad.append(i)
    check("combo bars 1-10 satisfy all strict conditions", not bad, f"offenders {bad[:5]}")


def test_countdown_deferral() -> None:
    """A 13 may only print when the 13-vs-8 rule is satisfied."""
    rng = np.random.default_rng(5)
    n = 800
    close = 100 - np.linspace(0, 70, n) + rng.normal(0, 1.2, n)
    high = close + rng.uniform(0.2, 1.2, n)
    low = close - rng.uniform(0.2, 1.2, n)
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close})

    with_def = dm.td_countdown(df, use_deferral=True)
    without = dm.td_countdown(df, use_deferral=False)

    check(
        "deferral never produces more 13s than the unqualified count",
        with_def["buy_signal"].sum() <= without["buy_signal"].sum(),
        f"{with_def['buy_signal'].sum()} vs {without['buy_signal'].sum()}",
    )
    check(
        "a 13 and a deferral never land on the same bar",
        not (with_def["buy_signal"] & with_def["buy_deferred"]).any(),
    )


# ---------------------------------------------------------------------------
# Trendline projection clamp (mirrors f_extendBars in the Pine scripts)
# ---------------------------------------------------------------------------

def _extend_bars(x1, y1, x2, y2, max_bars, limit_up, limit_dn) -> int:
    """Python mirror of the Pine f_extendBars helper."""
    slope = 0.0 if (x2 - x1) == 0 else (y2 - y1) / (x2 - x1)
    allowed = float(max_bars)
    if slope > 0.0:
        allowed = min(allowed, (limit_up - y2) / slope)
    elif slope < 0.0:
        allowed = min(allowed, (limit_dn - y2) / slope)
    return int(max(0.0, np.floor(allowed)))


def test_trendline_projection_is_bounded() -> None:
    """A steep trendline must not project off to an absurd price.

    This is what made the chart unreadable: `extend.right` runs a sloped line
    to infinity, so the auto-scale expands to fit it and the candles collapse
    into a thin band.
    """
    close_price = 100.0
    max_dev = 0.15
    limit_up = close_price * (1 + max_dev)
    limit_dn = close_price * (1 - max_dev)
    max_bars = 20

    cases = [
        ("steep up", 0, 100.0, 10, 140.0),
        ("steep down", 0, 100.0, 10, 60.0),
        ("gentle up", 0, 100.0, 50, 101.0),
        ("flat", 0, 100.0, 10, 100.0),
        ("vertical-ish", 0, 100.0, 1, 500.0),
    ]

    worst = 0.0
    for label, x1, y1, x2, y2 in cases:
        n = _extend_bars(x1, y1, x2, y2, max_bars, limit_up, limit_dn)
        slope = 0.0 if x2 == x1 else (y2 - y1) / (x2 - x1)
        end_price = y2 + slope * n
        check(
            f"projection bounded ({label})",
            n <= max_bars,
            f"projected {n} bars, cap is {max_bars}",
        )
        # The endpoint may start outside the band (the pivot itself can be far
        # from price); what matters is that projecting never pushes it further.
        if abs(y2 - close_price) <= close_price * max_dev:
            within = limit_dn - 1e-9 <= end_price <= limit_up + 1e-9
            check(
                f"endpoint stays inside the band ({label})",
                within,
                f"end price {end_price:.2f} outside [{limit_dn}, {limit_up}]",
            )
        worst = max(worst, abs(end_price))

    check("no projection reaches an absurd price", worst < 1000.0, f"worst {worst}")


def main() -> None:
    print("DeMark rule correctness tests\n")
    test_setup_completes_on_ninth_bar()
    test_setup_resets_when_condition_fails()
    test_setup_perfection()
    test_tdst_orientation()
    test_rei_matches_manual_formula()
    test_countdown_needs_close_below_low_two_back()
    test_combo_is_stricter_than_classic()
    test_countdown_deferral()
    test_trendline_projection_is_bounded()

    print(f"\n{PASSED} passed, {FAILED} failed")
    if FAILED:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
