# Pine_TECHNICAL

TradingView Pine Script indicators.

| Indicator | File | What it does |
| --- | --- | --- |
| Wyckoff Method | [`indicators/wyckoff_method.pine`](indicators/wyckoff_method.pine) | Finds the trading range that still describes the present, labels the classic Wyckoff events (PS, SC, AR, ST, Spring, SOS, LPS / PSY, BC, UTAD, SOW, LPSY), names the phase (A–E), draws the creek and the ice, and projects cause-and-effect targets with an invalidation. |

---

## Deploy on TradingView in 5 steps

1. Open any chart on [tradingview.com](https://www.tradingview.com) and click **Pine Editor** in the panel at the bottom of the screen.
2. Click **Open → New indicator** so you get a blank script (this leaves your other scripts untouched).
3. Select everything in the editor (`Ctrl/Cmd + A`) and paste the full contents of
   [`indicators/wyckoff_method.pine`](indicators/wyckoff_method.pine) over it.
   Use the **Raw** view on GitHub and copy from there so nothing is reformatted.
4. Click **Save** (`Ctrl/Cmd + S`), give it a name such as `Wyckoff Method`, then click **Add to chart**.
5. Open the indicator's **Settings → Inputs** and set **Pivot depth** for your timeframe (see the table below). That single input controls almost everything.

The script compiles to a standard overlay indicator, so it works on the free plan and on every symbol and timeframe. To reuse it later, it will be waiting under the **Indicators → My scripts** menu.

### First thing to set: pivot depth

Depth is how many bars on each side of a high or low must fail to exceed it before it counts as a swing. The campaign, the events and the range box all follow from those swings.

Depth is counted in **bars, not time**, so it has to suit how many bars your chart is showing. A rough guide is 2-5% of the bars on screen; the numbers below assume a few hundred bars of history.

| Chart | Start with |
| --- | --- |
| 1m - 15m | depth 5-8 |
| 1H - 4H | depth 8-12 |
| Daily | depth 8-12 |
| Weekly | depth 5-8 |
| Monthly | depth 4-6 |

If you see too many tiny ranges, raise the depth or raise **Minimum approach = ATR x**. If a range you can see by eye is being ignored, lower them.

Volume confirmation (absorption, climax, and the "volume drying on the test" confidence bonus) needs a real volume feed. On FX and some indices the panel will say `no volume` and the structure still runs on price alone.

---

## Reading the chart

- **The shaded box** is the trading range. Teal is accumulation (after a decline); maroon is distribution (after a rally). The letter in the corner is the Wyckoff phase, A through E.
- **Creek** is the dashed orange line at the top of the range (resistance that accumulation has to jump). **Ice** is the dashed blue line at the bottom (support that distribution has to break).
- **Event labels** sit on the swings that define the campaign:

| Accumulation | Distribution | Meaning |
| --- | --- | --- |
| PS | PSY | Preliminary support / supply, the halt before the climax |
| SC | BC | Selling / buying climax, the end of the approach |
| AR | AR | Automatic rally / reaction, which sets the other side of the range |
| ST | ST | Secondary test of the climax, usually on lighter volume |
| Spring | UTAD | False break of ice / creek that recovers back inside (Phase C) |
| SOS | SOW | Sign of strength / weakness — a held break of the creek / ice (Phase D) |
| LPS / BU | LPSY | Last point of support / supply, or backup to the creek |

- **A label ending in `?`** sits on the swing that has not confirmed yet. It is the script's best guess about the event in progress and it will move.
- **The 1x and 1.618x lines** are the vertical count: the height of the range, projected from the creek (markup) or the ice (markdown).
- **The horiz count line** is a bar-count approximation of the point-and-figure horizontal count: `cause bars × ATR / divisor`.
- **The dashed red line** is the invalidation: the spring low (accumulation) or the UTAD high (distribution), or the ice / creek when those events have not printed yet.
- **Diamonds** above bars are absorption (high volume, narrow spread). **Crosses** are climax bars (high volume, wide spread).
- **The panel** in the top right names the campaign, lists the events, and reports the range, the targets, the invalidation, the path of least resistance, and whether the latest bar is absorption, climax, or neutral.

Full input-by-input reference: [`docs/wyckoff_method.md`](docs/wyckoff_method.md).

---

## When the chart looks wrong

**Labels sit on an old range while the recent action is a trend.** A campaign with more than ten swings after it is not offered, so the script should not strand itself in history. If it still does, the recent swings are being read as a new Phase A on the last climax — raise **Minimum approach = ATR x** so a pullback inside a trend is not treated as a campaign.

**Almost nothing is labelled.** Check **Swings held** in the panel. Below about eight swings there is not enough structure. Lower the depth, or lower the approach filter, until the panel shows a campaign you can see by eye.

**A V-reversal is being boxed as a range.** The automatic rally is capped at 95% of the approach by default, which is what stops a straight reversal from becoming SC-AR. Raise **Maximum AR as a fraction of the approach** if you want those labelled.

**Two boxes, or a panel with text written over itself.** You have two copies of the indicator on the chart. Right click the chart, choose **Objects tree**, and remove the older one.

---

## Setting up alerts

The script ships five alert conditions plus a dynamic one:

- *Campaign changed*, *Spring*, *Sign of Strength / jump across the creek*, *UTAD*, *Sign of Weakness / ice break*.

Right click the chart → **Add alert** → set **Condition** to `Wyckoff Method` and pick the one you want. To receive the campaign title in the alert text, choose the condition **Any alert() function call** instead.

Alerts are driven by the confirmed campaign only, never by the provisional `?` swing, so they do not fire and then vanish.

---

## What this can and cannot do

Wyckoff analysis is discretionary. Two analysts will box the same chart differently, and so will this script when you change the pivot depth. What it does honestly:

- It only starts a campaign after a real approach (a decline into a selling climax, or a rally into a buying climax) of at least `ATR × Minimum approach`.
- An automatic rally that retraces the whole approach is rejected as a V-reversal, not a range.
- A spring / UTAD has to pierce the range *and recover*. A break that holds is SOS / SOW, or a failed campaign, not a Phase C test.
- The campaign has to still describe the present. An old range with a long trend after it is discarded rather than labelled.
- Volume is used as confirmation (climax effort, drying volume on the test) when the symbol has it, and ignored when it does not.

What it cannot do:

- **It recounts as the market develops.** A swing is only confirmed `depth` bars after it printed, so labels near the right edge change. This is inherent to range labelling, not a bug, but it does mean you must not backtest it by looking at settled history and assuming those labels were visible at the time.
- It does not count nested ranges inside a larger campaign, and it does not implement a full point-and-figure count. The horizontal target is an ATR approximation.
- It will not tell you whether the Composite Operator is "done". Phase B is noisy; wait for Phase C or D.

Treat the output as a structured, rule-checked hypothesis. Use the invalidation level.

---

## Development

Pine cannot run outside TradingView, so the campaign logic is mirrored in Python and tested against synthetic accumulation and distribution paths, effort-vs-result bars, and 400 randomized price paths:

```bash
python3 tools/test_wyckoff_logic.py
python3 tools/lint_pine.py
```

If you change a rule in the `.pine` file, change it in `tools/wyckoff_logic_reference.py` too and extend `tools/test_wyckoff_logic.py`.
