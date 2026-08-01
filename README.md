# Pine_TECHNICAL

Pine Script (v6) technical indicators for TradingView.

| File | Indicator | Pane |
| --- | --- | --- |
| [`demark_td_sequential.pine`](demark_td_sequential.pine) | DeMark TD Sequential: TD Setup, TD Countdown, TDST levels | Overlay |
| [`demarker_oscillator.pine`](demarker_oscillator.pine) | DeMarker (DeM) exhaustion oscillator | Separate |

## Installing a script

1. Open a chart on TradingView and click **Pine Editor** at the bottom of the screen.
2. Choose **Open → New indicator**, delete the template and paste the contents of the `.pine` file.
3. Click **Save**, give it a name, then **Add to chart**.
4. Open the indicator settings to change the inputs described below.

Both scripts are written for `//@version=6`. They only use standard built-ins, so
they also compile on v5 if you change the version comment on the first line.

## DeMark TD Sequential

Tom DeMark's trend exhaustion model. It counts how long a move has run rather
than how fast, and flags the point where a trend is statistically likely to
stall. The script draws three things.

### TD Setup (counts 1 to 9)

A setup starts with a **TD Price Flip**, the bar where the close crosses back
over the close of four bars earlier:

- Bearish flip (starts a **buy setup**): `close[1] > close[5]` and `close < close[4]`
- Bullish flip (starts a **sell setup**): `close[1] < close[5]` and `close > close[4]`

From there each bar must keep closing below (buy setup) or above (sell setup)
the close four bars earlier. Nine consecutive qualifying bars complete the
setup and print a triangle. One failing bar resets the count to zero, and a new
setup can only begin after a fresh price flip.

**Perfection.** A completed buy setup is perfected when the low of bar 8 or 9
is at or below the lows of bars 6 and 7 (mirrored for a sell setup). If that
has not happened by bar 9, the script keeps watching for a set number of bars
and prints the diamond later, which is DeMark's deferred perfection. An
unperfected 9 usually needs one more push before it turns.

### TDST levels

When a buy setup completes, the highest true high of its nine bars becomes
**TDST resistance**; a completed sell setup leaves **TDST support** at the
lowest true low. True high and true low include the previous close, as DeMark
defines them. The line extends to the right until a close breaks through it. A
break is the market telling you the exhaustion signal failed and the trend is
continuing.

### TD Countdown (counts 1 to 13)

A completed setup arms the countdown, which looks for the actual exhaustion
point rather than the end of the momentum run:

- Buy countdown: `close <= low[2]`
- Sell countdown: `close >= high[2]`

These bars do **not** need to be consecutive, so a countdown can take a long
time to finish. The 9th setup bar can be countdown bar 1 if it qualifies.

**Bar 13 qualifier.** The low of buy countdown bar 13 must be at or below the
close of countdown bar 8 (mirrored for a sell countdown). A bar that satisfies
the count but fails the qualifier is deferred and marked with a `+`; the
countdown waits for the next bar that satisfies both.

**Cancellation.** A completed setup in the opposite direction always cancels a
running countdown. Two further behaviours are configurable: recycling the
countdown when a new setup completes in the same direction, and cancelling it
when price closes through the TDST level.

### Inputs

| Group | Input | Default | Notes |
| --- | --- | --- | --- |
| TD Setup | Show setup counts | on | |
| TD Setup | Start plotting counts at | 1 | Set to 7 or 8 for a cleaner chart |
| TD Setup | Mark perfected setups | on | Diamond marker |
| TD Setup | Bars allowed for deferred perfection | 8 | 0 disables deferral |
| TD Countdown | Show countdown counts | on | |
| TD Countdown | Aggressive countdown | off | Uses `low <= low[2]` instead of the close |
| TD Countdown | Apply the bar 13 qualifier | on | |
| TD Countdown | Cancel countdown on a TDST break | off | |
| TD Countdown | Recycle countdown on a new same-direction setup | on | |
| TDST Levels | Show TDST support / resistance, line style, width | on, dashed, 1 | |
| Appearance | Buy / sell colour, label offset (ATR multiple) | teal, red, 0.4 | |

### Reading the chart

- Setup counts sit next to the bars, countdown counts one row further out.
- Triangle = completed 9, diamond = perfected setup, `13` label = completed countdown.
- A buy 9 or 13 is a signal that selling pressure is exhausted, not a mechanical
  buy order. The usual confirmation is a close back above the close of the
  signal bar or a bullish price flip immediately afterwards.
- Confluence matters: a 13 that lands on TDST support, a prior swing level or an
  oversold DeMarker reading is worth far more than one in mid-air.

### Limitations

- TradingView keeps only the last 500 labels per indicator, so counts eventually
  disappear from deep history. Raise "Start plotting counts at" to stretch that
  budget further back.
- DeMark's recycle rule compares the size of the new setup with the previous
  one. The script uses the simpler "any new same-direction setup restarts the
  countdown" interpretation, which you can switch off.
- Counts are evaluated on the close. On an unclosed bar the last count can flip
  as price moves; only closed bars are final.

## DeMarker (DeM)

The companion oscillator, bounded between 0 and 1:

```
DeMax = high > high[1] ? high - high[1] : 0
DeMin = low  < low[1]  ? low[1] - low   : 0
DeM   = MA(DeMax, n) / (MA(DeMax, n) + MA(DeMin, n))
```

Above 0.7 the advance is stretched, below 0.3 the decline is. Because the
signal is counter-trend, the most reliable use is as a filter: take TD Setup and
Countdown signals more seriously when DeMarker is at an extreme, and treat the
move back inside the band as the trigger.

| Input | Default | Notes |
| --- | --- | --- |
| Length | 14 | |
| Averaging | SMA | SMA, EMA, RMA or WMA |
| Overbought / Oversold | 0.7 / 0.3 | |
| Signal smoothing | 0 | 0 turns the signal line off |
| Shade overbought / oversold | on | Background highlight |

## Alerts

Both scripts expose alert conditions through **Create alert → Condition →
indicator name**: setup 9s, perfected setups, countdown 13s and TDST breaks for
TD Sequential, and the overbought/oversold crosses for DeMarker.

## Disclaimer

These scripts are for research and education. They are not financial advice and
carry no guarantee of profitability. Test any signal on your own instruments and
timeframes before risking money.
