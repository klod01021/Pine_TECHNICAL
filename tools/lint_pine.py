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

# Stateful ta.* functions keep an internal buffer and must be evaluated on
# every bar. Calling them inside an if/for body or a ternary branch silently
# corrupts that buffer.
STATEFUL_TA = (
    "highest", "lowest", "sma", "ema", "rma", "wma", "vwma", "swma", "hma",
    "atr", "rsi", "stdev", "variance", "mom", "change", "roc", "cum",
    "crossover", "crossunder", "cross", "barssince", "valuewhen", "pivothigh",
    "pivotlow", "linreg", "correlation", "percentrank", "percentile_linear_interpolation",
    "bb", "bbw", "cci", "cmo", "dmi", "macd", "mfi", "sar", "stoch", "supertrend",
    "tr", "tsi", "wpr", "falling", "rising", "median", "mode", "range",
)
STATEFUL_TA_RE = re.compile(r"\bta\.(" + "|".join(STATEFUL_TA) + r")\s*\(")
# math.sum keeps a rolling window too.
ROLLING_MATH_RE = re.compile(r"\bmath\.sum\s*\(")
# ta.* length arguments must be `simple int`; a user function parameter is
# always `series int`, so it can never be passed as one.
LENGTH_TA_RE = re.compile(
    r"\bta\.(?:highest|lowest|sma|ema|rma|wma|vwma|atr|rsi|stdev|linreg|mom|roc|"
    r"percentrank|pivothigh|pivotlow)\s*\(\s*([^,()]+)\s*,\s*([A-Za-z_]\w*)\s*\)"
)

errors: list[str] = []
warnings: list[str] = []


def in_function_body(raw: list[str], lineno: int) -> bool:
    """True when line ``lineno`` (1-based) sits inside a user function body.

    A function body is safe for stateful ta.* calls provided the function is
    itself invoked on every bar, which is the normal case; a conditional block
    is not.
    """
    for i in range(lineno - 2, -1, -1):
        candidate = strip_comment(raw[i])
        if not candidate.strip():
            continue
        if len(candidate) - len(candidate.lstrip(" ")) == 0:
            return bool(FUNC_RE.match(candidate))
    return False


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

    # Collect user-function parameter names so we can spot them being passed
    # as a ta.* length argument.
    func_params: set[str] = set()
    for l in raw:
        fm = FUNC_RE.match(strip_comment(l))
        if fm:
            for param in fm.group(2).split(","):
                pname = param.split("=")[0].strip()
                if pname:
                    func_params.add(pname)

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

        # --- stateful ta.* inside a conditional body ------------------------
        # Indented code is inside an if/else/for body or a function; only the
        # latter is safe, and only when the function is called every bar.
        if indent > 0 and not in_function_body(raw, lineno):
            hit = STATEFUL_TA_RE.search(line) or ROLLING_MATH_RE.search(line)
            if hit:
                errors.append(
                    f"{name}:{lineno}: '{hit.group(0).rstrip('(')}' is stateful and must be "
                    f"called on every bar; hoist it out of the conditional block"
                )

        # --- ta.* length argument that is a function parameter --------------
        lm = LENGTH_TA_RE.search(line)
        if lm and lm.group(2) in func_params:
            errors.append(
                f"{name}:{lineno}: length argument '{lm.group(2)}' is a function parameter "
                f"(series int), but ta.* requires a simple int"
            )

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
