"""Data loading helpers for the DeMark indicator library."""

from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = ("open", "high", "low", "close")


def validate_ohlc(df: pd.DataFrame, name: str = "df") -> pd.DataFrame:
    """Return ``df`` unchanged after checking it has OHLC columns.

    Raises
    ------
    TypeError
        If ``df`` is not a pandas DataFrame.
    ValueError
        If any required column is missing.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{name} must be a pandas DataFrame, got {type(df)!r}")
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")
    return df


def load_ohlc_csv(path: str, time_column: str | None = "time") -> pd.DataFrame:
    """Load an OHLC CSV exported from TradingView (or similar).

    The CSV must contain at least the columns ``open``, ``high``, ``low``,
    ``close`` (case-insensitive). If ``time_column`` names a column it is
    parsed as a datetime index; otherwise a plain integer index is kept.
    """
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    validate_ohlc(df, name=path)
    if time_column and time_column.lower() in df.columns:
        df[time_column.lower()] = pd.to_datetime(df[time_column.lower()], unit="s", errors="coerce")
        if df[time_column.lower()].isna().all():
            df[time_column.lower()] = pd.to_datetime(df[time_column.lower()], errors="coerce")
        df = df.set_index(time_column.lower())
    return df
