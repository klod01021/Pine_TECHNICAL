# Anchored VWAP + CVD

Session-anchored (or week / month / year / manual / rolling) **VWAP with σ bands**, plus **cumulative volume delta**, in two languages that share the same formulas:

| File | Role |
|---|---|
| [`python/anchored_vwap_cvd.py`](python/anchored_vwap_cvd.py) | Vectorized engine + unit-tested math |
| [`python/plot_avwap_cvd.py`](python/plot_avwap_cvd.py) | Demo chart |
| [`pine/AnchoredVWAP_CVD.pine`](pine/AnchoredVWAP_CVD.pine) | TradingView Pine Script v6 port |

VWAP lives on the price pane. CVD is a separate histogram pane, colored by that bar's delta. Regular bull/bear divergences (price vs CVD at price pivots) are marked on both.

This is a **bar-level CVD proxy**. TradingView does not expose a tick tape, so delta is estimated from OHLC + volume (CLV by default). Expect pattern-level agreement with a real order-flow platform, not tick-for-tick equality.

## Formulas

**Anchored VWAP** from the first bar of the current window:

```
src     = (H+L+C)/3        # or OHLC4 / HL2 / close
vwap    = Σ(src · vol) / Σ(vol)
variance= max( Σ(src² · vol)/Σ(vol) − vwap², 0 )
stdev   = √variance
bands   = vwap ± k · stdev
```

**Bar delta**

| Method | `delta` |
|---|---|
| **CLV** (default) | `volume * (2*close − high − low) / (high − low)` — zero-range bars use `sign(close − previous close)` |
| Close vs Open | `sign(close − open) * volume` |
| Close vs Close | `sign(close − close[1]) * volume` |
| Pine only: lower-TF | Sum of close-vs-open delta on a lower timeframe |

**CVD** is `Σ(delta)` over the same anchor as VWAP.

**Regular divergence** (confirmed `pivot_right` bars after the swing):

- Bull: price lower-low, CVD higher-low
- Bear: price higher-high, CVD lower-high

Hidden divergences are optional.

## Python

```bash
pip install -r requirements.txt
python3 python/plot_avwap_cvd.py          # writes examples/avwap_cvd_demo.png
python3 -m pytest
```

```python
from anchored_vwap_cvd import VwapCvdConfig, compute_anchored_vwap_cvd

out = compute_anchored_vwap_cvd(
    ohlcv,  # DatetimeIndex + open/high/low/close/volume
    VwapCvdConfig(
        anchor="session",          # session | week | month | year | timestamp | rolling
        price_source="hlc3",
        delta_method="clv",        # clv | close_open | close_close
        stdev_mults=(1.0, 2.0),
        cvd_ema=8,
        pivot_left=3,
        pivot_right=3,
    ),
)
# columns: vwap, stdev, vwap_upper_1, vwap_lower_1, vwap_upper_2, vwap_lower_2,
#          delta, cvd, cvd_smooth, dist_vwap_pct, price_bias, cvd_bias,
#          confluence, bull_div, bear_div, hidden_*_div, new_anchor
```

`anchor="timestamp"` requires `anchor_timestamp=`. `anchor="rolling"` uses `rolling_length` (default 50).

## Pine (TradingView)

1. Open a chart → **Pine Editor** → paste [`pine/AnchoredVWAP_CVD.pine`](pine/AnchoredVWAP_CVD.pine).
2. Add to chart. VWAP + bands overlay price (`force_overlay`); CVD plots in the indicator pane.
3. Set **Anchor** to Session (default), Week, Month, Year, Manual (pick a time), or Rolling.
4. Leave **Use lower-TF delta** off to stay 1:1 with the Python CLV engine. Turn it on only when the lower TF is strictly below the chart TF.

Alerts: CVD regular divergences, close cross of AVWAP, and VWAP/CVD confluence.

## How to read it

- **Price above VWAP + CVD > 0** — buyers in control of the window.
- **Price below VWAP + CVD < 0** — sellers in control.
- **Price at/through VWAP with the opposite CVD** — absorption / exhaustion; wait for a confirmed pivot divergence.
- **±2σ + fading CVD** — stretched vs the volume-weighted mean; fade-or-wait, not a standalone signal.

## Anchor mapping

| Python | Pine |
|---|---|
| `session` | `session.isfirstbar` (exchange session) |
| `week` | `timeframe.change("W")` |
| `month` | `timeframe.change("M")` |
| `year` | `timeframe.change("12M")` |
| `timestamp` | Manual `input.time` |
| `rolling` | `math.sum(..., min(length, bar_index+1))` |
