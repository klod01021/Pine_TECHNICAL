# Pine_TECHNICAL

TradingView Pine Script indicators.

| Indicator | File | What it does |
| --- | --- | --- |
| Elliott Wave Auto-Counter v2 | [`indicators/elliott_wave_auto_counter_v2.pine`](indicators/elliott_wave_auto_counter_v2.pine) | Labels rule-validated Elliott impulses and corrections at two degrees, draws a Fibonacci grid for the wave in progress with its target zone, projects when that wave should end, and marks the price that would invalidate the count. |

---

## Deploy on TradingView in 5 steps

1. Open any chart on [tradingview.com](https://www.tradingview.com) and click **Pine Editor** in the panel at the bottom of the screen.
2. Click **Open → New indicator** so you get a blank script (this leaves your other scripts untouched).
3. Select everything in the editor (`Ctrl/Cmd + A`) and paste the full contents of
   [`indicators/elliott_wave_auto_counter_v2.pine`](indicators/elliott_wave_auto_counter_v2.pine) over it.
   Use the **Raw** view on GitHub and copy from there so nothing is reformatted.
4. Click **Save** (`Ctrl/Cmd + S`), give it a name such as `Elliott Wave Auto-Counter v2`, then click **Add to chart**.
5. Open the indicator's **Settings → Inputs** and set **Pivot depth** for your timeframe (see the table below). That single input controls almost everything.

The script compiles to a standard indicator, so it works on the free plan and on every symbol and timeframe. To reuse it later, it will be waiting under the **Indicators → My scripts** menu.

### First thing to set: pivot depth

Depth is how many bars on each side of a high or low must fail to exceed it before it counts as a swing. Everything else follows from it.

Depth is counted in **bars, not time**, so it has to suit how many bars your chart is showing. A rough guide is 2-5% of the bars on screen; the numbers below assume a few hundred bars of history.

| Chart | Start with |
| --- | --- |
| 1m - 15m | depth 8-12 |
| 1H - 4H | depth 15-25 |
| Daily | depth 20-30 |
| Weekly | depth 10-15 |
| Monthly | depth 5-8 |

The higher timeframes want *smaller* numbers, which surprises people. A monthly chart of 30 years is only about 360 bars, so depth 20 asks for 20 months of quiet either side of every swing and finds almost nothing in a long trend. If your monthly chart shows only a handful of waves, that is the reason.

If you see too many small waves, raise the depth or raise the **Minimum swing = ATR x** filter. If whole legs of the move are being ignored, lower them.

---

## Reading the chart

- **Numbers 1-5 in the impulse colour** are a five wave move that passes all three hard Elliott rules.
- **Letters A-B-C in the corrective colour** are the correction that followed it, and A-B-C-D-E when the shape is a contracting triangle. Only the part of the correction that actually validates gets a letter: if the structure stops making sense after A, you see `A` and nothing more, and the panel says the rest is unresolved. Empty space is the honest answer there.
- **A label ending in `?` on a dashed leg** sits on the swing that has not confirmed yet. It is the script's best guess about the wave in progress and it will move.
- **The Fibonacci grid** is drawn the way the drawing tool draws it: a level line per ratio, anchored to the swing being measured and running out to the projection, with each level labelled by ratio and price. A retracing wave (2, 4, B) is measured back across the wave before it; an extending wave (3, 5, C) is projected forward from where it began.
- **The bright band** is the primary target zone, the range the wave most often finishes in: 0.5-0.786 for a wave 2 or B, 1.618-2.618 for a wave 3, 0.236-0.5 for a wave 4, 0.618-1.618 for a wave 5, and the 0.382-0.618 golden zone for the correction after a completed impulse. The panel shows its two prices.
- **The horizontal extent** of the projection is the Fibonacci *time* estimate, so the drawing says where the wave should end and roughly when. The dashed vertical line is the middle estimate, labelled with how many bars away it is; when a wave outruns its projection it reads `due now` instead.
- **The dashed red line** is the invalidation: the price that would break the count being shown, which is where a stop belongs if you are trading the count.
- **The panel** in the top right names the structure, the wave in progress, the Fibonacci fit, and which of the three rules pass.

Full input-by-input reference: [`docs/elliott_wave_auto_counter_v2.md`](docs/elliott_wave_auto_counter_v2.md).

---

## When the chart looks wrong

**Labels sit in old history with the recent rally bare.** The count only ever describes the present: a structure with more than eight swings after it is not offered as a count at all. If labels still cluster in one region and the rest of the chart is empty, the swing detection is finding almost no pivots in the quiet part - lower **Pivot depth**, and on a monthly or weekly chart lower it a lot (see the table above).

**Two sets of labels, or a panel with text written over itself.** You have two copies of the indicator on the chart. Right click the chart, choose **Objects tree**, and remove the older one; or open each indicator's title on the chart and delete the duplicate.

**Almost nothing is labelled.** Check **Swings held** in the panel. Below about ten swings there is not enough structure to count, so lower the depth or the noise filter until the panel shows twenty or more.

## Setting up alerts

The script ships five alert conditions plus a dynamic one:

- *Wave count changed*, *Wave 3 may be starting*, *Wave 5 may be starting*, *Impulse complete*, *Correction complete*.

Right click the chart → **Add alert** → set **Condition** to `EW Auto-Counter v2` and pick the one you want. To receive the count itself in the alert text, choose the condition **Any alert() function call** instead; the message then names the structure and its confidence.

Alerts are driven by the confirmed count only, never by the provisional `?` swing, so they do not fire and then vanish.

---

## What this can and cannot do

Elliott Wave counting is subjective. Two analysts label the same chart differently, and so will this script when you change the pivot depth. What it does honestly:

- It never shows a count that breaks a hard rule (wave 2 beyond the start of wave 1, wave 3 shortest of 1/3/5, wave 4 overlapping wave 1 outside a diagonal).
- A correction can never be labelled through the top or bottom it is correcting. If price makes a new extreme past the end of wave 5, that is not an A-B-C and the letters are withheld rather than stretched over it. If you *want* textbook expanded flats, where wave B does end past the start of wave A, turn on **Allow expanded flats**.
- A correction also has to hold the origin of the impulse it corrects. A move that retraces more than 100% is not a correction in a new direction, it *is* the new direction, so it is counted as an impulse: 1-2-3-4-5 straight off the top, no letters.
- When a move could be read either as A-B-C or as the first three waves of a new impulse, two things decide it. The lower degree: a leg that subdivides into five sub-waves is impulsive, one that subdivides into three is corrective. And velocity: a correction should not cover ground faster than the impulse it is undoing, so a first leg travelling further per bar than the impulse averaged is read as a trend rather than a pause. The subdivision test uses the lower degree even when its labels are switched off, so **Lower degree size** changes your counts either way.
- It prefers textbook structures, and only falls back to a diagonal or a truncation when nothing cleaner fits.
- It tells you how well the count matches the Fibonacci guidelines instead of implying certainty.

What it cannot do:

- **It recounts as the market develops.** A swing is only confirmed `depth` bars after it printed, so labels near the right edge change. This is inherent to wave counting, not a bug, but it does mean you must not backtest it by looking at settled history and assuming those labels were visible at the time.
- It counts two degrees, not the full nine, and it does not enumerate alternate counts.

Treat the output as a structured, rule-checked hypothesis. Use the invalidation level.

---

## Development

Pine cannot run outside TradingView, so the counting logic is mirrored in Python and tested against synthetic wave structures and 600 randomized price paths:

```bash
cd tools && python3 test_wave_logic.py
```

If you change a rule in the `.pine` file, change it in `tools/wave_logic_reference.py` too and extend `tools/test_wave_logic.py`.
