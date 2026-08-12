"""
DeMark Indicators for Python
============================

A from-scratch implementation of Tom DeMark's indicator library.

Every function takes a pandas OHLC DataFrame (columns: open, high, low, close)
and returns a DataFrame of indicator values, so each output can be compared
bar-for-bar against the matching Pine Script v6 script in ``/pine``.

Indicator catalogue
-------------------

Oscillators
    - demarker                    DeMarker (DeM), 0-100 bounded oscillator
    - demarker_ii                 DeMarker II, close/midpoint variant
    - td_pressure_ratio           TD Pressure Ratio (buying / selling pressure)
    - td_range_expansion_index    TD Range Expansion Index (TDREI)
    - td_poq                      TD Price Oscillator Qualifier
    - td_alignment                TD Alignment Oscillator
    - td_roc                      TD Rate of Change
    - td_oscillator               TD Oscillator

TD Sequential family
    - td_setup                    TD Buy/Sell Setup counts 1-9
    - td_countdown                Classic TD Countdown 1-13
    - td_combo                    TD Combo Countdown 1-13
    - td_sequential_ultimate      Sequential with qualifier filters and
                                  aggressive / conservative 13s

Levels and trend
    - td_setup_trend              TDST support / resistance levels
    - td_points                   Qualified TD Point highs and lows
    - td_lines                    TD Supply / Demand lines (levels 1-3)
    - td_moving_average           TD Moving Average I and II
    - td_range_projection         Next-bar projected high / low
    - td_retracements             TD Relative Retracement / Arc magnet levels
    - demark_trendline            Qualified DeMark trendlines with projections

Wave counting
    - td_d_wave                   TD D-Wave (Elliott-style wave count)

Helpers
    - load_ohlc_csv               Load a CSV into the expected DataFrame shape
"""

from .oscillators import (
    demarker,
    demarker_ii,
    td_pressure_ratio,
    td_range_expansion_index,
    td_poq,
    td_alignment,
    td_roc,
    td_oscillator,
)
from .sequential import (
    td_setup,
    td_countdown,
    td_combo,
    td_sequential_ultimate,
)
from .levels import (
    td_setup_trend,
    td_points,
    td_lines,
    td_retracements,
    demark_trendline,
)
from .moving_averages import td_moving_average
from .range_projection import td_range_projection
from .d_wave import td_d_wave
from .data import load_ohlc_csv

__version__ = "1.0.0"

__all__ = [
    "demarker",
    "demarker_ii",
    "td_pressure_ratio",
    "td_range_expansion_index",
    "td_poq",
    "td_alignment",
    "td_roc",
    "td_oscillator",
    "td_setup",
    "td_countdown",
    "td_combo",
    "td_sequential_ultimate",
    "td_setup_trend",
    "td_points",
    "td_lines",
    "td_retracements",
    "demark_trendline",
    "td_moving_average",
    "td_range_projection",
    "td_d_wave",
    "load_ohlc_csv",
]
