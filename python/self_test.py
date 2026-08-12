"""Self-test for the DeMark indicator library.

Generates a deterministic synthetic OHLC series (trend + chop + reversal)
and runs every indicator over it, asserting the outputs have the right
shape, bounds, and basic properties. Run with:

    python3 self_test.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import demark_indicators as dm


def make_sample_data(n: int = 400, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    # Uptrend, then chop, then downtrend: exercises buys and sells.
    base = 100 + 0.15 * t[: n // 2]
    chop = base[-1] + 2.0 * np.sin(np.linspace(0, 6 * np.pi, n - n // 2))
    price = np.concatenate([base, chop])
    price[n // 2 + n // 4 :] -= np.linspace(0, 12, len(price[n // 2 + n // 4 :]))

    close = price + rng.normal(0, 0.4, n)
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.0, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.0, n)

    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close}, index=idx
    )


def check(name: str, out: pd.DataFrame, n: int, required: list[str]) -> None:
    assert isinstance(out, pd.DataFrame), f"{name}: not a DataFrame"
    assert len(out) == n, f"{name}: expected {n} rows, got {len(out)}"
    for col in required:
        assert col in out.columns, f"{name}: missing column {col}"
    print(f"  ok  {name:<28} cols={list(out.columns)}")


def main() -> None:
    df = make_sample_data()
    n = len(df)
    print(f"Sample data: {n} bars\nRunning indicators...\n")

    # Oscillators -------------------------------------------------------------
    out = dm.demarker(df)
    check("demarker", out, n, ["dem"])
    vals = out["dem"].dropna()
    assert vals.between(0, 100).all(), "demarker out of [0,100]"

    out = dm.demarker_ii(df)
    check("demarker_ii", out, n, ["demarker_ii"])
    assert out["demarker_ii"].dropna().between(0, 100).all()

    out = dm.td_pressure_ratio(df)
    check("td_pressure_ratio", out, n, ["pressure_ratio"])
    assert out["pressure_ratio"].dropna().between(0, 100).all()

    out = dm.td_range_expansion_index(df)
    check("td_range_expansion_index", out, n, ["rei"])
    rei = out["rei"].dropna()
    assert (rei >= -100.000001).all() and (rei <= 100.000001).all()

    out = dm.td_poq(df)
    check("td_poq", out, n, ["poq"])

    out = dm.td_alignment(df)
    check("td_alignment", out, n, ["alignment", "signal"])

    out = dm.td_roc(df)
    check("td_roc", out, n, ["roc", "signal"])

    out = dm.td_oscillator(df)
    check("td_oscillator", out, n, ["td_oscillator"])

    # Sequential family --------------------------------------------------------
    out = dm.td_setup(df)
    check("td_setup", out, n, ["buy_setup", "sell_setup", "buy_setup_perfected"])
    assert out["buy_setup"].max() <= 9, "buy setup exceeded 9"
    assert out["sell_setup"].max() <= 9, "sell setup exceeded 9"
    print(f"      setups completed: {int(out['buy_setup_complete'].sum())} buy, "
          f"{int(out['sell_setup_complete'].sum())} sell "
          f"({int(out['buy_setup_perfected'].sum())} perfected buys)")

    out = dm.td_countdown(df)
    check("td_countdown", out, n, ["buy_countdown", "sell_countdown", "buy_deferred"])
    assert out["buy_countdown"].max() <= 13, "buy countdown exceeded 13"
    print(f"      countdown buy 13s: {int(out['buy_signal'].sum())}, "
          f"sell 13s: {int(out['sell_signal'].sum())}, "
          f"cancelled: {int(out['buy_cancelled'].sum() + out['sell_cancelled'].sum())}")

    out = dm.td_combo(df)
    check("td_combo", out, n, ["buy_combo", "sell_combo"])
    print(f"      combo buy 13s:     {int(out['buy_signal'].sum())}, "
          f"sell 13s: {int(out['sell_signal'].sum())}")

    out = dm.td_sequential_ultimate(df)
    check("td_sequential_ultimate", out, n,
          ["buy_confluence", "sell_confluence", "buy_combo"])

    # Levels and trend ----------------------------------------------------------
    out = dm.td_setup_trend(df)
    check("td_setup_trend", out, n, ["tdst_support", "tdst_resistance"])

    out = dm.td_risk_level(df)
    check("td_risk_level", out, n, ["buy_risk_level", "sell_risk_level"])

    out = dm.td_points(df)
    check("td_points", out, n, ["td_point_high", "td_point_low"])
    print(f"      TD points: {int(out['td_point_high'].notna().sum())} highs, "
          f"{int(out['td_point_low'].notna().sum())} lows")

    out = dm.td_lines(df)
    check("td_lines", out, n, ["demand_1", "supply_1"])

    out = dm.td_retracements(df)
    check("td_retracements", out, n, ["up_0_382", "down_0_618"])

    out = dm.demark_trendline(df)
    check("demark_trendline", out, n,
          ["demand_line", "supply_line", "demand_projection"])

    # Moving averages ------------------------------------------------------------
    out = dm.td_moving_average(df)
    check("td_moving_average", out, n, ["td_ma_1", "td_ma_2", "trend_up"])

    # Range projection -------------------------------------------------------------
    out = dm.td_range_projection(df)
    check("td_range_projection", out, n, ["projected_high", "projected_low"])
    assert (out["projected_high"] >= out["projected_low"]).all()

    # TD D-Wave ----------------------------------------------------------------------
    out = dm.td_d_wave(df)
    check("td_d_wave", out, n, ["wave_label", "pivot_name"])
    labelled = out["wave_label"].dropna()
    print(f"      D-Wave: {int(labelled.notna().sum())} bars labelled, "
          f"pivots: {out['pivot_name'].dropna().tolist()}")

    print("\nAll 21 indicators computed successfully.")


if __name__ == "__main__":
    main()
