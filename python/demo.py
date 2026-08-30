"""Run the ADX / Squeeze Filter over a CSV or synthetic sample data.

Usage:
    python3 demo.py
    python3 demo.py path/to/ohlc.csv
"""

from __future__ import annotations

import sys

import pandas as pd

import adx_squeeze_filter as asf
from self_test import make_sample_data

REGIME_NAME = {
    asf.REGIME_COMPRESSION: "compression",
    asf.REGIME_FIRE: "fire",
    asf.REGIME_DEVELOPING: "developing",
    asf.REGIME_EXPANSION: "expansion",
}


def main() -> None:
    if len(sys.argv) > 1:
        df = asf.load_ohlc_csv(sys.argv[1])
        print(f"Loaded {len(df)} bars from {sys.argv[1]}")
    else:
        df = make_sample_data()
        print(f"Synthetic sample: {len(df)} bars")

    out = asf.adx_squeeze_filter(df)
    last = out.dropna(subset=["adx", "momentum"]).iloc[-12:].copy()
    last["regime"] = last["regime"].map(lambda v: REGIME_NAME.get(int(v), str(v)))
    cols = [
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
    ]
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)
    print()
    print(last[cols].to_string(float_format=lambda x: f"{x:8.3f}"))

    ready = out.dropna(subset=["adx"])
    print()
    print(
        f"in_squeeze bars : {int(ready['in_squeeze'].sum())}\n"
        f"releases        : {int(ready['squeeze_release'].sum())}\n"
        f"long fires      : {int(ready['long_fire'].sum())}\n"
        f"short fires     : {int(ready['short_fire'].sum())}\n"
        f"allow_long bars : {int(ready['allow_long'].sum())}\n"
        f"allow_short bars: {int(ready['allow_short'].sum())}"
    )


if __name__ == "__main__":
    main()
