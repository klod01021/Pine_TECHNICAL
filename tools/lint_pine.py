"""A small static checker for the Pine Script v6 files in ``/pine``.

TradingView has no offline compiler, so this catches the classes of mistake
that can be detected by inspection: reserved words used as identifiers,
missing or wrong version annotations, unbalanced brackets, bad indentation
and a few v5-era function names that no longer exist in v6.

It is not a substitute for pasting a script into the Pine Editor, but it
does prevent the obvious breakage.

    python3 tools/lint_pine.py
"""

from __future__ import annotations

import pathlib
import re
import sys

PINE_DIR = pathlib.Path(__file__).resolve().parent.parent / "pine"

# Words that cannot be used as identifiers: language keywords, type names and
# built-in namespaces.
RESERVED = {
    "and", "or", "not", "if", "else", "for", "to", "by", "while", "switch",
    "var", "varip", "true", "false", "na", "continue", "break", "return",
    "export", "import", "as", "type", "method", "enum",
    "series", "simple", "const", "input",
    "int", "float", "bool", "string",
    "color", "line", "label", "box", "table", "array", "matrix", "map",
    "linefill", "polyline", "chart", "strategy", "indicator", "library",
    "open", "high", "low", "close", "volume", "time", "bar_index", "hl2",
    "hlc3", "ohlc4", "syminfo", "timeframe", "ta", "math", "str", "request",
}

# Functions that existed in older versions but are wrong or gone in v6.
BAD_CALLS = {
    "ta.sum": "use math.sum",
    "iff": "use the ternary operator",
    "study": "use indicator()",
    "security": "use request.security",
    "rsi(": "use ta.rsi",
    "sma(": "use ta.sma",
    "ema(": "use ta.ema",
    "highest(": "use ta.highest",
    "lowest(": "use ta.lowest",
    "crossover(": "use ta.crossover",
    "pivothigh(": "use ta.pivothigh",
    "valuewhen(": "use ta.valuewhen",
}

ASSIGN_RE = re.compile(
    r"^\s*(?:var\s+|varip\s+)?"
    r"(?:(?:int|float|bool|string|color|line|label|box|table)\s+)?"
    r"(?:array<[^>]+>\s+|matrix<[^>]+>\s+|map<[^>]+>\s+)?"
    r"([A-Za-z_]\w*)\s*(?::=|=)(?!=)"
)
FUNC_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*\(([^)]*)\)\s*=>")

errors: list[str] = []
warnings: list[str] = []


def strip_comment(line: str) -> str:
    """Remove a trailing // comment, ignoring // inside string literals."""
    out = []
    in_str = False
    quote = ""
    i = 0
    while i < len(line):
        ch = line[i]
        if in_str:
            if ch == quote:
                in_str = False
            out.append(ch)
        else:
            if ch in "\"'":
                in_str = True
                quote = ch
                out.append(ch)
            elif ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                break
            else:
                out.append(ch)
        i += 1
    return "".join(out)


def check_file(path: pathlib.Path) -> None:
    raw = path.read_text().splitlines()
    name = path.name

    # --- version annotation ------------------------------------------------
    version_lines = [l for l in raw if l.strip().startswith("//@version")]
    if not version_lines:
        errors.append(f"{name}: missing //@version annotation")
    elif version_lines[0].strip() != "//@version=6":
        errors.append(f"{name}: expected //@version=6, found {version_lines[0].strip()}")

    # --- exactly one declaration -------------------------------------------
    decls = [
        l for l in raw
        if re.match(r"^(indicator|strategy|library)\s*\(", l.strip())
    ]
    if len(decls) != 1:
        errors.append(f"{name}: expected exactly 1 indicator() declaration, found {len(decls)}")

    depth = 0
    for lineno, raw_line in enumerate(raw, start=1):
        line = strip_comment(raw_line)
        if not line.strip():
            continue

        # --- bracket balance across the file -------------------------------
        depth += line.count("(") - line.count(")")
        depth += line.count("[") - line.count("]")

        # --- indentation must be a multiple of 4 ---------------------------
        indent = len(line) - len(line.lstrip(" "))
        if "\t" in raw_line[:indent]:
            errors.append(f"{name}:{lineno}: tab indentation (Pine requires spaces)")
        elif indent % 4 != 0:
            errors.append(f"{name}:{lineno}: indent of {indent} is not a multiple of 4")

        # --- removed / renamed calls ---------------------------------------
        for bad, hint in BAD_CALLS.items():
            pattern = r"(?<![.\w])" + re.escape(bad)
            if re.search(pattern, line):
                errors.append(f"{name}:{lineno}: '{bad}' is not valid in v6 ({hint})")

        # --- reserved words as identifiers ---------------------------------
        m = ASSIGN_RE.match(line)
        if m and m.group(1) in RESERVED:
            errors.append(f"{name}:{lineno}: '{m.group(1)}' is reserved and cannot be assigned")

        f = FUNC_RE.match(line)
        if f:
            if f.group(1) in RESERVED:
                errors.append(f"{name}:{lineno}: function name '{f.group(1)}' is reserved")
            for param in f.group(2).split(","):
                pname = param.split("=")[0].strip()
                if pname and pname in RESERVED:
                    errors.append(
                        f"{name}:{lineno}: parameter '{pname}' is a reserved word"
                    )

    if depth != 0:
        errors.append(f"{name}: unbalanced brackets (net depth {depth})")


def main() -> None:
    files = sorted(PINE_DIR.glob("*.pine"))
    if not files:
        print(f"No .pine files found in {PINE_DIR}")
        raise SystemExit(1)

    for path in files:
        check_file(path)

    print(f"Checked {len(files)} Pine v6 scripts\n")
    for w in warnings:
        print(f"  warn  {w}")
    for e in errors:
        print(f"  ERROR {e}")

    if errors:
        print(f"\n{len(errors)} error(s)")
        raise SystemExit(1)
    print("No problems found.")


if __name__ == "__main__":
    main()
