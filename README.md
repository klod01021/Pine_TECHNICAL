# Pine_TECHNICAL

TradingView Pine Script indicators.

| Indicator | File | What it does |
| --- | --- | --- |
| Elliott Wave Auto-Counter | [`indicators/elliott_wave_auto_counter.pine`](indicators/elliott_wave_auto_counter.pine) | Detects swings, labels rule-validated Elliott impulses and corrections, projects Fibonacci targets and draws the invalidation level. |

---

## Deploy on TradingView in 5 steps

1. Open any chart on [tradingview.com](https://www.tradingview.com) and click **Pine Editor** in the panel at the bottom of the screen.
2. Click **Open → New indicator** so you get a blank script (this leaves your other scripts untouched).
3. Select everything in the editor (`Ctrl/Cmd + A`) and paste the full contents of
   [`indicators/elliott_wave_auto_counter.pine`](indicators/elliott_wave_auto_counter.pine) over it.
   Use the **Raw** view on GitHub and copy from there so nothing is reformatted.
4. Click **Save** (`Ctrl/Cmd + S`), give it a name such as `Elliott Wave Auto-Counter`, then click **Add to chart**.
5. Open the indicator's **Settings → Inputs** and set **Pivot depth** for your timeframe (see the table below). That single input controls almost everything.

The script compiles to a standard indicator, so it works on the free plan and on every symbol and timeframe. To reuse it later, it will be waiting under the **Indicators → My scripts** menu.

### First thing to set: pivot depth

Depth is how many bars on each side of a high or low must fail to exceed it before it counts as a swing. Everything else follows from it.

| You are trading | Chart | Start with |
| --- | --- | --- |
| Scalps | 1m - 15m | depth 8-12 |
| Swings | 1H - 4H | depth 15-25 |
| Positions | Daily | depth 20-30 |
| Macro structure | Weekly | depth 40+ |

If you see too many small waves, raise the depth or raise the **Minimum swing = ATR x** filter. If whole legs of the move are being ignored, lower them.

---

## Reading the chart

- **Numbers 1-5 in the impulse colour** are a five wave move that passes all three hard Elliott rules.
- **Letters A-B-C in the corrective colour** are the correction that followed it, and A-B-C-D-E when the shape is a contracting triangle. Only the part of the correction that actually validates gets a letter: if the structure stops making sense after A, you see `A` and nothing more, and the panel says the rest is unresolved. Empty space is the honest answer there.
- **A label ending in `?` on a dashed leg** sits on the swing that has not confirmed yet. It is the script's best guess about the wave in progress and it will move.
- **Dotted lines to the right** are the Fibonacci targets for the wave that is currently unfolding, with the shaded box marking the whole target zone.
- **The dashed red line** is the invalidation: the price that would break the count being shown, which is where a stop belongs if you are trading the count.
- **The panel** in the top right names the structure, the wave in progress, the Fibonacci fit, and which of the three rules pass.

Full input-by-input reference: [`docs/elliott_wave_auto_counter.md`](docs/elliott_wave_auto_counter.md).

---

## Setting up alerts

The script ships five alert conditions plus a dynamic one:

- *Wave count changed*, *Wave 3 may be starting*, *Wave 5 may be starting*, *Impulse complete*, *Correction complete*.

Right click the chart → **Add alert** → set **Condition** to `EW Auto-Counter` and pick the one you want. To receive the count itself in the alert text, choose the condition **Any alert() function call** instead; the message then names the structure and its confidence.

Alerts are driven by the confirmed count only, never by the provisional `?` swing, so they do not fire and then vanish.

---

## What this can and cannot do

Elliott Wave counting is subjective. Two analysts label the same chart differently, and so will this script when you change the pivot depth. What it does honestly:

- It never shows a count that breaks a hard rule (wave 2 beyond the start of wave 1, wave 3 shortest of 1/3/5, wave 4 overlapping wave 1 outside a diagonal).
- A correction can never be labelled through the top or bottom it is correcting. If price makes a new extreme past the end of wave 5, that is not an A-B-C and the letters are withheld rather than stretched over it. If you *want* textbook expanded flats, where wave B does end past the start of wave A, turn on **Allow expanded flats**.
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
