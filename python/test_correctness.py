"""Hand-verified correctness checks for the ADX / Squeeze Filter math.

These cases use tiny constructed series so each assertion can be worked
out on paper. Run with:

    python3 test_correctness.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from adx_squeeze_filter.mathutil import linreg, rma, sma, stdev, true_range
from adx_squeeze_filter.indicator import (
    adx_squeeze_filter,
    directional_movement,
    ttm_squeeze,
)


def ohlc_from_close(close: list[float], wick: float = 0.5) -> pd.DataFrame:
    close_s = pd.Series(close, dtype=float)
    open_ = close_s.shift(1).fillna(close_s.iloc[0])
    high = np.maximum(open_, close_s) + wick
    low = np.minimum(open_, close_s) - wick
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close_s})


def test_sma_and_stdev() -> None:
    s = pd.Series([2.0, 4.0, 6.0, 8.0])
    got = sma(s, 2)
    assert np.isnan(got.iloc[0])
    assert got.iloc[1] == 3.0
    assert got.iloc[2] == 5.0
    assert got.iloc[3] == 7.0

    # Population stdev of [2, 4] = sqrt(((2-3)^2 + (4-3)^2) / 2) = 1
    sd = stdev(s, 2)
    assert abs(sd.iloc[1] - 1.0) < 1e-12


def test_rma_sma_seed() -> None:
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    got = rma(s, 3)
    assert np.isnan(got.iloc[0]) and np.isnan(got.iloc[1])
    assert abs(got.iloc[2] - 2.0) < 1e-12  # SMA seed (1+2+3)/3
    assert abs(got.iloc[3] - 8.0 / 3.0) < 1e-12  # (4 + 2*2)/3
    assert abs(got.iloc[4] - 31.0 / 9.0) < 1e-12  # (5 + 2*(8/3))/3


def test_linreg_straight_line() -> None:
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    got = linreg(s, 4, offset=0)
    assert np.isnan(got.iloc[2])
    # Window [1,2,3,4] is a perfect line; fitted value at the newest bar is 4
    assert abs(got.iloc[3] - 4.0) < 1e-12
    assert abs(got.iloc[4] - 5.0) < 1e-12


def test_true_range_first_bar() -> None:
    high = pd.Series([10.0, 12.0, 11.0])
    low = pd.Series([9.0, 10.0, 8.0])
    close = pd.Series([9.5, 11.0, 9.0])
    tr = true_range(high, low, close)
    assert tr.iloc[0] == 1.0  # high - low on bar 0
    # bar 1: max(12-10, |12-9.5|, |10-9.5|) = max(2, 2.5, 0.5) = 2.5
    assert abs(tr.iloc[1] - 2.5) < 1e-12


def test_dmi_uptrend_plus_di_leads() -> None:
    close = list(np.linspace(100, 130, 80))
    df = ohlc_from_close(close, wick=0.4)
    dmi = directional_movement(df, di_length=14, adx_smoothing=14)
    tail = dmi.dropna().iloc[-10:]
    assert (tail["plus_di"] > tail["minus_di"]).all(), "+DI should lead in a climb"
    assert tail["adx"].mean() > 20.0, "ADX should confirm the climb"


def test_dmi_range_stays_weak() -> None:
    rng = np.random.default_rng(0)
    close = 100.0 + 0.3 * np.sin(np.linspace(0, 12 * np.pi, 120)) + rng.normal(0, 0.05, 120)
    df = ohlc_from_close(list(close), wick=0.3)
    dmi = directional_movement(df)
    mid = dmi["adx"].iloc[40:80].mean()
    assert mid < 25.0, f"ranging ADX should stay modest, got {mid:.2f}"


def test_squeeze_on_when_closes_are_tight() -> None:
    n = 80
    close = [100.0 + 0.01 * ((i % 4) - 1.5) for i in range(n)]
    open_ = close[:]
    # Wide wicks keep Keltner wide while close stdev stays tiny → BB inside KC
    high = [c + 3.0 for c in close]
    low = [c - 3.0 for c in close]
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})
    sqz = ttm_squeeze(df)
    tail = sqz.dropna(subset=["upper_bb", "upper_kc"]).iloc[-20:]
    assert tail["squeeze_on"].all(), "tight closes with wide wicks should squeeze"
    assert not tail["squeeze_off"].any()


def test_squeeze_off_in_volatile_trend() -> None:
    # A smooth climb with tiny wicks: close stdev (trend) dwarfs bar range,
    # so Bollinger expands outside Keltner (squeeze off).
    close = list(np.linspace(100, 160, 80))
    df = ohlc_from_close(close, wick=0.15)
    sqz = ttm_squeeze(df)
    tail = sqz.dropna(subset=["upper_bb", "upper_kc"]).iloc[-15:]
    assert tail["squeeze_off"].all(), "trending closes should take BB outside KC"


def test_fire_is_a_one_bar_release() -> None:
    n = 160
    close = np.ones(n) * 100.0
    close[:90] += 0.02 * np.sin(np.linspace(0, 8 * np.pi, 90))
    close[90:] = np.linspace(100, 128, n - 90)
    open_ = np.r_[close[0], close[:-1]]
    wick = np.r_[np.full(90, 2.5), np.full(n - 90, 0.25)]
    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - wick
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})

    out = adx_squeeze_filter(df, mode="ttm", require_adx_rising=False)
    releases = np.flatnonzero(out["squeeze_release"].to_numpy())
    assert len(releases) >= 1, "expected at least one squeeze release"
    for idx in releases:
        assert bool(out["in_squeeze"].iloc[idx - 1])
        assert not bool(out["in_squeeze"].iloc[idx])

    fires = out["long_fire"] | out["short_fire"]
    assert (fires <= out["squeeze_release"]).all()


def test_both_mode_stricter_than_either() -> None:
    rng = np.random.default_rng(1)
    n = 200
    close = 100 + np.cumsum(rng.normal(0, 0.4, n))
    df = ohlc_from_close(list(close), wick=0.8)
    both = adx_squeeze_filter(df, mode="both")
    either = adx_squeeze_filter(df, mode="either")
    ttm = adx_squeeze_filter(df, mode="ttm")
    adx_only = adx_squeeze_filter(df, mode="adx")
    assert (both["in_squeeze"] <= either["in_squeeze"]).all()
    assert (both["in_squeeze"] <= ttm["in_squeeze"]).all()
    assert (both["in_squeeze"] <= adx_only["in_squeeze"]).all()


def test_validate_rejects_bad_frames() -> None:
    from adx_squeeze_filter.data import validate_ohlc

    try:
        validate_ohlc(pd.DataFrame({"close": [1, 2]}))
        raise AssertionError("missing columns should raise")
    except ValueError:
        pass
    try:
        validate_ohlc([1, 2, 3])  # type: ignore[arg-type]
        raise AssertionError("non-frame should raise")
    except TypeError:
        pass


def main() -> None:
    tests = [
        test_sma_and_stdev,
        test_rma_sma_seed,
        test_linreg_straight_line,
        test_true_range_first_bar,
        test_dmi_uptrend_plus_di_leads,
        test_dmi_range_stays_weak,
        test_squeeze_on_when_closes_are_tight,
        test_squeeze_off_in_volatile_trend,
        test_fire_is_a_one_bar_release,
        test_both_mode_stricter_than_either,
        test_validate_rejects_bad_frames,
    ]
    for fn in tests:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(tests)} correctness tests passed.")


if __name__ == "__main__":
    main()
