"""Self-test for the ADX / Squeeze Filter.

Generates a deterministic synthetic OHLC series (coil then expansion) and
checks shapes, bounds, and regime consistency. Run with:

    python3 self_test.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import adx_squeeze_filter as asf


def make_sample_data(n: int = 400, seed: int = 42) -> pd.DataFrame:
    """Coil (tight closes, wide wicks) then a trending expansion."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    coil_n = n // 2

    close = np.empty(n)
    close[:coil_n] = 100.0 + rng.normal(0, 0.08, coil_n)
    trend = np.linspace(0, 25, n - coil_n)
    close[coil_n:] = close[coil_n - 1] + trend + rng.normal(0, 0.35, n - coil_n)

    open_ = np.roll(close, 1)
    open_[0] = close[0]

    wick = np.empty(n)
    wick[:coil_n] = rng.uniform(1.2, 2.4, coil_n)
    wick[coil_n:] = rng.uniform(0.15, 0.55, n - coil_n)

    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - wick

    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close},
        index=idx,
    )


def check(name: str, out: pd.DataFrame, n: int, required: list[str]) -> None:
    assert isinstance(out, pd.DataFrame), f"{name}: not a DataFrame"
    assert len(out) == n, f"{name}: expected {n} rows, got {len(out)}"
    for col in required:
        assert col in out.columns, f"{name}: missing column {col}"
    print(f"  ok  {name:<28} cols={len(out.columns)}")


def main() -> None:
    df = make_sample_data()
    n = len(df)
    print(f"Sample data: {n} bars\nRunning indicators...\n")

    dmi = asf.directional_movement(df)
    check("directional_movement", dmi, n, ["plus_di", "minus_di", "adx"])
    adx = dmi["adx"].dropna()
    assert len(adx) > 0, "ADX produced no values"
    assert adx.between(0, 100).all(), "ADX out of [0, 100]"
    assert dmi["plus_di"].dropna().between(0, 100).all(), "+DI out of [0, 100]"
    assert dmi["minus_di"].dropna().between(0, 100).all(), "-DI out of [0, 100]"

    sqz = asf.ttm_squeeze(df)
    check(
        "ttm_squeeze",
        sqz,
        n,
        [
            "upper_bb",
            "lower_bb",
            "upper_kc",
            "lower_kc",
            "squeeze_on",
            "squeeze_off",
            "no_squeeze",
            "momentum",
        ],
    )
    ready_sqz = sqz["upper_bb"].notna() & sqz["upper_kc"].notna()
    on = sqz.loc[ready_sqz, "squeeze_on"]
    off = sqz.loc[ready_sqz, "squeeze_off"]
    none = sqz.loc[ready_sqz, "no_squeeze"]
    assert (on.astype(int) + off.astype(int) + none.astype(int) == 1).all(), (
        "squeeze states are not mutually exclusive"
    )
    inside = (sqz["lower_bb"] > sqz["lower_kc"]) & (sqz["upper_bb"] < sqz["upper_kc"])
    assert (sqz.loc[ready_sqz, "squeeze_on"] == inside.loc[ready_sqz]).all()

    out = asf.adx_squeeze_filter(df)
    check(
        "adx_squeeze_filter",
        out,
        n,
        [
            "adx",
            "plus_di",
            "minus_di",
            "momentum",
            "in_squeeze",
            "squeeze_release",
            "long_fire",
            "short_fire",
            "allow_long",
            "allow_short",
            "regime",
        ],
    )

    fires = out["long_fire"] | out["short_fire"]
    assert (fires <= out["squeeze_release"]).all(), "fire without squeeze release"
    both_ways = out["long_fire"] & out["short_fire"]
    assert not both_ways.any(), "long and short fire on the same bar"
    both_allow = out["allow_long"] & out["allow_short"]
    assert not both_allow.any(), "allow_long and allow_short on the same bar"
    assert not (out["allow_long"] & out["in_squeeze"]).any()
    assert not (out["allow_short"] & out["in_squeeze"]).any()

    regimes = out["regime"].dropna()
    assert regimes.isin([1, 2, 3, 4]).all(), "unexpected regime code"

    # Coil half should produce some squeeze-on bars; trend half should not
    # stay coiled the whole time.
    coil_on = int(out["squeeze_on"].iloc[: n // 2].sum())
    trend_on = int(out["squeeze_on"].iloc[n // 2 :].sum())
    assert coil_on > 0, "expected TTM squeeze during the coil half"
    assert coil_on > trend_on, "coil half should squeeze more than the trend half"

    trend_adx = out["adx"].iloc[-40:].mean()
    coil_adx = out["adx"].iloc[40 : n // 2].mean()
    assert trend_adx > coil_adx, (
        f"ADX should rise in the trend half ({trend_adx:.2f} vs {coil_adx:.2f})"
    )

    for mode in asf.VALID_MODES:
        mode_out = asf.adx_squeeze_filter(df, mode=mode)
        assert len(mode_out) == n
        assert mode_out["in_squeeze"].notna().all()

    print("\nAll self-tests passed.")


if __name__ == "__main__":
    main()
