# Pine_TECHNICAL

Pine Script (v6) technical indicators for TradingView, currently a set of DeMark studies.

| File | Indicator | Pane |
| --- | --- | --- |
| [`demark_9_13.pine`](demark_9_13.pine) | Sequential **and** Combo countdowns, TDST, Risk Levels and Zones, 9-13-9, buy/sell entries | Overlay |
| [`demark_td_sequential.pine`](demark_td_sequential.pine) | TD Sequential only: setup, countdown, TDST, buy/sell entries on a 13 | Overlay |
| [`demarker_oscillator.pine`](demarker_oscillator.pine) | DeMarker (DeM) exhaustion oscillator | Separate |

Start with `demark_9_13.pine`; it is the complete one. The plain TD Sequential
script is kept as a smaller, easier-to-read reference implementation.

## About the licensed DeMARK indicators

The official **DeMARK Indicators** are a commercial, closed-source product from
DeMARK Analytics / Market Studies LLC. On TradingView they are sold as the
`DeMARK 9-13` add-on (a paid Space subscription); the full library of 70-plus
studies is only available on Symbolik, Bloomberg, CQG and DeMARK Prime. That
code cannot be copied, and nothing here is derived from it.

What *is* public is the methodology: Tom DeMark's rules are published in his own
books, principally *The New Science of Technical Analysis* and Jason Perl's
*DeMark Indicators* (Bloomberg Press). The scripts in this repo are an
independent implementation from those published rules. Per its product page, the
paid DeMARK 9-13 study consists of the 9 Setup, the 13 Countdown, TD Setup Trend
(TDST), Perfected Setups, and Risk Levels and Zones, drawn from both the
Sequential and Combo families — `demark_9_13.pine` covers that same ground.

Two honest caveats. First, the licensed product is the reference implementation
and the vendor has publicly said third-party versions contain mistakes; treat
counts from this script as your own work, not as DeMARK output, and if you need
the official numbers, buy the official product. Second, where the published
sources disagree, the script follows the book wording and says so below.

## Installing a script

1. Open a chart on TradingView and click **Pine Editor** at the bottom.
2. Choose **Open → New indicator**, delete the template, paste the `.pine` file.
3. **Save**, name it, then **Add to chart**.
4. Open the indicator settings to change the inputs described below.

Both overlay scripts are `//@version=6` and use only standard built-ins.

## DeMark 9-13 (`demark_9_13.pine`)

### TD Setup

A setup starts with a **TD Price Flip**, the bar where the close crosses back
over the close four bars earlier:

- Bearish flip (starts a **buy setup**): `close[1] > close[5]` and `close < close[4]`
- Bullish flip (starts a **sell setup**): `close[1] < close[5]` and `close > close[4]`

Nine consecutive qualifying bars complete the setup. Contrary to the common
belief that the count stops at nine, DeMark's setup runs until the sequence is
interrupted, so this script keeps counting: 10, 11, and on to 18 and beyond. The
extension is not cosmetic, the recycle rules depend on it.

**Perfection.** A buy setup is perfected when the low of bar 8 or 9 is at or
below the lows of bars 6 and 7, mirrored for a sell setup. If that has not
happened by bar 9 the script keeps watching for a configurable number of bars
and marks the deferred perfection when it arrives.

### TDST

A completed buy setup leaves **TDST resistance** at the highest true high of the
setup; a sell setup leaves **TDST support** at its lowest true low. True high and
true low include the previous close. The level and its line grow while the setup
extends, and the line stops extending once a close breaks through.

### Countdown: Sequential or Combo

Pick the method in the settings.

**Sequential** counts bars, not necessarily consecutive, where `close <= low[2]`
for a buy or `close >= high[2]` for a sell, starting once the setup completes.
Bar 13 must also satisfy the qualifier: its low must be at or below the close of
countdown bar 8. A bar that counts but fails the qualifier prints `+` and the
countdown waits for a bar that satisfies both.

**Combo** is the stricter sibling and starts counting from bar 1 of the setup,
which is why counts appear retroactively on the nine setup bars the moment the
9 completes. Every buy count must satisfy all of:

1. `close <= low[2]`
2. `low < low[1]`
3. `close < close[1]`
4. `close` below the close of the previous countdown bar

Version I applies those rules to all 13 counts. Version II applies them through
count 10 and then only requires successively lower closes for 11, 12 and 13.
The optional **termination count** lets the final count be satisfied by either
the close or the open of the bar.

**Aggressive** mode replaces the close in rule 1 with the bar's own low or high,
so it applies to Sequential and Combo alike.

### Cancellation and recycling

Both are the book's rules, and both can be switched off:

- A completed setup in the opposite direction erases the countdown.
- A bar that posts a **true low above TDST resistance** erases a buy countdown; a
  **true high below TDST support** erases a sell countdown. Note this is a true
  low/high test, not a close test.
- **Qualifier I**: when a new same-direction setup completes and its true range
  is at least as large as the active setup's but less than 1.618 times it, the
  countdown recycles and starts again.
- **Qualifier II**: if the new setup sits entirely inside the previous setup's
  true range, the earlier setup stays active and the countdown survives.
- A setup that stretches to 18 bars while a countdown is developing always
  recycles it, and prints `R`.

### Risk Levels and Zones

DeMark's protective stop. For a buy signal, find the bar with the lowest true
low in the pattern and subtract that bar's true range from its true low; mirror
it for a sell. The countdown version scans every bar of the countdown phase,
numbered or not, which is why it usually sits further away than the setup
version. The script draws the level, optionally shades the zone between the
pattern extreme and the level, and marks the bar that violates it. The default
violation test is intrabar, which is DeMark's own stated preference.

### 9-13-9

After a completed 13, a fresh same-direction setup that begins after the 13 bar,
with no opposing setup in between, prints `9-13-9`. It is a second, usually
better, opportunity to fade the same trend.

### Where you would buy and sell

The counts say a trend is exhausted; they do not say where to trade. These
markers apply DeMark's own entry rules to the counts and put a `BUY` or `SELL`
label, with the price, on the bar where the trade would be taken.

**Timing.** DeMark gives two ways into a completed 13:

- *Aggressive*: buy the close of the thirteen.
- *Conservative* (the default here): wait for the first close beyond the close
  four bars earlier, which is a price flip in your direction. It gives up some
  of the entry price but avoids being caught by a recycle. If no flip arrives
  within the confirmation window, the signal is dropped; if price takes out the
  risk level while you are still waiting, the signal is dropped too.

**Which signals.** Thirteens by default. Setup nines can be traded as well but
they are filtered, because most completed setups are not worth trading. Perl's
conditions are used: the setup must be perfected, no bar inside it may have
closed beyond TDST, and bar nine must close within a set distance of TDST.

**Where you get out.** The stop is the risk level described above. The target is
TDST, which is where DeMark expects a countertrend move to run to. A TDST level
that price has already passed is dropped rather than used, so a trade can be
carried on the stop alone. The trade closes with an `x` if the stop goes and a
square if the target is reached, and an opposite entry signal reverses the
position.

**Reward to risk.** DeMark's filter is to skip the trade unless the distance to
TDST is at least 1.5 times the distance to the risk level. That is the default
and it removes a lot of signals; set it to 0 to see them all.

The panel in the corner shows the current position, entry, stop, target, and the
open result in R multiples.

Two things this is not. It is an indicator, not a `strategy()`, so there is no
backtest report, no commission and no slippage; entries and exits are marked at
the close of the bar that triggers them. And one position is tracked at a time,
so a second signal in the same direction is ignored rather than added to.

### Inputs

| Group | Input | Default |
| --- | --- | --- |
| Method | Countdown method: Sequential, Combo V1, Combo V2 | Sequential |
| Method | Aggressive countdown | off |
| TD Setup | Show setup counts / start plotting at / show counts past 9 | on / 1 / on |
| TD Setup | Mark perfected setups, bars allowed for deferred perfection | on, 8 |
| TD Countdown | Show counts, bar 13 qualifier, termination count | on, on, off |
| TD Countdown | Cancel on opposite setup, cancel on TDST | on, on |
| TD Countdown | Recycle rule: DeMark qualifiers, Always, Never | DeMark qualifiers |
| Risk Levels | On setup 9 / on countdown 13 / shade zone | off / on / on |
| Risk Levels | Violated by: Intrabar or Close | Intrabar |
| Entries | Show buy / sell entries | on |
| Entries | Trade these signals: Countdown 13, Setup 9, Both | Countdown 13 |
| Entries | Entry timing: Aggressive or Conservative | Conservative |
| Entries | Bars to wait for confirmation | 12 |
| Entries | Filter setup 9 entries, TDST proximity (ATR) | on, 1.0 |
| Entries | Minimum reward to risk | 1.5 |
| Entries | Draw stop and target, show trade panel | on, on |
| TDST | Show levels, line style, width | on, dashed, 1 |
| Appearance | Buy and sell colours, label offset (ATR multiple) | teal, red, 0.4 |

### Chart legend

Everything to do with buying sits **below** the bars in teal, everything to do
with selling sits **above** them in red, and the marks are stacked in rows:
setup counts closest to the bar, countdown counts further out, entry labels
furthest out.

| Mark | Where | Meaning |
| --- | --- | --- |
| `1` … `9` | Row 1, dimmed | Setup count. Bar 9 is drawn in full colour |
| `10` … `18` | Row 1, dimmed | The setup running past nine. 18 is drawn in full colour |
| Small triangle | Against the bar | The setup completed on this bar |
| Diamond | Against the bar | The setup is perfected. May print after bar 9 if perfection was deferred |
| `1` … `12` | Row 2, dimmed | Countdown count. With Combo, counts 1 to 9 appear retroactively on the setup bars |
| `+` | Row 2 | The bar counted but failed the bar 13 qualifier, so the 13 is deferred |
| `13` in a solid tag | Against the bar | Countdown complete. This is the exhaustion signal |
| `9-13-9` in a solid tag | Against the bar | A fresh qualified setup after a 13, a second chance at the same trade |
| `R` | Row 2 | The countdown was recycled and starts again from zero |
| Faded `x` | Against the bar | A risk level was violated |
| Dashed horizontal line | At the level | TDST. Red above is resistance from a buy setup, teal below is support from a sell setup. Stops extending once a close breaks it |
| Solid horizontal line | At the level | The risk level of a signal. Teal for a buy, red for a sell |
| Shaded band | Under or over the extreme | The risk zone, between the pattern extreme and the risk level |
| `BUY 123.45` | Row 3 | Long entry, at that price, on that bar |
| `SELL 123.45` | Row 3 | Short entry |
| Dotted red line | At the level | The stop of the trade that is currently open |
| Dotted green line | At the level | The target of the trade that is currently open |
| Red `x` | At the stop price | The open trade was stopped out here |
| Green square | At the target price | The open trade reached TDST here |
| Corner panel | Top right | Position, entry, stop, target, and open result in R multiples |

Two `x` marks mean different things, and the difference is where they sit. A
faded teal or red `x` hugging the bar is bookkeeping: a risk level was taken
out. A solid red `x` floating at the stop price closes a trade that the script
had marked as open.

A buy 9 or 13 on its own says selling pressure is exhausted; it is not an order,
which is exactly why the entry rules add a confirmation step. Confluence
matters too: a 13 landing on TDST, on a prior swing, or on an oversold DeMarker
reading is worth far more than one in mid-air.

## TD Sequential (`demark_td_sequential.pine`)

The same Sequential setup, countdown, perfection and TDST logic in a much
shorter script, without Combo, extended setups, the recycle qualifiers or
9-13-9. Its optional TDST cancellation uses a close through the level rather
than the book's true low/high test. Useful if you want to read the method in a
couple of hundred lines, or want a plain 9-13 chart.

It marks buy and sell entries too, but only from a completed 13, with the same
aggressive or conservative timing, the risk level as the stop and TDST as the
target. Setup nine entries, the reward-to-risk filter and the trade panel are
only in `demark_9_13.pine`.

The legend above applies here as well, minus the marks for the features it does
not have: no `R`, no `9-13-9`, no counts past nine, and no risk level lines,
risk zones or faded `x` marks, since risk levels are only drawn in the full
script. The stop of an open trade is still drawn as a dotted red line.

## DeMarker (`demarker_oscillator.pine`)

The companion oscillator, bounded between 0 and 1:

```
DeMax = high > high[1] ? high - high[1] : 0
DeMin = low  < low[1]  ? low[1] - low   : 0
DeM   = MA(DeMax, n) / (MA(DeMax, n) + MA(DeMin, n))
```

Above 0.7 the advance is stretched, below 0.3 the decline is. The signal is
counter-trend, so the most reliable use is as a filter: take setup and countdown
signals more seriously at an extreme, and treat the move back inside the band as
the trigger.

| Input | Default | Notes |
| --- | --- | --- |
| Length | 14 | |
| Averaging | SMA | SMA, EMA, RMA or WMA |
| Overbought / Oversold | 0.7 / 0.3 | |
| Signal smoothing | 0 | 0 turns the signal line off |
| Shade overbought / oversold | on | Background highlight |

In its own pane: the thick line is DeMarker itself, turning red in the
overbought zone, teal in the oversold zone and grey in between. The thin orange
line is the smoothing, if you switch it on. The dashed lines are the two levels
with the neutral band shaded between them, the dotted line is the 0.5 midline,
and the background lights up while the reading is at an extreme. A small
triangle at the top or bottom of the pane marks the bar where the oscillator
came back inside the band, which is the usual trigger.

## Alerts

Every script exposes alert conditions through **Create alert → Condition →
indicator name**: buy and sell entries, stops and targets, setup 9s, perfected
setups, deferred and completed 13s, recycles, 9-13-9 counts, risk level
violations and TDST breaks for the DeMark scripts, and the level crosses for
DeMarker.

## Limitations

- TradingView keeps only the last 500 labels per indicator, so counts eventually
  drop off deep history. Raise "Start plotting counts at" to stretch the budget.
- Counts are evaluated on the close. On an unclosed bar the last count can flip
  as price moves; only closed bars are final.
- Sources disagree on Combo Version II. This script follows DeMark's own wording,
  where counts 11 to 13 need only successively lower or higher closes. Some
  write-ups instead apply the plain Sequential rule to those counts.
- Where DeMark describes discretionary judgement, the script has to pick a rule.
  The recycle qualifiers are the clearest case: Qualifier II is implemented as
  full containment of the new setup inside the previous setup's true range.
- The entry markers are an indicator drawing labels, not a backtest. Entries and
  exits print at the close of the triggering bar, with no costs modelled, and
  only one position is tracked at a time.

## Disclaimer

For research and education. Not financial advice, no guarantee of
profitability, and not affiliated with DeMARK Analytics or Market Studies LLC.
Test any signal on your own instruments and timeframes before risking money.
