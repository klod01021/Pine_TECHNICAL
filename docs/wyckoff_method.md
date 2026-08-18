# Wyckoff Method indicator

Overlay indicator that boxes the trading range still describing the present, labels the classic Wyckoff events, names the phase, and projects where the subsequent markup or markdown should reach.

The counting logic is mirrored in [`tools/wyckoff_logic_reference.py`](../tools/wyckoff_logic_reference.py) and tested by [`tools/test_wyckoff_logic.py`](../tools/test_wyckoff_logic.py). Pine cannot run outside TradingView, so that Python port is how the rules stay honest.

## How it works

1. **Swing skeleton.** A pivot is recorded once `depth` bars on both sides fail to exceed it, with an ATR or percent filter so small wiggles do not become events. The volume of the pivot bar is stored on the swing and used later as a confidence bonus.

2. **Approach.** A campaign only starts after a real move into a climax: a decline of at least `ATR × Minimum approach` into a swing low (selling climax) or a rally of the same size into a swing high (buying climax). Quiet pullbacks inside a trend are not labelled.

3. **Automatic rally / reaction.** The next swing the other way has to retrace a fraction of that approach (default 30–95%). Too small and the climax did not stop the trend; too large and it is a V-reversal rather than a range. That swing sets the **creek** (resistance) in accumulation and the **ice** (support) in distribution.

4. **Walking the range.** Subsequent swings are classified against the box:
   - A hold in the climax's end of the range is a **secondary test (ST)**.
   - A pierce of the ice that recovers back above it is a **spring**. A pierce of the creek that fails back below it is a **UTAD**. Either is Phase C.
   - A held break of the creek is a **sign of strength (SOS)** / jump across the creek. A held break of the ice is a **sign of weakness (SOW)**. Either is Phase D.
   - The pullback after SOS is **LPS** or **BU** (backup to the creek). The rally after SOW is **LPSY**.
   - A low after SOS that holds above the creek is Phase E (markup). A high after SOW that holds below the ice is Phase E (markdown).

5. **Choosing the campaign.** A range with more than ten swings after it is history, not the present, so it is not offered. Among what remains the scanner ranks every valid campaign by `confidence - 1.5 × (swings since it ended) + 2 × (event count)`. The recency term is small on purpose: a clean older range is not displaced by a poor newer one that merely ends further to the right.

6. **Cause and effect.** The height of the range is projected 1× and 1.618× from the creek (accumulation) or the ice (distribution). A horizontal count approximates the point-and-figure count as `cause bars × ATR / divisor`. Invalidation is the spring low, the UTAD high, or the ice / creek when those have not printed.

7. **Effort vs result.** Independently of the campaign, each bar is compared with a moving average of volume and of bar range. High volume with a narrow spread is **absorption**; high volume with a wide spread is a **climax**. On symbols with no volume the structure still runs and the panel says `no volume`.

## Inputs

### Swing detection

| Input | Default | Notes |
| --- | --- | --- |
| Pivot depth | 8 | The master sensitivity control. Larger returns fewer, larger ranges. |
| Noise filter | ATR | `ATR`, `Percent` or `None`. |
| Minimum swing = ATR x | 1.0 | Used when the filter is ATR. |
| ATR length | 14 | Also used for the approach filter and the horizontal count. |
| Minimum swing (%) | 2.0 | Used when the filter is Percent. |
| Include the live, unconfirmed swing | on | Adds the running high/low since the last confirmed pivot, marked `?`. |
| Swings to scan for a campaign | 25 | How far back the scanner looks. |

### Wyckoff rules

| Input | Default | Notes |
| --- | --- | --- |
| Minimum approach = ATR x | 1.0 | Decline into SC / rally into BC must be at least this. Keep it at or below the minimum swing. Raise it to stop trend pullbacks being boxed. |
| Minimum AR as a fraction of the approach | 0.25 | Automatic rally / reaction has to retrace at least this. |
| Maximum AR as a fraction of the approach | 1.10 | Stops a V-reversal being labelled as a range. |
| Secondary test zone | 0.45 | ST must finish in this fraction of the range nearest the climax. |
| Spring / UTAD max penetration | 0.40 | A false break may pierce by up to this fraction of the range height, provided it recovers. |
| Breakout tolerance | 0.02 | How far through the creek / ice a held break must go to count as SOS / SOW. |
| Minimum confidence to accept | 0 | Raise to see only well confirmed campaigns. |

### Effort vs result

| Input | Default | Notes |
| --- | --- | --- |
| Volume / spread average length | 20 | |
| Absorption: volume multiple | 1.6 | Bar volume versus the average. |
| Absorption: spread multiple (max) | 0.70 | Bar range versus the average; below this, with high volume, is absorption. |
| Climax: volume multiple | 2.0 | |
| Climax: spread multiple (min) | 1.5 | |

### Display and targets

Colours, label size, the swing skeleton, the range box, the event labels, the effort/result marks, bar colouring, the panel, the projection length, the horizontal-count divisor and the alert behaviour are all switchable.

## The panel

| Row | Meaning |
| --- | --- |
| Header | Campaign direction; teal for accumulation, maroon for distribution. The right cell is the confidence. |
| Campaign | Named structure, for example `Accumulation, Phase C — the test`. |
| Events | The labels in order, with `?` on the unconfirmed swing. |
| Range | Ice and creek prices. |
| Cause / effect | Bars spent in the range, then the 1× and 1.618× vertical counts. |
| Invalidation | Price that breaks the current reading. |
| Path of least resistance | Up after accumulation, down after distribution. |
| Effort vs result | Absorption, climax, neutral, or `no volume`. |
| Swings held | Pivots in the skeleton and the depth in use. |

## Invalidation levels

| Campaign | Invalidation |
| --- | --- |
| Accumulation with a spring | The spring low |
| Accumulation without a spring | The ice (selling climax) |
| Distribution with a UTAD | The UTAD high |
| Distribution without a UTAD | The creek (buying climax) |

## Repainting, stated plainly

A swing cannot be known until `depth` bars have passed, so the most recent labels change as bars close. The script marks the unconfirmed swing with `?` and a dashed box edge, and drives alerts from the confirmed campaign only. Historical labels are stable once their swing is confirmed, but they were not visible at the time they print, so a visual backtest across settled history will always look better than trading it live did.

## Keeping the logic honest

`tools/wyckoff_logic_reference.py` is a line-for-line Python port of the campaign logic, and `tools/test_wyckoff_logic.py` drives it with synthetic accumulation and distribution paths, springs that must recover, UTAD that must fail back, V-reversals that must be rejected, effort-vs-result bars, and 400 random walks that assert the event-index invariants. Run:

```bash
python3 tools/test_wyckoff_logic.py
python3 tools/lint_pine.py
```

If a rule changes in the Pine source, change it in the Python port too and extend the test.

## Version history

### v1

First release: swing detection, accumulation and distribution campaigns, event labels, phases A–E, creek and ice, cause-and-effect targets, effort vs result, panel and alerts.
