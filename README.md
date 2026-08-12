# DeMark Indicators — Python + Pine Script v6

A complete library of Tom DeMark's technical indicators, implemented twice:

- **[`python/`](python/README.md)** — a pandas library you can run on your own
  data, backtest against, and extend.
- **[`pine/`](pine)** — the same indicators as self-contained Pine Script **v6**
  scripts you can paste straight into TradingView.

Every indicator is calculated the same way in both languages so the values
line up bar-for-bar given the same OHLC data.

## Indicator catalogue (21)

### Oscillators

| # | Indicator | Python | Pine script |
|---|---|---|---|
| 1 | DeMarker (DeM) | `demarker()` | `demarker_oscillator.pine` |
| 2 | DeMarker II | `demarker_ii()` | `demarker_ii.pine` |
| 3 | TD Pressure Ratio | `td_pressure_ratio()` | `td_pressure_ratio.pine` |
| 4 | TD Range Expansion Index (TDREI) | `td_range_expansion_index()` | `td_range_expansion_index.pine` |
| 5 | TD POQ (Price Oscillator Qualifier) | `td_poq()` | `td_poq.pine` |
| 6 | TD Alignment Oscillator | `td_alignment()` | `td_alignment.pine` |
| 7 | TD Rate of Change | `td_roc()` | `td_roc.pine` |
| 8 | TD Oscillator | `td_oscillator()` | `td_oscillator.pine` |

### TD Sequential family

| # | Indicator | Python | Pine script |
|---|---|---|---|
| 9 | TD Setup (1–9) | `td_setup()` | `td_sequential.pine` |
| 10 | TD Countdown (1–13) | `td_countdown()` | `td_sequential.pine` |
| 11 | TD Combo Countdown | `td_combo()` | `td_combo.pine` |
| 12 | TD Sequential Ultimate (qualifiers) | `td_sequential_ultimate()` | `td_sequential_ultimate.pine` |

### Levels, lines and trend

| # | Indicator | Python | Pine script |
|---|---|---|---|
| 13 | TDST (TD Setup Trend) | `td_setup_trend()` | `td_setup_trend_tdst.pine` |
| 13b | TD Risk Level (stop for a 13) | `td_risk_level()` | `demark_v1_signals.pine` |
| 14 | TD Points | `td_points()` | `td_points.pine` |
| 15 | TD Lines (Supply/Demand 1–3) | `td_lines()` | `td_lines.pine` |
| 16 | TD Moving Average I / II | `td_moving_average()` | `td_moving_average.pine` |
| 17 | TD Range Projection | `td_range_projection()` | `td_range_projection.pine` |
| 18 | TD Retracements (Arc / Relative) | `td_retracements()` | `td_retracements.pine` |
| 19 | DeMark Trendline + projections | `demark_trendline()` | `demark_trendline.pine` |

### Wave counting

| # | Indicator | Python | Pine script |
|---|---|---|---|
| 20 | TD D-Wave | `td_d_wave()` | `td_d_wave.pine` |

## Start here: v1, v2, v3

Three scripts, grouped by **what you use together** rather than by indicator
family. Each answers one question in the trading workflow.

| Script | Question it answers | Contains |
|---|---|---|
| **`pine/demark_v1_signals.pine`**<br>DeMark v1 — Signals | *Is a reversal due, and where am I wrong?* | TD Setup (+ perfection), TD Countdown (+ 13-vs-8 deferral, cancellations), TD Combo, Sequential/Combo confluence, **TDST** invalidation levels, **TD Risk Level** stop |
| **`pine/demark_v2_trend_targets.pine`**<br>DeMark v2 — Trend & Targets | *Where is price going, and where do I exit?* | TD Lines (1–3), DeMark Trendline, TD Points, TD Moving Average I/II, TD Retracements, TD Range Projection, TD D-Wave |
| **`pine/demark_v3_momentum.pine`**<br>DeMark v3 — Momentum | *Does momentum confirm or diverge?* | All 8 oscillators: DeMarker, DeMarker II, Pressure Ratio, TD REI, POQ, Alignment, ROC, TD Oscillator |

v1 and v2 sit on the candles; v3 opens in its own pane. Together they cover
all 21 indicators, enforced by `tools/check_suite_coverage.py`.

### Why this grouping

The signal and its invalidation belong together: a TD Countdown is *cancelled*
by a TDST violation, and a completed 13 is meaningless without the risk level
that says where it failed. Splitting those across scripts meant you could not
act on a signal from one script alone. v2 holds the tools that answer what
happens next, and v3 is momentum, which belongs in a separate pane.

### Presets

Each script opens with a **Preset** dropdown so it is usable immediately:

- **Essential** — the core signal only
- **Standard** — the default; adds the levels most people want
- **Everything** — every tool in that script
- **Custom** — the individual checkboxes take over

A typical setup is v1 on Standard, v2 on Essential or Standard, and v3 on
Standard, then reaching for Custom once you know what you want.

## Keeping the chart readable

Start with the **Preset** dropdown rather than the individual checkboxes.
Beyond that, two settings matter most if the chart looks crowded or the
candles get squashed:

- **Project lines forward (bars)** and **Stop projecting past this % from
  price** (v2, "Display" group). Trendlines are *not* extended to infinity —
  a steep line taken to the right edge forces TradingView's auto-scale to
  include huge prices and compresses the candles into a thin band. The
  projection is capped at a number of bars and stops early if the line would
  travel further than the given percentage from current price.
- **TD Point left/right bars.** DeMark's strict TD Point is 1 bar either
  side, which on an intraday chart marks nearly every bar. The default is 3;
  set both to 1 for the textbook definition.

If you previously added one of these scripts to a chart, remove and re-add it
after updating — TradingView keeps your old input values, so you would not
pick up the new defaults.

## Use in TradingView

1. Open the [Pine Editor](https://www.tradingview.com/pine-editor/) on
   TradingView.
2. Open any file from [`pine/`](pine) (the three `all_*.pine` suites are the
   easiest starting point), copy its contents, paste into the editor, and
   click **Add to chart**.
3. Each script is `//@version=6` and self-contained — no libraries needed.

## Use in Python

```bash
cd python
pip install -r requirements.txt
python3 self_test.py          # validates all 21 indicators
python3 demo.py AAPL.csv      # run over your own TradingView CSV export
```

```python
import demark_indicators as dm

df = dm.load_ohlc_csv("AAPL.csv")
seq = dm.td_countdown(df)
print(seq[seq["buy_signal"]])   # bars that printed a buy 13
```

See [`python/README.md`](python/README.md) for the full API.

## Verification

```bash
python3 tools/lint_pine.py             # static check of all 22 Pine v6 scripts
python3 tools/check_suite_coverage.py  # every indicator present in its suite
python3 python/test_correctness.py     # 22 hand-verified DeMark rule tests
cd python && python3 self_test.py      # all 21 indicators over synthetic data
```

`tools/lint_pine.py` catches reserved words used as identifiers, wrong
version annotations, unbalanced brackets, bad indentation, v5-era function
names, stateful `ta.*` calls trapped inside conditional blocks, and `ta.*`
length arguments that are function parameters (`series int` where a
`simple int` is required). It is not a compiler — TradingView has no offline
one — but it prevents the breakage that is detectable by inspection.

## Rules implemented

The counts follow DeMark's published specification, including the details
that are easy to get wrong:

- **Setup** resets on *any* bar failing the strict comparison, including an
  equal close.
- **Setup perfection**: bar 8 or 9's low at or below the lows of bars 6 and 7
  (mirrored for sells).
- **TDST**: a completed **buy** setup defines **resistance** at the highest
  high of its nine bars; a completed **sell** setup defines **support** at
  the lowest low. (Not the other way round — this is a common error.)
- **13-vs-8 deferral**: the 13th countdown bar only qualifies if its low is
  at or below the close of countdown bar 8 (buy), or its high at or above it
  (sell). Otherwise the 13 is deferred, not cancelled.
- **Countdown cancellation** on an opposite-direction setup or a TDST
  violation.
- **TD Combo**: four conditions for counts 1–10, then the
  prior-counted-close rule for 11–13.
- **TD REI**: DeMark's two-filter formula referencing lows 5/6 and closes 7/8
  bars back, with ±45 thresholds and the six-bar duration test.

## Notes

- The implementations follow the published rules in DeMark's *The New
  Science of Technical Analysis* and *New Market Timing Techniques*. The
  commercial DeMARK™ product applies additional proprietary tweaks — treat
  these as the textbook versions.
- The Sequential counts (`td_setup`, `td_countdown`, `td_combo`) iterate
  bar by bar in both languages, so counts match TradingView exactly given
  identical data.
