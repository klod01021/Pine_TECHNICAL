# Pine_TECHNICAL

Python and Pine Script v6 implementations of technical indicators.

## ADX / Squeeze Filter

Combines **Wilder's ADX** (trend strength) with a **TTM squeeze**
(Bollinger Bands inside Keltner Channels) into one regime filter.

- **Compression** — squeeze is on and ADX is below the coil threshold. Volatility is coiled; there is no trend.
- **Fire** — the combined squeeze just released and ADX is turning up. Direction comes from squeeze momentum and +DI vs −DI.
- **Expansion** — squeeze is off and ADX is above the trend threshold. Trend-following is allowed.

The Python library is the reference implementation. The Pine script is a
bar-for-bar port of the same formulas.

| | |
|---|---|
| Python | [`python/adx_squeeze_filter`](python/adx_squeeze_filter) |
| Pine v6 | [`pine/adx_squeeze_filter.pine`](pine/adx_squeeze_filter.pine) |
| Docs | [`python/README.md`](python/README.md) |

### Run the Python version

```bash
cd python
pip install -r requirements.txt
python3 self_test.py
python3 test_correctness.py
python3 demo.py
```

### Use the Pine version

1. Open TradingView → Pine Editor.
2. Paste the contents of `pine/adx_squeeze_filter.pine`.
3. Add to chart. The pane defaults to ADX / +DI / −DI; switch **Pane view** to `Momentum` for the TTM histogram. Bollinger and Keltner bands plot on price.

### Defaults

| Input | Value |
|---|---|
| +DI / ADX length | 14 / 14 |
| Coil / trend thresholds | 20 / 25 |
| Bollinger | 20, 2.0 |
| Keltner | 20, 1.5, true range |
| Squeeze definition | `both` (TTM on **and** ADX < coil) |
