"""Verify the three combined suites cover every DeMark indicator.

Each of the 20 indicators is mapped to the evidence that must appear in its
suite: plot/plotshape titles for anything drawn as a series, and source
patterns for tools drawn with line.new / label.new (TD Lines, TD D-Wave).

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
}

LEVELS: Coverage = {
    "TDST": (["TDST Resistance", "TDST Support"], [r"setupHighest", r"setupLowest"]),
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

SUITES = [
    ("all_oscillators.pine", "Oscillators", OSCILLATORS),
    ("all_sequential.pine", "Sequential", SEQUENTIAL),
    ("all_levels_trend.pine", "Levels & Trend", LEVELS),
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
