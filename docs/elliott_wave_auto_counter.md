# Elliott Wave Auto-Counter - reference

Source: [`indicators/elliott_wave_auto_counter.pine`](../indicators/elliott_wave_auto_counter.pine) (Pine Script v6, overlay indicator).

## How the count is produced

1. **Swing skeleton.** A pivot high or low is recorded once `depth` bars on both sides fail to exceed it. A new pivot in the opposite direction is only accepted if the move is at least the noise filter (ATR multiple or percent), otherwise price is still on the same swing. Two pivots in the same direction collapse into the more extreme one, so the skeleton always alternates high, low, high, low.

2. **Rule tests.** Every candidate is normalised to `q = direction x price`, which makes a bear structure the mirror of a bull one so one set of comparisons covers both. A five wave impulse is rejected outright if it breaks a hard rule:

   | Rule | Test |
   | --- | --- |
   | R1 | Wave 2 never retraces more than 100% of wave 1 |
   | R2 | Wave 3 is never the shortest of waves 1, 3 and 5 |
   | R3 | Wave 4 never enters wave 1 territory, unless diagonals are allowed |

   Wave 3 must also exceed the end of wave 1, and wave 5 must exceed the end of wave 3 unless truncation is allowed.

3. **Guideline scoring.** Surviving candidates are scored on how closely each leg matches the usual Fibonacci relationships: wave 2 retracing 0.382-0.786 of wave 1, wave 3 extending 1.0-4.236, wave 4 retracing 0.236-0.618 of wave 3, wave 5 relating 0.382-1.618 to wave 1, plus the guideline of alternation, which rewards a shallow wave 2 pairing with a deep wave 4 or the reverse. Each leg gets a Gaussian proximity score to the nearest ideal ratio, and the mean becomes the **fib fit** shown in the panel. Counts that need a diagonal are multiplied by 0.80 and truncated fifths by 0.85, so an unusual structure must clearly beat a textbook one to win.

4. **Choosing the count.** The scanner ranks every valid complete impulse by `fib fit - 0.015 x (swings since it ended)`. The recency term is small on purpose: a clean older count is not displaced by a poor newer one that merely ends further to the right. Whatever follows the winning impulse is labelled as a correction, and if that correction is already over, the impulse building on top of it is labelled too. With no complete impulse anywhere, the script falls back to the longest partial impulse ending on the newest swing, then to a plain A-B-C, and finally shows "No valid count" rather than forcing labels onto noise.

5. **Two degrees.** The whole process runs twice: once at your pivot depth, and once at `depth x lower degree size` for the sub-waves, drawn smaller and faded.

## Inputs

### Swing detection

| Input | Default | Notes |
| --- | --- | --- |
| Pivot depth | 20 | The master sensitivity control. Larger returns fewer, larger waves. |
| Noise filter | ATR | `ATR`, `Percent` or `None`. Minimum size for a counter-swing to start a new wave. |
| Minimum swing = ATR x | 2.0 | Used when the filter is ATR. Raise it on noisy intraday charts. |
| ATR length | 14 | |
| Minimum swing (%) | 3.0 | Used when the filter is Percent. Better than ATR for crypto and long histories. |
| Include the live, unconfirmed swing | on | Adds the running high/low since the last confirmed pivot so the wave in progress is visible, marked `?` and dashed. |
| Swings to scan for a count | 25 | How far back the scanner looks. Higher finds older structures at some cost in speed. |

### Elliott rules

| Input | Default | Notes |
| --- | --- | --- |
| Allow diagonals | on | Permits wave 4 to overlap wave 1. Turn off for strict impulses only; the count then simply reports fewer complete impulses. |
| Allow a truncated wave 5 | on | Permits a fifth wave that fails to exceed wave 3. |
| Minimum Fibonacci fit to accept | 0 | Raise to roughly 40-60 to see only well proportioned counts. |

### Display and targets

Notation can be set per degree: `1 2 3 4 5 / A B C`, `(1) (2) (3) / (a) (b) (c)`, roman upper or lower, or circled numerals, which lets you approximate standard degree conventions. Colours, label sizes, the swing skeleton, the panel, the projection length and the alert behaviour are all switchable.

## The panel

| Row | Meaning |
| --- | --- |
| Header | Structure direction; teal for a bull impulse, maroon for a bear one, orange while corrective. The right cell is the fib fit. |
| Count | Named structure, for example `Zigzag complete` or `New impulse up, wave 3 in progress`. |
| Wave in progress | Which wave the script expects next. |
| Rules R1 R2 R3 | Per-rule pass, fail, `diag` when wave 4 overlap is being allowed as a diagonal, or `-` when the wave needed for the test does not exist yet. |
| Target zone | Span of the projected Fibonacci levels. |
| Invalidation | Price that breaks the current count. |
| Lower degree | The sub-degree count. |
| Swings held | Pivots in the skeleton and the depth in use. |

## Invalidation levels

The level depends on the wave in progress, and is exactly the price that would break the count:

| In progress | Invalidation |
| --- | --- |
| Wave 2 | Start of wave 1 |
| Wave 3 | End of wave 2 |
| Wave 4 | End of wave 1 (the overlap rule) |
| Wave 5 | End of wave 4 |
| After a complete impulse | End of wave 5 |
| Wave B or C | Start of wave A |

## Repainting, stated plainly

A swing cannot be known until `depth` bars have passed, so the most recent labels change as bars close. The script marks the unconfirmed swing with `?` and a dashed leg, and drives alerts from the confirmed count only. Historical labels are stable once their swing is confirmed, but they were not visible at the time they print, so a visual backtest across settled history will always look better than trading it live did.

## Keeping the logic honest

`tools/wave_logic_reference.py` is a line-for-line Python port of the counting logic, and `tools/test_wave_logic.py` drives it with synthetic impulses, corrections, triangles, deliberate rule violations, and 600 random walks that assert the swing and label invariants. Run `python3 tools/test_wave_logic.py` after any change to a rule, and mirror the change in both files.
