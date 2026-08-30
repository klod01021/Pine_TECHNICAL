# ADX / Squeeze Filter — Python

Wilder's ADX combined with a TTM-style squeeze (Bollinger Bands inside
Keltner Channels). Every function takes an OHLC DataFrame (`open`, `high`,
`low`, `close`) and returns a DataFrame indexed the same way, so the output
can be compared bar-for-bar against the Pine Script v6 script in
[`/pine`](../pine).

## Install

```bash
pip install -r requirements.txt
```

Run commands from this `python/` directory (so the `adx_squeeze_filter`
package imports).

## Quick start

```python
import adx_squeeze_filter as asf

df = asf.load_ohlc_csv("AAPL_daily.csv")     # TradingView export works
out = asf.adx_squeeze_filter(df)

# Bars where the squeeze just released in the trend's direction:
print(out[out["long_fire"] | out["short_fire"]])
```

Run the self-test (shape, bounds, coil-then-trend sample):

```bash
python3 self_test.py
```

Run the hand-verified math tests (RMA seed, linreg, squeeze on/off, fire):

```bash
python3 test_correctness.py
```

Run the demo over synthetic data, or your own CSV:

```bash
python3 demo.py
python3 demo.py path/to/ohlc.csv
```

## What it measures

| Piece | Role |
|---|---|
| **ADX / +DI / -DI** | Trend *strength* and *direction* (Wilder). ADX below the coil threshold (20) is "no trend"; ADX at or above the trend threshold (25) is a confirmed trend. |
| **TTM squeeze** | Volatility *compression*: squeeze is on when the Bollinger Band sits entirely inside the Keltner Channel. Momentum is a linear regression of price vs the Donchian/SMA midpoint (LazyBear / Carter). |
| **Combined filter** | Default mode `both`: you are in squeeze only when TTM is on **and** ADX is weak. That is the actual ADX / Squeeze Filter. |

### Regime codes (`regime` column)

| Code | Name | Meaning |
|---|---|---|
| 1 | compression | Combined squeeze is on — stand aside or fade |
| 2 | fire | Squeeze just released this bar |
| 3 | developing | Squeeze off, ADX not yet at the trend threshold |
| 4 | expansion | Squeeze off and ADX is strong — trend-following allowed |

### Filter modes (`mode`)

| Mode | In squeeze when |
|---|---|
| `both` (default) | TTM squeeze on **and** ADX < coil |
| `either` | TTM squeeze on **or** ADX < coil |
| `ttm` | Bollinger inside Keltner only |
| `adx` | ADX < coil only |

### Signal columns

- `long_fire` / `short_fire` — squeeze release, directional (+DI vs -DI and momentum sign), optionally requiring ADX to be rising.
- `allow_long` / `allow_short` — not in squeeze, ADX strong, direction agrees. Use these as a trend-following gate.

## Catalogue

| Function | Output |
|---|---|
| `directional_movement` | `plus_di`, `minus_di`, `adx` |
| `ttm_squeeze` | BB/KC bands, `squeeze_on` / `squeeze_off` / `no_squeeze`, `momentum` |
| `adx_squeeze_filter` | All of the above plus filter/regime/fire columns |
| `load_ohlc_csv` | Load a TradingView-style CSV |
