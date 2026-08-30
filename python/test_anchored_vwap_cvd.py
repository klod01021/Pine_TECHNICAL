"""Unit tests for Anchored VWAP + CVD. Formulas must stay aligned with the Pine port."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from anchored_vwap_cvd import VwapCvdConfig, compute_anchored_vwap_cvd, generate_synthetic_ohlcv


def _bars(rows: list[tuple], freq: str = "5min", start: str = "2024-06-03 09:30") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(rows), freq=freq)
    data = np.array(rows, dtype=float)
    return pd.DataFrame(
        {"open": data[:, 0], "high": data[:, 1], "low": data[:, 2], "close": data[:, 3], "volume": data[:, 4]},
        index=idx,
    )


def test_constant_price_vwap_equals_price_and_zero_stdev():
    df = _bars([(10, 10, 10, 10, v) for v in (100, 50, 25)])
    out = compute_anchored_vwap_cvd(df, detect_divergence=False)
    np.testing.assert_allclose(out["vwap"], 10.0)
    np.testing.assert_allclose(out["stdev"], 0.0)


def test_vwap_is_volume_weighted():
    # two bars, hlc3 == close because H=L=C
    df = _bars([(10, 10, 10, 10, 1), (20, 20, 20, 20, 3)])
    out = compute_anchored_vwap_cvd(df, detect_divergence=False)
    expected = np.array([10.0, (10 * 1 + 20 * 3) / 4])
    np.testing.assert_allclose(out["vwap"], expected)


def test_stdev_matches_volume_weighted_second_moment():
    df = _bars([(10, 12, 8, 11, 2), (11, 15, 10, 14, 8), (14, 16, 13, 13, 5)])
    cfg = VwapCvdConfig(price_source="hlc3", detect_divergence=False)
    out = compute_anchored_vwap_cvd(df, cfg)
    src = (df.high + df.low + df.close) / 3.0
    w = df.volume
    vwap = (src * w).cumsum() / w.cumsum()
    pv2 = (src * src * w).cumsum()
    var = np.maximum(pv2 / w.cumsum() - vwap * vwap, 0.0)
    np.testing.assert_allclose(out["vwap"], vwap)
    np.testing.assert_allclose(out["stdev"], np.sqrt(var))
    np.testing.assert_allclose(out["vwap_upper_1"], vwap + np.sqrt(var))
    np.testing.assert_allclose(out["vwap_lower_2"], vwap - 2.0 * np.sqrt(var))


def test_clv_delta_formula():
    # high 12, low 8, close 11, vol 100 -> clv = (22-12-8)/4 = 0.5, delta = 50
    df = _bars([(10, 12, 8, 11, 100)])
    out = compute_anchored_vwap_cvd(df, delta_method="clv", detect_divergence=False)
    np.testing.assert_allclose(out["delta"].iloc[0], 50.0)
    np.testing.assert_allclose(out["cvd"].iloc[0], 50.0)


def test_clv_zero_range_falls_back_to_close_vs_prev():
    df = _bars([(10, 10, 10, 10, 40), (10, 10, 10, 12, 40)])
    out = compute_anchored_vwap_cvd(df, delta_method="clv", detect_divergence=False)
    np.testing.assert_allclose(out["delta"].iloc[1], 40.0)


def test_close_open_delta():
    df = _bars([(10, 12, 9, 11, 10), (11, 12, 8, 8, 10)])
    out = compute_anchored_vwap_cvd(df, delta_method="close_open", detect_divergence=False)
    np.testing.assert_allclose(out["delta"], [10.0, -10.0])
    np.testing.assert_allclose(out["cvd"], [10.0, 0.0])


def test_session_anchor_resets_cumulatives():
    day1 = _bars([(10, 10, 10, 10, 10), (12, 12, 12, 12, 10)])
    day2 = _bars(
        [(20, 20, 20, 20, 10), (22, 22, 22, 22, 10)],
        start="2024-06-04 09:30",
    )
    df = pd.concat([day1, day2])
    out = compute_anchored_vwap_cvd(df, anchor="session", detect_divergence=False)
    assert bool(out["new_anchor"].iloc[0])
    assert not bool(out["new_anchor"].iloc[1])
    assert bool(out["new_anchor"].iloc[2])
    np.testing.assert_allclose(out["vwap"].iloc[1], 11.0)
    np.testing.assert_allclose(out["vwap"].iloc[2], 20.0)
    np.testing.assert_allclose(out["cvd"].iloc[2], out["delta"].iloc[2])


def test_timestamp_anchor_masks_prior_bars():
    df = _bars([(10, 10, 10, 10, 1), (20, 20, 20, 20, 1), (30, 30, 30, 30, 1)])
    ts = df.index[1]
    out = compute_anchored_vwap_cvd(df, anchor="timestamp", anchor_timestamp=ts, detect_divergence=False)
    assert np.isnan(out["vwap"].iloc[0])
    np.testing.assert_allclose(out["vwap"].iloc[1], 20.0)
    np.testing.assert_allclose(out["vwap"].iloc[2], 25.0)


def test_rolling_window_matches_pandas():
    df = generate_synthetic_ohlcv(n_sessions=2, seed=1)
    length = 12
    out = compute_anchored_vwap_cvd(
        df, VwapCvdConfig(anchor="rolling", rolling_length=length, detect_divergence=False)
    )
    src = (df.high + df.low + df.close) / 3.0
    pv = src * df.volume
    expected = pv.rolling(length, min_periods=1).sum() / df.volume.rolling(length, min_periods=1).sum()
    np.testing.assert_allclose(out["vwap"], expected.to_numpy())


def test_week_and_month_groupings_change_at_boundaries():
    idx = pd.DatetimeIndex(
        [
            "2024-06-28 10:00",  # Friday
            "2024-06-28 11:00",
            "2024-07-01 10:00",  # Monday, new ISO week + new month
        ]
    )
    df = pd.DataFrame(
        {"open": 1, "high": 1, "low": 1, "close": 1, "volume": [1, 1, 1]},
        index=idx,
    )
    week = compute_anchored_vwap_cvd(df, anchor="week", detect_divergence=False)
    month = compute_anchored_vwap_cvd(df, anchor="month", detect_divergence=False)
    assert list(week["new_anchor"]) == [True, False, True]
    assert list(month["new_anchor"]) == [True, False, True]


def test_regular_bullish_divergence_price_ll_cvd_hl():
    # Confirmed pivot lows at i=3 and i=9 with left=right=2.
    n = 14
    low = np.array([5, 4, 3, 2, 3, 4, 3, 2.5, 2.2, 1.5, 2.2, 3, 4, 5], dtype=float)
    high = low + 2
    close = low + 1
    open_ = close
    # CVD higher low while price lower low: 10 at first pivot low, 20 at second.
    cvd_target = np.array([30, 20, 12, 10, 14, 18, 16, 19, 21, 20, 22, 24, 26, 28], dtype=float)
    volume = np.ones(n)
    # Use close_open with crafted OHLC so delta == 0, then we cannot inject CVD.
    # Instead build price pivots and a CVD series via clv by placing close in the range.
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=pd.date_range("2024-06-03 09:30", periods=n, freq="5min"),
    )
    # Force CVD by using a custom path: compute then overwrite is not allowed.
    # Craft delta via close_close / volume so cvd tracks cvd_target.
    # delta[0] = cvd_target[0], delta[i] = diff.
    # close_open delta = sign(c-o)*vol, so keep o==c and use clv.
    # Easier: monkey through close_close with close path matching signs — skip.
    # Direct unit of _divergences via public compute using delta_method and volume signs:
    # We'll feed increasing then decreasing CVD independently by close_open:
    # up bars add +vol, down bars add -vol. Construct so cumulative matches.
    deltas = np.diff(cvd_target, prepend=0.0)
    # Reconstruct bars whose close-open sign and volume equal those deltas.
    open_ = np.full(n, 10.0)
    close = np.where(deltas >= 0, 11.0, 9.0)
    close = np.where(deltas == 0, 10.0, close)
    high = np.maximum(open_, close) + 0.5
    # Keep the designed swing lows on the low series (independent of body).
    df = pd.DataFrame(
        {"open": open_, "high": np.maximum(high, low + 1), "low": low, "close": close, "volume": np.abs(deltas)},
        index=pd.date_range("2024-06-03 09:30", periods=n, freq="5min"),
    )
    out = compute_anchored_vwap_cvd(
        df,
        VwapCvdConfig(
            delta_method="close_open",
            pivot_left=2,
            pivot_right=2,
            detect_divergence=True,
            cvd_ema=1,
        ),
    )
    np.testing.assert_allclose(out["cvd"], cvd_target)
    assert out["bull_div"].any()


def test_missing_columns_raise():
    df = pd.DataFrame({"close": [1, 2], "volume": [1, 1]})
    with pytest.raises(ValueError, match="missing columns"):
        compute_anchored_vwap_cvd(df)


def test_synthetic_demo_runs_and_has_finite_last_row():
    df = generate_synthetic_ohlcv(n_sessions=3, seed=0)
    out = compute_anchored_vwap_cvd(df, VwapCvdConfig(anchor="session", cvd_ema=5))
    last = out.iloc[-1]
    assert np.isfinite(last.vwap)
    assert np.isfinite(last.cvd)
    assert out["new_anchor"].sum() == 3
    assert set(["vwap_upper_1", "vwap_lower_2", "confluence"]).issubset(out.columns)
