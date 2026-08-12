# DeMark Indicators — Python Library

A from-scratch pandas implementation of Tom DeMark's indicator library.
Each function takes an OHLC DataFrame (`open`, `high`, `low`, `close`)
and returns a DataFrame of indicator values indexed the same way, so the
output can be compared bar-for-bar against the Pine Script v6 versions
in [`/pine`](../pine).

## Install

```bash
pip install -r requirements.txt
```

## Quick start

```python
import demark_indicators as dm

df = dm.load_ohlc_csv("AAPL_daily.csv")     # TradingView export works
seq = dm.td_countdown(df)
print(seq.tail())

# Bars that printed a buy 13:
print(seq[seq["buy_signal"]])
```

Run the full self-test (validates all 20 indicators on synthetic data):

```bash
python3 self_test.py
```

Run the demo over your own CSV:

```bash
python3 demo.py path/to/ohlc.csv
```

## Indicator catalogue

### Oscillators (`demark_indicators.oscillators`)

| Function | Indicator | Output |
|---|---|---|
| `demarker` | DeMarker (DeM), 0–100 | `dem` |
| `demarker_ii` | DeMarker II | `demarker_ii` |
| `td_pressure_ratio` | TD Pressure Ratio | `pressure_ratio` |
| `td_range_expansion_index` | TD Range Expansion Index (TDREI) | `rei` |
| `td_poq` | TD Price Oscillator Qualifier | `poq` |
| `td_alignment` | TD Alignment Oscillator | `alignment`, `signal` |
| `td_roc` | TD Rate of Change | `roc`, `signal` |
| `td_oscillator` | TD Oscillator | `td_oscillator` |

### TD Sequential family (`demark_indicators.sequential`)

| Function | Indicator | Key outputs |
|---|---|---|
| `td_setup` | TD Setup 1–9 | `buy_setup`, `sell_setup` |
| `td_countdown` | Classic Countdown 1–13 | `buy_countdown`, `sell_countdown`, `*_signal` |
| `td_combo` | TD Combo Countdown | `buy_combo`, `sell_combo`, `*_signal` |
| `td_sequential_ultimate` | Sequential + qualifiers | `buy_aggressive`, `buy_conservative`, ... |

### Levels and trend (`demark_indicators.levels`)

| Function | Indicator | Key outputs |
|---|---|---|
| `td_setup_trend` | TDST support/resistance | `tdst_support`, `tdst_resistance` |
| `td_points` | TD Point highs/lows | `td_point_high`, `td_point_low` |
| `td_lines` | TD Supply/Demand lines 1–3 | `demand_1..3`, `supply_1..3` |
| `td_retracements` | TD Relative Retracement | `up_0_382`, `down_0_618`, ... |
| `demark_trendline` | Qualified trendlines + projections | `demand_line`, `supply_projection`, ... |

### Other

| Function | Indicator | Key outputs |
|---|---|---|
| `td_moving_average` | TD MA I & II | `td_ma_1`, `td_ma_2`, `trend_up` |
| `td_range_projection` | Next-bar high/low projection | `projected_high`, `projected_low` |
| `td_d_wave` | TD D-Wave wave count | `wave_label`, `pivot_name` |

## Notes

- All moving averages match Pine's `ta.sma` / `ta.ema` / `ta.rma`
  conventions so values line up with the Pine scripts.
- The sequential counts iterate bar by bar, mirroring Pine's execution
  model, so counts match TradingView exactly given the same data.
- These implementations follow the published DeMark rules (DeMark,
  *The New Science of Technical Analysis* and *New Market Timing
  Techniques*). The commercial DeMARK™ product adds proprietary tweaks;
  treat these as the textbook versions.
