# Pine_TECHNICAL

TradingView Pine Script indicators.

## DeMark TD Lines (`demark_td_lines.pine`)

Objective trendlines from Tom DeMark's *The New Science of Technical Analysis*.
Instead of hand-drawing support and resistance, the script anchors lines to
**TD Points** and scores breakouts with mechanical **qualifiers**.

### How it works

1. **TD Point (level N)** — a swing high with N lower highs on each side, or a
   swing low with N higher lows on each side. Level 1 (default) is the classic
   three-bar pivot.
2. **TD Supply Line** — connects the two most recent same-level TD Point highs
   (resistance, drawn right to left).
3. **TD Demand Line** — connects the two most recent same-level TD Point lows
   (support).
4. **Breakout** — a close through the active line. That alone is not a trade;
   DeMark requires at least one of four momentum qualifiers.
5. **Price projection** — on a qualified break, the largest gap from the line
   to an extreme between the two TD Points is projected beyond the breakout.

### Chart legend

| Mark | Meaning |
| --- | --- |
| `H` / `L` | Confirmed TD Point high / low |
| Red ray | Active TD Supply Line (resistance) |
| Teal ray | Active TD Demand Line (support) |
| `Q↑` / `Q↓` | Qualified break of Supply / Demand |
| `DQ↑ fade` / `DQ↓ fade` | Disqualified break — fade candidate |
| Dotted `Proj` line | Price objective after a qualified break |
| Corner panel | Live Supply / Demand values and last projection |

### Qualifiers

Only one needs to be true for the break to count as qualified:

| # | Upside (Supply) | Downside (Demand) |
| --- | --- | --- |
| Q1 | Close > prior true high | Close < prior true low |
| Q2 | Open already above the line (gap) | Open already below the line |
| Q3 | Prior close + buying pressure still below the line | Prior close − selling pressure still above the line |
| Q4 | Exceptional thrust through the prior two true highs, with the line inside the prior bar | Mirror for true lows |

If none fire, the break is **disqualified**. With the default setting the script
labels those as fade candidates rather than continuation trades.

### Inputs

| Group | Input | Default |
| --- | --- | --- |
| TD Points | TD Point level (1–9) | 1 |
| TD Points | Mark TD Points on the chart | on |
| TD Lines | Show Supply / Demand, keep previous lines faded | on / on / off |
| Breakouts | Mark qualified / disqualified, treat DQ as fade | on / on |
| Targets | Draw projection, projection length | on, 15 bars |
| Appearance | Colours, marker offset, line width | red / teal |

### Alerts

Create alert → Condition → **DeMark TD Lines**:

- Qualified Supply / Demand break
- Disqualified Supply / Demand break
- Fade Supply / Demand break

### Limitations

- TD Points are only confirmed after `level` bars have printed past the pivot, so
  the newest point always lags by that many bars.
- TradingView caps labels and lines; older markers eventually drop off.
- Qualifier wording varies slightly across secondary sources; this script follows
  the pressure / thrust definitions commonly attributed to DeMark's Chapter 1.
- Educational indicator only — not affiliated with DeMARK Analytics.

### Disclaimer

For research and education. Not financial advice.
