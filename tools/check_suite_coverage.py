"""Verify the v1/v2/v3 scripts cover every DeMark indicator.

The three scripts are grouped by workflow rather than by indicator family:

    v1 Signals         what to trade      (setup, countdown, combo, TDST, risk)
    v2 Trend & Targets where it goes      (lines, MAs, retracements, D-Wave)
    v3 Momentum        does it confirm    (the eight oscillators)

Each indicator is mapped to the evidence that must appear in its script:
plot/plotshape titles for anything drawn as a series, and source patterns for
tools drawn with line.new / label.new.

Run:

    python3 tools/check_suite_coverage.py
"""

from __future__ import annotations

import pathlib
import re
import sys

PINE_DIR = pathlib.Path(__file__).resolve().parent.parent / "pine"

CALL_RE = re.compile(r"\b(?:plot|plotshape|plotchar)\s*\(")


def plot_titles(source: str) -> set[str]:
    """Extract the title of every plot/plotshape/plotchar call.

    The first argument can itself contain commas and parentheses (for example
    ``ta.crossover(ma1, ma2)``), so the call is scanned with balanced-paren
    matching rather than a flat regex, and the first string literal inside it
    is taken as the title.
    """
    titles: set[str] = set()
    for match in CALL_RE.finditer(source):
        i = match.end()
        depth = 1
        in_str = False
        body = []
        while i < len(source) and depth > 0:
            ch = source[i]
            if in_str:
                if ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            body.append(ch)
            i += 1
        literals = re.findall(r"\"([^\"]*)\"", "".join(body))
        if literals:
            titles.add(literals[0])
    return titles

# indicator -> (required plot titles, required source patterns)
Coverage = dict[str, tuple[list[str], list[str]]]

OSCILLATORS: Coverage = {
    "Preset selector": ([], [r"preset\s*=\s*input\.string", r"isCustom"]),
    "DeMarker": (["DeMarker"], []),
    "DeMarker II": (["DeMarker II"], []),
    "TD Pressure Ratio": (["TD Pressure Ratio"], []),
    "TD Range Expansion Index": (["TD REI (0-100 scaled)"], [r"condA", r"condB"]),
    "TD POQ": (["TD POQ (scaled)"], []),
    "TD Alignment": (["TD Alignment (scaled)", "TD Alignment signal"], []),
    "TD Rate of Change": (["TD ROC (scaled)", "TD ROC signal"], []),
    "TD Oscillator": (["TD Oscillator (scaled)"], []),
}

SEQUENTIAL: Coverage = {
    "TD Setup": (["Buy 9", "Sell 9"], [r"buySetup", r"sellSetup"]),
    "TD Setup perfection": (["Buy 9 perfected", "Sell 9 perfected"], []),
    "TD Countdown": (["Buy 13", "Sell 13"], [r"buyCd", r"close <= low\[2\]"]),
    "TD Countdown deferral": (["Buy 13 deferred", "Sell 13 deferred"], []),
    "TD Combo": (["Combo Buy 13", "Combo Sell 13"], [r"strictThrough"]),
    "TD Sequential Ultimate (confluence)": (
        ["Buy 13 confluence", "Sell 13 confluence"],
        [],
    ),
    "TDST (countdown guard)": (["TDST Resistance", "TDST Support"], []),
    "TD Risk Level": (
        ["Buy risk level", "Sell risk level"],
        [r"buyLowestTrueLow", r"sellHighestTrueHigh"],
    ),
    "Preset selector": ([], [r"preset\s*=\s*input\.string", r"isCustom"]),
}

LEVELS: Coverage = {
    "Preset selector": ([], [r"preset\s*=\s*input\.string", r"isCustom"]),
    "TDST": ([], []),  # lives in v1, where the countdown needs it
    "TD Points": (["TD Point high", "TD Point low"], [r"ta\.pivothigh", r"ta\.pivotlow"]),
    "TD Lines": ([], [r"demandLine\b", r"supplyLine\b", r"demandLine2", r"supplyLine2"]),
    "DeMark Trendline": (["Demand projection", "Supply projection"], [r"line\.get_price"]),
    "TD Moving Average": (
        ["TD MA I", "TD MA II", "TD MA bullish cross", "TD MA bearish cross"],
        [r"maBullish", r"maTrendUp"],
    ),
    "TD Range Projection": (["Projected high", "Projected low"], []),
    "TD Retracements": (
        ["Swing high", "Swing low", "Up 38.2%", "Up 61.8%", "Down 38.2%", "Down 61.8%"],
        [r"retrQualifiedUp", r"retrQualifiedDown"],
    ),
    "TD D-Wave": ([], [r"f_waveName", r"addWavePivot", r"w3Extreme"]),
}

# The original type-based suites are still shipped alongside v1/v2/v3 for
# anyone who prefers that grouping. They predate the preset system and the TD
# Risk Level, so they carry their own expectations.
LEGACY_OSCILLATORS: Coverage = {
    k: v for k, v in OSCILLATORS.items() if k != "Preset selector"
}
LEGACY_SEQUENTIAL: Coverage = {
    k: v
    for k, v in SEQUENTIAL.items()
    if k not in ("Preset selector", "TD Risk Level")
}
LEGACY_LEVELS: Coverage = {
    k: v for k, v in LEVELS.items() if k != "Preset selector"
}
# TDST lives in the levels suite under the original grouping.
LEGACY_LEVELS["TDST"] = (
    ["TDST Resistance", "TDST Support"],
    [r"setupHighest", r"setupLowest"],
)

SUITES = [
    ("demark_v1_signals.pine", "v1 — Signals", SEQUENTIAL),
    ("demark_v2_trend_targets.pine", "v2 — Trend & Targets", LEVELS),
    ("demark_v3_momentum.pine", "v3 — Momentum", OSCILLATORS),
    ("all_sequential.pine", "Legacy suite — Sequential", LEGACY_SEQUENTIAL),
    ("all_levels_trend.pine", "Legacy suite — Levels & Trend", LEGACY_LEVELS),
    ("all_oscillators.pine", "Legacy suite — Oscillators", LEGACY_OSCILLATORS),
]

missing_total = 0


def check_suite(filename: str, label: str, coverage: Coverage) -> None:
    global missing_total
    path = PINE_DIR / filename
    if not path.exists():
        print(f"  ERROR {filename} not found")
        missing_total += 1
        return

    source = path.read_text()
    titles = plot_titles(source)

    print(f"\n{label}  ({filename})")
    for indicator, (need_titles, need_patterns) in coverage.items():
        problems: list[str] = []
        for t in need_titles:
            if t not in titles:
                problems.append(f'missing plot "{t}"')
        for p in need_patterns:
            if not re.search(p, source):
                problems.append(f"missing code /{p}/")
        if problems:
            missing_total += len(problems)
            print(f"  MISSING  {indicator}: {'; '.join(problems)}")
        else:
            print(f"  ok       {indicator}")


def main() -> None:
    print("Suite coverage check — every DeMark indicator must appear in its suite")

    for filename, label, coverage in SUITES:
        check_suite(filename, label, coverage)

    total = sum(len(c) for _, _, c in SUITES)
    print(f"\n{total} indicator entries checked across {len(SUITES)} suites")
    if missing_total:
        print(f"{missing_total} problem(s) found")
        raise SystemExit(1)
    print("All indicators are present in their suite.")


if __name__ == "__main__":
    main()
