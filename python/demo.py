"""Demo: run every DeMark indicator over your own OHLC data.

Usage
-----
    python3 demo.py path/to/ohlc.csv

The CSV needs open, high, low, close columns (a TradingView chart export
works out of the box). Without a file argument the demo falls back to
built-in synthetic data.
"""

from __future__ import annotations

import sys

import pandas as pd

import demark_indicators as dm


def main() -> None:
    if len(sys.argv) > 1:
        df = dm.load_ohlc_csv(sys.argv[1])
        print(f"Loaded {len(df)} bars from {sys.argv[1]}")
    else:
        from self_test import make_sample_data

        df = make_sample_data()
        print(f"Using built-in synthetic data ({len(df)} bars)")

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 50)

    print("\n--- DeMarker (last 5 bars) ---")
    print(dm.demarker(df).tail())

    print("\n--- TD Sequential (bars with a 9 or a 13) ---")
    seq = dm.td_countdown(df)
    hot = seq[
        (seq["buy_setup"] == 9)
        | (seq["sell_setup"] == 9)
        | seq["buy_signal"]
        | seq["sell_signal"]
    ]
    print(hot.tail(10))

    print("\n--- TDST levels (last 5 bars) ---")
    print(dm.td_setup_trend(df)[["tdst_support", "tdst_resistance"]].tail())

    print("\n--- TD D-Wave pivots ---")
    wave = dm.td_d_wave(df)
    pivots = wave[["pivot_price", "pivot_name"]].dropna()
    print(pivots)


if __name__ == "__main__":
    main()
